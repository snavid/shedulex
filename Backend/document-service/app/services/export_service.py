from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from time import perf_counter

import httpx
from flask import current_app
from sqlalchemy import Float, cast, func

from app.extensions import db
from app.models import ExportEvent
from app.services.excel_service import generate_timetable_excel
from app.services.export_cache import export_cache
from app.services.pdf_service import generate_timetable_pdf


PDF_FORMAT = "pdf"
EXCEL_FORMAT = "excel"
CSV_FORMAT = "csv"
BUNDLE_FORMAT = "bundle"
SUPPORTED_EXPORT_FORMATS = (PDF_FORMAT, EXCEL_FORMAT, CSV_FORMAT)

MIMETYPES = {
    PDF_FORMAT: "application/pdf",
    EXCEL_FORMAT: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    CSV_FORMAT: "text/csv",
    BUNDLE_FORMAT: "application/zip",
}

EXTENSIONS = {
    PDF_FORMAT: "pdf",
    EXCEL_FORMAT: "xlsx",
    CSV_FORMAT: "csv",
    BUNDLE_FORMAT: "zip",
}

CSV_COLUMNS = ["Day", "Start", "End", "Course Code", "Course Name", "Lecturer", "Room", "Students"]


def _internal_headers() -> dict:
    return {"X-Internal-Service-Key": current_app.config["INTERNAL_SERVICE_KEY"]}


def _short_id(entity_id: str) -> str:
    return entity_id[:8]


def _filename(timetable_id: str, export_format: str) -> str:
    return f"timetable-{_short_id(timetable_id)}.{EXTENSIONS[export_format]}"


def _timetable_to_csv(entries: list[dict]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for entry in entries:
        slot = entry.get("time_slot", {})
        course = entry.get("course", {})
        lecturer = entry.get("lecturer", {})
        room = entry.get("room", {})
        writer.writerow([
            slot.get("day"), slot.get("start_time"), slot.get("end_time"),
            course.get("code"), course.get("name"),
            lecturer.get("name"), room.get("code"), course.get("student_count"),
        ])
    return output.getvalue().encode("utf-8")


def _generate_payload(timetable: dict, export_format: str) -> bytes:
    if export_format == PDF_FORMAT:
        return generate_timetable_pdf(timetable)
    if export_format == EXCEL_FORMAT:
        return generate_timetable_excel(timetable)
    if export_format == CSV_FORMAT:
        return _timetable_to_csv(timetable.get("entries", []))
    raise ValueError(f"Unsupported export format '{export_format}'.")


def _timetable_signature(timetable: dict, export_format: str) -> str:
    minimal = {
        "format": export_format,
        "id": timetable.get("id"),
        "version": timetable.get("version"),
        "fitness_score": timetable.get("fitness_score"),
        "generation_time_seconds": timetable.get("generation_time_seconds"),
        "entries": [
            {
                "course": (entry.get("course") or {}).get("id"),
                "room": (entry.get("room") or {}).get("id"),
                "lecturer": (entry.get("lecturer") or {}).get("id"),
                "slot": (entry.get("time_slot") or {}).get("id"),
            }
            for entry in timetable.get("entries", [])
        ],
    }
    encoded = json.dumps(minimal, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _record_event(
    *,
    timetable_id: str,
    export_format: str,
    delivery_channel: str,
    requested_by: str | None,
    cache_hit: bool,
    duration_ms: int,
    size_bytes: int,
    status: str,
    error_message: str | None = None,
):
    try:
        event = ExportEvent(
            timetable_id=timetable_id,
            export_format=export_format,
            delivery_channel=delivery_channel,
            requested_by=requested_by,
            cache_hit=cache_hit,
            duration_ms=duration_ms,
            size_bytes=size_bytes,
            status=status,
            error_message=(error_message or "")[:500] or None,
        )
        db.session.add(event)
        db.session.commit()
    except Exception:
        # Telemetry should not break export workflows.
        db.session.rollback()
        current_app.logger.exception(
            "Failed to record export event (timetable_id=%s, format=%s, status=%s)",
            timetable_id,
            export_format,
            status,
        )


def _fetch_timetable(timetable_id: str) -> dict:
    timeout_seconds = 30
    timetable_url = current_app.config["TIMETABLE_SERVICE_URL"]
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(
            f"{timetable_url}/api/v1/timetable/{timetable_id}",
            headers=_internal_headers(),
        )
        response.raise_for_status()
        return response.json().get("data", {})


def _export_from_timetable(
    *,
    timetable: dict,
    export_format: str,
    timetable_id: str,
    requested_by: str | None,
    delivery_channel: str,
    log_event: bool,
) -> dict:
    started = perf_counter()
    cache_hit = False
    try:
        etag = _timetable_signature(timetable, export_format)
        cache_key = f"{timetable_id}:{export_format}:{etag}"
        payload = export_cache.get(cache_key)
        if payload is None:
            payload = _generate_payload(timetable, export_format)
            export_cache.set(cache_key, payload, current_app.config["EXPORT_CACHE_TTL_SECONDS"])
        else:
            cache_hit = True

        duration_ms = int((perf_counter() - started) * 1000)
        size_bytes = len(payload)
        if log_event:
            _record_event(
                timetable_id=timetable_id,
                export_format=export_format,
                delivery_channel=delivery_channel,
                requested_by=requested_by,
                cache_hit=cache_hit,
                duration_ms=duration_ms,
                size_bytes=size_bytes,
                status="success",
            )
        return {
            "payload": payload,
            "mimetype": MIMETYPES[export_format],
            "filename": _filename(timetable_id, export_format),
            "etag": etag,
            "cache_hit": cache_hit,
            "duration_ms": duration_ms,
            "size_bytes": size_bytes,
        }
    except Exception as exc:
        duration_ms = int((perf_counter() - started) * 1000)
        if log_event:
            _record_event(
                timetable_id=timetable_id,
                export_format=export_format,
                delivery_channel=delivery_channel,
                requested_by=requested_by,
                cache_hit=False,
                duration_ms=duration_ms,
                size_bytes=0,
                status="failed",
                error_message=str(exc),
            )
        raise


def export_document(
    *,
    timetable_id: str,
    export_format: str,
    requested_by: str | None = None,
    delivery_channel: str = "download",
) -> dict:
    if export_format not in SUPPORTED_EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format '{export_format}'.")
    timetable = _fetch_timetable(timetable_id)
    return _export_from_timetable(
        timetable=timetable,
        export_format=export_format,
        timetable_id=timetable_id,
        requested_by=requested_by,
        delivery_channel=delivery_channel,
        log_event=True,
    )


def export_bundle(
    *,
    timetable_id: str,
    requested_by: str | None = None,
    delivery_channel: str = "download",
    formats: list[str] | None = None,
) -> dict:
    selected_formats = formats or list(SUPPORTED_EXPORT_FORMATS)
    clean_formats = [f for f in selected_formats if f in SUPPORTED_EXPORT_FORMATS]
    if not clean_formats:
        raise ValueError("No valid formats supplied for bundle export.")

    started = perf_counter()
    try:
        timetable = _fetch_timetable(timetable_id)

        exports: list[dict] = []
        for export_format in clean_formats:
            exports.append(
                _export_from_timetable(
                    timetable=timetable,
                    export_format=export_format,
                    timetable_id=timetable_id,
                    requested_by=requested_by,
                    delivery_channel=delivery_channel,
                    log_event=False,
                )
            )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for item in exports:
                zipf.writestr(item["filename"], item["payload"])
            metadata = {
                "timetable_id": timetable.get("id") or timetable_id,
                "name": timetable.get("name"),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "formats": [f for f in clean_formats],
                "entries_count": len(timetable.get("entries", [])),
            }
            zipf.writestr("metadata.json", json.dumps(metadata, indent=2))

        payload = zip_buffer.getvalue()
        duration_ms = int((perf_counter() - started) * 1000)
        etag_seed = "".join(item["etag"] for item in exports).encode("utf-8")
        etag = hashlib.sha256(etag_seed).hexdigest()

        _record_event(
            timetable_id=timetable_id,
            export_format=BUNDLE_FORMAT,
            delivery_channel=delivery_channel,
            requested_by=requested_by,
            cache_hit=all(item["cache_hit"] for item in exports),
            duration_ms=duration_ms,
            size_bytes=len(payload),
            status="success",
        )

        return {
            "payload": payload,
            "mimetype": MIMETYPES[BUNDLE_FORMAT],
            "filename": _filename(timetable_id, BUNDLE_FORMAT),
            "etag": etag,
            "cache_hit": all(item["cache_hit"] for item in exports),
            "duration_ms": duration_ms,
            "size_bytes": len(payload),
            "formats": clean_formats,
        }
    except Exception as exc:
        _record_event(
            timetable_id=timetable_id,
            export_format=BUNDLE_FORMAT,
            delivery_channel=delivery_channel,
            requested_by=requested_by,
            cache_hit=False,
            duration_ms=int((perf_counter() - started) * 1000),
            size_bytes=0,
            status="failed",
            error_message=str(exc),
        )
        raise


def preview_exports(timetable_id: str) -> dict:
    timetable = _fetch_timetable(timetable_id)
    entries = timetable.get("entries", [])
    lecturers = {(entry.get("lecturer") or {}).get("id") for entry in entries if (entry.get("lecturer") or {}).get("id")}
    rooms = {(entry.get("room") or {}).get("id") for entry in entries if (entry.get("room") or {}).get("id")}
    day_distribution = {day: 0 for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")}
    for entry in entries:
        day = (entry.get("time_slot") or {}).get("day")
        if day in day_distribution:
            day_distribution[day] += 1
    peak_day = max(day_distribution.items(), key=lambda item: item[1])[0] if entries else None

    recommendations = [
        "Use PDF for official circulation and print-ready sharing.",
        "Use Excel for manual edits and bulk analysis.",
        "Use ZIP bundle for one-click multi-format distribution.",
    ]
    if len(entries) >= 30:
        recommendations.append("Large timetable detected: Excel is recommended for fast filtering.")

    fitness = float(timetable.get("fitness_score") or 0)
    if fitness < 0.8:
        recommendations.append("Fitness score is below 0.80: use bundle export for cross-team review and validation.")

    if len(entries) >= 45:
        recommended_format = EXCEL_FORMAT
        complexity_tier = "high"
    elif len(entries) >= 20:
        recommended_format = BUNDLE_FORMAT
        complexity_tier = "medium"
    else:
        recommended_format = PDF_FORMAT
        complexity_tier = "low"

    return {
        "timetable": {
            "id": timetable.get("id"),
            "name": timetable.get("name"),
            "department": (timetable.get("department") or {}).get("name"),
            "semester": timetable.get("semester"),
            "academic_year": timetable.get("academic_year"),
            "fitness_score": timetable.get("fitness_score"),
        },
        "summary": {
            "total_sessions": len(entries),
            "total_lecturers": len(lecturers),
            "total_rooms": len(rooms),
            "peak_day": peak_day,
        },
        "insights": {
            "complexity_tier": complexity_tier,
            "recommended_format": recommended_format,
            "fitness_score": fitness,
            "day_distribution": day_distribution,
        },
        "exports": [
            {"format": PDF_FORMAT, "filename": _filename(timetable_id, PDF_FORMAT), "mimetype": MIMETYPES[PDF_FORMAT]},
            {"format": EXCEL_FORMAT, "filename": _filename(timetable_id, EXCEL_FORMAT), "mimetype": MIMETYPES[EXCEL_FORMAT]},
            {"format": CSV_FORMAT, "filename": _filename(timetable_id, CSV_FORMAT), "mimetype": MIMETYPES[CSV_FORMAT]},
            {"format": BUNDLE_FORMAT, "filename": _filename(timetable_id, BUNDLE_FORMAT), "mimetype": MIMETYPES[BUNDLE_FORMAT]},
        ],
        "recommendations": recommendations,
    }


def export_analytics(limit: int = 20) -> dict:
    limit = max(1, min(limit, 200))
    total = ExportEvent.query.count()
    failed = ExportEvent.query.filter_by(status="failed").count()

    by_format_rows = (
        db.session.query(
            ExportEvent.export_format,
            func.count(ExportEvent.id),
            func.avg(ExportEvent.duration_ms),
            func.avg(cast(ExportEvent.cache_hit, Float)),
            func.sum(ExportEvent.size_bytes),
        )
        .group_by(ExportEvent.export_format)
        .all()
    )

    by_channel_rows = (
        db.session.query(ExportEvent.delivery_channel, func.count(ExportEvent.id))
        .group_by(ExportEvent.delivery_channel)
        .all()
    )

    recent = (
        ExportEvent.query
        .order_by(ExportEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "total_exports": total,
        "failed_exports": failed,
        "success_rate": round(((total - failed) / total) * 100, 2) if total else 100.0,
        "by_format": [
            {
                "format": fmt,
                "count": int(count or 0),
                "avg_duration_ms": round(float(avg_duration or 0), 2),
                "cache_hit_rate_pct": round(float((avg_cache_hit or 0) * 100), 2),
                "total_size_bytes": int(total_size or 0),
            }
            for fmt, count, avg_duration, avg_cache_hit, total_size in by_format_rows
        ],
        "by_channel": [
            {"channel": channel, "count": int(count or 0)}
            for channel, count in by_channel_rows
        ],
        "recent_events": [event.to_dict() for event in recent],
    }

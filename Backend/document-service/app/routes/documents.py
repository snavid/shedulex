import re

from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.services.export_security import create_share_token, decode_share_token
from app.services.export_service import (
    BUNDLE_FORMAT,
    CSV_FORMAT,
    EXCEL_FORMAT,
    PDF_FORMAT,
    export_analytics,
    export_bundle,
    export_document,
    preview_exports,
)

documents_bp = Blueprint("documents", __name__, url_prefix="/api/v1/documents")

MANAGER_ROLES = {"admin", "timetable_officer", "hod"}


def _json_ok(data=None, message=None, status=200):
    payload = {"success": True}
    if message is not None:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status


def _json_error(message: str, status=400):
    return jsonify({"success": False, "message": message}), status


def _is_manager() -> bool:
    claims = get_jwt()
    roles = set()
    role = claims.get("role")
    if isinstance(role, str):
        roles.add(role.lower())

    role_list = claims.get("roles")
    if isinstance(role_list, (list, tuple, set)):
        for item in role_list:
            if isinstance(item, str):
                roles.add(item.lower())

    return bool(roles & MANAGER_ROLES)


def _normalize_if_none_match(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("W/"):
        normalized = normalized[2:]
    return normalized.strip().strip('"')


def _etag_or_304(etag: str):
    incoming = request.headers.get("If-None-Match")
    if incoming and _normalize_if_none_match(incoming) == etag:
        return Response(status=304, headers={"ETag": f'"{etag}"'})
    return None


def _download_response(result: dict, *, cache_control: str = "private, max-age=300"):
    maybe_304 = _etag_or_304(result["etag"])
    if maybe_304:
        return maybe_304

    headers = {
        "Content-Disposition": f'attachment; filename="{result["filename"]}"',
        "Content-Length": str(result["size_bytes"]),
        "ETag": f'"{result["etag"]}"',
        "Cache-Control": cache_control,
        "X-Export-Cache": "HIT" if result["cache_hit"] else "MISS",
        "X-Export-Duration-Ms": str(result["duration_ms"]),
    }
    return Response(result["payload"], mimetype=result["mimetype"], headers=headers)


def _formats_from_query() -> list[str]:
    raw = request.args.get("formats", f"{PDF_FORMAT},{EXCEL_FORMAT},{CSV_FORMAT}")
    if not raw:
        return [PDF_FORMAT, EXCEL_FORMAT, CSV_FORMAT]
    parsed = [token.strip().lower() for token in re.split(r"[,\s]+", raw) if token.strip()]
    return parsed or [PDF_FORMAT, EXCEL_FORMAT, CSV_FORMAT]


def _parse_positive_int(value, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")
    return parsed


def _share_url(token: str) -> str:
    relative = f"/api/v1/documents/share/{token}"
    public_base = (current_app.config.get("DOCUMENT_PUBLIC_BASE_URL") or "").rstrip("/")
    if public_base:
        return f"{public_base}{relative}"
    return relative


@documents_bp.get("/timetable/<timetable_id>/preview")
@jwt_required()
def export_preview(timetable_id):
    try:
        preview = preview_exports(timetable_id)
        return _json_ok(preview)
    except Exception:
        current_app.logger.exception("Failed to load export preview for timetable_id=%s", timetable_id)
        return _json_error("Failed to load export preview.", status=400)


@documents_bp.get("/timetable/<timetable_id>/pdf")
@jwt_required()
def download_pdf(timetable_id):
    try:
        result = export_document(
            timetable_id=timetable_id,
            export_format=PDF_FORMAT,
            requested_by=get_jwt_identity(),
            delivery_channel="download",
        )
        return _download_response(result)
    except Exception:
        current_app.logger.exception("Failed to generate PDF export for timetable_id=%s", timetable_id)
        return _json_error("Failed to generate PDF export.", status=400)


@documents_bp.get("/timetable/<timetable_id>/excel")
@jwt_required()
def download_excel(timetable_id):
    try:
        result = export_document(
            timetable_id=timetable_id,
            export_format=EXCEL_FORMAT,
            requested_by=get_jwt_identity(),
            delivery_channel="download",
        )
        return _download_response(result)
    except Exception:
        current_app.logger.exception("Failed to generate Excel export for timetable_id=%s", timetable_id)
        return _json_error("Failed to generate Excel export.", status=400)


@documents_bp.get("/timetable/<timetable_id>/csv")
@jwt_required()
def download_csv(timetable_id):
    try:
        result = export_document(
            timetable_id=timetable_id,
            export_format=CSV_FORMAT,
            requested_by=get_jwt_identity(),
            delivery_channel="download",
        )
        return _download_response(result)
    except Exception:
        current_app.logger.exception("Failed to generate CSV export for timetable_id=%s", timetable_id)
        return _json_error("Failed to generate CSV export.", status=400)


@documents_bp.get("/timetable/<timetable_id>/bundle")
@jwt_required()
def download_bundle(timetable_id):
    try:
        result = export_bundle(
            timetable_id=timetable_id,
            requested_by=get_jwt_identity(),
            delivery_channel="download",
            formats=_formats_from_query(),
        )
        return _download_response(result)
    except Exception:
        current_app.logger.exception("Failed to generate bundle export for timetable_id=%s", timetable_id)
        return _json_error("Failed to generate bundle export.", status=400)


@documents_bp.post("/share-links")
@jwt_required()
def create_share_link():
    if not _is_manager():
        return _json_error("Forbidden.", status=403)

    body = request.get_json() or {}
    timetable_id = str(body.get("timetable_id", "")).strip()
    export_format = str(body.get("format", BUNDLE_FORMAT)).strip().lower()
    expires_cap = int(current_app.config["EXPORT_SHARE_TOKEN_MAX_HOURS"])
    try:
        expires_hours = _parse_positive_int(body.get("expires_hours", 24), "expires_hours")
    except ValueError as exc:
        return _json_error(str(exc), status=422)

    if not timetable_id:
        return _json_error("timetable_id is required.", status=422)
    if export_format not in {PDF_FORMAT, EXCEL_FORMAT, CSV_FORMAT, BUNDLE_FORMAT}:
        return _json_error("Invalid export format.", status=422)
    if expires_hours > expires_cap:
        return _json_error(f"expires_hours exceeds max allowed ({expires_cap}).", status=422)

    token, expires_at = create_share_token(
        timetable_id=timetable_id,
        export_format=export_format,
        expires_hours=expires_hours,
        issued_by=get_jwt_identity(),
    )
    return _json_ok(
        data={
            "token": token,
            "download_url": _share_url(token),
            "expires_at": expires_at,
            "format": export_format,
            "timetable_id": timetable_id,
        },
        message="Share link created successfully.",
        status=201,
    )


@documents_bp.get("/share/<token>")
def download_shared(token):
    try:
        payload = decode_share_token(token)
    except ValueError as exc:
        return _json_error(str(exc), status=401)

    timetable_id = payload["tid"]
    export_format = payload["fmt"]

    try:
        if export_format == BUNDLE_FORMAT:
            result = export_bundle(
                timetable_id=timetable_id,
                requested_by=payload.get("iss"),
                delivery_channel="share",
            )
        else:
            result = export_document(
                timetable_id=timetable_id,
                export_format=export_format,
                requested_by=payload.get("iss"),
                delivery_channel="share",
            )
        return _download_response(result, cache_control="private, max-age=120")
    except Exception:
        current_app.logger.exception("Failed to generate shared export for timetable_id=%s", timetable_id)
        return _json_error("Failed to generate shared export.", status=400)


@documents_bp.get("/analytics/overview")
@jwt_required()
def document_analytics():
    if not _is_manager():
        return _json_error("Forbidden.", status=403)
    limit = request.args.get("limit", default=20, type=int)
    analytics = export_analytics(limit=limit)
    return _json_ok(data=analytics)

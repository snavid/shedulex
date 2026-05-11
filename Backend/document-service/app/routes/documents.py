import os
import httpx
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required

documents_bp = Blueprint("documents", __name__, url_prefix="/api/v1/documents")

TIMETABLE_URL = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")


def _fetch_timetable(timetable_id: str) -> dict:
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{TIMETABLE_URL}/api/v1/timetable/{timetable_id}")
        resp.raise_for_status()
        return resp.json().get("data", {})


@documents_bp.get("/timetable/<timetable_id>/pdf")
@jwt_required()
def download_pdf(timetable_id):
    try:
        timetable = _fetch_timetable(timetable_id)
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to fetch timetable: {e}"}), 400

    from app.services.pdf_service import generate_timetable_pdf
    pdf_bytes = generate_timetable_pdf(timetable)
    filename = f"timetable-{timetable_id[:8]}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@documents_bp.get("/timetable/<timetable_id>/excel")
@jwt_required()
def download_excel(timetable_id):
    try:
        timetable = _fetch_timetable(timetable_id)
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to fetch timetable: {e}"}), 400

    from app.services.excel_service import generate_timetable_excel
    excel_bytes = generate_timetable_excel(timetable)
    filename = f"timetable-{timetable_id[:8]}.xlsx"
    return Response(
        excel_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@documents_bp.get("/timetable/<timetable_id>/csv")
@jwt_required()
def download_csv(timetable_id):
    try:
        timetable = _fetch_timetable(timetable_id)
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to fetch timetable: {e}"}), 400

    import csv, io
    entries = timetable.get("entries", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Day", "Start", "End", "Course Code", "Course Name", "Lecturer", "Room", "Students"])
    for e in entries:
        slot = e.get("time_slot", {})
        course = e.get("course", {})
        lecturer = e.get("lecturer", {})
        room = e.get("room", {})
        writer.writerow([
            slot.get("day"), slot.get("start_time"), slot.get("end_time"),
            course.get("code"), course.get("name"),
            lecturer.get("name"), room.get("code"), course.get("student_count"),
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=timetable-{timetable_id[:8]}.csv"},
    )

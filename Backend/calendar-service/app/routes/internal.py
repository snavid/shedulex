import secrets
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models.event import AcademicEvent

internal_bp = Blueprint("internal", __name__, url_prefix="/api/v1/calendar/internal")
LOCAL_TZ = ZoneInfo("Africa/Dar_es_Salaam")


def _require_internal_key():
    expected = current_app.config.get("INTERNAL_SERVICE_KEY")
    provided = request.headers.get("X-Internal-Service-Key", "")
    if not expected or not provided or not secrets.compare_digest(provided, expected):
        return jsonify({"success": False, "message": "Forbidden."}), 403
    return None


@internal_bp.get("/events/today")
def events_today():
    denied = _require_internal_key()
    if denied:
        return denied

    university_id = request.args.get("university_id")
    now_local = datetime.now(LOCAL_TZ)
    day_start = datetime.combine(now_local.date(), time.min, tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    day_end = datetime.combine(now_local.date(), time.max, tzinfo=LOCAL_TZ).astimezone(timezone.utc)

    q = AcademicEvent.query.filter(
        AcademicEvent.is_cancelled.is_(False),
        AcademicEvent.start_datetime >= day_start,
        AcademicEvent.start_datetime <= day_end,
    )
    if university_id:
        q = q.filter_by(university_id=university_id)

    events = q.order_by(AcademicEvent.start_datetime.asc()).all()
    return jsonify({"success": True, "data": [e.to_dict() for e in events]}), 200

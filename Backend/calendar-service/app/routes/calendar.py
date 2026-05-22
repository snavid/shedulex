from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, date
from app.extensions import db
from app.models.event import AcademicEvent, AcademicHoliday, AcademicSemester

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/v1/calendar")

ADMIN_ROLES = ("admin",)
WRITE_ROLES = ("admin", "timetable_officer", "hod")


# ── Calendar Events ───────────────────────────────────────────────────────────

@calendar_bp.get("/events")
@jwt_required()
def list_events():
    start = request.args.get("start")
    end = request.args.get("end")
    event_type = request.args.get("type")
    dept = request.args.get("department_id")
    university_id = request.args.get("university_id")
    program_id = request.args.get("program_id")
    student_group_id = request.args.get("student_group_id")
    include_cancelled = request.args.get("include_cancelled", "false").lower() == "true"

    q = AcademicEvent.query
    if start:
        q = q.filter(AcademicEvent.start_datetime >= datetime.fromisoformat(start))
    if end:
        q = q.filter(AcademicEvent.start_datetime <= datetime.fromisoformat(end))
    if event_type:
        q = q.filter_by(event_type=event_type)
    if dept:
        q = q.filter_by(department_id=dept)
    if university_id:
        q = q.filter_by(university_id=university_id)
    if program_id:
        q = q.filter_by(program_id=program_id)
    if student_group_id:
        q = q.filter_by(student_group_id=student_group_id)
    if not include_cancelled:
        q = q.filter_by(is_cancelled=False)

    events = q.order_by(AcademicEvent.start_datetime).all()
    return jsonify({"success": True, "data": [e.to_dict() for e in events]}), 200


@calendar_bp.post("/events")
@jwt_required()
def create_event():
    claims = get_jwt()
    role = claims.get("role", "")
    body = request.get_json() or {}

    affects_timetable = body.get("affects_timetable", False)
    # Only admins/officers may create timetable-affecting events
    if affects_timetable and role not in WRITE_ROLES:
        return jsonify({"success": False, "message": "Forbidden."}), 403

    evt = AcademicEvent(
        title=body["title"],
        description=body.get("description"),
        event_type=body.get("event_type", "event"),
        start_datetime=datetime.fromisoformat(body["start"]),
        end_datetime=datetime.fromisoformat(body["end"]) if body.get("end") else None,
        all_day=body.get("all_day", False),
        location=body.get("location"),
        department_id=body.get("department_id"),
        course_id=body.get("course_id"),
        lecturer_id=body.get("lecturer_id"),
        created_by=get_jwt_identity(),
        is_public=body.get("is_public", True),
        color=body.get("color", "#3B82F6"),
        recurrence=body.get("recurrence", "none"),
        university_id=body.get("university_id"),
        student_group_id=body.get("student_group_id"),
        program_id=body.get("program_id"),
        affects_timetable=affects_timetable,
        timetable_scope=body.get("timetable_scope"),
    )
    db.session.add(evt)
    db.session.commit()
    return jsonify({"success": True, "data": evt.to_dict()}), 201


@calendar_bp.put("/events/<event_id>")
@jwt_required()
def update_event(event_id):
    evt = AcademicEvent.query.get_or_404(event_id)
    body = request.get_json() or {}
    for k in ("title", "description", "event_type", "location", "color",
              "recurrence", "is_public", "affects_timetable", "timetable_scope"):
        if k in body:
            setattr(evt, k, body[k])
    if "start" in body:
        evt.start_datetime = datetime.fromisoformat(body["start"])
    if "end" in body:
        evt.end_datetime = datetime.fromisoformat(body["end"])
    db.session.commit()
    return jsonify({"success": True, "data": evt.to_dict()}), 200


@calendar_bp.patch("/events/<event_id>/cancel")
@jwt_required()
def cancel_event(event_id):
    evt = AcademicEvent.query.get_or_404(event_id)
    body = request.get_json() or {}
    evt.is_cancelled = True
    evt.cancelled_by = get_jwt_identity()
    evt.cancellation_reason = body.get("reason", "")
    db.session.commit()
    return jsonify({"success": True, "data": evt.to_dict()}), 200


@calendar_bp.patch("/events/<event_id>/uncancel")
@jwt_required()
def uncancel_event(event_id):
    evt = AcademicEvent.query.get_or_404(event_id)
    evt.is_cancelled = False
    evt.cancelled_by = None
    evt.cancellation_reason = None
    db.session.commit()
    return jsonify({"success": True, "data": evt.to_dict()}), 200


@calendar_bp.delete("/events/<event_id>")
@jwt_required()
def delete_event(event_id):
    evt = AcademicEvent.query.get_or_404(event_id)
    db.session.delete(evt)
    db.session.commit()
    return jsonify({"success": True, "message": "Deleted."}), 200


@calendar_bp.get("/events/<event_id>/affected-sessions")
@jwt_required()
def affected_sessions(event_id):
    """
    Return metadata about which timetable sessions would be suppressed by this event.
    The actual removal from the calendar view is handled client-side; this endpoint
    provides the scope so the UI can show a preview before the admin confirms.
    """
    evt = AcademicEvent.query.get_or_404(event_id)
    if not evt.affects_timetable:
        return jsonify({"success": True, "data": {
            "affects_timetable": False,
            "message": "This event does not affect the timetable.",
        }}), 200

    start = evt.start_datetime.date() if evt.start_datetime else None
    end = evt.end_datetime.date() if evt.end_datetime else start

    return jsonify({"success": True, "data": {
        "affects_timetable": True,
        "timetable_scope": evt.timetable_scope,
        "department_id": evt.department_id,
        "program_id": evt.program_id,
        "student_group_id": evt.student_group_id,
        "university_id": evt.university_id,
        "affected_start": start.isoformat() if start else None,
        "affected_end": end.isoformat() if end else None,
        "message": (
            f"Timetable sessions between {start} and {end} "
            f"will be suppressed for scope '{evt.timetable_scope}'."
        ),
    }}), 200


@calendar_bp.get("/events/export.ics")
@jwt_required()
def export_ics():
    from icalendar import Calendar, Event as ICSEvent
    events = AcademicEvent.query.filter_by(is_public=True, is_cancelled=False).all()
    cal = Calendar()
    cal.add("prodid", "-//Shedulex//Academic Calendar//EN")
    cal.add("version", "2.0")
    for e in events:
        ics_event = ICSEvent()
        ics_event.add("summary", e.title)
        ics_event.add("dtstart", e.start_datetime)
        if e.end_datetime:
            ics_event.add("dtend", e.end_datetime)
        if e.description:
            ics_event.add("description", e.description)
        if e.location:
            ics_event.add("location", e.location)
        cal.add_component(ics_event)
    return Response(
        cal.to_ical(),
        mimetype="text/calendar",
        headers={"Content-Disposition": "attachment; filename=shedulex-calendar.ics"},
    )


# ── Academic Semesters ────────────────────────────────────────────────────────

@calendar_bp.get("/semesters")
@jwt_required()
def list_semesters():
    university_id = request.args.get("university_id")
    q = AcademicSemester.query
    if university_id:
        q = q.filter_by(university_id=university_id)
    semesters = q.order_by(AcademicSemester.start_date.desc()).all()
    return jsonify({"success": True, "data": [s.to_dict() for s in semesters]}), 200


@calendar_bp.get("/semesters/current")
@jwt_required()
def get_current_semester():
    university_id = request.args.get("university_id")
    today = date.today()
    q = AcademicSemester.query.filter(
        AcademicSemester.start_date <= today,
        AcademicSemester.end_date >= today,
    )
    if university_id:
        q = q.filter_by(university_id=university_id)
    sem = q.first()
    if not sem:
        # Fall back to the explicitly marked current semester
        q2 = AcademicSemester.query.filter_by(is_current=True)
        if university_id:
            q2 = q2.filter_by(university_id=university_id)
        sem = q2.first()
    if not sem:
        return jsonify({"success": False, "message": "No current semester found."}), 404
    return jsonify({"success": True, "data": sem.to_dict()}), 200


@calendar_bp.get("/semesters/<sem_id>")
@jwt_required()
def get_semester(sem_id):
    sem = AcademicSemester.query.get_or_404(sem_id)
    return jsonify({"success": True, "data": sem.to_dict()}), 200


@calendar_bp.post("/semesters")
@jwt_required()
def create_semester():
    claims = get_jwt()
    if claims.get("role") not in ADMIN_ROLES:
        return jsonify({"success": False, "message": "Forbidden."}), 403
    body = request.get_json() or {}

    def _parse_date(key):
        val = body.get(key)
        return date.fromisoformat(val) if val else None

    sem = AcademicSemester(
        name=body["name"],
        academic_year=body["academic_year"],
        semester_number=int(body["semester_number"]),
        start_date=date.fromisoformat(body["start_date"]),
        end_date=date.fromisoformat(body["end_date"]),
        break_start=_parse_date("break_start"),
        break_end=_parse_date("break_end"),
        registration_start=_parse_date("registration_start"),
        registration_end=_parse_date("registration_end"),
        exam_start=_parse_date("exam_start"),
        exam_end=_parse_date("exam_end"),
        university_id=body.get("university_id"),
        timezone=body.get("timezone", "UTC"),
        is_current=body.get("is_current", False),
    )
    if sem.is_current and sem.university_id:
        # Unset previous current for this university
        AcademicSemester.query.filter_by(
            university_id=sem.university_id, is_current=True
        ).update({"is_current": False})

    db.session.add(sem)
    db.session.commit()
    return jsonify({"success": True, "data": sem.to_dict()}), 201


@calendar_bp.put("/semesters/<sem_id>")
@jwt_required()
def update_semester(sem_id):
    claims = get_jwt()
    if claims.get("role") not in ADMIN_ROLES:
        return jsonify({"success": False, "message": "Forbidden."}), 403
    sem = AcademicSemester.query.get_or_404(sem_id)
    body = request.get_json() or {}

    def _parse_date(key):
        val = body.get(key)
        return date.fromisoformat(val) if val else getattr(sem, key)

    for k in ("name", "academic_year", "timezone"):
        if k in body:
            setattr(sem, k, body[k])
    if "semester_number" in body:
        sem.semester_number = int(body["semester_number"])
    if "start_date" in body:
        sem.start_date = date.fromisoformat(body["start_date"])
    if "end_date" in body:
        sem.end_date = date.fromisoformat(body["end_date"])
    for date_field in ("break_start", "break_end", "registration_start",
                       "registration_end", "exam_start", "exam_end"):
        if date_field in body:
            val = body[date_field]
            setattr(sem, date_field, date.fromisoformat(val) if val else None)

    if "is_current" in body and body["is_current"] and sem.university_id:
        AcademicSemester.query.filter(
            AcademicSemester.university_id == sem.university_id,
            AcademicSemester.id != sem.id,
        ).update({"is_current": False})
        sem.is_current = True
    elif "is_current" in body:
        sem.is_current = body["is_current"]

    db.session.commit()
    return jsonify({"success": True, "data": sem.to_dict()}), 200


@calendar_bp.patch("/semesters/<sem_id>/set-current")
@jwt_required()
def set_current_semester(sem_id):
    claims = get_jwt()
    if claims.get("role") not in ADMIN_ROLES:
        return jsonify({"success": False, "message": "Forbidden."}), 403
    sem = AcademicSemester.query.get_or_404(sem_id)
    if sem.university_id:
        AcademicSemester.query.filter(
            AcademicSemester.university_id == sem.university_id,
            AcademicSemester.id != sem.id,
        ).update({"is_current": False})
    sem.is_current = True
    db.session.commit()
    return jsonify({"success": True, "data": sem.to_dict()}), 200


@calendar_bp.delete("/semesters/<sem_id>")
@jwt_required()
def delete_semester(sem_id):
    claims = get_jwt()
    if claims.get("role") not in ADMIN_ROLES:
        return jsonify({"success": False, "message": "Forbidden."}), 403
    sem = AcademicSemester.query.get_or_404(sem_id)
    db.session.delete(sem)
    db.session.commit()
    return jsonify({"success": True, "message": "Semester deleted."}), 200


# ── Academic Holidays ─────────────────────────────────────────────────────────

@calendar_bp.get("/holidays")
@jwt_required()
def list_holidays():
    university_id = request.args.get("university_id")
    year = request.args.get("year", type=int)
    q = AcademicHoliday.query
    if university_id:
        q = q.filter_by(university_id=university_id)
    if year:
        from sqlalchemy import extract
        q = q.filter(extract("year", AcademicHoliday.date) == year)
    holidays = q.order_by(AcademicHoliday.date.asc()).all()
    return jsonify({"success": True, "data": [h.to_dict() for h in holidays]}), 200


@calendar_bp.post("/holidays")
@jwt_required()
def create_holiday():
    claims = get_jwt()
    if claims.get("role") not in WRITE_ROLES:
        return jsonify({"success": False, "message": "Forbidden."}), 403
    body = request.get_json() or {}
    holiday = AcademicHoliday(
        name=body["name"],
        date=date.fromisoformat(body["date"]),
        end_date=date.fromisoformat(body["end_date"]) if body.get("end_date") else None,
        holiday_type=body.get("holiday_type", "public"),
        university_id=body.get("university_id"),
        country_code=body.get("country_code"),
        is_recurring=body.get("is_recurring", False),
        created_by=get_jwt_identity(),
    )
    db.session.add(holiday)
    db.session.commit()
    return jsonify({"success": True, "data": holiday.to_dict()}), 201


@calendar_bp.put("/holidays/<holiday_id>")
@jwt_required()
def update_holiday(holiday_id):
    claims = get_jwt()
    if claims.get("role") not in WRITE_ROLES:
        return jsonify({"success": False, "message": "Forbidden."}), 403
    holiday = AcademicHoliday.query.get_or_404(holiday_id)
    body = request.get_json() or {}
    for k in ("name", "holiday_type", "university_id", "country_code", "is_recurring"):
        if k in body:
            setattr(holiday, k, body[k])
    if "date" in body:
        holiday.date = date.fromisoformat(body["date"])
    if "end_date" in body:
        holiday.end_date = date.fromisoformat(body["end_date"]) if body["end_date"] else None
    db.session.commit()
    return jsonify({"success": True, "data": holiday.to_dict()}), 200


@calendar_bp.delete("/holidays/<holiday_id>")
@jwt_required()
def delete_holiday(holiday_id):
    claims = get_jwt()
    if claims.get("role") not in WRITE_ROLES:
        return jsonify({"success": False, "message": "Forbidden."}), 403
    holiday = AcademicHoliday.query.get_or_404(holiday_id)
    db.session.delete(holiday)
    db.session.commit()
    return jsonify({"success": True, "message": "Holiday deleted."}), 200

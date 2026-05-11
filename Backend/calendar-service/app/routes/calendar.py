from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from datetime import datetime
from app.extensions import db
from app.models.event import AcademicEvent, AcademicSemester

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/v1/calendar")


@calendar_bp.get("/events")
@jwt_required()
def list_events():
    start = request.args.get("start")
    end = request.args.get("end")
    event_type = request.args.get("type")
    dept = request.args.get("department_id")

    q = AcademicEvent.query
    if start:
        q = q.filter(AcademicEvent.start_datetime >= datetime.fromisoformat(start))
    if end:
        q = q.filter(AcademicEvent.start_datetime <= datetime.fromisoformat(end))
    if event_type:
        q = q.filter_by(event_type=event_type)
    if dept:
        q = q.filter_by(department_id=dept)

    events = q.order_by(AcademicEvent.start_datetime).all()
    return jsonify({"success": True, "data": [e.to_dict() for e in events]}), 200


@calendar_bp.post("/events")
@jwt_required()
def create_event():
    body = request.get_json() or {}
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
    )
    db.session.add(evt)
    db.session.commit()
    return jsonify({"success": True, "data": evt.to_dict()}), 201


@calendar_bp.put("/events/<event_id>")
@jwt_required()
def update_event(event_id):
    evt = AcademicEvent.query.get_or_404(event_id)
    body = request.get_json() or {}
    for k in ("title", "description", "event_type", "location", "color", "recurrence", "is_public"):
        if k in body:
            setattr(evt, k, body[k])
    if "start" in body:
        evt.start_datetime = datetime.fromisoformat(body["start"])
    if "end" in body:
        evt.end_datetime = datetime.fromisoformat(body["end"])
    db.session.commit()
    return jsonify({"success": True, "data": evt.to_dict()}), 200


@calendar_bp.delete("/events/<event_id>")
@jwt_required()
def delete_event(event_id):
    evt = AcademicEvent.query.get_or_404(event_id)
    db.session.delete(evt)
    db.session.commit()
    return jsonify({"success": True, "message": "Deleted."}), 200


@calendar_bp.get("/events/export.ics")
@jwt_required()
def export_ics():
    """Export events as ICS (iCalendar) file."""
    from icalendar import Calendar, Event as ICSEvent
    events = AcademicEvent.query.filter_by(is_public=True).all()
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


@calendar_bp.get("/semesters")
@jwt_required()
def list_semesters():
    semesters = AcademicSemester.query.order_by(AcademicSemester.start_date.desc()).all()
    return jsonify({"success": True, "data": [s.to_dict() for s in semesters]}), 200


@calendar_bp.post("/semesters")
@jwt_required()
def create_semester():
    claims = get_jwt()
    if claims.get("role") not in ("admin",):
        return jsonify({"success": False, "message": "Forbidden."}), 403
    body = request.get_json() or {}
    from datetime import date
    sem = AcademicSemester(
        name=body["name"],
        academic_year=body["academic_year"],
        semester_number=int(body["semester_number"]),
        start_date=date.fromisoformat(body["start_date"]),
        end_date=date.fromisoformat(body["end_date"]),
        is_current=body.get("is_current", False),
    )
    db.session.add(sem)
    db.session.commit()
    return jsonify({"success": True, "data": sem.to_dict()}), 201

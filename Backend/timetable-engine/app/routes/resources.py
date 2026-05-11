"""CRUD routes for Departments, Rooms, Lecturers, Courses, TimeSlots."""
from flask import Blueprint, request
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.domain import Constraint, Course, Department, Lecturer, Room, TimeSlot
from app.security import service_or_jwt_required
from app.utils.responses import json_body, ok

resources_bp = Blueprint("resources", __name__, url_prefix="/api/v1")

WRITE_ROLES = ("admin", "timetable_officer", "hod")


def _create(instance):
    db.session.add(instance)
    db.session.commit()
    return instance


def _update(instance, payload: dict, allowed_fields: tuple[str, ...]):
    for key in allowed_fields:
        if key in payload:
            setattr(instance, key, payload[key])
    db.session.commit()
    return instance


def _dynamic_update(instance, payload: dict):
    """Keep legacy behavior: apply any attribute present on the model instance."""
    for key, value in payload.items():
        if hasattr(instance, key):
            setattr(instance, key, value)
    db.session.commit()
    return instance


def _delete(instance):
    db.session.delete(instance)
    db.session.commit()


# Departments
@resources_bp.get("/departments")
@service_or_jwt_required()
def list_departments():
    depts = Department.query.all()
    return ok(data=[d.to_dict() for d in depts])


@resources_bp.post("/departments")
@service_or_jwt_required(*WRITE_ROLES)
def create_department():
    body = json_body()
    dept = Department(
        name=body["name"],
        code=body["code"],
        faculty=body.get("faculty"),
        head_name=body.get("head_name"),
    )
    _create(dept)
    return ok(data=dept.to_dict(), status=201)


@resources_bp.put("/departments/<dept_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    _update(dept, json_body(), ("name", "code", "faculty", "head_name"))
    return ok(data=dept.to_dict())


@resources_bp.delete("/departments/<dept_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    _delete(dept)
    return ok(message="Deleted.")


# Rooms
@resources_bp.get("/rooms")
@service_or_jwt_required()
def list_rooms():
    rooms = Room.query.all()
    return ok(data=[r.to_dict() for r in rooms])


@resources_bp.post("/rooms")
@service_or_jwt_required(*WRITE_ROLES)
def create_room():
    body = json_body()
    room = Room(**{k: body[k] for k in body if k in Room.__table__.columns.keys()})
    _create(room)
    return ok(data=room.to_dict(), status=201)


@resources_bp.put("/rooms/<room_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_room(room_id):
    room = Room.query.get_or_404(room_id)
    _dynamic_update(room, json_body())
    return ok(data=room.to_dict())


@resources_bp.delete("/rooms/<room_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_room(room_id):
    room = Room.query.get_or_404(room_id)
    _delete(room)
    return ok(message="Deleted.")


# Lecturers
@resources_bp.get("/lecturers")
@service_or_jwt_required()
def list_lecturers():
    lecturers = Lecturer.query.options(joinedload(Lecturer.department)).filter_by(is_active=True).all()
    return ok(data=[l.to_dict() for l in lecturers])


@resources_bp.post("/lecturers")
@service_or_jwt_required(*WRITE_ROLES)
def create_lecturer():
    body = json_body()
    allowed = {
        "name",
        "email",
        "staff_id",
        "department_id",
        "specialization",
        "max_hours_per_week",
        "availability",
        "user_id",
    }
    lecturer = Lecturer(**{k: body[k] for k in body if k in allowed})
    _create(lecturer)
    return ok(data=lecturer.to_dict(), status=201)


@resources_bp.put("/lecturers/<lec_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_lecturer(lec_id):
    lecturer = Lecturer.query.get_or_404(lec_id)
    _dynamic_update(lecturer, json_body())
    return ok(data=lecturer.to_dict())


@resources_bp.delete("/lecturers/<lec_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_lecturer(lec_id):
    lecturer = Lecturer.query.get_or_404(lec_id)
    lecturer.is_active = False
    db.session.commit()
    return ok(message="Lecturer deactivated.")


# Courses
@resources_bp.get("/courses")
@service_or_jwt_required()
def list_courses():
    department_id = request.args.get("department_id")
    semester = request.args.get("semester", type=int)
    query = Course.query.options(
        joinedload(Course.department),
        joinedload(Course.lecturer).joinedload(Lecturer.department),
    ).filter_by(is_active=True)
    if department_id:
        query = query.filter_by(department_id=department_id)
    if semester:
        query = query.filter_by(semester=semester)
    courses = query.all()
    return ok(data=[c.to_dict() for c in courses])


@resources_bp.post("/courses")
@service_or_jwt_required(*WRITE_ROLES)
def create_course():
    body = json_body()
    allowed = {
        "name",
        "code",
        "department_id",
        "lecturer_id",
        "semester",
        "year_of_study",
        "credit_hours",
        "weekly_hours",
        "student_count",
        "requires_lab",
        "course_type",
        "priority",
    }
    course = Course(**{k: body[k] for k in body if k in allowed})
    _create(course)
    return ok(data=course.to_dict(), status=201)


@resources_bp.put("/courses/<course_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_course(course_id):
    course = Course.query.get_or_404(course_id)
    _dynamic_update(course, json_body())
    return ok(data=course.to_dict())


@resources_bp.delete("/courses/<course_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.is_active = False
    db.session.commit()
    return ok(message="Course deactivated.")


# Constraints
@resources_bp.get("/constraints")
@service_or_jwt_required()
def list_constraints():
    constraints = Constraint.query.filter_by(is_active=True).all()
    return ok(data=[c.to_dict() for c in constraints])


@resources_bp.post("/constraints")
@service_or_jwt_required(*WRITE_ROLES)
def create_constraint():
    body = json_body()
    constraint = Constraint(
        name=body["name"],
        constraint_type=body.get("constraint_type", "soft"),
        category=body.get("category"),
        weight=body.get("weight", 1.0),
        config=body.get("config", {}),
    )
    _create(constraint)
    return ok(data=constraint.to_dict(), status=201)


# Time slots
@resources_bp.get("/time-slots")
@service_or_jwt_required()
def list_time_slots():
    slots = TimeSlot.query.order_by(TimeSlot.slot_index.asc()).all()
    return ok(data=[s.to_dict() for s in slots])


@resources_bp.post("/time-slots")
@service_or_jwt_required(*WRITE_ROLES)
def create_time_slot():
    body = json_body()
    slot = TimeSlot(
        day=body["day"],
        start_time=body["start_time"],
        end_time=body["end_time"],
        slot_index=body.get("slot_index"),
        is_break=body.get("is_break", False),
        academic_year=body.get("academic_year"),
    )
    _create(slot)
    return ok(data=slot.to_dict(), status=201)


@resources_bp.put("/time-slots/<slot_id>")
@service_or_jwt_required(*WRITE_ROLES)
def update_time_slot(slot_id):
    slot = TimeSlot.query.get_or_404(slot_id)
    _update(slot, json_body(), ("day", "start_time", "end_time", "slot_index", "is_break", "academic_year"))
    return ok(data=slot.to_dict())


@resources_bp.delete("/time-slots/<slot_id>")
@service_or_jwt_required(*WRITE_ROLES)
def delete_time_slot(slot_id):
    slot = TimeSlot.query.get_or_404(slot_id)
    _delete(slot)
    return ok(message="Deleted.")

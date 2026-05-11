"""CRUD routes for Departments, Rooms, Lecturers, Courses, TimeSlots."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.extensions import db
from app.models.domain import Department, Room, Lecturer, Course, TimeSlot, Constraint

resources_bp = Blueprint("resources", __name__, url_prefix="/api/v1")


def admin_or_officer():
    claims = get_jwt()
    return claims.get("role") in ("admin", "timetable_officer", "hod")


# ── Departments ───────────────────────────────────────────────────────────────
@resources_bp.get("/departments")
@jwt_required()
def list_departments():
    depts = Department.query.all()
    return jsonify({"success": True, "data": [d.to_dict() for d in depts]}), 200


@resources_bp.post("/departments")
@jwt_required()
def create_department():
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    body = request.get_json() or {}
    dept = Department(name=body["name"], code=body["code"],
                      faculty=body.get("faculty"), head_name=body.get("head_name"))
    db.session.add(dept)
    db.session.commit()
    return jsonify({"success": True, "data": dept.to_dict()}), 201


@resources_bp.put("/departments/<dept_id>")
@jwt_required()
def update_department(dept_id):
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    dept = Department.query.get_or_404(dept_id)
    body = request.get_json() or {}
    for k in ("name", "code", "faculty", "head_name"):
        if k in body:
            setattr(dept, k, body[k])
    db.session.commit()
    return jsonify({"success": True, "data": dept.to_dict()}), 200


@resources_bp.delete("/departments/<dept_id>")
@jwt_required()
def delete_department(dept_id):
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    dept = Department.query.get_or_404(dept_id)
    db.session.delete(dept)
    db.session.commit()
    return jsonify({"success": True, "message": "Deleted."}), 200


# ── Rooms ─────────────────────────────────────────────────────────────────────
@resources_bp.get("/rooms")
@jwt_required()
def list_rooms():
    rooms = Room.query.all()
    return jsonify({"success": True, "data": [r.to_dict() for r in rooms]}), 200


@resources_bp.post("/rooms")
@jwt_required()
def create_room():
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    body = request.get_json() or {}
    room = Room(**{k: body[k] for k in body if k in Room.__table__.columns.keys()})
    db.session.add(room)
    db.session.commit()
    return jsonify({"success": True, "data": room.to_dict()}), 201


@resources_bp.put("/rooms/<room_id>")
@jwt_required()
def update_room(room_id):
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    room = Room.query.get_or_404(room_id)
    body = request.get_json() or {}
    for k, v in body.items():
        if hasattr(room, k):
            setattr(room, k, v)
    db.session.commit()
    return jsonify({"success": True, "data": room.to_dict()}), 200


@resources_bp.delete("/rooms/<room_id>")
@jwt_required()
def delete_room(room_id):
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    room = Room.query.get_or_404(room_id)
    db.session.delete(room)
    db.session.commit()
    return jsonify({"success": True, "message": "Deleted."}), 200


# ── Lecturers ─────────────────────────────────────────────────────────────────
@resources_bp.get("/lecturers")
@jwt_required()
def list_lecturers():
    lecs = Lecturer.query.filter_by(is_active=True).all()
    return jsonify({"success": True, "data": [l.to_dict() for l in lecs]}), 200


@resources_bp.post("/lecturers")
@jwt_required()
def create_lecturer():
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    body = request.get_json() or {}
    allowed = {"name", "email", "staff_id", "department_id", "specialization",
               "max_hours_per_week", "availability", "user_id"}
    lec = Lecturer(**{k: body[k] for k in body if k in allowed})
    db.session.add(lec)
    db.session.commit()
    return jsonify({"success": True, "data": lec.to_dict()}), 201


@resources_bp.put("/lecturers/<lec_id>")
@jwt_required()
def update_lecturer(lec_id):
    lec = Lecturer.query.get_or_404(lec_id)
    body = request.get_json() or {}
    for k, v in body.items():
        if hasattr(lec, k):
            setattr(lec, k, v)
    db.session.commit()
    return jsonify({"success": True, "data": lec.to_dict()}), 200


@resources_bp.delete("/lecturers/<lec_id>")
@jwt_required()
def delete_lecturer(lec_id):
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    lec = Lecturer.query.get_or_404(lec_id)
    lec.is_active = False
    db.session.commit()
    return jsonify({"success": True, "message": "Lecturer deactivated."}), 200


# ── Courses ───────────────────────────────────────────────────────────────────
@resources_bp.get("/courses")
@jwt_required()
def list_courses():
    dept = request.args.get("department_id")
    sem = request.args.get("semester", type=int)
    q = Course.query.filter_by(is_active=True)
    if dept:
        q = q.filter_by(department_id=dept)
    if sem:
        q = q.filter_by(semester=sem)
    courses = q.all()
    return jsonify({"success": True, "data": [c.to_dict() for c in courses]}), 200


@resources_bp.post("/courses")
@jwt_required()
def create_course():
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    body = request.get_json() or {}
    allowed = {"name", "code", "department_id", "lecturer_id", "semester", "year_of_study",
               "credit_hours", "weekly_hours", "student_count", "requires_lab", "course_type", "priority"}
    course = Course(**{k: body[k] for k in body if k in allowed})
    db.session.add(course)
    db.session.commit()
    return jsonify({"success": True, "data": course.to_dict()}), 201


@resources_bp.put("/courses/<course_id>")
@jwt_required()
def update_course(course_id):
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    course = Course.query.get_or_404(course_id)
    body = request.get_json() or {}
    for k, v in body.items():
        if hasattr(course, k):
            setattr(course, k, v)
    db.session.commit()
    return jsonify({"success": True, "data": course.to_dict()}), 200


@resources_bp.delete("/courses/<course_id>")
@jwt_required()
def delete_course(course_id):
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    course = Course.query.get_or_404(course_id)
    course.is_active = False
    db.session.commit()
    return jsonify({"success": True, "message": "Course deactivated."}), 200


# ── Constraints ───────────────────────────────────────────────────────────────
@resources_bp.get("/constraints")
@jwt_required()
def list_constraints():
    constraints = Constraint.query.filter_by(is_active=True).all()
    return jsonify({"success": True, "data": [c.to_dict() for c in constraints]}), 200


@resources_bp.post("/constraints")
@jwt_required()
def create_constraint():
    if not admin_or_officer():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    body = request.get_json() or {}
    c = Constraint(
        name=body["name"],
        constraint_type=body.get("constraint_type", "soft"),
        category=body.get("category"),
        weight=body.get("weight", 1.0),
        config=body.get("config", {}),
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({"success": True, "data": c.to_dict()}), 201

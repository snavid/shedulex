from flask import Blueprint, jsonify, request
from app.extensions import db
from app.middleware.internal_auth import require_internal_key
from app.models.user import User, Role

internal_bp = Blueprint("internal", __name__, url_prefix="/api/v1/users/internal")


@internal_bp.get("/recipients")
def list_recipients():
    denied = require_internal_key()
    if denied:
        return denied

    role_name = request.args.get("role")
    university_id = request.args.get("university_id")
    department_id = request.args.get("department_id")
    program_id = request.args.get("program_id")
    student_group_id = request.args.get("student_group_id")
    has_phone = request.args.get("has_phone", "").lower() == "true"
    has_email = request.args.get("has_email", "").lower() == "true"
    email = request.args.get("email")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 100, type=int), 500)

    query = User.query.filter_by(is_active=True, is_approved=True)

    if role_name:
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            return jsonify({"success": True, "data": [], "meta": {"page": page, "per_page": per_page, "total": 0, "pages": 0}}), 200
        query = query.filter_by(role_id=role.id)
    if university_id:
        query = query.filter_by(university_id=university_id)
    if department_id:
        query = query.filter_by(department_id=department_id)
    if program_id:
        query = query.filter_by(program_id=program_id)
    if student_group_id:
        query = query.filter_by(student_group_id=student_group_id)
    if has_phone:
        query = query.filter(User.phone.isnot(None), User.phone != "")
    if has_email:
        query = query.filter(User.email.isnot(None), User.email != "")
    if email:
        query = query.filter(User.email == email)

    pagination = query.order_by(User.created_at.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    data = [
        {
            "id": u.id,
            "phone": u.phone,
            "email": u.email,
            "role": u.role.name if u.role else None,
            "program_id": u.program_id,
            "student_group_id": u.student_group_id,
            "department_id": u.department_id,
            "first_name": u.first_name,
            "last_name": u.last_name,
        }
        for u in pagination.items
    ]
    return jsonify({
        "success": True,
        "data": data,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    }), 200


@internal_bp.get("/<user_id>")
def get_recipient(user_id):
    denied = require_internal_key()
    if denied:
        return denied

    user = User.query.get(user_id)
    if not user or not user.is_active or not user.is_approved:
        return jsonify({"success": False, "message": "User not found."}), 404

    return jsonify({
        "success": True,
        "data": {
            "id": user.id,
            "phone": user.phone,
            "email": user.email,
            "role": user.role.name if user.role else None,
            "program_id": user.program_id,
            "student_group_id": user.student_group_id,
            "department_id": user.department_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
    }), 200


@internal_bp.post("/batch")
def batch_users():
    denied = require_internal_key()
    if denied:
        return denied

    body = request.get_json() or {}
    ids = body.get("ids") or []
    if not ids:
        return jsonify({"success": True, "data": {}}), 200

    users = User.query.filter(User.id.in_(ids)).all()
    data = {}
    for user in users:
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        data[user.id] = {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "display_name": name or user.email,
            "role": user.role.name if user.role else None,
        }
    return jsonify({"success": True, "data": data}), 200

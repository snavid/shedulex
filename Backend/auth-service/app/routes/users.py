from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError
from app.extensions import db
from app.models.user import User, Role, UserSession
from app.schemas import UserUpdateSchema
from app.middleware.rbac import roles_required
from app.services import auth_service

users_bp = Blueprint("users", __name__, url_prefix="/api/v1/users")

update_schema = UserUpdateSchema()


@users_bp.get("/")
@jwt_required()
@roles_required("admin", "timetable_officer")
def list_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    role_filter = request.args.get("role")
    search = request.args.get("search", "")

    query = User.query
    if role_filter:
        role = Role.query.filter_by(name=role_filter).first()
        if role:
            query = query.filter_by(role_id=role.id)
    if search:
        query = query.filter(
            User.email.ilike(f"%{search}%") | User.username.ilike(f"%{search}%")
        )

    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "success": True,
        "data": [u.to_dict() for u in pagination.items],
        "meta": {
            "page": page, "per_page": per_page,
            "total": pagination.total, "pages": pagination.pages,
        },
    }), 200


@users_bp.get("/<user_id>")
@jwt_required()
def get_user(user_id):
    requester_id = get_jwt_identity()
    claims = get_jwt()
    # users can only view their own profile unless admin/timetable_officer
    if requester_id != user_id and claims.get("role") not in ("admin", "timetable_officer"):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404
    return jsonify({"success": True, "data": user.to_dict()}), 200


@users_bp.patch("/<user_id>")
@jwt_required()
def update_user(user_id):
    requester_id = get_jwt_identity()
    claims = get_jwt()
    if requester_id != user_id and claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Forbidden."}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    try:
        data = update_schema.load(request.get_json())
    except ValidationError as e:
        return jsonify({"success": False, "message": "Validation failed", "errors": e.messages}), 422

    for key, value in data.items():
        setattr(user, key, value)
    db.session.commit()
    return jsonify({"success": True, "data": user.to_dict()}), 200


@users_bp.patch("/<user_id>/activate")
@jwt_required()
@roles_required("admin")
def toggle_activation(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404
    user.is_active = not user.is_active
    db.session.commit()
    status = "activated" if user.is_active else "deactivated"
    return jsonify({"success": True, "message": f"User {status}.", "data": user.to_dict()}), 200


@users_bp.patch("/<user_id>/role")
@jwt_required()
@roles_required("admin")
def change_role(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    body = request.get_json()
    role_name = body.get("role_name")
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        return jsonify({"success": False, "message": f"Role '{role_name}' not found."}), 404

    user.role_id = role.id
    db.session.commit()
    return jsonify({"success": True, "data": user.to_dict()}), 200


@users_bp.get("/<user_id>/sessions")
@jwt_required()
def get_sessions(user_id):
    requester_id = get_jwt_identity()
    claims = get_jwt()
    if requester_id != user_id and claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Forbidden."}), 403

    sessions = UserSession.query.filter_by(user_id=user_id, is_active=True).all()
    return jsonify({"success": True, "data": [s.to_dict() for s in sessions]}), 200


@users_bp.get("/roles/all")
@jwt_required()
@roles_required("admin")
def list_roles():
    roles = Role.query.all()
    return jsonify({"success": True, "data": [r.to_dict() for r in roles]}), 200


# Lecturer account management
@users_bp.post("/lecturers")
@jwt_required()
@roles_required("admin", "timetable_officer", "hod")
def create_lecturer():
    body = request.get_json() or {}
    required = ["email", "first_name", "last_name"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({"success": False, "message": f"Missing fields: {', '.join(missing)}"}), 422

    try:
        user, plain_password = auth_service.create_lecturer_account(body)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 409
    except RuntimeError as e:
        return jsonify({"success": False, "message": str(e)}), 500

    response_data = user.to_dict()
    response_data["default_password"] = plain_password  # visible to admin only at creation time
    return jsonify({"success": True, "data": response_data, "message": "Lecturer account created. Credentials emailed."}), 201


@users_bp.post("/<user_id>/resend-credentials")
@jwt_required()
@roles_required("admin", "timetable_officer", "hod")
def resend_credentials(user_id):
    try:
        user, plain_password = auth_service.resend_credentials(user_id)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404

    response_data = user.to_dict()
    response_data["default_password"] = plain_password
    return jsonify({"success": True, "data": response_data, "message": "New credentials generated and emailed."}), 200

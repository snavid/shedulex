from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError
from app.extensions import db
from app.models.user import User, Role, UserSession
from app.schemas import UserUpdateSchema, StudentCreateSchema
from app.middleware.rbac import roles_required
from app.services import auth_service

users_bp = Blueprint("users", __name__, url_prefix="/api/v1/users")

update_schema = UserUpdateSchema()
student_schema = StudentCreateSchema()


@users_bp.get("/")
@jwt_required()
@roles_required("admin", "timetable_officer")
def list_users():
    claims = get_jwt()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    role_filter = request.args.get("role")
    search = request.args.get("search", "")
    pending_only = request.args.get("pending") == "true"

    query = User.query
    # Scope to the requester's university
    uni_id = claims.get("university_id")
    if uni_id:
        query = query.filter_by(university_id=uni_id)
    if role_filter:
        role = Role.query.filter_by(name=role_filter).first()
        if role:
            query = query.filter_by(role_id=role.id)
    if pending_only:
        query = query.filter_by(is_approved=False)
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

    if requester_id != user_id:
        uni_id = claims.get("university_id")
        if uni_id and user.university_id != uni_id:
            return jsonify({"success": False, "message": "Forbidden."}), 403

    try:
        data = update_schema.load(request.get_json())
    except ValidationError as e:
        return jsonify({"success": False, "message": "Validation failed", "errors": e.messages}), 422

    data = {k: v for k, v in data.items() if v is not None}

    if "email" in data:
        data["email"] = data["email"].lower()
        if data["email"] != user.email:
            existing = User.query.filter_by(email=data["email"]).first()
            if existing:
                return jsonify({"success": False, "message": "A user with this email already exists."}), 409

    for key, value in data.items():
        setattr(user, key, value)
    if data.get("department_id") and not data.get("department"):
        dept_name = auth_service._resolve_department_name(data["department_id"])
        if dept_name:
            user.department = dept_name
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


@users_bp.patch("/<user_id>/approve")
@jwt_required()
@roles_required("admin")
def approve_user(user_id):
    """Approve a pending registration, activating the account."""
    claims = get_jwt()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404
    # University isolation: admin can only approve users from their own university
    uni_id = claims.get("university_id")
    if uni_id and user.university_id != uni_id:
        return jsonify({"success": False, "message": "Forbidden."}), 403
    user.is_approved = True
    user.is_active = True
    db.session.commit()
    return jsonify({"success": True, "message": "User approved and activated.", "data": user.to_dict()}), 200


@users_bp.patch("/<user_id>/reject")
@jwt_required()
@roles_required("admin")
def reject_user(user_id):
    """Reject (permanently deactivate) a pending registration."""
    claims = get_jwt()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404
    uni_id = claims.get("university_id")
    if uni_id and user.university_id != uni_id:
        return jsonify({"success": False, "message": "Forbidden."}), 403
    user.is_approved = False
    user.is_active = False
    db.session.commit()
    return jsonify({"success": True, "message": "Registration rejected.", "data": user.to_dict()}), 200


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
    required = ["email", "first_name", "last_name", "phone"]
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


@users_bp.post("/lecturer-invite-link")
@jwt_required()
@roles_required("admin", "timetable_officer", "hod")
def create_lecturer_invite_link():
    """Mint a self-registration link for a lecturer who has no auth account yet."""
    body = request.get_json() or {}
    required = ["lecturer_id", "name", "email"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({"success": False, "message": f"Missing fields: {', '.join(missing)}"}), 422

    token = auth_service.create_lecturer_invite(
        lecturer_id=body["lecturer_id"], name=body["name"], email=body["email"],
        phone=body.get("phone"), department=body.get("department"),
        university_id=body.get("university_id"),
    )
    frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:5173")
    invite_url = f"{frontend_url}/lecturer-register?token={token}"
    return jsonify({"success": True, "data": {"invite_url": invite_url, "token": token}}), 201


@users_bp.post("/students")
@jwt_required()
@roles_required("admin")
def create_student():
    claims = get_jwt()
    uni_id = claims.get("university_id")
    if not uni_id:
        return jsonify({"success": False, "message": "University scope is required."}), 422

    try:
        data = student_schema.load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"success": False, "message": "Validation failed", "errors": e.messages}), 422

    try:
        user, _plain_password = auth_service.create_student_account(data, uni_id)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 409
    except RuntimeError as e:
        return jsonify({"success": False, "message": str(e)}), 500

    return jsonify({
        "success": True,
        "data": user.to_dict(),
        "message": "Student enrolled. They can access the portal with their registration number and phone last 4 digits.",
    }), 201


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

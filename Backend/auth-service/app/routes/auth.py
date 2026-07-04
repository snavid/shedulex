from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from marshmallow import ValidationError
from app.extensions import limiter
from app.schemas import (
    RegisterSchema, LoginSchema, PasswordResetRequestSchema,
    PasswordResetSchema, ChangePasswordSchema,
)
from app.services import auth_service
from app.services.token_service import generate_tokens, blacklist_token, is_token_blacklisted
from app.models.user import User
from shared.audit_client import record_audit

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

register_schema = RegisterSchema()
login_schema = LoginSchema()
reset_req_schema = PasswordResetRequestSchema()
reset_schema = PasswordResetSchema()
change_pw_schema = ChangePasswordSchema()


@auth_bp.post("/register")
@limiter.limit("10 per hour")
def register():
    try:
        data = register_schema.load(request.get_json())
    except ValidationError as e:
        return jsonify({"success": False, "message": "Validation failed", "errors": e.messages}), 422

    try:
        user, tokens = auth_service.register_user(data)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 409

    if tokens is None:
        # Non-admin registration: account created but pending approval
        return jsonify({
            "success": True,
            "pending": True,
            "message": "Registration submitted. Your account is pending approval by a university administrator.",
            "data": {"user": user.to_dict()},
        }), 202

    return jsonify({
        "success": True,
        "message": "Account created. Please verify your email.",
        "data": {"user": user.to_dict(), **tokens, "token_type": "Bearer"},
    }), 201


@auth_bp.post("/login")
@limiter.limit("20 per 5 minutes")
def login():
    try:
        data = login_schema.load(request.get_json())
    except ValidationError as e:
        return jsonify({"success": False, "message": "Validation failed", "errors": e.messages}), 422

    try:
        user, tokens = auth_service.login_user(data["email"], data["password"])
    except (ValueError, PermissionError) as e:
        failed_user = User.query.filter_by(email=data["email"].lower()).first()
        failed_name = (
            f"{failed_user.first_name} {failed_user.last_name}".strip()
            if failed_user else None
        )
        record_audit(
            service="auth-service",
            action="auth.login",
            user_id=str(failed_user.id) if failed_user else None,
            user_email=failed_user.email if failed_user else data["email"],
            user_name=failed_name or data["email"],
            university_id=str(failed_user.university_id) if failed_user and failed_user.university_id else None,
            description=f"Failed login attempt for {data['email']}",
            status="failure",
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")[:500],
            metadata={"email": data["email"], "reason": str(e)},
        )
        return jsonify({"success": False, "message": str(e)}), 401

    user_display = f"{user.first_name} {user.last_name}".strip() or user.email
    record_audit(
        service="auth-service",
        action="auth.login",
        user_id=str(user.id),
        user_email=user.email,
        user_name=user_display,
        university_id=str(user.university_id) if user.university_id else None,
        description=f"{user.email} logged in",
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:500],
        metadata={"role": user.role.name if user.role else None},
    )

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "data": {"user": user.to_dict(), **tokens, "token_type": "Bearer"},
    }), 200


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return jsonify({"success": False, "message": "User not found or inactive."}), 404

    tokens = generate_tokens(user_id, {
        "role": user.role.name,
        "email": user.email,
        "must_change_password": user.must_change_password,
        "university_id": str(user.university_id) if user.university_id else None,
    })
    return jsonify({"success": True, "data": {**tokens, "token_type": "Bearer"}}), 200


@auth_bp.post("/logout")
@jwt_required()
def logout():
    claims = get_jwt()
    user_id = get_jwt_identity()
    auth_service.logout_user(claims["jti"], user_id)
    record_audit(
        service="auth-service",
        action="auth.logout",
        user_id=user_id,
        user_email=claims.get("email"),
        user_name=claims.get("email"),
        university_id=claims.get("university_id"),
        description=f"{claims.get('email', 'User')} logged out",
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:500],
    )
    return jsonify({"success": True, "message": "Logged out successfully."}), 200


@auth_bp.get("/verify-email")
def verify_email():
    token = request.args.get("token")
    if not token:
        return jsonify({"success": False, "message": "Token is required."}), 400
    try:
        auth_service.verify_email(token)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    return jsonify({"success": True, "message": "Email verified successfully."}), 200


@auth_bp.post("/password-reset/request")
@limiter.limit("5 per hour")
def password_reset_request():
    try:
        data = reset_req_schema.load(request.get_json())
    except ValidationError as e:
        return jsonify({"success": False, "message": "Validation failed", "errors": e.messages}), 422
    auth_service.request_password_reset(data["email"])
    return jsonify({"success": True, "message": "If the email exists, a reset link has been sent."}), 200


@auth_bp.post("/password-reset/confirm")
@limiter.limit("5 per hour")
def password_reset_confirm():
    try:
        data = reset_schema.load(request.get_json())
    except ValidationError as e:
        return jsonify({"success": False, "message": "Validation failed", "errors": e.messages}), 422
    try:
        auth_service.reset_password(data["token"], data["password"])
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    return jsonify({"success": True, "message": "Password reset successfully."}), 200


@auth_bp.post("/change-password")
@jwt_required()
def change_password():
    try:
        data = change_pw_schema.load(request.get_json())
    except ValidationError as e:
        return jsonify({"success": False, "message": "Validation failed", "errors": e.messages}), 422

    user = User.query.get(get_jwt_identity())
    try:
        auth_service.change_password(user, data["current_password"], data["new_password"])
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    return jsonify({"success": True, "message": "Password changed successfully."}), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    user = User.query.get(get_jwt_identity())
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404
    return jsonify({"success": True, "data": user.to_dict()}), 200

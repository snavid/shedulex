import uuid
import secrets
from datetime import datetime, timezone, timedelta
from flask import request, current_app
from flask_jwt_extended import decode_token
from app.extensions import db
from app.models.user import User, Role, UserSession
from app.services.token_service import generate_tokens, blacklist_token
from app.services.email_service import send_verification_email, send_password_reset_email


ROLES = ["admin", "lecturer", "student", "timetable_officer", "hod"]


def seed_roles():
    """Ensure default roles exist in the DB."""
    role_permissions = {
        "admin": ["*"],
        "timetable_officer": ["timetable:read", "timetable:write", "timetable:generate", "users:read"],
        "hod": ["timetable:read", "timetable:approve", "department:manage"],
        "lecturer": ["timetable:read", "schedule:read", "profile:write"],
        "student": ["timetable:read", "schedule:read"],
    }
    for name, perms in role_permissions.items():
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name, permissions=perms, description=name.replace("_", " ").title()))
    db.session.commit()


def register_user(data: dict) -> tuple[User, dict]:
    role_name = data.pop("role_name", "student")
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        role = Role.query.filter_by(name="student").first()

    if User.query.filter_by(email=data["email"]).first():
        raise ValueError("A user with this email already exists.")
    if User.query.filter_by(username=data["username"]).first():
        raise ValueError("This username is already taken.")

    verification_token = secrets.token_urlsafe(32)
    user = User(
        email=data["email"],
        username=data["username"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=data.get("phone"),
        department=data.get("department"),
        staff_id=data.get("staff_id"),
        role_id=role.id,
        verification_token=verification_token,
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    try:
        send_verification_email(user.email, user.first_name, verification_token)
    except Exception:
        current_app.logger.warning("Verification email failed to send.")

    tokens = generate_tokens(user.id, {"role": role.name, "email": user.email})
    _persist_session(user.id, tokens["access_token"])
    return user, tokens


def login_user(email: str, password: str) -> tuple[User, dict]:
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        raise ValueError("Invalid email or password.")
    if not user.is_active:
        raise PermissionError("This account has been deactivated.")

    user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    tokens = generate_tokens(user.id, {"role": user.role.name, "email": user.email})
    _persist_session(user.id, tokens["access_token"])
    return user, tokens


def logout_user(jti: str, user_id: str):
    blacklist_token(jti)
    session = UserSession.query.filter_by(jti=jti, user_id=user_id).first()
    if session:
        session.is_active = False
        db.session.commit()


def verify_email(token: str) -> User:
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        raise ValueError("Invalid or expired verification token.")
    user.is_verified = True
    user.verification_token = None
    db.session.commit()
    return user


def request_password_reset(email: str):
    user = User.query.filter_by(email=email).first()
    if not user:
        return  # silently ignore to prevent email enumeration
    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    db.session.commit()
    send_password_reset_email(user.email, user.first_name, token)


def reset_password(token: str, new_password: str) -> User:
    user = User.query.filter_by(reset_token=token).first()
    if not user:
        raise ValueError("Invalid or expired reset token.")
    if user.reset_token_expires < datetime.now(timezone.utc):
        raise ValueError("Reset token has expired.")
    user.set_password(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.session.commit()
    return user


def change_password(user: User, current_password: str, new_password: str):
    if not user.check_password(current_password):
        raise ValueError("Current password is incorrect.")
    user.set_password(new_password)
    db.session.commit()


def _persist_session(user_id: str, access_token: str):
    try:
        decoded = decode_token(access_token)
        jti = decoded["jti"]
        expires_at = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        session = UserSession(
            user_id=user_id,
            jti=jti,
            ip_address=request.remote_addr,
            device_info=request.headers.get("User-Agent", "")[:500],
            expires_at=expires_at,
        )
        db.session.add(session)
        db.session.commit()
    except Exception as exc:
        current_app.logger.warning(f"Session persistence failed: {exc}")

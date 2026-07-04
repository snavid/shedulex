import uuid
import secrets
import string
import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from flask import request, current_app
from flask_jwt_extended import decode_token, create_access_token
from app.extensions import db
from app.models.user import User, Role, UserSession
from app.services.token_service import generate_tokens, blacklist_token, blacklist_all_user_tokens
from app.services.email_service import (
    send_verification_email,
    send_password_reset_email,
    send_lecturer_credentials_email,
)

TIMETABLE_URL = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")
INTERNAL_KEY  = os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")


def _resolve_department_name(department_id: str) -> str | None:
    """Fetch department name from timetable-engine for display on user profile."""
    req = urllib.request.Request(
        f"{TIMETABLE_URL}/api/v1/departments/{department_id}",
        headers={"X-Internal-Service-Key": INTERNAL_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            return (body.get("data") or {}).get("name")
    except Exception:
        current_app.logger.warning("Could not resolve department name for %s.", department_id)
        return None


def _resolve_university_id(university_id: str | None, university_name: str | None, university_code: str | None) -> str | None:
    """
    Return a university_id.
    - If university_id is explicitly provided, return it directly.
    - If university_name + code are provided, call timetable-engine to create or find the university.
    - Otherwise return None.
    """
    if university_id:
        return university_id
    if not university_name or not university_code:
        return None

    payload = json.dumps({"name": university_name, "code": university_code}).encode()
    req = urllib.request.Request(
        f"{TIMETABLE_URL}/api/v1/universities",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Internal-Service-Key": INTERNAL_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            return (body.get("data") or {}).get("id")
    except urllib.error.HTTPError as e:
        # 409 = already exists; try to find it
        if e.code == 409:
            list_req = urllib.request.Request(
                f"{TIMETABLE_URL}/api/v1/universities",
                headers={"X-Internal-Service-Key": INTERNAL_KEY},
            )
            with urllib.request.urlopen(list_req, timeout=10) as resp2:
                unis = json.loads(resp2.read()).get("data") or []
                match = next((u for u in unis if u.get("code") == university_code), None)
                return match["id"] if match else None
    except Exception:
        current_app.logger.warning("Could not resolve university from timetable-engine.")
        return None


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


SELF_APPROVE_ROLES = {"admin"}


def register_user(data: dict) -> tuple[User, dict | None]:
    """
    Returns (user, tokens) for admin registrations (immediate access) or
    (user, None) for all other roles (pending admin approval).
    """
    role_name = data.pop("role_name", "student")
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        role = Role.query.filter_by(name="student").first()

    if User.query.filter_by(email=data["email"]).first():
        raise ValueError("A user with this email already exists.")
    if User.query.filter_by(username=data["username"]).first():
        raise ValueError("This username is already taken.")

    university_id = _resolve_university_id(
        data.get("university_id"),
        data.get("university_name"),
        data.get("university_code"),
    )

    # Admins creating their own university account are immediately active and approved.
    # All other self-registrations require admin approval before the account can be used.
    self_approve = role.name in SELF_APPROVE_ROLES
    verification_token = secrets.token_urlsafe(32)
    department_name = data.get("department")
    department_id = data.get("department_id")
    if department_id and not department_name:
        department_name = _resolve_department_name(department_id)

    user = User(
        email=data["email"],
        username=data["username"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=data.get("phone"),
        department=department_name,
        department_id=department_id,
        program_id=data.get("program_id"),
        student_group_id=data.get("student_group_id"),
        staff_id=data.get("staff_id"),
        university_id=university_id,
        role_id=role.id,
        is_active=self_approve,
        is_approved=self_approve,
        verification_token=verification_token,
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    try:
        send_verification_email(user.email, user.first_name, verification_token)
    except Exception:
        current_app.logger.warning("Verification email failed to send.")

    if not self_approve:
        return user, None  # pending approval — no tokens issued

    tokens = generate_tokens(user.id, {
        "role": role.name,
        "email": user.email,
        "university_id": str(user.university_id) if user.university_id else None,
    })
    _persist_session(user.id, tokens["access_token"])
    return user, tokens


def login_user(email: str, password: str) -> tuple[User, dict]:
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        raise ValueError("Invalid email or password.")
    if not user.is_approved:
        raise PermissionError("Your account is pending admin approval. Please wait for an administrator to activate your account.")
    if not user.is_active:
        raise PermissionError("This account has been deactivated. Please contact your administrator.")

    user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    extra_claims = {
        "role": user.role.name,
        "email": user.email,
        "must_change_password": user.must_change_password,
        "university_id": str(user.university_id) if user.university_id else None,
    }
    tokens = generate_tokens(user.id, extra_claims)
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
    blacklist_all_user_tokens(str(user.id))
    return user


def change_password(user: User, current_password: str, new_password: str):
    if not user.check_password(current_password):
        raise ValueError("Current password is incorrect.")
    user.set_password(new_password)
    user.must_change_password = False
    db.session.commit()
    blacklist_all_user_tokens(str(user.id))


def _generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.isupper() for c in pwd)
            and any(c.islower() for c in pwd)
            and any(c.isdigit() for c in pwd)
        ):
            return pwd


def create_lecturer_account(data: dict) -> tuple[User, str]:
    """
    Create a lecturer user account with auto-generated credentials.
    Returns (user, plain_text_password) so the caller can display / resend them.
    """
    role = Role.query.filter_by(name="lecturer").first()
    if not role:
        raise RuntimeError("Lecturer role not found. Ensure roles are seeded.")

    email = data["email"]
    first_name = data["first_name"]
    last_name = data["last_name"]
    phone = data.get("phone")
    if not phone:
        raise ValueError("Phone number is required for lecturer accounts.")

    if User.query.filter_by(email=email).first():
        raise ValueError(f"A user with email '{email}' already exists.")

    plain_password = _generate_password()
    username = data.get("username") or f"{first_name.lower()}.{last_name.lower()}.{secrets.token_hex(3)}"
    username = username.replace(" ", "").lower()

    if User.query.filter_by(username=username).first():
        username = f"{username}.{secrets.token_hex(3)}"

    user = User(
        email=email,
        username=username,
        first_name=first_name,
        last_name=last_name,
        phone=data.get("phone"),
        department=data.get("department"),
        staff_id=data.get("staff_id"),
        university_id=data.get("university_id"),
        role_id=role.id,
        is_active=True,
        is_verified=True,          # admin-created accounts skip email verification
        must_change_password=True, # force change on first login
    )
    user.set_password(plain_password)
    db.session.add(user)
    db.session.commit()

    try:
        send_lecturer_credentials_email(
            to=email,
            name=f"{first_name} {last_name}",
            username=username,
            password=plain_password,
        )
    except Exception:
        current_app.logger.warning("Credential email failed to send for %s", email)

    return user, plain_password


def _phone_matches_last4(phone: str | None, last4: str) -> bool:
    if not phone or not last4:
        return False
    digits = re.sub(r"\D", "", phone)
    return digits.endswith(last4)


def _resolve_university_by_code(university_code: str) -> dict | None:
    """Find university record from timetable-engine by code."""
    code = university_code.strip().upper()
    list_req = urllib.request.Request(f"{TIMETABLE_URL}/api/v1/universities")
    try:
        with urllib.request.urlopen(list_req, timeout=10) as resp:
            unis = json.loads(resp.read()).get("data") or []
            return next((u for u in unis if (u.get("code") or "").upper() == code), None)
    except Exception:
        current_app.logger.warning("Could not resolve university code %s.", university_code)
        return None


def create_student_account(data: dict, university_id: str) -> tuple[User, str]:
    """Create a student account for admin enrollment."""
    role = Role.query.filter_by(name="student").first()
    if not role:
        raise RuntimeError("Student role not found. Ensure roles are seeded.")

    reg_number = data["registration_number"].strip()
    phone = data.get("phone")
    if not phone:
        raise ValueError("Phone number is required for student accounts.")

    existing_reg = User.query.filter_by(
        university_id=university_id,
        registration_number=reg_number,
    ).first()
    if existing_reg:
        raise ValueError(f"A student with registration number '{reg_number}' already exists.")

    uni = _resolve_university_by_code(data.get("university_code") or "")
    uni_code = (uni or {}).get("code") or "student"
    email = (data.get("email") or "").strip().lower() or f"{reg_number.lower()}@{uni_code.lower()}.student.shedulex"

    if User.query.filter_by(email=email).first():
        raise ValueError(f"A user with email '{email}' already exists.")

    username = reg_number.replace(" ", "").lower()
    if User.query.filter_by(username=username).first():
        username = f"{username}.{secrets.token_hex(3)}"

    department_name = _resolve_department_name(data["department_id"])
    plain_password = _generate_password()

    user = User(
        email=email,
        username=username,
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=phone,
        department=department_name,
        department_id=data["department_id"],
        program_id=data["program_id"],
        student_group_id=data["student_group_id"],
        registration_number=reg_number,
        university_id=university_id,
        role_id=role.id,
        is_active=True,
        is_approved=True,
        is_verified=True,
        must_change_password=False,
    )
    user.set_password(plain_password)
    db.session.add(user)
    db.session.commit()
    return user, plain_password


def create_portal_session(university_code: str, registration_number: str, phone_last4: str) -> dict:
    """Authenticate a student via reg number + phone last 4 and return a portal JWT."""
    uni = _resolve_university_by_code(university_code)
    if not uni:
        raise ValueError("University not found.")

    role = Role.query.filter_by(name="student").first()
    if not role:
        raise RuntimeError("Student role not found.")

    reg = registration_number.strip()
    user = User.query.filter_by(
        university_id=uni["id"],
        registration_number=reg,
        role_id=role.id,
        is_active=True,
        is_approved=True,
    ).first()
    if not user or not _phone_matches_last4(user.phone, phone_last4):
        raise ValueError("Invalid registration number or phone digits.")

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            "role": "student",
            "portal": True,
            "registration_number": user.registration_number,
            "student_group_id": user.student_group_id,
            "program_id": user.program_id,
            "university_id": str(user.university_id) if user.university_id else None,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
        expires_delta=timedelta(hours=24),
    )
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 86400,
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "registration_number": user.registration_number,
            "phone": user.phone,
            "email": user.email,
            "student_group_id": user.student_group_id,
            "program_id": user.program_id,
            "university_id": user.university_id,
        },
    }


def update_portal_subscription(user: User, data: dict) -> User:
    """Update phone/email for portal notification opt-in."""
    if data.get("phone"):
        user.phone = data["phone"]
    if data.get("email"):
        user.email = data["email"].lower()
    db.session.commit()
    return user


def resend_credentials(user_id: str) -> tuple[User, str]:
    """Reset the lecturer's password and resend credentials."""
    user = User.query.get(user_id)
    if not user:
        raise ValueError("User not found.")
    if user.role.name not in ("lecturer",):
        raise ValueError("Credential resend is only available for lecturer accounts.")

    plain_password = _generate_password()
    user.set_password(plain_password)
    user.must_change_password = True
    db.session.commit()

    try:
        send_lecturer_credentials_email(
            to=user.email,
            name=f"{user.first_name} {user.last_name}",
            username=user.username,
            password=plain_password,
        )
    except Exception:
        current_app.logger.warning("Credential resend email failed for %s", user.email)

    return user, plain_password


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

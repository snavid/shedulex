import secrets
from functools import wraps

from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request


def is_internal_request() -> bool:
    expected = current_app.config.get("INTERNAL_SERVICE_KEY")
    provided = request.headers.get("X-Internal-Service-Key", "")
    return bool(expected) and bool(provided) and secrets.compare_digest(provided, expected)


def get_jwt_university_id() -> str | None:
    """Return the university_id from the current JWT claims.
    Returns None for internal service requests (no tenant scope) or missing claims."""
    if is_internal_request():
        return None
    try:
        return get_jwt().get("university_id") or None
    except Exception:
        return None


def get_optional_jwt_university_id() -> str | None:
    """Best-effort JWT university_id — verifies a JWT if one is present, but never
    raises. Used by endpoints that must serve both authenticated (tenant-scoped)
    and anonymous (pre-login registration) callers."""
    if is_internal_request():
        return None
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    try:
        claims = get_jwt()
        return claims.get("university_id") if claims else None
    except Exception:
        return None


def portal_jwt_required(fn):
    """Require a valid portal JWT (portal=true claim)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if is_internal_request():
            return fn(*args, **kwargs)
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({"success": False, "message": "Authorization token required."}), 401
        claims = get_jwt()
        if not claims.get("portal"):
            return jsonify({"success": False, "message": "Portal access token required."}), 403
        return fn(*args, **kwargs)

    return wrapper


def service_or_jwt_required(*roles):
    """Allow either trusted internal service key or a valid JWT."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if is_internal_request():
                return fn(*args, **kwargs)

            try:
                verify_jwt_in_request()
            except Exception:
                return jsonify({"success": False, "message": "Authorization token required."}), 401

            if roles:
                claims = get_jwt()
                if claims.get("role") not in roles:
                    return jsonify({"success": False, "message": "Forbidden."}), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator

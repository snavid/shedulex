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

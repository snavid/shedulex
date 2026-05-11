from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request


def roles_required(*roles):
    """Decorator: require the JWT bearer to have one of the listed roles."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            user_role = claims.get("role", "")
            if user_role not in roles:
                return jsonify({"success": False, "message": "Insufficient permissions."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def permission_required(permission: str):
    """Decorator: require the JWT bearer to have a specific permission."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            perms = claims.get("permissions", [])
            if "*" not in perms and permission not in perms:
                return jsonify({"success": False, "message": "Insufficient permissions."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

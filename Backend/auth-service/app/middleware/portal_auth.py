from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request


def portal_jwt_required(fn):
    """Require a valid portal JWT (portal=true claim)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if not claims.get("portal"):
            return jsonify({"success": False, "message": "Portal access token required."}), 403
        return fn(*args, **kwargs)

    return wrapper

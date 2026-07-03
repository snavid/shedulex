import secrets

from flask import current_app, jsonify, request


def is_internal_request() -> bool:
    expected = current_app.config.get("INTERNAL_SERVICE_KEY")
    provided = request.headers.get("X-Internal-Service-Key", "")
    return bool(expected) and bool(provided) and secrets.compare_digest(provided, expected)


def require_internal_key():
    if not is_internal_request():
        return jsonify({"success": False, "message": "Forbidden."}), 403
    return None

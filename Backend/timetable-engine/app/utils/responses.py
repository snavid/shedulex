from flask import jsonify, request


def json_body() -> dict:
    return request.get_json() or {}


def ok(*, data=None, message=None, status=200, extra: dict | None = None):
    payload = {"success": True}
    if message is not None:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    if extra:
        payload.update(extra)
    return jsonify(payload), status


def fail(message: str, *, status=400, errors=None):
    payload = {"success": False, "message": message}
    if errors is not None:
        payload["errors"] = errors
    return jsonify(payload), status


def require_fields(body: dict, fields: list[str]) -> tuple[bool, str | None]:
    for field in fields:
        if not body.get(field):
            return False, field
    return True, None

from flask import jsonify


def success(data=None, message="Success", status=200, meta=None):
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    if meta is not None:
        payload["meta"] = meta
    return jsonify(payload), status


def error(message="An error occurred", status=400, errors=None):
    payload = {"success": False, "message": message}
    if errors is not None:
        payload["errors"] = errors
    return jsonify(payload), status

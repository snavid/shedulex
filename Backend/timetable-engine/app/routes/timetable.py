from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.services import timetable_service

timetable_bp = Blueprint("timetable", __name__, url_prefix="/api/v1/timetable")


@timetable_bp.post("/generate")
@jwt_required()
def generate():
    claims = get_jwt()
    if claims.get("role") not in ("admin", "timetable_officer"):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    body = request.get_json() or {}
    required = ["department_id", "semester", "academic_year", "name"]
    for field in required:
        if not body.get(field):
            return jsonify({"success": False, "message": f"'{field}' is required."}), 422

    try:
        timetable = timetable_service.generate_timetable(
            department_id=body["department_id"],
            semester=int(body["semester"]),
            academic_year=body["academic_year"],
            name=body["name"],
            created_by=get_jwt_identity(),
            config_overrides=body.get("ga_config"),
        )
    except (ValueError, RuntimeError) as e:
        return jsonify({"success": False, "message": str(e)}), 400

    return jsonify({
        "success": True,
        "message": "Timetable generated successfully.",
        "data": timetable.to_dict(include_entries=True),
    }), 201


@timetable_bp.get("/")
@jwt_required()
def list_timetables():
    dept = request.args.get("department_id")
    sem = request.args.get("semester", type=int)
    status = request.args.get("status")
    timetables = timetable_service.list_timetables(dept, sem, status)
    return jsonify({"success": True, "data": [t.to_dict() for t in timetables]}), 200


@timetable_bp.get("/<timetable_id>")
@jwt_required()
def get_timetable(timetable_id):
    tt = timetable_service.get_timetable_by_id(timetable_id)
    if not tt:
        return jsonify({"success": False, "message": "Timetable not found."}), 404
    return jsonify({"success": True, "data": tt.to_dict(include_entries=True)}), 200


@timetable_bp.get("/<timetable_id>/conflicts")
@jwt_required()
def get_conflicts(timetable_id):
    conflicts = timetable_service.detect_conflicts(timetable_id)
    return jsonify({"success": True, "data": conflicts, "total": len(conflicts)}), 200


@timetable_bp.post("/entries/swap")
@jwt_required()
def swap_entries():
    claims = get_jwt()
    if claims.get("role") not in ("admin", "timetable_officer"):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    body = request.get_json() or {}
    e1_id = body.get("entry1_id")
    e2_id = body.get("entry2_id")
    if not e1_id or not e2_id:
        return jsonify({"success": False, "message": "entry1_id and entry2_id required."}), 422

    try:
        e1, e2 = timetable_service.swap_entries(e1_id, e2_id)
    except ValueError as ex:
        return jsonify({"success": False, "message": str(ex)}), 400

    return jsonify({"success": True, "data": {"entry1": e1.to_dict(), "entry2": e2.to_dict()}}), 200

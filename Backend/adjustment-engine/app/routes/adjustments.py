from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from langchain_core.messages import HumanMessage
from app.extensions import db
from app.models.adjustment import AdjustmentRequest, ConflictLog
from app.agents import get_graph, AdjustmentState

adjustments_bp = Blueprint("adjustments", __name__, url_prefix="/api/v1/adjustments")


@adjustments_bp.post("/chat")
@jwt_required()
def ai_chat():
    """Natural language timetable adjustment via LangGraph AI agent."""
    body = request.get_json() or {}
    prompt = body.get("prompt", "").strip()
    timetable_id = body.get("timetable_id", "")

    if not prompt or not timetable_id:
        return jsonify({"success": False, "message": "prompt and timetable_id are required."}), 422

    adj = AdjustmentRequest(
        timetable_id=timetable_id,
        requested_by=get_jwt_identity(),
        prompt=prompt,
        status="processing",
    )
    db.session.add(adj)
    db.session.commit()

    try:
        graph = get_graph()
        initial_state: AdjustmentState = {
            "messages": [HumanMessage(content=f"Timetable ID: {timetable_id}\n\nRequest: {prompt}")],
            "timetable_id": timetable_id,
            "intent": "",
            "resolved": False,
            "suggestions": [],
            "conflicts": [],
            "context": {},
        }
        result = graph.invoke(initial_state)
        final_message = result["messages"][-1]
        response_text = final_message.content if hasattr(final_message, "content") else str(final_message)

        adj.response = response_text
        adj.status = "completed"
        adj.completed_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({
            "success": True,
            "data": {
                "request_id": adj.id,
                "response": response_text,
                "status": "completed",
            },
        }), 200

    except Exception as exc:
        adj.status = "failed"
        adj.response = str(exc)
        db.session.commit()
        return jsonify({"success": False, "message": f"AI processing failed: {exc}"}), 500


@adjustments_bp.get("/history")
@jwt_required()
def get_history():
    timetable_id = request.args.get("timetable_id")
    q = AdjustmentRequest.query
    if timetable_id:
        q = q.filter_by(timetable_id=timetable_id)
    requests = q.order_by(AdjustmentRequest.created_at.desc()).limit(50).all()
    return jsonify({"success": True, "data": [r.to_dict() for r in requests]}), 200


@adjustments_bp.get("/conflicts")
@jwt_required()
def get_conflicts():
    timetable_id = request.args.get("timetable_id")
    q = ConflictLog.query
    if timetable_id:
        q = q.filter_by(timetable_id=timetable_id)
    resolved = request.args.get("resolved")
    if resolved is not None:
        q = q.filter_by(resolved=(resolved.lower() == "true"))
    conflicts = q.order_by(ConflictLog.created_at.desc()).all()
    return jsonify({"success": True, "data": [c.to_dict() for c in conflicts]}), 200


@adjustments_bp.post("/conflicts/<conflict_id>/resolve")
@jwt_required()
def resolve_conflict(conflict_id):
    conflict = ConflictLog.query.get(conflict_id)
    if not conflict:
        return jsonify({"success": False, "message": "Conflict not found."}), 404
    body = request.get_json() or {}
    conflict.resolved = True
    conflict.resolution = body.get("resolution", "Manually resolved.")
    db.session.commit()
    return jsonify({"success": True, "data": conflict.to_dict()}), 200


@adjustments_bp.post("/suggest-slots")
@jwt_required()
def suggest_slots():
    """Rule-based slot suggestion (no AI): returns free slots for a lecturer."""
    body = request.get_json() or {}
    lecturer_id = body.get("lecturer_id")
    timetable_id = body.get("timetable_id")
    if not lecturer_id or not timetable_id:
        return jsonify({"success": False, "message": "lecturer_id and timetable_id required."}), 422

    from app.agents.tools import get_lecturer_free_slots
    result = get_lecturer_free_slots.invoke({"lecturer_id": lecturer_id, "timetable_id": timetable_id})
    return jsonify({"success": True, "data": result}), 200

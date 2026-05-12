from __future__ import annotations

import json
from datetime import datetime, timezone
from threading import Thread

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from langchain_core.messages import HumanMessage, ToolMessage

from app.extensions import db
from app.models.adjustment import AdjustmentRequest, ConflictLog, TOOL_TRACE_MARKER
from app.agents import get_graph, AdjustmentState
from app.services.timetable_snapshots import create_timetable_snapshot

adjustments_bp = Blueprint("adjustments", __name__, url_prefix="/api/v1/adjustments")


def _extract_tool_trace(messages: list) -> list[dict]:
    trace = []
    for m in messages or []:
        if isinstance(m, ToolMessage):
            name = getattr(m, "name", None)
            if name is None or str(name).strip() == "":
                ak = getattr(m, "additional_kwargs", None) or {}
                name = ak.get("name") or "unknown"
            trace.append({
                "tool": str(name),
                "output": str(getattr(m, "content", m))[:3000],
            })
    return trace


def _mutation_recorded_in_trace(trace: list[dict]) -> bool:
    """True if a swap/move tool reported success (matches tools.py return strings)."""
    for t in trace or []:
        out = str(t.get("output", "")).strip()
        if out.startswith("Swap successful:") or out.startswith("Move successful:"):
            return True
    return False


def _user_requested_schedule_change(prompt: str) -> bool:
    p = (prompt or "").lower()
    keys = (
        "don't want", "dont want", "do not want", "remove", "move", "swap",
        "reschedule", "change schedule", "not on ", "no longer", "don't need",
        "dont need", "take off", "cancel ", "avoid ", "get rid",
    )
    return any(k in p for k in keys)


def _finalize_ai_response(response_text: str, trace: list[dict], prompt: str) -> str:
    """If the user asked to change the timetable but no mutation succeeded, append a clear disclaimer."""
    base = (response_text or "").strip()
    if not base:
        base = "No assistant message was produced."
    if _user_requested_schedule_change(prompt) and not _mutation_recorded_in_trace(trace):
        disclaimer = (
            "\n\n---\nImportant: The live timetable was NOT updated in the database — "
            "no successful swap or move was recorded. Expand Tool trace to see tool outputs "
            "(failed calls, wrong IDs, or occupied slots). Open the timetable page again to load latest data."
        )
        return base + disclaimer
    return base


def _run_adjustment_job(app, adjustment_id: str, timetable_id: str, prompt: str):
    with app.app_context():
        adj = AdjustmentRequest.query.get(adjustment_id)
        if not adj:
            return

        create_timetable_snapshot(
            timetable_id,
            f"Before AI request {adjustment_id}: {prompt[:200]}",
            adjustment_id,
        )

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
            result = graph.invoke(initial_state, config={"recursion_limit": 48})
            messages_out = result.get("messages", [])
            trace = _extract_tool_trace(messages_out)
            final_message = messages_out[-1]
            response_text = final_message.content if hasattr(final_message, "content") else str(final_message)
            response_text = _finalize_ai_response(response_text, trace, prompt)

            adj.response = (
                response_text
                + TOOL_TRACE_MARKER
                + json.dumps(trace)
            )
            adj.status = "completed"
            adj.completed_at = datetime.now(timezone.utc)
            db.session.commit()

            create_timetable_snapshot(
                timetable_id,
                f"After AI request {adjustment_id}",
                adjustment_id,
            )
        except Exception as exc:
            adj.status = "failed"
            adj.response = str(exc)
            db.session.commit()


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

    app = current_app._get_current_object()
    worker = Thread(
        target=_run_adjustment_job,
        args=(app, adj.id, timetable_id, prompt),
        daemon=True,
    )
    worker.start()

    return jsonify({
        "success": True,
        "data": {
            "request_id": adj.id,
            "status": "processing",
            "message": "AI request accepted and is processing.",
        },
    }), 202


@adjustments_bp.get("/requests/<request_id>")
@jwt_required()
def get_request_status(request_id):
    req = AdjustmentRequest.query.get(request_id)
    if not req:
        return jsonify({"success": False, "message": "Request not found."}), 404
    return jsonify({"success": True, "data": req.to_dict()}), 200


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

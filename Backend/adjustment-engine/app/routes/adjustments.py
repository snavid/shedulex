"""
Adjustment engine routes — session-based AI chat with SSE streaming.

New session-based API:
  POST   /sessions                    — create (or get active) session for a timetable
  GET    /sessions                    — list sessions for a timetable
  GET    /sessions/<id>               — get session detail
  POST   /sessions/<id>/chat          — send a message (returns 202, streams via SSE)
  GET    /sessions/<id>/stream        — SSE event stream for a session
  POST   /sessions/<id>/respond       — provide human answer after an interrupt
  POST   /sessions/<id>/archive       — manually archive a full session

Legacy single-shot API (kept for backwards compatibility):
  POST   /chat
  GET    /requests/<id>
  GET    /history
  GET    /conflicts
  POST   /conflicts/<id>/resolve
  POST   /suggest-slots
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from threading import Thread

from flask import Blueprint, Response, request, jsonify, current_app, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command

from app.extensions import db
from app.models.adjustment import (
    AdjustmentRequest, ConflictLog, ConversationSession,
    TOOL_TRACE_MARKER,
)
from app.agents import get_graph, AdjustmentState
from app.agents.graph import thread_config
from app.services import timetable_snapshots
from app.services.memory import compress_session, build_memory_context
from app.services.vector_store import store_session_summary, retrieve_relevant_context
from app.services.redis_pubsub import publish, subscribe, get_event_log, clear_event_log

logger = logging.getLogger(__name__)
adjustments_bp = Blueprint("adjustments", __name__, url_prefix="/api/v1/adjustments")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_name_from_jwt() -> str:
    claims = get_jwt()
    first  = claims.get("first_name") or claims.get("email") or ""
    last   = claims.get("last_name") or ""
    return (first + " " + last).strip() or "timetable officer"


def _extract_tool_trace(messages: list) -> list[dict]:
    trace = []
    for m in messages or []:
        if isinstance(m, ToolMessage):
            name = getattr(m, "name", None) or (getattr(m, "additional_kwargs", {}) or {}).get("name") or "unknown"
            trace.append({"tool": str(name), "output": str(getattr(m, "content", m))[:3000]})
    return trace


def _run_session_job(app, session_id: str, prompt: str, is_resume: bool = False, resume_value: str = ""):
    """Background thread: runs/resumes the LangGraph agent for a session."""
    with app.app_context():
        session = ConversationSession.query.get(session_id)
        if not session:
            return

        graph  = get_graph()
        config = thread_config(session_id)

        def emit(event: dict):
            publish(session_id, event)

        try:
            if is_resume:
                # Resume after interrupt
                emit({"type": "thinking", "content": "Continuing with your decision…"})
                stream_input = Command(resume=resume_value)
            else:
                # Build initial state with memory context
                past_ctx = retrieve_relevant_context(session.timetable_id, prompt, top_k=3)
                mem_ctx   = build_memory_context(session)
                full_ctx  = (past_ctx + "\n" + mem_ctx).strip()

                history_msgs = []
                for m in (session.messages or []):
                    if m.get("role") == "user":
                        history_msgs.append(HumanMessage(content=m["content"]))

                stream_input = {
                    "messages":       history_msgs + [HumanMessage(content=prompt)],
                    "timetable_id":   session.timetable_id,
                    "session_id":     session_id,
                    "user_name":      session.user_name or "timetable officer",
                    "memory_context": full_ctx,
                    "waiting_for_input": False,
                    "interrupt_question": "",
                    "intent": "", "resolved": False,
                    "suggestions": [], "conflicts": [], "context": {},
                }
                emit({"type": "thinking", "content": "Analysing your request…"})

            response_text = ""
            tool_trace    = []

            for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
                # ── interrupt from ask_user tool ──
                if "__interrupt__" in chunk:
                    iv = chunk["__interrupt__"]
                    interrupt_value = iv[0].value if hasattr(iv[0], "value") else iv[0]
                    question = interrupt_value.get("question", str(interrupt_value)) if isinstance(interrupt_value, dict) else str(interrupt_value)
                    session.status         = "waiting_for_input"
                    session.interrupt_data = {"question": question}
                    session.last_activity  = datetime.now(timezone.utc)
                    db.session.commit()
                    emit({"type": "interrupt", "question": question})
                    return

                for node_name, node_output in chunk.items():
                    if node_name == "agent":
                        msgs = node_output.get("messages", [])
                        for m in msgs:
                            if hasattr(m, "tool_calls") and m.tool_calls:
                                for tc in m.tool_calls:
                                    tool_name = tc.get("name", "tool")
                                    emit({
                                        "type":  "tool_start",
                                        "tool":  tool_name,
                                        "input": str(tc.get("args", {}))[:400],
                                    })
                            elif hasattr(m, "content") and m.content:
                                response_text = m.content

                    elif node_name == "tools":
                        msgs = node_output.get("messages", [])
                        for m in msgs:
                            if isinstance(m, ToolMessage):
                                output = str(getattr(m, "content", ""))
                                tool_trace.append({"tool": m.name, "output": output[:3000]})
                                emit({
                                    "type":    "tool_end",
                                    "tool":    m.name,
                                    "output":  output[:400],
                                    "success": output.startswith(("Move successful:", "Swap successful:")),
                                })

            # ── Job finished (no interrupt) ──
            session.status = "active"

            ts = datetime.now(timezone.utc).isoformat()
            msgs = session.messages or []
            msgs.append({"role": "user",      "content": prompt,        "ts": ts})
            msgs.append({"role": "assistant",  "content": response_text, "ts": ts, "tool_trace": tool_trace})
            session.messages        = msgs
            session.total_messages  = len(msgs)
            session.interrupt_data  = None
            session.last_activity   = datetime.now(timezone.utc)

            # Compress memory if threshold reached
            if session.needs_compression:
                compress_session(session)
                # Store compressed summary in ChromaDB
                if session.compressed_summary:
                    store_session_summary(session_id, session.timetable_id, session.compressed_summary)

            db.session.commit()

            # Create snapshot (before/after already handled by individual tools)
            timetable_snapshots.create_timetable_snapshot(
                session.timetable_id,
                f"Sora AI session {session_id}: {prompt[:200]}",
                session.user_name or "Sora AI",
            )

            emit({"type": "done", "response": response_text, "tool_trace": tool_trace})

        except Exception as exc:
            logger.exception("Session job failed for %s", session_id)
            try:
                session.status = "active"
                db.session.commit()
            except Exception:
                pass
            emit({"type": "error", "message": str(exc)})


# ══════════════════════════════════════════════════════════════════════════════
# Session endpoints
# ══════════════════════════════════════════════════════════════════════════════

@adjustments_bp.post("/sessions")
@jwt_required()
def create_or_get_session():
    """Get the active session for a timetable, or create one."""
    body         = request.get_json() or {}
    timetable_id = body.get("timetable_id", "").strip()
    if not timetable_id:
        return jsonify({"success": False, "message": "timetable_id required"}), 422

    user_id   = get_jwt_identity()
    user_name = _user_name_from_jwt()

    # Try to reuse an existing active session
    existing = (
        ConversationSession.query
        .filter_by(timetable_id=timetable_id, user_id=user_id, status="active")
        .order_by(ConversationSession.last_activity.desc())
        .first()
    )
    if existing and not existing.is_full:
        return jsonify({"success": True, "data": existing.to_dict()}), 200

    # Create a new session
    session = ConversationSession(
        timetable_id=timetable_id,
        user_id=user_id,
        user_name=user_name,
        messages=[],
    )
    db.session.add(session)
    db.session.commit()
    return jsonify({"success": True, "data": session.to_dict()}), 201


@adjustments_bp.get("/sessions")
@jwt_required()
def list_sessions():
    timetable_id = request.args.get("timetable_id")
    q = ConversationSession.query.filter_by(user_id=get_jwt_identity())
    if timetable_id:
        q = q.filter_by(timetable_id=timetable_id)
    sessions = q.order_by(ConversationSession.last_activity.desc()).limit(20).all()
    return jsonify({"success": True, "data": [s.to_dict() for s in sessions]}), 200


@adjustments_bp.get("/sessions/<session_id>")
@jwt_required()
def get_session(session_id):
    s = ConversationSession.query.get_or_404(session_id)
    return jsonify({"success": True, "data": s.to_dict()}), 200


@adjustments_bp.post("/sessions/<session_id>/chat")
@jwt_required()
def session_chat(session_id):
    """Send a user message to an active session. Agent runs in background, stream via SSE."""
    s = ConversationSession.query.get_or_404(session_id)
    if s.status == "waiting_for_input":
        return jsonify({"success": False, "message": "Session is waiting for your response. Use /respond."}), 409
    if s.is_full:
        return jsonify({"success": False, "message": "Session is full. Start a new chat."}), 409

    body   = request.get_json() or {}
    prompt = body.get("prompt", "").strip()
    if not prompt:
        return jsonify({"success": False, "message": "prompt required"}), 422

    clear_event_log(session_id)
    s.status        = "active"
    s.last_activity = datetime.now(timezone.utc)
    db.session.commit()

    app = current_app._get_current_object()
    Thread(target=_run_session_job, args=(app, session_id, prompt), daemon=True).start()

    return jsonify({"success": True, "data": {"session_id": session_id, "status": "processing"}}), 202


@adjustments_bp.post("/sessions/<session_id>/respond")
@jwt_required()
def session_respond(session_id):
    """Provide the human answer after an interrupt and resume the agent."""
    s = ConversationSession.query.get_or_404(session_id)
    if s.status != "waiting_for_input":
        return jsonify({"success": False, "message": "Session is not waiting for input."}), 409

    body   = request.get_json() or {}
    answer = body.get("answer", "").strip()
    if not answer:
        return jsonify({"success": False, "message": "answer required"}), 422

    # Add user decision to message history immediately (visible in chat)
    ts   = datetime.now(timezone.utc).isoformat()
    msgs = s.messages or []
    msgs.append({"role": "user", "content": f"[Decision] {answer}", "ts": ts})
    s.messages       = msgs
    s.total_messages = len(msgs)
    s.status         = "active"
    s.interrupt_data = None
    s.last_activity  = datetime.now(timezone.utc)
    db.session.commit()

    clear_event_log(session_id)

    app = current_app._get_current_object()
    Thread(
        target=_run_session_job,
        args=(app, session_id, answer, True, answer),
        daemon=True,
    ).start()

    return jsonify({"success": True, "data": {"session_id": session_id, "status": "resumed"}}), 202


@adjustments_bp.post("/sessions/<session_id>/archive")
@jwt_required()
def archive_session(session_id):
    s = ConversationSession.query.get_or_404(session_id)
    s.status = "archived"
    db.session.commit()
    return jsonify({"success": True, "data": s.to_dict()}), 200


# ── SSE stream endpoint ───────────────────────────────────────────────────────

@adjustments_bp.get("/sessions/<session_id>/stream")
@jwt_required()
def session_stream(session_id):
    """
    Server-Sent Events endpoint — delivers real-time agent steps to the frontend.

    Events emitted (JSON):
      {type: "connected"}
      {type: "thinking",   content: "..."}
      {type: "tool_start", tool: "...", input: "..."}
      {type: "tool_end",   tool: "...", output: "...", success: bool}
      {type: "interrupt",  question: "..."}
      {type: "done",       response: "...", tool_trace: [...]}
      {type: "error",      message: "..."}
      {type: "keepalive"}   — sent every 15 s to keep connection alive
    """
    def generate():
        yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

        # Replay any events that were published before the client connected
        for ev in get_event_log(session_id):
            yield f"data: {json.dumps(ev)}\n\n"
            if ev.get("type") in ("done", "error", "interrupt"):
                return

        # Subscribe for live events
        ps = subscribe(session_id)
        idle = 0
        max_idle = 300  # 5 minutes

        try:
            while idle < max_idle:
                msg = ps.get_message(timeout=1.0)
                if msg is None:
                    idle += 1
                    if idle % 15 == 0:
                        yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
                    continue

                if msg["type"] == "subscribe":
                    continue

                data = msg["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                yield f"data: {data}\n\n"

                parsed = json.loads(data)
                if parsed.get("type") in ("done", "error", "interrupt"):
                    break
                idle = 0  # reset on real event

        except GeneratorExit:
            pass
        finally:
            try:
                ps.unsubscribe()
                ps.close()
            except Exception:
                pass

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# Legacy single-shot API (backwards compatible)
# ══════════════════════════════════════════════════════════════════════════════

def _extract_legacy_tool_trace(messages: list) -> list[dict]:
    trace = []
    for m in messages or []:
        if isinstance(m, ToolMessage):
            name = getattr(m, "name", None) or (getattr(m, "additional_kwargs", {}) or {}).get("name") or "unknown"
            trace.append({"tool": str(name), "output": str(getattr(m, "content", m))[:3000]})
    return trace


def _run_legacy_job(app, adjustment_id: str, timetable_id: str, prompt: str):
    with app.app_context():
        adj = AdjustmentRequest.query.get(adjustment_id)
        if not adj:
            return

        timetable_snapshots.create_timetable_snapshot(
            timetable_id, f"Before AI request {adjustment_id}: {prompt[:200]}", adjustment_id
        )

        try:
            graph  = get_graph()
            config = thread_config(f"legacy-{adjustment_id}")
            state: AdjustmentState = {
                "messages":           [HumanMessage(content=f"Timetable ID: {timetable_id}\n\nRequest: {prompt}")],
                "timetable_id":       timetable_id,
                "session_id":         f"legacy-{adjustment_id}",
                "user_name":          "timetable officer",
                "memory_context":     "",
                "waiting_for_input":  False,
                "interrupt_question": "",
                "intent":             "",
                "resolved":           False,
                "suggestions":        [],
                "conflicts":          [],
                "context":            {},
            }
            result      = graph.invoke(state, config=config)
            msgs_out    = result.get("messages", [])
            trace       = _extract_legacy_tool_trace(msgs_out)
            last        = msgs_out[-1]
            response    = last.content if hasattr(last, "content") else str(last)

            adj.response     = response + TOOL_TRACE_MARKER + json.dumps(trace)
            adj.status       = "completed"
            adj.completed_at = datetime.now(timezone.utc)
            db.session.commit()

            timetable_snapshots.create_timetable_snapshot(
                timetable_id, f"After AI request {adjustment_id}", adjustment_id
            )
        except Exception as exc:
            adj.status   = "failed"
            adj.response = str(exc)
            db.session.commit()


@adjustments_bp.post("/chat")
@jwt_required()
def ai_chat():
    body         = request.get_json() or {}
    prompt       = body.get("prompt", "").strip()
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
    Thread(target=_run_legacy_job, args=(app, adj.id, timetable_id, prompt), daemon=True).start()

    return jsonify({"success": True, "data": {"request_id": adj.id, "status": "processing"}}), 202


@adjustments_bp.get("/requests/<request_id>")
@jwt_required()
def get_request_status(request_id):
    req = AdjustmentRequest.query.get_or_404(request_id)
    return jsonify({"success": True, "data": req.to_dict()}), 200


@adjustments_bp.get("/history")
@jwt_required()
def get_history():
    timetable_id = request.args.get("timetable_id")
    q = AdjustmentRequest.query.filter_by(requested_by=get_jwt_identity())
    if timetable_id:
        q = q.filter_by(timetable_id=timetable_id)
    reqs = q.order_by(AdjustmentRequest.created_at.desc()).limit(50).all()
    return jsonify({"success": True, "data": [r.to_dict() for r in reqs]}), 200


@adjustments_bp.get("/conflicts")
@jwt_required()
def get_conflicts():
    timetable_id = request.args.get("timetable_id")
    if not timetable_id:
        return jsonify({"success": True, "data": []}), 200
    q = ConflictLog.query.filter_by(timetable_id=timetable_id)
    resolved = request.args.get("resolved")
    if resolved is not None:
        q = q.filter_by(resolved=(resolved.lower() == "true"))
    conflicts = q.order_by(ConflictLog.created_at.desc()).all()
    return jsonify({"success": True, "data": [c.to_dict() for c in conflicts]}), 200


@adjustments_bp.post("/conflicts/<conflict_id>/resolve")
@jwt_required()
def resolve_conflict(conflict_id):
    conflict = ConflictLog.query.get_or_404(conflict_id)
    body = request.get_json() or {}
    conflict.resolved   = True
    conflict.resolution = body.get("resolution", "Manually resolved.")
    db.session.commit()
    return jsonify({"success": True, "data": conflict.to_dict()}), 200


@adjustments_bp.post("/suggest-slots")
@jwt_required()
def suggest_slots():
    body         = request.get_json() or {}
    lecturer_id  = body.get("lecturer_id")
    timetable_id = body.get("timetable_id")
    if not lecturer_id or not timetable_id:
        return jsonify({"success": False, "message": "lecturer_id and timetable_id required."}), 422

    from app.agents.tools import get_lecturer_free_slots
    result = get_lecturer_free_slots.invoke({"lecturer_id": lecturer_id, "timetable_id": timetable_id})
    return jsonify({"success": True, "data": result}), 200

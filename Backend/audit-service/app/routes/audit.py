import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.extensions import db
from app.models.audit_log import AuditLog

audit_bp = Blueprint("audit", __name__, url_prefix="/api/v1/audit")

_INTERNAL_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "")


@audit_bp.post("/log")
def create_log():
    """Internal endpoint — called by other services to log events."""
    if _INTERNAL_KEY and request.headers.get("X-Internal-Key", "") != _INTERNAL_KEY:
        return jsonify({"success": False, "message": "Unauthorized."}), 401
    body = request.get_json() or {}
    log = AuditLog(
        user_id=body.get("user_id"),
        action=body.get("action", "unknown"),
        resource_type=body.get("resource_type"),
        resource_id=body.get("resource_id"),
        description=body.get("description"),
        ip_address=body.get("ip_address") or request.remote_addr,
        user_agent=body.get("user_agent") or request.headers.get("User-Agent", "")[:500],
        service=body.get("service"),
        status=body.get("status", "success"),
        metadata_=body.get("metadata", {}),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"success": True, "data": log.to_dict()}), 201


@audit_bp.get("/logs")
@jwt_required()
def list_logs():
    claims = get_jwt()
    if claims.get("role") not in ("admin",):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    user_id = request.args.get("user_id")
    action = request.args.get("action")
    service = request.args.get("service")

    q = AuditLog.query
    if user_id:
        q = q.filter_by(user_id=user_id)
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if service:
        q = q.filter_by(service=service)

    pagination = q.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "success": True,
        "data": [l.to_dict() for l in pagination.items],
        "meta": {"page": page, "per_page": per_page, "total": pagination.total},
    }), 200


@audit_bp.get("/logs/user/<user_id>")
@jwt_required()
def user_activity(user_id):
    requester = get_jwt()
    if requester.get("role") not in ("admin",) and requester.get("sub") != user_id:
        return jsonify({"success": False, "message": "Forbidden."}), 403

    logs = AuditLog.query.filter_by(user_id=user_id).order_by(AuditLog.created_at.desc()).limit(100).all()
    return jsonify({"success": True, "data": [l.to_dict() for l in logs]}), 200


@audit_bp.get("/logs/stats")
@jwt_required()
def log_stats():
    claims = get_jwt()
    if claims.get("role") not in ("admin",):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    from sqlalchemy import func
    action_counts = db.session.query(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action).all()
    service_counts = db.session.query(AuditLog.service, func.count(AuditLog.id)).group_by(AuditLog.service).all()
    return jsonify({
        "success": True,
        "data": {
            "by_action": {a: c for a, c in action_counts},
            "by_service": {s: c for s, c in service_counts},
            "total": AuditLog.query.count(),
        },
    }), 200

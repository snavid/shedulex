import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import func, or_

from app.extensions import db
from app.models.audit_log import AuditLog
from app.services.user_lookup import lookup_users

audit_bp = Blueprint("audit", __name__, url_prefix="/api/v1/audit")

_INTERNAL_KEY = os.environ.get("INTERNAL_SERVICE_KEY", "")


def _parse_date(value: str | None, *, end_of_day: bool = False):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if end_of_day and len(value) <= 10:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return dt
    except ValueError:
        return None


def _apply_filters(q, uni_id: str | None):
    user_id = request.args.get("user_id")
    user_email = request.args.get("user_email")
    action = request.args.get("action")
    service = request.args.get("service")
    status = request.args.get("status")
    search = request.args.get("search")
    from_date = _parse_date(request.args.get("from_date"))
    to_date = _parse_date(request.args.get("to_date"), end_of_day=True)

    if uni_id:
        q = q.filter_by(university_id=uni_id)
    if user_id:
        q = q.filter_by(user_id=user_id)
    if user_email:
        q = q.filter(AuditLog.user_email.ilike(f"%{user_email}%"))
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if service:
        q = q.filter(AuditLog.service.ilike(f"%{service}%"))
    if status:
        q = q.filter_by(status=status)
    if search:
        q = q.filter(
            or_(
                AuditLog.description.ilike(f"%{search}%"),
                AuditLog.action.ilike(f"%{search}%"),
                AuditLog.user_email.ilike(f"%{search}%"),
                AuditLog.user_name.ilike(f"%{search}%"),
            )
        )
    if from_date:
        q = q.filter(AuditLog.created_at >= from_date)
    if to_date:
        q = q.filter(AuditLog.created_at <= to_date)
    return q


def _serialize_logs(logs: list[AuditLog]) -> list[dict]:
    missing_ids = [
        log.user_id for log in logs
        if log.user_id and not log.user_name and not log.user_email
    ]
    resolved = lookup_users(list(set(missing_ids)))

    items = []
    for log in logs:
        data = log.to_dict()
        if log.user_id and log.user_id in resolved:
            info = resolved[log.user_id]
            data["user_email"] = data.get("user_email") or info.get("email")
            data["user_name"] = data.get("user_name") or info.get("display_name")
        data["display_user"] = (
            data.get("user_name")
            or data.get("user_email")
            or (f"User {log.user_id[:8]}…" if log.user_id else "System")
        )
        items.append(data)
    return items


@audit_bp.post("/log")
def create_log():
    """Internal endpoint — called by other services to log events."""
    if _INTERNAL_KEY and request.headers.get("X-Internal-Key", "") != _INTERNAL_KEY:
        return jsonify({"success": False, "message": "Unauthorized."}), 401
    body = request.get_json() or {}
    log = AuditLog(
        user_id=body.get("user_id"),
        user_email=body.get("user_email"),
        user_name=body.get("user_name"),
        university_id=body.get("university_id"),
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
    data = log.to_dict()
    data["display_user"] = log.display_user()
    return jsonify({"success": True, "data": data}), 201


@audit_bp.get("/logs")
@jwt_required()
def list_logs():
    claims = get_jwt()
    if claims.get("role") not in ("admin",):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)

    q = _apply_filters(AuditLog.query, claims.get("university_id"))
    pagination = q.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "success": True,
        "data": _serialize_logs(pagination.items),
        "meta": {"page": page, "per_page": per_page, "total": pagination.total, "pages": pagination.pages},
    }), 200


@audit_bp.get("/logs/user/<user_id>")
@jwt_required()
def user_activity(user_id):
    requester = get_jwt()
    if requester.get("role") not in ("admin",) and requester.get("sub") != user_id:
        return jsonify({"success": False, "message": "Forbidden."}), 403

    q = AuditLog.query.filter_by(user_id=user_id)
    uni_id = requester.get("university_id")
    if uni_id:
        q = q.filter_by(university_id=uni_id)
    logs = q.order_by(AuditLog.created_at.desc()).limit(100).all()
    return jsonify({"success": True, "data": _serialize_logs(logs)}), 200


@audit_bp.get("/logs/stats")
@jwt_required()
def log_stats():
    claims = get_jwt()
    if claims.get("role") not in ("admin",):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    base = _apply_filters(AuditLog.query, claims.get("university_id"))

    action_counts = (
        base.with_entities(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action).all()
    )
    service_counts = (
        base.with_entities(AuditLog.service, func.count(AuditLog.id))
        .group_by(AuditLog.service).all()
    )
    return jsonify({
        "success": True,
        "data": {
            "by_action": {a: c for a, c in action_counts if a},
            "by_service": {s: c for s, c in service_counts if s},
            "total": base.count(),
        },
    }), 200

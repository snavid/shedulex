from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app.extensions import db
from app.models.notification import Notification, NotificationTemplate
from app.services.sms_service import send_sms, send_bulk_sms
from app.services.email_service import send_email

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/v1/notifications")


@notifications_bp.post("/send")
@jwt_required()
def send_notification():
    claims = get_jwt()
    if claims.get("role") not in ("admin", "timetable_officer"):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    body = request.get_json() or {}
    notif = Notification(
        recipient_id=body.get("recipient_id"),
        recipient_email=body.get("email"),
        recipient_phone=body.get("phone"),
        channel=body.get("channel", "email"),
        subject=body.get("subject", ""),
        body=body.get("body", ""),
        notification_type=body.get("type", "general"),
        scheduled_at=datetime.now(timezone.utc),
    )
    db.session.add(notif)
    db.session.commit()

    # Send immediately
    sent = False
    if notif.channel in ("sms", "both") and notif.recipient_phone:
        sent = send_sms(notif.recipient_phone, notif.body)
    if notif.channel in ("email", "both") and notif.recipient_email:
        sent = send_email(notif.recipient_email, notif.subject, notif.body)

    notif.status = "sent" if sent else "failed"
    notif.sent_at = datetime.now(timezone.utc) if sent else None
    db.session.commit()

    return jsonify({"success": True, "data": notif.to_dict()}), 201


@notifications_bp.post("/broadcast")
@jwt_required()
def broadcast():
    claims = get_jwt()
    if claims.get("role") not in ("admin",):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    body = request.get_json() or {}
    from app.tasks.reminder_tasks import broadcast_announcement
    broadcast_announcement.delay(
        subject=body.get("subject", "Announcement"),
        body=body.get("body", ""),
        recipient_ids=body.get("recipient_ids", []),
    )
    return jsonify({"success": True, "message": "Broadcast queued."}), 202


@notifications_bp.get("/")
@jwt_required()
def list_notifications():
    user_id = get_jwt_identity()
    claims = get_jwt()
    q = Notification.query
    if claims.get("role") not in ("admin",):
        q = q.filter_by(recipient_id=user_id)
    notifications = q.order_by(Notification.created_at.desc()).limit(50).all()
    return jsonify({"success": True, "data": [n.to_dict() for n in notifications]}), 200


@notifications_bp.get("/templates")
@jwt_required()
def list_templates():
    templates = NotificationTemplate.query.all()
    return jsonify({"success": True, "data": [t.to_dict() for t in templates]}), 200


@notifications_bp.post("/templates")
@jwt_required()
def create_template():
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Forbidden."}), 403
    body = request.get_json() or {}
    template = NotificationTemplate(
        name=body["name"],
        subject=body.get("subject", ""),
        body=body["body"],
        channel=body.get("channel", "email"),
    )
    db.session.add(template)
    db.session.commit()
    return jsonify({"success": True, "data": template.to_dict()}), 201

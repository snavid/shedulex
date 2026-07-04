from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app.extensions import db
from app.models.notification import Notification, NotificationTemplate
from app.models.event_reminder import EventReminder
from app.middleware.internal_auth import require_internal_key
from app.services.dispatch_service import deliver_message, dispatch_notification
from app.services.timetable_events import append_event
from app.services.task_queue import enqueue_task, enqueue_task_async
from app.services.reminder_service import create_reminders, list_reminders, cancel_reminder

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/v1/notifications")


def _parse_send_payload(body: dict) -> tuple[dict, str | None]:
    """Normalize send payload and return (fields, validation_error)."""
    email = body.get("email") or body.get("recipient_email")
    phone = body.get("phone") or body.get("recipient_phone")
    channel = body.get("channel", "email")
    notif_type = body.get("type") or body.get("notification_type", "general")

    if channel in ("email", "both") and not email:
        return {}, "Email address is required for email delivery."

    return {
        "recipient_id": body.get("recipient_id"),
        "recipient_email": email,
        "recipient_phone": phone,
        "channel": channel,
        "subject": body.get("subject", ""),
        "body": body.get("body", ""),
        "notification_type": notif_type,
    }, None


@notifications_bp.post("/send")
@jwt_required()
def send_notification():
    claims = get_jwt()
    if claims.get("role") not in ("admin", "timetable_officer"):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    body = request.get_json() or {}
    fields, error = _parse_send_payload(body)
    if error:
        return jsonify({"success": False, "message": error}), 422

    notif = Notification(
        **fields,
        scheduled_at=datetime.now(timezone.utc),
    )
    db.session.add(notif)
    db.session.commit()

    success, error_message = deliver_message(
        phone=notif.recipient_phone,
        email=notif.recipient_email,
        channel=notif.channel,
        subject=notif.subject or "",
        body=notif.body,
    )

    notif.status = "sent" if success else "failed"
    notif.sent_at = datetime.now(timezone.utc) if success else None
    notif.error_message = error_message
    db.session.commit()

    return jsonify({"success": True, "data": notif.to_dict()}), 201


@notifications_bp.post("/broadcast")
@jwt_required()
def broadcast():
    claims = get_jwt()
    if claims.get("role") not in ("admin", "timetable_officer"):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    body = request.get_json() or {}
    subject = body.get("subject", "Announcement")
    message = body.get("body", "")
    if not message:
        return jsonify({"success": False, "message": "Message body is required."}), 422

    audience = body.get("audience", "all")
    channel = body.get("channel", "sms")
    university_id = body.get("university_id") or claims.get("university_id")
    if not university_id:
        current_app.logger.warning(
            "Broadcast attempted without university_id by user %s",
            get_jwt_identity(),
        )
        return jsonify({
            "success": False,
            "message": "University scope is required for broadcasts.",
        }), 422
    department_id = body.get("department_id")
    program_id = body.get("program_id")
    student_group_id = body.get("student_group_id")

    from app.tasks.reminder_tasks import broadcast_announcement
    enqueue_task(
        broadcast_announcement,
        subject=subject,
        body=message,
        audience=audience,
        channel=channel,
        university_id=university_id,
        department_id=department_id,
        program_id=program_id,
        student_group_id=student_group_id,
        recipient_ids=body.get("recipient_ids") or [],
    )
    return jsonify({"success": True, "message": "Broadcast queued."}), 202


@notifications_bp.post("/class-announcement")
@jwt_required()
def class_announcement():
    claims = get_jwt()
    if claims.get("role") not in ("admin", "lecturer", "timetable_officer", "hod"):
        return jsonify({"success": False, "message": "Forbidden."}), 403

    body = request.get_json() or {}
    entry_id = body.get("entry_id")
    message = (body.get("message") or "").strip()
    channel = body.get("channel", "sms")
    if not entry_id:
        return jsonify({"success": False, "message": "entry_id is required."}), 422
    if not message:
        return jsonify({"success": False, "message": "Message body is required."}), 422

    from app.services.timetable_client import get_timetable_entry
    from app.tasks.reminder_tasks import broadcast_announcement

    entry = get_timetable_entry(entry_id)
    if not entry:
        return jsonify({"success": False, "message": "Timetable entry not found."}), 404

    student_group = entry.get("student_group") or {}
    student_group_id = student_group.get("id") or entry.get("student_group_id")
    if not student_group_id:
        return jsonify({"success": False, "message": "This session has no student group assigned."}), 422

    course = entry.get("course") or {}
    subject = body.get("subject") or course.get("name") or "Class Announcement"
    university_id = claims.get("university_id")
    dept = course.get("department") or {}
    if not university_id:
        university_id = dept.get("university_id")

    enqueue_task(
        broadcast_announcement,
        subject=subject,
        body=message,
        audience="students",
        channel=channel,
        university_id=university_id,
        student_group_id=student_group_id,
    )
    group_name = student_group.get("name") or "class"
    return jsonify({
        "success": True,
        "message": f"Announcement queued for {group_name} students.",
    }), 202


@notifications_bp.get("/")
@jwt_required()
def list_notifications():
    user_id = get_jwt_identity()
    claims = get_jwt()
    q = Notification.query
    if claims.get("role") not in ("admin", "timetable_officer"):
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


@notifications_bp.post("/internal/timetable-event")
def ingest_timetable_event():
    denied = require_internal_key()
    if denied:
        return denied

    if not current_app.config.get("TIMETABLE_NOTIFY_ENABLED", True):
        return jsonify({"success": True, "message": "Timetable notifications disabled."}), 202

    body = request.get_json() or {}
    timetable_id = body.get("timetable_id")
    if not timetable_id:
        return jsonify({"success": False, "message": "timetable_id is required."}), 422

    from app.tasks.reminder_tasks import process_timetable_digest

    event_type = body.get("event_type", "update")
    if event_type == "generated":
        append_event(timetable_id, body)
        enqueue_task(process_timetable_digest, timetable_id)
        return jsonify({"success": True, "message": "Generation notifications queued."}), 202

    started = append_event(timetable_id, body)
    if started:
        debounce_seconds = current_app.config.get("TIMETABLE_EVENT_DEBOUNCE_SECONDS", 300)
        enqueue_task_async(
            process_timetable_digest,
            args=[timetable_id],
            countdown=debounce_seconds,
        )

    return jsonify({"success": True, "message": "Timetable event buffered."}), 202


@notifications_bp.post("/internal/calendar-event")
def ingest_calendar_event():
    denied = require_internal_key()
    if denied:
        return denied

    body = request.get_json() or {}
    from app.tasks.reminder_tasks import dispatch_calendar_event
    enqueue_task(dispatch_calendar_event, body)
    return jsonify({"success": True, "message": "Calendar event notification queued."}), 202


def _check_portal_reminder_access(claims: dict, body: dict | None = None):
    """Portal students may manage session reminders only."""
    if not claims.get("portal"):
        return None
    if claims.get("role") != "student":
        return jsonify({"success": False, "message": "Portal access denied."}), 403
    if body is not None and body.get("event_source") != "session":
        return jsonify({"success": False, "message": "Portal students can only set class session reminders."}), 403
    return None


@notifications_bp.post("/reminders")
@jwt_required()
def create_event_reminders():
    claims = get_jwt()
    body = request.get_json() or {}
    denied = _check_portal_reminder_access(claims, body)
    if denied:
        return denied

    user_id = get_jwt_identity()
    reminders, error = create_reminders(user_id, body)
    if error:
        return jsonify({"success": False, "message": error}), 422

    return jsonify({
        "success": True,
        "data": [r.to_dict() for r in reminders],
        "message": f"{len(reminders)} reminder(s) scheduled.",
    }), 201


@notifications_bp.get("/reminders")
@jwt_required()
def get_event_reminders():
    claims = get_jwt()
    denied = _check_portal_reminder_access(claims)
    if denied:
        return denied

    user_id = get_jwt_identity()
    event_key = request.args.get("event_key")
    status = request.args.get("status")
    reminders = list_reminders(user_id, event_key=event_key, status=status)
    return jsonify({"success": True, "data": [r.to_dict() for r in reminders]}), 200


@notifications_bp.delete("/reminders/<reminder_id>")
@jwt_required()
def delete_event_reminder(reminder_id):
    claims = get_jwt()
    denied = _check_portal_reminder_access(claims)
    if denied:
        return denied

    user_id = get_jwt_identity()
    reminder, error = cancel_reminder(user_id, reminder_id)
    if error:
        status = 404 if "not found" in error.lower() else 422
        return jsonify({"success": False, "message": error}), status

    return jsonify({"success": True, "data": reminder.to_dict(), "message": "Reminder cancelled."}), 200

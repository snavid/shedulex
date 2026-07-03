import time
from datetime import datetime, timezone

from flask import current_app

from app.extensions import db
from app.models.notification import Notification
from app.services.email_service import send_email
from app.services.sms_service import normalize_phone, send_sms


def _default_sms_phone() -> str:
    return current_app.config.get("DEFAULT_SMS_PHONE", "+255749300606")


def _effective_sms_phone(phone: str | None) -> tuple[str, bool]:
    """Return (normalized_dest, used_default)."""
    cleaned = normalize_phone(phone)
    if cleaned:
        return cleaned, False
    return normalize_phone(_default_sms_phone()), True


def _build_sms_text(subject: str, body: str) -> str:
    subject = (subject or "").strip()
    if subject:
        return f"{subject}: {body}"
    return body


def deliver_message(
    *,
    phone: str | None,
    email: str | None,
    channel: str,
    subject: str,
    body: str,
) -> tuple[bool, str | None]:
    """Send via requested channel(s). Returns (success, error_message)."""
    channel = channel or "email"
    errors: list[str] = []
    sms_ok = False
    email_ok = False

    if channel in ("sms", "both"):
        sms_dest, used_default = _effective_sms_phone(phone)
        if used_default:
            current_app.logger.info(
                "No phone for recipient; using default SMS number %s",
                _default_sms_phone(),
            )
        sms_text = _build_sms_text(subject, body)
        sms_ok, sms_error = send_sms(sms_dest, sms_text)
        if not sms_ok:
            errors.append(sms_error or "SMS delivery failed")

    if channel in ("email", "both"):
        if not email:
            errors.append("Email selected but no email address provided")
        else:
            email_ok = send_email(email, subject or "Notification", body)
            if not email_ok:
                errors.append("Email delivery failed")

    if channel == "sms":
        return sms_ok, errors[0] if errors else None
    if channel == "email":
        return email_ok, errors[0] if errors else None

    success = sms_ok or email_ok
    if success and errors:
        return True, "; ".join(errors)
    if not success:
        return False, "; ".join(errors) if errors else "Delivery failed"
    return True, None


def dispatch_notification(
    *,
    recipient_id: str | None,
    phone: str | None,
    email: str | None,
    subject: str,
    body: str,
    notification_type: str = "update",
    metadata: dict | None = None,
    channel: str = "sms",
) -> bool:
    if not body:
        return False

    meta = dict(metadata or {})
    if channel in ("sms", "both"):
        _, used_default = _effective_sms_phone(phone)
        if used_default:
            meta["sms_dest"] = _default_sms_phone()

    notif = Notification(
        recipient_id=recipient_id,
        recipient_phone=phone,
        recipient_email=email,
        channel=channel,
        subject=subject,
        body=body,
        notification_type=notification_type,
        scheduled_at=datetime.now(timezone.utc),
        metadata_=meta,
    )
    db.session.add(notif)
    db.session.flush()

    success, error_message = deliver_message(
        phone=phone,
        email=email,
        channel=channel,
        subject=subject,
        body=body,
    )

    notif.status = "sent" if success else "failed"
    notif.sent_at = datetime.now(timezone.utc) if success else None
    notif.error_message = error_message
    db.session.commit()
    time.sleep(0.05)
    return success

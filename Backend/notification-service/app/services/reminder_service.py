"""User-facing event reminder scheduling."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.extensions import db
from app.models.event_reminder import EventReminder
from app.models.notification import Notification
from app.services.recipient_resolver import fetch_user_by_id

ALLOWED_LEAD_MINUTES = {0, 15, 60, 1440}

LEAD_LABELS = {
    1440: "1 day",
    60: "1 hour",
    15: "15 minutes",
    0: "now",
}


def resolve_user_contact(user_id: str) -> dict:
    """Fetch fresh phone/email from auth-service."""
    user = fetch_user_by_id(user_id) or {}
    return {
        "email": (user.get("email") or "").strip() or None,
        "phone": (user.get("phone") or "").strip() or None,
        "display_name": (
            f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            or user.get("email")
        ),
    }


def validate_channel(channel: str, phone: str | None, email: str | None) -> str | None:
    if channel in ("sms", "both") and not phone:
        return "Add a phone number in your profile to receive SMS reminders."
    if channel in ("email", "both") and not email:
        return "Add an email address in your profile to receive email reminders."
    return None


def parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def compute_scheduled_at(event_start: datetime, lead_minutes: int) -> datetime:
    return event_start - timedelta(minutes=lead_minutes)


def build_reminder_body(
    *,
    event_title: str,
    event_start: datetime,
    lead_minutes: int,
    metadata: dict | None = None,
) -> tuple[str, str]:
    meta = metadata or {}
    course = meta.get("course_name") or meta.get("course_code") or ""
    room = meta.get("room") or ""
    location = f", {room}" if room else ""

    when_label = LEAD_LABELS.get(lead_minutes, f"{lead_minutes} min")
    if lead_minutes == 0:
        timing = "starting now"
    elif lead_minutes >= 1440:
        timing = f"in {when_label}"
    else:
        timing = f"in {when_label}"

    start_local = event_start.strftime("%a %d %b %H:%M")

    title_part = course or event_title
    body = f"Reminder: {title_part} {timing} — {start_local}{location}."
    subject = f"Reminder: {event_title}"
    return subject, body


def _enqueue_reminder(notification_id: str, scheduled_at: datetime) -> None:
    from app.tasks.reminder_tasks import send_lecture_reminder

    now = datetime.now(timezone.utc)
    if scheduled_at <= now:
        send_lecture_reminder.delay(notification_id)
    else:
        send_lecture_reminder.apply_async(args=[notification_id], eta=scheduled_at)


def _parse_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def generate_weekly_occurrences(first_start: datetime, repeat_until: str | date | datetime) -> list[datetime]:
    """Weekly occurrences from first_start through repeat_until (inclusive)."""
    until = _parse_date(repeat_until)
    occurrences: list[datetime] = []
    current = first_start
    while current.date() <= until:
        occurrences.append(current)
        current = current + timedelta(weeks=1)
    return occurrences


def _create_reminders_for_occurrence(
    *,
    user_id: str,
    event_key: str,
    event_source: str,
    event_title: str,
    event_start: datetime,
    event_end: datetime | None,
    channel: str,
    lead_times: list[int],
    metadata: dict,
    phone: str | None,
    email: str | None,
    now: datetime,
    created: list[EventReminder],
    skipped_past: list[int],
) -> None:
    for lead in sorted(set(lead_times)):
        scheduled_at = compute_scheduled_at(event_start, lead)
        if scheduled_at <= now:
            skipped_past.append(lead)
            continue

        existing = EventReminder.query.filter_by(
            user_id=user_id,
            event_key=event_key,
            lead_minutes=lead,
            status="pending",
        ).first()
        if existing:
            continue

        subject, body = build_reminder_body(
            event_title=event_title,
            event_start=event_start,
            lead_minutes=lead,
            metadata=metadata,
        )

        notif = Notification(
            recipient_id=user_id,
            recipient_email=email,
            recipient_phone=phone,
            channel=channel,
            subject=subject,
            body=body,
            notification_type="reminder",
            status="pending",
            scheduled_at=scheduled_at,
            metadata_={
                "event_key": event_key,
                "event_source": event_source,
                "lead_minutes": lead,
                **metadata,
            },
        )
        db.session.add(notif)
        db.session.flush()

        reminder = EventReminder(
            user_id=user_id,
            event_key=event_key,
            event_source=event_source,
            event_title=event_title,
            event_start=event_start,
            event_end=event_end,
            lead_minutes=lead,
            channel=channel,
            scheduled_at=scheduled_at,
            status="pending",
            notification_id=notif.id,
            metadata_=metadata,
        )
        db.session.add(reminder)
        db.session.flush()
        created.append(reminder)

        _enqueue_reminder(notif.id, scheduled_at)


def create_reminders(user_id: str, payload: dict) -> tuple[list[EventReminder], str | None]:
    """
    Create one EventReminder + pending Notification per lead time.
    Returns (reminders, error_message).
    """
    event_key = (payload.get("event_key") or "").strip()
    event_source = (payload.get("event_source") or "").strip()
    event_title = (payload.get("event_title") or "").strip()
    channel = payload.get("channel", "sms")
    lead_times = payload.get("lead_times") or []
    metadata = payload.get("metadata") or {}

    if not event_key or not event_source or not event_title:
        return [], "event_key, event_source, and event_title are required."
    if not lead_times:
        return [], "Select at least one reminder time."
    if event_source not in ("session", "calendar"):
        return [], "event_source must be 'session' or 'calendar'."

    invalid_leads = [lt for lt in lead_times if lt not in ALLOWED_LEAD_MINUTES]
    if invalid_leads:
        return [], f"Invalid lead_times: {invalid_leads}. Allowed: {sorted(ALLOWED_LEAD_MINUTES)}."

    try:
        event_start = parse_datetime(payload["event_start"])
    except (KeyError, ValueError):
        return [], "event_start is required and must be a valid ISO datetime."

    event_end = None
    if payload.get("event_end"):
        try:
            event_end = parse_datetime(payload["event_end"])
        except ValueError:
            return [], "event_end must be a valid ISO datetime."

    contact = resolve_user_contact(user_id)
    phone = contact["phone"]
    email = contact["email"]

    channel_error = validate_channel(channel, phone, email)
    if channel_error:
        return [], channel_error

    repeat_until_raw = payload.get("repeat_weekly_until")
    entry_id = (payload.get("entry_id") or metadata.get("entry_id") or "").strip()
    if repeat_until_raw:
        if event_source != "session":
            return [], "Weekly recurrence is only supported for class sessions."
        if not entry_id:
            return [], "entry_id is required for weekly recurrence."

    now = datetime.now(timezone.utc)
    created: list[EventReminder] = []
    skipped_past: list[int] = []

    if repeat_until_raw:
        try:
            repeat_until = _parse_date(repeat_until_raw)
        except ValueError:
            return [], "repeat_weekly_until must be a valid ISO date."

        occurrences = generate_weekly_occurrences(event_start, repeat_until)
        if not occurrences:
            return [], "No class occurrences fall within the selected semester range."

        for occ_start in occurrences:
            occ_date = occ_start.date().isoformat()
            occ_key = f"session:{entry_id}:{occ_date}"
            occ_meta = {**metadata, "entry_id": entry_id, "occurrence_date": occ_date}
            _create_reminders_for_occurrence(
                user_id=user_id,
                event_key=occ_key,
                event_source=event_source,
                event_title=event_title,
                event_start=occ_start,
                event_end=event_end,
                channel=channel,
                lead_times=lead_times,
                metadata=occ_meta,
                phone=phone,
                email=email,
                now=now,
                created=created,
                skipped_past=skipped_past,
            )
    else:
        _create_reminders_for_occurrence(
            user_id=user_id,
            event_key=event_key,
            event_source=event_source,
            event_title=event_title,
            event_start=event_start,
            event_end=event_end,
            channel=channel,
            lead_times=lead_times,
            metadata=metadata,
            phone=phone,
            email=email,
            now=now,
            created=created,
            skipped_past=skipped_past,
        )

    if not created:
        if skipped_past and len(skipped_past) >= len(set(lead_times)):
            return [], "All selected reminder times are in the past for this event."
        return [], "Reminders already exist for all selected times."

    db.session.commit()
    return created, None


def list_reminders(
    user_id: str,
    *,
    event_key: str | None = None,
    status: str | None = None,
) -> list[EventReminder]:
    q = EventReminder.query.filter_by(user_id=user_id)
    if event_key:
        q = q.filter_by(event_key=event_key)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(EventReminder.scheduled_at.asc()).all()


def cancel_reminder(user_id: str, reminder_id: str) -> tuple[EventReminder | None, str | None]:
    reminder = EventReminder.query.filter_by(id=reminder_id, user_id=user_id).first()
    if not reminder:
        return None, "Reminder not found."

    if reminder.status in ("sent", "failed"):
        return None, f"Cannot cancel a reminder that is already {reminder.status}."

    reminder.status = "cancelled"
    if reminder.notification_id:
        notif = Notification.query.get(reminder.notification_id)
        if notif and notif.status == "pending":
            notif.status = "cancelled"
    db.session.commit()
    return reminder, None

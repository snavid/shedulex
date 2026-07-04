"""
Celery tasks for automated notifications and reminders.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from app.celery_app import celery
from flask import current_app

LOCAL_TZ = ZoneInfo("Africa/Dar_es_Salaam")


def _dispatch_notification_record(notif) -> bool:
    from app.services.dispatch_service import deliver_message

    success, error_message = deliver_message(
        phone=notif.recipient_phone,
        email=notif.recipient_email,
        channel=notif.channel,
        subject=notif.subject or "Notification",
        body=notif.body,
    )
    notif.error_message = error_message
    return success


@celery.task(name="tasks.send_lecture_reminder", bind=True, max_retries=3)
def send_lecture_reminder(self, notification_id: str):
    from app.extensions import db
    from app.models.notification import Notification

    with current_app.app_context():
        notif = Notification.query.get(notification_id)
        if not notif or notif.status != "pending":
            return

        try:
            sent = _dispatch_notification_record(notif)
            notif.status = "sent" if sent else "failed"
            notif.sent_at = datetime.now(timezone.utc) if sent else None
            if not sent and not notif.error_message:
                notif.error_message = "Delivery failed"
            db.session.commit()
        except Exception as exc:
            notif.status = "failed"
            notif.error_message = str(exc)
            db.session.commit()
            raise self.retry(exc=exc, countdown=60)


@celery.task(name="tasks.schedule_daily_reminders")
def schedule_daily_reminders():
    from app.extensions import db
    from app.models.notification import Notification
    import httpx

    timetable_url = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")
    internal_key = os.environ.get("INTERNAL_SERVICE_KEY", "dev-internal-service-key")
    tomorrow_local = datetime.now(LOCAL_TZ) + timedelta(days=1)
    tomorrow = tomorrow_local.strftime("%A")

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{timetable_url}/api/v1/timetable/entries?day={tomorrow}",
                headers={"X-Internal-Service-Key": internal_key},
            )
            if resp.status_code != 200:
                return
            entries = resp.json().get("data", [])
    except Exception:
        return

    with current_app.app_context():
        for entry in entries:
            course_name = entry.get("course", {}).get("name", "your class")
            lecturer = entry.get("lecturer", {})
            slot = entry.get("time_slot", {})
            notif = Notification(
                recipient_email=lecturer.get("email"),
                recipient_phone=lecturer.get("phone"),
                channel="both" if lecturer.get("phone") else "email",
                subject=f"Reminder: {course_name} tomorrow",
                body=f"Reminder: You have {course_name} tomorrow ({slot.get('day')}) at {slot.get('start_time')}.",
                notification_type="reminder",
                scheduled_at=datetime.now(timezone.utc),
            )
            db.session.add(notif)
            db.session.flush()
            send_lecture_reminder.delay(notif.id)
        db.session.commit()


@celery.task(name="tasks.broadcast_announcement")
def broadcast_announcement(
    subject: str,
    body: str,
    audience: str = "all",
    channel: str = "sms",
    university_id: str | None = None,
    department_id: str | None = None,
    program_id: str | None = None,
    student_group_id: str | None = None,
    recipient_ids: list[str] | None = None,
):
    from app.services.recipient_resolver import fetch_user_by_id, resolve_broadcast_audience
    from app.services.dispatch_service import dispatch_notification

    with current_app.app_context():
        recipients: list[dict] = []
        if recipient_ids:
            for rid in recipient_ids:
                user = fetch_user_by_id(rid)
                if user:
                    recipients.append(user)
        else:
            recipients = resolve_broadcast_audience(
                audience=audience,
                university_id=university_id,
                department_id=department_id,
                program_id=program_id,
                student_group_id=student_group_id,
            )

        sent_count = 0
        for user in recipients:
            if dispatch_notification(
                recipient_id=user.get("id"),
                phone=user.get("phone"),
                email=user.get("email"),
                subject=subject,
                body=body,
                notification_type="announcement",
                channel=channel,
                metadata={"audience": audience},
            ):
                sent_count += 1

        current_app.logger.info(
            "Broadcast to audience=%s: %s/%s sent",
            audience,
            sent_count,
            len(recipients),
        )


@celery.task(name="tasks.dispatch_calendar_event")
def dispatch_calendar_event(event: dict):
    with current_app.app_context():
        _notify_calendar_event(event)


def _notify_calendar_event(event: dict) -> None:
    from app.services.recipient_resolver import resolve_calendar_event_recipients
    from app.services.dispatch_service import dispatch_notification
    from app.services.timetable_events import _redis_client

    event_id = event.get("id")
    if not event_id:
        return

    today_key = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    redis_client = _redis_client()
    dedupe_key = f"calendar_notified:{event_id}:{today_key}"
    if redis_client.get(dedupe_key):
        return

    title = event.get("title") or "Event"
    start = event.get("start") or ""
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        time_label = start_dt.astimezone(LOCAL_TZ).strftime("%H:%M")
    except Exception:
        time_label = ""
    location = event.get("location") or ""
    message = f"SheduleX: {title} today"
    if time_label:
        message += f" at {time_label}"
    if location:
        message += f" ({location})"

    recipients = resolve_calendar_event_recipients(event)
    sent_any = False
    for user in recipients:
        if dispatch_notification(
            recipient_id=user.get("id"),
            phone=user.get("phone"),
            email=user.get("email"),
            subject=f"Today: {title}",
            body=message,
            notification_type="reminder",
            channel="both" if user.get("phone") else "email",
            metadata={"calendar_event_id": event_id, "event_type": event.get("event_type")},
        ):
            sent_any = True

    if sent_any:
        redis_client.setex(dedupe_key, 86400, "1")


@celery.task(name="tasks.schedule_calendar_event_reminders")
def schedule_calendar_event_reminders():
    from app.services.calendar_client import fetch_today_events

    with current_app.app_context():
        for event in fetch_today_events():
            _notify_calendar_event(event)


@celery.task(name="tasks.process_timetable_digest")
def process_timetable_digest(timetable_id: str):
    from app.services.timetable_events import pop_events
    from app.services.timetable_client import get_timetable
    from app.services.recipient_resolver import resolve_all_recipients
    from app.services.message_builder import (
        build_student_message,
        build_lecturer_message,
        build_hod_message,
        build_timetable_officer_message,
    )
    from app.services.dispatch_service import dispatch_notification

    with current_app.app_context():
        if not current_app.config.get("TIMETABLE_NOTIFY_ENABLED", True):
            return

        events = pop_events(timetable_id)
        if not events:
            return

        timetable = get_timetable(timetable_id)
        if not timetable:
            current_app.logger.error("Timetable %s not found for digest.", timetable_id)
            return

        entries = timetable.get("entries") or []
        department = timetable.get("department") or {}
        department_id = timetable.get("department_id") or department.get("id")
        department_name = department.get("name") or "Department"
        university_id = department.get("university_id")
        semester = timetable.get("semester") or 1

        is_generation = any(e.get("event_type") == "generated" for e in events)
        changes: list[dict] = []
        triggered_by = "system"
        for event in events:
            changes.extend(event.get("changes") or [])
            if event.get("triggered_by") and event.get("triggered_by") != "system":
                triggered_by = event.get("triggered_by")

        affected_program_ids = {
            c.get("program_id") for c in changes if c.get("program_id")
        }
        affected_group_ids = {
            c.get("student_group_id") for c in changes if c.get("student_group_id")
        }
        affected_lecturer_ids = set()
        for change in changes:
            if change.get("lecturer_id"):
                affected_lecturer_ids.add(change["lecturer_id"])
            if change.get("old_lecturer_id"):
                affected_lecturer_ids.add(change["old_lecturer_id"])
            if change.get("new_lecturer_id"):
                affected_lecturer_ids.add(change["new_lecturer_id"])

        if is_generation:
            affected_lecturer_ids = {
                (e.get("lecturer") or {}).get("id")
                for e in entries
                if (e.get("lecturer") or {}).get("id")
            }

        recipients = resolve_all_recipients(
            department_id=department_id,
            university_id=university_id,
            affected_program_ids=affected_program_ids,
            affected_group_ids=affected_group_ids,
            affected_lecturer_ids=affected_lecturer_ids,
            entries=entries,
            changes=changes,
            is_generation=is_generation,
        )

        for recipient in recipients:
            role = recipient.get("role")
            subject = ""
            body = ""

            if role == "student":
                subject, body = build_student_message(
                    timetable_id=timetable_id,
                    semester=semester,
                    entries=entries,
                    changes=changes,
                    program_id=recipient.get("program_id"),
                    student_group_id=recipient.get("student_group_id"),
                    is_generation=is_generation,
                )
            elif role == "lecturer":
                lecturer_id = recipient.get("lecturer_id")
                if not lecturer_id:
                    continue
                subject, body = build_lecturer_message(
                    timetable_id=timetable_id,
                    lecturer_id=lecturer_id,
                    entries=entries,
                    changes=changes,
                    is_generation=is_generation,
                )
            elif role == "hod":
                subject, body = build_hod_message(
                    timetable_id=timetable_id,
                    department_name=department_name,
                    changes=changes,
                    entry_count=len(entries),
                    is_generation=is_generation,
                )
            elif role == "timetable_officer":
                subject, body = build_timetable_officer_message(
                    timetable_id=timetable_id,
                    timetable_name=timetable.get("name") or "",
                    department_name=department_name,
                    changes=changes,
                    triggered_by=triggered_by,
                    entry_count=len(entries),
                    is_generation=is_generation,
                )

            if not body:
                continue

            dispatch_notification(
                recipient_id=recipient.get("id"),
                phone=recipient.get("phone"),
                email=recipient.get("email"),
                subject=subject,
                body=body,
                notification_type="update" if not is_generation else "announcement",
                metadata={
                    "timetable_id": timetable_id,
                    "role": role,
                    "event_count": len(events),
                    "change_count": len(changes),
                },
                channel="both" if recipient.get("phone") else "email",
            )

"""
Celery tasks for automated notifications and reminders.

Schedules (configured in celery beat):
  - every_day_19h:   send next-day lecture reminders
  - every_hour:      send 3-hours-before reminders
  - every_morning:   broadcast daily announcements
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from celery import shared_task
from flask import current_app


@shared_task(name="tasks.send_lecture_reminder", bind=True, max_retries=3)
def send_lecture_reminder(self, notification_id: str):
    """Send a single lecture reminder notification."""
    from app.extensions import db
    from app.models.notification import Notification
    from app.services.sms_service import send_sms
    from app.services.email_service import send_email

    with current_app.app_context():
        notif = Notification.query.get(notification_id)
        if not notif or notif.status != "pending":
            return

        try:
            sent = False
            if notif.channel in ("sms", "both") and notif.recipient_phone:
                sent = send_sms(notif.recipient_phone, notif.body)
            if notif.channel in ("email", "both") and notif.recipient_email:
                sent = send_email(notif.recipient_email, notif.subject or "Lecture Reminder", notif.body)

            notif.status = "sent" if sent else "failed"
            notif.sent_at = datetime.now(timezone.utc)
            db.session.commit()
        except Exception as exc:
            notif.status = "failed"
            notif.error_message = str(exc)
            db.session.commit()
            raise self.retry(exc=exc, countdown=60)


@shared_task(name="tasks.schedule_daily_reminders")
def schedule_daily_reminders():
    """
    Runs at 19:00 daily.
    Queries timetable service for tomorrow's classes and queues reminders.
    """
    from app.extensions import db
    from app.models.notification import Notification
    import httpx, os

    timetable_url = os.environ.get("TIMETABLE_SERVICE_URL", "http://timetable-engine:5002")
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%A")

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{timetable_url}/api/v1/timetable/entries?day={tomorrow}")
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
                channel="email",
                subject=f"Reminder: {course_name} tomorrow",
                body=f"Reminder: You have {course_name} tomorrow ({slot.get('day')}) at {slot.get('start_time')}.",
                notification_type="reminder",
                scheduled_at=datetime.now(timezone.utc),
            )
            db.session.add(notif)
        db.session.commit()


@shared_task(name="tasks.broadcast_announcement")
def broadcast_announcement(subject: str, body: str, recipient_ids: list[str]):
    """Broadcast an announcement to a list of users."""
    from app.extensions import db
    from app.models.notification import Notification

    with current_app.app_context():
        for rid in recipient_ids:
            notif = Notification(
                recipient_id=rid,
                channel="email",
                subject=subject,
                body=body,
                notification_type="announcement",
                scheduled_at=datetime.now(timezone.utc),
            )
            db.session.add(notif)
        db.session.commit()

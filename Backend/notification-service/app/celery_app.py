import os

from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.environ.get(
    "CELERY_BROKER_URL",
    os.environ.get("REDIS_URL", "redis://localhost:6490/0"),
)

celery = Celery(
    "notification-service",
    broker=REDIS_URL,
    backend=os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL),
    include=["app.tasks.reminder_tasks"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Dar_es_Salaam",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "daily-reminders": {
            "task": "tasks.schedule_daily_reminders",
            "schedule": crontab(hour=19, minute=0),
        },
        "calendar-event-reminders": {
            "task": "tasks.schedule_calendar_event_reminders",
            "schedule": crontab(hour=7, minute=0),
        },
        "process-due-reminders": {
            "task": "tasks.process_due_reminders",
            "schedule": crontab(minute="*/5"),
        },
    },
)

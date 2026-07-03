"""Seed default notification templates for timetable broadcasts."""
from app.extensions import db
from app.models.notification import NotificationTemplate

DEFAULT_TEMPLATES = [
    {
        "name": "timetable_generated_student",
        "subject": "Timetable Ready",
        "body": "SheduleX: Your Sem {semester} timetable is ready. {summary}. View: {link}",
        "channel": "sms",
    },
    {
        "name": "timetable_change_student",
        "subject": "Timetable Update",
        "body": "SheduleX Update: {changes}. View: {link}",
        "channel": "sms",
    },
    {
        "name": "timetable_generated_lecturer",
        "subject": "Your Teaching Schedule",
        "body": "SheduleX: Your teaching schedule is ready. {summary}. View: {link}",
        "channel": "sms",
    },
    {
        "name": "timetable_change_lecturer",
        "subject": "Schedule Updated",
        "body": "SheduleX: Your schedule updated. {changes}. View: {link}",
        "channel": "sms",
    },
    {
        "name": "timetable_generated_hod",
        "subject": "Department Timetable Published",
        "body": "SheduleX: {department} timetable published with {entry_count} sessions. View: {link}",
        "channel": "sms",
    },
    {
        "name": "timetable_change_hod",
        "subject": "Department Timetable Updated",
        "body": "SheduleX: {department} timetable updated ({change_count} changes): {changes}. View: {link}",
        "channel": "sms",
    },
]


def seed_notification_templates():
    for item in DEFAULT_TEMPLATES:
        if NotificationTemplate.query.filter_by(name=item["name"]).first():
            continue
        db.session.add(NotificationTemplate(**item))
    db.session.commit()

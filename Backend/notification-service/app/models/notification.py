import uuid
from datetime import datetime, timezone
from app.extensions import db


class NotificationTemplate(db.Model):
    __tablename__ = "notification_templates"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False, unique=True)
    subject = db.Column(db.String(255))
    body = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(20), default="email")  # email, sms, both
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {"id": self.id, "name": self.name, "subject": self.subject,
                "body": self.body, "channel": self.channel}


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_id = db.Column(db.String(36))
    recipient_email = db.Column(db.String(255))
    recipient_phone = db.Column(db.String(20))
    channel = db.Column(db.String(20), default="email")  # email, sms, both
    subject = db.Column(db.String(255))
    body = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50))  # reminder, alert, announcement, update
    status = db.Column(db.String(30), default="pending")  # pending, sent, failed, cancelled
    scheduled_at = db.Column(db.DateTime(timezone=True))
    sent_at = db.Column(db.DateTime(timezone=True))
    error_message = db.Column(db.Text)
    metadata_ = db.Column("metadata", db.JSON, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id, "recipient_id": self.recipient_id,
            "recipient_email": self.recipient_email, "channel": self.channel,
            "subject": self.subject, "body": self.body,
            "notification_type": self.notification_type, "status": self.status,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat(),
        }

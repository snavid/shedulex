import uuid
from datetime import datetime, timezone

from app.extensions import db


class EventReminder(db.Model):
    __tablename__ = "event_reminders"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "event_key", "lead_minutes",
            name="uq_event_reminder_user_event_lead",
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), nullable=False, index=True)
    event_key = db.Column(db.String(255), nullable=False, index=True)
    event_source = db.Column(db.String(50), nullable=False)  # session, calendar
    event_title = db.Column(db.String(255), nullable=False)
    event_start = db.Column(db.DateTime(timezone=True), nullable=False)
    event_end = db.Column(db.DateTime(timezone=True))
    lead_minutes = db.Column(db.Integer, nullable=False)
    channel = db.Column(db.String(20), default="sms")
    scheduled_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    status = db.Column(db.String(30), default="pending")  # pending, sent, failed, cancelled
    notification_id = db.Column(db.String(36), db.ForeignKey("notifications.id"))
    metadata_ = db.Column("metadata", db.JSON, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    notification = db.relationship("Notification", backref="event_reminder", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event_key": self.event_key,
            "event_source": self.event_source,
            "event_title": self.event_title,
            "event_start": self.event_start.isoformat() if self.event_start else None,
            "event_end": self.event_end.isoformat() if self.event_end else None,
            "lead_minutes": self.lead_minutes,
            "channel": self.channel,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "status": self.status,
            "notification_id": self.notification_id,
            "metadata": self.metadata_ or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

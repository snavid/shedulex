import uuid
from datetime import datetime, timezone
from app.extensions import db


class AdjustmentRequest(db.Model):
    __tablename__ = "adjustment_requests"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timetable_id = db.Column(db.String(36), nullable=False)
    requested_by = db.Column(db.String(36))
    prompt = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text)
    status = db.Column(db.String(30), default="pending")  # pending, processing, completed, failed
    conflict_reason = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime(timezone=True))

    def to_dict(self):
        return {
            "id": self.id,
            "timetable_id": self.timetable_id,
            "prompt": self.prompt,
            "response": self.response,
            "status": self.status,
            "conflict_reason": self.conflict_reason,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ConflictLog(db.Model):
    __tablename__ = "conflict_logs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timetable_id = db.Column(db.String(36), nullable=False)
    conflict_type = db.Column(db.String(100))
    description = db.Column(db.Text)
    severity = db.Column(db.String(20), default="medium")  # low, medium, high, critical
    resolved = db.Column(db.Boolean, default=False)
    resolution = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id, "timetable_id": self.timetable_id,
            "conflict_type": self.conflict_type, "description": self.description,
            "severity": self.severity, "resolved": self.resolved,
            "resolution": self.resolution, "created_at": self.created_at.isoformat(),
        }

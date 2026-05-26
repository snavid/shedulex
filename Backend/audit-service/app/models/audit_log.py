import uuid
from datetime import datetime, timezone
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), index=True)
    university_id = db.Column(db.String(36), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(100))
    resource_id = db.Column(db.String(36))
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    service = db.Column(db.String(50))
    status = db.Column(db.String(20), default="success")  # success, failure, warning
    metadata_ = db.Column("metadata", db.JSON, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id, "user_id": self.user_id,
            "university_id": self.university_id,
            "action": self.action,
            "resource_type": self.resource_type, "resource_id": self.resource_id,
            "description": self.description, "ip_address": self.ip_address,
            "service": self.service, "status": self.status,
            "metadata": self.metadata_, "created_at": self.created_at.isoformat(),
        }

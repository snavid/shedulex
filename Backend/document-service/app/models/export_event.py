import uuid
from datetime import datetime, timezone

from app.extensions import db


class ExportEvent(db.Model):
    __tablename__ = "export_events"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timetable_id = db.Column(db.String(36), nullable=False, index=True)
    export_format = db.Column(db.String(20), nullable=False, index=True)  # pdf, excel, csv, bundle
    delivery_channel = db.Column(db.String(20), nullable=False, default="download")  # download, share
    requested_by = db.Column(db.String(36), nullable=True)
    cache_hit = db.Column(db.Boolean, nullable=False, default=False)
    duration_ms = db.Column(db.Integer, nullable=False, default=0)
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="success")  # success, failed
    error_message = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "timetable_id": self.timetable_id,
            "export_format": self.export_format,
            "delivery_channel": self.delivery_channel,
            "requested_by": self.requested_by,
            "cache_hit": self.cache_hit,
            "duration_ms": self.duration_ms,
            "size_bytes": self.size_bytes,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

import json
import uuid
from datetime import datetime, timezone
from app.extensions import db

TOOL_TRACE_MARKER = "\n___TOOL_TRACE___\n"

# Token budget thresholds
SESSION_COMPRESS_THRESHOLD = 40   # compress after 40 messages
SESSION_ARCHIVE_THRESHOLD  = 80   # force new chat after 80 (even compressed)
SUMMARY_MAX_CHARS          = 6000 # if summary > this the session is "full"


def split_response_and_trace(raw: str | None) -> tuple[str, list]:
    if not raw:
        return "", []
    if TOOL_TRACE_MARKER not in raw:
        return raw.strip(), []
    text_part, rest = raw.split(TOOL_TRACE_MARKER, 1)
    text_part = text_part.strip()
    try:
        trace = json.loads(rest.strip())
        if not isinstance(trace, list):
            return text_part, []
    except json.JSONDecodeError:
        return raw.strip(), []
    return text_part, trace


class ConversationSession(db.Model):
    """Persistent chat session with memory compression and interrupt support."""
    __tablename__ = "conversation_sessions"

    id              = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timetable_id    = db.Column(db.String(36), nullable=False, index=True)
    user_id         = db.Column(db.String(36), index=True)
    user_name       = db.Column(db.String(200))

    # ── Message storage ──────────────────────────────────────────────────────
    # Full list of messages kept as JSON  [{role, content, ts, tool_trace?}]
    messages        = db.Column(db.JSON, default=list)
    # LLM-generated summary of older messages (compression artefact)
    compressed_summary = db.Column(db.Text, default="")
    total_messages  = db.Column(db.Integer, default=0)

    # ── Agent state ──────────────────────────────────────────────────────────
    # active | waiting_for_input | archived
    status          = db.Column(db.String(30), default="active")
    # JSON payload emitted by interrupt(): {question, options?}
    interrupt_data  = db.Column(db.JSON)

    # ── ChromaDB reference ───────────────────────────────────────────────────
    vector_id       = db.Column(db.String(200))

    created_at      = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_activity   = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def is_full(self):
        """True when the session can no longer accept new messages."""
        return (
            self.status == "archived"
            or self.total_messages >= SESSION_ARCHIVE_THRESHOLD
            or len(self.compressed_summary or "") >= SUMMARY_MAX_CHARS
        )

    @property
    def needs_compression(self):
        return (
            self.status == "active"
            and self.total_messages >= SESSION_COMPRESS_THRESHOLD
            and not self.is_full
        )

    def to_dict(self):
        return {
            "id":                self.id,
            "timetable_id":      self.timetable_id,
            "user_id":           self.user_id,
            "user_name":         self.user_name,
            "messages":          self.messages or [],
            "compressed_summary":self.compressed_summary or "",
            "total_messages":    self.total_messages,
            "status":            self.status,
            "interrupt_data":    self.interrupt_data,
            "is_full":           self.is_full,
            "created_at":        self.created_at.isoformat(),
            "last_activity":     self.last_activity.isoformat(),
        }


class AdjustmentRequest(db.Model):
    """Legacy single-shot request record (kept for backwards compatibility)."""
    __tablename__ = "adjustment_requests"

    id              = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timetable_id    = db.Column(db.String(36), nullable=False)
    requested_by    = db.Column(db.String(36))
    prompt          = db.Column(db.Text, nullable=False)
    response        = db.Column(db.Text)
    status          = db.Column(db.String(30), default="pending")
    conflict_reason = db.Column(db.String(500))
    created_at      = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at    = db.Column(db.DateTime(timezone=True))

    def to_dict(self):
        text, trace = split_response_and_trace(self.response)
        return {
            "id":             self.id,
            "timetable_id":   self.timetable_id,
            "prompt":         self.prompt,
            "response":       text,
            "tool_trace":     trace,
            "status":         self.status,
            "conflict_reason":self.conflict_reason,
            "created_at":     self.created_at.isoformat(),
            "completed_at":   self.completed_at.isoformat() if self.completed_at else None,
        }


class ConflictLog(db.Model):
    __tablename__ = "conflict_logs"

    id            = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timetable_id  = db.Column(db.String(36), nullable=False)
    conflict_type = db.Column(db.String(100))
    description   = db.Column(db.Text)
    severity      = db.Column(db.String(20), default="medium")
    resolved      = db.Column(db.Boolean, default=False)
    resolution    = db.Column(db.Text)
    created_at    = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id, "timetable_id": self.timetable_id,
            "conflict_type": self.conflict_type, "description": self.description,
            "severity": self.severity, "resolved": self.resolved,
            "resolution": self.resolution, "created_at": self.created_at.isoformat(),
        }

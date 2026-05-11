import uuid
from datetime import datetime, timezone
from app.extensions import db


class AcademicEvent(db.Model):
    __tablename__ = "academic_events"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_type = db.Column(db.String(50), default="event")
    # Types: class, exam, holiday, deadline, makeup, meeting, announcement
    start_datetime = db.Column(db.DateTime(timezone=True), nullable=False)
    end_datetime = db.Column(db.DateTime(timezone=True))
    all_day = db.Column(db.Boolean, default=False)
    location = db.Column(db.String(200))
    department_id = db.Column(db.String(36))
    course_id = db.Column(db.String(36))
    lecturer_id = db.Column(db.String(36))
    created_by = db.Column(db.String(36))
    is_public = db.Column(db.Boolean, default=True)
    color = db.Column(db.String(20), default="#3B82F6")
    recurrence = db.Column(db.String(50))  # none, daily, weekly, monthly
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "description": self.description,
            "event_type": self.event_type,
            "start": self.start_datetime.isoformat(),
            "end": self.end_datetime.isoformat() if self.end_datetime else None,
            "all_day": self.all_day, "location": self.location,
            "department_id": self.department_id, "course_id": self.course_id,
            "lecturer_id": self.lecturer_id, "is_public": self.is_public,
            "color": self.color, "recurrence": self.recurrence,
        }


class AcademicSemester(db.Model):
    __tablename__ = "academic_semesters"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    semester_number = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    registration_start = db.Column(db.Date)
    registration_end = db.Column(db.Date)
    exam_start = db.Column(db.Date)
    exam_end = db.Column(db.Date)
    is_current = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "academic_year": self.academic_year,
            "semester_number": self.semester_number,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "is_current": self.is_current,
        }

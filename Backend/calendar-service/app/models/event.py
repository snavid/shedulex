import uuid
from datetime import datetime, timezone
from app.extensions import db


class AcademicEvent(db.Model):
    __tablename__ = "academic_events"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    # class | exam | holiday | deadline | makeup | meeting | announcement
    # closure_university | closure_department | closure_program | emergency
    event_type = db.Column(db.String(50), default="event")
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
    recurrence = db.Column(db.String(50))  # none | daily | weekly | monthly
    university_id = db.Column(db.String(36))
    student_group_id = db.Column(db.String(36))
    program_id = db.Column(db.String(36))
    is_cancelled = db.Column(db.Boolean, default=False)
    cancelled_by = db.Column(db.String(36))
    cancellation_reason = db.Column(db.String(300))
    # Whether this event suppresses timetable sessions for the covered date range
    affects_timetable = db.Column(db.Boolean, default=False)
    # Scope of timetable suppression: university | department | program | student_group
    timetable_scope = db.Column(db.String(50))
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
            "university_id": self.university_id,
            "student_group_id": self.student_group_id,
            "program_id": self.program_id,
            "is_cancelled": self.is_cancelled,
            "cancellation_reason": self.cancellation_reason,
            "affects_timetable": self.affects_timetable,
            "timetable_scope": self.timetable_scope,
        }


class AcademicSemester(db.Model):
    """
    University/tenant-scoped academic semester configuration.
    Drives timetable generation, event scheduling, and reminder systems.
    """
    __tablename__ = "academic_semesters"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    semester_number = db.Column(db.Integer, nullable=False)  # 1 or 2
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    # Optional mid-semester break
    break_start = db.Column(db.Date)
    break_end = db.Column(db.Date)
    # Registration window
    registration_start = db.Column(db.Date)
    registration_end = db.Column(db.Date)
    # Exam block
    exam_start = db.Column(db.Date)
    exam_end = db.Column(db.Date)
    # University scope
    university_id = db.Column(db.String(36))
    # IANA timezone e.g. "Africa/Nairobi"
    timezone = db.Column(db.String(60), default="UTC")
    is_current = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "academic_year": self.academic_year,
            "semester_number": self.semester_number,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "break_start": self.break_start.isoformat() if self.break_start else None,
            "break_end": self.break_end.isoformat() if self.break_end else None,
            "registration_start": self.registration_start.isoformat() if self.registration_start else None,
            "registration_end": self.registration_end.isoformat() if self.registration_end else None,
            "exam_start": self.exam_start.isoformat() if self.exam_start else None,
            "exam_end": self.exam_end.isoformat() if self.exam_end else None,
            "university_id": self.university_id,
            "timezone": self.timezone,
            "is_current": self.is_current,
        }


class AcademicHoliday(db.Model):
    """
    Public or institutional holidays.  The calendar engine and timetable
    generator will skip scheduling on these dates.
    """
    __tablename__ = "academic_holidays"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)   # null = single-day holiday
    # public | national | institutional | religious | departmental
    holiday_type = db.Column(db.String(50), default="public")
    university_id = db.Column(db.String(36))   # null = applies to all
    country_code = db.Column(db.String(5))     # ISO 3166-1 alpha-2, e.g. "KE"
    is_recurring = db.Column(db.Boolean, default=False)  # repeats every year
    created_by = db.Column(db.String(36))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id, "name": self.name,
            "date": self.date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "holiday_type": self.holiday_type,
            "university_id": self.university_id,
            "country_code": self.country_code,
            "is_recurring": self.is_recurring,
        }

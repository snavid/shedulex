"""
Core domain models for the timetable engine.
All scheduling entities share a common UUID primary key and timestamp pattern.
"""
import uuid
from datetime import datetime, timezone
from app.extensions import db


class TimetableTemplate(db.Model):
    """
    Reusable daily schedule template (e.g. "Standard 8-5", "Evening Programme").
    A template owns a set of TemplateTimeBlocks that define the labelled periods
    for an academic day.  The GA uses the non-break/non-lunch blocks as the pool
    of available slots when generating a timetable.
    """
    __tablename__ = "timetable_templates"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    university_id = db.Column(db.String(36))
    is_default = db.Column(db.Boolean, default=False)
    days_of_week = db.Column(db.JSON, default=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    blocks = db.relationship("TemplateTimeBlock", back_populates="template",
                             cascade="all, delete-orphan", order_by="TemplateTimeBlock.sort_order")

    def to_dict(self, include_blocks=False):
        d = {
            "id": self.id, "name": self.name, "description": self.description,
            "university_id": self.university_id, "is_default": self.is_default,
            "days_of_week": self.days_of_week,
            "block_count": len(self.blocks) if self.blocks else 0,
        }
        if include_blocks:
            d["blocks"] = [b.to_dict() for b in self.blocks]
        return d


class TemplateTimeBlock(db.Model):
    """
    A single named time period within a TimetableTemplate.
    block_type: 'class' | 'break' | 'lunch' | 'lab' | 'exam'
    Only 'class' and 'lab' blocks are eligible for course scheduling.
    """
    __tablename__ = "template_time_blocks"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = db.Column(db.String(36), db.ForeignKey("timetable_templates.id"), nullable=False)
    label = db.Column(db.String(100), nullable=False)    # e.g. "Period 1", "Lunch Break"
    start_time = db.Column(db.String(10), nullable=False)  # "08:00"
    end_time = db.Column(db.String(10), nullable=False)    # "09:00"
    block_type = db.Column(db.String(20), default="class")  # class, break, lunch, lab, exam
    sort_order = db.Column(db.Integer, default=0)

    template = db.relationship("TimetableTemplate", back_populates="blocks")

    def to_dict(self):
        return {
            "id": self.id, "template_id": self.template_id,
            "label": self.label, "start_time": self.start_time,
            "end_time": self.end_time, "block_type": self.block_type,
            "sort_order": self.sort_order,
        }


# Association table: many lecturers ↔ many programs
lecturer_programs = db.Table(
    "lecturer_programs",
    db.Column("lecturer_id", db.String(36), db.ForeignKey("lecturers.id"), primary_key=True),
    db.Column("program_id", db.String(36), db.ForeignKey("programs.id"), primary_key=True),
)

# Association table: many courses ↔ many student_groups
course_student_groups = db.Table(
    "course_student_groups",
    db.Column("course_id", db.String(36), db.ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
    db.Column("student_group_id", db.String(36), db.ForeignKey("student_groups.id", ondelete="CASCADE"), primary_key=True),
)


class University(db.Model):
    __tablename__ = "universities"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    address = db.Column(db.String(300))
    website = db.Column(db.String(255))
    logo_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    departments = db.relationship("Department", back_populates="university", cascade="all, delete-orphan")
    academic_years = db.relationship("AcademicYear", back_populates="university",
                                     cascade="all, delete-orphan",
                                     order_by="AcademicYear.name.desc()")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "address": self.address,
            "website": self.website,
            "logo_url": self.logo_url,
            "is_active": self.is_active,
        }


class AcademicYear(db.Model):
    """
    Workspace / academic-year container — e.g. "2025-2026".
    Timetables are scoped to a year; structural data (rooms, lecturers, time slots,
    departments) is shared across years so nothing needs to be re-entered.
    Semester date ranges here drive the calendar integration.
    """
    __tablename__ = "academic_years"

    id          = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = db.Column(db.String(20), nullable=False)          # "2025-2026"
    university_id = db.Column(db.String(36), db.ForeignKey("universities.id"), nullable=False)
    # Semester 1 date window
    sem1_start  = db.Column(db.Date)
    sem1_end    = db.Column(db.Date)
    # Semester 2 date window
    sem2_start  = db.Column(db.Date)
    sem2_end    = db.Column(db.Date)
    is_current  = db.Column(db.Boolean, default=False)
    status      = db.Column(db.String(20), default="active")        # active | archived
    created_at  = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    university = db.relationship("University", back_populates="academic_years")
    timetables = db.relationship("Timetable", back_populates="year", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("name", "university_id", name="uq_academic_year_uni"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "university_id": self.university_id,
            "sem1_start": self.sem1_start.isoformat() if self.sem1_start else None,
            "sem1_end":   self.sem1_end.isoformat()   if self.sem1_end   else None,
            "sem2_start": self.sem2_start.isoformat() if self.sem2_start else None,
            "sem2_end":   self.sem2_end.isoformat()   if self.sem2_end   else None,
            "is_current": self.is_current,
            "status":     self.status,
        }


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    faculty = db.Column(db.String(150))
    head_name = db.Column(db.String(150))
    university_id = db.Column(db.String(36), db.ForeignKey("universities.id"))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    university = db.relationship("University", back_populates="departments")
    programs = db.relationship("Program", back_populates="department", cascade="all, delete-orphan")
    courses = db.relationship("Course", back_populates="department", cascade="all, delete-orphan")
    lecturers = db.relationship("Lecturer", back_populates="department")

    __table_args__ = (
        db.UniqueConstraint("code", "university_id", name="uq_dept_code_university"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "faculty": self.faculty,
            "head_name": self.head_name,
            "university_id": self.university_id,
            "university": self.university.to_dict() if self.university else None,
        }


class Program(db.Model):
    """A study programme within a department, e.g. BCS, BIT, DCS."""
    __tablename__ = "programs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    department_id = db.Column(db.String(36), db.ForeignKey("departments.id"), nullable=False)
    # Certificate, Diploma, Bachelor, Master, PhD
    academic_level = db.Column(db.String(50), nullable=False, default="Bachelor")
    duration_years = db.Column(db.Integer, default=3)
    description = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    department = db.relationship("Department", back_populates="programs")
    courses = db.relationship("Course", back_populates="program")
    student_groups = db.relationship("StudentGroup", back_populates="program", cascade="all, delete-orphan")
    timetables = db.relationship("Timetable", back_populates="program")
    lecturers = db.relationship("Lecturer", secondary=lecturer_programs, back_populates="programs")

    __table_args__ = (
        db.UniqueConstraint("code", "department_id", name="uq_program_code_dept"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "department_id": self.department_id,
            "department": self.department.to_dict() if self.department else None,
            "academic_level": self.academic_level,
            "duration_years": self.duration_years,
            "description": self.description,
            "is_active": self.is_active,
        }


class StudentGroup(db.Model):
    """A cohort / class within a programme, e.g. BCS Year 2 Group A."""
    __tablename__ = "student_groups"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    program_id = db.Column(db.String(36), db.ForeignKey("programs.id"), nullable=False)
    year_of_study = db.Column(db.Integer, nullable=False, default=1)
    semester = db.Column(db.Integer, nullable=False, default=1)
    student_count = db.Column(db.Integer, default=30)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    program = db.relationship("Program", back_populates="student_groups")
    courses = db.relationship("Course", secondary="course_student_groups", back_populates="student_groups")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "program_id": self.program_id,
            "program": self.program.to_dict() if self.program else None,
            "year_of_study": self.year_of_study,
            "semester": self.semester,
            "student_count": self.student_count,
            "is_active": self.is_active,
            "course_ids": [c.id for c in self.courses] if self.courses else [],
        }


class Room(db.Model):
    __tablename__ = "rooms"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), nullable=False, unique=True)
    capacity = db.Column(db.Integer, nullable=False, default=30)
    room_type = db.Column(db.String(50), default="lecture")  # lecture, lab, seminar
    building = db.Column(db.String(100))
    floor = db.Column(db.Integer, default=1)
    has_projector = db.Column(db.Boolean, default=True)
    has_lab_equipment = db.Column(db.Boolean, default=False)
    is_available = db.Column(db.Boolean, default=True)
    university_id = db.Column(db.String(36), db.ForeignKey("universities.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "code": self.code,
            "capacity": self.capacity, "room_type": self.room_type,
            "building": self.building, "floor": self.floor,
            "has_projector": self.has_projector, "has_lab_equipment": self.has_lab_equipment,
            "is_available": self.is_available, "university_id": self.university_id,
        }


class Lecturer(db.Model):
    __tablename__ = "lecturers"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36))  # reference to auth-service user
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    phone = db.Column(db.String(20))
    staff_id = db.Column(db.String(50), unique=True)
    department_id = db.Column(db.String(36), db.ForeignKey("departments.id"))
    specialization = db.Column(db.String(200))
    max_hours_per_week = db.Column(db.Integer, default=20)
    max_hours_per_day = db.Column(db.Integer, default=6)
    max_consecutive_hours = db.Column(db.Integer, default=3)
    preferred_days = db.Column(db.JSON, default=list)         # ["Monday", "Wednesday"]
    unavailable_slots = db.Column(db.JSON, default=list)      # [slot_id, ...]  explicit block list
    availability = db.Column(db.JSON, default=dict)           # {day: [slot_ids]}
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    department = db.relationship("Department", back_populates="lecturers")
    courses = db.relationship("Course", back_populates="lecturer")
    programs = db.relationship("Program", secondary=lecturer_programs, back_populates="lecturers")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "email": self.email,
            "phone": self.phone,
            "staff_id": self.staff_id, "specialization": self.specialization,
            "max_hours_per_week": self.max_hours_per_week,
            "max_hours_per_day": self.max_hours_per_day,
            "max_consecutive_hours": self.max_consecutive_hours,
            "preferred_days": self.preferred_days or [],
            "unavailable_slots": self.unavailable_slots or [],
            "availability": self.availability,
            "department": self.department.to_dict() if self.department else None,
            "program_ids": [p.id for p in self.programs],
        }


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), nullable=False, unique=True)
    department_id = db.Column(db.String(36), db.ForeignKey("departments.id"))
    program_id = db.Column(db.String(36), db.ForeignKey("programs.id"))
    lecturer_id = db.Column(db.String(36), db.ForeignKey("lecturers.id"))
    semester = db.Column(db.Integer, nullable=False, default=1)
    year_of_study = db.Column(db.Integer, nullable=False, default=1)
    credit_hours = db.Column(db.Integer, default=3)
    weekly_hours = db.Column(db.Integer, default=3)  # contact hours per week
    student_count = db.Column(db.Integer, default=30)
    requires_lab = db.Column(db.Boolean, default=False)
    course_type = db.Column(db.String(50), default="core")  # core, elective, lab
    priority = db.Column(db.Integer, default=1)  # higher = scheduled first
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    department = db.relationship("Department", back_populates="courses")
    program = db.relationship("Program", back_populates="courses")
    lecturer = db.relationship("Lecturer", back_populates="courses")
    student_groups = db.relationship("StudentGroup", secondary="course_student_groups", back_populates="courses")
    group_lecturers = db.relationship("CourseGroupLecturer", back_populates="course",
                                      cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "code": self.code,
            "semester": self.semester, "year_of_study": self.year_of_study,
            "credit_hours": self.credit_hours, "weekly_hours": self.weekly_hours,
            "student_count": self.student_count, "requires_lab": self.requires_lab,
            "course_type": self.course_type, "priority": self.priority,
            "program_id": self.program_id,
            "program": self.program.to_dict() if self.program else None,
            "lecturer": self.lecturer.to_dict() if self.lecturer else None,
            "department": self.department.to_dict() if self.department else None,
            "student_group_ids": [g.id for g in self.student_groups] if self.student_groups else [],
            "student_groups": [{"id": g.id, "code": g.code, "name": g.name} for g in self.student_groups] if self.student_groups else [],
            # Per-group lecturer overrides: { student_group_id: { lecturer_id, lecturer } }
            "group_lecturers": {
                gl.student_group_id: {
                    "lecturer_id": gl.lecturer_id,
                    "lecturer":    gl.lecturer.to_dict() if gl.lecturer else None,
                }
                for gl in self.group_lecturers
            },
        }


class CourseGroupLecturer(db.Model):
    """
    Per-(course, student_group) lecturer override.
    When the same course is taught to multiple groups by *different* lecturers,
    add a row here for each group that has a non-default lecturer.
    Falls back to Course.lecturer_id when no row exists for a (course, group) pair.
    """
    __tablename__ = "course_group_lecturers"

    course_id        = db.Column(db.String(36), db.ForeignKey("courses.id",        ondelete="CASCADE"),   primary_key=True)
    student_group_id = db.Column(db.String(36), db.ForeignKey("student_groups.id", ondelete="CASCADE"),   primary_key=True)
    lecturer_id      = db.Column(db.String(36), db.ForeignKey("lecturers.id",      ondelete="SET NULL"),  nullable=True)

    course        = db.relationship("Course",        back_populates="group_lecturers")
    student_group = db.relationship("StudentGroup")
    lecturer      = db.relationship("Lecturer")

    def to_dict(self):
        return {
            "course_id":        self.course_id,
            "student_group_id": self.student_group_id,
            "lecturer_id":      self.lecturer_id,
            "lecturer":         self.lecturer.to_dict() if self.lecturer else None,
        }


class TimeSlot(db.Model):
    __tablename__ = "time_slots"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    day = db.Column(db.String(20), nullable=False)         # Monday – Friday / Saturday
    start_time = db.Column(db.String(10), nullable=False)  # "08:00"
    end_time = db.Column(db.String(10), nullable=False)    # "09:00"
    slot_index = db.Column(db.Integer)                     # sequential ordering
    is_break = db.Column(db.Boolean, default=False)
    # class | break | lunch | lab | exam — drives GA eligibility
    slot_type = db.Column(db.String(20), default="class")
    label = db.Column(db.String(100))                      # "Period 1", "Lunch Break"
    template_id = db.Column(db.String(36), db.ForeignKey("timetable_templates.id"))
    academic_year = db.Column(db.String(20))

    template = db.relationship("TimetableTemplate")

    def to_dict(self):
        return {
            "id": self.id, "day": self.day,
            "start_time": self.start_time, "end_time": self.end_time,
            "slot_index": self.slot_index, "is_break": self.is_break,
            "slot_type": self.slot_type, "label": self.label,
            "template_id": self.template_id,
        }


class Timetable(db.Model):
    __tablename__ = "timetables"
    __table_args__ = (
        db.Index("ix_timetables_department_id_status", "department_id", "status"),
        db.Index("ix_timetables_calendar_semester_id", "calendar_semester_id"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    department_id = db.Column(db.String(36), db.ForeignKey("departments.id"))
    program_id = db.Column(db.String(36), db.ForeignKey("programs.id"))
    template_id = db.Column(db.String(36), db.ForeignKey("timetable_templates.id"))
    academic_year_id = db.Column(db.String(36), db.ForeignKey("academic_years.id"))
    # References academic_semesters.id in calendar-service (soft ref, no FK across services)
    calendar_semester_id = db.Column(db.String(36))
    status = db.Column(db.String(30), default="draft")  # draft, generating, active, archived
    version = db.Column(db.Integer, default=1)
    fitness_score = db.Column(db.Float)
    # Serialised violation report from last GA run
    violation_report = db.Column(db.JSON, default=list)
    generation_time_seconds = db.Column(db.Float)
    generations_run = db.Column(db.Integer)
    created_by = db.Column(db.String(36))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    entries = db.relationship("TimetableEntry", back_populates="timetable", cascade="all, delete-orphan")
    snapshots = db.relationship("TimetableSnapshot", back_populates="timetable", cascade="all, delete-orphan")
    department = db.relationship("Department")
    program = db.relationship("Program", back_populates="timetables")
    template = db.relationship("TimetableTemplate")
    year = db.relationship("AcademicYear", back_populates="timetables")

    def to_dict(self, include_entries=False):
        d = {
            "id": self.id, "name": self.name, "semester": self.semester,
            "academic_year": self.academic_year, "status": self.status,
            "version": self.version, "fitness_score": self.fitness_score,
            "generation_time_seconds": self.generation_time_seconds,
            "generations_run": self.generations_run,
            "template_id": self.template_id,
            "template": self.template.to_dict() if self.template else None,
            "academic_year_id": self.academic_year_id,
            "academic_year_obj": self.year.to_dict() if self.year else None,
            "calendar_semester_id": self.calendar_semester_id,
            "violation_report": self.violation_report or [],
            "department": self.department.to_dict() if self.department else None,
            "program": self.program.to_dict() if self.program else None,
            "created_at": self.created_at.isoformat(),
        }
        if include_entries:
            d["entries"] = [e.to_dict() for e in self.entries]
        return d


class TimetableEntry(db.Model):
    __tablename__ = "timetable_entries"
    __table_args__ = (
        db.Index("ix_timetable_entries_timetable_id", "timetable_id"),
        db.Index("ix_timetable_entries_lecturer_id", "lecturer_id"),
        db.Index("ix_timetable_entries_room_id", "room_id"),
        db.Index("ix_timetable_entries_time_slot_id", "time_slot_id"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timetable_id = db.Column(db.String(36), db.ForeignKey("timetables.id"), nullable=False)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    lecturer_id = db.Column(db.String(36), db.ForeignKey("lecturers.id"), nullable=False)
    room_id = db.Column(db.String(36), db.ForeignKey("rooms.id"), nullable=False)
    time_slot_id = db.Column(db.String(36), db.ForeignKey("time_slots.id"), nullable=False)
    student_group_id = db.Column(db.String(36), db.ForeignKey("student_groups.id"))
    is_locked = db.Column(db.Boolean, default=False)  # locked entries cannot be moved
    notes = db.Column(db.String(500))

    timetable = db.relationship("Timetable", back_populates="entries")
    course = db.relationship("Course")
    lecturer = db.relationship("Lecturer")
    room = db.relationship("Room")
    time_slot = db.relationship("TimeSlot")
    student_group = db.relationship("StudentGroup")

    def to_dict(self):
        return {
            "id": self.id,
            "course": self.course.to_dict() if self.course else None,
            "lecturer": self.lecturer.to_dict() if self.lecturer else None,
            "room": self.room.to_dict() if self.room else None,
            "time_slot": self.time_slot.to_dict() if self.time_slot else None,
            "student_group": self.student_group.to_dict() if self.student_group else None,
            "is_locked": self.is_locked,
            "notes": self.notes,
        }


class TimetableSnapshot(db.Model):
    __tablename__ = "timetable_snapshots"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timetable_id = db.Column(db.String(36), db.ForeignKey("timetables.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.String(500))
    created_by = db.Column(db.String(36))
    snapshot_data = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    timetable = db.relationship("Timetable", back_populates="snapshots")

    def to_dict(self):
        return {
            "id": self.id,
            "timetable_id": self.timetable_id,
            "version": self.version,
            "notes": self.notes,
            "created_by": self.created_by,
            "entry_count": len(self.snapshot_data or []),
            "created_at": self.created_at.isoformat(),
        }


class Constraint(db.Model):
    """
    Structured scheduling constraint loaded into the GA fitness evaluator.

    rule_type values (used by fitness.py to route evaluation):
      Lecturer: max_daily_hours | max_weekly_hours | max_consecutive | preferred_times | unavailable
      Room:     capacity_check  | equipment_required | shared_room
      Student:  no_overlap      | max_consecutive    | exam_gap
      Academic: semester_only   | fixed_session      | mandatory_order
      System:   timezone_aware  | holiday_aware
    """
    __tablename__ = "constraints"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    constraint_type = db.Column(db.String(50), nullable=False)  # hard | soft
    category = db.Column(db.String(100))         # lecturer | room | student | academic | system
    rule_type = db.Column(db.String(100))        # structured rule name (see docstring)
    # Optional entity scoping — null means constraint applies globally
    entity_type = db.Column(db.String(50))       # lecturer | room | student_group | program | department | university
    entity_id = db.Column(db.String(36))         # FK-style reference to the specific entity
    university_id = db.Column(db.String(36))     # restrict constraint to a university
    department_id = db.Column(db.String(36), db.ForeignKey("departments.id"))
    weight = db.Column(db.Float, default=1.0)
    config = db.Column(db.JSON, default=dict)    # rule-specific parameters
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    department = db.relationship("Department")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name,
            "constraint_type": self.constraint_type,
            "category": self.category, "rule_type": self.rule_type,
            "entity_type": self.entity_type, "entity_id": self.entity_id,
            "university_id": self.university_id,
            "department_id": self.department_id,
            "weight": self.weight, "config": self.config,
            "is_active": self.is_active,
        }

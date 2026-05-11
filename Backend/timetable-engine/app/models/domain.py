"""
Core domain models for the timetable engine.
All scheduling entities share a common UUID primary key and timestamp pattern.
"""
import uuid
from datetime import datetime, timezone
from app.extensions import db


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(150), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    faculty = db.Column(db.String(150))
    head_name = db.Column(db.String(150))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    courses = db.relationship("Course", back_populates="department", cascade="all, delete-orphan")
    lecturers = db.relationship("Lecturer", back_populates="department")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "code": self.code,
                "faculty": self.faculty, "head_name": self.head_name}


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
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "code": self.code,
            "capacity": self.capacity, "room_type": self.room_type,
            "building": self.building, "floor": self.floor,
            "has_projector": self.has_projector, "has_lab_equipment": self.has_lab_equipment,
            "is_available": self.is_available,
        }


class Lecturer(db.Model):
    __tablename__ = "lecturers"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36))  # reference to auth-service user
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    staff_id = db.Column(db.String(50), unique=True)
    department_id = db.Column(db.String(36), db.ForeignKey("departments.id"))
    specialization = db.Column(db.String(200))
    max_hours_per_week = db.Column(db.Integer, default=20)
    availability = db.Column(db.JSON, default=dict)  # {day: [slot_ids]}
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    department = db.relationship("Department", back_populates="lecturers")
    courses = db.relationship("Course", back_populates="lecturer")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "email": self.email,
            "staff_id": self.staff_id, "specialization": self.specialization,
            "max_hours_per_week": self.max_hours_per_week, "availability": self.availability,
            "department": self.department.to_dict() if self.department else None,
        }


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), nullable=False, unique=True)
    department_id = db.Column(db.String(36), db.ForeignKey("departments.id"))
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
    lecturer = db.relationship("Lecturer", back_populates="courses")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "code": self.code,
            "semester": self.semester, "year_of_study": self.year_of_study,
            "credit_hours": self.credit_hours, "weekly_hours": self.weekly_hours,
            "student_count": self.student_count, "requires_lab": self.requires_lab,
            "course_type": self.course_type, "priority": self.priority,
            "lecturer": self.lecturer.to_dict() if self.lecturer else None,
            "department": self.department.to_dict() if self.department else None,
        }


class TimeSlot(db.Model):
    __tablename__ = "time_slots"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    day = db.Column(db.String(20), nullable=False)      # Monday – Friday / Saturday
    start_time = db.Column(db.String(10), nullable=False)  # "08:00"
    end_time = db.Column(db.String(10), nullable=False)    # "09:00"
    slot_index = db.Column(db.Integer)  # sequential ordering
    is_break = db.Column(db.Boolean, default=False)
    academic_year = db.Column(db.String(20))

    def to_dict(self):
        return {
            "id": self.id, "day": self.day,
            "start_time": self.start_time, "end_time": self.end_time,
            "slot_index": self.slot_index, "is_break": self.is_break,
        }


class Timetable(db.Model):
    __tablename__ = "timetables"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    department_id = db.Column(db.String(36), db.ForeignKey("departments.id"))
    status = db.Column(db.String(30), default="draft")  # draft, generating, active, archived
    version = db.Column(db.Integer, default=1)
    fitness_score = db.Column(db.Float)
    generation_time_seconds = db.Column(db.Float)
    generations_run = db.Column(db.Integer)
    created_by = db.Column(db.String(36))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    entries = db.relationship("TimetableEntry", back_populates="timetable", cascade="all, delete-orphan")
    snapshots = db.relationship("TimetableSnapshot", back_populates="timetable", cascade="all, delete-orphan")
    department = db.relationship("Department")

    def to_dict(self, include_entries=False):
        d = {
            "id": self.id, "name": self.name, "semester": self.semester,
            "academic_year": self.academic_year, "status": self.status,
            "version": self.version, "fitness_score": self.fitness_score,
            "generation_time_seconds": self.generation_time_seconds,
            "generations_run": self.generations_run,
            "department": self.department.to_dict() if self.department else None,
            "created_at": self.created_at.isoformat(),
        }
        if include_entries:
            d["entries"] = [e.to_dict() for e in self.entries]
        return d


class TimetableEntry(db.Model):
    __tablename__ = "timetable_entries"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timetable_id = db.Column(db.String(36), db.ForeignKey("timetables.id"), nullable=False)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    lecturer_id = db.Column(db.String(36), db.ForeignKey("lecturers.id"), nullable=False)
    room_id = db.Column(db.String(36), db.ForeignKey("rooms.id"), nullable=False)
    time_slot_id = db.Column(db.String(36), db.ForeignKey("time_slots.id"), nullable=False)
    is_locked = db.Column(db.Boolean, default=False)  # locked entries cannot be moved
    notes = db.Column(db.String(500))

    timetable = db.relationship("Timetable", back_populates="entries")
    course = db.relationship("Course")
    lecturer = db.relationship("Lecturer")
    room = db.relationship("Room")
    time_slot = db.relationship("TimeSlot")

    def to_dict(self):
        return {
            "id": self.id,
            "course": self.course.to_dict() if self.course else None,
            "lecturer": self.lecturer.to_dict() if self.lecturer else None,
            "room": self.room.to_dict() if self.room else None,
            "time_slot": self.time_slot.to_dict() if self.time_slot else None,
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
    __tablename__ = "constraints"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    constraint_type = db.Column(db.String(50), nullable=False)  # hard, soft
    category = db.Column(db.String(100))  # lecturer, room, student, department
    weight = db.Column(db.Float, default=1.0)
    config = db.Column(db.JSON, default=dict)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "constraint_type": self.constraint_type,
            "category": self.category, "weight": self.weight, "config": self.config,
            "is_active": self.is_active,
        }

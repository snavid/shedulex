"""
Timetable service — converts DB data to GA input, runs the algorithm,
then persists results back to the database.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from flask import current_app
from app.extensions import db
from app.models.domain import (
    Course, Lecturer, Room, TimeSlot, Timetable, TimetableEntry, Department,
)
from app.ga import run_ga, GAConfig


def generate_timetable(
    department_id: str,
    semester: int,
    academic_year: str,
    name: str,
    created_by: str,
    config_overrides: dict | None = None,
) -> Timetable:
    """
    Orchestrates the full GA pipeline for a department/semester pair.
    Raises ValueError if there is not enough data to schedule.
    """
    # Load domain data
    courses = (
        Course.query
        .filter_by(department_id=department_id, semester=semester, is_active=True)
        .all()
    )
    if not courses:
        raise ValueError("No active courses found for this department and semester.")

    lecturers = Lecturer.query.filter_by(is_active=True).all()
    rooms = Room.query.filter_by(is_available=True).all()
    slots = TimeSlot.query.order_by(TimeSlot.slot_index).all()

    if not rooms:
        raise ValueError("No available rooms found.")
    if not slots:
        raise ValueError("No time slots configured.")

    # Serialise for GA (plain dicts — keeps the GA layer decoupled from ORM)
    courses_data = [
        {
            "id": c.id,
            "name": c.name,
            "lecturer_id": c.lecturer_id,
            "student_count": c.student_count,
            "requires_lab": c.requires_lab,
            "weekly_hours": c.weekly_hours,
            "department_id": c.department_id,
            "priority": c.priority,
        }
        for c in courses
    ]
    rooms_data = [
        {
            "id": r.id,
            "capacity": r.capacity,
            "room_type": r.room_type,
        }
        for r in rooms
    ]
    slots_data = [
        {
            "id": s.id,
            "day": s.day,
            "slot_index": s.slot_index,
            "is_break": s.is_break,
        }
        for s in slots
    ]
    lecturers_dict = {
        l.id: {"id": l.id, "name": l.name, "availability": l.availability or {}}
        for l in lecturers
    }

    # Build GA config
    cfg_params = {
        "population_size": 100,
        "max_generations": 300,
        "elite_count": 5,
        "fitness_threshold": 0.95,
    }
    if config_overrides:
        cfg_params.update(config_overrides)
    ga_cfg = GAConfig(**cfg_params)

    # Create a timetable record in "generating" state
    timetable = Timetable(
        name=name,
        semester=semester,
        academic_year=academic_year,
        department_id=department_id,
        status="generating",
        created_by=created_by,
    )
    db.session.add(timetable)
    db.session.commit()

    try:
        result = run_ga(
            courses=courses_data,
            rooms=rooms_data,
            slots=slots_data,
            lecturers=lecturers_dict,
            config=ga_cfg,
        )
    except Exception as exc:
        timetable.status = "failed"
        db.session.commit()
        raise RuntimeError(f"GA failed: {exc}") from exc

    # Persist entries
    for gene in result.best_chromosome.genes:
        entry = TimetableEntry(
            timetable_id=timetable.id,
            course_id=gene.course_id,
            lecturer_id=_get_lecturer_id(gene.course_id, courses),
            room_id=gene.room_id,
            time_slot_id=gene.time_slot_id,
        )
        db.session.add(entry)

    timetable.status = "active"
    timetable.fitness_score = result.best_fitness
    timetable.generation_time_seconds = result.elapsed_seconds
    timetable.generations_run = result.generations_run
    db.session.commit()

    return timetable


def _get_lecturer_id(course_id: str, courses: list) -> str | None:
    for c in courses:
        if c.id == course_id:
            return c.lecturer_id
    return None


def get_timetable_by_id(timetable_id: str) -> Timetable | None:
    return Timetable.query.get(timetable_id)


def list_timetables(department_id: str = None, semester: int = None, status: str = None):
    q = Timetable.query
    if department_id:
        q = q.filter_by(department_id=department_id)
    if semester:
        q = q.filter_by(semester=semester)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(Timetable.created_at.desc()).all()


def swap_entries(entry1_id: str, entry2_id: str) -> tuple:
    """Swap time slots of two entries (drag-and-drop)."""
    e1 = TimetableEntry.query.get(entry1_id)
    e2 = TimetableEntry.query.get(entry2_id)
    if not e1 or not e2:
        raise ValueError("One or both entries not found.")
    if e1.is_locked or e2.is_locked:
        raise ValueError("Cannot move locked entries.")

    e1.time_slot_id, e2.time_slot_id = e2.time_slot_id, e1.time_slot_id
    db.session.commit()
    return e1, e2


def detect_conflicts(timetable_id: str) -> list[dict]:
    """Return a list of conflict descriptions for a given timetable."""
    entries = TimetableEntry.query.filter_by(timetable_id=timetable_id).all()
    conflicts = []

    seen_lecturer_slot: dict = {}
    seen_room_slot: dict = {}

    for e in entries:
        lec_key = f"{e.lecturer_id}:{e.time_slot_id}"
        room_key = f"{e.room_id}:{e.time_slot_id}"

        if lec_key in seen_lecturer_slot:
            conflicts.append({
                "type": "lecturer_clash",
                "message": f"Lecturer double-booked at slot {e.time_slot_id}",
                "entry1": seen_lecturer_slot[lec_key],
                "entry2": e.id,
            })
        else:
            seen_lecturer_slot[lec_key] = e.id

        if room_key in seen_room_slot:
            conflicts.append({
                "type": "room_clash",
                "message": f"Room double-booked at slot {e.time_slot_id}",
                "entry1": seen_room_slot[room_key],
                "entry2": e.id,
            })
        else:
            seen_room_slot[room_key] = e.id

    return conflicts


def seed_default_slots():
    """Create a standard Mon–Fri timetable grid if none exists."""
    if TimeSlot.query.count() > 0:
        return

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    periods = [
        ("08:00", "09:00"), ("09:00", "10:00"), ("10:00", "11:00"),
        ("11:00", "12:00"), ("12:00", "13:00"),  # lunch break
        ("13:00", "14:00"), ("14:00", "15:00"), ("15:00", "16:00"),
        ("16:00", "17:00"),
    ]
    idx = 0
    for day in days:
        for i, (start, end) in enumerate(periods):
            slot = TimeSlot(
                day=day,
                start_time=start,
                end_time=end,
                slot_index=idx,
                is_break=(start == "12:00"),
            )
            db.session.add(slot)
            idx += 1
    db.session.commit()

"""
Timetable service — converts DB data to GA input, runs the algorithm,
then persists results back to the database.
"""
from __future__ import annotations
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models.domain import (
    Course, Lecturer, Room, TimeSlot, Timetable, TimetableEntry, TimetableSnapshot,
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

    lecturer_by_course_id = {c.id: c.lecturer_id for c in courses}

    # Persist entries
    for gene in result.best_chromosome.genes:
        entry = TimetableEntry(
            timetable_id=timetable.id,
            course_id=gene.course_id,
            lecturer_id=lecturer_by_course_id.get(gene.course_id),
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


def get_timetable_by_id(timetable_id: str) -> Timetable | None:
    return (
        Timetable.query
        .options(
            joinedload(Timetable.department),
            selectinload(Timetable.entries).joinedload(TimetableEntry.room),
            selectinload(Timetable.entries).joinedload(TimetableEntry.time_slot),
            selectinload(Timetable.entries).joinedload(TimetableEntry.lecturer).joinedload(Lecturer.department),
            selectinload(Timetable.entries).joinedload(TimetableEntry.course).joinedload(Course.department),
            selectinload(Timetable.entries).joinedload(TimetableEntry.course).joinedload(Course.lecturer).joinedload(Lecturer.department),
        )
        .filter_by(id=timetable_id)
        .first()
    )


def list_timetables(department_id: str = None, semester: int = None, status: str = None):
    q = Timetable.query.options(joinedload(Timetable.department))
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
    if e1.timetable_id != e2.timetable_id:
        raise ValueError("Entries must belong to the same timetable.")
    if e1.is_locked or e2.is_locked:
        raise ValueError("Cannot move locked entries.")

    e1.time_slot_id, e2.time_slot_id = e2.time_slot_id, e1.time_slot_id
    db.session.commit()
    return e1, e2


def move_entry_to_slot(entry_id: str, time_slot_id: str) -> TimetableEntry:
    """Move one entry to another time slot without swapping (target slot must be free for room/lecturer)."""
    entry = TimetableEntry.query.get(entry_id)
    if not entry:
        raise ValueError("Entry not found.")
    if entry.is_locked:
        raise ValueError("Cannot move locked entry.")

    slot = TimeSlot.query.get(time_slot_id)
    if not slot:
        raise ValueError("Time slot not found.")

    if entry.time_slot_id == time_slot_id:
        return entry

    timetable_id = entry.timetable_id
    others = (
        TimetableEntry.query.filter_by(timetable_id=timetable_id)
        .filter(TimetableEntry.id != entry.id)
        .all()
    )

    for o in others:
        if o.time_slot_id != time_slot_id:
            continue
        if o.lecturer_id == entry.lecturer_id:
            raise ValueError("Lecturer is already scheduled in the target time slot.")
        if o.room_id == entry.room_id:
            raise ValueError("Room is already booked in the target time slot.")

    entry.time_slot_id = time_slot_id
    timetable = Timetable.query.get(timetable_id)
    if timetable:
        timetable.version = (timetable.version or 1) + 1
    db.session.commit()
    return entry


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


def list_entries(timetable_id: str | None = None, day: str | None = None):
    q = (
        TimetableEntry.query
        .options(
            joinedload(TimetableEntry.room),
            joinedload(TimetableEntry.time_slot),
            joinedload(TimetableEntry.lecturer).joinedload(Lecturer.department),
            joinedload(TimetableEntry.course).joinedload(Course.department),
            joinedload(TimetableEntry.course).joinedload(Course.lecturer).joinedload(Lecturer.department),
        )
        .join(TimeSlot, TimetableEntry.time_slot_id == TimeSlot.id)
        .join(Timetable, TimetableEntry.timetable_id == Timetable.id)
    )
    q = q.filter(Timetable.status == "active")
    if timetable_id:
        q = q.filter(TimetableEntry.timetable_id == timetable_id)
    if day:
        q = q.filter(TimeSlot.day == day)
    return q.order_by(TimeSlot.slot_index.asc()).all()


def predict_conflicts(timetable_id: str) -> list[dict]:
    """
    Predict likely pressure points even if current entries are technically conflict-free.
    This is useful for proactive adjustments before publishing a timetable.
    """
    timetable = Timetable.query.get(timetable_id)
    if not timetable:
        return []

    entries = (
        TimetableEntry.query
        .options(
            joinedload(TimetableEntry.room),
            joinedload(TimetableEntry.time_slot),
            joinedload(TimetableEntry.lecturer),
            joinedload(TimetableEntry.course),
        )
        .filter_by(timetable_id=timetable_id)
        .all()
    )
    predictions: list[dict] = []

    # 1) Room capacity pressure
    for entry in entries:
        course = entry.course
        room = entry.room
        if not course or not room:
            continue
        if course.student_count > room.capacity:
            overflow = course.student_count - room.capacity
            predictions.append({
                "type": "capacity_risk",
                "severity": "high",
                "entry_id": entry.id,
                "message": f"{course.code} exceeds room capacity by {overflow} students.",
            })

    # 2) Consecutive lecturer overload (4+ consecutive slots/day)
    by_lecturer_day: dict[tuple[str, str], list[int]] = {}
    lecturer_names = {
        e.lecturer_id: e.lecturer.name
        for e in entries
        if e.lecturer_id and e.lecturer is not None
    }
    for entry in entries:
        if not entry.lecturer_id or not entry.time_slot:
            continue
        key = (entry.lecturer_id, entry.time_slot.day)
        by_lecturer_day.setdefault(key, []).append(entry.time_slot.slot_index or 0)

    for (lecturer_id, day), slot_indexes in by_lecturer_day.items():
        sorted_indexes = sorted(slot_indexes)
        streak = 1
        max_streak = 1
        for idx in range(1, len(sorted_indexes)):
            if sorted_indexes[idx] == sorted_indexes[idx - 1] + 1:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 1
        if max_streak >= 4:
            lecturer_name = lecturer_names.get(lecturer_id, lecturer_id)
            predictions.append({
                "type": "lecturer_workload_risk",
                "severity": "medium",
                "lecturer_id": lecturer_id,
                "message": f"{lecturer_name} has {max_streak} consecutive periods on {day}.",
            })

    # 3) Peak-hour density by day/slot
    occupancy: dict[str, int] = {}
    for entry in entries:
        slot = entry.time_slot
        if not slot:
            continue
        key = f"{slot.day} {slot.start_time}"
        occupancy[key] = occupancy.get(key, 0) + 1

    if occupancy:
        max_occupancy = max(occupancy.values())
        for key, count in occupancy.items():
            if max_occupancy >= 4 and count == max_occupancy:
                predictions.append({
                    "type": "peak_hour_risk",
                    "severity": "low",
                    "message": f"Peak congestion at {key} ({count} classes running in parallel).",
                })

    return predictions


def create_snapshot(timetable_id: str, created_by: str | None, notes: str = "") -> TimetableSnapshot:
    timetable = Timetable.query.get(timetable_id)
    if not timetable:
        raise ValueError("Timetable not found.")

    snapshot_data = []
    for entry in timetable.entries:
        snapshot_data.append({
            "course_id": entry.course_id,
            "lecturer_id": entry.lecturer_id,
            "room_id": entry.room_id,
            "time_slot_id": entry.time_slot_id,
            "is_locked": entry.is_locked,
            "notes": entry.notes,
        })

    snapshot = TimetableSnapshot(
        timetable_id=timetable.id,
        version=timetable.version,
        notes=notes,
        created_by=created_by,
        snapshot_data=snapshot_data,
    )
    db.session.add(snapshot)
    db.session.commit()
    return snapshot


def list_snapshots(timetable_id: str):
    return (
        TimetableSnapshot.query
        .filter_by(timetable_id=timetable_id)
        .order_by(TimetableSnapshot.created_at.desc())
        .all()
    )


def restore_snapshot(snapshot_id: str) -> Timetable:
    snapshot = TimetableSnapshot.query.get(snapshot_id)
    if not snapshot:
        raise ValueError("Snapshot not found.")

    timetable = Timetable.query.get(snapshot.timetable_id)
    if not timetable:
        raise ValueError("Timetable not found.")

    TimetableEntry.query.filter_by(timetable_id=timetable.id).delete(synchronize_session=False)
    for row in snapshot.snapshot_data or []:
        restored = TimetableEntry(
            timetable_id=timetable.id,
            course_id=row["course_id"],
            lecturer_id=row["lecturer_id"],
            room_id=row["room_id"],
            time_slot_id=row["time_slot_id"],
            is_locked=row.get("is_locked", False),
            notes=row.get("notes"),
        )
        db.session.add(restored)

    timetable.version = (timetable.version or 1) + 1
    db.session.commit()
    return timetable


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

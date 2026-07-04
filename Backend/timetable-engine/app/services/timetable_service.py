"""
Timetable service — converts DB data to GA input, runs the algorithm,
then persists results back to the database.
"""
from __future__ import annotations
import os
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models.domain import (
    Constraint, Course, CourseGroupLecturer, Department, Lecturer, Program, Room, StudentGroup,
    TimeSlot, Timetable, TimetableEntry, TimetableSnapshot, TimetableTemplate,
)
from app.ga import run_ga, GAConfig


def _load_external_bookings(current_timetable: "Timetable") -> dict:
    """Return room+lecturer bookings from OTHER active timetables in the same
    university / semester / academic-year, keyed by (id, day, start_time, end_time).

    Uses wall-clock times (not time_slot_id) so two departments using different
    TimetableTemplate rows whose blocks share the same physical hours still collide.
    """
    dept = current_timetable.department
    if not dept:
        return {"room": {}, "lecturer": {}}

    q = (
        TimetableEntry.query
        .join(Timetable, TimetableEntry.timetable_id == Timetable.id)
        .join(Department, Timetable.department_id == Department.id)
        .join(TimeSlot, TimetableEntry.time_slot_id == TimeSlot.id)
        .options(
            joinedload(TimetableEntry.time_slot),
            joinedload(TimetableEntry.room),
            joinedload(TimetableEntry.lecturer),
            joinedload(TimetableEntry.course).joinedload(Course.department),
        )
        .filter(
            Department.university_id == dept.university_id,
            Timetable.semester == current_timetable.semester,
            Timetable.status == "active",
            Timetable.id != current_timetable.id,
        )
    )
    if current_timetable.academic_year_id:
        q = q.filter(Timetable.academic_year_id == current_timetable.academic_year_id)
    else:
        q = q.filter(Timetable.academic_year == current_timetable.academic_year)

    room_idx: dict = {}
    lec_idx: dict = {}
    for e in q.all():
        s = e.time_slot
        if not s:
            continue
        meta = {
            "course_name": e.course.name if e.course else "?",
            "department_name": e.course.department.name if e.course and e.course.department else "?",
            "timetable_id": e.timetable_id,
            "room_name": e.room.name if e.room else None,
            "lecturer_name": e.lecturer.name if e.lecturer else None,
        }
        if e.room_id:
            room_idx.setdefault((e.room_id, s.day, s.start_time, s.end_time), []).append(meta)
        if e.lecturer_id:
            lec_idx.setdefault((e.lecturer_id, s.day, s.start_time, s.end_time), []).append(meta)
    return {"room": room_idx, "lecturer": lec_idx}


def generate_timetable(
    department_id: str,
    semester: int,
    academic_year: str,
    name: str,
    created_by: str,
    program_id: str | None = None,
    template_id: str | None = None,
    calendar_semester_id: str | None = None,
    academic_year_id: str | None = None,
    config_overrides: dict | None = None,
) -> Timetable:
    """
    Orchestrates the full GA pipeline for a department/semester pair.
    If program_id is given the schedule is scoped to that programme.
    Raises ValueError if there is not enough data to schedule.
    """
    course_q = Course.query.filter_by(semester=semester, is_active=True)
    if program_id:
        course_q = course_q.filter_by(program_id=program_id)
    else:
        course_q = course_q.filter_by(department_id=department_id)
    courses = course_q.all()
    if not courses:
        scope = f"program {program_id}" if program_id else f"department {department_id}"
        raise ValueError(f"No active courses found for {scope} and semester {semester}.")

    lecturers = Lecturer.query.filter_by(is_active=True).all()
    rooms = Room.query.filter_by(is_available=True).all()

    # Use template-scoped slots if a template is specified
    if template_id:
        slots = TimeSlot.query.filter_by(template_id=template_id).order_by(TimeSlot.slot_index).all()
        if not slots:
            slots = TimeSlot.query.order_by(TimeSlot.slot_index).all()
    else:
        slots = TimeSlot.query.order_by(TimeSlot.slot_index).all()

    if not rooms:
        raise ValueError("No available rooms found.")
    if not slots:
        raise ValueError("No time slots configured.")

    # Load all active constraints from DB (scoped to department/program/global)
    constraint_q = Constraint.query.filter_by(is_active=True)
    db_constraints_raw = constraint_q.all()
    db_constraints_data = [c.to_dict() for c in db_constraints_raw]

    # Load per-group lecturer overrides for these courses.
    # Include rows where lecturer_id IS NULL — those represent "explicitly unassigned"
    # for that (course, group) pair (overrides Course.lecturer_id).
    # Sentinel _NO_OVERRIDE is used below to distinguish "no row" from "row with null".
    _NO_OVERRIDE = object()
    course_ids = [c.id for c in courses]
    _override_rows = CourseGroupLecturer.query.filter(
        CourseGroupLecturer.course_id.in_(course_ids)
    ).all()
    # Map key present → override exists (lecturer_id may be None = explicitly unassigned)
    group_lecturer_overrides: dict[tuple[str, str], str | None] = {
        (gl.course_id, gl.student_group_id): gl.lecturer_id
        for gl in _override_rows
    }

    # Serialise domain objects → plain dicts for GA layer.
    # student_group_ids: explicit assignments take priority; fall back to program-inferred group.
    # per_group_lecturer_ids: effective lecturer per group (override → course default).
    courses_data = []
    for c in courses:
        explicit_groups = [g.id for g in (c.student_groups or [])]
        courses_data.append({
            "id": c.id,
            "name": c.name,
            "lecturer_id": c.lecturer_id,
            "student_count": c.student_count,
            "student_group_id": _resolve_student_group(c) if not explicit_groups else explicit_groups[0],
            "student_group_ids": explicit_groups,  # GA population uses this to explode by group
            # Effective lecturer per group — GA population.py injects this per scheduling unit.
            # If an override row exists (even with lecturer_id=None), that wins over course default.
            "per_group_lecturer_ids": {
                gid: (
                    group_lecturer_overrides[(c.id, gid)]   # may be None (explicit unassign)
                    if (c.id, gid) in group_lecturer_overrides
                    else c.lecturer_id                       # no override → course default
                )
                for gid in explicit_groups
            },
            "requires_lab": c.requires_lab,
            "weekly_hours": c.weekly_hours,
            "department_id": c.department_id,
            "program_id": c.program_id,
            "priority": c.priority,
        })
    rooms_data = [
        {
            "id": r.id,
            "capacity": r.capacity,
            "room_type": r.room_type,
            "name": r.name,
            "building": r.building,
            "has_projector": r.has_projector,
            "has_lab_equipment": r.has_lab_equipment,
        }
        for r in rooms
    ]
    slots_data = [
        {
            "id": s.id,
            "day": s.day,
            "slot_index": s.slot_index,
            "is_break": s.is_break,
            "slot_type": s.slot_type or ("break" if s.is_break else "class"),
            "label": s.label,
            "start_time": s.start_time,
            "end_time": s.end_time,
        }
        for s in slots
    ]
    lecturers_dict = {
        l.id: {
            "id": l.id,
            "name": l.name,
            "availability": l.availability or {},
            "max_hours_per_week": l.max_hours_per_week or 20,
            "max_hours_per_day": l.max_hours_per_day or 6,
            "max_consecutive_hours": l.max_consecutive_hours or 3,
            "preferred_days": l.preferred_days or [],
            "unavailable_slots": l.unavailable_slots or [],
        }
        for l in lecturers
    }

    ga_timeout = int(os.environ.get("GA_TIMEOUT_SECONDS", "0"))
    ga_min_fitness = float(os.environ.get("GA_MIN_FITNESS", "0"))
    cfg_params = {
        "population_size": 100,
        "max_generations": 300,
        "elite_count": 5,
        "fitness_threshold": 0.95,
        "max_seconds": ga_timeout,
    }
    if config_overrides:
        cfg_params.update({k: v for k, v in config_overrides.items() if k in cfg_params})
    ga_cfg = GAConfig(**cfg_params)

    timetable = Timetable(
        name=name,
        semester=semester,
        academic_year=academic_year,
        academic_year_id=academic_year_id,
        department_id=department_id,
        program_id=program_id,
        template_id=template_id,
        calendar_semester_id=calendar_semester_id,
        status="generating",
        created_by=created_by,
    )
    db.session.add(timetable)
    db.session.flush()  # assign primary key without committing

    # Load existing bookings from sibling active timetables so the GA avoids conflicts
    # with rooms/lecturers already scheduled by another department.
    external_bookings = _load_external_bookings(timetable)

    try:
        result = run_ga(
            courses=courses_data,
            rooms=rooms_data,
            slots=slots_data,
            lecturers=lecturers_dict,
            config=ga_cfg,
            db_constraints=db_constraints_data,
            external_bookings=external_bookings,
        )
    except Exception as exc:
        db.session.rollback()
        raise RuntimeError(f"GA failed: {exc}") from exc

    if ga_min_fitness > 0 and result.best_fitness < ga_min_fitness:
        db.session.rollback()
        raise RuntimeError(
            f"GA produced an infeasible timetable (fitness {result.best_fitness:.2f} < "
            f"required {ga_min_fitness:.2f}). Add more rooms or reduce course load."
        )

    lecturer_by_course = {c.id: c.lecturer_id for c in courses}

    for gene in result.best_chromosome.genes:
        # Per-group override takes priority over the course-level default.
        # A null override (explicit unassign) is kept as-is rather than falling
        # back to the course default.
        key = (gene.course_id, gene.student_group_id or "")
        if key in group_lecturer_overrides:
            effective_lecturer_id = group_lecturer_overrides[key]   # may be None
        else:
            effective_lecturer_id = lecturer_by_course.get(gene.course_id)
        entry = TimetableEntry(
            timetable_id=timetable.id,
            course_id=gene.course_id,
            lecturer_id=effective_lecturer_id,
            room_id=gene.room_id,
            time_slot_id=gene.time_slot_id,
            student_group_id=gene.student_group_id or None,
        )
        db.session.add(entry)

    timetable.status = "active"
    timetable.fitness_score = result.best_fitness
    timetable.generation_time_seconds = result.elapsed_seconds
    timetable.generations_run = result.generations_run
    timetable.violation_report = result.violations
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        raise RuntimeError(f"Failed to save timetable results: {exc}") from exc

    from app.services.notification_client import emit_timetable_event
    from app.services.timetable_events import base_event
    emit_timetable_event(base_event(timetable, "generated", triggered_by=created_by))

    return timetable


def _resolve_student_group(course: Course) -> str | None:
    """Return the first student group ID for a course's programme, if any."""
    if course.program_id:
        grp = (
            StudentGroup.query
            .filter_by(program_id=course.program_id, semester=course.semester, is_active=True)
            .first()
        )
        return grp.id if grp else None
    return None


def get_timetable_by_id(timetable_id: str) -> Timetable | None:
    return (
        Timetable.query
        .options(
            joinedload(Timetable.department),
            joinedload(Timetable.program),
            joinedload(Timetable.template),
            selectinload(Timetable.entries).joinedload(TimetableEntry.room),
            selectinload(Timetable.entries).joinedload(TimetableEntry.time_slot),
            selectinload(Timetable.entries).joinedload(TimetableEntry.student_group),
            selectinload(Timetable.entries).joinedload(TimetableEntry.lecturer).joinedload(Lecturer.department),
            selectinload(Timetable.entries).joinedload(TimetableEntry.course).joinedload(Course.department),
            selectinload(Timetable.entries).joinedload(TimetableEntry.course).joinedload(Course.program),
            selectinload(Timetable.entries).joinedload(TimetableEntry.course).joinedload(Course.lecturer).joinedload(Lecturer.department),
        )
        .filter_by(id=timetable_id)
        .first()
    )


def update_timetable_metadata(timetable_id: str, **fields) -> Timetable:
    """Update mutable timetable metadata (e.g. calendar_semester_id)."""
    allowed = {"calendar_semester_id", "name"}
    tt = Timetable.query.get(timetable_id)
    if not tt:
        raise ValueError("Timetable not found.")
    changed = False
    for key, value in fields.items():
        if key in allowed and value is not None:
            setattr(tt, key, value)
            changed = True
    if not changed:
        raise ValueError("No updatable fields provided.")
    db.session.commit()
    return tt


def list_timetables(
    department_id: str = None,
    semester: int = None,
    status: str = None,
    program_id: str = None,
    academic_year_id: str = None,
    university_id: str = None,
):
    q = Timetable.query.options(
        joinedload(Timetable.department),
        joinedload(Timetable.program),
        joinedload(Timetable.template),
        joinedload(Timetable.year),
    )
    if department_id:
        q = q.filter_by(department_id=department_id)
    if program_id:
        q = q.filter_by(program_id=program_id)
    if academic_year_id:
        q = q.filter_by(academic_year_id=academic_year_id)
    if semester:
        q = q.filter_by(semester=semester)
    if status:
        q = q.filter_by(status=status)
    if university_id:
        q = q.join(Timetable.department).filter(Department.university_id == university_id)
    return q.order_by(Timetable.created_at.desc()).all()


def swap_entries(entry1_id: str, entry2_id: str, triggered_by: str | None = None) -> tuple:
    load_opts = (
        joinedload(TimetableEntry.course),
        joinedload(TimetableEntry.time_slot),
        joinedload(TimetableEntry.room),
        joinedload(TimetableEntry.lecturer),
    )
    e1 = TimetableEntry.query.options(*load_opts).get(entry1_id)
    e2 = TimetableEntry.query.options(*load_opts).get(entry2_id)
    if not e1 or not e2:
        raise ValueError("One or both entries not found.")
    if e1.timetable_id != e2.timetable_id:
        raise ValueError("Entries must belong to the same timetable.")
    if e1.is_locked or e2.is_locked:
        raise ValueError("Cannot move locked entries.")

    from app.services.timetable_events import change_from_entry, slot_payload, base_event
    from app.services.notification_client import emit_timetable_event

    old_slot_e1 = slot_payload(e1)
    old_slot_e2 = slot_payload(e2)

    e1.time_slot_id, e2.time_slot_id = e2.time_slot_id, e1.time_slot_id
    db.session.commit()

    db.session.refresh(e1)
    db.session.refresh(e2)
    timetable = Timetable.query.get(e1.timetable_id)
    if timetable:
        emit_timetable_event(base_event(
            timetable,
            "entry_swapped",
            triggered_by=triggered_by,
            changes=[
                change_from_entry(e1, old_slot=old_slot_e1),
                change_from_entry(e2, old_slot=old_slot_e2),
            ],
        ))
    return e1, e2


def move_entry_to_slot(entry_id: str, time_slot_id: str, triggered_by: str | None = None) -> TimetableEntry:
    entry = (
        TimetableEntry.query
        .options(
            joinedload(TimetableEntry.course),
            joinedload(TimetableEntry.time_slot),
            joinedload(TimetableEntry.room),
            joinedload(TimetableEntry.lecturer),
        )
        .get(entry_id)
    )
    if not entry:
        raise ValueError("Entry not found.")
    if entry.is_locked:
        raise ValueError("Cannot move locked entry.")

    slot = TimeSlot.query.get(time_slot_id)
    if not slot:
        raise ValueError("Time slot not found.")
    if slot.slot_type in ("break", "lunch") or slot.is_break:
        raise ValueError("Cannot move a class into a break or lunch slot.")

    if entry.time_slot_id == time_slot_id:
        return entry

    from app.services.timetable_events import change_from_entry, slot_payload, base_event
    from app.services.notification_client import emit_timetable_event

    old_slot = slot_payload(entry)

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
        if o.student_group_id and o.student_group_id == entry.student_group_id:
            raise ValueError("Student group already has a class in the target time slot.")

    # Lecturer availability check for the target slot
    if entry.lecturer_id:
        lec = Lecturer.query.get(entry.lecturer_id)
        if lec and time_slot_id in (lec.unavailable_slots or []):
            raise ValueError(
                f"Lecturer '{lec.name}' has marked this time slot as unavailable."
            )

    entry.time_slot_id = time_slot_id
    timetable = Timetable.query.get(timetable_id)
    if timetable:
        timetable.version = (timetable.version or 1) + 1
    db.session.commit()
    entry = (
        TimetableEntry.query
        .options(
            joinedload(TimetableEntry.course),
            joinedload(TimetableEntry.time_slot),
            joinedload(TimetableEntry.room),
            joinedload(TimetableEntry.lecturer),
        )
        .get(entry_id)
    )
    if timetable:
        emit_timetable_event(base_event(
            timetable,
            "entry_moved",
            triggered_by=triggered_by,
            changes=[change_from_entry(entry, old_slot=old_slot)],
        ))
    return entry


def detect_conflicts(timetable_id: str) -> list[dict]:
    entries = (
        TimetableEntry.query
        .options(
            joinedload(TimetableEntry.time_slot),
            joinedload(TimetableEntry.course),
            joinedload(TimetableEntry.lecturer),
            joinedload(TimetableEntry.room),
            joinedload(TimetableEntry.student_group),
        )
        .filter_by(timetable_id=timetable_id)
        .all()
    )
    conflicts = []
    seen_lec: dict = {}
    seen_room: dict = {}
    seen_grp: dict = {}

    for e in entries:
        slot_label = (
            f"{e.time_slot.day} {e.time_slot.start_time}"
            if e.time_slot else e.time_slot_id
        )

        if e.lecturer_id:
            key = f"{e.lecturer_id}:{e.time_slot_id}"
            if key in seen_lec:
                conflicts.append({
                    "type": "lecturer_clash",
                    "severity": "high",
                    "rule": "H1 — Lecturer double-booked",
                    "message": f"Lecturer '{e.lecturer.name if e.lecturer else e.lecturer_id}' double-booked at {slot_label}",
                    "entry1": seen_lec[key], "entry2": e.id,
                })
            else:
                seen_lec[key] = e.id

        if e.room_id:
            key = f"{e.room_id}:{e.time_slot_id}"
            if key in seen_room:
                conflicts.append({
                    "type": "room_clash",
                    "severity": "high",
                    "rule": "H2 — Room double-booked",
                    "message": f"Room '{e.room.code if e.room else e.room_id}' double-booked at {slot_label}",
                    "entry1": seen_room[key], "entry2": e.id,
                })
            else:
                seen_room[key] = e.id

        if e.student_group_id:
            key = f"{e.student_group_id}:{e.time_slot_id}"
            if key in seen_grp:
                conflicts.append({
                    "type": "student_group_clash",
                    "severity": "high",
                    "rule": "H7 — Student group double-booked",
                    "message": f"Student group '{e.student_group.name if e.student_group else e.student_group_id}' has two classes at {slot_label}",
                    "entry1": seen_grp[key], "entry2": e.id,
                })
            else:
                seen_grp[key] = e.id

        # Extra: class in break slot
        if e.time_slot and (e.time_slot.is_break or e.time_slot.slot_type in ("break", "lunch")):
            conflicts.append({
                "type": "break_slot_violation",
                "severity": "high",
                "rule": "H6 — Class in break/lunch slot",
                "message": f"{e.course.name if e.course else 'Unknown'} scheduled in a break period at {slot_label}",
                "entry1": e.id, "entry2": None,
            })

    return conflicts


def get_violation_report(timetable_id: str) -> list[dict]:
    """Return the stored violation report from last GA run."""
    tt = Timetable.query.get(timetable_id)
    if not tt:
        return []
    return tt.violation_report or []


def list_entries(timetable_id: str | None = None, day: str | None = None):
    q = (
        TimetableEntry.query
        .options(
            joinedload(TimetableEntry.room),
            joinedload(TimetableEntry.time_slot),
            joinedload(TimetableEntry.student_group),
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

    # Room capacity pressure
    for entry in entries:
        if entry.course and entry.room:
            overflow = entry.course.student_count - entry.room.capacity
            if overflow > 0:
                predictions.append({
                    "type": "capacity_risk", "severity": "high",
                    "entry_id": entry.id,
                    "message": f"{entry.course.code} exceeds room capacity by {overflow} students.",
                })

    # Consecutive lecturer overload
    from collections import defaultdict
    by_lec_day: dict[tuple, list] = defaultdict(list)
    lec_names = {
        e.lecturer_id: e.lecturer.name
        for e in entries if e.lecturer_id and e.lecturer
    }
    for entry in entries:
        if entry.lecturer_id and entry.time_slot:
            by_lec_day[(entry.lecturer_id, entry.time_slot.day)].append(
                entry.time_slot.slot_index or 0
            )

    for (lec_id, day), idxs in by_lec_day.items():
        sorted_idxs = sorted(idxs)
        streak = max_streak = 1
        for i in range(1, len(sorted_idxs)):
            if sorted_idxs[i] == sorted_idxs[i - 1] + 1:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 1
        if max_streak >= 4:
            predictions.append({
                "type": "lecturer_workload_risk", "severity": "medium",
                "lecturer_id": lec_id,
                "message": f"{lec_names.get(lec_id, lec_id)} has {max_streak} consecutive periods on {day}.",
            })

    # Peak-hour density
    occupancy: dict[str, int] = {}
    for entry in entries:
        if entry.time_slot:
            key = f"{entry.time_slot.day} {entry.time_slot.start_time}"
            occupancy[key] = occupancy.get(key, 0) + 1
    if occupancy:
        max_occ = max(occupancy.values())
        for key, count in occupancy.items():
            if max_occ >= 4 and count == max_occ:
                predictions.append({
                    "type": "peak_hour_risk", "severity": "low",
                    "message": f"Peak congestion at {key} ({count} classes in parallel).",
                })

    return predictions


def create_snapshot(timetable_id: str, created_by: str | None, notes: str = "") -> TimetableSnapshot:
    timetable = Timetable.query.get(timetable_id)
    if not timetable:
        raise ValueError("Timetable not found.")

    snapshot_data = [
        {
            "course_id": e.course_id,
            "lecturer_id": e.lecturer_id,
            "room_id": e.room_id,
            "time_slot_id": e.time_slot_id,
            "student_group_id": e.student_group_id,
            "is_locked": e.is_locked,
            "notes": e.notes,
        }
        for e in timetable.entries
    ]

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
        db.session.add(TimetableEntry(
            timetable_id=timetable.id,
            course_id=row["course_id"],
            lecturer_id=row["lecturer_id"],
            room_id=row["room_id"],
            time_slot_id=row["time_slot_id"],
            student_group_id=row.get("student_group_id"),
            is_locked=row.get("is_locked", False),
            notes=row.get("notes"),
        ))

    timetable.version = (timetable.version or 1) + 1
    db.session.commit()

    from app.services.notification_client import emit_timetable_event
    from app.services.timetable_events import base_event
    emit_timetable_event(base_event(
        timetable,
        "restored",
        changes=[{"snapshot_id": snapshot.id, "snapshot_notes": snapshot.notes}],
    ))
    return timetable


def seed_default_slots(template_id: str | None = None):
    """Create a standard Mon–Fri timetable grid using structured slot_types."""
    if TimeSlot.query.count() > 0:
        return

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    schedule = [
        ("08:00", "09:00", "class",  "Period 1"),
        ("09:00", "10:00", "class",  "Period 2"),
        ("10:00", "10:30", "break",  "Morning Break"),
        ("10:30", "11:30", "class",  "Period 3"),
        ("11:30", "12:30", "class",  "Period 4"),
        ("12:30", "13:30", "lunch",  "Lunch Break"),
        ("13:30", "14:30", "class",  "Period 5"),
        ("14:30", "15:30", "class",  "Period 6"),
        ("15:30", "16:30", "class",  "Period 7"),
        ("16:30", "17:00", "class",  "Period 8"),
    ]
    idx = 0
    for day in days:
        for start, end, stype, label in schedule:
            db.session.add(TimeSlot(
                day=day,
                start_time=start,
                end_time=end,
                slot_index=idx,
                is_break=(stype in ("break", "lunch")),
                slot_type=stype,
                label=label,
                template_id=template_id,
            ))
            idx += 1
    db.session.commit()

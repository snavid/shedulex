"""
Population initialisation — creates a smart but structurally valid initial population.

Improvements over the naive random version:
  • Filters out break/lunch slots (slot_type != 'class'/'lab') upfront.
  • Respects lecturer availability when selecting slots (heuristic-guided, not hard-forced).
  • Sorts courses by priority descending so high-priority courses get the first crack at slots.
  • Lab courses are pre-assigned to lab rooms; lecture courses to non-lab rooms.
  • Builds a per-lecturer used-slot cache to reduce initialization-level clashes.
  • Respects DB constraints: room department access, blocked slots, fixed sessions.
"""
from __future__ import annotations
import random
from collections import defaultdict
from app.ga.chromosome import Chromosome, Gene
from app.ga.constraint_index import ConstraintIndex


def _eligible_slots(slots: list[dict], lab_ok: bool = False) -> list[dict]:
    """Return schedulable (non-break, non-lunch) slots, optionally only lab-eligible ones."""
    types = {"class", "lab"} if lab_ok else {"class"}
    types.add("class")  # always include generic class slots
    return [s for s in slots if s.get("slot_type", "class") in types
            and not s.get("is_break", False)]


def initialize_population(
    size: int,
    courses: list[dict],
    rooms: list[dict],
    slots: list[dict],
    lecturers: dict | None = None,
    external_bookings: dict | None = None,
    generating_department_id: str | None = None,
    constraint_index: ConstraintIndex | None = None,
    building_id: str | None = None,
) -> list[Chromosome]:
    """
    courses:  list of dicts with keys id, weekly_hours, requires_lab, lecturer_id, priority
    rooms:    list of room dicts (id, room_type, capacity)
    slots:    list of slot dicts (id, day, slot_index, is_break, slot_type)
    lecturers: optional dict[lec_id → {availability, preferred_days, unavailable_slots}]
    external_bookings: optional {room: {(room_id, day, start, end): [meta]},
                                  lecturer: {(lec_id, day, start, end): [meta]}}
    """
    lecturers = lecturers or {}
    external_bookings = external_bookings or {"room": {}, "lecturer": {}}
    idx = constraint_index or ConstraintIndex()
    dept_id = generating_department_id or ""

    # Build wall-clock → slot_id index for resolving external booking keys
    wallclock_to_slot: dict[tuple, str] = {}
    for s in slots:
        day, st, en = s.get("day"), s.get("start_time"), s.get("end_time")
        if day and st and en:
            wallclock_to_slot[(day, st, en)] = s["id"]
    room_busy_slots: dict[str, set] = defaultdict(set)
    for (room_id, d, st, en) in external_bookings.get("room", {}):
        sid = wallclock_to_slot.get((d, st, en))
        if sid:
            room_busy_slots[room_id].add(sid)
    lec_busy_slots: dict[str, set] = defaultdict(set)
    for (lec_id, d, st, en) in external_bookings.get("lecturer", {}):
        sid = wallclock_to_slot.get((d, st, en))
        if sid:
            lec_busy_slots[lec_id].add(sid)

    dept_rooms = idx.rooms_for_department(rooms, dept_id) if dept_id else rooms
    lab_rooms = [r for r in dept_rooms if r.get("room_type") == "lab"]
    non_lab_rooms = [r for r in dept_rooms if r.get("room_type") != "lab"]
    all_rooms = dept_rooms if dept_rooms else rooms

    schedulable_slots = _eligible_slots(slots)
    if not schedulable_slots:
        schedulable_slots = [s for s in slots if not s.get("is_break", False)] or slots

    sorted_courses = sorted(courses, key=lambda c: c.get("priority") or 1, reverse=True)

    def _lec_preferred_slots(lec_id: str, course_id: str = "") -> list[dict]:
        """Return slot subset matching lecturer availability + DB blocked slots."""
        blocked = idx.blocked_slots_for_lecturer(lec_id)
        if course_id:
            blocked = blocked | idx.blocked_slots_for_course(course_id)

        if lec_id not in lecturers:
            base = [s for s in schedulable_slots if s["id"] not in blocked]
            return base if base else schedulable_slots

        lec = lecturers[lec_id]
        avail: dict = lec.get("availability", {})
        unavail: list = lec.get("unavailable_slots", [])
        pref_days: list = lec.get("preferred_days", [])
        all_blocked = set(unavail) | blocked

        if avail:
            allowed_ids: set[str] = set()
            for day_slots in avail.values():
                allowed_ids.update(day_slots)
            candidates = [s for s in schedulable_slots if s["id"] in allowed_ids]
        else:
            candidates = [s for s in schedulable_slots if s["id"] not in all_blocked]

        if all_blocked:
            candidates = [s for s in candidates if s["id"] not in all_blocked]

        if pref_days:
            pref_candidates = [s for s in candidates if s.get("day") in pref_days]
            if pref_candidates:
                return pref_candidates if random.random() < 0.7 else candidates

        return candidates if candidates else schedulable_slots

    scheduling_units: list[dict] = []
    for course in sorted_courses:
        group_ids: list[str] = course.get("student_group_ids") or []
        per_group_lec: dict[str, str] = course.get("per_group_lecturer_ids") or {}
        if group_ids:
            for gid in group_ids:
                unit = {**course, "student_group_id": gid}
                if per_group_lec.get(gid):
                    unit["lecturer_id"] = per_group_lec[gid]
                scheduling_units.append(unit)
        else:
            scheduling_units.append(course)

    population: list[Chromosome] = []

    for _ in range(size):
        genes: list[Gene] = []
        lec_used: dict[str, list[str]] = {}
        group_used: dict[str, list[str]] = {}

        for unit in scheduling_units:
            sessions = max(1, unit.get("weekly_hours", 1))
            lec_id = unit.get("lecturer_id", "")
            group_id = unit.get("student_group_id", "")
            course_id = unit["id"]
            unit_dept = unit.get("department_id") or dept_id
            fixed_slot = idx.fixed_session(course_id)

            fixed_room_id = unit.get("fixed_room_id")
            required_type = unit.get("required_room_type")

            if fixed_room_id:
                # Unrestricted, raw room list — guaranteed to contain the fixed
                # room regardless of department/type pre-filtering, so the
                # eligible_ids intersection below can never wipe it out.
                room_pool = rooms
            elif required_type == "lab" or unit.get("requires_lab"):
                room_pool = lab_rooms if lab_rooms else all_rooms
            elif required_type:
                typed_rooms = [r for r in all_rooms if r.get("room_type") == required_type]
                room_pool = typed_rooms if typed_rooms else all_rooms
            elif non_lab_rooms:
                room_pool = non_lab_rooms
            else:
                room_pool = all_rooms

            slot_pool = _lec_preferred_slots(lec_id, course_id)

            if lec_id not in lec_used:
                lec_used[lec_id] = []
            if group_id and group_id not in group_used:
                group_used[group_id] = []

            for session_idx in range(sessions):
                busy = set(lec_used.get(lec_id, []))
                if group_id:
                    busy |= set(group_used.get(group_id, []))
                busy |= lec_busy_slots.get(lec_id, set())

                if fixed_slot and fixed_slot not in busy:
                    chosen_slot = next(
                        (s for s in slot_pool if s["id"] == fixed_slot),
                        next((s for s in schedulable_slots if s["id"] == fixed_slot), None),
                    )
                    if chosen_slot is None:
                        unused = [s for s in slot_pool if s["id"] not in busy]
                        chosen_slot = random.choice(unused) if unused else random.choice(slot_pool)
                else:
                    unused = [s for s in slot_pool if s["id"] not in busy]
                    chosen_slot = (
                        random.choice(unused)
                        if unused
                        else random.choice(slot_pool)
                    )

                slot_id_chosen = chosen_slot["id"]
                eligible_ids = idx.eligible_room_ids_for_gene(
                    rooms, unit_dept,
                    requires_lab=bool(unit.get("requires_lab")),
                    required_room_type=required_type,
                    fixed_room_id=fixed_room_id,
                    building_id=building_id,
                    slot_id=slot_id_chosen,
                    room_busy_slots=room_busy_slots,
                )
                eligible_in_pool = [r for r in room_pool if r["id"] in eligible_ids]
                if eligible_in_pool:
                    pick_from = eligible_in_pool
                else:
                    pick_from = [r for r in all_rooms if r["id"] in eligible_ids] or room_pool
                chosen_room = random.choice(pick_from)

                lec_used.setdefault(lec_id, []).append(chosen_slot["id"])
                if group_id:
                    group_used.setdefault(group_id, []).append(chosen_slot["id"])

                genes.append(Gene(
                    course_id=course_id,
                    session_index=session_idx,
                    room_id=chosen_room["id"],
                    time_slot_id=chosen_slot["id"],
                    student_group_id=group_id,
                ))

        population.append(Chromosome(genes=genes))

    return population

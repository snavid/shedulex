"""
Population initialisation — creates a smart but structurally valid initial population.

Improvements over the naive random version:
  • Filters out break/lunch slots (slot_type != 'class'/'lab') upfront.
  • Respects lecturer availability when selecting slots (heuristic-guided, not hard-forced).
  • Sorts courses by priority descending so high-priority courses get the first crack at slots.
  • Lab courses are pre-assigned to lab rooms; lecture courses to non-lab rooms.
  • Builds a per-lecturer used-slot cache to reduce initialization-level clashes.
"""
from __future__ import annotations
import random
from collections import defaultdict
from app.ga.chromosome import Chromosome, Gene


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

    # Build wall-clock → slot_id index for resolving external booking keys
    wallclock_to_slot: dict[tuple, str] = {
        (s["day"], s["start_time"], s["end_time"]): s["id"] for s in slots
    }
    # room_id → set of slot_ids already taken by other departments
    room_busy_slots: dict[str, set] = defaultdict(set)
    for (room_id, d, st, en) in external_bookings.get("room", {}):
        sid = wallclock_to_slot.get((d, st, en))
        if sid:
            room_busy_slots[room_id].add(sid)
    # lec_id → set of slot_ids already taken by other departments
    lec_busy_slots: dict[str, set] = defaultdict(set)
    for (lec_id, d, st, en) in external_bookings.get("lecturer", {}):
        sid = wallclock_to_slot.get((d, st, en))
        if sid:
            lec_busy_slots[lec_id].add(sid)

    lab_rooms = [r for r in rooms if r.get("room_type") == "lab"]
    non_lab_rooms = [r for r in rooms if r.get("room_type") != "lab"]
    all_rooms = rooms

    schedulable_slots = _eligible_slots(slots)
    if not schedulable_slots:
        schedulable_slots = [s for s in slots if not s.get("is_break", False)] or slots

    # Sort courses by priority descending (higher = scheduled first, less conflict risk)
    sorted_courses = sorted(courses, key=lambda c: c.get("priority", 1), reverse=True)

    # Pre-bucket slots by day for each lecturer based on availability
    def _lec_preferred_slots(lec_id: str) -> list[dict]:
        """Return slot subset matching lecturer availability + preferred days if configured."""
        if lec_id not in lecturers:
            return schedulable_slots
        lec = lecturers[lec_id]
        avail: dict = lec.get("availability", {})
        unavail: list = lec.get("unavailable_slots", [])
        pref_days: list = lec.get("preferred_days", [])

        # Build allowed set
        if avail:
            allowed_ids: set[str] = set()
            for day_slots in avail.values():
                allowed_ids.update(day_slots)
            candidates = [s for s in schedulable_slots if s["id"] in allowed_ids]
        else:
            candidates = [s for s in schedulable_slots if s["id"] not in unavail]

        # Remove explicitly unavailable
        if unavail:
            candidates = [s for s in candidates if s["id"] not in unavail]

        # Prefer matching days with some probability
        if pref_days:
            pref_candidates = [s for s in candidates if s.get("day") in pref_days]
            if pref_candidates:
                # 70 % chance to draw from preferred, 30 % from all eligible
                return pref_candidates if random.random() < 0.7 else candidates

        return candidates if candidates else schedulable_slots

    # Expand courses into (course, group) scheduling units.
    # If a course has explicit student_group_ids, create one unit per group.
    # If not, create one unit with the pre-resolved student_group_id (may be empty).
    # per_group_lecturer_ids overrides lecturer_id per unit so fitness evaluation
    # uses the correct lecturer's availability constraints for each group.
    scheduling_units: list[dict] = []
    for course in sorted_courses:
        group_ids: list[str] = course.get("student_group_ids") or []
        per_group_lec: dict[str, str] = course.get("per_group_lecturer_ids") or {}
        if group_ids:
            for gid in group_ids:
                unit = {**course, "student_group_id": gid}
                # Inject the effective lecturer so fitness.py checks the right constraints
                if per_group_lec.get(gid):
                    unit["lecturer_id"] = per_group_lec[gid]
                scheduling_units.append(unit)
        else:
            scheduling_units.append(course)

    population: list[Chromosome] = []

    for _ in range(size):
        genes: list[Gene] = []
        lec_used: dict[str, list[str]] = {}  # lec_id → [slot_ids used so far]
        group_used: dict[str, list[str]] = {}  # group_id → [slot_ids used so far]

        for unit in scheduling_units:
            sessions = max(1, unit.get("weekly_hours", 1))
            lec_id = unit.get("lecturer_id", "")
            group_id = unit.get("student_group_id", "")

            # Pick room pool
            if unit.get("requires_lab") and lab_rooms:
                room_pool = lab_rooms
            elif non_lab_rooms:
                room_pool = non_lab_rooms
            else:
                room_pool = all_rooms

            # Pick slot pool guided by availability
            slot_pool = _lec_preferred_slots(lec_id)

            if lec_id not in lec_used:
                lec_used[lec_id] = []
            if group_id and group_id not in group_used:
                group_used[group_id] = []

            for session_idx in range(sessions):
                # Avoid slots already used by this lecturer, this group, or by another dept
                busy = set(lec_used[lec_id])
                if group_id:
                    busy |= set(group_used[group_id])
                # Also exclude slots blocked by other departments for this lecturer
                busy |= lec_busy_slots.get(lec_id, set())
                unused = [s for s in slot_pool if s["id"] not in busy]
                chosen_slot = (
                    random.choice(unused)
                    if unused
                    else random.choice(slot_pool)
                )

                # Prefer a room not already booked externally for this slot
                slot_id_chosen = chosen_slot["id"]
                free_rooms = [
                    r for r in room_pool
                    if slot_id_chosen not in room_busy_slots.get(r["id"], set())
                ]
                chosen_room = random.choice(free_rooms) if free_rooms else random.choice(room_pool)

                lec_used[lec_id].append(chosen_slot["id"])
                if group_id:
                    group_used[group_id].append(chosen_slot["id"])

                genes.append(Gene(
                    course_id=unit["id"],
                    session_index=session_idx,
                    room_id=chosen_room["id"],
                    time_slot_id=chosen_slot["id"],
                    student_group_id=group_id,
                ))

        population.append(Chromosome(genes=genes))

    return population

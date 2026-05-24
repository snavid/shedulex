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
) -> list[Chromosome]:
    """
    courses:  list of dicts with keys id, weekly_hours, requires_lab, lecturer_id, priority
    rooms:    list of room dicts (id, room_type, capacity)
    slots:    list of slot dicts (id, day, slot_index, is_break, slot_type)
    lecturers: optional dict[lec_id → {availability, preferred_days, unavailable_slots}]
    """
    lecturers = lecturers or {}

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
    scheduling_units: list[dict] = []
    for course in sorted_courses:
        group_ids: list[str] = course.get("student_group_ids") or []
        if group_ids:
            for gid in group_ids:
                scheduling_units.append({**course, "student_group_id": gid})
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
                # Avoid slots already used by this lecturer or this group
                busy = set(lec_used[lec_id])
                if group_id:
                    busy |= set(group_used[group_id])
                unused = [s for s in slot_pool if s["id"] not in busy]
                chosen_slot = (
                    random.choice(unused)
                    if unused
                    else random.choice(slot_pool)
                )
                chosen_room = random.choice(room_pool)

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

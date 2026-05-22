"""
Multi-objective fitness function for the timetable genetic algorithm.

Hard constraints (violation → heavy penalty, cannot be optimised away):
  H1 – No lecturer teaches two classes at the same time
  H2 – No room hosts two classes at the same time
  H3 – Room capacity must not be exceeded
  H4 – Lab courses must be assigned lab rooms
  H5 – Courses must only appear in lecturer's available slots
  H6 – No classes scheduled in break/lunch slots
  H7 – Student group must not have two classes at the same time
  H8 – Lecturer daily hours must not exceed max_hours_per_day
  H9 – Explicitly unavailable slots must not be used for a lecturer

Soft constraints (violation → proportional penalty scaled by weight):
  S1 – Prefer no consecutive lectures for a lecturer (> max_consecutive_hours)
  S2 – Distribute lectures evenly across days
  S3 – Respect department / lecturer preferred times
  S4 – Minimise gaps in student-group daily schedules
  S5 – Balance room utilisation across available rooms
  S6 – Prefer lecturer preferred days when specified
  S7 – Exam-gap: avoid scheduling classes immediately before exam blocks
  S8 – DB-driven soft constraints (rule_type routing)
"""
from __future__ import annotations
from collections import defaultdict
from app.ga.chromosome import Chromosome

HARD_PENALTY = 1000.0
SOFT_WEIGHTS = {
    "consecutive": 60.0,
    "distribution": 30.0,
    "dept_preference": 25.0,
    "student_gaps": 45.0,
    "room_balance": 15.0,
    "preferred_days": 20.0,
    "exam_gap": 35.0,
    "max_weekly": 80.0,
}


def _slots_per_day(slot_ids: list[str], slots: dict) -> dict[str, list[int]]:
    """Return {day: [sorted slot_indexes]} for the given list of slot IDs."""
    by_day: dict[str, list[int]] = defaultdict(list)
    for sid in slot_ids:
        s = slots.get(sid, {})
        if s:
            by_day[s["day"]].append(s.get("slot_index", 0))
    for day in by_day:
        by_day[day].sort()
    return dict(by_day)


def _consecutive_run(indexes: list[int]) -> int:
    """Return the length of the longest consecutive run in a sorted index list."""
    if not indexes:
        return 0
    max_run = run = 1
    for i in range(1, len(indexes)):
        if indexes[i] == indexes[i - 1] + 1:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    return max_run


def evaluate(chromosome: Chromosome, context: dict) -> float:
    """
    Returns a fitness score ∈ [0, 1] where 1.0 = perfect schedule.
    Accepts an optional 'db_constraints' list in context for DB-driven rules.
    """
    penalty = 0.0

    courses = context["courses"]
    rooms = context["rooms"]
    slots = context["slots"]
    lecturers = context["lecturers"]
    db_constraints: list[dict] = context.get("db_constraints", [])

    # ── Build lookup indices ──────────────────────────────────────────────────
    # slot_key → [course_id]
    lec_slot_map: dict[str, list[str]] = defaultdict(list)   # "{lec}:{slot}" → courses
    room_slot_map: dict[str, list[str]] = defaultdict(list)  # "{room}:{slot}" → courses
    group_slot_map: dict[str, list[str]] = defaultdict(list) # "{grp}:{slot}" → courses
    lec_slots: dict[str, list[str]] = defaultdict(list)      # lec_id → [slot_ids]
    lec_day_slots: dict[tuple, list[str]] = defaultdict(list) # (lec_id, day) → [slot_ids]
    dept_day_count: dict[tuple, int] = defaultdict(int)       # (dept_id, day) → count
    group_day_slots: dict[tuple, list[int]] = defaultdict(list)  # (grp_id, day) → [indexes]
    room_usage: dict[str, int] = defaultdict(int)            # room_id → usage count

    for gene in chromosome.genes:
        course = courses.get(gene.course_id, {})
        room = rooms.get(gene.room_id, {})
        slot = slots.get(gene.time_slot_id, {})
        lec_id = course.get("lecturer_id", "")
        grp_id = course.get("student_group_id", "")
        slot_day = slot.get("day", "")
        slot_idx = slot.get("slot_index", 0)
        slot_type = slot.get("slot_type", "class")

        # H1 – Lecturer double-booking
        if lec_id:
            key = f"{lec_id}:{gene.time_slot_id}"
            lec_slot_map[key].append(gene.course_id)
            if len(lec_slot_map[key]) > 1:
                penalty += HARD_PENALTY

        # H2 – Room double-booking
        rkey = f"{gene.room_id}:{gene.time_slot_id}"
        room_slot_map[rkey].append(gene.course_id)
        if len(room_slot_map[rkey]) > 1:
            penalty += HARD_PENALTY

        # H3 – Room capacity
        if room and course:
            if room.get("capacity", 0) < course.get("student_count", 0):
                penalty += HARD_PENALTY

        # H4 – Lab requirement
        if course.get("requires_lab") and room.get("room_type") != "lab":
            penalty += HARD_PENALTY

        # H5 – Lecturer availability (day-level from availability dict)
        if lec_id and lecturers.get(lec_id):
            lec_info = lecturers[lec_id]
            availability = lec_info.get("availability", {})
            if availability and slot_day:
                allowed = availability.get(slot_day, [])
                if allowed and gene.time_slot_id not in allowed:
                    penalty += HARD_PENALTY

        # H6 – No classes in break/lunch slots
        if slot_type in ("break", "lunch") or slot.get("is_break"):
            penalty += HARD_PENALTY

        # H7 – Student group double-booking
        if grp_id:
            gkey = f"{grp_id}:{gene.time_slot_id}"
            group_slot_map[gkey].append(gene.course_id)
            if len(group_slot_map[gkey]) > 1:
                penalty += HARD_PENALTY

        # H9 – Explicitly unavailable slots for lecturer
        if lec_id and lecturers.get(lec_id):
            unavailable = lecturers[lec_id].get("unavailable_slots", [])
            if gene.time_slot_id in unavailable:
                penalty += HARD_PENALTY

        # Accumulate for soft constraint analysis
        if lec_id:
            lec_slots[lec_id].append(gene.time_slot_id)
            if slot_day:
                lec_day_slots[(lec_id, slot_day)].append(gene.time_slot_id)

        if grp_id and slot_day:
            group_day_slots[(grp_id, slot_day)].append(slot_idx)

        dept_id = course.get("department_id", "")
        if dept_id and slot_day:
            dept_day_count[(dept_id, slot_day)] += 1

        room_usage[gene.room_id] += 1

    # ── H8 – Lecturer daily hours ────────────────────────────────────────────
    for (lec_id, day), day_slot_ids in lec_day_slots.items():
        hours = len(day_slot_ids)
        lec_info = lecturers.get(lec_id, {})
        max_day = lec_info.get("max_hours_per_day", 6)
        if hours > max_day:
            penalty += HARD_PENALTY * (hours - max_day)

    # ── Soft: Weekly hours ───────────────────────────────────────────────────
    for lec_id, all_slots in lec_slots.items():
        lec_info = lecturers.get(lec_id, {})
        max_week = lec_info.get("max_hours_per_week", 20)
        hours = len(all_slots)
        if hours > max_week:
            penalty += SOFT_WEIGHTS["max_weekly"] * (hours - max_week)

    # ── S1 – Consecutive lectures ────────────────────────────────────────────
    for lec_id, all_slots in lec_slots.items():
        lec_info = lecturers.get(lec_id, {})
        max_consec = lec_info.get("max_consecutive_hours", 3)
        by_day = _slots_per_day(all_slots, slots)
        for day_idxs in by_day.values():
            run = _consecutive_run(day_idxs)
            if run > max_consec:
                penalty += SOFT_WEIGHTS["consecutive"] * (run - max_consec)

    # ── S2 – Even distribution across days ──────────────────────────────────
    for dept_id in {d for d, _ in dept_day_count}:
        counts = [dept_day_count[(dept_id, d)]
                  for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                  if (dept_id, d) in dept_day_count]
        if len(counts) > 1:
            avg = sum(counts) / len(counts)
            variance = sum((c - avg) ** 2 for c in counts) / len(counts)
            penalty += variance * SOFT_WEIGHTS["distribution"] * 0.1

    # ── S4 – Student-group schedule gaps ────────────────────────────────────
    for (grp_id, day), idxs in group_day_slots.items():
        idxs_sorted = sorted(idxs)
        if len(idxs_sorted) > 1:
            gaps = sum(
                max(0, idxs_sorted[i] - idxs_sorted[i - 1] - 1)
                for i in range(1, len(idxs_sorted))
            )
            penalty += gaps * SOFT_WEIGHTS["student_gaps"] * 0.5

    # ── S5 – Room utilisation balance ───────────────────────────────────────
    if room_usage:
        avg_usage = sum(room_usage.values()) / len(room_usage)
        variance = sum((v - avg_usage) ** 2 for v in room_usage.values()) / len(room_usage)
        penalty += variance * SOFT_WEIGHTS["room_balance"] * 0.01

    # ── S6 – Lecturer preferred days ────────────────────────────────────────
    for gene in chromosome.genes:
        course = courses.get(gene.course_id, {})
        lec_id = course.get("lecturer_id", "")
        if lec_id and lecturers.get(lec_id):
            pref_days = lecturers[lec_id].get("preferred_days", [])
            if pref_days:
                slot = slots.get(gene.time_slot_id, {})
                if slot.get("day") not in pref_days:
                    penalty += SOFT_WEIGHTS["preferred_days"]

    # ── DB-driven constraint routing ─────────────────────────────────────────
    for c in db_constraints:
        if not c.get("is_active"):
            continue
        rule = c.get("rule_type", "")
        cfg = c.get("config", {})
        weight = float(c.get("weight", 1.0))
        eid = c.get("entity_id")
        etype = c.get("entity_type", "")

        if rule == "max_consecutive" and etype == "lecturer":
            lim = int(cfg.get("limit", 3))
            lec_info = lecturers.get(eid, {})
            if lec_info and eid in lec_slots:
                by_day = _slots_per_day(lec_slots[eid], slots)
                for day_idxs in by_day.values():
                    run = _consecutive_run(day_idxs)
                    if run > lim:
                        penalty += weight * 50.0 * (run - lim)

        elif rule == "max_daily_hours" and etype == "lecturer":
            lim = int(cfg.get("limit", 6))
            for (lec_id, _), day_s in lec_day_slots.items():
                if lec_id == eid and len(day_s) > lim:
                    penalty += weight * HARD_PENALTY * (len(day_s) - lim)

        elif rule == "preferred_times" and etype == "lecturer":
            preferred_slot_ids = set(cfg.get("slot_ids", []))
            if preferred_slot_ids and eid:
                for gene in chromosome.genes:
                    c_data = courses.get(gene.course_id, {})
                    if c_data.get("lecturer_id") == eid:
                        if gene.time_slot_id not in preferred_slot_ids:
                            penalty += weight * 20.0

        elif rule == "exam_gap":
            exam_slot_ids = set(cfg.get("exam_slot_ids", []))
            gap = int(cfg.get("min_gap_slots", 2))
            for gene in chromosome.genes:
                slot_idx = slots.get(gene.time_slot_id, {}).get("slot_index", -1)
                slot_day = slots.get(gene.time_slot_id, {}).get("day", "")
                for exam_sid in exam_slot_ids:
                    exam_slot = slots.get(exam_sid, {})
                    if exam_slot.get("day") == slot_day:
                        dist = abs(slot_idx - exam_slot.get("slot_index", -1))
                        if 0 < dist <= gap:
                            penalty += weight * SOFT_WEIGHTS["exam_gap"]

    # ── Normalise ─────────────────────────────────────────────────────────────
    n = max(1, len(chromosome.genes))
    # Worst-case: every gene triggers every hard constraint
    worst = n * HARD_PENALTY * 5
    fitness = max(0.0, 1.0 - (penalty / worst))
    return round(fitness, 6)


def violation_report(chromosome: Chromosome, context: dict) -> list[dict]:
    """
    Returns a human-readable list of constraint violations for display in the UI.
    Called once after GA completion on the best chromosome.
    """
    violations: list[dict] = []

    courses = context["courses"]
    rooms = context["rooms"]
    slots = context["slots"]
    lecturers = context["lecturers"]

    lec_slot_map: dict[str, list] = defaultdict(list)
    room_slot_map: dict[str, list] = defaultdict(list)
    group_slot_map: dict[str, list] = defaultdict(list)
    lec_day_count: dict[tuple, int] = defaultdict(int)

    for gene in chromosome.genes:
        course = courses.get(gene.course_id, {})
        room = rooms.get(gene.room_id, {})
        slot = slots.get(gene.time_slot_id, {})
        lec_id = course.get("lecturer_id", "")
        grp_id = course.get("student_group_id", "")
        slot_day = slot.get("day", "")
        slot_type = slot.get("slot_type", "class")
        slot_label = f"{slot_day} {slot.get('start_time', '')}–{slot.get('end_time', '')}"

        if lec_id:
            key = f"{lec_id}:{gene.time_slot_id}"
            lec_slot_map[key].append(course.get("name", gene.course_id))
            if len(lec_slot_map[key]) == 2:
                lec_name = lecturers.get(lec_id, {}).get("name", lec_id)
                violations.append({
                    "severity": "high", "category": "lecturer",
                    "rule": "H1 — Lecturer double-booked",
                    "message": f"{lec_name} has two classes at {slot_label}: "
                               f"{lec_slot_map[key][0]} and {lec_slot_map[key][1]}",
                })

        rkey = f"{gene.room_id}:{gene.time_slot_id}"
        room_slot_map[rkey].append(course.get("name", gene.course_id))
        if len(room_slot_map[rkey]) == 2:
            room_name = room.get("name", gene.room_id)
            violations.append({
                "severity": "high", "category": "room",
                "rule": "H2 — Room double-booked",
                "message": f"{room_name} has two classes at {slot_label}: "
                           f"{room_slot_map[rkey][0]} and {room_slot_map[rkey][1]}",
            })

        if room and course:
            cap, students = room.get("capacity", 0), course.get("student_count", 0)
            if cap < students:
                violations.append({
                    "severity": "high", "category": "room",
                    "rule": "H3 — Room over capacity",
                    "message": f"{course.get('name')} ({students} students) in {room.get('name')} (capacity {cap})",
                })

        if course.get("requires_lab") and room.get("room_type") != "lab":
            violations.append({
                "severity": "high", "category": "room",
                "rule": "H4 — Lab room required",
                "message": f"{course.get('name')} requires a lab but is in {room.get('name')} ({room.get('room_type')})",
            })

        if slot_type in ("break", "lunch") or slot.get("is_break"):
            violations.append({
                "severity": "high", "category": "schedule",
                "rule": "H6 — Class in break/lunch slot",
                "message": f"{course.get('name')} is scheduled during a {slot_type} period at {slot_label}",
            })

        if grp_id:
            gkey = f"{grp_id}:{gene.time_slot_id}"
            group_slot_map[gkey].append(course.get("name", gene.course_id))
            if len(group_slot_map[gkey]) == 2:
                violations.append({
                    "severity": "high", "category": "student",
                    "rule": "H7 — Student group double-booked",
                    "message": f"Student group has two classes at {slot_label}: "
                               f"{group_slot_map[gkey][0]} and {group_slot_map[gkey][1]}",
                })

        if lec_id and slot_day:
            lec_day_count[(lec_id, slot_day)] += 1

    for (lec_id, day), hours in lec_day_count.items():
        lec_info = lecturers.get(lec_id, {})
        max_day = lec_info.get("max_hours_per_day", 6)
        if hours > max_day:
            violations.append({
                "severity": "medium", "category": "lecturer",
                "rule": "H8 — Daily hours exceeded",
                "message": f"{lec_info.get('name', lec_id)} has {hours} hours on {day} (max {max_day})",
            })

    return violations

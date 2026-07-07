"""
Multi-objective fitness function for the timetable genetic algorithm.

Hard constraints (violation → heavy penalty, cannot be optimised away):
  H1  – No lecturer teaches two classes at the same time
  H2  – No room hosts two classes at the same time
  H3  – Room capacity must not be exceeded
  H4  – Lab courses must be assigned lab rooms
  H5  – Courses must only appear in lecturer's available slots
  H6  – No classes scheduled in break/lunch slots
  H7  – Student group must not have two classes at the same time
  H8  – Lecturer daily hours must not exceed max_hours_per_day
  H9  – Explicitly unavailable slots must not be used for a lecturer
  H10 – Room booked by another active timetable (cross-department)
  H11 – Lecturer booked by another active timetable (cross-department)
  H12 – Equipment required not present in assigned room (DB-driven)
  H13 – Fixed-session course must occupy its designated slot (DB-driven)
  H14 – Mandatory course ordering violated (DB-driven)

Soft constraints (violation → proportional penalty scaled by weight):
  S1  – Prefer no consecutive lectures for a lecturer (> max_consecutive_hours)
  S2  – Distribute lectures evenly across days
  S3  – Respect department / lecturer preferred times
  S4  – Minimise gaps in student-group daily schedules
  S5  – Balance room utilisation across available rooms
  S6  – Prefer lecturer preferred days when specified
  S7  – Exam-gap: avoid scheduling classes immediately before exam blocks
  S8  – DB-driven soft constraints (rule_type routing)
  S9  – Same-course sessions spread across different days
  S10 – Building cohesion: consecutive slots stay in same building
"""
from __future__ import annotations
from collections import defaultdict
from app.ga.chromosome import Chromosome
from app.ga.constraint_index import ConstraintIndex

HARD_PENALTY = 1000.0
SOFT_WEIGHTS = {
    "consecutive":     60.0,
    "distribution":    30.0,
    "dept_preference": 25.0,
    "student_gaps":    45.0,
    "room_balance":    15.0,
    "preferred_days":  20.0,
    "exam_gap":        35.0,
    "max_weekly":      80.0,
    "course_spread":   40.0,  # S9
    "travel":          25.0,  # S10
}

# Ordered days for chronological comparison
_DAY_ORD = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2,
    "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6,
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


def _severity(c: dict, soft_factor: float) -> float:
    """Return HARD_PENALTY or weight * soft_factor depending on constraint_type."""
    if c.get("constraint_type") == "hard":
        return HARD_PENALTY
    return float(c.get("weight", 1.0)) * soft_factor


def _gene_lecturer_id(gene, course: dict, context: dict, gene_index: int) -> str:
    gene_lecturers = context.get("gene_lecturers")
    if gene_lecturers is not None and gene_index in gene_lecturers:
        lec = gene_lecturers[gene_index]
        return lec or ""
    per_group = course.get("per_group_lecturer_ids") or {}
    if gene.student_group_id and gene.student_group_id in per_group:
        val = per_group[gene.student_group_id]
        return val or ""
    return course.get("lecturer_id", "") or ""


def _session_label(course: dict, gene, context: dict) -> str:
    name = course.get("name", gene.course_id)
    grp_id = gene.student_group_id or course.get("student_group_id", "")
    if grp_id:
        groups = context.get("student_groups") or {}
        g = groups.get(grp_id, {})
        code = g.get("code") or g.get("name") or grp_id
        return f"{name} ({code})"
    return name


def _clash_message(resource_label: str, slot_label: str, labels: list[str]) -> str:
    if len(labels) == 2:
        return f"{resource_label} has two classes at {slot_label}: {labels[0]} and {labels[1]}"
    return f"{resource_label} has {len(labels)} classes at {slot_label}: {', '.join(labels)}"


def evaluate(chromosome: Chromosome, context: dict) -> float:
    """
    Returns a fitness score ∈ [0, 1] where 1.0 = perfect schedule.
    Accepts an optional 'db_constraints' list in context for DB-driven rules.
    """
    penalty = 0.0

    courses = context["courses"]
    rooms   = context["rooms"]
    slots   = context["slots"]
    lecturers = context["lecturers"]
    db_constraints: list[dict] = context.get("db_constraints", [])
    constraint_index: ConstraintIndex = context.get("constraint_index") or ConstraintIndex(db_constraints)
    _ext = context.get("external_bookings", {"room": {}, "lecturer": {}, "student_group": {}})
    ext_room: dict = _ext.get("room", {})
    ext_lec:  dict = _ext.get("lecturer", {})
    ext_grp:  dict = _ext.get("student_group", {})

    # ── Build lookup indices ──────────────────────────────────────────────────
    lec_slot_map:   dict[str, list[str]] = defaultdict(list)   # "{lec}:{slot}" → courses
    room_slot_map:  dict[str, list[str]] = defaultdict(list)   # "{room}:{slot}" → courses
    group_slot_map: dict[str, list[str]] = defaultdict(list)   # "{grp}:{slot}" → courses
    lec_slots:      dict[str, list[str]] = defaultdict(list)   # lec_id → [slot_ids]
    lec_day_slots:  dict[tuple, list[str]] = defaultdict(list) # (lec_id, day) → [slot_ids]
    dept_day_count: dict[tuple, int] = defaultdict(int)        # (dept_id, day) → count
    group_day_slots: dict[tuple, list[int]] = defaultdict(list)# (grp_id, day) → [indexes]
    group_slots:    dict[str, list[str]] = defaultdict(list)   # grp_id → [slot_ids]
    room_usage:     dict[str, int] = defaultdict(int)          # room_id → usage count
    # (slot_id, actor_id) → room_id; used for S10 building check
    slot_room_for_actor: dict[tuple, str] = {}

    for i, gene in enumerate(chromosome.genes):
        course   = courses.get(gene.course_id, {})
        room     = rooms.get(gene.room_id, {})
        slot     = slots.get(gene.time_slot_id, {})
        lec_id   = _gene_lecturer_id(gene, course, context, i)
        grp_id   = gene.student_group_id or course.get("student_group_id", "")
        slot_day   = slot.get("day", "")
        slot_idx   = slot.get("slot_index", 0)
        slot_type  = slot.get("slot_type", "class")
        slot_start = slot.get("start_time", "")
        slot_end   = slot.get("end_time", "")

        # H10 – Room booked by another active timetable (cross-department)
        if gene.room_id and (gene.room_id, slot_day, slot_start, slot_end) in ext_room:
            penalty += HARD_PENALTY

        # H11 – Lecturer booked by another active timetable (cross-department)
        if lec_id and (lec_id, slot_day, slot_start, slot_end) in ext_lec:
            penalty += HARD_PENALTY

        # H-ext-group – Student group booked by a FIXED (non-target) entry in a scoped reschedule
        if grp_id and (grp_id, slot_day, slot_start, slot_end) in ext_grp:
            penalty += HARD_PENALTY

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

        # H4 – Required room type (generalizes the old lab-only check to any
        # required_room_type: science_lab, main_hall, etc. — falls back to the
        # legacy requires_lab boolean when no specific type is set).
        req_type = course.get("required_room_type") or ("lab" if course.get("requires_lab") else None)
        if req_type and room.get("room_type") != req_type:
            penalty += HARD_PENALTY

        # H5 – Lecturer availability (day-level from availability dict)
        if lec_id and lecturers.get(lec_id):
            lec_info     = lecturers[lec_id]
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
                slot_room_for_actor[(gene.time_slot_id, lec_id)] = gene.room_id

        if grp_id:
            group_slots[grp_id].append(gene.time_slot_id)
            if slot_day:
                group_day_slots[(grp_id, slot_day)].append(slot_idx)
                slot_room_for_actor[(gene.time_slot_id, grp_id)] = gene.room_id

        dept_id = course.get("department_id", "")
        if dept_id and slot_day:
            dept_day_count[(dept_id, slot_day)] += 1

        room_usage[gene.room_id] += 1

        # DB shared_room — department allow-list + priority (per gene)
        if gene.room_id:
            dept_id = course.get("department_id", "")
            room_rule = constraint_index.shared_room_constraints().get(gene.room_id)
            if room_rule and room_rule["allowed"] and dept_id:
                if dept_id not in room_rule["allowed"]:
                    c = room_rule["constraint"]
                    penalty += _severity(c, 80.0)
                else:
                    penalty += constraint_index.room_priority_penalty(gene.room_id, dept_id)

    # ── H8 – Lecturer daily hours ────────────────────────────────────────────
    for (lec_id, day), day_slot_ids in lec_day_slots.items():
        hours    = len(day_slot_ids)
        lec_info = lecturers.get(lec_id, {})
        max_day  = lec_info.get("max_hours_per_day", 6)
        if hours > max_day:
            penalty += HARD_PENALTY * (hours - max_day)

    # ── Soft: Weekly hours ───────────────────────────────────────────────────
    for lec_id, all_slots in lec_slots.items():
        lec_info  = lecturers.get(lec_id, {})
        max_week  = lec_info.get("max_hours_per_week", 20)
        hours     = len(all_slots)
        if hours > max_week:
            penalty += SOFT_WEIGHTS["max_weekly"] * (hours - max_week)

    # ── S1 – Consecutive lectures ────────────────────────────────────────────
    for lec_id, all_slots in lec_slots.items():
        lec_info   = lecturers.get(lec_id, {})
        max_consec = lec_info.get("max_consecutive_hours", 3)
        by_day     = _slots_per_day(all_slots, slots)
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
            avg      = sum(counts) / len(counts)
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
        variance  = sum((v - avg_usage) ** 2 for v in room_usage.values()) / len(room_usage)
        penalty  += variance * SOFT_WEIGHTS["room_balance"] * 0.01

    # ── S6 – Lecturer preferred days ────────────────────────────────────────
    for i, gene in enumerate(chromosome.genes):
        course = courses.get(gene.course_id, {})
        lec_id = _gene_lecturer_id(gene, course, context, i)
        if lec_id and lecturers.get(lec_id):
            pref_days = lecturers[lec_id].get("preferred_days", [])
            if pref_days:
                slot = slots.get(gene.time_slot_id, {})
                if slot.get("day") not in pref_days:
                    penalty += SOFT_WEIGHTS["preferred_days"]

    # ── S9 – Same-course sessions spread across days ─────────────────────────
    course_day_count: dict[tuple, int] = defaultdict(int)
    for gene in chromosome.genes:
        d = slots.get(gene.time_slot_id, {}).get("day")
        if d:
            course_day_count[(gene.course_id, d)] += 1
    for (_, _), count in course_day_count.items():
        if count > 1:
            penalty += SOFT_WEIGHTS["course_spread"] * (count - 1)

    # ── S10 – Building cohesion (travel-time penalty) ────────────────────────
    # For each actor (lecturer or student group), penalise every pair of
    # consecutive slots that land in different buildings.
    for (lec_id, day), day_slot_ids in lec_day_slots.items():
        ordered = sorted(
            [(slots[s].get("slot_index", 0), s) for s in day_slot_ids],
            key=lambda t: t[0],
        )
        for i in range(1, len(ordered)):
            idx_a, sid_a = ordered[i - 1]
            idx_b, sid_b = ordered[i]
            if idx_b != idx_a + 1:
                continue
            bldg_a = rooms.get(slot_room_for_actor.get((sid_a, lec_id), ""), {}).get("building_id")
            bldg_b = rooms.get(slot_room_for_actor.get((sid_b, lec_id), ""), {}).get("building_id")
            if bldg_a and bldg_b and bldg_a != bldg_b:
                penalty += SOFT_WEIGHTS["travel"]

    for (grp_id, day), day_slot_idxs in group_day_slots.items():
        # group_day_slots stores slot_indexes, not slot_ids — need slot_ids from group_slots
        grp_day_slot_ids = [
            s for s in group_slots.get(grp_id, [])
            if slots.get(s, {}).get("day") == day
        ]
        ordered = sorted(
            [(slots[s].get("slot_index", 0), s) for s in grp_day_slot_ids],
            key=lambda t: t[0],
        )
        for i in range(1, len(ordered)):
            idx_a, sid_a = ordered[i - 1]
            idx_b, sid_b = ordered[i]
            if idx_b != idx_a + 1:
                continue
            bldg_a = rooms.get(slot_room_for_actor.get((sid_a, grp_id), ""), {}).get("building_id")
            bldg_b = rooms.get(slot_room_for_actor.get((sid_b, grp_id), ""), {}).get("building_id")
            if bldg_a and bldg_b and bldg_a != bldg_b:
                penalty += SOFT_WEIGHTS["travel"]

    # ── DB-driven constraint routing ─────────────────────────────────────────
    for c in db_constraints:
        if not c.get("is_active"):
            continue
        rule   = c.get("rule_type", "")
        cfg    = c.get("config", {})
        weight = float(c.get("weight", 1.0))
        eid    = c.get("entity_id")
        etype  = c.get("entity_type", "")

        # ── Lecturer rules ────────────────────────────────────────────────────
        if rule == "max_consecutive" and etype == "lecturer":
            lim      = int(cfg.get("limit", 3))
            sev      = _severity(c, 50.0)
            lec_info = lecturers.get(eid, {})
            if lec_info and eid in lec_slots:
                by_day = _slots_per_day(lec_slots[eid], slots)
                for day_idxs in by_day.values():
                    run = _consecutive_run(day_idxs)
                    if run > lim:
                        penalty += sev * (run - lim)

        elif rule == "max_daily_hours" and etype == "lecturer":
            lim = int(cfg.get("limit", 6))
            sev = _severity(c, 50.0)
            for (lec_id, _), day_s in lec_day_slots.items():
                if lec_id == eid and len(day_s) > lim:
                    penalty += sev * (len(day_s) - lim)

        elif rule == "max_weekly_hours" and etype == "lecturer":
            lim = int(cfg.get("limit", 20))
            sev = _severity(c, 80.0)
            if eid in lec_slots and len(lec_slots[eid]) > lim:
                penalty += sev * (len(lec_slots[eid]) - lim)

        elif rule == "preferred_times" and etype == "lecturer":
            preferred_slot_ids = set(cfg.get("slot_ids", []))
            sev = _severity(c, 20.0)
            if preferred_slot_ids and eid:
                for i, gene in enumerate(chromosome.genes):
                    c_data = courses.get(gene.course_id, {})
                    if _gene_lecturer_id(gene, c_data, context, i) == eid:
                        if gene.time_slot_id not in preferred_slot_ids:
                            penalty += sev

        elif rule == "unavailable" and etype == "lecturer":
            blocked = set(cfg.get("slot_ids", []))
            sev = _severity(c, 50.0)
            if blocked and eid:
                for i, gene in enumerate(chromosome.genes):
                    c_data = courses.get(gene.course_id, {})
                    if _gene_lecturer_id(gene, c_data, context, i) == eid and gene.time_slot_id in blocked:
                        penalty += sev

        # ── Student-group rules ───────────────────────────────────────────────
        elif rule == "max_daily_hours" and etype == "student_group":
            lim = int(cfg.get("limit", 6))
            sev = _severity(c, 50.0)
            for (grp_id, _), day_s in group_day_slots.items():
                if grp_id == eid and len(day_s) > lim:
                    penalty += sev * (len(day_s) - lim)

        elif rule == "max_consecutive" and etype == "student_group":
            lim = int(cfg.get("limit", 3))
            sev = _severity(c, 50.0)
            if eid in group_slots:
                for day_idxs in _slots_per_day(group_slots[eid], slots).values():
                    run = _consecutive_run(day_idxs)
                    if run > lim:
                        penalty += sev * (run - lim)

        elif rule == "max_weekly_hours" and etype == "student_group":
            lim = int(cfg.get("limit", 25))
            sev = _severity(c, 80.0)
            if eid in group_slots and len(group_slots[eid]) > lim:
                penalty += sev * (len(group_slots[eid]) - lim)

        # ── Room rules ────────────────────────────────────────────────────────
        elif rule == "equipment_required":
            needs = set(cfg.get("equipment", []))
            sev   = _severity(c, 40.0)
            if needs:
                for gene in chromosome.genes:
                    if eid and gene.room_id != eid:
                        continue
                    r = rooms.get(gene.room_id, {})
                    if "projector" in needs and not r.get("has_projector"):
                        penalty += sev
                    if "lab_equipment" in needs and not r.get("has_lab_equipment"):
                        penalty += sev
                    if "whiteboard" in needs and not r.get("has_projector") and r.get("room_type") not in ("seminar", "lab"):
                        penalty += sev

        elif rule == "shared_room" and etype == "room":
            # Evaluated per-gene above via constraint_index; kept for explicit config routing
            pass

        # ── Academic / course rules ───────────────────────────────────────────
        elif rule == "fixed_session":
            target_slot   = cfg.get("slot_id")
            target_course = cfg.get("course_id") or (eid if etype == "course" else None)
            sev = _severity(c, 100.0)
            if target_slot and target_course:
                for gene in chromosome.genes:
                    if gene.course_id == target_course and gene.time_slot_id != target_slot:
                        penalty += sev

        elif rule == "mandatory_order":
            before_id = cfg.get("before_course_id")
            after_id  = cfg.get("after_course_id")
            sev = _severity(c, 60.0)
            if before_id and after_id:
                def _first_ord(course_id: str):
                    best = None
                    for g in chromosome.genes:
                        if g.course_id != course_id:
                            continue
                        s = slots.get(g.time_slot_id, {})
                        o = (_DAY_ORD.get(s.get("day"), 9), s.get("slot_index", 99))
                        best = o if best is None or o < best else best
                    return best
                ord_a = _first_ord(before_id)
                ord_b = _first_ord(after_id)
                if ord_a is not None and ord_b is not None and ord_a >= ord_b:
                    penalty += sev

        elif rule == "semester_only":
            # Handled at course query level; penalise if the gene's course is from
            # the wrong semester (only possible when cross-semester data leaks in).
            target_sem = int(cfg.get("semester", 1))
            sev = _severity(c, 80.0)
            if eid:
                for gene in chromosome.genes:
                    if gene.course_id == eid:
                        course_data = courses.get(gene.course_id, {})
                        if course_data.get("semester") and course_data["semester"] != target_sem:
                            penalty += sev

        elif rule in ("course_preferred_times", "preferred_times") and etype == "course":
            preferred_slot_ids = set(cfg.get("slot_ids", []))
            sev = _severity(c, 20.0)
            if preferred_slot_ids and eid:
                for gene in chromosome.genes:
                    if gene.course_id == eid and gene.time_slot_id not in preferred_slot_ids:
                        penalty += sev

        elif rule in ("course_unavailable", "unavailable") and etype == "course":
            blocked = set(cfg.get("slot_ids", []))
            sev = _severity(c, 60.0)
            if blocked and eid:
                for gene in chromosome.genes:
                    if gene.course_id == eid and gene.time_slot_id in blocked:
                        penalty += sev

        elif rule == "exam_gap":
            exam_slot_ids = set(cfg.get("exam_slot_ids", []))
            gap = int(cfg.get("min_gap_slots", 2))
            sev = _severity(c, SOFT_WEIGHTS["exam_gap"])
            for gene in chromosome.genes:
                slot_idx = slots.get(gene.time_slot_id, {}).get("slot_index", -1)
                slot_day = slots.get(gene.time_slot_id, {}).get("day", "")
                for exam_sid in exam_slot_ids:
                    exam_slot = slots.get(exam_sid, {})
                    if exam_slot.get("day") == slot_day:
                        dist = abs(slot_idx - exam_slot.get("slot_index", -1))
                        if 0 < dist <= gap:
                            penalty += sev

    # ── Normalise ─────────────────────────────────────────────────────────────
    n = max(1, len(chromosome.genes))
    # Worst-case: every gene triggers every hard constraint
    # H1–H11 (original 9) + H12 equipment + H13 fixed_session + H14 mandatory_order = 13 checks
    worst = n * HARD_PENALTY * 13
    fitness = max(0.0, 1.0 - (penalty / worst))
    return round(fitness, 6)


def violation_report(chromosome: Chromosome, context: dict) -> list[dict]:
    """
    Returns a human-readable list of constraint violations for display in the UI.
    Called once after GA completion on the best chromosome.
    """
    violations: list[dict] = []

    courses   = context["courses"]
    rooms     = context["rooms"]
    slots     = context["slots"]
    lecturers = context["lecturers"]
    db_constraints: list[dict] = context.get("db_constraints", [])
    constraint_index: ConstraintIndex = context.get("constraint_index") or ConstraintIndex(db_constraints)
    _ext_vr    = context.get("external_bookings", {"room": {}, "lecturer": {}, "student_group": {}})
    ext_room_vr: dict = _ext_vr.get("room", {})
    ext_lec_vr:  dict = _ext_vr.get("lecturer", {})
    ext_grp_vr:  dict = _ext_vr.get("student_group", {})

    lec_slot_map:   dict[str, list] = defaultdict(list)
    room_slot_map:  dict[str, list] = defaultdict(list)
    group_slot_map: dict[str, list] = defaultdict(list)
    lec_day_count:  dict[tuple, int] = defaultdict(int)
    group_day_slots_vr: dict[tuple, list[int]] = defaultdict(list)
    lec_day_slots_vr:   dict[tuple, list[str]] = defaultdict(list)
    group_slots_vr:     dict[str, list[str]]   = defaultdict(list)
    lec_slots_vr:       dict[str, list[str]]   = defaultdict(list)

    for i, gene in enumerate(chromosome.genes):
        course    = courses.get(gene.course_id, {})
        room      = rooms.get(gene.room_id, {})
        slot      = slots.get(gene.time_slot_id, {})
        lec_id    = _gene_lecturer_id(gene, course, context, i)
        grp_id    = gene.student_group_id or course.get("student_group_id", "")
        session_label = _session_label(course, gene, context)
        slot_day       = slot.get("day", "")
        slot_start_vr  = slot.get("start_time", "")
        slot_end_vr    = slot.get("end_time", "")
        slot_type      = slot.get("slot_type", "class")
        slot_label     = f"{slot_day} {slot_start_vr}–{slot_end_vr}"

        if lec_id:
            key = f"{lec_id}:{gene.time_slot_id}"
            lec_slot_map[key].append(session_label)

        rkey = f"{gene.room_id}:{gene.time_slot_id}"
        room_slot_map[rkey].append(session_label)

        if room and course:
            cap, students = room.get("capacity", 0), course.get("student_count", 0)
            if cap < students:
                violations.append({
                    "severity": "high", "category": "room",
                    "rule": "H3 — Room over capacity",
                    "message": f"{course.get('name')} ({students} students) in "
                               f"{room.get('name')} (capacity {cap})",
                })

        req_type_vr = course.get("required_room_type") or ("lab" if course.get("requires_lab") else None)
        if req_type_vr and room.get("room_type") != req_type_vr:
            violations.append({
                "severity": "high", "category": "room",
                "rule": "H4 — Required room type",
                "message": f"{course.get('name')} requires a '{req_type_vr}' room but is in "
                           f"{room.get('name')} ({room.get('room_type')})",
            })

        if slot_type in ("break", "lunch") or slot.get("is_break"):
            violations.append({
                "severity": "high", "category": "schedule",
                "rule": "H6 — Class in break/lunch slot",
                "message": f"{course.get('name')} is scheduled during a {slot_type} period at {slot_label}",
            })

        if grp_id:
            gkey = f"{grp_id}:{gene.time_slot_id}"
            group_slot_map[gkey].append(session_label)

        # H10 – Room booked by another active timetable
        if gene.room_id:
            hit = ext_room_vr.get((gene.room_id, slot_day, slot_start_vr, slot_end_vr))
            if hit:
                other = hit[0]
                violations.append({
                    "severity": "high", "category": "room",
                    "rule": "H10 — Room booked by another department",
                    "message": (
                        f"{room.get('name', gene.room_id)} at {slot_label} is already booked by "
                        f"{other['department_name']} ({other['course_name']})."
                    ),
                })

        # H11 – Lecturer booked by another active timetable
        if lec_id:
            hit = ext_lec_vr.get((lec_id, slot_day, slot_start_vr, slot_end_vr))
            if hit:
                other = hit[0]
                violations.append({
                    "severity": "high", "category": "lecturer",
                    "rule": "H11 — Lecturer booked by another department",
                    "message": (
                        f"{other.get('lecturer_name', lec_id)} at {slot_label} is already assigned by "
                        f"{other['department_name']} ({other['course_name']})."
                    ),
                })

        # H-ext-group – Student group booked by a FIXED (non-target) entry in a scoped reschedule
        if grp_id:
            hit = ext_grp_vr.get((grp_id, slot_day, slot_start_vr, slot_end_vr))
            if hit:
                other = hit[0]
                violations.append({
                    "severity": "high", "category": "student",
                    "rule": "H-ext-group — Student group booked by a fixed session",
                    "message": (
                        f"Student group already has a fixed class at {slot_label} "
                        f"({other['course_name']})."
                    ),
                })

        if lec_id and slot_day:
            lec_day_count[(lec_id, slot_day)] += 1
            lec_day_slots_vr[(lec_id, slot_day)].append(gene.time_slot_id)
            lec_slots_vr[lec_id].append(gene.time_slot_id)

        if grp_id:
            group_slots_vr[grp_id].append(gene.time_slot_id)
            if slot_day:
                group_day_slots_vr[(grp_id, slot_day)].append(slot.get("slot_index", 0))

        # shared_room — department access and priority
        if gene.room_id:
            dept_id = course.get("department_id", "")
            room_rule = constraint_index.shared_room_constraints().get(gene.room_id)
            if room_rule and room_rule["allowed"] and dept_id:
                room_name = room.get("name", gene.room_id)
                if dept_id not in room_rule["allowed"]:
                    violations.append({
                        "severity": "high", "category": "room",
                        "rule": "Shared room — department not allowed",
                        "message": (
                            f"{course.get('name', gene.course_id)} uses {room_name} at {slot_label}, "
                            f"but this room is restricted to other departments."
                        ),
                    })
                elif constraint_index.room_priority_penalty(gene.room_id, dept_id) > 0:
                    violations.append({
                        "severity": "low", "category": "room",
                        "rule": "Shared room — lower priority department",
                        "message": (
                            f"{course.get('name', gene.course_id)} uses priority room {room_name} "
                            f"at {slot_label} (a higher-priority department is configured for this room)."
                        ),
                    })

    for key, labels in lec_slot_map.items():
        if len(labels) < 2:
            continue
        lec_id, slot_id = key.split(":", 1)
        slot = slots.get(slot_id, {})
        slot_label = f"{slot.get('day', '')} {slot.get('start_time', '')}–{slot.get('end_time', '')}"
        lec_name = lecturers.get(lec_id, {}).get("name", lec_id)
        violations.append({
            "severity": "high", "category": "lecturer",
            "rule": "H1 — Lecturer double-booked",
            "message": _clash_message(lec_name, slot_label, labels),
        })

    for key, labels in room_slot_map.items():
        if len(labels) < 2:
            continue
        room_id, slot_id = key.split(":", 1)
        slot = slots.get(slot_id, {})
        slot_label = f"{slot.get('day', '')} {slot.get('start_time', '')}–{slot.get('end_time', '')}"
        room_name = rooms.get(room_id, {}).get("name", room_id)
        violations.append({
            "severity": "high", "category": "room",
            "rule": "H2 — Room double-booked",
            "message": _clash_message(room_name, slot_label, labels),
        })

    for key, labels in group_slot_map.items():
        if len(labels) < 2:
            continue
        grp_id, slot_id = key.split(":", 1)
        slot = slots.get(slot_id, {})
        slot_label = f"{slot.get('day', '')} {slot.get('start_time', '')}–{slot.get('end_time', '')}"
        groups = context.get("student_groups") or {}
        grp_name = groups.get(grp_id, {}).get("name", grp_id)
        violations.append({
            "severity": "high", "category": "student",
            "rule": "H7 — Student group double-booked",
            "message": _clash_message(f"Student group {grp_name}", slot_label, labels),
        })

    for (lec_id, day), hours in lec_day_count.items():
        lec_info = lecturers.get(lec_id, {})
        max_day  = lec_info.get("max_hours_per_day", 6)
        if hours > max_day:
            violations.append({
                "severity": "medium", "category": "lecturer",
                "rule": "H8 — Daily hours exceeded",
                "message": f"{lec_info.get('name', lec_id)} has {hours} hours on {day} (max {max_day})",
            })

    # ── DB-driven violation reporting ─────────────────────────────────────────
    for c in db_constraints:
        if not c.get("is_active"):
            continue
        rule  = c.get("rule_type", "")
        cfg   = c.get("config", {})
        eid   = c.get("entity_id")
        etype = c.get("entity_type", "")

        if rule == "equipment_required":
            needs = set(cfg.get("equipment", []))
            if not needs:
                continue
            for gene in chromosome.genes:
                if eid and gene.room_id != eid:
                    continue
                r = rooms.get(gene.room_id, {})
                course = courses.get(gene.course_id, {})
                slot   = slots.get(gene.time_slot_id, {})
                label  = f"{slot.get('day')} {slot.get('start_time')}–{slot.get('end_time')}"
                if "projector" in needs and not r.get("has_projector"):
                    violations.append({
                        "severity": "high", "category": "room",
                        "rule": "H12 — Equipment missing: projector",
                        "message": f"{course.get('name')} at {label} — "
                                   f"{r.get('name', gene.room_id)} has no projector.",
                    })
                if "lab_equipment" in needs and not r.get("has_lab_equipment"):
                    violations.append({
                        "severity": "high", "category": "room",
                        "rule": "H12 — Equipment missing: lab_equipment",
                        "message": f"{course.get('name')} at {label} — "
                                   f"{r.get('name', gene.room_id)} has no lab equipment.",
                    })

        elif rule == "fixed_session":
            target_slot   = cfg.get("slot_id")
            target_course = cfg.get("course_id") or (eid if etype == "course" else None)
            if not (target_slot and target_course):
                continue
            for gene in chromosome.genes:
                if gene.course_id == target_course and gene.time_slot_id != target_slot:
                    course = courses.get(gene.course_id, {})
                    actual_slot = slots.get(gene.time_slot_id, {})
                    wanted_slot = slots.get(target_slot, {})
                    violations.append({
                        "severity": "high", "category": "schedule",
                        "rule": "H13 — Fixed session violated",
                        "message": (
                            f"{course.get('name', target_course)} must be at "
                            f"{wanted_slot.get('day')} {wanted_slot.get('start_time')} but is at "
                            f"{actual_slot.get('day')} {actual_slot.get('start_time')}."
                        ),
                    })

        elif rule == "mandatory_order":
            before_id = cfg.get("before_course_id")
            after_id  = cfg.get("after_course_id")
            if not (before_id and after_id):
                continue

            def _first_ord_vr(course_id: str):
                best = None
                for g in chromosome.genes:
                    if g.course_id != course_id:
                        continue
                    s = slots.get(g.time_slot_id, {})
                    o = (_DAY_ORD.get(s.get("day"), 9), s.get("slot_index", 99))
                    best = o if best is None or o < best else best
                return best

            ord_a = _first_ord_vr(before_id)
            ord_b = _first_ord_vr(after_id)
            if ord_a is not None and ord_b is not None and ord_a >= ord_b:
                before_name = courses.get(before_id, {}).get("name", before_id)
                after_name  = courses.get(after_id,  {}).get("name", after_id)
                violations.append({
                    "severity": "high", "category": "schedule",
                    "rule": "H14 — Mandatory order violated",
                    "message": f"{before_name} must be scheduled before {after_name} in the week.",
                })

        elif rule == "max_daily_hours" and etype == "student_group":
            lim = int(cfg.get("limit", 6))
            for (grp_id, day), day_s in group_day_slots_vr.items():
                if grp_id == eid and len(day_s) > lim:
                    violations.append({
                        "severity": "medium", "category": "student",
                        "rule": "Student group daily hours exceeded",
                        "message": f"Student group {eid[:8]} has {len(day_s)} sessions on {day} (limit {lim}).",
                    })

        elif rule == "max_consecutive" and etype == "student_group":
            lim = int(cfg.get("limit", 3))
            if eid in group_slots_vr:
                for day, day_idxs in _slots_per_day(group_slots_vr[eid], slots).items():
                    run = _consecutive_run(day_idxs)
                    if run > lim:
                        violations.append({
                            "severity": "medium", "category": "student",
                            "rule": "Student group consecutive classes exceeded",
                            "message": f"Student group {eid[:8]} has {run} consecutive classes on {day} (limit {lim}).",
                        })

        elif rule in ("course_preferred_times", "preferred_times") and etype == "course":
            preferred_slot_ids = set(cfg.get("slot_ids", []))
            if preferred_slot_ids and eid:
                for gene in chromosome.genes:
                    if gene.course_id == eid and gene.time_slot_id not in preferred_slot_ids:
                        course = courses.get(gene.course_id, {})
                        slot   = slots.get(gene.time_slot_id, {})
                        label  = f"{slot.get('day')} {slot.get('start_time')}"
                        violations.append({
                            "severity": "low", "category": "schedule",
                            "rule": "Course outside preferred time slots",
                            "message": f"{course.get('name', eid)} is scheduled at {label} which is not a preferred slot.",
                        })

        elif rule in ("course_unavailable", "unavailable") and etype == "course":
            blocked = set(cfg.get("slot_ids", []))
            if blocked and eid:
                for gene in chromosome.genes:
                    if gene.course_id == eid and gene.time_slot_id in blocked:
                        course = courses.get(gene.course_id, {})
                        slot   = slots.get(gene.time_slot_id, {})
                        label  = f"{slot.get('day')} {slot.get('start_time')}"
                        violations.append({
                            "severity": "high", "category": "schedule",
                            "rule": "Course scheduled in unavailable slot",
                            "message": f"{course.get('name', eid)} is in a blocked slot at {label}.",
                        })

        elif rule == "max_daily_hours" and etype == "lecturer":
            lim = int(cfg.get("limit", 6))
            for (lec_id, day), day_s in lec_day_slots_vr.items():
                if lec_id == eid and len(day_s) > lim:
                    lec_info = lecturers.get(lec_id, {})
                    violations.append({
                        "severity": "medium", "category": "lecturer",
                        "rule": "Lecturer daily hours exceeded (constraint)",
                        "message": f"{lec_info.get('name', lec_id)} has {len(day_s)} sessions on {day} (limit {lim}).",
                    })

        elif rule == "max_weekly_hours" and etype == "lecturer":
            lim = int(cfg.get("limit", 20))
            if eid in lec_slots_vr and len(lec_slots_vr[eid]) > lim:
                lec_info = lecturers.get(eid, {})
                violations.append({
                    "severity": "medium", "category": "lecturer",
                    "rule": "Lecturer weekly hours exceeded (constraint)",
                    "message": f"{lec_info.get('name', eid)} has {len(lec_slots_vr[eid])} sessions (limit {lim}).",
                })

        elif rule == "max_consecutive" and etype == "lecturer":
            lim = int(cfg.get("limit", 3))
            if eid in lec_slots_vr:
                for day, day_idxs in _slots_per_day(lec_slots_vr[eid], slots).items():
                    run = _consecutive_run(day_idxs)
                    if run > lim:
                        lec_info = lecturers.get(eid, {})
                        violations.append({
                            "severity": "medium", "category": "lecturer",
                            "rule": "Lecturer consecutive periods exceeded",
                            "message": f"{lec_info.get('name', eid)} has {run} consecutive periods on {day} (limit {lim}).",
                        })

        elif rule == "preferred_times" and etype == "lecturer":
            preferred_slot_ids = set(cfg.get("slot_ids", []))
            if preferred_slot_ids and eid:
                for i, gene in enumerate(chromosome.genes):
                    c_data = courses.get(gene.course_id, {})
                    if _gene_lecturer_id(gene, c_data, context, i) == eid and gene.time_slot_id not in preferred_slot_ids:
                        lec_info = lecturers.get(eid, {})
                        slot = slots.get(gene.time_slot_id, {})
                        label = f"{slot.get('day')} {slot.get('start_time')}"
                        violations.append({
                            "severity": "low", "category": "lecturer",
                            "rule": "Outside preferred time slots",
                            "message": f"{lec_info.get('name', eid)} — {c_data.get('name', gene.course_id)} at {label} is not preferred.",
                        })

        elif rule == "unavailable" and etype == "lecturer":
            blocked = set(cfg.get("slot_ids", []))
            if blocked and eid:
                for i, gene in enumerate(chromosome.genes):
                    c_data = courses.get(gene.course_id, {})
                    if _gene_lecturer_id(gene, c_data, context, i) == eid and gene.time_slot_id in blocked:
                        lec_info = lecturers.get(eid, {})
                        slot = slots.get(gene.time_slot_id, {})
                        label = f"{slot.get('day')} {slot.get('start_time')}"
                        violations.append({
                            "severity": "high", "category": "lecturer",
                            "rule": "Lecturer unavailable slot used",
                            "message": f"{lec_info.get('name', eid)} is scheduled at blocked slot {label}.",
                        })

        elif rule == "max_weekly_hours" and etype == "student_group":
            lim = int(cfg.get("limit", 25))
            if eid in group_slots_vr and len(group_slots_vr[eid]) > lim:
                violations.append({
                    "severity": "medium", "category": "student",
                    "rule": "Student group weekly hours exceeded",
                    "message": f"Student group {eid[:8]} has {len(group_slots_vr[eid])} sessions (limit {lim}).",
                })

        elif rule == "semester_only":
            target_sem = int(cfg.get("semester", 1))
            if eid:
                for gene in chromosome.genes:
                    if gene.course_id == eid:
                        course_data = courses.get(gene.course_id, {})
                        if course_data.get("semester") and course_data["semester"] != target_sem:
                            violations.append({
                                "severity": "high", "category": "academic",
                                "rule": "Semester-only module violated",
                                "message": f"{course_data.get('name', eid)} is scheduled but belongs to semester {target_sem} only.",
                            })

        elif rule == "exam_gap":
            exam_slot_ids = set(cfg.get("exam_slot_ids", []))
            gap = int(cfg.get("min_gap_slots", 2))
            for gene in chromosome.genes:
                slot_idx = slots.get(gene.time_slot_id, {}).get("slot_index", -1)
                slot_day = slots.get(gene.time_slot_id, {}).get("day", "")
                course = courses.get(gene.course_id, {})
                for exam_sid in exam_slot_ids:
                    exam_slot = slots.get(exam_sid, {})
                    if exam_slot.get("day") == slot_day:
                        dist = abs(slot_idx - exam_slot.get("slot_index", -1))
                        if 0 < dist <= gap:
                            violations.append({
                                "severity": "low", "category": "academic",
                                "rule": "Exam preparation gap violated",
                                "message": f"{course.get('name', gene.course_id)} is too close to an exam slot on {slot_day}.",
                            })

    return violations

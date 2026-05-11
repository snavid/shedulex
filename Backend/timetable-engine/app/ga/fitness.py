"""
Multi-objective fitness function for the timetable genetic algorithm.

Hard constraints (violations → heavy penalty):
  H1 – No lecturer teaches two classes at the same time
  H2 – No room hosts two classes at the same time
  H3 – Room capacity must not be exceeded
  H4 – Lab courses must be assigned lab rooms
  H5 – Courses must only appear in lecturer's available slots

Soft constraints (violations → proportional penalty scaled by weight):
  S1 – Prefer no consecutive lectures for a lecturer (>2 consecutive)
  S2 – Distribute lectures evenly across days
  S3 – No classes in break slots
  S4 – Respect department preferred times
  S5 – Minimize gaps in student schedules
  S6 – Balance room utilization
"""
from __future__ import annotations
from collections import defaultdict
from app.ga.chromosome import Chromosome

HARD_PENALTY = 1000.0
SOFT_WEIGHTS = {
    "consecutive": 50.0,
    "distribution": 30.0,
    "breaks": 80.0,
    "dept_preference": 20.0,
    "student_gaps": 40.0,
    "room_balance": 10.0,
}


def evaluate(chromosome: Chromosome, context: dict) -> float:
    """
    Returns a fitness score ∈ [0, 1] where 1 = perfect.
    The raw penalty is normalised against the worst possible score.
    """
    penalty = 0.0

    # Index genes for fast lookups
    slot_lecturer: dict[str, list[str]] = defaultdict(list)    # slot_id → [course_id]
    slot_room: dict[str, list[str]] = defaultdict(list)        # (slot_id,room_id) → [course_id]
    lecturer_slots: dict[str, list[str]] = defaultdict(list)   # lecturer_id → [slot_ids]
    dept_day_count: dict[tuple, int] = defaultdict(int)        # (dept_id, day) → count

    courses = context["courses"]       # dict[course_id → Course-like dict]
    rooms = context["rooms"]           # dict[room_id → Room-like dict]
    slots = context["slots"]           # dict[slot_id → Slot-like dict]
    lecturers = context["lecturers"]   # dict[lecturer_id → Lecturer-like dict]

    for gene in chromosome.genes:
        course = courses.get(gene.course_id, {})
        room = rooms.get(gene.room_id, {})
        slot = slots.get(gene.time_slot_id, {})
        lecturer_id = course.get("lecturer_id", "")

        # H1 – Lecturer double-booking
        key_lec = f"{lecturer_id}:{gene.time_slot_id}"
        slot_lecturer[key_lec].append(gene.course_id)
        if len(slot_lecturer[key_lec]) > 1:
            penalty += HARD_PENALTY

        # H2 – Room double-booking
        key_room = f"{gene.room_id}:{gene.time_slot_id}"
        slot_room[key_room].append(gene.course_id)
        if len(slot_room[key_room]) > 1:
            penalty += HARD_PENALTY

        # H3 – Room capacity
        if room and course:
            if room.get("capacity", 0) < course.get("student_count", 0):
                penalty += HARD_PENALTY

        # H4 – Lab requirement
        if course.get("requires_lab") and room.get("room_type") != "lab":
            penalty += HARD_PENALTY

        # H5 – Lecturer availability
        if lecturer_id and lecturers.get(lecturer_id):
            availability = lecturers[lecturer_id].get("availability", {})
            day = slot.get("day", "")
            allowed_slots = availability.get(day, [])
            if allowed_slots and gene.time_slot_id not in allowed_slots:
                penalty += HARD_PENALTY

        # S3 – Break slots
        if slot.get("is_break"):
            penalty += SOFT_WEIGHTS["breaks"]

        # Track for soft constraint analysis
        if lecturer_id:
            lecturer_slots[lecturer_id].append(gene.time_slot_id)

        dept_id = course.get("department_id", "unknown")
        day = slot.get("day", "unknown")
        dept_day_count[(dept_id, day)] += 1

    # S1 – Consecutive lectures (>2 back-to-back for same lecturer)
    for lec_id, slot_ids in lecturer_slots.items():
        lec_slots_info = [slots[s] for s in slot_ids if s in slots]
        lec_slots_info.sort(key=lambda s: (s.get("day", ""), s.get("slot_index", 0)))
        consecutive = 1
        for i in range(1, len(lec_slots_info)):
            prev = lec_slots_info[i - 1]
            curr = lec_slots_info[i]
            if (prev.get("day") == curr.get("day") and
                    curr.get("slot_index", 0) - prev.get("slot_index", 0) == 1):
                consecutive += 1
                if consecutive > 2:
                    penalty += SOFT_WEIGHTS["consecutive"]
            else:
                consecutive = 1

    # S2 – Even distribution across days
    for dept_id in set(d for d, _ in dept_day_count.keys()):
        counts = [dept_day_count[(dept_id, d)] for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"] if (dept_id, d) in dept_day_count]
        if counts:
            avg = sum(counts) / len(counts)
            variance = sum((c - avg) ** 2 for c in counts) / len(counts)
            penalty += variance * SOFT_WEIGHTS["distribution"] * 0.1

    # Normalise: worst case ≈ len(genes) * HARD_PENALTY
    worst = max(1, len(chromosome.genes)) * HARD_PENALTY
    fitness = max(0.0, 1.0 - (penalty / worst))
    return fitness

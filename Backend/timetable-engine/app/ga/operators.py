"""
Genetic operators: selection, crossover, mutation, elitism.

Selection  – Tournament selection (size k=5)
Crossover  – Single-point, uniform, and two-point strategies
Mutation   – Guided (respects lecturer availability + DB constraints) + random fallback
Elitism    – Top N chromosomes carried over unchanged
"""
from __future__ import annotations
import random
from collections import defaultdict
from app.ga.chromosome import Chromosome, Gene
from app.ga.constraint_index import ConstraintIndex


def tournament_selection(population: list[Chromosome], tournament_size: int = 5) -> Chromosome:
    candidates = random.sample(population, min(tournament_size, len(population)))
    return max(candidates, key=lambda c: c.fitness).clone()


def single_point_crossover(parent1: Chromosome, parent2: Chromosome) -> tuple[Chromosome, Chromosome]:
    if len(parent1) < 2 or len(parent2) < 2:
        return parent1.clone(), parent2.clone()
    point = random.randint(1, min(len(parent1), len(parent2)) - 1)
    c1_genes = parent1.genes[:point] + parent2.genes[point:]
    c2_genes = parent2.genes[:point] + parent1.genes[point:]
    return (Chromosome(genes=[g.clone() for g in c1_genes]),
            Chromosome(genes=[g.clone() for g in c2_genes]))


def two_point_crossover(parent1: Chromosome, parent2: Chromosome) -> tuple[Chromosome, Chromosome]:
    """Two-point crossover swaps the middle segment — better preserves building blocks."""
    n = min(len(parent1), len(parent2))
    if n < 3:
        return single_point_crossover(parent1, parent2)
    p1, p2 = sorted(random.sample(range(1, n), 2))
    c1_genes = parent1.genes[:p1] + parent2.genes[p1:p2] + parent1.genes[p2:]
    c2_genes = parent2.genes[:p1] + parent1.genes[p1:p2] + parent2.genes[p2:]
    return (Chromosome(genes=[g.clone() for g in c1_genes]),
            Chromosome(genes=[g.clone() for g in c2_genes]))


def uniform_crossover(parent1: Chromosome, parent2: Chromosome) -> tuple[Chromosome, Chromosome]:
    """Per-gene coin-flip — maximum diversity."""
    length = min(len(parent1), len(parent2))
    c1_genes, c2_genes = [], []
    for i in range(length):
        if random.random() < 0.5:
            c1_genes.append(parent1.genes[i].clone())
            c2_genes.append(parent2.genes[i].clone())
        else:
            c1_genes.append(parent2.genes[i].clone())
            c2_genes.append(parent1.genes[i].clone())
    return Chromosome(genes=c1_genes), Chromosome(genes=c2_genes)


def _build_room_busy_slots(slots_info: dict, external_bookings: dict) -> dict[str, set[str]]:
    wallclock_to_slot = {}
    for s in slots_info.values():
        day, st, en = s.get("day"), s.get("start_time"), s.get("end_time")
        if day and st and en:
            wallclock_to_slot[(day, st, en)] = s["id"]
    room_busy: dict[str, set[str]] = defaultdict(set)
    for (room_id, d, st, en) in external_bookings.get("room", {}):
        sid = wallclock_to_slot.get((d, st, en))
        if sid:
            room_busy[room_id].add(sid)
    return room_busy


def mutate(
    chromosome: Chromosome,
    mutation_rate: float,
    available_rooms: list[str],
    available_slots: list[str],
    lecturers: dict | None = None,
    courses: dict | None = None,
    slots_info: dict | None = None,
    generating_department_id: str | None = None,
    constraint_index: ConstraintIndex | None = None,
    rooms: list[dict] | None = None,
    external_bookings: dict | None = None,
    building_id: str | None = None,
) -> Chromosome:
    """
    Guided mutation: respects lecturer availability and DB constraint blocked slots/rooms.
    """
    lecturers = lecturers or {}
    courses = courses or {}
    slots_info = slots_info or {}
    idx = constraint_index or ConstraintIndex()
    if not rooms:
        if available_rooms and isinstance(available_rooms[0], dict):
            rooms = available_rooms
        else:
            rooms = [{"id": rid} for rid in (available_rooms or [])]
    external_bookings = external_bookings or {"room": {}, "lecturer": {}}
    room_busy = _build_room_busy_slots(slots_info, external_bookings)
    dept_id = generating_department_id or ""

    if available_slots and isinstance(available_slots[0], dict):
        slot_id_list = [s["id"] for s in available_slots]
    else:
        slot_id_list = list(available_slots or [])

    mutant = chromosome.clone()
    for gene in mutant.genes:
        if random.random() >= mutation_rate:
            continue

        course = courses.get(gene.course_id, {})
        lec_id = course.get("lecturer_id", "")
        unit_dept = course.get("department_id") or dept_id
        fixed_slot = idx.fixed_session(gene.course_id)

        action = random.choice(["room", "slot", "both"])

        if action in ("room", "both"):
            eligible = idx.eligible_room_ids_for_gene(
                rooms, unit_dept,
                requires_lab=bool(course.get("requires_lab")),
                required_room_type=course.get("required_room_type"),
                fixed_room_id=course.get("fixed_room_id"),
                building_id=building_id,
                slot_id=gene.time_slot_id,
                room_busy_slots=room_busy,
            )
            if eligible:
                gene.room_id = random.choice(eligible)
            elif rooms:
                gene.room_id = random.choice([r["id"] for r in rooms])

        if action in ("slot", "both") and slot_id_list:
            db_blocked = idx.blocked_slots_for_lecturer(lec_id) | idx.blocked_slots_for_course(gene.course_id)
            guided = False
            if lec_id and lec_id in lecturers:
                lec = lecturers[lec_id]
                avail = lec.get("availability", {})
                unavail = set(lec.get("unavailable_slots", [])) | db_blocked
                if avail:
                    allowed = {sid for sids in avail.values() for sid in sids}
                    candidates = [s for s in slot_id_list
                                  if s in allowed and s not in unavail]
                else:
                    candidates = [s for s in slot_id_list if s not in unavail]
                candidates = [s for s in candidates
                              if slots_info.get(s, {}).get("slot_type", "class")
                              not in ("break", "lunch")
                              and not slots_info.get(s, {}).get("is_break", False)]
                if fixed_slot and fixed_slot in candidates:
                    gene.time_slot_id = fixed_slot
                    guided = True
                elif candidates:
                    gene.time_slot_id = random.choice(candidates)
                    guided = True
            if not guided:
                clean = [s for s in slot_id_list
                         if s not in db_blocked
                         and slots_info.get(s, {}).get("slot_type", "class")
                         not in ("break", "lunch")
                         and not slots_info.get(s, {}).get("is_break", False)]
                if fixed_slot and fixed_slot in clean:
                    gene.time_slot_id = fixed_slot
                elif clean:
                    gene.time_slot_id = random.choice(clean)
                elif slot_id_list:
                    gene.time_slot_id = random.choice(slot_id_list)

        # Enforce room eligibility after any mutation (including slot-only changes)
        eligible = idx.eligible_room_ids_for_gene(
            rooms, unit_dept,
            requires_lab=bool(course.get("requires_lab")),
            required_room_type=course.get("required_room_type"),
            fixed_room_id=course.get("fixed_room_id"),
            building_id=building_id,
            slot_id=gene.time_slot_id,
            room_busy_slots=room_busy,
        )
        if eligible and gene.room_id not in eligible:
            gene.room_id = random.choice(eligible)

    return mutant


def adaptive_mutation_rate(
    generation: int,
    max_generations: int,
    base_rate: float = 0.02,
    max_rate: float = 0.15,
) -> float:
    """Increase mutation rate with generational progress to escape local optima."""
    progress = generation / max(max_generations, 1)
    return base_rate + (max_rate - base_rate) * progress


def elitism(population: list[Chromosome], elite_count: int) -> list[Chromosome]:
    sorted_pop = sorted(population, key=lambda c: c.fitness, reverse=True)
    return [c.clone() for c in sorted_pop[:elite_count]]

"""
Genetic operators: selection, crossover, mutation, elitism.

Selection  – Tournament selection (size k=5)
Crossover  – Single-point, uniform, and two-point strategies
Mutation   – Guided (respects lecturer availability) + random fallback
Elitism    – Top N chromosomes carried over unchanged
"""
from __future__ import annotations
import random
from app.ga.chromosome import Chromosome, Gene


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


def mutate(
    chromosome: Chromosome,
    mutation_rate: float,
    available_rooms: list[str],
    available_slots: list[str],
    lecturers: dict | None = None,
    courses: dict | None = None,
    slots_info: dict | None = None,
) -> Chromosome:
    """
    Guided mutation: when a lecturer has defined availability, prefer valid slots.
    Falls back to random selection when guidance is unavailable or not applicable.
    """
    lecturers = lecturers or {}
    courses = courses or {}
    slots_info = slots_info or {}

    mutant = chromosome.clone()
    for gene in mutant.genes:
        if random.random() >= mutation_rate:
            continue

        action = random.choice(["room", "slot", "both"])

        if action in ("room", "both") and available_rooms:
            gene.room_id = random.choice(available_rooms)

        if action in ("slot", "both") and available_slots:
            # Try guided slot selection
            lec_id = courses.get(gene.course_id, {}).get("lecturer_id", "")
            guided = False
            if lec_id and lec_id in lecturers:
                lec = lecturers[lec_id]
                avail = lec.get("availability", {})
                unavail = lec.get("unavailable_slots", [])
                # Build candidate set from availability
                if avail:
                    allowed = {sid for sids in avail.values() for sid in sids}
                    candidates = [s for s in available_slots
                                  if s in allowed and s not in unavail]
                else:
                    candidates = [s for s in available_slots if s not in unavail]
                # Filter break/lunch slots
                candidates = [s for s in candidates
                              if slots_info.get(s, {}).get("slot_type", "class")
                              not in ("break", "lunch")
                              and not slots_info.get(s, {}).get("is_break", False)]
                if candidates:
                    gene.time_slot_id = random.choice(candidates)
                    guided = True
            if not guided:
                # Random fallback but still filter breaks
                clean = [s for s in available_slots
                         if slots_info.get(s, {}).get("slot_type", "class")
                         not in ("break", "lunch")
                         and not slots_info.get(s, {}).get("is_break", False)]
                gene.time_slot_id = random.choice(clean) if clean else random.choice(available_slots)

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

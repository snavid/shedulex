"""
Genetic Algorithm Engine — orchestrates the full evolution loop.

Algorithm:
  1. Pre-filter: exclude break/lunch slots from schedulable pool.
  2. Initialise guided population (respects availability + priority).
  3. Parallel fitness evaluation (ThreadPoolExecutor).
  4. Apply elitism (carry best N individuals).
  5. Tournament-select parents → crossover (single-point / two-point / uniform) → guided mutate → new gen.
  6. Stagnation escape: inject fresh random individuals when no improvement.
  7. Return best chromosome + violation report.
"""
from __future__ import annotations
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from functools import partial

from app.ga.chromosome import Chromosome
from app.ga.population import initialize_population
from app.ga.fitness import evaluate, violation_report
from app.ga.operators import (
    tournament_selection, single_point_crossover, two_point_crossover,
    uniform_crossover, mutate, adaptive_mutation_rate, elitism,
)

logger = logging.getLogger(__name__)

# Number of worker threads for parallel fitness evaluation.
# Keep ≤ 4 to avoid GIL contention on CPU-bound pure-Python work.
_EVAL_WORKERS = 4


@dataclass
class GAConfig:
    population_size: int = 100
    max_generations: int = 300
    elite_count: int = 5
    base_mutation_rate: float = 0.02
    crossover_rate: float = 0.85
    fitness_threshold: float = 0.95
    tournament_size: int = 5
    stagnation_limit: int = 50
    max_seconds: int = 0


@dataclass
class GAResult:
    best_chromosome: Chromosome
    best_fitness: float
    generations_run: int
    elapsed_seconds: float
    fitness_history: list[float] = field(default_factory=list)
    violations: list[dict] = field(default_factory=list)


def _parallel_evaluate(population: list[Chromosome], ctx: dict, workers: int) -> None:
    """Evaluate fitness in parallel and write scores back in-place."""
    def _eval_one(chrom: Chromosome) -> float:
        return evaluate(chrom, ctx)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_eval_one, c): i for i, c in enumerate(population)}
        for fut in as_completed(futures):
            idx = futures[fut]
            population[idx].fitness = fut.result()


def run_ga(
    courses: list[dict],
    rooms: list[dict],
    slots: list[dict],
    lecturers: dict,
    config: GAConfig | None = None,
    db_constraints: list[dict] | None = None,
    progress_callback=None,
) -> GAResult:
    """
    Main entry point for the genetic algorithm.

    Args:
        courses:           list of course dicts
        rooms:             list of room dicts
        slots:             list of time_slot dicts
        lecturers:         dict[lecturer_id → lecturer dict]
        config:            GAConfig (uses defaults if None)
        db_constraints:    list of active Constraint dicts from the database
        progress_callback: optional callable(generation, best_fitness)
    Returns:
        GAResult with best chromosome, statistics, and violation report
    """
    if not courses or not rooms or not slots:
        raise ValueError("courses, rooms, and slots must not be empty.")

    cfg = config or GAConfig()

    # Pre-filter: only schedulable (non-break/lunch) slots used for mutations
    schedulable_slots = [
        s for s in slots
        if s.get("slot_type", "class") not in ("break", "lunch")
        and not s.get("is_break", False)
    ] or slots  # fall back to all slots if nothing qualifies

    ctx = {
        "courses": {c["id"]: c for c in courses},
        "rooms": {r["id"]: r for r in rooms},
        "slots": {s["id"]: s for s in slots},
        "lecturers": lecturers,
        "db_constraints": db_constraints or [],
    }

    room_ids = [r["id"] for r in rooms]
    slot_ids = [s["id"] for s in schedulable_slots]
    slots_info = {s["id"]: s for s in schedulable_slots}

    start = time.perf_counter()

    # Step 1 – Smart population initialisation
    population = initialize_population(cfg.population_size, courses, rooms, slots, lecturers)

    # Step 2 – Initial parallel fitness evaluation
    _parallel_evaluate(population, ctx, _EVAL_WORKERS)

    best = max(population, key=lambda c: c.fitness).clone()
    fitness_history = [best.fitness]
    stagnation_count = 0
    generation = 0

    logger.info(
        "GA started: %d courses, pop=%d, max_gen=%d",
        len(courses), cfg.population_size, cfg.max_generations,
    )

    for generation in range(1, cfg.max_generations + 1):
        if cfg.max_seconds > 0 and (time.perf_counter() - start) >= cfg.max_seconds:
            logger.info("GA timed out at generation %d (%.1fs limit reached)", generation, cfg.max_seconds)
            break

        # Step 3 – Elitism
        new_population = elitism(population, cfg.elite_count)

        mutation_rate = adaptive_mutation_rate(
            generation, cfg.max_generations, cfg.base_mutation_rate,
        )

        pending: list[Chromosome] = []

        while len(new_population) + len(pending) < cfg.population_size:
            p1 = tournament_selection(population, cfg.tournament_size)
            p2 = tournament_selection(population, cfg.tournament_size)

            # Rotate crossover strategies for diversity
            mode = generation % 3
            if mode == 0:
                c1, c2 = uniform_crossover(p1, p2)
            elif mode == 1:
                c1, c2 = two_point_crossover(p1, p2)
            else:
                c1, c2 = single_point_crossover(p1, p2)

            c1 = mutate(c1, mutation_rate, room_ids, slot_ids, lecturers, ctx["courses"], slots_info)
            c2 = mutate(c2, mutation_rate, room_ids, slot_ids, lecturers, ctx["courses"], slots_info)
            pending.extend([c1, c2])

        # Parallel evaluation of new children
        _parallel_evaluate(pending, ctx, _EVAL_WORKERS)
        new_population.extend(pending)
        population = new_population[:cfg.population_size]

        gen_best = max(population, key=lambda c: c.fitness)
        fitness_history.append(gen_best.fitness)

        if gen_best.fitness > best.fitness:
            best = gen_best.clone()
            stagnation_count = 0
        else:
            stagnation_count += 1

        if progress_callback:
            progress_callback(generation, best.fitness)

        if best.fitness >= cfg.fitness_threshold:
            logger.info(
                "Fitness threshold %.2f reached at generation %d",
                cfg.fitness_threshold, generation,
            )
            break

        if stagnation_count >= cfg.stagnation_limit:
            logger.debug("Stagnation at gen %d, injecting diversity", generation)
            inject_count = cfg.population_size // 5
            fresh = initialize_population(inject_count, courses, rooms, slots, lecturers)
            _parallel_evaluate(fresh, ctx, _EVAL_WORKERS)
            population[-inject_count:] = fresh
            stagnation_count = 0

    elapsed = time.perf_counter() - start
    logger.info(
        "GA done: gen=%d, best_fitness=%.4f, time=%.2fs",
        generation, best.fitness, elapsed,
    )

    violations = violation_report(best, ctx)

    return GAResult(
        best_chromosome=best,
        best_fitness=best.fitness,
        generations_run=generation,
        elapsed_seconds=elapsed,
        fitness_history=fitness_history,
        violations=violations,
    )

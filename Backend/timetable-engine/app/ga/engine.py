"""
Genetic Algorithm Engine — orchestrates the full evolution loop.

Algorithm:
  1. Initialise random population
  2. Evaluate fitness for each chromosome
  3. Apply elitism (carry best N individuals)
  4. Tournament-select parents → crossover → mutate → new generation
  5. Repeat until max_generations reached or fitness_threshold met
  6. Return the best chromosome found
"""
from __future__ import annotations
import time
import logging
from dataclasses import dataclass, field
from app.ga.chromosome import Chromosome
from app.ga.population import initialize_population
from app.ga.fitness import evaluate
from app.ga.operators import (
    tournament_selection, single_point_crossover, uniform_crossover,
    mutate, adaptive_mutation_rate, elitism,
)

logger = logging.getLogger(__name__)


@dataclass
class GAConfig:
    population_size: int = 100
    max_generations: int = 300
    elite_count: int = 5
    base_mutation_rate: float = 0.02
    crossover_rate: float = 0.85
    fitness_threshold: float = 0.95
    tournament_size: int = 5
    stagnation_limit: int = 50  # restart mutation if no improvement


@dataclass
class GAResult:
    best_chromosome: Chromosome
    best_fitness: float
    generations_run: int
    elapsed_seconds: float
    fitness_history: list[float] = field(default_factory=list)


def run_ga(
    courses: list[dict],
    rooms: list[dict],
    slots: list[dict],
    lecturers: dict,
    config: GAConfig | None = None,
    progress_callback=None,
) -> GAResult:
    """
    Main entry point for the genetic algorithm.

    Args:
        courses:           list of course dicts (id, lecturer_id, student_count, …)
        rooms:             list of room dicts (id, capacity, room_type, …)
        slots:             list of time_slot dicts (id, day, slot_index, is_break, …)
        lecturers:         dict[lecturer_id → lecturer dict with availability]
        config:            GAConfig (uses defaults if None)
        progress_callback: optional callable(generation, best_fitness) for real-time updates
    Returns:
        GAResult with the best chromosome and statistics
    """
    if not courses or not rooms or not slots:
        raise ValueError("courses, rooms, and slots must not be empty.")

    cfg = config or GAConfig()
    ctx = {
        "courses": {c["id"]: c for c in courses},
        "rooms": {r["id"]: r for r in rooms},
        "slots": {s["id"]: s for s in slots},
        "lecturers": lecturers,
    }
    room_ids = [r["id"] for r in rooms]
    slot_ids = [s["id"] for s in slots]

    start = time.perf_counter()

    # Step 1 – Initialise
    population = initialize_population(cfg.population_size, courses, rooms, slots)

    # Step 2 – Initial fitness evaluation
    for chrom in population:
        chrom.fitness = evaluate(chrom, ctx)

    best = max(population, key=lambda c: c.fitness).clone()
    fitness_history = [best.fitness]
    stagnation_count = 0
    generation = 0

    logger.info(f"GA started: {len(courses)} courses, pop={cfg.population_size}, max_gen={cfg.max_generations}")

    for generation in range(1, cfg.max_generations + 1):
        # Step 3 – Elitism
        new_population = elitism(population, cfg.elite_count)

        # Step 4 – Selection + crossover + mutation
        mutation_rate = adaptive_mutation_rate(generation, cfg.max_generations, cfg.base_mutation_rate)

        while len(new_population) < cfg.population_size:
            p1 = tournament_selection(population, cfg.tournament_size)
            p2 = tournament_selection(population, cfg.tournament_size)

            if generation % 5 == 0:
                # Alternate crossover strategies for diversity
                c1, c2 = uniform_crossover(p1, p2)
            else:
                c1, c2 = single_point_crossover(p1, p2)

            c1 = mutate(c1, mutation_rate, rooms, slots)
            c2 = mutate(c2, mutation_rate, rooms, slots)

            c1.fitness = evaluate(c1, ctx)
            c2.fitness = evaluate(c2, ctx)

            new_population.extend([c1, c2])

        population = new_population[:cfg.population_size]

        # Track best
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
            logger.info(f"Fitness threshold {cfg.fitness_threshold} reached at generation {generation}")
            break

        # Stagnation escape: inject new random individuals
        if stagnation_count >= cfg.stagnation_limit:
            logger.debug(f"Stagnation at gen {generation}, injecting diversity")
            inject_count = cfg.population_size // 5
            new_individuals = initialize_population(inject_count, courses, rooms, slots)
            for ind in new_individuals:
                ind.fitness = evaluate(ind, ctx)
            population[-inject_count:] = new_individuals
            stagnation_count = 0

    elapsed = time.perf_counter() - start
    logger.info(f"GA completed: gen={generation}, best_fitness={best.fitness:.4f}, time={elapsed:.2f}s")

    return GAResult(
        best_chromosome=best,
        best_fitness=best.fitness,
        generations_run=generation,
        elapsed_seconds=elapsed,
        fitness_history=fitness_history,
    )

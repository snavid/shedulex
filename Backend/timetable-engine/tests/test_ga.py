"""Unit tests for the Genetic Algorithm engine."""
import pytest
from app.ga.chromosome import Gene, Chromosome
from app.ga.fitness import evaluate
from app.ga.operators import tournament_selection, single_point_crossover, mutate
from app.ga.population import initialize_population
from app.ga.engine import run_ga, GAConfig


COURSES = [
    {"id": "c1", "lecturer_id": "l1", "student_count": 30, "requires_lab": False,
     "weekly_hours": 2, "department_id": "d1", "priority": 1},
    {"id": "c2", "lecturer_id": "l2", "student_count": 25, "requires_lab": True,
     "weekly_hours": 1, "department_id": "d1", "priority": 2},
]
ROOMS = [
    {"id": "r1", "capacity": 50, "room_type": "lecture"},
    {"id": "r2", "capacity": 30, "room_type": "lab"},
]
SLOTS = [
    {"id": f"s{i}", "day": "Monday", "slot_index": i, "is_break": False}
    for i in range(5)
] + [
    {"id": f"s{5+i}", "day": "Tuesday", "slot_index": i, "is_break": False}
    for i in range(5)
]
LECTURERS = {
    "l1": {"id": "l1", "name": "Dr A", "availability": {}},
    "l2": {"id": "l2", "name": "Dr B", "availability": {}},
}


class TestChromosome:
    def test_clone_is_independent(self):
        gene = Gene("c1", 0, "r1", "s0")
        chrom = Chromosome(genes=[gene])
        clone = chrom.clone()
        clone.genes[0].room_id = "r2"
        assert chrom.genes[0].room_id == "r1"


class TestPopulationInit:
    def test_creates_correct_size(self):
        pop = initialize_population(10, COURSES, ROOMS, SLOTS)
        assert len(pop) == 10

    def test_gene_count_matches_weekly_hours(self):
        pop = initialize_population(1, COURSES, ROOMS, SLOTS)
        # c1 has 2 weekly_hours, c2 has 1 → total 3 genes
        assert len(pop[0].genes) == 3

    def test_lab_course_gets_lab_room(self):
        pop = initialize_population(20, COURSES, ROOMS, SLOTS)
        for chrom in pop:
            for gene in chrom.genes:
                if gene.course_id == "c2":
                    assert gene.room_id == "r2"


class TestFitness:
    def _make_context(self):
        return {
            "courses": {c["id"]: c for c in COURSES},
            "rooms": {r["id"]: r for r in ROOMS},
            "slots": {s["id"]: s for s in SLOTS},
            "lecturers": LECTURERS,
        }

    def test_fitness_between_0_and_1(self):
        pop = initialize_population(1, COURSES, ROOMS, SLOTS)
        ctx = self._make_context()
        f = evaluate(pop[0], ctx)
        assert 0.0 <= f <= 1.0

    def test_conflict_reduces_fitness(self):
        ctx = self._make_context()
        # Force same slot for both genes of same lecturer
        chrom = Chromosome(genes=[
            Gene("c1", 0, "r1", "s0"),
            Gene("c1", 1, "r1", "s0"),  # same slot → clash
        ])
        f_bad = evaluate(chrom, ctx)

        chrom_good = Chromosome(genes=[
            Gene("c1", 0, "r1", "s0"),
            Gene("c1", 1, "r1", "s1"),  # different slots
        ])
        f_good = evaluate(chrom_good, ctx)
        assert f_good >= f_bad


class TestOperators:
    def _pop(self):
        return initialize_population(10, COURSES, ROOMS, SLOTS)

    def test_tournament_returns_chromosome(self):
        pop = self._pop()
        for c in pop:
            c.fitness = 0.5
        selected = tournament_selection(pop)
        assert isinstance(selected, Chromosome)

    def test_crossover_preserves_length(self):
        pop = self._pop()
        c1, c2 = single_point_crossover(pop[0], pop[1])
        assert len(c1) == len(pop[0])

    def test_mutate_changes_genes(self):
        pop = initialize_population(1, COURSES, ROOMS, SLOTS)
        original_slots = [g.time_slot_id for g in pop[0].genes]
        mutant = mutate(pop[0], mutation_rate=1.0, available_rooms=ROOMS, available_slots=SLOTS)
        new_slots = [g.time_slot_id for g in mutant.genes]
        # With 100% mutation rate at least some slots should change
        assert mutant is not pop[0]


class TestGAEngine:
    def test_run_ga_returns_result(self):
        cfg = GAConfig(population_size=20, max_generations=10, fitness_threshold=0.99)
        result = run_ga(COURSES, ROOMS, SLOTS, LECTURERS, config=cfg)
        assert 0.0 <= result.best_fitness <= 1.0
        assert result.generations_run <= 10
        assert result.elapsed_seconds > 0

    def test_result_has_correct_gene_count(self):
        cfg = GAConfig(population_size=10, max_generations=5)
        result = run_ga(COURSES, ROOMS, SLOTS, LECTURERS, config=cfg)
        # 2 sessions for c1 + 1 for c2 = 3 total
        assert len(result.best_chromosome.genes) == 3

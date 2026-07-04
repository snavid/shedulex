"""Tests for shared_room constraints and ConstraintIndex."""
import pytest
from app.ga.chromosome import Gene, Chromosome
from app.ga.constraint_index import ConstraintIndex, filter_constraints_for_generation
from app.ga.fitness import evaluate, violation_report
from app.ga.population import initialize_population
from app.ga.operators import mutate


ROOMS = [
    {"id": "r1", "capacity": 50, "room_type": "lecture", "name": "Hall A"},
    {"id": "r2", "capacity": 30, "room_type": "lab", "name": "Lab B"},
    {"id": "r3", "capacity": 40, "room_type": "lecture", "name": "CS Lab"},
]
SLOTS = [
    {"id": f"s{i}", "day": "Monday", "slot_index": i, "is_break": False,
     "slot_type": "class", "start_time": f"0{8+i}:00", "end_time": f"0{9+i}:00"}
    for i in range(5)
]
COURSES_CS = [
    {"id": "c1", "lecturer_id": "l1", "student_count": 30, "requires_lab": False,
     "weekly_hours": 1, "department_id": "dept-cs", "priority": 1, "name": "CS101"},
]
COURSES_IT = [
    {"id": "c2", "lecturer_id": "l2", "student_count": 25, "requires_lab": False,
     "weekly_hours": 1, "department_id": "dept-it", "priority": 1, "name": "IT101"},
]
LECTURERS = {
    "l1": {"id": "l1", "name": "Dr CS", "availability": {}},
    "l2": {"id": "l2", "name": "Dr IT", "availability": {}},
}


def _shared_room_constraint(room_id: str, allowed: list[str], order: list[str] | None = None,
                            weights: dict | None = None):
    return {
        "id": "cstr-1",
        "is_active": True,
        "constraint_type": "hard",
        "rule_type": "shared_room",
        "entity_type": "room",
        "entity_id": room_id,
        "weight": 1.0,
        "config": {
            "allowed_department_ids": allowed,
            "priority_order": order or allowed,
            "department_weights": weights or {},
        },
    }


class TestConstraintIndex:
    def test_exclusive_room_blocks_other_dept(self):
        idx = ConstraintIndex([_shared_room_constraint("r3", ["dept-cs"])])
        assert idx.room_allowed("r3", "dept-cs")
        assert not idx.room_allowed("r3", "dept-it")
        assert idx.room_allowed("r1", "dept-it")

    def test_priority_penalty_increases_with_rank(self):
        c = _shared_room_constraint(
            "r3", ["dept-cs", "dept-it", "dept-biz"],
            order=["dept-cs", "dept-it", "dept-biz"],
        )
        idx = ConstraintIndex([c])
        assert idx.room_priority_penalty("r3", "dept-cs") == 0.0
        assert idx.room_priority_penalty("r3", "dept-it") == 25.0
        assert idx.room_priority_penalty("r3", "dept-biz") == 50.0

    def test_department_weights_override_rank(self):
        c = _shared_room_constraint(
            "r3", ["dept-cs", "dept-it"],
            weights={"dept-cs": 1.0, "dept-it": 0.5},
        )
        idx = ConstraintIndex([c])
        assert idx.room_priority_penalty("r3", "dept-it") == pytest.approx(12.5)

    def test_filter_by_university(self):
        constraints = [
            {"is_active": True, "university_id": "u1", "rule_type": "shared_room"},
            {"is_active": True, "university_id": "u2", "rule_type": "shared_room"},
        ]
        filtered = filter_constraints_for_generation(constraints, university_id="u1")
        assert len(filtered) == 1


class TestSharedRoomFitness:
    def _ctx(self, dept_id: str, constraints: list):
        idx = ConstraintIndex(constraints)
        return {
            "courses": {c["id"]: c for c in (COURSES_CS if dept_id == "dept-cs" else COURSES_IT)},
            "rooms": {r["id"]: r for r in ROOMS},
            "slots": {s["id"]: s for s in SLOTS},
            "lecturers": LECTURERS,
            "db_constraints": constraints,
            "constraint_index": idx,
            "external_bookings": {"room": {}, "lecturer": {}},
        }

    def test_it_using_cs_only_room_low_fitness(self):
        constraints = [_shared_room_constraint("r3", ["dept-cs"])]
        chrom = Chromosome(genes=[
            Gene("c2", 0, "r3", "s0", student_group_id=""),
        ])
        f = evaluate(chrom, self._ctx("dept-it", constraints))
        assert f < 0.95

    def test_cs_using_cs_only_room_ok(self):
        constraints = [_shared_room_constraint("r3", ["dept-cs"])]
        chrom = Chromosome(genes=[
            Gene("c1", 0, "r3", "s0", student_group_id=""),
        ])
        f = evaluate(chrom, self._ctx("dept-cs", constraints))
        assert f > 0.9

    def test_violation_report_for_blocked_dept(self):
        constraints = [_shared_room_constraint("r3", ["dept-cs"])]
        chrom = Chromosome(genes=[Gene("c2", 0, "r3", "s0")])
        ctx = self._ctx("dept-it", constraints)
        violations = violation_report(chrom, ctx)
        assert any("department not allowed" in v["rule"].lower() for v in violations)


class TestPopulationRoomFilter:
    def test_population_respects_exclusive_room(self):
        constraints = [_shared_room_constraint("r3", ["dept-cs"])]
        idx = ConstraintIndex(constraints)
        pop = initialize_population(
            15, COURSES_IT, ROOMS, SLOTS, LECTURERS,
            generating_department_id="dept-it",
            constraint_index=idx,
        )
        for chrom in pop:
            for gene in chrom.genes:
                assert gene.room_id != "r3"

    def test_mutate_respects_exclusive_room(self):
        constraints = [_shared_room_constraint("r3", ["dept-cs"])]
        idx = ConstraintIndex(constraints)
        chrom = Chromosome(genes=[Gene("c2", 0, "r3", "s0")])
        for _ in range(30):
            mutant = mutate(
                chrom, 1.0, [r["id"] for r in ROOMS], [s["id"] for s in SLOTS],
                LECTURERS, {"c2": COURSES_IT[0]}, {s["id"]: s for s in SLOTS},
                generating_department_id="dept-it",
                constraint_index=idx,
                rooms=ROOMS,
            )
            assert mutant.genes[0].room_id != "r3"

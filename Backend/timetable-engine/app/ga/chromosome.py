"""
A chromosome represents one complete candidate timetable solution.
Each gene maps a (course_id, session_index) → (room_id, time_slot_id).
"""
from __future__ import annotations
import random
import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Gene:
    course_id: str
    session_index: int   # which weekly session for this course (0-based)
    room_id: str
    time_slot_id: str

    def clone(self) -> "Gene":
        return Gene(self.course_id, self.session_index, self.room_id, self.time_slot_id)


@dataclass
class Chromosome:
    genes: list[Gene] = field(default_factory=list)
    fitness: float = 0.0

    def clone(self) -> "Chromosome":
        c = Chromosome(genes=[g.clone() for g in self.genes])
        c.fitness = self.fitness
        return c

    def __len__(self):
        return len(self.genes)

    def __repr__(self):
        return f"<Chromosome genes={len(self.genes)} fitness={self.fitness:.4f}>"

"""
Population initialisation — creates a random but structurally valid initial population.
Each chromosome contains one gene per (course, session_index) pair.
"""
from __future__ import annotations
import random
from app.ga.chromosome import Chromosome, Gene


def initialize_population(
    size: int,
    courses: list[dict],
    rooms: list[str],
    slots: list[str],
) -> list[Chromosome]:
    """
    courses: list of dicts with keys id, weekly_hours, requires_lab
    rooms:   list of room_ids
    slots:   list of slot_ids
    """
    population: list[Chromosome] = []
    lab_rooms = [r for r in rooms if r.get("room_type") == "lab"]
    lecture_rooms = [r for r in rooms if r.get("room_type") != "lab"]

    for _ in range(size):
        genes: list[Gene] = []
        for course in courses:
            sessions = course.get("weekly_hours", 1)
            for session_idx in range(sessions):
                if course.get("requires_lab") and lab_rooms:
                    room_id = random.choice(lab_rooms)["id"]
                elif lecture_rooms:
                    room_id = random.choice(lecture_rooms)["id"]
                else:
                    room_id = random.choice(rooms)["id"] if rooms else "unknown"

                slot_id = random.choice(slots)["id"] if slots else "unknown"
                genes.append(Gene(
                    course_id=course["id"],
                    session_index=session_idx,
                    room_id=room_id,
                    time_slot_id=slot_id,
                ))
        population.append(Chromosome(genes=genes))
    return population

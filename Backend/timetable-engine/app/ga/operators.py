"""
Genetic operators: selection, crossover, mutation.

Selection  – Tournament selection (size k=5)
Crossover  – Single-point crossover (preserves gene integrity)
Mutation   – Random gene reassignment with adaptive rate
Elitism    – Top N chromosomes carried over unchanged
"""
from __future__ import annotations
import random
import copy
from app.ga.chromosome import Chromosome, Gene


def tournament_selection(population: list[Chromosome], tournament_size: int = 5) -> Chromosome:
    candidates = random.sample(population, min(tournament_size, len(population)))
    return max(candidates, key=lambda c: c.fitness).clone()


def single_point_crossover(parent1: Chromosome, parent2: Chromosome) -> tuple[Chromosome, Chromosome]:
    if len(parent1) < 2 or len(parent2) < 2:
        return parent1.clone(), parent2.clone()

    point = random.randint(1, min(len(parent1), len(parent2)) - 1)
    child1_genes = parent1.genes[:point] + parent2.genes[point:]
    child2_genes = parent2.genes[:point] + parent1.genes[point:]
    return Chromosome(genes=[g.clone() for g in child1_genes]), \
           Chromosome(genes=[g.clone() for g in child2_genes])


def uniform_crossover(parent1: Chromosome, parent2: Chromosome) -> tuple[Chromosome, Chromosome]:
    """Swap genes at random positions — produces more diverse offspring."""
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


def mutate(chromosome: Chromosome, mutation_rate: float, available_rooms: list[str], available_slots: list[str]) -> Chromosome:
    """Replace room or time_slot for randomly selected genes."""
    mutant = chromosome.clone()
    for gene in mutant.genes:
        if random.random() < mutation_rate:
            # Randomly choose: mutate room, slot, or both
            action = random.choice(["room", "slot", "both"])
            if action in ("room", "both") and available_rooms:
                gene.room_id = random.choice(available_rooms)
            if action in ("slot", "both") and available_slots:
                gene.time_slot_id = random.choice(available_slots)
    return mutant


def adaptive_mutation_rate(generation: int, max_generations: int, base_rate: float = 0.02, max_rate: float = 0.15) -> float:
    """Increase mutation rate as generations progress to escape local optima."""
    progress = generation / max(max_generations, 1)
    return base_rate + (max_rate - base_rate) * progress


def elitism(population: list[Chromosome], elite_count: int) -> list[Chromosome]:
    sorted_pop = sorted(population, key=lambda c: c.fitness, reverse=True)
    return [c.clone() for c in sorted_pop[:elite_count]]

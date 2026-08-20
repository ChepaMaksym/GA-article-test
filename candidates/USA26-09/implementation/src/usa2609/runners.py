from __future__ import annotations

from hashlib import sha256
from typing import Sequence

import numpy as np

from .core import MTSPInstance, nearest_neighbor_order, population_digest, split_minmax
from .controls import Roulette, RunResult, lambda_controls, update_lambda
from .operators import (
    adjacency_surrogate, apply_edit, apply_move, guided_move, order_crossover,
    positive_binomial, sample_edit,
)

class ObjectiveCounter:
    def __init__(self, instance: MTSPInstance, budget: int, target: float):
        self.instance = instance
        self.budget = int(budget)
        self.target = float(target)
        self.calls = 0
        self.first_hit: int | None = None
        self.cache: dict[tuple[int, ...], float] = {}

    def evaluate(self, order: Sequence[int]) -> float:
        if self.calls >= self.budget:
            raise RuntimeError("evaluation budget exhausted")
        key = tuple(int(x) for x in order)
        self.calls += 1
        if key not in self.cache:
            self.cache[key] = float(split_minmax(key, self.instance))
        value = self.cache[key]
        if self.first_hit is None and value <= self.target:
            self.first_hit = self.calls
        return value


def generate_initial_population(instance: MTSPInstance, seed: int, size: int = 40) -> tuple[tuple[int, ...], ...]:
    if size < 4:
        raise ValueError("initial population size must be >= 4")
    rng = np.random.default_rng(seed ^ 0xA5A5A5A5)
    base = nearest_neighbor_order(instance)
    population: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()
    # A deterministic range of perturbation depths; exact base is deliberately excluded.
    while len(population) < size:
        candidate = base
        depth = int(rng.integers(2, 11))
        for _ in range(depth):
            move = int(rng.integers(0, 4))
            candidate = apply_move(candidate, move, rng)
        if candidate != base and candidate not in seen:
            seen.add(candidate)
            population.append(candidate)
    return tuple(population)


def _evaluate_initial(counter: ObjectiveCounter, population: Sequence[Sequence[int]]) -> list[tuple[float, tuple[int, ...]]]:
    evaluated = [(counter.evaluate(order), tuple(order)) for order in population]
    evaluated.sort(key=lambda item: (item[0], item[1]))
    return evaluated


def run_old(instance: MTSPInstance, seed: int, budget: int = 1500, target: float = 1.830, population_size: int = 40) -> RunResult:
    rng = np.random.default_rng(seed)
    initial = generate_initial_population(instance, seed, population_size)
    init_digest = population_digest(initial)
    counter = ObjectiveCounter(instance, budget, target)
    population = _evaluate_initial(counter, initial)
    roulette = Roulette()
    generations = 0
    while counter.calls < budget:
        top = population[: min(12, len(population))]
        idxs = rng.choice(len(top), size=min(3, len(top)), replace=False)
        parent_value, parent = min((top[int(i)] for i in idxs), key=lambda x: (x[0], x[1]))
        mate = top[int(rng.integers(0, len(top)))][1]
        child = order_crossover(parent, mate, rng) if rng.random() < 0.70 else parent
        move_index = roulette.choose(rng)
        child = guided_move(child, move_index, rng, instance, trials=6)
        value = counter.evaluate(child)
        roulette.reward(move_index, value < parent_value)
        population.append((value, child))
        population.sort(key=lambda item: (item[0], item[1]))
        # Keep diversity, then fill to requested size.
        unique: list[tuple[float, tuple[int, ...]]] = []
        seen: set[tuple[int, ...]] = set()
        for item in population:
            if item[1] not in seen:
                unique.append(item)
                seen.add(item[1])
            if len(unique) == population_size:
                break
        population = unique
        generations += 1
    best_value, best_order = population[0]
    return RunResult(
        seed=seed,
        method="OLD",
        final_objective=best_value,
        first_hit_nfe=counter.first_hit,
        logical_nfe=counter.calls,
        generations=generations,
        initial_population_digest=init_digest,
        final_order_digest=sha256(np.asarray(best_order, dtype="<i4").tobytes()).hexdigest(),
        roulette_weights=tuple(int(x) for x in roulette.weights),
    )


def run_hybrid(
    instance: MTSPInstance,
    seed: int,
    budget: int = 1500,
    target: float = 1.830,
    population_size: int = 40,
    factor: float = 1.5,
    reset: bool = True,
) -> RunResult:
    rng = np.random.default_rng(seed)
    initial = generate_initial_population(instance, seed, population_size)
    init_digest = population_digest(initial)
    counter = ObjectiveCounter(instance, budget, target)
    evaluated = _evaluate_initial(counter, initial)
    incumbent_value, incumbent = evaluated[0]
    roulette = Roulette()
    lambda_value = 1.0
    lambda_trace: list[float] = [lambda_value]
    lambda_max = lambda_value
    reset_events = 0
    generations = 0
    n = len(incumbent)
    while counter.calls < budget:
        p, c, offspring = lambda_controls(lambda_value, n)
        remaining = budget - counter.calls
        mutant_count = min(offspring, remaining)
        if mutant_count <= 0:
            break
        L = positive_binomial(rng, n, p)
        previous_best = incumbent_value
        mutants: list[tuple[float, tuple[int, ...], tuple[tuple[int, tuple[int, ...]], ...]]] = []
        for _ in range(mutant_count):
            edits: list[tuple[int, tuple[int, ...]]] = []
            mutant = incumbent
            for _edit in range(L):
                move_index = roulette.choose(rng)
                # Sample several legal edits and retain the one with the best
                # cheap route-adjacency surrogate.  This is the same education
                # principle used by OLD; lambda controls its adaptive depth.
                proposals = [sample_edit(mutant, move_index, rng) for _ in range(max(4, offspring))]
                edit = min(
                    proposals,
                    key=lambda e: (adjacency_surrogate(apply_edit(mutant, e), instance), e),
                )
                mutant = apply_edit(mutant, edit)
                edits.append(edit)
            value = counter.evaluate(mutant)
            mutants.append((value, mutant, tuple(edits)))
            if counter.calls >= budget:
                break
        best_mutant_value, best_mutant, best_edits = min(mutants, key=lambda x: (x[0], x[1]))
        candidates: list[tuple[float, tuple[int, ...], tuple[tuple[int, tuple[int, ...]], ...]]] = list(mutants)
        cross_count = min(len(mutants), budget - counter.calls)
        # One crossover per independently sampled mutant preserves the intended
        # mutation/crossover phase separation and avoids conditioning every
        # crossover on a single mutation path.
        for _value, _mutant, edits in mutants[:cross_count]:
            chosen = [edit for edit in edits if rng.random() < c]
            if not chosen:
                chosen = [edits[int(rng.integers(0, len(edits)))]]
            child = incumbent
            for edit in chosen:
                child = apply_edit(child, edit)
            value = counter.evaluate(child)
            candidates.append((value, child, tuple(chosen)))
        best_value, best_order, winning_edits = min(candidates, key=lambda x: (x[0], x[1]))
        strict_success = best_value < previous_best
        accepted = best_value <= previous_best
        if strict_success:
            for move_index in {edit[0] for edit in winning_edits}:
                roulette.reward(move_index, True)
        before = lambda_value
        lambda_value = update_lambda(lambda_value, strict_success, n, factor, reset)
        if reset and before == float(n) and not strict_success and lambda_value == 1.0:
            reset_events += 1
        lambda_max = max(lambda_max, before, lambda_value)
        lambda_trace.append(lambda_value)
        if accepted:
            incumbent_value, incumbent = best_value, best_order
        generations += 1
    return RunResult(
        seed=seed,
        method="HYBRID" if reset else "HYBRID_NO_RESET",
        final_objective=incumbent_value,
        first_hit_nfe=counter.first_hit,
        logical_nfe=counter.calls,
        generations=generations,
        initial_population_digest=init_digest,
        final_order_digest=sha256(np.asarray(incumbent, dtype="<i4").tobytes()).hexdigest(),
        roulette_weights=tuple(int(x) for x in roulette.weights),
        lambda_max=lambda_max,
        reset_events=reset_events,
        lambda_trace=tuple(lambda_trace),
    )


"""Independent non-vendored replay of the published Jump fixture."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import random
from typing import Any

import numpy as np

from .canonical import ARTIFACT_JUMP_OPTIMIZED, controls, jump_fitness, next_lambda


@dataclass(frozen=True)
class RunRow:
    run: int
    effective_seed: int
    generations: int
    evaluations: int
    final_lambda: int
    last_mutation_probability: float
    solved: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mutate(parent: int, n: int, strength: int) -> int:
    indexes = np.random.choice(n, size=strength, replace=False)
    mask = sum(2 ** int(index) for index in indexes)
    return int(mask ^ parent)


def _crossover(parent: int, second_parent: int, n: int, probability: float) -> int:
    choices = np.random.choice(
        [False, True], n, p=[1.0 - probability, probability]
    )
    first_bits = format(parent, f"0{n}b")
    second_bits = format(second_parent, f"0{n}b")
    child = [second_bits[i] if choices[i] else first_bits[i] for i in range(n)]
    return int("".join(child), 2)


def _select_best_mutant(offspring: list[tuple[tuple[int, bool], int]]) -> int:
    best_evaluation = max(offspring)[0]
    best = [child for evaluation, child in offspring if evaluation[0] == best_evaluation[0]]
    return int(np.random.choice(np.array(best, dtype="object"), 1)[0])


def _select_final(
    offspring: list[tuple[tuple[int, bool], int]],
    parent: int,
    parent_evaluation: tuple[int, bool],
) -> tuple[int, tuple[int, bool], int, bool]:
    eligible = [child for child in offspring if child[1] != parent]
    if not eligible:
        return parent, parent_evaluation, 0, False
    best_evaluation = max(eligible)[0]
    fitter = [child for evaluation, child in eligible if evaluation[0] > parent_evaluation[0]]
    best = [child for evaluation, child in eligible if evaluation[0] == best_evaluation[0]]
    selected = int(np.random.choice(np.array(best, dtype="object"), 1)[0])
    if best_evaluation[0] >= parent_evaluation[0]:
        return selected, best_evaluation, len(fitter), bool(best_evaluation[1])
    return parent, parent_evaluation, len(fitter), bool(best_evaluation[1])


def _local_optimum_direct_crossover(
    parent: int,
    n: int,
    k: int,
    probability: float,
) -> bool:
    strengths = np.random.binomial(n, probability, n)
    found = False
    for strength in strengths[strengths == k]:
        child = _mutate(parent, n, int(strength))
        if jump_fitness(child, n, k)[1]:
            found = True
    return found


def run_artifact_jump_optimized(
    run: int,
    *,
    base_seed: int = 816_114_841,
    n: int = 20,
    k: int = 4,
    update_factor: float = 1.5,
    lambda_max: float = 20.0,
    max_generations: int | None = None,
) -> RunRow:
    """Replay the problem-specific class used for the author raw ledger.

    The implementation intentionally reproduces the shortcut RNG consumption
    and logical accounting.  It is not the default paper-faithful profile.
    """

    if isinstance(run, bool) or not isinstance(run, int) or run < 1:
        raise ValueError("run must be a positive integer")
    if n != 20 or k != 4 or update_factor != 1.5 or lambda_max != 20.0:
        raise ValueError("raw-compatible runner is restricted to the frozen fixture")
    effective_seed = int(base_seed) + run
    np.random.seed(effective_seed)
    random.seed(effective_seed)

    parent = random.randint(0, 2**n - 1)
    parent_evaluation = jump_fitness(parent, n, k)
    lambda_real = 1.0
    solved = False
    generations = 0
    evaluations = 0
    final_lambda = 1
    last_probability = 1.0 / n

    while not solved:
        if max_generations is not None and generations >= max_generations:
            raise RuntimeError("max_generations reached before the optimum")
        ctl = controls(lambda_real, n, ARTIFACT_JUMP_OPTIMIZED)
        m = ctl.offspring_count
        final_lambda = m
        last_probability = ctl.mutation_probability
        strength = int(np.random.binomial(n, ctl.mutation_probability))
        success_count = 0
        offspring: list[tuple[tuple[int, bool], int]] = []
        at_local_optimum = parent_evaluation[0] == n

        if at_local_optimum and m == n:
            solved = _local_optimum_direct_crossover(
                parent, n, k, ctl.crossover_probability
            )
        elif at_local_optimum:
            if strength >= k:
                for _ in range(m):
                    child = _mutate(parent, n, strength)
                    offspring.append((jump_fitness(child, n, k), child))
                selected_mutant = _select_best_mutant(offspring)
                if (selected_mutant | parent) == (1 << n) - 1:
                    for _ in range(m):
                        child = _crossover(
                            parent, selected_mutant, n, ctl.crossover_probability
                        )
                        offspring.append((jump_fitness(child, n, k), child))
                    parent, parent_evaluation, success_count, found = _select_final(
                        offspring, parent, parent_evaluation
                    )
                    solved = solved or found
        elif strength > 0:
            for _ in range(m):
                child = _mutate(parent, n, strength)
                offspring.append((jump_fitness(child, n, k), child))
            selected_mutant = _select_best_mutant(offspring)
            for _ in range(m):
                child = _crossover(
                    parent, selected_mutant, n, ctl.crossover_probability
                )
                offspring.append((jump_fitness(child, n, k), child))
            parent, parent_evaluation, success_count, found = _select_final(
                offspring, parent, parent_evaluation
            )
            solved = solved or found

        evaluations += 2 * m
        generations += 1
        lambda_real = next_lambda(
            lambda_real,
            strict_success=success_count > 0,
            update_factor=update_factor,
            lambda_max=lambda_max,
            reset=True,
        )

    return RunRow(
        run=run,
        effective_seed=effective_seed,
        generations=generations,
        evaluations=evaluations,
        final_lambda=final_lambda,
        last_mutation_probability=last_probability,
        solved=True,
    )

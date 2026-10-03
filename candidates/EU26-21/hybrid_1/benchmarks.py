"""Deterministic control benchmarks for Hybrid 1."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import statistics
from typing import Dict, Iterable, List, Sequence, Tuple

from .core import Fitness, Mask, RunResult, run_reset_lambda_ga


@dataclass(frozen=True)
class JumpObjective:
    k: int

    def __call__(self, mask: Mask) -> Fitness:
        n = len(mask)
        if not 2 <= self.k < n:
            raise ValueError("Jump requires 2 <= k < n")
        ones = sum(mask)
        value = (
            self.k + ones
            if ones <= n - self.k or ones == n
            else n - ones
        )
        return float(value), 0.0


@dataclass(frozen=True)
class OneMaxObjective:
    def __call__(self, mask: Mask) -> Fitness:
        return float(sum(mask)), 0.0


def jump_local_optimum(n: int, k: int) -> Mask:
    if not 2 <= k < n:
        raise ValueError("Jump requires 2 <= k < n")
    return tuple([1] * (n - k) + [0] * k)


def _compact(result: RunResult) -> Dict[str, object]:
    return {
        "solved": result.solved,
        "evaluations": result.evaluations,
        "generations": result.generations,
        "reset_events": result.reset_events,
        "best_primary": result.best_fitness[0],
        "best_secondary": result.best_fitness[1],
        "best_mask": list(result.best_mask),
        "lambda_trace": [
            [row.lambda_before, row.lambda_after, row.reset_event]
            for row in result.trace
        ],
    }


def run_jump_pair(
    arguments: Tuple[int, int, int, int, float, int]
) -> Dict[str, object]:
    """Run reset and no-reset from the exact Jump local optimum."""

    n, k, seed, budget, update_factor, evaluation_workers = arguments
    objective = JumpObjective(k)
    initial = jump_local_optimum(n, k)
    target = float(n + k)
    reset_result = run_reset_lambda_ga(
        objective,
        dimension=n,
        seed=seed,
        max_evaluations=budget,
        workers=evaluation_workers,
        update_factor=update_factor,
        reset=True,
        initial_mask=initial,
        target_primary=target,
    )
    no_reset_result = run_reset_lambda_ga(
        objective,
        dimension=n,
        seed=seed,
        max_evaluations=budget,
        workers=evaluation_workers,
        update_factor=update_factor,
        reset=False,
        initial_mask=initial,
        target_primary=target,
    )
    return {
        "seed": seed,
        "reset": _compact(reset_result),
        "no_reset": _compact(no_reset_result),
    }


def run_jump_campaign(
    *,
    n: int,
    k: int,
    seeds: Iterable[int],
    budget: int,
    campaign_workers: int = 1,
    evaluation_workers: int = 1,
    update_factor: float = 1.5,
) -> List[Dict[str, object]]:
    seed_list = [int(seed) for seed in seeds]
    arguments = [
        (n, k, seed, budget, update_factor, evaluation_workers)
        for seed in seed_list
    ]
    if campaign_workers < 1:
        raise ValueError("campaign_workers must be positive")
    if campaign_workers == 1:
        return [run_jump_pair(item) for item in arguments]
    with ProcessPoolExecutor(max_workers=campaign_workers) as executor:
        return list(executor.map(run_jump_pair, arguments))


def summarize_jump(rows: Sequence[Dict[str, object]]) -> Dict[str, object]:
    if not rows:
        raise ValueError("Jump campaign must contain at least one row")
    reset_solved = [
        row for row in rows if bool(row["reset"]["solved"])  # type: ignore[index]
    ]
    no_reset_solved = [
        row for row in rows if bool(row["no_reset"]["solved"])  # type: ignore[index]
    ]

    def solved_evaluations(
        selected: Sequence[Dict[str, object]], key: str
    ) -> List[int]:
        return [
            int(row[key]["evaluations"])  # type: ignore[index]
            for row in selected
        ]

    reset_count = len(reset_solved)
    no_reset_count = len(no_reset_solved)
    total = len(rows)
    ratio = (
        float("inf")
        if no_reset_count == 0 and reset_count > 0
        else reset_count / max(1, no_reset_count)
    )
    return {
        "runs": total,
        "reset_solved": reset_count,
        "no_reset_solved": no_reset_count,
        "reset_success_rate": reset_count / total,
        "no_reset_success_rate": no_reset_count / total,
        "success_rate_difference": (reset_count - no_reset_count) / total,
        "success_ratio": ratio,
        "reset_median_evaluations_when_solved": (
            statistics.median(solved_evaluations(reset_solved, "reset"))
            if reset_solved
            else None
        ),
        "no_reset_median_evaluations_when_solved": (
            statistics.median(
                solved_evaluations(no_reset_solved, "no_reset")
            )
            if no_reset_solved
            else None
        ),
        "total_reset_events": sum(
            int(row["reset"]["reset_events"])  # type: ignore[index]
            for row in rows
        ),
    }


def run_onemax_pair(
    *,
    n: int,
    seed: int,
    budget: int,
    workers: int = 1,
) -> Tuple[RunResult, RunResult]:
    objective = OneMaxObjective()
    reset_result = run_reset_lambda_ga(
        objective,
        dimension=n,
        seed=seed,
        max_evaluations=budget,
        workers=workers,
        reset=True,
        target_primary=float(n),
    )
    no_reset_result = run_reset_lambda_ga(
        objective,
        dimension=n,
        seed=seed,
        max_evaluations=budget,
        workers=workers,
        reset=False,
        target_primary=float(n),
    )
    return reset_result, no_reset_result

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable, Sequence

import numpy as np

from .core import (
    EffortLedger,
    conditional_mutation,
    hypervolume_contribution,
    oneminmax_objective,
    random_bits,
)
from .old import update_two_rate

TIE_POLICIES = {"uniform", "first"}
SPLIT_POLICIES = {"balanced", "literal_one_based"}


@dataclass(frozen=True)
class RecoveryRunResult:
    seed: int
    n: int
    offspring: int
    tie_policy: str
    split_policy: str
    complete: bool
    evaluations: int
    generations: int
    archive_size: int
    first_hits: tuple[int | None, ...]
    final_rate: float
    lower_winners: int
    higher_winners: int
    archive_digest: str
    trace_digest: str
    effort: EffortLedger

    def canonical(self) -> dict:
        return {
            "seed": self.seed,
            "n": self.n,
            "offspring": self.offspring,
            "tie_policy": self.tie_policy,
            "split_policy": self.split_policy,
            "complete": self.complete,
            "evaluations": self.evaluations,
            "generations": self.generations,
            "archive_size": self.archive_size,
            "first_hits": list(self.first_hits),
            "final_rate": format(self.final_rate, ".17g"),
            "lower_winners": self.lower_winners,
            "higher_winners": self.higher_winners,
            "archive_digest": self.archive_digest,
            "trace_digest": self.trace_digest,
            "effort": self.effort.__dict__,
        }


def lower_group(index: int, offspring: int, split_policy: str) -> bool:
    if split_policy not in SPLIT_POLICIES:
        raise ValueError(f"unknown split policy: {split_policy}")
    if index < 0 or index >= offspring:
        raise ValueError("offspring index out of range")
    if split_policy == "balanced":
        return index < offspring // 2
    one_based = index + 1
    return one_based < offspring // 2


def split_counts(offspring: int, split_policy: str) -> tuple[int, int]:
    lower = sum(lower_group(index, offspring, split_policy) for index in range(offspring))
    return lower, offspring - lower


def select_winner_index(
    scores: Sequence[int | float],
    *,
    tie_policy: str,
    rng: np.random.Generator,
) -> int:
    if tie_policy not in TIE_POLICIES:
        raise ValueError(f"unknown tie policy: {tie_policy}")
    if not scores:
        raise ValueError("scores must not be empty")
    numeric = np.asarray(scores, dtype=np.float64)
    if not np.all(np.isfinite(numeric)):
        raise ValueError("scores contain non-finite values")
    best = float(np.max(numeric))
    tied = np.flatnonzero(numeric == best)
    if tie_policy == "first":
        return int(tied[0])
    return int(tied[int(rng.integers(0, len(tied)))])


def run_two_rate_recovery(
    seed: int,
    *,
    tie_policy: str,
    split_policy: str,
    n: int = 100,
    offspring: int = 10,
    max_evaluations: int = 2_000_000,
    record_trace: bool = False,
) -> RecoveryRunResult:
    if n < 2:
        raise ValueError("n must be at least 2")
    if offspring < 2 or offspring % 2:
        raise ValueError("offspring must be a positive even integer")
    if max_evaluations < 1 + offspring:
        raise ValueError("max_evaluations is too small")
    if tie_policy not in TIE_POLICIES:
        raise ValueError(f"unknown tie policy: {tie_policy}")
    if split_policy not in SPLIT_POLICIES:
        raise ValueError(f"unknown split policy: {split_policy}")

    rng = np.random.Generator(np.random.PCG64DXSM(int(seed)))
    initial = random_bits(rng, n)
    initial_weight = oneminmax_objective(initial, n)[0]
    archive: dict[int, int] = {initial_weight: initial}
    first_hits: list[int | None] = [None] * (n + 1)
    first_hits[initial_weight] = 1
    evaluations = 1
    generations = 0
    rate = 1.0
    lower_winners = 0
    higher_winners = 0
    mutation_draws = 0
    flipped_bits = 0
    archive_insertions = 1
    trace = sha256()
    trace.update(
        (
            f"seed={seed};tie={tie_policy};split={split_policy};"
            f"initial={initial};weight={initial_weight}"
        ).encode()
    )

    while len(archive) < n + 1 and evaluations + offspring <= max_evaluations:
        snapshot_weights = tuple(sorted(archive))
        snapshot_bits = tuple(archive[weight] for weight in snapshot_weights)
        candidates: list[tuple[int, int, str, int, int]] = []
        for index in range(offspring):
            parent = snapshot_bits[int(rng.integers(0, len(snapshot_bits)))]
            group = "lower" if lower_group(index, offspring, split_policy) else "higher"
            probability = rate / (2.0 * n) if group == "lower" else 2.0 * rate / n
            child, strength = conditional_mutation(parent, n, probability, rng)
            mutation_draws += 1
            flipped_bits += strength
            weight = oneminmax_objective(child, n)[0]
            contribution = hypervolume_contribution(snapshot_weights, weight, n)
            candidates.append((contribution, weight, group, child, strength))
            evaluations += 1
            if first_hits[weight] is None:
                first_hits[weight] = evaluations

        winner_index = select_winner_index(
            [candidate[0] for candidate in candidates],
            tie_policy=tie_policy,
            rng=rng,
        )
        winner_group = candidates[winner_index][2]
        if winner_group == "lower":
            lower_winners += 1
        else:
            higher_winners += 1
        rate = update_two_rate(rate, winner_group, float(rng.random()), n)

        for _contribution, weight, _group, child, _strength in candidates:
            if weight not in archive:
                archive[weight] = child
                archive_insertions += 1

        generations += 1
        if record_trace:
            trace.update(
                (
                    f";g={generations};size={len(archive)};winner={winner_group};"
                    f"winner_index={winner_index};rate={format(rate,'.17g')}"
                ).encode()
            )

    effort = EffortLedger(
        objective_evaluations=evaluations,
        generated_offspring=generations * offspring,
        mutation_draws=mutation_draws,
        flipped_bits=flipped_bits,
        archive_insertions=archive_insertions,
        generations=generations,
    )
    effort.validate(offspring)
    archive_digest = sha256(
        ",".join(str(value) for value in sorted(archive)).encode("ascii")
    ).hexdigest()
    return RecoveryRunResult(
        seed=int(seed),
        n=n,
        offspring=offspring,
        tie_policy=tie_policy,
        split_policy=split_policy,
        complete=len(archive) == n + 1,
        evaluations=evaluations,
        generations=generations,
        archive_size=len(archive),
        first_hits=tuple(first_hits),
        final_rate=rate,
        lower_winners=lower_winners,
        higher_winners=higher_winners,
        archive_digest=archive_digest,
        trace_digest=trace.hexdigest(),
        effort=effort,
    )


def _task(args: tuple[int, str, str, int, int, int]) -> RecoveryRunResult:
    seed, tie_policy, split_policy, n, offspring, budget = args
    return run_two_rate_recovery(
        seed,
        tie_policy=tie_policy,
        split_policy=split_policy,
        n=n,
        offspring=offspring,
        max_evaluations=budget,
    )


def run_recovery_campaign(
    seeds: Iterable[int],
    *,
    tie_policy: str,
    split_policy: str,
    workers: int = 1,
    n: int = 100,
    offspring: int = 10,
    max_evaluations: int = 2_000_000,
) -> list[RecoveryRunResult]:
    seed_list = [int(seed) for seed in seeds]
    if not seed_list:
        raise ValueError("seed ledger must not be empty")
    if len(seed_list) != len(set(seed_list)):
        raise ValueError("seed ledger contains duplicates")
    if workers not in {1, 2, 4}:
        raise ValueError("workers must be one of 1, 2, 4")
    if tie_policy not in TIE_POLICIES or split_policy not in SPLIT_POLICIES:
        raise ValueError("invalid recovery policy")
    args = [
        (seed, tie_policy, split_policy, n, offspring, max_evaluations)
        for seed in seed_list
    ]
    if workers == 1:
        results = [_task(arg) for arg in args]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_task, args))
    return sorted(results, key=lambda result: result.seed)


def recovery_campaign_digest(results: Sequence[RecoveryRunResult]) -> str:
    if not results:
        raise ValueError("results must not be empty")
    payload = json.dumps(
        [result.canonical() for result in sorted(results, key=lambda item: item.seed)],
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()

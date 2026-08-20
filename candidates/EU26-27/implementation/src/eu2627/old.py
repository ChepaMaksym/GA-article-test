from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np

from .core import (
    EffortLedger,
    conditional_mutation,
    hypervolume_contribution,
    oneminmax_objective,
    random_bits,
)


@dataclass(frozen=True)
class OldRunResult:
    seed: int
    n: int
    offspring: int
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


def update_two_rate(
    rate: float,
    winner_group: str,
    draw: float,
    n: int,
) -> float:
    if winner_group not in {"lower", "higher"}:
        raise ValueError("winner_group must be lower or higher")
    if not 0.0 <= draw < 1.0:
        raise ValueError("draw must be in [0,1)")
    lower_probability = 0.75 if winner_group == "lower" else 0.25
    if draw < lower_probability:
        return max(rate / 2.0, 0.5)
    return min(rate * 2.0, n / 4.0)


def run_two_rate_old(
    seed: int,
    *,
    n: int = 100,
    offspring: int = 10,
    max_evaluations: int = 2_000_000,
    record_trace: bool = False,
) -> OldRunResult:
    if n < 2:
        raise ValueError("n must be at least 2")
    if offspring < 2 or offspring % 2:
        raise ValueError("offspring must be a positive even integer")
    if max_evaluations < 1 + offspring:
        raise ValueError("max_evaluations is too small")

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
    trace.update(f"seed={seed};initial={initial};weight={initial_weight}".encode())

    while len(archive) < n + 1 and evaluations + offspring <= max_evaluations:
        snapshot_weights = tuple(sorted(archive))
        snapshot_bits = tuple(archive[weight] for weight in snapshot_weights)
        candidates: list[tuple[int, int, str, int, int]] = []
        half = offspring // 2
        for index in range(offspring):
            parent_index = int(rng.integers(0, len(snapshot_bits)))
            parent = snapshot_bits[parent_index]
            group = "lower" if index < half else "higher"
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

        best_contribution = max(item[0] for item in candidates)
        tied = [item for item in candidates if item[0] == best_contribution]
        winner = tied[int(rng.integers(0, len(tied)))]
        winner_group = winner[2]
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
                    f"contribution={best_contribution};rate={format(rate,'.17g')}"
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
    return OldRunResult(
        seed=int(seed),
        n=n,
        offspring=offspring,
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

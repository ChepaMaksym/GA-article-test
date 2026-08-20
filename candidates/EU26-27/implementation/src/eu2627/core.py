from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

import numpy as np


def oneminmax_objective(bits: int, n: int) -> tuple[int, int]:
    if n < 1:
        raise ValueError("n must be positive")
    if bits < 0 or bits >= (1 << n):
        raise ValueError("bits are outside the n-bit search space")
    ones = int(bits.bit_count())
    return ones, n - ones


def hypervolume(
    weights: Iterable[int],
    n: int,
    reference: tuple[int, int] = (-1, -1),
) -> int:
    ref_x, ref_y = reference
    if ref_x >= 0 or ref_y >= 0:
        raise ValueError("OneMinMax reference point must be below the front")
    unique = sorted(set(int(weight) for weight in weights))
    if any(weight < 0 or weight > n for weight in unique):
        raise ValueError("front weight outside [0,n]")
    total = 0
    previous_x = ref_x
    for weight in unique:
        x = weight
        y = n - weight
        total += (x - previous_x) * (y - ref_y)
        previous_x = x
    return int(total)


def hypervolume_contribution(
    archive_weights: Iterable[int], candidate_weight: int, n: int
) -> int:
    weights = set(int(value) for value in archive_weights)
    if candidate_weight in weights:
        return 0
    return hypervolume(weights | {candidate_weight}, n) - hypervolume(weights, n)


def random_bits(rng: np.random.Generator, n: int) -> int:
    chunks = (n + 63) // 64
    value = 0
    for index in range(chunks):
        word = int(rng.integers(0, 1 << 64, dtype=np.uint64))
        value |= word << (64 * index)
    return value & ((1 << n) - 1)


def conditional_mutation(
    bits: int,
    n: int,
    probability: float,
    rng: np.random.Generator,
) -> tuple[int, int]:
    if not np.isfinite(probability) or not 0.0 < probability <= 1.0:
        raise ValueError("mutation probability must be in (0,1]")
    for _ in range(100_000):
        flips = int(rng.binomial(n, probability))
        if flips == 0:
            continue
        positions = rng.choice(n, size=flips, replace=False)
        mask = 0
        for position in positions:
            mask |= 1 << int(position)
        return bits ^ mask, flips
    raise RuntimeError("failed to sample positive mutation strength")


def scientific_hash(parts: Iterable[str]) -> str:
    digest = sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class EffortLedger:
    objective_evaluations: int
    generated_offspring: int
    mutation_draws: int
    flipped_bits: int
    archive_insertions: int
    generations: int

    def validate(self, offspring: int) -> None:
        if self.objective_evaluations != 1 + self.generated_offspring:
            raise RuntimeError("objective accounting drift")
        if self.generated_offspring != offspring * self.generations:
            raise RuntimeError("incomplete generation accounting")
        values = (
            self.objective_evaluations,
            self.generated_offspring,
            self.mutation_draws,
            self.flipped_bits,
            self.archive_insertions,
            self.generations,
        )
        if min(values) < 0:
            raise RuntimeError("negative effort counter")

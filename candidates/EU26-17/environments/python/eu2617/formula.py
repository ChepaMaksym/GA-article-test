"""Fail-closed clean-room implementation of the frozen SupRB SAGA1 step.

The equations and defaults are copied from the preregistered contract, not by
importing SupRB.  Unlike the authenticated upstream methods, this harness
rejects empty, non-finite, and zero-maximum fitness vectors before division.
That divergence is deliberate validation hygiene and is never attributed to
the authors.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike


def _finite_scalar(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} must be a real scalar")
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


@dataclass(frozen=True)
class SAGA1Config:
    """Frozen source defaults and bounds for SAGA1."""

    v_min: float = 0.005
    v_max: float = 0.15
    mutation_rate_min: float = 0.001
    mutation_rate_max: float = 0.25
    mutation_rate_multiplier: float = 1.1
    crossover_rate_min: float = 0.5
    crossover_rate_max: float = 1.0
    crossover_rate_multiplier: float = 1.1

    def validate(self) -> None:
        v_min = _finite_scalar(self.v_min, "v_min")
        v_max = _finite_scalar(self.v_max, "v_max")
        if v_min < 0.0 or v_min >= v_max:
            raise ValueError("thresholds must satisfy 0 <= v_min < v_max")

        mutation_min = _finite_scalar(
            self.mutation_rate_min, "mutation_rate_min"
        )
        mutation_max = _finite_scalar(
            self.mutation_rate_max, "mutation_rate_max"
        )
        crossover_min = _finite_scalar(
            self.crossover_rate_min, "crossover_rate_min"
        )
        crossover_max = _finite_scalar(
            self.crossover_rate_max, "crossover_rate_max"
        )
        if not 0.0 <= mutation_min <= mutation_max <= 1.0:
            raise ValueError("mutation-rate bounds must lie in [0, 1] in order")
        if not 0.0 <= crossover_min <= crossover_max <= 1.0:
            raise ValueError("crossover-rate bounds must lie in [0, 1] in order")

        mutation_multiplier = _finite_scalar(
            self.mutation_rate_multiplier, "mutation_rate_multiplier"
        )
        crossover_multiplier = _finite_scalar(
            self.crossover_rate_multiplier, "crossover_rate_multiplier"
        )
        if mutation_multiplier <= 1.0 or crossover_multiplier <= 1.0:
            raise ValueError("rate multipliers must be finite and greater than one")


@dataclass(frozen=True)
class RateState:
    mutation_rate: float = 0.025
    crossover_rate: float = 0.75

    def validate(self, config: SAGA1Config) -> None:
        mutation = _finite_scalar(self.mutation_rate, "mutation_rate")
        crossover = _finite_scalar(self.crossover_rate, "crossover_rate")
        if not config.mutation_rate_min <= mutation <= config.mutation_rate_max:
            raise ValueError("mutation_rate is outside its configured bounds")
        if not config.crossover_rate_min <= crossover <= config.crossover_rate_max:
            raise ValueError("crossover_rate is outside its configured bounds")


@dataclass(frozen=True)
class TransitionResult:
    gdm: float
    previous: RateState
    current: RateState
    branch: str


def _fitness_vector(fitness: ArrayLike) -> np.ndarray:
    try:
        values = np.asarray(fitness, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("fitness must be a numeric vector") from exc
    if values.ndim != 1 or values.size == 0:
        raise ValueError("fitness must be a nonempty one-dimensional vector")
    if not np.all(np.isfinite(values)):
        raise ValueError("fitness must contain only finite values")
    if float(np.max(values)) == 0.0:
        raise ValueError("max(fitness) must be nonzero")
    return values


def calc_gdm(fitness: ArrayLike) -> float:
    """Compute ``mean(fitness) / max(fitness)`` after fail-closed checks."""

    values = _fitness_vector(fitness)
    result = float(np.mean(values) / np.max(values))
    if not np.isfinite(result):
        raise FloatingPointError("gdm calculation produced a non-finite value")
    return result


def adjust_rates(
    fitness: ArrayLike,
    state: RateState = RateState(),
    config: SAGA1Config = SAGA1Config(),
) -> TransitionResult:
    """Apply one exact source-order SAGA1 crossover/mutation-rate update."""

    config.validate()
    state.validate(config)
    gdm = calc_gdm(fitness)

    mutation_rate = float(state.mutation_rate)
    crossover_rate = float(state.crossover_rate)
    branch = "no_change"
    if gdm > config.v_max:
        mutation_rate = min(
            config.mutation_rate_max,
            mutation_rate * config.mutation_rate_multiplier,
        )
        crossover_rate = max(
            config.crossover_rate_min,
            crossover_rate / config.crossover_rate_multiplier,
        )
        branch = "above_v_max"
    elif gdm < config.v_min:
        mutation_rate = max(
            config.mutation_rate_min,
            mutation_rate / config.mutation_rate_multiplier,
        )
        crossover_rate = min(
            config.crossover_rate_max,
            crossover_rate * config.crossover_rate_multiplier,
        )
        branch = "below_v_min"

    current = RateState(mutation_rate, crossover_rate)
    current.validate(config)
    return TransitionResult(gdm, state, current, branch)


def run_trajectory(
    fitness_by_generation: Iterable[ArrayLike],
    state: RateState = RateState(),
    config: SAGA1Config = SAGA1Config(),
) -> tuple[TransitionResult, ...]:
    """Apply the frozen transition sequentially to fitted populations."""

    results: list[TransitionResult] = []
    current = state
    for fitness in fitness_by_generation:
        result = adjust_rates(fitness, current, config)
        results.append(result)
        current = result.current
    return tuple(results)

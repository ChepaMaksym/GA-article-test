from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

MOVE_NAMES = ("reinsert", "exchange", "oropt2", "oropt3")


def round_half_up(value: float) -> int:
    if not np.isfinite(value) or value < 0:
        raise ValueError("value must be finite and non-negative")
    return int(np.floor(value + 0.5))


def lambda_controls(lambda_value: float, n: int) -> tuple[float, float, int]:
    if not np.isfinite(lambda_value) or not 1 <= lambda_value <= n:
        raise ValueError("require 1 <= lambda <= n")
    return lambda_value / n, 1.0 / lambda_value, max(1, round_half_up(lambda_value))


def update_lambda(lambda_value: float, strict_success: bool, n: int, factor: float = 1.5, reset: bool = True) -> float:
    if not np.isfinite(lambda_value) or not 1 <= lambda_value <= n:
        raise ValueError("require 1 <= lambda <= n")
    if not np.isfinite(factor) or factor <= 1:
        raise ValueError("factor must be > 1")
    if strict_success:
        return max(1.0, lambda_value / factor)
    if reset and lambda_value == float(n):
        return 1.0
    return min(float(n), lambda_value * factor ** 0.25)


@dataclass
class Roulette:
    weights: np.ndarray = field(default_factory=lambda: np.full(4, 100, dtype=np.int64))

    def probabilities(self) -> np.ndarray:
        if self.weights.shape != (4,) or np.any(self.weights <= 0):
            raise ValueError("roulette weights must contain four positive integers")
        return self.weights / self.weights.sum()

    def choose(self, rng: np.random.Generator) -> int:
        return int(rng.choice(4, p=self.probabilities()))

    def reward(self, index: int, strict_improvement: bool) -> None:
        if not 0 <= index < 4:
            raise ValueError("invalid move index")
        if strict_improvement:
            self.weights[index] += 1




@dataclass
class RunResult:
    seed: int
    method: str
    final_objective: float
    first_hit_nfe: int | None
    logical_nfe: int
    generations: int
    initial_population_digest: str
    final_order_digest: str
    roulette_weights: tuple[int, ...]
    lambda_max: float = 1.0
    reset_events: int = 0
    lambda_trace: tuple[float, ...] = ()

    def canonical(self) -> dict:
        return {
            "seed": self.seed,
            "method": self.method,
            "final_objective": round(self.final_objective, 15),
            "first_hit_nfe": self.first_hit_nfe,
            "logical_nfe": self.logical_nfe,
            "generations": self.generations,
            "initial_population_digest": self.initial_population_digest,
            "final_order_digest": self.final_order_digest,
            "roulette_weights": list(self.roulette_weights),
            "lambda_max": round(self.lambda_max, 15),
            "reset_events": self.reset_events,
        }



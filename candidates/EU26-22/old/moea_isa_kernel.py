"""Clean-room formula kernel for MOEA-ISa source audit.

This module intentionally covers only deterministic formulas exposed by the
paper-linked source. It is not a paper-result reproduction or a complete
PlatEMO port.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Sequence

STATES = tuple(i / 20 for i in range(1, 21))
ACTIONS = tuple(i / 10 for i in range(1, 11))
INITIAL_INTERVAL_PROBABILITIES = (0.6571, 0.1664, 0.0872, 0.0539, 0.0354)


class FormulaDomainError(ValueError):
    """Raised when the source formula has no defined state."""


def matlab_round_nonnegative(value: float) -> int:
    if value < 0:
        raise FormulaDomainError("value must be non-negative")
    return floor(value + 0.5)


def jaccard_similarity(parent1: Sequence[int], parent2: Sequence[int]) -> float:
    if len(parent1) != len(parent2) or not parent1:
        raise FormulaDomainError("parents must have equal non-zero length")
    if any(v not in (0, 1, False, True) for v in (*parent1, *parent2)):
        raise FormulaDomainError("parents must be binary")
    intersection = sum(bool(a) and bool(b) for a, b in zip(parent1, parent2))
    union = sum(bool(a) or bool(b) for a, b in zip(parent1, parent2))
    if union == 0:
        raise FormulaDomainError("all-zero parents have undefined Jaccard state")
    return intersection / union


def state_index(similarity: float) -> int:
    if not 0 <= similarity <= 1:
        raise FormulaDomainError("similarity must be in [0, 1]")
    for i, boundary in enumerate(STATES, start=1):
        if boundary >= similarity:
            return i
    raise FormulaDomainError("no state boundary found")


def action_fraction(action_index: int) -> float:
    if not 1 <= action_index <= len(ACTIONS):
        raise FormulaDomainError("action index must be 1..10")
    return ACTIONS[action_index - 1]


def crossover_count(parent1: Sequence[int], parent2: Sequence[int], action_index: int) -> int:
    if len(parent1) != len(parent2):
        raise FormulaDomainError("parents must have equal length")
    disagreements = sum(a != b for a, b in zip(parent1, parent2))
    count = matlab_round_nonnegative(disagreements * action_fraction(action_index))
    if disagreements > 1:
        count = max(count, 1)
    return min(count, disagreements)


def interval_bounds(dimension: int, interval_index: int) -> tuple[int, int]:
    if dimension < 1 or not 1 <= interval_index <= 5:
        raise FormulaDomainError("dimension >=1 and interval index 1..5 required")
    low = floor((interval_index - 1) * dimension / 5) + 1
    high = floor(interval_index * dimension / 5)
    if low > high:
        raise FormulaDomainError("interval is empty at this dimension")
    return low, high


def roulette_index(weights: Sequence[float], tape: float) -> int:
    if not weights or not 0 <= tape < 1:
        raise FormulaDomainError("non-empty weights and tape in [0,1) required")
    adjusted = [0.03 if w == 0 else float(w) for w in weights]
    if any(w < 0 for w in adjusted):
        raise FormulaDomainError("weights must be non-negative")
    total = sum(adjusted)
    if total <= 0:
        raise FormulaDomainError("positive total weight required")
    cumulative = 0.0
    for i, weight in enumerate(adjusted, start=1):
        cumulative += weight / total
        if cumulative >= tape:
            return i
    return len(adjusted)


def update_probability_table(old, successes, attempts, alpha: float = 0.3):
    if not 0 <= alpha <= 1:
        raise FormulaDomainError("alpha must be in [0,1]")
    rows = len(old)
    if rows == 0 or len(successes) != rows or len(attempts) != rows:
        raise FormulaDomainError("matrix row mismatch")
    result = []
    for old_row, success_row, attempt_row in zip(old, successes, attempts):
        if len(old_row) != len(success_row) or len(old_row) != len(attempt_row):
            raise FormulaDomainError("matrix column mismatch")
        row = []
        for previous, success, attempt in zip(old_row, success_row, attempt_row):
            if success < 0 or attempt < 0 or success > attempt:
                raise FormulaDomainError("invalid success/attempt counts")
            if attempt == 0:
                row.append(float(previous))
            else:
                observed = success / attempt
                row.append((1 - alpha) * float(previous) + alpha * observed)
        result.append(row)
    return result


@dataclass(frozen=True)
class FormulaCase:
    parent1: tuple[int, ...]
    parent2: tuple[int, ...]
    action_index: int

    def canonical(self) -> tuple[float, int, int]:
        similarity = jaccard_similarity(self.parent1, self.parent2)
        return similarity, state_index(similarity), crossover_count(
            self.parent1, self.parent2, self.action_index
        )

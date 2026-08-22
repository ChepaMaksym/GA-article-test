from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RollbackState:
    lambda_real: float
    lambda_count: int
    lambda_base: float
    bad_count: int
    delta: int


def round_half_up(value: float) -> int:
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    return int(math.floor(value + 0.5))


def next_rollback(
    state: RollbackState,
    *,
    strict_success: bool,
    update_factor: float = 1.5,
    u: int = 5,
    lambda_floor: float = 10.0,
    lambda_max: float = 100.0,
    delta_initial: int = 10,
) -> RollbackState:
    if update_factor <= 1.0 or u <= 1 or delta_initial <= 0:
        raise ValueError("invalid controller constants")
    if not lambda_floor <= state.lambda_real <= lambda_max:
        raise ValueError("lambda_real outside bounds")
    if not lambda_floor <= state.lambda_base <= lambda_max:
        raise ValueError("lambda_base outside bounds")
    if state.bad_count < 0 or state.delta <= 0:
        raise ValueError("invalid rollback counters")

    if strict_success:
        value = max(state.lambda_real / update_factor, lambda_floor)
        base = value
        bad = 0
        delta = delta_initial
    else:
        base = state.lambda_base
        bad = state.bad_count + 1
        delta = state.delta
        if bad == delta:
            bad = 0
            delta += 1
        value = min(base * update_factor ** (bad / (u - 1)), lambda_max)

    count = max(int(lambda_floor), min(round_half_up(value), int(lambda_max)))
    return RollbackState(value, count, base, bad, delta)


def next_floor_only(
    lambda_real: float,
    *,
    strict_success: bool,
    update_factor: float = 1.5,
    lambda_floor: float = 10.0,
    lambda_max: float = 100.0,
) -> tuple[float, int]:
    if not lambda_floor <= lambda_real <= lambda_max:
        raise ValueError("lambda_real outside bounds")
    if strict_success:
        value = max(lambda_real / update_factor, lambda_floor)
    else:
        value = min(lambda_real * update_factor ** 0.25, lambda_max)
    count = max(int(lambda_floor), min(round_half_up(value), int(lambda_max)))
    return value, count


def initial_state(lambda_floor: float = 10.0, delta_initial: int = 10) -> RollbackState:
    return RollbackState(lambda_floor, int(lambda_floor), lambda_floor, 0, delta_initial)

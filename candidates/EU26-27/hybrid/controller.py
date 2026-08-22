from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ControllerState:
    lambda_real: float
    lambda_count: int


def round_half_up(value: float) -> int:
    if not math.isfinite(value) or value < 1:
        raise ValueError("lambda must be finite and >= 1")
    return int(math.floor(value + 0.5))


def next_lambda(
    lambda_real: float,
    *,
    strict_success: bool,
    update_factor: float = 1.5,
    lambda_max: float = 100.0,
    reset: bool = True,
) -> ControllerState:
    if not math.isfinite(lambda_real) or not math.isfinite(update_factor) or not math.isfinite(lambda_max):
        raise ValueError("controller inputs must be finite")
    if not 1.0 <= lambda_real <= lambda_max:
        raise ValueError("require 1 <= lambda_real <= lambda_max")
    if update_factor <= 1.0:
        raise ValueError("update_factor must be > 1")
    if not isinstance(strict_success, bool) or not isinstance(reset, bool):
        raise TypeError("strict_success and reset must be bool")

    if strict_success:
        value = max(lambda_real / update_factor, 1.0)
    elif reset and lambda_real == lambda_max:
        value = 1.0
    else:
        value = min(lambda_real * update_factor ** 0.25, lambda_max)

    count = max(1, min(round_half_up(value), int(lambda_max)))
    return ControllerState(lambda_real=value, lambda_count=count)

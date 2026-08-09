"""Independent parameter-control formulas for the source and paper profiles."""

from __future__ import annotations

import math
from dataclasses import dataclass


class ControlError(ValueError):
    """Raised when a control state violates the frozen domain."""


@dataclass(frozen=True)
class ControlState:
    lambda_real: float
    mutation_probability: float
    crossover_probability: float
    source_offspring_count: int
    paper_offspring_count: int
    evaluation_increment: int


def _finite_positive(value: float, *, name: str) -> float:
    if isinstance(value, bool):
        raise ControlError(f"{name} must be numeric, not boolean")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ControlError(f"{name} is not numeric") from error
    if not math.isfinite(parsed) or parsed <= 0.0:
        raise ControlError(f"{name} must be finite and positive")
    return parsed


def round_ties_to_even_positive(value: float) -> int:
    """Implement Python's positive nearest/ties-to-even integer rule directly."""

    parsed = _finite_positive(value, name="value")
    lower = math.floor(parsed)
    fraction = parsed - lower
    if fraction < 0.5:
        return lower
    if fraction > 0.5:
        return lower + 1
    return lower if lower % 2 == 0 else lower + 1


def control_state(
    lambda_real: float,
    *,
    dimension: int,
    crossover_rate: float = 1.0,
) -> ControlState:
    """Map one real lambda to both audited semantics profiles."""

    value = _finite_positive(lambda_real, name="lambda_real")
    rate = _finite_positive(crossover_rate, name="crossover_rate")
    if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension <= 1:
        raise ControlError("dimension must be an integer greater than one")
    if value > dimension:
        raise ControlError("lambda_real exceeds the dimension/cap")
    source_count = round_ties_to_even_positive(value)
    paper_count = math.ceil(value)
    mutation_probability = value / dimension
    crossover_probability = min(1.0, rate / value) if rate >= 1.0 else rate
    if not 0.0 < mutation_probability <= 1.0:
        raise ControlError("mutation probability is outside (0, 1]")
    if not 0.0 < crossover_probability <= 1.0:
        raise ControlError("crossover probability is outside (0, 1]")
    if source_count < 1 or paper_count < 1:
        raise ControlError("offspring counts must be positive")
    return ControlState(
        lambda_real=value,
        mutation_probability=mutation_probability,
        crossover_probability=crossover_probability,
        source_offspring_count=source_count,
        paper_offspring_count=paper_count,
        evaluation_increment=2 * source_count,
    )


def transition_lambda(
    lambda_real: float,
    *,
    success: bool,
    update_factor: float,
    lambda_max: float,
) -> float:
    """Apply the audited source class's success/failure/reset transition."""

    value = _finite_positive(lambda_real, name="lambda_real")
    factor = _finite_positive(update_factor, name="update_factor")
    cap = _finite_positive(lambda_max, name="lambda_max")
    if factor <= 1.0:
        raise ControlError("update_factor must be greater than one")
    if value > cap:
        raise ControlError("lambda_real exceeds lambda_max")
    if type(success) is not bool:
        raise ControlError("success must be a boolean")

    if success:
        updated = value / factor
    elif value == cap:
        updated = 1.0
    else:
        updated = value * math.pow(factor, 0.25)
    return min(max(updated, 1.0), cap)

"""Independent released-source control transitions for EU26-12."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from typing import Any, Iterable, Mapping, Sequence


class ControlError(ValueError):
    """Raised when a control fixture is outside the frozen source domain."""


@dataclass(frozen=True)
class MemoryUpdate:
    successful_indices: tuple[int, ...]
    weights: tuple[Fraction, ...]
    F: Fraction
    CR: Fraction


@dataclass(frozen=True)
class ScheduleResult:
    generations: int
    used_budget: int
    logged_evaluations: int
    terminal_population: int


def _fraction(value: Any, *, name: str) -> Fraction:
    if isinstance(value, bool):
        raise ControlError(f"{name} must be numeric, not boolean")
    try:
        parsed = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as error:
        raise ControlError(f"{name} is not a finite decimal number") from error
    if not math.isfinite(float(parsed)):
        raise ControlError(f"{name} must be finite")
    return parsed


def _equal_lengths(values: Sequence[Sequence[Any]]) -> int:
    lengths = {len(value) for value in values}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) == 0:
        raise ControlError("control vectors must have one equal non-zero length")
    return next(iter(lengths))


def update_success_memory(
    old_fitness: Sequence[Any],
    new_fitness: Sequence[Any],
    successful_F: Sequence[Any],
    successful_CR: Sequence[Any],
) -> MemoryUpdate:
    """Apply the released weighted arithmetic memory update exactly."""

    length = _equal_lengths((old_fitness, new_fitness, successful_F, successful_CR))
    old = [_fraction(value, name=f"old_fitness[{index}]") for index, value in enumerate(old_fitness)]
    new = [_fraction(value, name=f"new_fitness[{index}]") for index, value in enumerate(new_fitness)]
    f_values = [_fraction(value, name=f"F[{index}]") for index, value in enumerate(successful_F)]
    cr_values = [_fraction(value, name=f"CR[{index}]") for index, value in enumerate(successful_CR)]
    for index in range(length):
        if not 0 < f_values[index] <= 1 or not 0 <= cr_values[index] <= 1:
            raise ControlError("F must be in (0,1] and CR in [0,1]")
    indices = tuple(index for index in range(length) if new[index] < old[index])
    if not indices:
        raise ControlError("memory update requires at least one strict improvement")
    deltas = tuple(abs(old[index] - new[index]) for index in indices)
    total = sum(deltas, Fraction(0))
    if total <= 0:
        raise ControlError("strict-improvement weight sum must be positive")
    weights = tuple(delta / total for delta in deltas)
    f_update = sum((weight * f_values[index] for weight, index in zip(weights, indices)), Fraction(0))
    cr_update = sum((weight * cr_values[index] for weight, index in zip(weights, indices)), Fraction(0))
    return MemoryUpdate(indices, weights, f_update, cr_update)


def transform_cr(memory: Any, normal_z: Iterable[Any]) -> tuple[Fraction, ...]:
    """Transform standard-normal fixtures using clip(memory + 0.1*z)."""

    center = _fraction(memory, name="CR memory")
    if not 0 <= center <= 1:
        raise ControlError("CR memory must be in [0,1]")
    results: list[Fraction] = []
    for index, draw in enumerate(normal_z):
        candidate = center + Fraction(1, 10) * _fraction(draw, name=f"normal_z[{index}]")
        results.append(min(max(candidate, Fraction(0)), Fraction(1)))
    if not results:
        raise ControlError("at least one CR draw is required")
    return tuple(results)


def transform_f(memory: Any, cauchy_draw_sequences: Sequence[Sequence[Any]]) -> tuple[Fraction, ...]:
    """Redraw non-positive F values and cap accepted values above one."""

    center = _fraction(memory, name="F memory")
    if not 0 < center <= 1:
        raise ControlError("F memory must be in (0,1]")
    results: list[Fraction] = []
    if not cauchy_draw_sequences:
        raise ControlError("at least one F draw sequence is required")
    for individual, sequence in enumerate(cauchy_draw_sequences):
        accepted: Fraction | None = None
        if not sequence:
            raise ControlError(f"F sequence {individual} is empty")
        for draw_index, draw in enumerate(sequence):
            candidate = center + Fraction(1, 10) * _fraction(
                draw, name=f"cauchy[{individual}][{draw_index}]"
            )
            if candidate > 0:
                accepted = min(candidate, Fraction(1))
                break
        if accepted is None:
            raise ControlError(f"F sequence {individual} never produces a positive draw")
        results.append(accepted)
    return tuple(results)


def round_ties_even(value: Decimal) -> int:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ControlError("ties-even input must be a finite non-negative Decimal")
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def lpsr_population(
    *,
    initial_population: int,
    minimum_population: int,
    budget: int,
    used_budget: int,
) -> int:
    """Apply exact linear reduction with the released ties-even rounding rule."""

    values = (initial_population, minimum_population, budget, used_budget)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ControlError("LPSR inputs must be integers")
    if minimum_population <= 0 or initial_population < minimum_population:
        raise ControlError("LPSR population bounds are invalid")
    if budget <= 0 or used_budget < 0:
        raise ControlError("LPSR budgets are invalid")
    with localcontext() as context:
        context.prec = 60
        raw = (
            Decimal(minimum_population - initial_population)
            / Decimal(budget)
            * Decimal(used_budget)
            + Decimal(initial_population)
        )
    rounded = round_ties_even(raw)
    return max(minimum_population, min(initial_population, rounded))


def replacement_sources(
    parent_fitness: Sequence[Any], offspring_fitness: Sequence[Any]
) -> tuple[tuple[str, ...], tuple[bool, ...]]:
    """Implement parent `<` offspring selection and strict improvement flags."""

    _equal_lengths((parent_fitness, offspring_fitness))
    parents = [_fraction(value, name=f"parent[{index}]") for index, value in enumerate(parent_fitness)]
    offspring = [_fraction(value, name=f"offspring[{index}]") for index, value in enumerate(offspring_fitness)]
    sources = tuple("parent" if parent < child else "offspring" for parent, child in zip(parents, offspring))
    improved = tuple(child < parent for parent, child in zip(parents, offspring))
    return sources, improved


def evaluation_schedule(
    *,
    initial_population: int,
    minimum_population: int,
    budget: int,
) -> ScheduleResult:
    """Replay population-only accounting until the IOH budget check fires."""

    population = initial_population
    used_budget = 0
    logged = initial_population
    generations = 0
    while logged < budget:
        used_budget += population
        logged += population
        generations += 1
        population = lpsr_population(
            initial_population=initial_population,
            minimum_population=minimum_population,
            budget=budget,
            used_budget=used_budget,
        )
        if generations > budget:
            raise ControlError("evaluation schedule failed to terminate")
    return ScheduleResult(generations, used_budget, logged, population)


def fraction_decimal(value: Fraction, *, places: int | None = None) -> str:
    """Render an exact fraction canonically for cross-language fixture reports."""

    if places is None:
        denominator = value.denominator
        reduced = denominator
        while reduced % 2 == 0:
            reduced //= 2
        while reduced % 5 == 0:
            reduced //= 5
        if reduced != 1:
            raise ControlError("non-terminating fraction needs an explicit place count")
        with localcontext() as context:
            context.prec = 80
            text = format(Decimal(value.numerator) / Decimal(value.denominator), "f")
    else:
        if places < 0:
            raise ControlError("decimal place count must be non-negative")
        with localcontext() as context:
            context.prec = places + 20
            decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
            quantum = Decimal(1).scaleb(-places)
            text = format(decimal_value.quantize(quantum, rounding=ROUND_HALF_EVEN), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def fixture_report(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate all preregistered controls and reject any changed expectation."""

    fixtures = contract["control_fixtures"]
    memory_fixture = fixtures["memory_update"]
    update = update_success_memory(
        memory_fixture["old_fitness"],
        memory_fixture["new_fitness"],
        memory_fixture["successful_F"],
        memory_fixture["successful_CR"],
    )
    memory_f = fraction_decimal(update.F)
    memory_cr = fraction_decimal(update.CR, places=50)
    if memory_f != memory_fixture["expected_F"] or memory_cr != memory_fixture["expected_CR"]:
        raise ControlError("memory fixture differs from the preregistration")

    cr_fixture = fixtures["cr_transform"]
    cr_values = tuple(fraction_decimal(value) for value in transform_cr(cr_fixture["memory"], cr_fixture["normal_z"]))
    expected_cr = tuple(fraction_decimal(_fraction(value, name="expected CR")) for value in cr_fixture["expected"])
    if cr_values != expected_cr:
        raise ControlError("CR transform fixture differs")

    f_fixture = fixtures["f_transform"]
    f_values = tuple(
        fraction_decimal(value)
        for value in transform_f(f_fixture["memory"], f_fixture["cauchy_draw_sequences"])
    )
    expected_f = tuple(fraction_decimal(_fraction(value, name="expected F")) for value in f_fixture["expected"])
    if f_values != expected_f:
        raise ControlError("F transform fixture differs")

    replacement = fixtures["replacement"]
    sources, improved = replacement_sources(
        replacement["parent_fitness"], replacement["offspring_fitness"]
    )
    if list(sources) != replacement["expected_sources"] or list(improved) != replacement["expected_improved"]:
        raise ControlError("replacement fixture differs")

    schedule_fixture = fixtures["evaluation_schedule"]
    schedule = evaluation_schedule(
        initial_population=schedule_fixture["initial_population"],
        minimum_population=schedule_fixture["minimum_population"],
        budget=schedule_fixture["budget"],
    )
    observed_schedule = {
        "generations": schedule.generations,
        "used_budget": schedule.used_budget,
        "logged_evaluations": schedule.logged_evaluations,
        "terminal_population": schedule.terminal_population,
    }
    expected_schedule = {
        key.removeprefix("expected_"): value
        for key, value in schedule_fixture.items()
        if key.startswith("expected_")
    }
    if observed_schedule != expected_schedule:
        raise ControlError(f"evaluation schedule differs: {observed_schedule!r}")
    return {
        "memory_successful_indices": list(update.successful_indices),
        "memory_weights": [fraction_decimal(value, places=50) for value in update.weights],
        "memory_F": memory_f,
        "memory_CR": memory_cr,
        "CR_values": list(cr_values),
        "F_values": list(f_values),
        "replacement_sources": list(sources),
        "replacement_improved": list(improved),
        "schedule": observed_schedule,
        "round_half_even": {
            "two_point_five": round_ties_even(Decimal("2.5")),
            "three_point_five": round_ties_even(Decimal("3.5")),
        },
    }

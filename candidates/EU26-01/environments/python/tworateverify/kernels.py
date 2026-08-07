"""Clean-room OneMinMax, 2-D HV and TwoRate transition kernels.

The functions consume explicit deterministic tapes. They deliberately do not
emulate IOHexperimenter or claim compatibility with the authors' RNG stream.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Iterable, Sequence


Point = tuple[int, int]


class FormulaValidationError(ValueError):
    """Raised when a formula input is outside the frozen protocol."""


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FormulaValidationError(f"{label} must be an integer")
    return value


def _fraction(value: Any, label: str) -> Fraction:
    if isinstance(value, bool) or isinstance(value, float):
        raise FormulaValidationError(
            f"{label} must be an integer, rational string, or Fraction"
        )
    try:
        result = value if isinstance(value, Fraction) else Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError) as error:
        raise FormulaValidationError(f"{label} is not a finite rational") from error
    return result


def fraction_value(value: Fraction) -> int | str:
    return value.numerator if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _point(value: Any, label: str) -> Point:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise FormulaValidationError(f"{label} must contain exactly two objectives")
    x = _integer(value[0], f"{label}[0]")
    y = _integer(value[1], f"{label}[1]")
    return (x, y)


def _points(values: Any, label: str, *, allow_empty: bool = False) -> list[Point]:
    if not isinstance(values, (list, tuple)):
        raise FormulaValidationError(f"{label} must be a sequence")
    result = [_point(value, f"{label}[{index}]") for index, value in enumerate(values)]
    if not allow_empty and not result:
        raise FormulaValidationError(f"{label} cannot be empty")
    return result


def _bits(value: Any, label: str) -> tuple[int, ...]:
    if isinstance(value, str):
        if not value or any(character not in "01" for character in value):
            raise FormulaValidationError(f"{label} must be a non-empty binary string")
        return tuple(int(character) for character in value)
    if not isinstance(value, (list, tuple)) or not value:
        raise FormulaValidationError(f"{label} must be a non-empty bit sequence")
    bits = tuple(_integer(bit, f"{label}[{index}]") for index, bit in enumerate(value))
    if any(bit not in (0, 1) for bit in bits):
        raise FormulaValidationError(f"{label} must contain only zero and one")
    return bits


def oneminmax(bits: Any) -> Point:
    parsed = _bits(bits, "bits")
    ones = sum(parsed)
    return (ones, len(parsed) - ones)


def weakly_dominates(left: Any, right: Any) -> bool:
    a = _point(left, "left")
    b = _point(right, "right")
    return a[0] >= b[0] and a[1] >= b[1]


def strictly_dominates(left: Any, right: Any) -> bool:
    a = _point(left, "left")
    b = _point(right, "right")
    return weakly_dominates(a, b) and a != b


def canonical_pareto(points: Any, *, allow_empty: bool = False) -> list[Point]:
    parsed = _points(points, "points", allow_empty=allow_empty)
    unique = sorted(set(parsed))
    return [
        point
        for point in unique
        if not any(strictly_dominates(other, point) for other in unique)
    ]


def pareto_insert(population: Any, child: Any) -> list[Point]:
    """Apply the source's sequential Pareto-set replacement semantics."""

    current = _points(population, "population")
    candidate = _point(child, "child")
    if canonical_pareto(current) != sorted(set(current)) or len(set(current)) != len(current):
        raise FormulaValidationError("population must be a unique Pareto set")
    if any(strictly_dominates(point, candidate) for point in current):
        return sorted(current)
    retained = [point for point in current if not weakly_dominates(candidate, point)]
    retained.append(candidate)
    return sorted(set(retained))


def hypervolume_2d(points: Any, reference: Any = (-1, -1)) -> int:
    """Exact maximization hypervolume of integer points in two dimensions."""

    ref = _point(reference, "reference")
    front = canonical_pareto(points)
    if any(point[0] < ref[0] or point[1] < ref[1] for point in front):
        raise FormulaValidationError("all points must weakly dominate the reference")
    volume = 0
    last_x = ref[0]
    for x, y in sorted(front):
        width = x - last_x
        if width < 0:
            raise FormulaValidationError("hypervolume front is not ordered")
        volume += width * (y - ref[1])
        last_x = x
    return volume


def mutation_probabilities(r: Any, n: Any, lambda_: Any) -> list[Fraction]:
    strength = _fraction(r, "r")
    dimension = _integer(n, "n")
    offspring = _integer(lambda_, "lambda")
    if strength <= 0 or dimension <= 0 or offspring <= 0 or offspring % 2:
        raise FormulaValidationError("r, n and even lambda must be positive")
    low = strength / (2 * dimension)
    high = 2 * strength / dimension
    if low <= 0 or high > 1:
        raise FormulaValidationError("mutation probability lies outside (0,1]")
    return [low] * (offspring // 2) + [high] * (offspring // 2)


def zero_truncated_binomial_count(draws: Any, n: Any) -> int:
    dimension = _integer(n, "n")
    if dimension <= 0 or not isinstance(draws, (list, tuple)) or not draws:
        raise FormulaValidationError("binomial tape must be a non-empty sequence")
    parsed = [_integer(value, f"draws[{index}]") for index, value in enumerate(draws)]
    if any(value < 0 or value > dimension for value in parsed):
        raise FormulaValidationError("binomial draw lies outside [0,n]")
    if parsed[-1] <= 0 or any(value != 0 for value in parsed[:-1]):
        raise FormulaValidationError("tape must end at the first positive binomial draw")
    return parsed[-1]


def mutate_bits(bits: Any, flip_indices: Any) -> tuple[int, ...]:
    parent = list(_bits(bits, "bits"))
    if not isinstance(flip_indices, (list, tuple)) or not flip_indices:
        raise FormulaValidationError("flip_indices must be a non-empty sequence")
    parsed = [
        _integer(index, f"flip_indices[{position}]")
        for position, index in enumerate(flip_indices)
    ]
    if len(set(parsed)) != len(parsed):
        raise FormulaValidationError("flip indices must be distinct")
    if any(index < 0 or index >= len(parent) for index in parsed):
        raise FormulaValidationError("flip index is outside the bit vector")
    for index in parsed:
        parent[index] = 1 - parent[index]
    return tuple(parent)


def adapt_two_rate(
    population: Any,
    children: Any,
    r: Any,
    q: Any,
    *,
    n: Any = 100,
    reference: Any = (-1, -1),
) -> dict[str, Any]:
    current = _points(population, "population")
    offspring = _points(children, "children")
    dimension = _integer(n, "n")
    strength = _fraction(r, "r")
    draw = _fraction(q, "q")
    if dimension <= 0 or len(offspring) <= 0 or len(offspring) % 2:
        raise FormulaValidationError("n and an even, positive child count are required")
    if strength < Fraction(1, 2) or strength > Fraction(dimension, 4):
        raise FormulaValidationError("r lies outside the frozen [1/2,n/4] bounds")
    if draw < 0 or draw > 1:
        raise FormulaValidationError("q must lie in [0,1]")
    if canonical_pareto(current) != sorted(set(current)) or len(set(current)) != len(current):
        raise FormulaValidationError("population must be a unique Pareto set")

    scores = [hypervolume_2d(current + [child], reference) for child in offspring]
    winner = max(range(len(scores)), key=scores.__getitem__)
    half = len(offspring) // 2
    s = Fraction(3, 4) if winner < half else Fraction(1, 4)
    decision = "halve" if draw <= s else "double"
    if decision == "halve":
        updated = max(strength / 2, Fraction(1, 2))
    else:
        updated = min(strength * 2, Fraction(dimension, 4))
    return {
        "scores": scores,
        "winner_index": winner,
        "winner_group": "low" if winner < half else "high",
        "s": fraction_value(s),
        "q": fraction_value(draw),
        "decision": decision,
        "r_before": fraction_value(strength),
        "r_after": fraction_value(updated),
    }


def generation_from_tape(case: Any) -> dict[str, Any]:
    """Execute one generation from an explicit, outcome-independent tape."""

    if not isinstance(case, dict):
        raise FormulaValidationError("generation case must be a dictionary")
    dimension = _integer(case.get("n"), "n")
    lambda_ = _integer(case.get("lambda"), "lambda")
    population_raw = case.get("population_bits")
    if not isinstance(population_raw, list) or not population_raw:
        raise FormulaValidationError("population_bits must be a non-empty list")
    population_bits = [
        _bits(value, f"population_bits[{index}]")
        for index, value in enumerate(population_raw)
    ]
    if any(len(bits) != dimension for bits in population_bits):
        raise FormulaValidationError("every population bit vector must have length n")
    population_points = [oneminmax(bits) for bits in population_bits]
    if len(set(population_points)) != len(population_points):
        raise FormulaValidationError("population objectives must be unique")
    if canonical_pareto(population_points) != sorted(population_points):
        raise FormulaValidationError("population objectives must form a Pareto set")

    tapes = case.get("children")
    if not isinstance(tapes, list) or len(tapes) != lambda_:
        raise FormulaValidationError("children tape length must equal lambda")
    rates = mutation_probabilities(case.get("r"), dimension, lambda_)
    child_points: list[Point] = []
    parent_indices: list[int] = []
    counts: list[int] = []
    for index, tape in enumerate(tapes):
        if not isinstance(tape, dict):
            raise FormulaValidationError(f"children[{index}] must be a dictionary")
        parent_index = _integer(tape.get("parent_index"), f"children[{index}].parent_index")
        if parent_index < 0 or parent_index >= len(population_bits):
            raise FormulaValidationError("parent index must address the pre-generation population")
        count = zero_truncated_binomial_count(tape.get("binomial_draws"), dimension)
        flip_indices = tape.get("flip_indices")
        if not isinstance(flip_indices, list) or len(flip_indices) != count:
            raise FormulaValidationError("positive binomial count must equal flip-index count")
        child_bits = mutate_bits(population_bits[parent_index], flip_indices)
        parent_indices.append(parent_index)
        counts.append(count)
        child_points.append(oneminmax(child_bits))

    adaptation = adapt_two_rate(
        population_points,
        child_points,
        case.get("r"),
        case.get("q"),
        n=dimension,
    )
    final_population = sorted(population_points)
    for child in child_points:
        final_population = pareto_insert(final_population, child)
    return {
        "n": dimension,
        "lambda": lambda_,
        "population_points_before": [list(point) for point in sorted(population_points)],
        "parent_indices": parent_indices,
        "mutation_probabilities": [fraction_value(rate) for rate in rates],
        "positive_binomial_counts": counts,
        "child_points": [list(point) for point in child_points],
        "adaptation": adaptation,
        "population_points_after": [list(point) for point in final_population],
        "hypervolume_after": hypervolume_2d(final_population),
    }


def validate_fixture(fixture: Any) -> dict[str, Any]:
    if not isinstance(fixture, dict) or fixture.get("schema_version") != "1.0.0":
        raise FormulaValidationError("fixture schema version is invalid")
    adaptation_results: list[dict[str, Any]] = []
    for entry in fixture.get("adaptation_cases", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("case_id"), str):
            raise FormulaValidationError("adaptation fixture case is malformed")
        actual = adapt_two_rate(
            entry.get("population"),
            entry.get("children"),
            entry.get("r"),
            entry.get("q"),
            n=entry.get("n"),
        )
        if actual != entry.get("expected"):
            raise FormulaValidationError(f"adaptation fixture mismatch: {entry['case_id']}")
        adaptation_results.append({"case_id": entry["case_id"], "result": actual})
    generation_results: list[dict[str, Any]] = []
    for entry in fixture.get("generation_cases", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("case_id"), str):
            raise FormulaValidationError("generation fixture case is malformed")
        actual = generation_from_tape(entry)
        if actual != entry.get("expected"):
            raise FormulaValidationError(f"generation fixture mismatch: {entry['case_id']}")
        generation_results.append({"case_id": entry["case_id"], "result": actual})
    if not adaptation_results or not generation_results:
        raise FormulaValidationError("fixture must contain adaptation and generation cases")
    invalid_results: list[dict[str, str]] = []
    for entry in fixture.get("invalid_generation_cases", []):
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("case_id"), str)
            or not isinstance(entry.get("expected_error"), str)
        ):
            raise FormulaValidationError("invalid-generation fixture case is malformed")
        try:
            generation_from_tape(entry.get("case"))
        except FormulaValidationError as error:
            if entry["expected_error"] not in str(error):
                raise FormulaValidationError(
                    f"unexpected invalid-case error: {entry['case_id']}"
                ) from error
            invalid_results.append({"case_id": entry["case_id"], "error": str(error)})
        else:
            raise FormulaValidationError(
                f"invalid generation fixture was accepted: {entry['case_id']}"
            )
    if not invalid_results:
        raise FormulaValidationError("fixture must contain invalid generation cases")
    return {
        "adaptation_cases": adaptation_results,
        "generation_cases": generation_results,
        "invalid_generation_cases": invalid_results,
    }

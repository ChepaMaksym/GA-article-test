"""Independent Python oracle for the narrow EU26-05 validation contract.

This module deliberately has no CEC-2017 implementation, no GA driver and no
published-result gate. Functions that depend on semantics missing from the
chapter require explicit conventions or reject the call.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
import math
from collections.abc import Sequence as RuntimeSequence
from typing import Any, Callable, Sequence


PROTOCOL_ID = "EU26-05-FORMULA-TRANSITION-v1"
PAPER_LEVEL_STATUS = "BLOCKED_SOURCE_BYTE_FREEZE_AND_STOCHASTIC_PROVENANCE"
SOURCE_BYTE_STATUS = "PASS_METADATA_ONLY"
SOURCE_FREEZE_STATUS = "BLOCKED_SOURCE_BYTE_FREEZE"
H0_SOURCE_STATUS = "PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE"
PROFILE = "FORMULA_AND_TRANSITION_VALIDATION_ONLY"


class ValidationError(ValueError):
    """Raised when a caller attempts an unfrozen or malformed transition."""


def _integer_vector(values: Sequence[int], name: str, length: int) -> tuple[int, ...]:
    if (
        not isinstance(values, RuntimeSequence)
        or isinstance(values, (str, bytes))
        or len(values) != length
    ):
        raise ValidationError(f"{name} must contain exactly {length} integers")
    result: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(f"{name} must contain integers, not booleans/floats")
        result.append(value)
    return tuple(result)


def _bits(value: str, name: str, minimum_length: int = 1) -> str:
    if not isinstance(value, str) or len(value) < minimum_length:
        raise ValidationError(f"{name} must be a binary string")
    if any(bit not in "01" for bit in value):
        raise ValidationError(f"{name} contains a non-binary character")
    return value


def update_probabilities(
    successes: Sequence[int], crossovers: Sequence[int]
) -> tuple[Fraction, Fraction, Fraction, Fraction]:
    """Apply the complete-positive-denominator four-type formula profile.

    A per-type zero denominator is not defined by the sources and therefore
    always fails closed. Fractions keep the oracle exact.
    """

    success = _integer_vector(successes, "successes", 4)
    total = _integer_vector(crossovers, "crossovers", 4)
    if any(value <= 0 for value in total):
        raise ValidationError("every crossover denominator must be positive")
    if any(value < 0 or value > count for value, count in zip(success, total)):
        raise ValidationError("successes must satisfy 0 <= successes <= crossovers")

    rates = tuple(Fraction(value, count) for value, count in zip(success, total))
    rate_sum = sum(rates, Fraction(0, 1))
    if rate_sum == 0:
        probabilities = (Fraction(1, 4),) * 4
    else:
        probabilities = tuple(
            Fraction(1, 10) + Fraction(3, 5) * rate / rate_sum for rate in rates
        )
    if sum(probabilities, Fraction(0, 1)) != 1:
        raise AssertionError("probability oracle violated normalization")
    if any(value < Fraction(1, 10) or value > Fraction(7, 10) for value in probabilities):
        raise AssertionError("probability oracle violated the frozen bounds")
    return probabilities  # type: ignore[return-value]


def _fraction_string(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = 40
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
        return format(decimal, ".12f")


def binary_decode_anchor(
    bits: str,
    lower: float,
    upper: float,
    *,
    bit_order: str,
    endpoint_convention: str,
) -> float:
    """Decode one explicit-convention block; this is not paper-faithful by default."""

    block = _bits(bits, "bits")
    if isinstance(lower, bool) or isinstance(upper, bool):
        raise ValidationError("decode bounds must be finite real scalars")
    if not isinstance(lower, (int, float)) or not isinstance(upper, (int, float)):
        raise ValidationError("decode bounds must be finite real scalars")
    if not math.isfinite(float(lower)) or not math.isfinite(float(upper)) or lower >= upper:
        raise ValidationError("decode bounds must be finite and increasing")
    if endpoint_convention != "closed_linear":
        raise ValidationError("the endpoint convention must be supplied as closed_linear")
    if bit_order == "msb_first":
        integer = int(block, 2)
    elif bit_order == "lsb_first":
        integer = int(block[::-1], 2)
    else:
        raise ValidationError("bit_order must be msb_first or lsb_first")
    maximum = (1 << len(block)) - 1
    return float(lower) + (float(upper) - float(lower)) * integer / maximum


def one_point_crossover(parent_a: str, parent_b: str, cut: int) -> tuple[str, str]:
    first = _bits(parent_a, "parent_a", minimum_length=2)
    second = _bits(parent_b, "parent_b", minimum_length=2)
    if len(first) != len(second):
        raise ValidationError("parents must have equal length")
    if isinstance(cut, bool) or not isinstance(cut, int) or not 1 <= cut < len(first):
        raise ValidationError("the fixed one-point cut must be an interior integer")
    return first[:cut] + second[cut:], second[:cut] + first[cut:]


def _maximum_extension_child(origin: str, through: str) -> str:
    # Thesis profile: copy `through`, then complement every common locus.
    child = [bit for bit in through]
    for index, (origin_bit, through_bit) in enumerate(zip(origin, through)):
        if origin_bit == through_bit:
            child[index] = "1" if through_bit == "0" else "0"
    result = "".join(child)
    complement_origin = "".join("1" if bit == "0" else "0" for bit in origin)
    if result != complement_origin:
        raise AssertionError("maximum-extension algebra does not complement the origin")
    return result


def maximum_extension_crossover(parent_a: str, parent_b: str) -> tuple[str, str]:
    first = _bits(parent_a, "parent_a", minimum_length=2)
    second = _bits(parent_b, "parent_b", minimum_length=2)
    if len(first) != len(second):
        raise ValidationError("parents must have equal length")
    return _maximum_extension_child(first, second), _maximum_extension_child(second, first)


def post_selection_transition(
    parent_a: str,
    parent_b: str,
    preference: int,
    *,
    cut: int | None,
) -> dict[str, Any]:
    """Apply a transition after P/P' has already supplied both parents."""

    if isinstance(preference, bool) or not isinstance(preference, int) or preference not in range(4):
        raise ValidationError("preference must be one of the experimental labels 0..3")
    if preference == 3:
        if cut is not None:
            raise ValidationError("maximum extension has no one-point cut")
        children = maximum_extension_crossover(parent_a, parent_b)
        operator = "thesis_maximum_extension_complement_origin"
    else:
        if cut is None:
            raise ValidationError("one-point transitions require an explicit frozen cut")
        children = one_point_crossover(parent_a, parent_b, cut)
        operator = "one_point_explicit_cut"
    return {
        "operator": operator,
        "preference": preference,
        "cut": cut,
        "children": list(children),
    }


def hamming_distance(left: str, right: str) -> int:
    first = _bits(left, "left")
    second = _bits(right, "right")
    if len(first) != len(second):
        raise ValidationError("Hamming operands must have equal length")
    return sum(a != b for a, b in zip(first, second))


def objective_interface_anchor(
    chromosome: str,
    objective: Callable[[tuple[float, ...]], float],
    *,
    bit_order: str,
    endpoint_convention: str,
    claimed_authenticated_cec: bool = False,
) -> dict[str, Any]:
    """Exercise a 30x20 decode/objective interface without supplying CEC functions."""

    genome = _bits(chromosome, "chromosome")
    if len(genome) != 600:
        raise ValidationError("the selected interface requires exactly 600 bits")
    if not callable(objective):
        raise ValidationError("objective must be an injected callable")
    if claimed_authenticated_cec:
        raise ValidationError("v1 has no authenticated CEC-2017 implementation")
    coordinates = tuple(
        binary_decode_anchor(
            genome[index : index + 20],
            -100.0,
            100.0,
            bit_order=bit_order,
            endpoint_convention=endpoint_convention,
        )
        for index in range(0, 600, 20)
    )
    value = objective(coordinates)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("the injected objective must return a real scalar")
    if not math.isfinite(float(value)):
        raise ValidationError("the injected objective returned NaN or Inf")
    return {"coordinates": list(coordinates), "value": float(value), "objective_kind": "toy_injected"}


def fixture_report(fixture: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(fixture, dict) or set(fixture) != {
        "schema_version",
        "protocol_id",
        "probability_cases",
        "decode_cases",
        "transition_cases",
    }:
        raise ValidationError("fixture top-level schema is not exact")
    if fixture.get("schema_version") != "1.0.0":
        raise ValidationError("fixture schema version is not EU26-05 v1")
    if fixture.get("protocol_id") != PROTOCOL_ID:
        raise ValidationError("fixture protocol identity is not EU26-05 v1")

    expected_probability_ids = [
        "all-zero-reset",
        "equal-rates",
        "single-dominant",
        "unequal-finite-decimals",
        "ordered-rates",
    ]
    expected_decode_ids = [
        "four-bit-lower",
        "four-bit-upper",
        "four-bit-msb-eight",
        "four-bit-lsb-one",
    ]
    expected_transition_ids = [
        "one-point-middle",
        "one-point-pref-two",
        "extension-two-directions",
        "extension-identical-parents",
    ]
    collections = (
        ("probability_cases", {"id", "successes", "crossovers", "expected"}, expected_probability_ids),
        (
            "decode_cases",
            {"id", "bits", "lower", "upper", "bit_order", "endpoint_convention", "expected"},
            expected_decode_ids,
        ),
        (
            "transition_cases",
            {"id", "parent_a", "parent_b", "preference", "cut", "operator", "expected_children"},
            expected_transition_ids,
        ),
    )
    for name, keys, expected_ids in collections:
        rows = fixture[name]
        if not isinstance(rows, list) or [row.get("id") if isinstance(row, dict) else None for row in rows] != expected_ids:
            raise ValidationError(f"{name} identities/order are not the frozen set")
        if any(set(row) != keys for row in rows):
            raise ValidationError(f"{name} row schema is not exact")

    probability_rows: list[dict[str, Any]] = []
    for case in fixture["probability_cases"]:
        values = update_probabilities(case["successes"], case["crossovers"])
        result = [_fraction_string(value) for value in values]
        if result != case["expected"]:
            raise AssertionError(f"probability fixture mismatch: {case['id']}")
        probability_rows.append({"id": case["id"], "probabilities": result})

    decode_rows: list[dict[str, Any]] = []
    for case in fixture["decode_cases"]:
        value = binary_decode_anchor(
            case["bits"],
            case["lower"],
            case["upper"],
            bit_order=case["bit_order"],
            endpoint_convention=case["endpoint_convention"],
        )
        result = format(value, ".12f")
        if result != case["expected"]:
            raise AssertionError(f"decode fixture mismatch: {case['id']}")
        decode_rows.append({"id": case["id"], "decoded": result})

    transition_rows: list[dict[str, Any]] = []
    for case in fixture["transition_cases"]:
        transition = post_selection_transition(
            case["parent_a"],
            case["parent_b"],
            case["preference"],
            cut=case["cut"],
        )
        if transition["operator"] != case["operator"] or transition["children"] != case["expected_children"]:
            raise AssertionError(f"transition fixture mismatch: {case['id']}")
        transition_rows.append(
            {
                "id": case["id"],
                "operator": transition["operator"],
                "children": transition["children"],
            }
        )

    return {
        "protocol_id": PROTOCOL_ID,
        "paper_level_status": PAPER_LEVEL_STATUS,
        "source_byte_status": SOURCE_BYTE_STATUS,
        "source_freeze_status": SOURCE_FREEZE_STATUS,
        "h0_source_status": H0_SOURCE_STATUS,
        "profile": PROFILE,
        "probability_cases": probability_rows,
        "decode_cases": decode_rows,
        "transition_cases": transition_rows,
    }

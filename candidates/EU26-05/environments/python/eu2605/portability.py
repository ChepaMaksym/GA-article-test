"""Deterministic EU26-05 formula-portability payloads.

Only the frozen clean-room formula and post-selection transition profiles are
exercised here.  This module contains no CEC functions, GA driver, parent
selection, success classifier, or published 27/30 endpoint evaluator.
"""

from __future__ import annotations

from fractions import Fraction
import itertools
from typing import Any

from .core import (
    fixture_report,
    hamming_distance,
    maximum_extension_crossover,
    objective_interface_anchor,
    one_point_crossover,
    post_selection_transition,
    update_probabilities,
)


PARALLEL_CASE_COUNT = 128


def _bitstrings(length: int) -> tuple[str, ...]:
    return tuple(format(value, f"0{length}b") for value in range(1 << length))


def property_summary() -> dict[str, Any]:
    """Recompute every frozen property count from first principles."""

    probability_cases = 0
    for successes in itertools.product(range(2), range(3), range(4), range(5)):
        values = update_probabilities(successes, (1, 2, 3, 4))
        if sum(values, Fraction(0, 1)) != 1:
            raise AssertionError("probability grid violated the simplex")
        if any(value < Fraction(1, 10) or value > Fraction(7, 10) for value in values):
            raise AssertionError("probability grid violated the frozen floor/range")
        probability_cases += 1

    values = _bitstrings(4)
    one_point_transitions = 0
    for first, second, cut in itertools.product(values, values, range(1, 4)):
        for child in one_point_crossover(first, second, cut):
            if (
                hamming_distance(first, child) + hamming_distance(child, second)
                != hamming_distance(first, second)
            ):
                raise AssertionError("one-point child left the Hamming interval")
        one_point_transitions += 1

    extension_children = 0
    for first, second in itertools.product(values, values):
        children = maximum_extension_crossover(first, second)
        complements = tuple(
            "".join("1" if bit == "0" else "0" for bit in parent)
            for parent in (first, second)
        )
        if children != complements:
            raise AssertionError("thesis extension profile did not complement its origin")
        extension_children += len(children)

    witness, _ = maximum_extension_crossover("0000", "0000")
    non_geometric_witness = (
        hamming_distance("0000", witness) + hamming_distance(witness, "0000")
        != hamming_distance("0000", "0000")
    )
    if not non_geometric_witness:
        raise AssertionError("extension adversarial witness stopped discriminating")

    objective = objective_interface_anchor(
        "0" * 600,
        lambda coordinates: sum(value * value for value in coordinates),
        bit_order="msb_first",
        endpoint_convention="closed_linear",
    )
    return {
        "probability_grid_cases": probability_cases,
        "probability_zero_denominator_policy": "REJECT",
        "one_point_four_bit_transitions": one_point_transitions,
        "one_point_property": "HAMMING_GEOMETRIC",
        "extension_four_bit_children": extension_children,
        "extension_profile": "THESIS_MAXIMUM_BINARY_COMPLEMENT_ORIGIN",
        "extension_author_code_claimed": False,
        "extension_non_geometric_witness": non_geometric_witness,
        "objective_anchor_kind": objective["objective_kind"],
        "objective_anchor_coordinates": len(objective["coordinates"]),
        "objective_anchor_value": objective["value"],
        "cec2017_claimed": False,
    }


def parallel_case(index: int) -> dict[str, Any]:
    """Build one deterministic worker case with no RNG or outcome data."""

    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < PARALLEL_CASE_COUNT:
        raise ValueError(f"parallel case index must be in 0..{PARALLEL_CASE_COUNT - 1}")
    totals = tuple(1 + (index + 3 * offset) % 9 for offset in range(4))
    successes = tuple((index * (offset + 2) + offset) % (total + 1) for offset, total in enumerate(totals))
    probabilities = update_probabilities(successes, totals)

    first = format((index * 73 + 19) % 4096, "012b")
    second = format((index * 151 + 7) % 4096, "012b")
    preference = index % 4
    cut = None if preference == 3 else 1 + (index * 5) % 11
    transition = post_selection_transition(first, second, preference, cut=cut)
    return {
        "case_id": f"formula-transition-{index:03d}",
        "successes": list(successes),
        "crossovers": list(totals),
        "probabilities": [f"{value.numerator}/{value.denominator}" for value in probabilities],
        "parent_a": first,
        "parent_b": second,
        "preference": preference,
        "cut": cut,
        "operator": transition["operator"],
        "children": transition["children"],
    }


def expected_parallel_cases() -> list[dict[str, Any]]:
    return [parallel_case(index) for index in range(PARALLEL_CASE_COUNT)]


def scientific_payload(
    fixture: dict[str, Any], parallel_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Assemble the exact payload compared across Work4/Work8/GitHub4."""

    expected_ids = [f"formula-transition-{index:03d}" for index in range(PARALLEL_CASE_COUNT)]
    if [row.get("case_id") for row in parallel_rows] != expected_ids:
        raise ValueError("parallel rows are incomplete, duplicated, or out of order")
    return {
        "fixture_report": fixture_report(fixture),
        "property_summary": property_summary(),
        "parallel_cases": parallel_rows,
    }

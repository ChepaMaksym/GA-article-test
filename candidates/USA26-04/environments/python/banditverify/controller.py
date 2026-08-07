"""Local controller equations and explicit USA26-04 ambiguity witnesses."""

from __future__ import annotations

import copy
from decimal import Decimal, ROUND_FLOOR
import math
from numbers import Real
from typing import Any

from .rewards import evaluate_reward


FIXTURE_STATE_PROVENANCE = "synthetic_fixture_not_article_state"


def _finite_real(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number, not a boolean")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def paper_tile_index(x: Real, left: Real, offset: Real, width: Real) -> int:
    point = _finite_real("x", x)
    lower = _finite_real("left", left)
    shift = _finite_real("offset", offset)
    span = _finite_real("width", width)
    if span <= 0.0:
        raise ValueError("tile width must be positive")
    return math.floor((point - shift - lower) / span) + 1


def nesterov_update(
    value: Real,
    momentum: Real,
    reward: Real,
    learning_rate: Real,
    momentum_factor: Real,
) -> dict[str, float]:
    current_value = _finite_real("value", value)
    current_momentum = _finite_real("momentum", momentum)
    target = _finite_real("reward", reward)
    gamma = _finite_real("learning_rate", learning_rate)
    mu = _finite_real("momentum_factor", momentum_factor)
    if gamma <= 0.0:
        raise ValueError("learning rate must be positive")
    if not 0.0 <= mu < 1.0:
        raise ValueError("momentum factor must be in [0,1)")
    gradient = 2.0 * (current_value - target)
    next_momentum = mu * current_momentum + gradient
    next_value = current_value - gamma * (gradient + mu * next_momentum)
    if not all(math.isfinite(item) for item in (gradient, next_momentum, next_value)):
        raise ArithmeticError("controller update produced a non-finite value")
    return {
        "gradient": gradient,
        "momentum": next_momentum,
        "value": next_value,
    }


def tile_boundary_witness(
    left: str = "-100",
    right: str = "100",
    resolution: str = "0.03",
) -> dict[str, Any]:
    """Demonstrate the source's uncovered-tail versus overshoot conflict."""

    lower = Decimal(left)
    upper = Decimal(right)
    width = Decimal(resolution)
    if not lower < upper or width <= 0:
        raise ValueError("boundary witness requires left < right and positive resolution")
    count = int(((upper - lower) / width).to_integral_value(rounding=ROUND_FLOOR))
    clamped_index = count - 1
    clamped_lower = lower + width * clamped_index
    clamped_upper = clamped_lower + width
    next_lower = lower + width * count
    next_upper = next_lower + width
    uncovered = upper - clamped_upper
    overshoot = next_upper - upper
    confirmed = uncovered > 0 and overshoot > 0 and clamped_upper == next_lower
    return {
        "status": "AMBIGUITY_CONFIRMED" if confirmed else "NO_AMBIGUITY",
        "resolution_chosen": False,
        "floor_tile_count": count,
        "last_clamped_tile": clamped_index,
        "last_clamped_interval": [float(clamped_lower), float(clamped_upper)],
        "next_tile": count,
        "next_interval": [float(next_lower), float(next_upper)],
        "declared_right": float(upper),
        "uncovered_width_if_clamped": float(uncovered),
        "overshoot_width_if_next_tile": float(overshoot),
    }


def tie_ambiguity_witness(weights: list[Real], epsilon: Real = 0.0) -> dict[str, Any]:
    if not isinstance(weights, list) or not weights:
        raise ValueError("weights must be a nonempty list")
    values = [_finite_real("weight", item) for item in weights]
    exploration = _finite_real("epsilon", epsilon)
    if not 0.0 <= exploration <= 1.0:
        raise ValueError("epsilon must be in [0,1]")
    best = max(values)
    maximizers = [index for index, value in enumerate(values) if value == best]
    ambiguous = exploration == 0.0 and len(maximizers) > 1
    return {
        "status": "AMBIGUITY_CONFIRMED" if ambiguous else "UNIQUE_OR_EXPLORATORY",
        "resolution_chosen": False,
        "maximizer_tiles": maximizers,
        "selected_tile": None,
    }


def standard_deviation_witness() -> dict[str, Any]:
    actual = math.log(2.0) / math.sqrt(3.0)
    printed_expression = math.sqrt(2.0 * math.log(2.0) / 12.0)
    stated = 0.223
    return {
        "status": "AMBIGUITY_CONFIRMED",
        "resolution_chosen": False,
        "actual_sd_log_two_to_uniform": actual,
        "printed_symbolic_value": printed_expression,
        "stated_numeric_value": stated,
        "all_distinct_at_1e-3": (
            abs(actual - printed_expression) > 1e-3
            and abs(actual - stated) > 1e-3
            and abs(printed_expression - stated) > 1e-3
        ),
    }


def _coding_value(coding: dict[str, Any], paper_index: int) -> float:
    values = coding.get("values_by_paper_index")
    if not isinstance(values, list) or not 0 <= paper_index < len(values):
        raise ValueError(f"paper tile index {paper_index} has no supplied synthetic value")
    if values[paper_index] is None:
        raise ValueError(f"paper tile index {paper_index} points to a null sentinel")
    return _finite_real("coding value", values[paper_index])


def _unique_argmax(values: list[float]) -> int:
    maximum = max(values)
    indices = [index for index, value in enumerate(values) if value == maximum]
    if len(indices) != 1:
        raise ValueError("fixed-tape transition requires a unique maximum; tie is source-ambiguous")
    return indices[0]


def run_fixed_controller_tape(fixture: dict[str, Any]) -> dict[str, Any]:
    """Run the explicitly synthetic, interior fixed-tape controller transition."""

    if not isinstance(fixture, dict):
        raise TypeError("fixed controller fixture must be an object")
    description = fixture.get("description")
    if not isinstance(description, str) or "not article state" not in description:
        raise ValueError("fixture must explicitly state that its initial state is not article state")
    if fixture.get("reward_semantics") != "P1":
        raise ValueError("the frozen controller fixture requires primary semantics P1")
    search = fixture.get("search")
    tape = fixture.get("tape")
    codings = fixture.get("codings")
    if not isinstance(search, dict) or not isinstance(tape, dict):
        raise ValueError("fixture search and tape must be objects")
    if not isinstance(codings, list) or not codings:
        raise ValueError("fixture must supply at least one synthetic coding")

    left = _finite_real("left", search.get("left"))
    right = _finite_real("right", search.get("right"))
    resolution = _finite_real("resolution", search.get("resolution"))
    epsilon = _finite_real("epsilon", search.get("epsilon"))
    history_length = search.get("history_length")
    if not left < right or resolution <= 0.0:
        raise ValueError("fixed search requires left < right and positive resolution")
    raw_count = (right - left) / resolution
    base_tile_count = round(raw_count)
    if not math.isclose(raw_count, base_tile_count, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("synthetic fixture must divide its range into exact base tiles")
    if not isinstance(history_length, int) or isinstance(history_length, bool) or history_length < 1:
        raise ValueError("history length must be a positive integer")
    if not 0.0 <= epsilon <= 1.0:
        raise ValueError("epsilon must be in [0,1]")

    base_weights: list[float] = []
    for base_index in range(base_tile_count):
        point = left + base_index * resolution
        associated = []
        for coding in codings:
            paper_index = paper_tile_index(
                point,
                left,
                coding.get("offset"),
                coding.get("width"),
            )
            associated.append(_coding_value(coding, paper_index))
        base_weights.append(math.fsum(associated) / len(associated))

    epsilon_uniform = _finite_real("epsilon_uniform", tape.get("epsilon_uniform"))
    if not 0.0 <= epsilon_uniform < 1.0:
        raise ValueError("epsilon tape value must be in [0,1)")
    if epsilon_uniform < epsilon:
        branch = "explore"
        selected_before_noise = tape.get("exploration_tile")
        if not isinstance(selected_before_noise, int) or isinstance(selected_before_noise, bool):
            raise ValueError("exploration tile must be an integer")
        argmax_tile = None
    else:
        branch = "exploit"
        argmax_tile = _unique_argmax(base_weights)
        selected_before_noise = argmax_tile

    noise_floor = tape.get("noise_floor")
    if not isinstance(noise_floor, int) or isinstance(noise_floor, bool):
        raise ValueError("the already-floored noise tape value must be an integer")
    selected_tile = min(max(selected_before_noise + noise_floor, 0), base_tile_count - 1)
    within_uniform = _finite_real("within_tile_uniform", tape.get("within_tile_uniform"))
    if not 0.0 <= within_uniform < 1.0:
        raise ValueError("within-tile tape value must be in [0,1)")
    log_rate = left + resolution * (selected_tile + within_uniform)
    rate = math.exp(log_rate)

    immediate_reward = evaluate_reward(
        "P1", fixture.get("parent_error"), fixture.get("child_error")
    )
    next_codings = copy.deepcopy(codings)
    updates: list[dict[str, Any]] = []
    for coding_index, coding in enumerate(next_codings):
        paper_index = paper_tile_index(
            log_rate,
            left,
            coding.get("offset"),
            coding.get("width"),
        )
        values = coding.get("values_by_paper_index")
        momenta = coding.get("momenta_by_paper_index")
        histories = coding.get("histories_by_paper_index")
        if not all(isinstance(field, list) for field in (values, momenta, histories)):
            raise ValueError("synthetic coding state arrays must be lists")
        if not all(paper_index < len(field) for field in (values, momenta, histories)):
            raise ValueError("synthetic coding state does not cover the selected paper index")
        history = histories[paper_index]
        if not isinstance(history, list):
            raise ValueError("synthetic history must be a supplied list")
        history_values = [_finite_real("history reward", item) for item in history]
        history_values.append(immediate_reward)
        history_values = history_values[-history_length:]
        max_reward = max(history_values)
        update = nesterov_update(
            _coding_value(coding, paper_index),
            momenta[paper_index],
            max_reward,
            coding.get("learning_rate"),
            coding.get("momentum_factor"),
        )
        values[paper_index] = update["value"]
        momenta[paper_index] = update["momentum"]
        histories[paper_index] = history_values
        updates.append(
            {
                "coding": coding_index,
                "paper_index": paper_index,
                "history": history_values,
                "max_reward": max_reward,
                **update,
            }
        )

    return {
        "verification_scope": "FORMULA_AND_AMBIGUITY_VALIDATION_ONLY",
        "paper_level_status": "BLOCKED_G5_G9",
        "published_result_status": "INCONCLUSIVE_PUBLISHED_RESULT",
        "state_provenance": FIXTURE_STATE_PROVENANCE,
        "base_weights": base_weights,
        "branch": branch,
        "argmax_tile": argmax_tile,
        "selected_tile": selected_tile,
        "log_rate": log_rate,
        "rate": rate,
        "immediate_reward": immediate_reward,
        "updates": updates,
        "next_codings": next_codings,
    }

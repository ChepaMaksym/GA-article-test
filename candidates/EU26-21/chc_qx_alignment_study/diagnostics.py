"""Independent one-bit diagnostics after QX search, with no feedback or escape."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from .search import DIMENSION, _mask, _score


def _certificate(
    mask: tuple[int, ...], objective: Callable[[tuple[int, ...]], float], scope: str,
) -> dict[str, Any]:
    center = _score(objective(mask))
    evaluations = [{"call": 1, "bit": None, "mask": list(mask), "wba": center}]
    higher = equal = lower = 0
    for bit in range(DIMENSION):
        neighbor = list(mask)
        neighbor[bit] = 1 - neighbor[bit]
        neighbor_mask = tuple(neighbor)
        score = _score(objective(neighbor_mask))
        relation = "higher" if score > center else "equal" if score == center else "lower"
        higher += int(relation == "higher")
        equal += int(relation == "equal")
        lower += int(relation == "lower")
        evaluations.append({
            "call": bit + 2, "bit": bit, "mask": list(neighbor_mask),
            "wba": score, "difference_from_center": score - center, "relation": relation,
        })
    local = higher == 0
    return {
        "scope": scope, "center_wba": center, "objective_calls": DIMENSION + 1,
        "local_maximum": local, "strict_local_maximum": local and equal == 0,
        "plateau_local_maximum": local and equal > 0,
        "higher_neighbors": higher, "equal_neighbors": equal, "lower_neighbors": lower,
        "evaluations": evaluations, "numerical_tolerance": 0.0,
        "global_optimality": "not_assessed", "non_globality": "not_assessed",
    }


def certify_snapshot(
    *, snapshot: Mapping[str, Any],
    active_objective: Callable[[tuple[int, ...]], float],
    full_objective: Callable[[tuple[int, ...]], float],
) -> dict[str, Any]:
    """Reevaluate both centers independently; query every one-bit neighbor."""
    if not callable(active_objective) or not callable(full_objective):
        raise TypeError("both diagnostic objectives must be callable")
    if not isinstance(snapshot, Mapping) or "mask" not in snapshot:
        raise ValueError("a diagnostic snapshot with its center mask is required")
    mask = _mask(snapshot["mask"])
    approximate = _certificate(mask, active_objective, "active_training_validation_WBA")
    full = _certificate(mask, full_objective, "full_internal_training_validation_WBA")
    classification = {
        (False, False): "neither_local",
        (True, False): "approximate_only_false_local",
        (True, True): "both_local",
        (False, True): "full_only_local",
    }[(approximate["local_maximum"], full["local_maximum"])]
    return {
        "schema": "eu26-21-chc-qx-diagnostic-v1", "center_mask": list(mask),
        "snapshot": dict(snapshot), "approximate": approximate, "full": full,
        "classification": classification, "active_objective_calls": DIMENSION + 1,
        "full_objective_calls": DIMENSION + 1, "objective_calls": 2 * (DIMENSION + 1),
        "independent_center_reevaluation": True, "feed_back_to_search": False,
        "two_bit_audit": False, "controlled_escape": False,
    }

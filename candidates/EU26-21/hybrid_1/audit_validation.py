"""Independent strict validation for the frozen Hybrid 1 evidence.

This module does not rerun or tune either optimizer.  It validates the recorded
row structure, fixes the historical analysis-only first-hit guard, and then
recomputes the frozen paired decisions from immutable seed rows.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .paired_comparison import DEFAULT_TARGETS
from . import run_old_hybrid_comparison_v2 as v2


DIMENSION = 41
EXPECTED_INITIAL_POPULATION = 50
EXPECTED_SEARCH_SEED_OFFSET = 1_000_003


def corrected_capped(value: Optional[int], budget: int) -> Tuple[int, bool]:
    """Censor a missing/late first hit and accept every positive call index.

    A hit in ``1..50`` is valid because the common initial population is
    evaluated sequentially and may already contain a target-reaching mask.
    """

    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
        raise ValueError("budget must be a positive integer")
    if value is None or int(value) > budget:
        return budget, False
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("first-hit NFE must be an integer or None")
    if value < 1:
        raise ValueError("first-hit NFE must be positive")
    return value, True


def _target_key(target: float) -> str:
    return f"{float(target):.6f}"


def _validate_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} must be a 64-character digest")
    if any(character not in "0123456789abcdef" for character in value.lower()):
        raise ValueError(f"{label} is not hexadecimal")


def _validate_selected_mask(result: Mapping[str, Any], label: str) -> None:
    selected = result.get("selected_features")
    mask = result.get("best_mask")
    if not isinstance(selected, list) or not selected:
        raise ValueError(f"{label}: selected feature list is empty")
    if not isinstance(mask, list) or len(mask) != DIMENSION:
        raise ValueError(f"{label}: best mask must contain {DIMENSION} bits")
    if any(isinstance(value, bool) or int(value) not in (0, 1) for value in mask):
        raise ValueError(f"{label}: best mask is not binary")
    normalized = [int(value) for value in selected]
    if normalized != sorted(set(normalized)):
        raise ValueError(f"{label}: selected feature indices are not unique/sorted")
    if any(not 0 <= index < DIMENSION for index in normalized):
        raise ValueError(f"{label}: selected feature index is outside the mask")
    derived = [index for index, bit in enumerate(mask) if int(bit) == 1]
    if derived != normalized:
        raise ValueError(f"{label}: selected indices disagree with best mask")
    if int(result.get("selected_feature_count", -1)) != len(normalized):
        raise ValueError(f"{label}: selected feature count is inconsistent")


def _validate_target_map(
    mapping: Any,
    *,
    targets: Sequence[float],
    maximum_nfe: int,
    best_primary: float,
    label: str,
) -> None:
    if not isinstance(mapping, Mapping):
        raise ValueError(f"{label}: target map is missing")
    expected_keys = [_target_key(target) for target in targets]
    if set(mapping) != set(expected_keys):
        raise ValueError(f"{label}: target map keys do not match the frozen targets")
    if not math.isfinite(best_primary):
        raise ValueError(f"{label}: best evaluated primary fitness is not finite")

    previous_nfe = 0
    lower_target_missing = False
    for target, key in zip(targets, expected_keys):
        raw = mapping[key]
        if raw is None:
            lower_target_missing = True
            if best_primary + 1e-15 >= target:
                raise ValueError(f"{label}: reached target {target} lacks first-hit NFE")
            continue
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise TypeError(f"{label}: target NFE must be an integer or None")
        if lower_target_missing:
            raise ValueError(f"{label}: a higher target is hit after a lower target is missing")
        if not 1 <= raw <= maximum_nfe:
            raise ValueError(f"{label}: target NFE lies outside executed evaluations")
        if raw < previous_nfe:
            raise ValueError(f"{label}: target first-hit NFEs are not monotone")
        if best_primary + 1e-15 < target:
            raise ValueError(f"{label}: target hit exceeds recorded best fitness")
        previous_nfe = raw


def validate_row_strict(
    row: Mapping[str, Any],
    seed: int,
    targets: Iterable[float] = DEFAULT_TARGETS,
) -> None:
    """Fail closed on provenance, configuration, mask, and NFE inconsistencies."""

    target_values = tuple(sorted(float(target) for target in targets))
    v2._validate_row(row, seed)

    if int(row.get("initial_population", -1)) != EXPECTED_INITIAL_POPULATION:
        raise ValueError(f"seed {seed}: initial population mismatch")
    _validate_digest(row.get("active_indices_sha256"), f"seed {seed} active digest")
    _validate_digest(row.get("initial_masks_sha256"), f"seed {seed} mask digest")

    old = row["old"]
    h1 = row["hybrid_h1"]
    h3 = row["hybrid_h3"]
    assert isinstance(old, Mapping) and isinstance(h1, Mapping) and isinstance(h3, Mapping)

    for label, result in (("OLD", old), ("H1", h1), ("H3", h3)):
        if int(result.get("seed", -1)) != seed:
            raise ValueError(f"seed {seed}: {label} seed mismatch")
        if int(result.get("search_seed", -1)) != seed + EXPECTED_SEARCH_SEED_OFFSET:
            raise ValueError(f"seed {seed}: {label} search seed mismatch")

    if h1.get("reset") is not True or h3.get("reset") is not True:
        raise ValueError(f"seed {seed}: Hybrid result did not use reset=True")
    if h1.get("exact_first_hit") is not False:
        raise ValueError(f"seed {seed}: H1 must not claim exact threaded first-hit NFE")
    if h3.get("exact_first_hit") is not True or int(h3.get("workers", -1)) != 1:
        raise ValueError(f"seed {seed}: H3 exact first-hit protocol is invalid")

    _validate_selected_mask(h1, f"seed {seed} H1")
    _validate_selected_mask(h3, f"seed {seed} H3")

    h1_targets = h1.get("nfe_to_target")
    if not isinstance(h1_targets, Mapping) or set(h1_targets) != {
        _target_key(target) for target in target_values
    }:
        raise ValueError(f"seed {seed}: H1 target placeholder map is invalid")
    if any(value is not None for value in h1_targets.values()):
        raise ValueError(f"seed {seed}: H1 threaded run must not claim exact first-hit NFE")

    old_maximum = int(old.get("optimizer_nfe", 0))
    _validate_target_map(
        old.get("active_nfe_to_target"),
        targets=target_values,
        maximum_nfe=old_maximum,
        best_primary=float(old.get("best_active_fitness", float("nan"))),
        label=f"seed {seed} OLD",
    )
    _validate_target_map(
        h3.get("nfe_to_target"),
        targets=target_values,
        maximum_nfe=int(h3.get("evaluations", 0)),
        best_primary=float(h3.get("best_evaluated_primary", float("nan"))),
        label=f"seed {seed} H3",
    )


def evaluate_strict(
    rows: Sequence[Mapping[str, Any]],
    targets: Sequence[float] = DEFAULT_TARGETS,
) -> Dict[str, Any]:
    """Recompute v2 decisions after strict row validation and guard correction."""

    for seed, row in enumerate(rows, start=1):
        validate_row_strict(row, seed, targets)

    original_capped = v2._capped
    try:
        v2._capped = corrected_capped
        report = v2.evaluate(rows, targets)
    finally:
        v2._capped = original_capped

    raw_h2_decision = report["h2"]["decision"]
    report["h2"]["unconditional_decision"] = raw_h2_decision
    if not str(report["h1"]["decision"]).startswith("PASS"):
        report["h2"]["decision"] = "BLOCKED_BY_H1"

    report["audit_gates"] = {
        "A0_STRICT_ROW_SCHEMA": True,
        "A1_RESET_CONFIGURATION": True,
        "A2_MASK_INDEX_CONSISTENCY": True,
        "A3_TARGET_NFE_MONOTONICITY": True,
        "A4_POSITIVE_INITIAL_POPULATION_HITS": True,
        "A5_H2_CONDITIONAL_ON_H1": True,
    }
    report["audit_status"] = "PASS_STRICT_REVALIDATION"
    return report

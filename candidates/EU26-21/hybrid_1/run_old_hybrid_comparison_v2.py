#!/usr/bin/env python3
"""Corrected 30-seed OLD CHC-QX versus Hybrid 1 experiment.

Primary inferential decisions use the lower endpoint of a two-sided 95% BCa
interval (alpha=0.025), which is more conservative than the earlier one-sided
95% draft. Hypothesis failure is reported as a scientific result; only protocol
or implementation failure makes the workflow fail.
"""
from __future__ import annotations

import argparse
import gc
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hybrid_1.paired_comparison import (
        DEFAULT_ACTIVE_SAMPLE_SIZE,
        DEFAULT_TARGETS,
    )
    from hybrid_1.paired_comparison_v2 import run_paired_seed_v2
    from hybrid_1.run_old_hybrid_comparison import _bca_quantiles
else:
    from .paired_comparison import DEFAULT_ACTIVE_SAMPLE_SIZE, DEFAULT_TARGETS
    from .paired_comparison_v2 import run_paired_seed_v2
    from .run_old_hybrid_comparison import _bca_quantiles

SCHEMA = "eu26-21-old-hybrid-paired-v2"
RUNS = 30
INITIAL_POPULATION = 50
H1_BUDGET = 400
H3_BUDGET = 2_500
H1_MARGIN = 0.001
PRIMARY_TARGET = 0.946
BOOTSTRAP_RESAMPLES = 50_000


def _target_key(target: float) -> str:
    return f"{float(target):.6f}"


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values))


def _bca_interval(values: Sequence[float], *, seed: int, resamples: int) -> Dict[str, Any]:
    quantiles = _bca_quantiles(
        values,
        alphas=(0.025, 0.05, 0.975),
        seed=seed,
        resamples=resamples,
    )
    return {
        "point_median": _median(values),
        "two_sided_95": [
            quantiles["0.025000"],
            quantiles["0.975000"],
        ],
        "two_sided_95_lower": quantiles["0.025000"],
        "one_sided_95_lower": quantiles["0.050000"],
        "values": [float(value) for value in values],
    }


def _validate_row(row: Mapping[str, Any], seed: int) -> None:
    if row.get("schema") != "eu26-21-old-hybrid-paired-row-v2":
        raise ValueError(f"seed {seed}: row schema mismatch")
    if int(row.get("seed", -1)) != seed:
        raise ValueError(f"seed {seed}: row seed mismatch")
    if int(row.get("active_sample_size", -1)) != DEFAULT_ACTIVE_SAMPLE_SIZE:
        raise ValueError(f"seed {seed}: active sample size mismatch")
    for field in ("active_indices_sha256", "initial_masks_sha256"):
        value = row.get(field)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"seed {seed}: invalid {field}")

    old = row.get("old")
    h1 = row.get("hybrid_h1")
    h3 = row.get("hybrid_h3")
    if not all(isinstance(value, Mapping) for value in (old, h1, h3)):
        raise ValueError(f"seed {seed}: missing optimizer results")
    assert isinstance(old, Mapping) and isinstance(h1, Mapping) and isinstance(h3, Mapping)

    if old.get("active_indices_sha256") != row.get("active_indices_sha256"):
        raise ValueError(f"seed {seed}: OLD active digest mismatch")
    if int(old.get("optimizer_nfe", 0)) != (
        int(old.get("active_nfe", 0)) + int(old.get("full_validation_nfe", 0))
    ):
        raise ValueError(f"seed {seed}: OLD NFE accounting mismatch")
    if int(h1.get("budget", -1)) != H1_BUDGET:
        raise ValueError(f"seed {seed}: H1 budget mismatch")
    if int(h3.get("budget", -1)) != H3_BUDGET:
        raise ValueError(f"seed {seed}: H3 budget mismatch")
    if h3.get("exact_first_hit") is not True or int(h3.get("workers", -1)) != 1:
        raise ValueError(f"seed {seed}: H3 first-hit protocol is not exact")
    if h1.get("exact_first_hit") is not False:
        raise ValueError(f"seed {seed}: H1 protocol flag mismatch")
    if int(h1.get("workers", -1)) != 4:
        raise ValueError(f"seed {seed}: H1 worker setting mismatch")

    for name, result in (("H1", h1), ("H3", h3)):
        evaluations = int(result.get("evaluations", 0))
        budget = int(result.get("budget", 0))
        if not INITIAL_POPULATION <= evaluations <= budget:
            raise ValueError(f"seed {seed}: invalid {name} NFE")
        selected = result.get("selected_features")
        if not isinstance(selected, list) or not selected:
            raise ValueError(f"seed {seed}: empty {name} feature subset")
        for metric in ("validation_accuracy", "test_accuracy"):
            value = float(result.get(metric, -1.0))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"seed {seed}: invalid {name} {metric}")


def _capped(value: Optional[int], budget: int) -> Tuple[int, bool]:
    if value is None or int(value) > budget:
        return int(budget), False
    result = int(value)
    if result < INITIAL_POPULATION:
        raise ValueError("first-hit NFE predates the common initial population")
    return result, True


def _target_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    target: float,
    budget: int,
    bootstrap_seed: int,
    resamples: int,
) -> Dict[str, Any]:
    key = _target_key(target)
    old_capped: List[int] = []
    hybrid_capped: List[int] = []
    old_hits: List[bool] = []
    hybrid_hits: List[bool] = []

    for row in rows:
        old = row["old"]
        hybrid = row["hybrid_h3"]
        assert isinstance(old, Mapping) and isinstance(hybrid, Mapping)
        old_targets = old["active_nfe_to_target"]
        hybrid_targets = hybrid["nfe_to_target"]
        assert isinstance(old_targets, Mapping) and isinstance(hybrid_targets, Mapping)
        old_value, old_hit = _capped(old_targets.get(key), budget)
        hybrid_value, hybrid_hit = _capped(hybrid_targets.get(key), budget)
        old_capped.append(old_value)
        hybrid_capped.append(hybrid_value)
        old_hits.append(old_hit)
        hybrid_hits.append(hybrid_hit)

    paired_reduction = [
        (float(old_value) - float(hybrid_value)) / float(old_value)
        for old_value, hybrid_value in zip(old_capped, hybrid_capped)
    ]
    interval = _bca_interval(
        paired_reduction,
        seed=bootstrap_seed,
        resamples=resamples,
    )
    old_reached = sum(old_hits)
    hybrid_reached = sum(hybrid_hits)
    common_reached = sum(
        old_hit and hybrid_hit
        for old_hit, hybrid_hit in zip(old_hits, hybrid_hits)
    )
    required_common = math.ceil(0.80 * len(rows))
    restricted_mean_reduction = (
        statistics.fmean(old_capped) - statistics.fmean(hybrid_capped)
    ) / statistics.fmean(old_capped)

    point_pass = (
        common_reached >= required_common
        and hybrid_reached >= old_reached
        and float(interval["point_median"]) >= 0.20
    )
    confidence_pass = (
        point_pass
        and float(interval["two_sided_95_lower"]) >= 0.20
    )
    return {
        "target": float(target),
        "target_semantics": (
            "first evaluated active-sample validation objective reaching target; "
            "OLD NFE includes prior outer full-validation reevaluations"
        ),
        "censor_budget": int(budget),
        "old_reached": old_reached,
        "hybrid_reached": hybrid_reached,
        "common_reached": common_reached,
        "required_common_reached": required_common,
        "old_capped_nfe": old_capped,
        "hybrid_capped_nfe": hybrid_capped,
        "old_median_capped_nfe": _median([float(value) for value in old_capped]),
        "hybrid_median_capped_nfe": _median(
            [float(value) for value in hybrid_capped]
        ),
        "restricted_mean_relative_reduction": restricted_mean_reduction,
        "paired_relative_reduction": interval,
        "point_gate_20_percent": point_pass,
        "confidence_gate_20_percent": confidence_pass,
        "decision": (
            "PASS_CONFIDENCE_BOUND"
            if confidence_pass
            else "PASS_POINT_ONLY"
            if point_pass
            else "FAIL_OR_INSUFFICIENT_TARGET_COVERAGE"
        ),
    }


def evaluate(rows: Sequence[Mapping[str, Any]], targets: Sequence[float]) -> Dict[str, Any]:
    if len(rows) != RUNS:
        raise ValueError(f"the frozen campaign requires {RUNS} rows")
    for seed, row in enumerate(rows, start=1):
        _validate_row(row, seed)

    old_accuracy = [float(row["old"]["test_accuracy"]) for row in rows]  # type: ignore[index]
    hybrid_accuracy = [
        float(row["hybrid_h1"]["test_accuracy"]) for row in rows  # type: ignore[index]
    ]
    paired_accuracy = [
        hybrid - old for hybrid, old in zip(hybrid_accuracy, old_accuracy)
    ]
    old_features = [
        len(row["old"]["selected_features"]) for row in rows  # type: ignore[index]
    ]
    hybrid_features = [
        int(row["hybrid_h1"]["selected_feature_count"]) for row in rows  # type: ignore[index]
    ]
    paired_features = [
        hybrid - old for hybrid, old in zip(hybrid_features, old_features)
    ]
    baselines = [float(row["baseline_test_accuracy"]) for row in rows]

    paired_interval = _bca_interval(
        paired_accuracy,
        seed=2026081601,
        resamples=BOOTSTRAP_RESAMPLES,
    )
    hybrid_interval = _bca_interval(
        hybrid_accuracy,
        seed=2026081602,
        resamples=BOOTSTRAP_RESAMPLES,
    )
    baseline_gain_count = sum(
        hybrid - baseline >= 0.015
        for hybrid, baseline in zip(hybrid_accuracy, baselines)
    )
    required_baseline_gain = math.ceil(0.80 * RUNS)
    h1_point_pass = float(paired_interval["point_median"]) >= -H1_MARGIN
    h1_confidence_pass = (
        float(paired_interval["two_sided_95_lower"]) >= -H1_MARGIN
    )
    h1_decision = (
        "PASS_CONFIDENCE_BOUND"
        if h1_confidence_pass and baseline_gain_count >= required_baseline_gain
        else "PASS_POINT_ONLY"
        if h1_point_pass and baseline_gain_count >= required_baseline_gain
        else "FAIL_NONINFERIORITY_OR_BASELINE_GAIN"
    )

    target_reports = {
        _target_key(target): _target_report(
            rows,
            target=target,
            budget=H3_BUDGET,
            bootstrap_seed=2026081700 + index,
            resamples=BOOTSTRAP_RESAMPLES,
        )
        for index, target in enumerate(targets)
    }
    primary_key = _target_key(PRIMARY_TARGET)
    primary = target_reports[primary_key]

    protocol_gates = {
        "P0_COMPLETE_30_SEEDS": len(rows) == RUNS,
        "P1_SEED_LEDGER": [int(row["seed"]) for row in rows]
        == list(range(1, RUNS + 1)),
        "P2_FIXED_ACTIVE_SAMPLE": all(
            int(row["active_sample_size"]) == DEFAULT_ACTIVE_SAMPLE_SIZE
            for row in rows
        ),
        "P3_COMMON_INITIAL_MASK_DIGESTS": all(
            isinstance(row["initial_masks_sha256"], str)
            and len(row["initial_masks_sha256"]) == 64
            for row in rows
        ),
        "P4_EXACT_OLD_NFE": all(
            int(row["old"]["optimizer_nfe"])  # type: ignore[index]
            == int(row["old"]["active_nfe"])  # type: ignore[index]
            + int(row["old"]["full_validation_nfe"])  # type: ignore[index]
            for row in rows
        ),
        "P5_EXACT_HYBRID_FIRST_HIT": all(
            row["hybrid_h3"]["exact_first_hit"] is True  # type: ignore[index]
            and int(row["hybrid_h3"]["workers"]) == 1  # type: ignore[index]
            for row in rows
        ),
    }
    protocol_pass = all(protocol_gates.values())

    return {
        "schema": SCHEMA,
        "claim_status": (
            "PASS_PROTOCOL_RESULTS_AVAILABLE"
            if protocol_pass
            else "BLOCKED_PROTOCOL_FAILURE"
        ),
        "protocol_gates": protocol_gates,
        "parameters": {
            "runs": RUNS,
            "seed_ledger": list(range(1, RUNS + 1)),
            "active_sample_size": DEFAULT_ACTIVE_SAMPLE_SIZE,
            "initial_population": INITIAL_POPULATION,
            "h1_budget": H1_BUDGET,
            "h3_budget": H3_BUDGET,
            "h1_workers": 4,
            "h3_workers": 1,
            "h1_noninferiority_margin": H1_MARGIN,
            "primary_h3_target": PRIMARY_TARGET,
            "targets": list(targets),
            "bootstrap_method": "BCa paired median",
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "primary_confidence_rule": "lower endpoint of two-sided 95% BCa interval",
        },
        "h1": {
            "decision": h1_decision,
            "margin": H1_MARGIN,
            "old_test_accuracy": {
                "mean": statistics.fmean(old_accuracy),
                "median": _median(old_accuracy),
                "values": old_accuracy,
            },
            "hybrid_test_accuracy": {
                "mean": statistics.fmean(hybrid_accuracy),
                "median": _median(hybrid_accuracy),
                "interval": hybrid_interval,
                "values": hybrid_accuracy,
            },
            "paired_hybrid_minus_old": paired_interval,
            "point_noninferiority": h1_point_pass,
            "confidence_bound_noninferiority": h1_confidence_pass,
            "runs_improving_all_feature_baseline_by_1_5_points": baseline_gain_count,
            "required_baseline_gain_runs": required_baseline_gain,
        },
        "h2": {
            "decision": (
                "PASS"
                if _median([float(value) for value in paired_features]) <= 0.0
                else "FAIL"
            ),
            "old_feature_count_median": _median(
                [float(value) for value in old_features]
            ),
            "hybrid_feature_count_median": _median(
                [float(value) for value in hybrid_features]
            ),
            "paired_hybrid_minus_old_feature_count_median": _median(
                [float(value) for value in paired_features]
            ),
            "paired_values": paired_features,
        },
        "h3": {
            "primary_target": PRIMARY_TARGET,
            "primary_decision": primary["decision"],
            "target_reports": target_reports,
        },
        "rows": list(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--enforce-protocol", action="store_true")
    args = parser.parse_args()

    targets = tuple(DEFAULT_TARGETS)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    for seed in range(1, RUNS + 1):
        row = run_paired_seed_v2(
            args.upstream.resolve(),
            seed=seed,
            active_sample_size=DEFAULT_ACTIVE_SAMPLE_SIZE,
            initial_population=INITIAL_POPULATION,
            h1_budget=H1_BUDGET,
            h3_budget=H3_BUDGET,
            h1_workers=4,
            targets=targets,
        )
        _validate_row(row, seed)
        (output_dir / f"seed-{seed:02d}.json").write_text(
            json.dumps(row, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        rows.append(row)
        print(
            json.dumps(
                {
                    "seed": seed,
                    "old_test_accuracy": row["old"]["test_accuracy"],
                    "hybrid_test_accuracy": row["hybrid_h1"]["test_accuracy"],
                    "old_optimizer_nfe": row["old"]["optimizer_nfe"],
                    "hybrid_h3_nfe": row["hybrid_h3"]["evaluations"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        gc.collect()

    report = evaluate(rows, targets)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "claim_status": report["claim_status"],
                "protocol_gates": report["protocol_gates"],
                "h1_decision": report["h1"]["decision"],
                "h2_decision": report["h2"]["decision"],
                "h3_primary_decision": report["h3"]["primary_decision"],
            },
            sort_keys=True,
        )
    )
    if args.enforce_protocol and report["claim_status"] != "PASS_PROTOCOL_RESULTS_AVAILABLE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

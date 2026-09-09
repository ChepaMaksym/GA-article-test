#!/usr/bin/env python3
"""Run the frozen 30-seed OLD CHC-QX versus Hybrid 1 experiment.

This campaign closes two previously open questions:

* H1: confidence-bound non-inferiority of Hybrid 1 test accuracy;
* H3: logical feature-mask evaluation efficiency at matched validation targets.

The experiment is paired by seed. Both optimizers receive the same encoded
Census data, the same fixed 14,964-instance active sample, and the same 50
initial feature masks. Scientific hypothesis failure does not fail CI; CI fails
only when the protocol, provenance, or result structure is invalid.
"""
from __future__ import annotations

import argparse
import gc
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import norm

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hybrid_1.paired_comparison import (
        DEFAULT_ACTIVE_SAMPLE_SIZE,
        DEFAULT_TARGETS,
        run_paired_seed,
    )
else:
    from .paired_comparison import (
        DEFAULT_ACTIVE_SAMPLE_SIZE,
        DEFAULT_TARGETS,
        run_paired_seed,
    )

SCHEMA = "eu26-21-old-hybrid-paired-v1"
DEFAULT_RUNS = 30
DEFAULT_H1_MARGIN = 0.001  # 0.10 percentage point in probability units
DEFAULT_PRIMARY_TARGET = 0.946
DEFAULT_H1_BUDGET = 400
DEFAULT_H3_BUDGET = 2_500
DEFAULT_INITIAL_POPULATION = 50
DEFAULT_BOOTSTRAP_RESAMPLES = 50_000

Statistic = Callable[[np.ndarray], float]


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values))


def _target_key(target: float) -> str:
    return f"{float(target):.6f}"


def _bca_quantiles(
    values: Sequence[float],
    *,
    alphas: Sequence[float],
    seed: int,
    resamples: int,
    statistic: Statistic = lambda data: float(np.median(data)),
) -> Dict[str, float]:
    """Return deterministic BCa bootstrap quantiles for one scalar statistic."""

    data = np.asarray(list(values), dtype=float)
    if data.ndim != 1 or data.size < 3:
        raise ValueError("BCa input must contain at least three scalar values")
    alpha_values = tuple(float(alpha) for alpha in alphas)
    if any(not 0.0 < alpha < 1.0 for alpha in alpha_values):
        raise ValueError("BCa alphas must lie strictly inside (0,1)")
    if resamples < 5_000:
        raise ValueError("BCa resamples must be at least 5000")
    if not np.all(np.isfinite(data)):
        raise ValueError("BCa input must be finite")

    observed = float(statistic(data))
    if np.all(data == data[0]):
        return {f"{alpha:.6f}": observed for alpha in alpha_values}

    rng = np.random.default_rng(seed)
    indices = rng.integers(0, data.size, size=(resamples, data.size))
    samples = data[indices]
    # All campaign statistics currently use the median. Keeping the callable in
    # the API makes tests explicit while retaining vectorized execution here.
    if statistic is not _mean_statistic:
        bootstrap = np.median(samples, axis=1)
    else:
        bootstrap = np.mean(samples, axis=1)

    less = float(np.count_nonzero(bootstrap < observed))
    equal = float(np.count_nonzero(bootstrap == observed))
    probability = (less + 0.5 * equal) / float(resamples)
    epsilon = 0.5 / float(resamples)
    probability = min(max(probability, epsilon), 1.0 - epsilon)
    bias = float(norm.ppf(probability))

    jackknife = np.asarray(
        [statistic(np.delete(data, index)) for index in range(data.size)],
        dtype=float,
    )
    jackknife_mean = float(np.mean(jackknife))
    centered = jackknife_mean - jackknife
    denominator = 6.0 * float(np.sum(centered ** 2)) ** 1.5
    acceleration = (
        0.0
        if denominator == 0.0
        else float(np.sum(centered ** 3)) / denominator
    )

    output: Dict[str, float] = {}
    for alpha in alpha_values:
        z_value = float(norm.ppf(alpha))
        inner = bias + z_value
        correction_denominator = 1.0 - acceleration * inner
        if abs(correction_denominator) < 1e-12:
            adjusted = alpha
        else:
            adjusted = float(
                norm.cdf(bias + inner / correction_denominator)
            )
        adjusted = min(max(adjusted, 0.0), 1.0)
        output[f"{alpha:.6f}"] = float(np.quantile(bootstrap, adjusted))
    return output


def _mean_statistic(data: np.ndarray) -> float:
    return float(np.mean(data))


def _interval_payload(
    values: Sequence[float],
    *,
    seed: int,
    resamples: int,
) -> Dict[str, Any]:
    quantiles = _bca_quantiles(
        values,
        alphas=(0.025, 0.05, 0.975),
        seed=seed,
        resamples=resamples,
    )
    return {
        "point_median": _median(values),
        "bca_two_sided_95": [
            quantiles["0.025000"],
            quantiles["0.975000"],
        ],
        "bca_one_sided_95_lower": quantiles["0.050000"],
        "values": [float(value) for value in values],
    }


def _validate_row(row: Mapping[str, Any], seed: int) -> None:
    if int(row.get("seed", -1)) != seed:
        raise ValueError(f"seed {seed}: row seed mismatch")
    if int(row.get("active_sample_size", -1)) != DEFAULT_ACTIVE_SAMPLE_SIZE:
        raise ValueError(f"seed {seed}: active sample size mismatch")
    for digest_name in ("active_indices_sha256", "initial_masks_sha256"):
        digest = row.get(digest_name)
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"seed {seed}: invalid {digest_name}")

    old = row.get("old")
    h1 = row.get("hybrid_h1")
    h3 = row.get("hybrid_h3")
    if not all(isinstance(value, Mapping) for value in (old, h1, h3)):
        raise ValueError(f"seed {seed}: missing optimizer result")
    assert isinstance(old, Mapping) and isinstance(h1, Mapping) and isinstance(h3, Mapping)

    if old.get("active_indices_sha256") != row.get("active_indices_sha256"):
        raise ValueError(f"seed {seed}: OLD active sample digest mismatch")
    if int(h1.get("budget", -1)) != DEFAULT_H1_BUDGET:
        raise ValueError(f"seed {seed}: H1 budget mismatch")
    if int(h3.get("budget", -1)) != DEFAULT_H3_BUDGET:
        raise ValueError(f"seed {seed}: H3 budget mismatch")
    if int(old.get("active_nfe", 0)) < DEFAULT_INITIAL_POPULATION:
        raise ValueError(f"seed {seed}: invalid OLD active NFE")
    if int(old.get("optimizer_nfe", 0)) < int(old.get("active_nfe", 0)):
        raise ValueError(f"seed {seed}: invalid OLD optimizer NFE")
    for result_name, result in (("H1", h1), ("H3", h3)):
        evaluations = int(result.get("evaluations", 0))
        budget = int(result.get("budget", 0))
        if not DEFAULT_INITIAL_POPULATION <= evaluations <= budget:
            raise ValueError(f"seed {seed}: invalid {result_name} NFE")
        selected = result.get("selected_features")
        if not isinstance(selected, list) or not selected:
            raise ValueError(f"seed {seed}: empty {result_name} subset")
        for metric in ("validation_accuracy", "test_accuracy"):
            value = float(result.get(metric, -1.0))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"seed {seed}: invalid {result_name} {metric}")


def _capped_hit(raw: Optional[int], budget: int) -> Tuple[int, bool]:
    if raw is None or int(raw) > budget:
        return budget, False
    value = int(raw)
    if value < DEFAULT_INITIAL_POPULATION:
        raise ValueError("target NFE predates the common initial population")
    return value, True


def _target_efficiency(
    rows: Sequence[Mapping[str, Any]],
    *,
    target: float,
    budget: int,
    resamples: int,
    bootstrap_seed: int,
) -> Dict[str, Any]:
    key = _target_key(target)
    old_capped: List[int] = []
    hybrid_capped: List[int] = []
    old_reached: List[bool] = []
    hybrid_reached: List[bool] = []

    for row in rows:
        old = row["old"]
        hybrid = row["hybrid_h3"]
        assert isinstance(old, Mapping) and isinstance(hybrid, Mapping)
        old_map = old["active_nfe_to_target"]
        hybrid_map = hybrid["nfe_to_target"]
        assert isinstance(old_map, Mapping) and isinstance(hybrid_map, Mapping)
        old_value, old_hit = _capped_hit(old_map.get(key), budget)
        hybrid_value, hybrid_hit = _capped_hit(hybrid_map.get(key), budget)
        old_capped.append(old_value)
        hybrid_capped.append(hybrid_value)
        old_reached.append(old_hit)
        hybrid_reached.append(hybrid_hit)

    relative_reductions = [
        (float(old_value) - float(hybrid_value)) / float(old_value)
        for old_value, hybrid_value in zip(old_capped, hybrid_capped)
    ]
    interval = _interval_payload(
        relative_reductions,
        seed=bootstrap_seed,
        resamples=resamples,
    )
    common_reached = sum(
        first and second
        for first, second in zip(old_reached, hybrid_reached)
    )
    old_reach_count = sum(old_reached)
    hybrid_reach_count = sum(hybrid_reached)
    restricted_mean_reduction = (
        statistics.fmean(old_capped) - statistics.fmean(hybrid_capped)
    ) / statistics.fmean(old_capped)
    point_pass = (
        common_reached >= math.ceil(0.80 * len(rows))
        and hybrid_reach_count >= old_reach_count
        and float(interval["point_median"]) >= 0.20
    )
    confidence_pass = (
        point_pass
        and float(interval["bca_one_sided_95_lower"]) >= 0.20
    )
    return {
        "target": float(target),
        "budget": int(budget),
        "old_reached": old_reach_count,
        "hybrid_reached": hybrid_reach_count,
        "common_reached": common_reached,
        "required_common_reached": math.ceil(0.80 * len(rows)),
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


def evaluate_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    h1_margin: float,
    primary_target: float,
    targets: Sequence[float],
    h3_budget: int,
    resamples: int,
) -> Dict[str, Any]:
    if len(rows) < 3:
        raise ValueError("at least three paired rows are required")
    expected_seeds = list(range(1, len(rows) + 1))
    for seed, row in zip(expected_seeds, rows):
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

    h1_paired_interval = _interval_payload(
        paired_accuracy,
        seed=2026081601,
        resamples=resamples,
    )
    h1_hybrid_interval = _interval_payload(
        hybrid_accuracy,
        seed=2026081602,
        resamples=resamples,
    )
    h1_point_pass = float(h1_paired_interval["point_median"]) >= -h1_margin
    h1_confidence_pass = (
        float(h1_paired_interval["bca_one_sided_95_lower"])
        >= -h1_margin
    )
    baseline_gain_count = sum(
        hybrid - baseline >= 0.015
        for hybrid, baseline in zip(hybrid_accuracy, baselines)
    )
    required_baseline_gain = math.ceil(0.80 * len(rows))

    target_reports = {
        _target_key(target): _target_efficiency(
            rows,
            target=target,
            budget=h3_budget,
            resamples=resamples,
            bootstrap_seed=2026081700 + index,
        )
        for index, target in enumerate(targets)
    }
    primary_key = _target_key(primary_target)
    if primary_key not in target_reports:
        raise ValueError("primary target is missing from target reports")
    primary_report = target_reports[primary_key]

    protocol_gates = {
        "P0_COMPLETE_30_SEEDS": len(rows) == DEFAULT_RUNS,
        "P1_SEED_LEDGER": [int(row["seed"]) for row in rows]
        == list(range(1, DEFAULT_RUNS + 1)),
        "P2_FIXED_ACTIVE_SAMPLE": all(
            int(row["active_sample_size"]) == DEFAULT_ACTIVE_SAMPLE_SIZE
            for row in rows
        ),
        "P3_COMMON_INITIAL_MASKS": all(
            isinstance(row["initial_masks_sha256"], str)
            and len(row["initial_masks_sha256"]) == 64
            for row in rows
        ),
        "P4_EXACT_LOGICAL_NFE_PRESENT": all(
            int(row["old"]["active_nfe"]) >= DEFAULT_INITIAL_POPULATION  # type: ignore[index]
            and int(row["hybrid_h3"]["evaluations"]) >= DEFAULT_INITIAL_POPULATION  # type: ignore[index]
            for row in rows
        ),
    }
    protocol_pass = all(protocol_gates.values())

    h1_status = (
        "PASS_CONFIDENCE_BOUND"
        if h1_confidence_pass and baseline_gain_count >= required_baseline_gain
        else "PASS_POINT_ONLY"
        if h1_point_pass and baseline_gain_count >= required_baseline_gain
        else "FAIL_NONINFERIORITY_OR_BASELINE_GAIN"
    )
    h2_point_pass = _median([float(value) for value in paired_features]) <= 0.0

    return {
        "schema": SCHEMA,
        "claim_status": (
            "PASS_PROTOCOL_RESULTS_AVAILABLE"
            if protocol_pass
            else "BLOCKED_PROTOCOL_FAILURE"
        ),
        "protocol_gates": protocol_gates,
        "parameters": {
            "runs": len(rows),
            "seed_ledger": list(range(1, len(rows) + 1)),
            "active_sample_size": DEFAULT_ACTIVE_SAMPLE_SIZE,
            "initial_population": DEFAULT_INITIAL_POPULATION,
            "h1_budget": DEFAULT_H1_BUDGET,
            "h3_budget": h3_budget,
            "h1_noninferiority_margin": h1_margin,
            "primary_h3_target": primary_target,
            "targets": list(targets),
            "bootstrap_method": "BCa",
            "bootstrap_resamples": resamples,
        },
        "h1": {
            "decision": h1_status,
            "margin": h1_margin,
            "old_test_accuracy": {
                "mean": statistics.fmean(old_accuracy),
                "median": _median(old_accuracy),
                "values": old_accuracy,
            },
            "hybrid_test_accuracy": {
                "mean": statistics.fmean(hybrid_accuracy),
                "median": _median(hybrid_accuracy),
                "interval": h1_hybrid_interval,
                "values": hybrid_accuracy,
            },
            "paired_hybrid_minus_old": h1_paired_interval,
            "point_noninferiority": h1_point_pass,
            "confidence_bound_noninferiority": h1_confidence_pass,
            "runs_improving_all_feature_baseline_by_1_5_points": (
                baseline_gain_count
            ),
            "required_baseline_gain_runs": required_baseline_gain,
        },
        "h2": {
            "decision": "PASS" if h2_point_pass else "FAIL",
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
            "primary_target": primary_target,
            "primary_decision": primary_report["decision"],
            "target_reports": target_reports,
        },
        "rows": list(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument(
        "--active-sample-size",
        type=int,
        default=DEFAULT_ACTIVE_SAMPLE_SIZE,
    )
    parser.add_argument(
        "--initial-population",
        type=int,
        default=DEFAULT_INITIAL_POPULATION,
    )
    parser.add_argument("--h1-budget", type=int, default=DEFAULT_H1_BUDGET)
    parser.add_argument("--h3-budget", type=int, default=DEFAULT_H3_BUDGET)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--targets",
        type=float,
        nargs="+",
        default=list(DEFAULT_TARGETS),
    )
    parser.add_argument(
        "--primary-target",
        type=float,
        default=DEFAULT_PRIMARY_TARGET,
    )
    parser.add_argument(
        "--h1-margin",
        type=float,
        default=DEFAULT_H1_MARGIN,
    )
    parser.add_argument(
        "--bootstrap-resamples",
        type=int,
        default=DEFAULT_BOOTSTRAP_RESAMPLES,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--enforce-protocol", action="store_true")
    args = parser.parse_args()

    if args.seed_start != 1:
        raise SystemExit("the frozen extended ledger must start at seed 1")
    if args.runs != DEFAULT_RUNS:
        raise SystemExit(f"the frozen extended ledger requires {DEFAULT_RUNS} runs")
    if args.active_sample_size != DEFAULT_ACTIVE_SAMPLE_SIZE:
        raise SystemExit("the frozen paired protocol requires active size 14964")
    if args.initial_population != DEFAULT_INITIAL_POPULATION:
        raise SystemExit("the frozen paired protocol requires 50 initial masks")
    if args.h1_budget != DEFAULT_H1_BUDGET or args.h3_budget != DEFAULT_H3_BUDGET:
        raise SystemExit("the frozen H1/H3 budgets are 400 and 2500")
    targets = tuple(sorted(set(float(value) for value in args.targets)))
    if args.primary_target not in targets:
        raise SystemExit("primary target must be included in --targets")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    for seed in range(1, DEFAULT_RUNS + 1):
        row_path = output_dir / f"seed-{seed:02d}.json"
        row = run_paired_seed(
            args.upstream.resolve(),
            seed=seed,
            active_sample_size=args.active_sample_size,
            initial_population=args.initial_population,
            h1_budget=args.h1_budget,
            h3_budget=args.h3_budget,
            workers=args.workers,
            targets=targets,
        )
        _validate_row(row, seed)
        row_path.write_text(
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
                    "old_active_nfe": row["old"]["active_nfe"],
                    "hybrid_h3_nfe": row["hybrid_h3"]["evaluations"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        gc.collect()

    report = evaluate_rows(
        rows,
        h1_margin=args.h1_margin,
        primary_target=args.primary_target,
        targets=targets,
        h3_budget=args.h3_budget,
        resamples=args.bootstrap_resamples,
    )
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

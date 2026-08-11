#!/usr/bin/env python3
"""Run and evaluate the preregistered ten-seed Colon OLD campaign.

This module executes only the pinned author-source compatibility profile. It
contains no PR #8 or HYBRID optimizer logic.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any, Iterable, Sequence

PAPER_ACCURACY = 0.94
PAPER_SUBSET_LENGTH = 6.0
PAPER_BASELINE = 0.69
EXPECTED_SEEDS = list(range(1, 11))
# Two-sided 95% Student-t critical value, df=9, frozen because the campaign
# has exactly ten runs.
T_CRITICAL_DF9 = 2.2621571628540993
CAMPAIGN_PREFIX = "EU26_20_CAMPAIGN="

DETERMINISTIC_FIELDS = (
    "best_accuracy",
    "subset_length",
    "features",
    "precision",
    "recall",
    "fscore",
    "mcc",
    "nfe",
    "iterations",
    "adaptive_events",
    "final_pc",
    "final_pm",
    "first_target_iteration",
    "first_target_nfe",
)


def _mean_ci95(values: Sequence[float]) -> dict[str, float]:
    if len(values) != 10:
        raise ValueError("the preregistered confidence interval requires 10 values")
    mean = statistics.fmean(values)
    sd = statistics.stdev(values)
    half_width = T_CRITICAL_DF9 * sd / math.sqrt(len(values))
    return {
        "mean": float(mean),
        "sample_sd": float(sd),
        "ci95_low": float(mean - half_width),
        "ci95_high": float(mean + half_width),
        "median": float(statistics.median(values)),
        "min": float(min(values)),
        "max": float(max(values)),
    }


def _same_fields(a: dict[str, Any], b: dict[str, Any], fields: Iterable[str]) -> bool:
    return all(a.get(key) == b.get(key) for key in fields)


def _validate_result(result: dict[str, Any], seed: int) -> None:
    expected = {
        "schema": "eu26-20-colon-old-v1",
        "profile": "author_source_compatibility",
        "seed": seed,
        "upstream_commit": "d24e61e78ac197ad75342e8f4be5d63d17bd9e7a",
        "offspring_rounding": "python_round_ties_to_even",
        "dataset_rows": 62,
        "raw_features": 2000,
        "class_labels": [1, 2],
        "class_counts": [22, 40],
        "search_space_size": 128,
        "baseline_accuracy": PAPER_BASELINE,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise ValueError(f"seed {seed}: {key}={result.get(key)!r}, expected {value!r}")

    features = result.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError(f"seed {seed}: missing selected features")
    if len(features) != len(set(features)):
        raise ValueError(f"seed {seed}: duplicate selected features")
    if result.get("subset_length") != len(features):
        raise ValueError(f"seed {seed}: subset length mismatch")

    for key in ("source_sha256", "dataset_sha256", "features_sha256"):
        value = result.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"seed {seed}: invalid {key}")

    for key in ("best_accuracy", "precision", "recall", "fscore"):
        value = result.get(key)
        if value is not None and not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"seed {seed}: invalid {key}={value!r}")
    if int(result.get("nfe", 0)) <= 0 or int(result.get("iterations", 0)) <= 0:
        raise ValueError(f"seed {seed}: invalid effort accounting")


def evaluate_campaign(
    results: Sequence[dict[str, Any]],
    repeated_first: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate G0-G5 using the frozen NUMERIC_GATE.md criteria."""
    if [int(row.get("seed", -1)) for row in results] != EXPECTED_SEEDS:
        raise ValueError("results must be ordered for seeds 1..10")
    for seed, row in zip(EXPECTED_SEEDS, results):
        _validate_result(row, seed)
    _validate_result(repeated_first, 1)

    identity_fields = (
        "upstream_commit",
        "source_sha256",
        "dataset_sha256",
        "features_sha256",
        "dataset_rows",
        "raw_features",
        "class_labels",
        "class_counts",
        "search_space_size",
        "profile",
        "offspring_rounding",
    )
    identity_reference = results[0]
    identity_consistent = all(
        _same_fields(identity_reference, row, identity_fields) for row in results[1:]
    )
    deterministic = _same_fields(results[0], repeated_first, DETERMINISTIC_FIELDS)

    accuracies = [float(row["best_accuracy"]) for row in results]
    subset_lengths = [float(row["subset_length"]) for row in results]
    nfes = [float(row["nfe"]) for row in results]
    iterations = [float(row["iterations"]) for row in results]
    adaptive_events = [float(row["adaptive_events"]) for row in results]

    accuracy_stats = _mean_ci95(accuracies)
    subset_stats = _mean_ci95(subset_lengths)
    nfe_stats = _mean_ci95(nfes)
    iteration_stats = _mean_ci95(iterations)
    adaptation_stats = _mean_ci95(adaptive_events)

    gates: dict[str, dict[str, Any]] = {}
    gates["G0_provenance_structure"] = {
        "pass": bool(identity_consistent),
        "detail": "all source/data/search-space identities and structural checks agree",
    }
    gates["G1_deterministic_replay"] = {
        "pass": bool(deterministic),
        "detail": "seed 1 repeated with exact algorithm/result fields",
    }
    baseline_pass = all(float(row["baseline_accuracy"]) == PAPER_BASELINE for row in results)
    gates["G2_baseline_endpoint"] = {
        "pass": baseline_pass,
        "observed": sorted({float(row["baseline_accuracy"]) for row in results}),
        "target": PAPER_BASELINE,
    }

    accuracy_distance = abs(accuracy_stats["mean"] - PAPER_ACCURACY)
    accuracy_ci_contains = (
        accuracy_stats["ci95_low"] <= PAPER_ACCURACY <= accuracy_stats["ci95_high"]
    )
    gates["G3_final_accuracy_alignment"] = {
        "pass": bool(accuracy_distance <= 0.03 and accuracy_ci_contains),
        "target": PAPER_ACCURACY,
        "absolute_mean_difference": float(accuracy_distance),
        "tolerance": 0.03,
        "ci_contains_target": bool(accuracy_ci_contains),
        "statistics": accuracy_stats,
    }

    subset_distance = abs(subset_stats["mean"] - PAPER_SUBSET_LENGTH)
    subset_ci_contains = (
        subset_stats["ci95_low"] <= PAPER_SUBSET_LENGTH <= subset_stats["ci95_high"]
    )
    gates["G4_subset_length_alignment"] = {
        "pass": bool(subset_distance <= 1.5 and subset_ci_contains),
        "target": PAPER_SUBSET_LENGTH,
        "absolute_mean_difference": float(subset_distance),
        "tolerance": 1.5,
        "ci_contains_target": bool(subset_ci_contains),
        "statistics": subset_stats,
    }

    strong_improvements = sum(
        value >= PAPER_BASELINE + 0.20 - 1e-12 for value in accuracies
    )
    no_regressions = min(accuracies) >= PAPER_BASELINE
    gates["G5_qualitative_improvement"] = {
        "pass": bool(strong_improvements >= 8 and no_regressions),
        "runs_improving_by_at_least_0_20": int(strong_improvements),
        "required": 8,
        "minimum_final_accuracy": float(min(accuracies)),
        "baseline": PAPER_BASELINE,
    }

    all_pass = all(bool(gate["pass"]) for gate in gates.values())
    claim_status = "PASS_OLD_REPRODUCTION" if all_pass else "BLOCKED_NUMERIC_MISMATCH"
    if not gates["G0_provenance_structure"]["pass"] or not gates[
        "G1_deterministic_replay"
    ]["pass"]:
        claim_status = "BLOCKED_IMPLEMENTATION_OR_PROVENANCE"

    return {
        "schema": "eu26-20-colon-campaign-v1",
        "claim_status": claim_status,
        "profile": "author_source_compatibility",
        "seed_ledger": EXPECTED_SEEDS,
        "runs": len(results),
        "paper_targets": {
            "baseline_accuracy": PAPER_BASELINE,
            "mean_accuracy": PAPER_ACCURACY,
            "mean_subset_length": PAPER_SUBSET_LENGTH,
            "mean_nfe_diagnostic": 788,
            "nfe_claim_note": (
                "Table 8 caption says 3 runs while nearby prose says 10; "
                "NFE is diagnostic only"
            ),
        },
        "gates": gates,
        "statistics": {
            "accuracy": accuracy_stats,
            "subset_length": subset_stats,
            "nfe": nfe_stats,
            "iterations": iteration_stats,
            "adaptive_events": adaptation_stats,
            "runs_at_or_above_paper_accuracy": int(
                sum(value >= PAPER_ACCURACY for value in accuracies)
            ),
        },
        "deterministic_fields": list(DETERMINISTIC_FIELDS),
        "results": list(results),
        "repeated_seed_1": repeated_first,
    }


def _run_one(
    upstream: Path,
    seed: int,
    output_dir: Path,
    timeout_seconds: int,
    suffix: str = "",
) -> dict[str, Any]:
    stem = f"seed-{seed}{suffix}"
    output_json = output_dir / f"{stem}.json"
    log_file = output_dir / f"{stem}.log"
    runner = Path(__file__).with_name("run_author_colon.py")
    command = [
        sys.executable,
        str(runner),
        str(upstream),
        "--seed",
        str(seed),
        "--quiet",
        "--output-json",
        str(output_json),
        "--log-file",
        str(log_file),
    ]
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_seconds,
        check=False,
    )
    (output_dir / f"{stem}.driver.log").write_text(
        completed.stdout, encoding="utf-8"
    )
    if completed.returncode:
        raise RuntimeError(
            f"seed {seed}{suffix} failed with exit {completed.returncode}; see {log_file}"
        )
    if not output_json.is_file():
        raise RuntimeError(f"seed {seed}{suffix} produced no JSON result")
    return json.loads(output_json.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--timeout-per-run", type=int, default=300)
    parser.add_argument(
        "--enforce-reproduction",
        action="store_true",
        help="return nonzero unless all preregistered gates pass",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        _run_one(args.upstream.resolve(), seed, output_dir, args.timeout_per_run)
        for seed in EXPECTED_SEEDS
    ]
    repeated = _run_one(
        args.upstream.resolve(), 1, output_dir, args.timeout_per_run, suffix="-repeat"
    )
    report = evaluate_campaign(results, repeated)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    compact = {
        "claim_status": report["claim_status"],
        "accuracy": report["statistics"]["accuracy"],
        "subset_length": report["statistics"]["subset_length"],
        "nfe": report["statistics"]["nfe"],
        "gates": {key: bool(value["pass"]) for key, value in report["gates"].items()},
    }
    print(CAMPAIGN_PREFIX + json.dumps(compact, sort_keys=True))
    if args.enforce_reproduction and report["claim_status"] != "PASS_OLD_REPRODUCTION":
        raise SystemExit(report["claim_status"])


if __name__ == "__main__":
    main()

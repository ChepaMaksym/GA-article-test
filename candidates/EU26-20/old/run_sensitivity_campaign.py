#!/usr/bin/env python3
"""Run one preregistered ten-seed OLD sensitivity campaign."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any, Iterable, Sequence

from sensitivity_variants import VARIANTS

PAPER_ACCURACY = 0.94
PAPER_SUBSET_LENGTH = 6.0
PAPER_BASELINE = 0.69
SEEDS = list(range(1, 11))
T_CRITICAL_DF9 = 2.2621571628540993
EPS = 1e-12
PREFIX = "EU26_20_SENSITIVITY_CAMPAIGN="

DETERMINISTIC_FIELDS = (
    "best_accuracy",
    "subset_length",
    "features",
    "accuracy",
    "precision",
    "recall",
    "fscore",
    "mcc",
    "nfe",
    "iterations",
    "adaptive_events",
    "final_pc",
    "final_pm",
    "stagnation",
    "first_target_iteration",
    "first_target_nfe",
)


def mean_ci95(values: Sequence[float]) -> dict[str, float]:
    if len(values) != 10:
        raise ValueError("sensitivity CI requires ten completed runs")
    mean = statistics.fmean(values)
    sd = statistics.stdev(values)
    half_width = T_CRITICAL_DF9 * sd / math.sqrt(10)
    return {
        "mean": float(mean),
        "sample_sd": float(sd),
        "ci95_low": float(mean - half_width),
        "ci95_high": float(mean + half_width),
        "median": float(statistics.median(values)),
        "min": float(min(values)),
        "max": float(max(values)),
    }


def same_fields(
    first: dict[str, Any], second: dict[str, Any], fields: Iterable[str]
) -> bool:
    return all(first.get(key) == second.get(key) for key in fields)


def validate(result: dict[str, Any], seed: int, variant: str) -> None:
    expected = {
        "schema": "eu26-20-colon-sensitivity-v1",
        "profile": "old_sensitivity_only",
        "variant": variant,
        "seed": seed,
        "primary_gate_eligible": False,
        "upstream_commit": "d24e61e78ac197ad75342e8f4be5d63d17bd9e7a",
        "dataset_rows": 62,
        "raw_features": 2000,
        "class_labels": [1, 2],
        "class_counts": [22, 40],
        "search_space_size": 128,
        "baseline_accuracy": PAPER_BASELINE,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise ValueError(
                f"{variant} seed {seed}: {key}={result.get(key)!r}, expected {value!r}"
            )
    features = result.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError(f"{variant} seed {seed}: empty final subset")
    if len(features) != len(set(features)) or len(features) != result["subset_length"]:
        raise ValueError(f"{variant} seed {seed}: malformed final subset")
    for key in ("source_sha256", "dataset_sha256", "features_sha256"):
        value = result.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"{variant} seed {seed}: invalid {key}")


def evaluate(
    results: Sequence[dict[str, Any]],
    repeated: dict[str, Any],
    variant: str,
) -> dict[str, Any]:
    if [int(row.get("seed", -1)) for row in results] != SEEDS:
        raise ValueError("sensitivity results must be ordered seeds 1..10")
    for seed, result in zip(SEEDS, results):
        validate(result, seed, variant)
    validate(repeated, 1, variant)

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
        "variant",
        "numpy_rng_mode",
        "offspring_rounding",
        "stop_after",
        "geometry",
        "primary_gate_eligible",
    )
    identity_ok = all(
        same_fields(results[0], row, identity_fields) for row in results[1:]
    )
    deterministic_ok = same_fields(results[0], repeated, DETERMINISTIC_FIELDS)

    accuracies = [float(row["best_accuracy"]) for row in results]
    subsets = [float(row["subset_length"]) for row in results]
    nfes = [float(row["nfe"]) for row in results]
    iterations = [float(row["iterations"]) for row in results]
    adaptive_events = [float(row["adaptive_events"]) for row in results]

    accuracy_stats = mean_ci95(accuracies)
    subset_stats = mean_ci95(subsets)
    nfe_stats = mean_ci95(nfes)
    iteration_stats = mean_ci95(iterations)
    adaptation_stats = mean_ci95(adaptive_events)

    accuracy_distance = abs(accuracy_stats["mean"] - PAPER_ACCURACY)
    accuracy_contains = (
        accuracy_stats["ci95_low"] - EPS
        <= PAPER_ACCURACY
        <= accuracy_stats["ci95_high"] + EPS
    )
    subset_distance = abs(subset_stats["mean"] - PAPER_SUBSET_LENGTH)
    subset_contains = (
        subset_stats["ci95_low"] - EPS
        <= PAPER_SUBSET_LENGTH
        <= subset_stats["ci95_high"] + EPS
    )
    strong = sum(value >= PAPER_BASELINE + 0.20 - EPS for value in accuracies)

    gates = {
        "S0_provenance_structure": {"pass": identity_ok},
        "S1_deterministic_replay": {"pass": deterministic_ok},
        "S2_baseline_endpoint": {
            "pass": all(row["baseline_accuracy"] == PAPER_BASELINE for row in results),
            "target": PAPER_BASELINE,
        },
        "S3_accuracy_alignment": {
            "pass": accuracy_distance <= 0.03 + EPS and accuracy_contains,
            "target": PAPER_ACCURACY,
            "absolute_mean_difference": accuracy_distance,
            "ci_contains_target": accuracy_contains,
            "statistics": accuracy_stats,
        },
        "S4_subset_alignment": {
            "pass": subset_distance <= 1.5 + EPS and subset_contains,
            "target": PAPER_SUBSET_LENGTH,
            "absolute_mean_difference": subset_distance,
            "ci_contains_target": subset_contains,
            "statistics": subset_stats,
        },
        "S5_qualitative_improvement": {
            "pass": strong >= 8 and min(accuracies) >= PAPER_BASELINE - EPS,
            "runs_improving_by_at_least_0_20": strong,
            "minimum_final_accuracy": min(accuracies),
        },
    }
    if not identity_ok or not deterministic_ok:
        status = "BLOCKED_SENSITIVITY_IMPLEMENTATION_OR_PROVENANCE"
    elif all(gate["pass"] for gate in gates.values()):
        status = "ALIGNED_SENSITIVITY_ONLY"
    else:
        status = "SENSITIVITY_MISMATCH"
    return {
        "claim_status": status,
        "gates": gates,
        "statistics": {
            "accuracy": accuracy_stats,
            "subset_length": subset_stats,
            "nfe": nfe_stats,
            "iterations": iteration_stats,
            "adaptive_events": adaptation_stats,
            "runs_at_or_above_paper_accuracy": sum(
                value >= PAPER_ACCURACY - EPS for value in accuracies
            ),
        },
    }


def run_one(
    upstream: Path,
    variant: str,
    seed: int,
    output_dir: Path,
    attempt_limit: int,
    timeout_seconds: int,
    suffix: str = "",
) -> dict[str, Any]:
    stem = f"{variant}-seed-{seed}{suffix}"
    output_json = output_dir / f"{stem}.json"
    runner = Path(__file__).with_name("run_sensitivity_colon.py")
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(runner),
                str(upstream),
                "--variant",
                variant,
                "--seed",
                str(seed),
                "--repository-attempt-limit",
                str(attempt_limit),
                "--output-json",
                str(output_json),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
        )
        (output_dir / f"{stem}.log").write_text(completed.stdout, encoding="utf-8")
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        (output_dir / f"{stem}.log").write_text(partial, encoding="utf-8")
        return {
            "schema": "eu26-20-colon-sensitivity-failure-v1",
            "profile": "old_sensitivity_only",
            "variant": variant,
            "seed": seed,
            "status": "SENSITIVITY_WALL_TIMEOUT",
            "timeout_seconds": timeout_seconds,
        }
    if completed.returncode == 0 and output_json.is_file():
        result = json.loads(output_json.read_text(encoding="utf-8"))
        validate(result, seed, variant)
        return result
    return {
        "schema": "eu26-20-colon-sensitivity-failure-v1",
        "profile": "old_sensitivity_only",
        "variant": variant,
        "seed": seed,
        "status": (
            "SENSITIVITY_REPOSITORY_GENERATION_FAILURE"
            if "RepositoryGenerationError" in completed.stdout
            else "SENSITIVITY_PROCESS_FAILURE"
        ),
        "return_code": completed.returncode,
        "log_tail": completed.stdout.splitlines()[-30:],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--repository-attempt-limit", type=int, default=100_000)
    parser.add_argument("--timeout-per-run", type=int, default=600)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    all_results = [
        run_one(
            args.upstream.resolve(),
            args.variant,
            seed,
            output_dir,
            args.repository_attempt_limit,
            args.timeout_per_run,
        )
        for seed in SEEDS
    ]
    successes = [
        row
        for row in all_results
        if row.get("schema") == "eu26-20-colon-sensitivity-v1"
    ]
    failures = [
        row
        for row in all_results
        if row.get("schema") != "eu26-20-colon-sensitivity-v1"
    ]
    repeated = run_one(
        args.upstream.resolve(),
        args.variant,
        1,
        output_dir,
        args.repository_attempt_limit,
        args.timeout_per_run,
        suffix="-repeat",
    )
    if repeated.get("schema") != "eu26-20-colon-sensitivity-v1":
        failures.append(repeated)

    report: dict[str, Any] = {
        "schema": "eu26-20-colon-sensitivity-campaign-v1",
        "profile": "old_sensitivity_only",
        "variant": args.variant,
        "primary_gate_eligible": False,
        "seed_ledger": SEEDS,
        "runs_requested": 10,
        "successful_runs": len(successes),
        "failed_runs": len(failures),
        "repository_attempt_limit": args.repository_attempt_limit,
        "paper_targets": {
            "baseline_accuracy": PAPER_BASELINE,
            "mean_accuracy": PAPER_ACCURACY,
            "mean_subset_length": PAPER_SUBSET_LENGTH,
            "mean_nfe_diagnostic": 788,
        },
        "results": all_results,
        "repeated_seed_1": repeated,
    }
    if failures:
        statuses = [str(row.get("status", "UNKNOWN_FAILURE")) for row in failures]
        if any(
            value == "SENSITIVITY_REPOSITORY_GENERATION_FAILURE"
            for value in statuses
        ):
            claim_status = "BLOCKED_SENSITIVITY_REPOSITORY_GENERATION"
        elif any(value == "SENSITIVITY_WALL_TIMEOUT" for value in statuses):
            claim_status = "BLOCKED_SENSITIVITY_WALL_TIMEOUT"
        else:
            claim_status = "BLOCKED_SENSITIVITY_RUN_FAILURE"
        report.update(
            {
                "claim_status": claim_status,
                "failure_statuses": statuses,
                "gates": {
                    "S_all_ten_complete": {
                        "pass": False,
                        "successful": len(successes),
                        "required": 10,
                    }
                },
                "partial_statistics": {
                    "accuracy": (
                        {
                            "mean": statistics.fmean(
                                float(row["best_accuracy"]) for row in successes
                            ),
                            "values": [float(row["best_accuracy"]) for row in successes],
                        }
                        if successes
                        else None
                    ),
                    "subset_length": (
                        {
                            "mean": statistics.fmean(
                                float(row["subset_length"]) for row in successes
                            ),
                            "values": [int(row["subset_length"]) for row in successes],
                        }
                        if successes
                        else None
                    ),
                    "nfe": (
                        {
                            "mean": statistics.fmean(float(row["nfe"]) for row in successes),
                            "values": [int(row["nfe"]) for row in successes],
                        }
                        if successes
                        else None
                    ),
                },
            }
        )
    else:
        report.update(evaluate(successes, repeated, args.variant))

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    compact = {
        "claim_status": report["claim_status"],
        "variant": args.variant,
        "successful_runs": report["successful_runs"],
        "failed_runs": report["failed_runs"],
        "failure_statuses": report.get("failure_statuses"),
        "gates": {key: value["pass"] for key, value in report.get("gates", {}).items()},
        "statistics": report.get("statistics"),
        "partial_statistics": report.get("partial_statistics"),
    }
    print(PREFIX + json.dumps(compact, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Bounded ten-seed campaign for the pinned author-source Colon OLD profile.

Unlike the original campaign driver, this version does not abort at the first
failed seed. It records all successful and failed runs, writes a report in all
cases, and distinguishes numeric mismatch from source non-termination.
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
T_CRITICAL_DF9 = 2.2621571628540993
NUMERIC_EPS = 1e-12
CAMPAIGN_PREFIX = "EU26_20_SOURCE_CAMPAIGN="

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


def mean_ci95(values: Sequence[float]) -> dict[str, float]:
    if len(values) != 10:
        raise ValueError("literal campaign CI requires ten successful values")
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


def same_fields(first: dict[str, Any], second: dict[str, Any], fields: Iterable[str]) -> bool:
    return all(first.get(field) == second.get(field) for field in fields)


def validate_success(result: dict[str, Any], seed: int) -> None:
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
        raise ValueError(f"seed {seed}: empty feature subset")
    if len(features) != len(set(features)) or len(features) != result.get("subset_length"):
        raise ValueError(f"seed {seed}: malformed feature subset")
    for key in ("source_sha256", "dataset_sha256", "features_sha256"):
        value = result.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"seed {seed}: invalid {key}")


def evaluate_successes(
    results: Sequence[dict[str, Any]], repeated_seed_1: dict[str, Any]
) -> dict[str, Any]:
    if [int(row["seed"]) for row in results] != EXPECTED_SEEDS:
        raise ValueError("results must be ordered seeds 1..10")
    for seed, row in zip(EXPECTED_SEEDS, results):
        validate_success(row, seed)
    validate_success(repeated_seed_1, 1)

    identities = (
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
    identity_ok = all(same_fields(results[0], row, identities) for row in results[1:])
    deterministic_ok = same_fields(results[0], repeated_seed_1, DETERMINISTIC_FIELDS)

    accuracies = [float(row["best_accuracy"]) for row in results]
    subsets = [float(row["subset_length"]) for row in results]
    nfes = [float(row["nfe"]) for row in results]
    iterations = [float(row["iterations"]) for row in results]
    adaptations = [float(row["adaptive_events"]) for row in results]
    accuracy_stats = mean_ci95(accuracies)
    subset_stats = mean_ci95(subsets)
    nfe_stats = mean_ci95(nfes)
    iteration_stats = mean_ci95(iterations)
    adaptation_stats = mean_ci95(adaptations)

    accuracy_distance = abs(accuracy_stats["mean"] - PAPER_ACCURACY)
    accuracy_contains = (
        accuracy_stats["ci95_low"] - NUMERIC_EPS
        <= PAPER_ACCURACY
        <= accuracy_stats["ci95_high"] + NUMERIC_EPS
    )
    subset_distance = abs(subset_stats["mean"] - PAPER_SUBSET_LENGTH)
    subset_contains = (
        subset_stats["ci95_low"] - NUMERIC_EPS
        <= PAPER_SUBSET_LENGTH
        <= subset_stats["ci95_high"] + NUMERIC_EPS
    )
    strong = sum(value >= PAPER_BASELINE + 0.20 - NUMERIC_EPS for value in accuracies)

    gates = {
        "G0_provenance_structure": {"pass": identity_ok},
        "G1_deterministic_replay": {"pass": deterministic_ok},
        "G2_baseline_endpoint": {
            "pass": all(float(row["baseline_accuracy"]) == PAPER_BASELINE for row in results),
            "target": PAPER_BASELINE,
        },
        "G3_final_accuracy_alignment": {
            "pass": accuracy_distance <= 0.03 + NUMERIC_EPS and accuracy_contains,
            "target": PAPER_ACCURACY,
            "absolute_mean_difference": accuracy_distance,
            "ci_contains_target": accuracy_contains,
            "statistics": accuracy_stats,
        },
        "G4_subset_length_alignment": {
            "pass": subset_distance <= 1.5 + NUMERIC_EPS and subset_contains,
            "target": PAPER_SUBSET_LENGTH,
            "absolute_mean_difference": subset_distance,
            "ci_contains_target": subset_contains,
            "statistics": subset_stats,
        },
        "G5_qualitative_improvement": {
            "pass": strong >= 8 and min(accuracies) >= PAPER_BASELINE - NUMERIC_EPS,
            "runs_improving_by_at_least_0_20": strong,
            "minimum_final_accuracy": min(accuracies),
        },
    }
    if not identity_ok or not deterministic_ok:
        status = "BLOCKED_SOURCE_IMPLEMENTATION_OR_PROVENANCE"
    elif all(gate["pass"] for gate in gates.values()):
        status = "PASS_SOURCE_NUMERIC_ALIGNMENT"
    else:
        status = "BLOCKED_SOURCE_NUMERIC_MISMATCH"
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
                value >= PAPER_ACCURACY - NUMERIC_EPS for value in accuracies
            ),
        },
    }


def run_one(
    upstream: Path,
    seed: int,
    output_dir: Path,
    attempt_limit: int,
    timeout_seconds: int,
    suffix: str = "",
) -> dict[str, Any]:
    stem = f"source-seed-{seed}{suffix}"
    output_json = output_dir / f"{stem}.json"
    log_file = output_dir / f"{stem}.log"
    driver_log = output_dir / f"{stem}.driver.log"
    runner = Path(__file__).with_name("run_author_colon_guarded.py")
    command = [
        sys.executable,
        str(runner),
        str(upstream),
        "--seed",
        str(seed),
        "--attempt-limit",
        str(attempt_limit),
        "--quiet",
        "--output-json",
        str(output_json),
        "--log-file",
        str(log_file),
    ]
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
        )
        driver_log.write_text(completed.stdout, encoding="utf-8")
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        driver_log.write_text(partial, encoding="utf-8")
        return {
            "schema": "eu26-20-colon-source-failure-v1",
            "profile": "author_source_compatibility_guarded",
            "seed": seed,
            "status": "SOURCE_WALL_TIMEOUT",
            "timeout_seconds": timeout_seconds,
            "repository_attempt_limit": attempt_limit,
        }

    if output_json.is_file():
        payload = json.loads(output_json.read_text(encoding="utf-8"))
    else:
        payload = {
            "schema": "eu26-20-colon-source-failure-v1",
            "profile": "author_source_compatibility_guarded",
            "seed": seed,
            "status": "SOURCE_NO_RESULT",
            "return_code": completed.returncode,
        }
    if completed.returncode == 0:
        validate_success(payload, seed)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--attempt-limit", type=int, default=100_000)
    parser.add_argument("--timeout-per-run", type=int, default=480)
    parser.add_argument("--enforce-reproduction", action="store_true")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    all_results = [
        run_one(
            args.upstream.resolve(),
            seed,
            output_dir,
            args.attempt_limit,
            args.timeout_per_run,
        )
        for seed in EXPECTED_SEEDS
    ]
    successes = [row for row in all_results if row.get("schema") == "eu26-20-colon-old-v1"]
    failures = [row for row in all_results if row.get("schema") != "eu26-20-colon-old-v1"]

    repeated = run_one(
        args.upstream.resolve(),
        1,
        output_dir,
        args.attempt_limit,
        args.timeout_per_run,
        suffix="-repeat",
    )
    if repeated.get("schema") != "eu26-20-colon-old-v1":
        failures.append(repeated)

    report: dict[str, Any] = {
        "schema": "eu26-20-colon-source-campaign-v2",
        "profile": "author_source_compatibility_guarded",
        "seed_ledger": EXPECTED_SEEDS,
        "runs_requested": 10,
        "successful_runs": len(successes),
        "failed_runs": len(failures),
        "repository_attempt_limit": args.attempt_limit,
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
        if any(status == "SOURCE_REPOSITORY_NONTERMINATION" for status in statuses):
            status = "BLOCKED_SOURCE_REPOSITORY_NONTERMINATION"
        elif any(status == "SOURCE_WALL_TIMEOUT" for status in statuses):
            status = "BLOCKED_SOURCE_WALL_TIMEOUT"
        else:
            status = "BLOCKED_SOURCE_RUN_FAILURE"
        report.update(
            {
                "claim_status": status,
                "failure_statuses": statuses,
                "gates": {
                    "G_source_all_ten_complete": {
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
        evaluated = evaluate_successes(successes, repeated)
        report.update(evaluated)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    compact = {
        "claim_status": report["claim_status"],
        "successful_runs": report["successful_runs"],
        "failed_runs": report["failed_runs"],
        "gates": {key: value["pass"] for key, value in report.get("gates", {}).items()},
        "statistics": report.get("statistics"),
        "partial_statistics": report.get("partial_statistics"),
        "failure_statuses": report.get("failure_statuses"),
    }
    print(CAMPAIGN_PREFIX + json.dumps(compact, sort_keys=True))
    if args.enforce_reproduction and report["claim_status"] != "PASS_SOURCE_NUMERIC_ALIGNMENT":
        raise SystemExit(report["claim_status"])


if __name__ == "__main__":
    main()

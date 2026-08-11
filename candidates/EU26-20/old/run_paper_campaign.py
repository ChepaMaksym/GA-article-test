#!/usr/bin/env python3
"""Run the independent ten-seed Colon OLD paper-profile campaign.

All seeds are attempted and the report is written even if a run fails. This
keeps paper-profile non-termination or implementation failures separate from a
literal numeric mismatch.
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
PREFIX = "EU26_20_PAPER_CAMPAIGN="

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


def _same_fields(
    first: dict[str, Any], second: dict[str, Any], fields: Iterable[str]
) -> bool:
    return all(first.get(key) == second.get(key) for key in fields)


def validate_result(result: dict[str, Any], seed: int) -> None:
    expected = {
        "schema": "eu26-20-colon-paper-old-v1",
        "profile": "paper_cleanroom_feature_geometry",
        "seed": seed,
        "upstream_commit": "d24e61e78ac197ad75342e8f4be5d63d17bd9e7a",
        "offspring_rounding": "paper_ceil",
        "geometry": "feature_vectors_euclidean",
        "dataset_rows": 62,
        "raw_features": 2000,
        "class_labels": [1, 2],
        "class_counts": [22, 40],
        "search_space_size": 128,
        "baseline_accuracy": PAPER_BASELINE,
    }
    for key, expected_value in expected.items():
        if result.get(key) != expected_value:
            raise ValueError(
                f"seed {seed}: {key}={result.get(key)!r}, expected {expected_value!r}"
            )
    features = result.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError(f"seed {seed}: missing final features")
    if len(features) != len(set(features)) or len(features) != result["subset_length"]:
        raise ValueError(f"seed {seed}: invalid final features")
    if not 0.0 <= float(result["best_accuracy"]) <= 1.0:
        raise ValueError(f"seed {seed}: invalid best accuracy")
    if int(result["nfe"]) <= 0 or int(result["iterations"]) < 0:
        raise ValueError(f"seed {seed}: invalid effort accounting")
    for key in ("source_sha256", "dataset_sha256", "features_sha256"):
        value = result.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"seed {seed}: invalid {key}")


def evaluate(
    results: Sequence[dict[str, Any]], repeated: dict[str, Any]
) -> dict[str, Any]:
    if [int(row.get("seed", -1)) for row in results] != EXPECTED_SEEDS:
        raise ValueError("paper results must be ordered for seeds 1..10")
    for seed, result in zip(EXPECTED_SEEDS, results):
        validate_result(result, seed)
    validate_result(repeated, 1)

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
        "geometry",
        "kmeans_n_init",
    )
    identity_ok = all(
        _same_fields(results[0], row, identity_fields) for row in results[1:]
    )
    deterministic_ok = _same_fields(
        results[0], repeated, DETERMINISTIC_FIELDS + ("stagnation",)
    )

    accuracies = [float(row["best_accuracy"]) for row in results]
    subsets = [float(row["subset_length"]) for row in results]
    nfes = [float(row["nfe"]) for row in results]
    iterations = [float(row["iterations"]) for row in results]
    adaptations = [float(row["adaptive_events"]) for row in results]

    accuracy_stats = _mean_ci95(accuracies)
    subset_stats = _mean_ci95(subsets)
    nfe_stats = _mean_ci95(nfes)
    iteration_stats = _mean_ci95(iterations)
    adaptation_stats = _mean_ci95(adaptations)

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
    strong_improvements = sum(
        value >= PAPER_BASELINE + 0.20 - NUMERIC_EPS for value in accuracies
    )

    gates = {
        "P0_provenance_structure": {"pass": identity_ok},
        "P1_deterministic_replay": {"pass": deterministic_ok},
        "P2_baseline_endpoint": {
            "pass": all(row["baseline_accuracy"] == PAPER_BASELINE for row in results),
            "target": PAPER_BASELINE,
        },
        "P3_final_accuracy_alignment": {
            "pass": accuracy_distance <= 0.03 + NUMERIC_EPS and accuracy_contains,
            "target": PAPER_ACCURACY,
            "absolute_mean_difference": accuracy_distance,
            "ci_contains_target": accuracy_contains,
            "statistics": accuracy_stats,
        },
        "P4_subset_length_alignment": {
            "pass": subset_distance <= 1.5 + NUMERIC_EPS and subset_contains,
            "target": PAPER_SUBSET_LENGTH,
            "absolute_mean_difference": subset_distance,
            "ci_contains_target": subset_contains,
            "statistics": subset_stats,
        },
        "P5_qualitative_improvement": {
            "pass": strong_improvements >= 8
            and min(accuracies) >= PAPER_BASELINE - NUMERIC_EPS,
            "runs_improving_by_at_least_0_20": strong_improvements,
            "minimum_final_accuracy": min(accuracies),
        },
    }

    if not gates["P0_provenance_structure"]["pass"] or not gates[
        "P1_deterministic_replay"
    ]["pass"]:
        status = "BLOCKED_PAPER_IMPLEMENTATION_OR_PROVENANCE"
    elif all(gate["pass"] for gate in gates.values()):
        status = "PASS_PAPER_PROFILE_NUMERIC"
    else:
        status = "BLOCKED_PAPER_NUMERIC_MISMATCH"

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
    timeout_seconds: int,
    suffix: str = "",
) -> dict[str, Any]:
    stem = f"paper-seed-{seed}{suffix}"
    output_json = output_dir / f"{stem}.json"
    runner = Path(__file__).with_name("run_paper_colon.py")
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(runner),
                str(upstream),
                "--seed",
                str(seed),
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
            "schema": "eu26-20-colon-paper-failure-v1",
            "profile": "paper_cleanroom_feature_geometry",
            "seed": seed,
            "status": "PAPER_WALL_TIMEOUT",
            "timeout_seconds": timeout_seconds,
        }
    if completed.returncode == 0 and output_json.is_file():
        result = json.loads(output_json.read_text(encoding="utf-8"))
        validate_result(result, seed)
        return result
    return {
        "schema": "eu26-20-colon-paper-failure-v1",
        "profile": "paper_cleanroom_feature_geometry",
        "seed": seed,
        "status": (
            "PAPER_REPOSITORY_GENERATION_FAILURE"
            if "RepositoryGenerationError" in completed.stdout
            else "PAPER_PROCESS_FAILURE"
        ),
        "return_code": completed.returncode,
        "log_tail": completed.stdout.splitlines()[-30:],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--timeout-per-run", type=int, default=600)
    parser.add_argument("--enforce-reproduction", action="store_true")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    all_results = [
        run_one(args.upstream.resolve(), seed, output_dir, args.timeout_per_run)
        for seed in EXPECTED_SEEDS
    ]
    successes = [
        row for row in all_results if row.get("schema") == "eu26-20-colon-paper-old-v1"
    ]
    failures = [
        row for row in all_results if row.get("schema") != "eu26-20-colon-paper-old-v1"
    ]
    repeated = run_one(
        args.upstream.resolve(), 1, output_dir, args.timeout_per_run, suffix="-repeat"
    )
    if repeated.get("schema") != "eu26-20-colon-paper-old-v1":
        failures.append(repeated)

    report: dict[str, Any] = {
        "schema": "eu26-20-colon-paper-campaign-v1",
        "profile": "paper_cleanroom_feature_geometry",
        "seed_ledger": EXPECTED_SEEDS,
        "runs_requested": 10,
        "successful_runs": len(successes),
        "failed_runs": len(failures),
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
        if any(value == "PAPER_REPOSITORY_GENERATION_FAILURE" for value in statuses):
            claim_status = "BLOCKED_PAPER_REPOSITORY_GENERATION"
        elif any(value == "PAPER_WALL_TIMEOUT" for value in statuses):
            claim_status = "BLOCKED_PAPER_WALL_TIMEOUT"
        else:
            claim_status = "BLOCKED_PAPER_RUN_FAILURE"
        report.update(
            {
                "claim_status": claim_status,
                "failure_statuses": statuses,
                "gates": {
                    "P_all_ten_complete": {
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
        report.update(evaluate(successes, repeated))

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
    print(PREFIX + json.dumps(compact, sort_keys=True))
    if args.enforce_reproduction and report["claim_status"] != "PASS_PAPER_PROFILE_NUMERIC":
        raise SystemExit(report["claim_status"])


if __name__ == "__main__":
    main()

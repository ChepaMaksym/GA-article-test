#!/usr/bin/env python3
"""Execute and evaluate the preregistered EU26-21 source campaign."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Any, Iterable, Sequence

SEEDS = list(range(1, 11))
PAPER_BASELINE_PERCENT = 92.87
PAPER_MEDIAN_PERCENT = 94.94
PAPER_SD_PERCENT = 0.07
PREFIX = "EU26_21_SOURCE_CAMPAIGN="

DETERMINISTIC_FIELDS = (
    "target_labels",
    "target_counts",
    "split_sizes",
    "baseline_validation_accuracy",
    "baseline_test_accuracy",
    "meta_model_sample_size",
    "controlled_individuals",
    "evolution_control_frequency",
    "outer_no_change_limit",
    "population_size",
    "chc_chunk_count",
    "chc_chunk_final_d",
    "chc_chunk_improvement_rows",
    "improvement_rows",
    "validation_fitness",
    "test_accuracy",
    "selected_feature_count",
    "selected_features",
    "feature_mask",
)


def same_fields(first: dict[str, Any], second: dict[str, Any], fields: Iterable[str]) -> bool:
    return all(first.get(field) == second.get(field) for field in fields)


def validate_result(result: dict[str, Any], seed: int) -> None:
    expected = {
        "schema": "eu26-21-census-source-v1",
        "profile": "author_source_seeded",
        "seed": seed,
        "upstream_commit": "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6",
        "dataset_rows": 199_523,
        "raw_features": 41,
        "split_sizes": [119_713, 39_905, 39_905],
        "controlled_individuals": 10,
        "evolution_control_frequency": 10,
        "outer_no_change_limit": 2,
        "population_size": 50,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise ValueError(
                f"seed {seed}: {key}={result.get(key)!r}, expected {value!r}"
            )
    if len(result.get("target_labels", [])) != 2:
        raise ValueError(f"seed {seed}: invalid target labels")
    if sum(result.get("target_counts", [])) != 199_523:
        raise ValueError(f"seed {seed}: invalid target counts")
    selected = result.get("selected_features")
    if not isinstance(selected, list) or not selected:
        raise ValueError(f"seed {seed}: empty selected subset")
    if selected != sorted(set(selected)) or min(selected) < 0 or max(selected) > 40:
        raise ValueError(f"seed {seed}: invalid selected feature indices")
    if result.get("selected_feature_count") != len(selected):
        raise ValueError(f"seed {seed}: selected count mismatch")
    if not 5_000 <= int(result.get("meta_model_sample_size", 0)) <= 119_713:
        raise ValueError(f"seed {seed}: invalid meta-model sample size")
    for key in (
        "baseline_validation_accuracy",
        "baseline_test_accuracy",
        "validation_fitness",
        "test_accuracy",
    ):
        value = float(result.get(key, -1.0))
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"seed {seed}: invalid {key}={value}")
    if int(result.get("chc_chunk_count", 0)) <= 0:
        raise ValueError(f"seed {seed}: no CHC chunks")
    if int(result.get("improvement_rows", 0)) <= 0:
        raise ValueError(f"seed {seed}: empty improvement log")
    for key in (
        "source_sha256",
        "dataset_source_sha256",
        "notebook_sha256",
        "data_sha256",
    ):
        value = result.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"seed {seed}: invalid {key}")


def evaluate(
    results: Sequence[dict[str, Any]],
    repeated_seed_1: dict[str, Any],
) -> dict[str, Any]:
    if [int(result.get("seed", -1)) for result in results] != SEEDS:
        raise ValueError("results must be ordered for seeds 1..10")
    for seed, result in zip(SEEDS, results):
        validate_result(result, seed)
    validate_result(repeated_seed_1, 1)

    identity_fields = (
        "upstream_commit",
        "source_sha256",
        "dataset_source_sha256",
        "notebook_sha256",
        "data_sha256",
        "dataset_rows",
        "raw_features",
        "target_labels",
        "target_counts",
        "split_sizes",
        "profile",
        "controlled_individuals",
        "evolution_control_frequency",
        "outer_no_change_limit",
        "population_size",
    )
    identity_ok = all(
        same_fields(results[0], result, identity_fields) for result in results[1:]
    )
    deterministic_ok = same_fields(
        results[0], repeated_seed_1, DETERMINISTIC_FIELDS
    )

    baseline_percent = [
        100.0 * float(result["baseline_test_accuracy"]) for result in results
    ]
    test_percent = [100.0 * float(result["test_accuracy"]) for result in results]
    validation_percent = [
        100.0 * float(result["validation_fitness"]) for result in results
    ]
    feature_counts = [int(result["selected_feature_count"]) for result in results]
    sample_sizes = [int(result["meta_model_sample_size"]) for result in results]
    chunks = [int(result["chc_chunk_count"]) for result in results]
    elapsed = [float(result["elapsed_seconds"]) for result in results]

    observed_baseline = statistics.fmean(baseline_percent)
    observed_median = statistics.median(test_percent)
    observed_sd = statistics.stdev(test_percent)
    baseline_distance = abs(observed_baseline - PAPER_BASELINE_PERCENT)
    median_distance = abs(observed_median - PAPER_MEDIAN_PERCENT)
    sd_distance = abs(observed_sd - PAPER_SD_PERCENT)
    high_accuracy_runs = sum(value >= 94.75 - 1e-12 for value in test_percent)
    strong_improvement_runs = sum(
        value >= baseline + 1.50 - 1e-12
        for value, baseline in zip(test_percent, baseline_percent)
    )
    no_regressions = all(
        value >= baseline - 1e-12
        for value, baseline in zip(test_percent, baseline_percent)
    )

    gates: dict[str, dict[str, Any]] = {
        "S0_provenance_structure": {
            "pass": bool(identity_ok),
            "detail": "all commit/blob/data/split identities agree",
        },
        "S1_deterministic_source_replay": {
            "pass": bool(deterministic_ok),
            "detail": "seed 1 repeated exactly excluding elapsed time",
        },
        "S2_baseline_endpoint": {
            "pass": baseline_distance <= 0.02 + 1e-12,
            "target_percent": PAPER_BASELINE_PERCENT,
            "observed_percent": observed_baseline,
            "absolute_difference": baseline_distance,
            "tolerance": 0.02,
        },
        "S3_chcqx_median_alignment": {
            "pass": median_distance <= 0.15 + 1e-12 and high_accuracy_runs >= 8,
            "target_median_percent": PAPER_MEDIAN_PERCENT,
            "observed_median_percent": observed_median,
            "absolute_difference": median_distance,
            "tolerance": 0.15,
            "runs_at_or_above_94_75": high_accuracy_runs,
            "required_runs": 8,
        },
        "S4_run_dispersion": {
            "pass": observed_sd <= 0.20 + 1e-12 and sd_distance <= 0.15 + 1e-12,
            "target_sample_sd_percent": PAPER_SD_PERCENT,
            "observed_sample_sd_percent": observed_sd,
            "absolute_difference": sd_distance,
            "maximum_sd": 0.20,
            "difference_tolerance": 0.15,
        },
        "S5_qualitative_improvement": {
            "pass": bool(no_regressions and strong_improvement_runs >= 8),
            "no_run_below_baseline": bool(no_regressions),
            "runs_improving_by_at_least_1_50_points": strong_improvement_runs,
            "required_runs": 8,
        },
        "S6_source_completion_invariants": {
            "pass": True,
            "completed_runs": 10,
            "required_runs": 10,
        },
    }

    if not gates["S0_provenance_structure"]["pass"] or not gates[
        "S1_deterministic_source_replay"
    ]["pass"]:
        claim_status = "BLOCKED_SOURCE_IMPLEMENTATION_OR_PROVENANCE"
    elif all(gate["pass"] for gate in gates.values()):
        claim_status = "PASS_SOURCE_NUMERIC_ALIGNMENT"
    else:
        claim_status = "BLOCKED_SOURCE_NUMERIC_MISMATCH"

    return {
        "schema": "eu26-21-census-source-campaign-v1",
        "claim_status": claim_status,
        "profile": "author_source_seeded",
        "seed_ledger": SEEDS,
        "runs": 10,
        "paper_targets": {
            "baseline_percent": PAPER_BASELINE_PERCENT,
            "chcqx_median_percent": PAPER_MEDIAN_PERCENT,
            "chcqx_sample_sd_percent": PAPER_SD_PERCENT,
            "notebook_test_percent": 94.96,
            "notebook_meta_model_sample_size": 14_964,
            "notebook_features": [12, 16, 17, 19, 40],
        },
        "gates": gates,
        "statistics": {
            "baseline_test_percent": {
                "mean": observed_baseline,
                "min": min(baseline_percent),
                "max": max(baseline_percent),
            },
            "chcqx_test_percent": {
                "mean": statistics.fmean(test_percent),
                "median": observed_median,
                "sample_sd": observed_sd,
                "min": min(test_percent),
                "max": max(test_percent),
                "values": test_percent,
            },
            "validation_percent": {
                "mean": statistics.fmean(validation_percent),
                "median": statistics.median(validation_percent),
                "values": validation_percent,
            },
            "selected_feature_count": {
                "mean": statistics.fmean(feature_counts),
                "median": statistics.median(feature_counts),
                "min": min(feature_counts),
                "max": max(feature_counts),
                "values": feature_counts,
            },
            "meta_model_sample_size": {
                "mean": statistics.fmean(sample_sizes),
                "median": statistics.median(sample_sizes),
                "min": min(sample_sizes),
                "max": max(sample_sizes),
                "values": sample_sizes,
            },
            "chc_chunk_count": {
                "mean": statistics.fmean(chunks),
                "median": statistics.median(chunks),
                "values": chunks,
            },
            "elapsed_seconds": {
                "mean": statistics.fmean(elapsed),
                "median": statistics.median(elapsed),
                "min": min(elapsed),
                "max": max(elapsed),
            },
        },
        "deterministic_fields": list(DETERMINISTIC_FIELDS),
        "results": list(results),
        "repeated_seed_1": repeated_seed_1,
    }


def run_one(
    upstream: Path,
    seed: int,
    output_dir: Path,
    timeout_seconds: int,
    suffix: str = "",
) -> dict[str, Any]:
    stem = f"seed-{seed}{suffix}"
    result_path = output_dir / f"{stem}.json"
    log_path = output_dir / f"{stem}.source.log"
    driver_path = output_dir / f"{stem}.driver.log"
    runner = Path(__file__).with_name("run_source_census.py")
    command = [
        sys.executable,
        str(runner),
        str(upstream),
        "--seed",
        str(seed),
        "--output-json",
        str(result_path),
        "--log-file",
        str(log_path),
    ]
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_seconds,
        check=False,
    )
    driver_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"seed {seed}{suffix} failed with exit {completed.returncode}; "
            f"see {driver_path} and {log_path}"
        )
    if not result_path.is_file():
        raise RuntimeError(f"seed {seed}{suffix} produced no JSON result")
    return json.loads(result_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--timeout-per-run", type=int, default=900)
    parser.add_argument("--enforce-reproduction", action="store_true")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        results = [
            run_one(
                args.upstream.resolve(),
                seed,
                output_dir,
                args.timeout_per_run,
            )
            for seed in SEEDS
        ]
        repeated = run_one(
            args.upstream.resolve(),
            1,
            output_dir,
            args.timeout_per_run,
            suffix="-repeat",
        )
        report = evaluate(results, repeated)
    except subprocess.TimeoutExpired as exc:
        report = {
            "schema": "eu26-21-census-source-campaign-v1",
            "claim_status": "BLOCKED_SOURCE_TIMEOUT",
            "seed_ledger": SEEDS,
            "timeout_seconds": args.timeout_per_run,
            "error": str(exc),
        }
    except Exception as exc:
        report = {
            "schema": "eu26-21-census-source-campaign-v1",
            "claim_status": "BLOCKED_SOURCE_RUN_FAILURE",
            "seed_ledger": SEEDS,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    compact = {
        "claim_status": report["claim_status"],
        "gates": {
            key: value["pass"] for key, value in report.get("gates", {}).items()
        },
        "statistics": report.get("statistics"),
        "error": report.get("error"),
    }
    print(PREFIX + json.dumps(compact, sort_keys=True))
    if args.enforce_reproduction and report["claim_status"] != "PASS_SOURCE_NUMERIC_ALIGNMENT":
        raise SystemExit(report["claim_status"])


if __name__ == "__main__":
    main()

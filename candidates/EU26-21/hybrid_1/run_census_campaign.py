#!/usr/bin/env python3
"""Paired applied Census campaign for Hybrid 1 and its no-reset ablation.

The campaign keeps the already verified OLD seed ledger in the report, uses
identical initial masks for reset/no-reset variants, and reports both the
applied Hybrid-vs-OLD question and the narrower causal reset-vs-no-reset
question. A reset effect is never claimed when the reset branch was dormant.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
from typing import Dict, List, Sequence, Tuple

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hybrid_1.census import (
        FROZEN_ACTIVE_SAMPLE_SIZES,
        FeatureSelectionObjective,
        final_test_accuracy,
        prepare_author_census,
    )
    from hybrid_1.core import run_reset_lambda_ga, source_density_population
else:
    from .census import (
        FROZEN_ACTIVE_SAMPLE_SIZES,
        FeatureSelectionObjective,
        final_test_accuracy,
        prepare_author_census,
    )
    from .core import run_reset_lambda_ga, source_density_population

OLD_TEST_ACCURACY = {
    1: 0.948528,
    2: 0.949204,
    3: 0.949555,
    4: 0.949580,
    5: 0.949130,
    6: 0.949405,
    7: 0.949480,
    8: 0.949655,
    9: 0.949500,
    10: 0.949650,
}
OLD_FEATURE_COUNT = {
    1: 3,
    2: 6,
    3: 9,
    4: 13,
    5: 7,
    6: 9,
    7: 5,
    8: 13,
    9: 7,
    10: 14,
}
OLD_MEDIAN_TEST_ACCURACY = 0.949455
OLD_MEDIAN_FEATURE_COUNT = 8.0
ALL_FEATURE_BASELINE = 0.9286806164641022


def _bootstrap_median_ci(
    values: Sequence[float],
    *,
    seed: int,
    resamples: int,
) -> Tuple[float, float]:
    data = np.asarray(list(values), dtype=float)
    if data.ndim != 1 or data.size == 0:
        raise ValueError("bootstrap values must be a non-empty vector")
    if resamples < 1000:
        raise ValueError("bootstrap resamples must be at least 1000")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, data.size, size=(resamples, data.size))
    medians = np.median(data[indices], axis=1)
    low, high = np.quantile(medians, [0.025, 0.975])
    return float(low), float(high)


def _variant(
    prepared,
    *,
    seed: int,
    budget: int,
    workers: int,
    initial_masks,
    reset: bool,
) -> Dict[str, object]:
    objective = FeatureSelectionObjective(
        prepared.x_train[prepared.active_instances],
        prepared.y_train[prepared.active_instances],
        prepared.x_validation,
        prepared.y_validation,
    )
    result = run_reset_lambda_ga(
        objective,
        dimension=41,
        seed=seed + 1_000_003,
        max_evaluations=budget,
        workers=workers,
        reset=reset,
        initial_masks=initial_masks,
    )
    selected = [
        index for index, value in enumerate(result.best_mask) if value == 1
    ]
    first_reset_evaluations = next(
        (row.evaluations for row in result.trace if row.reset_event),
        None,
    )
    return {
        "validation_accuracy": result.best_fitness[0],
        "test_accuracy": final_test_accuracy(prepared, result.best_mask),
        "selected_feature_count": len(selected),
        "selected_features": selected,
        "evaluations": result.evaluations,
        "generations": result.generations,
        "reset_events": result.reset_events,
        "first_reset_evaluations": first_reset_evaluations,
        "max_lambda_before": max(
            (row.lambda_before for row in result.trace),
            default=1.0,
        ),
        "strict_successes": sum(row.strict_success for row in result.trace),
        "accepted_generations": sum(row.accepted for row in result.trace),
    }


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--budget", type=int, default=800)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--initial-population", type=int, default=50)
    parser.add_argument("--bootstrap-resamples", type=int, default=20_000)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--enforce-h1-h2", action="store_true")
    args = parser.parse_args()

    rows: List[Dict[str, object]] = []
    for seed in range(args.seed_start, args.seed_start + args.runs):
        prepared = prepare_author_census(args.upstream, seed)
        search_seed = seed + 1_000_003
        initial_masks = source_density_population(
            args.initial_population,
            41,
            np.random.default_rng(search_seed + 99),
        )
        reset_row = _variant(
            prepared,
            seed=seed,
            budget=args.budget,
            workers=args.workers,
            initial_masks=initial_masks,
            reset=True,
        )
        no_reset_row = _variant(
            prepared,
            seed=seed,
            budget=args.budget,
            workers=args.workers,
            initial_masks=initial_masks,
            reset=False,
        )
        old_accuracy = OLD_TEST_ACCURACY.get(seed)
        old_features = OLD_FEATURE_COUNT.get(seed)
        rows.append({
            "seed": seed,
            "old_test_accuracy": old_accuracy,
            "old_selected_feature_count": old_features,
            "active_sample_size": int(prepared.active_instances.size),
            "active_indices_sha256": prepared.metadata[
                "active_indices_sha256"
            ],
            "active_sampling": prepared.metadata["active_sampling"],
            "reset": reset_row,
            "no_reset": no_reset_row,
            "paired_differences": {
                "reset_minus_no_reset_test_accuracy": (
                    float(reset_row["test_accuracy"])
                    - float(no_reset_row["test_accuracy"])
                ),
                "reset_minus_no_reset_features": (
                    int(reset_row["selected_feature_count"])
                    - int(no_reset_row["selected_feature_count"])
                ),
                "reset_minus_old_test_accuracy": (
                    None
                    if old_accuracy is None
                    else float(reset_row["test_accuracy"])
                    - float(old_accuracy)
                ),
                "reset_minus_old_features": (
                    None
                    if old_features is None
                    else int(reset_row["selected_feature_count"])
                    - int(old_features)
                ),
            },
        })

    reset_accuracy = [
        float(row["reset"]["test_accuracy"]) for row in rows  # type: ignore[index]
    ]
    no_reset_accuracy = [
        float(row["no_reset"]["test_accuracy"]) for row in rows  # type: ignore[index]
    ]
    reset_features = [
        int(row["reset"]["selected_feature_count"]) for row in rows  # type: ignore[index]
    ]
    no_reset_features = [
        int(row["no_reset"]["selected_feature_count"]) for row in rows  # type: ignore[index]
    ]
    reset_minus_no_reset_accuracy = [
        first - second
        for first, second in zip(reset_accuracy, no_reset_accuracy)
    ]
    reset_minus_no_reset_features = [
        first - second
        for first, second in zip(reset_features, no_reset_features)
    ]
    old_pairs = [
        (
            float(row["reset"]["test_accuracy"]),  # type: ignore[index]
            float(row["old_test_accuracy"]),
            int(row["reset"]["selected_feature_count"]),  # type: ignore[index]
            int(row["old_selected_feature_count"]),
        )
        for row in rows
        if row["old_test_accuracy"] is not None
        and row["old_selected_feature_count"] is not None
    ]
    reset_minus_old_accuracy = [first - old for first, old, _, _ in old_pairs]
    reset_minus_old_features = [first - old for _, _, first, old in old_pairs]

    reset_events = [
        int(row["reset"]["reset_events"]) for row in rows  # type: ignore[index]
    ]
    first_reset_values = [
        int(row["reset"]["first_reset_evaluations"])  # type: ignore[index]
        for row in rows
        if row["reset"]["first_reset_evaluations"] is not None  # type: ignore[index]
    ]
    reset_accuracy_ci = _bootstrap_median_ci(
        reset_accuracy,
        seed=2026081201,
        resamples=args.bootstrap_resamples,
    )
    reset_features_ci = _bootstrap_median_ci(
        [float(value) for value in reset_features],
        seed=2026081202,
        resamples=args.bootstrap_resamples,
    )
    reset_no_reset_ci = _bootstrap_median_ci(
        reset_minus_no_reset_accuracy,
        seed=2026081203,
        resamples=args.bootstrap_resamples,
    )
    reset_old_ci = (
        _bootstrap_median_ci(
            reset_minus_old_accuracy,
            seed=2026081204,
            resamples=args.bootstrap_resamples,
        )
        if reset_minus_old_accuracy
        else (None, None)
    )

    statistics_payload = {
        "reset_test_accuracy": {
            "mean": statistics.fmean(reset_accuracy),
            "median": _median(reset_accuracy),
            "sample_sd": (
                statistics.stdev(reset_accuracy)
                if len(reset_accuracy) > 1
                else 0.0
            ),
            "bootstrap_95_percent_median_ci": list(reset_accuracy_ci),
            "values": reset_accuracy,
        },
        "no_reset_test_accuracy": {
            "mean": statistics.fmean(no_reset_accuracy),
            "median": _median(no_reset_accuracy),
            "sample_sd": (
                statistics.stdev(no_reset_accuracy)
                if len(no_reset_accuracy) > 1
                else 0.0
            ),
            "values": no_reset_accuracy,
        },
        "reset_feature_count": {
            "mean": statistics.fmean(reset_features),
            "median": _median([float(value) for value in reset_features]),
            "bootstrap_95_percent_median_ci": list(reset_features_ci),
            "values": reset_features,
        },
        "no_reset_feature_count": {
            "mean": statistics.fmean(no_reset_features),
            "median": _median([float(value) for value in no_reset_features]),
            "values": no_reset_features,
        },
        "paired_reset_minus_no_reset": {
            "median_test_accuracy": _median(reset_minus_no_reset_accuracy),
            "bootstrap_95_percent_median_ci": list(reset_no_reset_ci),
            "test_accuracy_values": reset_minus_no_reset_accuracy,
            "median_feature_count": _median(
                [float(value) for value in reset_minus_no_reset_features]
            ),
            "feature_count_values": reset_minus_no_reset_features,
        },
        "paired_reset_minus_old": {
            "pairs": len(old_pairs),
            "median_test_accuracy": (
                _median(reset_minus_old_accuracy)
                if reset_minus_old_accuracy
                else None
            ),
            "bootstrap_95_percent_median_ci": list(reset_old_ci),
            "test_accuracy_values": reset_minus_old_accuracy,
            "median_feature_count": (
                _median([float(value) for value in reset_minus_old_features])
                if reset_minus_old_features
                else None
            ),
            "feature_count_values": reset_minus_old_features,
        },
        "reset_activation": {
            "runs_with_reset": sum(value > 0 for value in reset_events),
            "total_reset_events": sum(reset_events),
            "first_reset_median_evaluations": (
                _median([float(value) for value in first_reset_values])
                if first_reset_values
                else None
            ),
            "per_run_reset_events": reset_events,
        },
        "old_frozen": {
            "median_test_accuracy": OLD_MEDIAN_TEST_ACCURACY,
            "median_feature_count": OLD_MEDIAN_FEATURE_COUNT,
        },
    }

    full_frozen_ledger = args.seed_start == 1 and args.runs == 10
    active_ledger_ok = all(
        row["active_sampling"] == "frozen_passing_old_size_ledger"
        and int(row["active_sample_size"])
        == FROZEN_ACTIVE_SAMPLE_SIZES[int(row["seed"])]
        and isinstance(row["active_indices_sha256"], str)
        and len(row["active_indices_sha256"]) == 64
        for row in rows
        if int(row["seed"]) in FROZEN_ACTIVE_SAMPLE_SIZES
    )
    applied_gates = {
        "C0_COMPLETE": len(rows) == args.runs,
        "C0B_FROZEN_ACTIVE_LEDGER": full_frozen_ledger and active_ledger_ok,
        "C1_H1_NONINFERIOR": (
            full_frozen_ledger
            and statistics_payload["reset_test_accuracy"]["median"]
            >= 0.948455
        ),
        "C2_H1_BASELINE_GAIN": (
            full_frozen_ledger
            and sum(value - ALL_FEATURE_BASELINE >= 0.015 for value in reset_accuracy)
            >= 8
        ),
        "C3_H2_SPARSITY": (
            full_frozen_ledger
            and statistics_payload["reset_feature_count"]["median"] <= 8.0
        ),
    }
    applied_pass = all(applied_gates.values())

    reset_activated = sum(reset_events) > 0
    reset_changed_outcome = any(
        first != second
        for first, second in zip(
            [
                (
                    row["reset"]["test_accuracy"],  # type: ignore[index]
                    row["reset"]["selected_features"],  # type: ignore[index]
                )
                for row in rows
            ],
            [
                (
                    row["no_reset"]["test_accuracy"],  # type: ignore[index]
                    row["no_reset"]["selected_features"],  # type: ignore[index]
                )
                for row in rows
            ],
        )
    )
    if not reset_activated:
        reset_effect_status = "NOT_IDENTIFIABLE_RESET_BRANCH_DORMANT"
    elif not reset_changed_outcome:
        reset_effect_status = "RESET_ACTIVATED_NO_FINAL_OUTCOME_DIFFERENCE"
    elif _median(reset_minus_no_reset_accuracy) > 0.0:
        reset_effect_status = "POSITIVE_MEDIAN_RESET_ACCURACY_EFFECT"
    elif (
        _median(reset_minus_no_reset_accuracy) == 0.0
        and _median(
            [float(value) for value in reset_minus_no_reset_features]
        ) < 0.0
    ):
        reset_effect_status = "POSITIVE_MEDIAN_RESET_SPARSITY_EFFECT"
    else:
        reset_effect_status = "MIXED_OR_NONPOSITIVE_RESET_EFFECT"

    report = {
        "schema": "eu26-21-hybrid-1-census-campaign-v2",
        "parameters": {
            "seed_start": args.seed_start,
            "runs": args.runs,
            "budget": args.budget,
            "workers": args.workers,
            "initial_population": args.initial_population,
            "bootstrap_resamples": args.bootstrap_resamples,
        },
        "statistics": statistics_payload,
        "applied_gates": applied_gates,
        "applied_claim_status": (
            "PASS_HYBRID_1_APPLIED_H1_H2"
            if applied_pass
            else "PILOT_OR_APPLIED_GATE_NOT_PASSED"
        ),
        "reset_effect_status": reset_effect_status,
        "rows": rows,
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "applied_claim_status": report["applied_claim_status"],
        "reset_effect_status": reset_effect_status,
        "statistics": statistics_payload,
        "applied_gates": applied_gates,
    }, sort_keys=True))
    if args.enforce_h1_h2 and not applied_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Paired applied Census campaign for Hybrid 1 and its no-reset ablation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
from typing import Dict, List

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hybrid_1.census import (
        FeatureSelectionObjective,
        final_test_accuracy,
        prepare_author_census,
    )
    from hybrid_1.core import run_reset_lambda_ga, source_density_population
else:
    from .census import (
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
OLD_MEDIAN_TEST_ACCURACY = 0.949455
OLD_MEDIAN_FEATURE_COUNT = 8.0


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
    return {
        "validation_accuracy": result.best_fitness[0],
        "test_accuracy": final_test_accuracy(prepared, result.best_mask),
        "selected_feature_count": len(selected),
        "selected_features": selected,
        "evaluations": result.evaluations,
        "generations": result.generations,
        "reset_events": result.reset_events,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--budget", type=int, default=800)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--initial-population", type=int, default=50)
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
        rows.append({
            "seed": seed,
            "old_test_accuracy": OLD_TEST_ACCURACY.get(seed),
            "active_sample_size": int(prepared.active_instances.size),
            "reset": reset_row,
            "no_reset": no_reset_row,
        })

    reset_accuracy = [float(row["reset"]["test_accuracy"]) for row in rows]  # type: ignore[index]
    reset_features = [int(row["reset"]["selected_feature_count"]) for row in rows]  # type: ignore[index]
    no_reset_accuracy = [float(row["no_reset"]["test_accuracy"]) for row in rows]  # type: ignore[index]
    statistics_payload = {
        "reset_median_test_accuracy": statistics.median(reset_accuracy),
        "no_reset_median_test_accuracy": statistics.median(no_reset_accuracy),
        "reset_median_feature_count": statistics.median(reset_features),
        "old_frozen_median_test_accuracy": OLD_MEDIAN_TEST_ACCURACY,
        "old_frozen_median_feature_count": OLD_MEDIAN_FEATURE_COUNT,
    }
    full_frozen_ledger = args.seed_start == 1 and args.runs == 10
    gates = {
        "C0_COMPLETE": len(rows) == args.runs,
        "C1_H1_NONINFERIOR": (
            full_frozen_ledger
            and statistics_payload["reset_median_test_accuracy"] >= 0.948455
        ),
        "C2_H1_BASELINE_GAIN": (
            full_frozen_ledger
            and sum(
                float(row["reset"]["test_accuracy"])  # type: ignore[index]
                - 0.928681
                >= 0.015
                for row in rows
            )
            >= 8
        ),
        "C3_H2_SPARSITY": (
            full_frozen_ledger
            and statistics_payload["reset_median_feature_count"] <= 8.0
        ),
    }
    h1_h2_pass = all(gates.values())
    report = {
        "schema": "eu26-21-hybrid-1-census-campaign-v1",
        "parameters": {
            "seed_start": args.seed_start,
            "runs": args.runs,
            "budget": args.budget,
            "workers": args.workers,
            "initial_population": args.initial_population,
        },
        "statistics": statistics_payload,
        "gates": gates,
        "claim_status": (
            "PASS_HYBRID_1_APPLIED_H1_H2"
            if h1_h2_pass
            else "PILOT_OR_APPLIED_GATE_NOT_PASSED"
        ),
        "rows": rows,
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "claim_status": report["claim_status"],
        "statistics": statistics_payload,
        "gates": gates,
    }, sort_keys=True))
    if args.enforce_h1_h2 and not h1_h2_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

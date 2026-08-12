#!/usr/bin/env python3
"""Run one applied Census-Income Hybrid 1 endpoint."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

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

RESULT_PREFIX = "EU26_21_HYBRID_1_RESULT="


def run(
    upstream: Path,
    *,
    seed: int,
    budget: int,
    workers: int,
    reset: bool,
    initial_population: int,
) -> dict:
    prepared = prepare_author_census(upstream, seed)
    objective = FeatureSelectionObjective(
        prepared.x_train[prepared.active_instances],
        prepared.y_train[prepared.active_instances],
        prepared.x_validation,
        prepared.y_validation,
    )
    search_seed = seed + 1_000_003
    initial_rng = np.random.default_rng(search_seed + 99)
    initial_masks = source_density_population(
        initial_population,
        41,
        initial_rng,
    )
    started = time.perf_counter()
    result = run_reset_lambda_ga(
        objective,
        dimension=41,
        seed=search_seed,
        max_evaluations=budget,
        workers=workers,
        update_factor=1.5,
        reset=reset,
        initial_masks=initial_masks,
    )
    elapsed = time.perf_counter() - started
    test_accuracy = final_test_accuracy(prepared, result.best_mask)
    selected = [
        index for index, value in enumerate(result.best_mask) if value == 1
    ]
    payload = {
        "schema": "eu26-21-hybrid-1-census-v1",
        "profile": "reset_lambda_feature_selection" if reset else "no_reset_ablation",
        "seed": seed,
        "search_seed": search_seed,
        "workers": workers,
        "budget": budget,
        "initial_population": initial_population,
        "baseline_validation_accuracy": prepared.baseline_validation_accuracy,
        "baseline_test_accuracy": prepared.baseline_test_accuracy,
        "hybrid_validation_accuracy": result.best_fitness[0],
        "hybrid_test_accuracy": test_accuracy,
        "selected_feature_count": len(selected),
        "selected_features": selected,
        "evaluations": result.evaluations,
        "generations": result.generations,
        "reset_events": result.reset_events,
        "final_secondary_fitness": result.best_fitness[1],
        "elapsed_seconds": elapsed,
        "lambda_trace": [
            {
                "generation": row.generation,
                "before": row.lambda_before,
                "after": row.lambda_after,
                "reset": row.reset_event,
                "strict_success": row.strict_success,
                "mutation_strength": row.mutation_strength,
            }
            for row in result.trace
        ],
        "data": prepared.metadata,
    }
    if payload["evaluations"] > budget:
        raise RuntimeError("hybrid exceeded the logical evaluation budget")
    if not selected:
        raise RuntimeError("hybrid returned an empty feature subset")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--budget", type=int, default=800)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--initial-population", type=int, default=50)
    parser.add_argument("--no-reset", action="store_true")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    payload = run(
        args.upstream,
        seed=args.seed,
        budget=args.budget,
        workers=args.workers,
        reset=not args.no_reset,
        initial_population=args.initial_population,
    )
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(RESULT_PREFIX + json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()

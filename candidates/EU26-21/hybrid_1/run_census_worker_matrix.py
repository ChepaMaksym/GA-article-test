#!/usr/bin/env python3
"""Verify that 1/2/4 evaluation workers do not change Hybrid 1 results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hybrid_1.census import FeatureSelectionObjective, prepare_author_census
    from hybrid_1.core import run_reset_lambda_ga, source_density_population
else:
    from .census import FeatureSelectionObjective, prepare_author_census
    from .core import run_reset_lambda_ga, source_density_population


def signature(result) -> dict:
    return {
        "evaluations": result.evaluations,
        "generations": result.generations,
        "reset_events": result.reset_events,
        "best_mask": list(result.best_mask),
        "best_fitness": list(result.best_fitness),
        "trace": [
            [
                row.generation,
                row.evaluations,
                row.lambda_before,
                row.lambda_after,
                row.mutation_strength,
                row.strict_success,
                row.accepted,
                row.reset_event,
            ]
            for row in result.trace
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--budget", type=int, default=160)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    prepared = prepare_author_census(args.upstream, args.seed)
    objective = FeatureSelectionObjective(
        prepared.x_train[prepared.active_instances],
        prepared.y_train[prepared.active_instances],
        prepared.x_validation,
        prepared.y_validation,
    )
    search_seed = args.seed + 1_000_003
    initial_masks = source_density_population(
        20,
        41,
        np.random.default_rng(search_seed + 99),
    )
    results = {}
    for workers in (1, 2, 4):
        result = run_reset_lambda_ga(
            objective,
            dimension=41,
            seed=search_seed,
            max_evaluations=args.budget,
            workers=workers,
            reset=True,
            initial_masks=initial_masks,
        )
        results[str(workers)] = signature(result)
    invariant = results["1"] == results["2"] == results["4"]
    report = {
        "schema": "eu26-21-hybrid-1-worker-matrix-v1",
        "seed": args.seed,
        "budget": args.budget,
        "workers": [1, 2, 4],
        "invariant": invariant,
        "results": results,
        "active_sample_size": int(prepared.active_instances.size),
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "invariant": invariant,
        "active_sample_size": report["active_sample_size"],
    }, sort_keys=True))
    if not invariant:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

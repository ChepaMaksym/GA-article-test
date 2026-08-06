#!/usr/bin/env python3
"""Run one preregistered analytic GESMR configuration.

This driver emits a compact deterministic summary.  It does not implement
or claim a published-result equivalence gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from gesmr import GESMRConfig, get_benchmark, run_gesmr  # noqa: E402

PAPER_GENERATIONS = {2: 100, 30: 300, 100: 1000, 1000: 2500}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--function",
        required=True,
        choices=("ackley", "griewank", "rastrigin", "rosenbrock", "sphere"),
    )
    parser.add_argument("--dimension", required=True, type=int, choices=tuple(PAPER_GENERATIONS))
    parser.add_argument("--initial-std", required=True, type=float, choices=(1.0, 10.0))
    parser.add_argument("--seed", required=True, type=int, choices=range(40), metavar="0..39")
    parser.add_argument(
        "--generations",
        type=int,
        default=None,
        help="diagnostic override; omit for the source-grounded dimension budget",
    )
    parser.add_argument("--output", type=Path, default=None, help="optional JSON output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_generations = PAPER_GENERATIONS[args.dimension]
    generations = source_generations if args.generations is None else args.generations
    if generations < 0:
        raise SystemExit("--generations must be non-negative")

    result = run_gesmr(
        get_benchmark(args.function),
        dimension=args.dimension,
        initial_std=args.initial_std,
        seed=args.seed,
        generations=generations,
        config=GESMRConfig(),
    )
    summary = {
        "candidate_id": "USA26-01",
        "algorithm": "GESMR",
        "task_class": "direct_analytic_minimization",
        "function": args.function,
        "dimension": args.dimension,
        "initial_std": args.initial_std,
        "seed": args.seed,
        "generations": generations,
        "source_grounded_generations": source_generations,
        "diagnostic_budget_override": generations != source_generations,
        "objective_call_count": result.objective_call_count,
        "objective_row_evaluation_count": result.objective_row_evaluation_count,
        "initial_best": float(result.best_fitness_history[0]),
        "final_best": float(result.best_fitness_history[-1]),
        "initial_geometric_mean_sigma": float(result.geometric_mean_sigma_history[0]),
        "final_geometric_mean_sigma": float(result.geometric_mean_sigma_history[-1]),
        "initial_arithmetic_mean_sigma_diagnostic": float(
            result.arithmetic_mean_sigma_history[0]
        ),
        "final_arithmetic_mean_sigma_diagnostic": float(
            result.arithmetic_mean_sigma_history[-1]
        ),
        "mutation_rates_changed_within_run": bool(
            (result.sigma_history[1:] != result.sigma_history[:-1]).any()
        ),
        "verification_status": "NOT_A_PUBLISHED_RESULT_GATE",
    }
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(payload)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

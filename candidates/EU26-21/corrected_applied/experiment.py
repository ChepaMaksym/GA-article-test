"""One-seed corrected applied OLD/Hybrid experiment.

The source-compatible OLD reproduction remains frozen elsewhere.  This module
runs a new, explicitly amended applied profile with the official UCI test file,
instance-weight exclusion, weighted balanced-accuracy optimization, and a
paired 30-seed reset/no-reset ablation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import copy
import hashlib
import importlib
import json
from pathlib import Path
import random
import subprocess
import sys
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from hybrid_1.core import Mask, run_reset_lambda_ga, source_density_population
from .data_protocol import (
    ACTIVE_SAMPLE_SIZE,
    PREDICTIVE_DIMENSION,
    PreparedCorrectedCensus,
    WeightedBalancedFeatureObjective,
    WeightedDatasetAdapter,
    evaluate_mask_on_official_test,
    prepare_corrected_census,
)

EXPECTED_UPSTREAM_COMMIT = "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6"
INITIAL_POPULATION = 50
H1_BUDGET = 400
ABLATION_BUDGET = 2_500
UPDATE_FACTOR = 1.5
SEARCH_SEED_OFFSET = 1_000_003
INITIAL_MASK_SEED_OFFSET = 99


@dataclass(frozen=True)
class OldCorrectedResult:
    seed: int
    search_seed: int
    selected_mask: Tuple[int, ...]
    validation_weighted_balanced_accuracy: float
    active_best_weighted_balanced_accuracy: float
    active_nfe: int
    full_validation_nfe: int
    optimizer_nfe: int
    chunks: int
    final_distance: int
    official_test_metrics: Dict[str, Any]



def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()



def load_upstream_evolution(upstream: Path):
    root = upstream.resolve()
    commit = _git(root, "rev-parse", "HEAD")
    if commit != EXPECTED_UPSTREAM_COMMIT:
        raise RuntimeError("unexpected upstream commit: {0}".format(commit))
    code_dir = root / "code"
    if not code_dir.is_dir():
        raise RuntimeError("upstream code directory is missing")
    sys.path.insert(0, str(code_dir))
    try:
        module = importlib.import_module("Evolution")
        from deap import creator
    finally:
        try:
            sys.path.remove(str(code_dir))
        except ValueError:
            pass
    return module.Evolution, creator



def _mask_digest(masks: Sequence[Mask]) -> str:
    return hashlib.sha256(
        np.asarray(masks, dtype=np.uint8).tobytes(order="C")
    ).hexdigest()



def _objective(prepared: PreparedCorrectedCensus) -> WeightedBalancedFeatureObjective:
    active = prepared.active_instances
    return WeightedBalancedFeatureObjective(
        x_active=prepared.x_train[active],
        y_active=prepared.y_train[active],
        weight_active=prepared.weight_train[active],
        x_validation=prepared.x_validation,
        y_validation=prepared.y_validation,
        weight_validation=prepared.weight_validation,
    )



def run_old_corrected(
    prepared: PreparedCorrectedCensus,
    *,
    evolution,
    deap_creator,
    seed: int,
    initial_masks: Sequence[Mask],
    chunk_generations: int = 10,
    outer_no_change_limit: int = 2,
) -> OldCorrectedResult:
    """Run the source CHC search on the corrected weighted objective."""

    if chunk_generations < 1 or outer_no_change_limit < 1:
        raise ValueError("OLD stopping parameters must be positive")
    if not initial_masks:
        raise ValueError("OLD initial population must not be empty")
    if any(len(mask) != PREDICTIVE_DIMENSION for mask in initial_masks):
        raise ValueError("OLD corrected masks must contain 40 bits")

    search_seed = seed + SEARCH_SEED_OFFSET
    random.seed(search_seed)
    np.random.seed(search_seed)

    full_adapter = WeightedDatasetAdapter(prepared)
    active_adapter = copy.copy(full_adapter)
    active_adapter.set_instances(prepared.active_instances)
    toolbox = evolution.create_toolbox(
        "feature_selection",
        "validation",
        active_adapter,
        [],
    )
    population = [
        deap_creator.Individual(list(mask)) for mask in initial_masks
    ]

    original_evaluate = toolbox.evaluate
    active_nfe = 0
    full_validation_nfe = 0
    active_best = float("-inf")

    def counted_active_evaluate(individual):
        nonlocal active_nfe, active_best
        value = original_evaluate(individual)
        active_nfe += 1
        active_best = max(active_best, float(value[0]))
        return value

    toolbox.unregister("evaluate")
    toolbox.register("evaluate", counted_active_evaluate)

    evaluated_population: List[Any] = []
    best_full = float("-inf")
    best_mask: Tuple[int, ...] = tuple()
    no_change = 0
    distance = PREDICTIVE_DIMENSION // 4
    chunks = 0

    while no_change < outer_no_change_limit:
        no_change += 1
        _, population, distance = evolution.CHC(
            active_adapter,
            toolbox,
            distance,
            population,
            max_generations=chunk_generations,
            verbose=0,
        )
        chunks += 1
        for individual in population:
            if individual not in evaluated_population:
                evaluated_population.append(copy.deepcopy(individual))
                score = float(
                    evolution.evaluate(
                        individual,
                        "feature_selection",
                        "validation",
                        full_adapter,
                    )[0]
                )
                full_validation_nfe += 1
                if score > best_full:
                    best_full = score
                    best_mask = tuple(int(value) for value in individual)
                    no_change = 0
        if chunks > 100:
            raise RuntimeError("OLD corrected CHC exceeded chunk safety limit")

    if not best_mask or not any(best_mask):
        raise RuntimeError("OLD corrected CHC produced no valid mask")
    optimizer_nfe = active_nfe + full_validation_nfe
    if optimizer_nfe < len(initial_masks):
        raise RuntimeError("OLD corrected NFE missed initial evaluations")

    return OldCorrectedResult(
        seed=seed,
        search_seed=search_seed,
        selected_mask=best_mask,
        validation_weighted_balanced_accuracy=best_full,
        active_best_weighted_balanced_accuracy=active_best,
        active_nfe=active_nfe,
        full_validation_nfe=full_validation_nfe,
        optimizer_nfe=optimizer_nfe,
        chunks=chunks,
        final_distance=int(distance),
        official_test_metrics=evaluate_mask_on_official_test(prepared, best_mask),
    )



def _hybrid_result(
    prepared: PreparedCorrectedCensus,
    *,
    seed: int,
    initial_masks: Sequence[Mask],
    budget: int,
    reset: bool,
    workers: int,
) -> Dict[str, Any]:
    result = run_reset_lambda_ga(
        _objective(prepared),
        dimension=PREDICTIVE_DIMENSION,
        seed=seed + SEARCH_SEED_OFFSET,
        max_evaluations=budget,
        workers=workers,
        update_factor=UPDATE_FACTOR,
        reset=reset,
        initial_masks=initial_masks,
    )
    metrics = evaluate_mask_on_official_test(prepared, result.best_mask)
    return {
        "seed": seed,
        "search_seed": seed + SEARCH_SEED_OFFSET,
        "reset": reset,
        "workers": workers,
        "budget": budget,
        "evaluations": int(result.evaluations),
        "generations": int(result.generations),
        "reset_events": int(result.reset_events),
        "validation_weighted_balanced_accuracy": float(result.best_fitness[0]),
        "selected_mask": list(result.best_mask),
        "official_test_metrics": metrics,
    }



def run_corrected_seed(
    upstream: Path,
    official_test_path: Path,
    *,
    seed: int,
) -> Dict[str, Any]:
    evolution, deap_creator = load_upstream_evolution(upstream)
    train_path = upstream.resolve() / "data" / "census-income.data"
    prepared = prepare_corrected_census(
        train_path,
        official_test_path,
        seed=seed,
        active_sample_size=ACTIVE_SAMPLE_SIZE,
    )
    initial_masks = source_density_population(
        INITIAL_POPULATION,
        PREDICTIVE_DIMENSION,
        np.random.default_rng(seed + SEARCH_SEED_OFFSET + INITIAL_MASK_SEED_OFFSET),
    )

    baseline_mask = tuple([1] * PREDICTIVE_DIMENSION)
    baseline_metrics = evaluate_mask_on_official_test(prepared, baseline_mask)
    old = run_old_corrected(
        prepared,
        evolution=evolution,
        deap_creator=deap_creator,
        seed=seed,
        initial_masks=initial_masks,
    )
    hybrid_h1 = _hybrid_result(
        prepared,
        seed=seed,
        initial_masks=initial_masks,
        budget=H1_BUDGET,
        reset=True,
        workers=4,
    )
    hybrid_reset = _hybrid_result(
        prepared,
        seed=seed,
        initial_masks=initial_masks,
        budget=ABLATION_BUDGET,
        reset=True,
        workers=1,
    )
    hybrid_no_reset = _hybrid_result(
        prepared,
        seed=seed,
        initial_masks=initial_masks,
        budget=ABLATION_BUDGET,
        reset=False,
        workers=1,
    )

    return {
        "schema": "eu26-21-corrected-applied-row-v1",
        "seed": seed,
        "protocol": prepared.metadata,
        "initial_population": INITIAL_POPULATION,
        "initial_masks_sha256": _mask_digest(initial_masks),
        "baseline": {
            "selected_mask": list(baseline_mask),
            "official_test_metrics": baseline_metrics,
        },
        "old": asdict(old),
        "hybrid_h1": hybrid_h1,
        "hybrid_reset": hybrid_reset,
        "hybrid_no_reset": hybrid_no_reset,
    }



def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("official_test", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    row = run_corrected_seed(
        args.upstream,
        args.official_test,
        seed=args.seed,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(row, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "seed": row["seed"],
        "official_test_sha256": row["protocol"]["official_test_file_sha256"],
        "old_weighted_balanced_accuracy": row["old"]["official_test_metrics"]["weighted"]["balanced_accuracy"],
        "hybrid_h1_weighted_balanced_accuracy": row["hybrid_h1"]["official_test_metrics"]["weighted"]["balanced_accuracy"],
        "reset_weighted_balanced_accuracy": row["hybrid_reset"]["official_test_metrics"]["weighted"]["balanced_accuracy"],
        "no_reset_weighted_balanced_accuracy": row["hybrid_no_reset"]["official_test_metrics"]["weighted"]["balanced_accuracy"],
        "reset_events": row["hybrid_reset"]["reset_events"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

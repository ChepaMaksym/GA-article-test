"""Corrected paired OLD CHC-QX versus Hybrid 1 comparison.

Version 2 is frozen before inspection of the 30-seed outcome. It corrects a
methodological asymmetry in the first implementation: both optimizers now
record the first *evaluated* feature mask that reaches a validation target.
OLD target NFE includes all earlier outer full-validation reevaluations. Hybrid
H3 is executed sequentially so objective-call order is exact and independent
of thread scheduling. H1 may still use four workers because previous tests
established complete worker invariance for final scientific outputs.
"""
from __future__ import annotations

from dataclasses import asdict
import copy
import hashlib
import random
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np

from .census import FeatureSelectionObjective, final_test_accuracy
from .core import Mask, normalize_fitness, run_reset_lambda_ga, source_density_population
from .paired_comparison import (
    DEFAULT_ACTIVE_SAMPLE_SIZE,
    DEFAULT_TARGETS,
    OldRunResult,
    PreparedPair,
    _target_key,
    _validate_targets,
    prepare_fixed_pair,
)


class SequentialTargetObjective:
    """Count ordered objective calls and first-hit validation targets."""

    def __init__(self, objective, targets: Iterable[float]) -> None:
        self.objective = objective
        self.targets = _validate_targets(targets)
        self.calls = 0
        self.best_primary = float("-inf")
        self.first_hit: Dict[str, Optional[int]] = {
            _target_key(target): None for target in self.targets
        }

    def __call__(self, mask: Mask):
        self.calls += 1
        fitness = normalize_fitness(self.objective(mask))
        self.best_primary = max(self.best_primary, fitness[0])
        for target in self.targets:
            key = _target_key(target)
            if self.first_hit[key] is None and self.best_primary >= target:
                self.first_hit[key] = self.calls
        return fitness


def run_old_chcqx_v2(
    pair: PreparedPair,
    *,
    seed: int,
    initial_masks: Sequence[Mask],
    targets: Iterable[float] = DEFAULT_TARGETS,
    chunk_generations: int = 10,
    outer_no_change_limit: int = 2,
) -> OldRunResult:
    """Run source CHC-QX with symmetric, global logical-NFE accounting."""

    target_values = _validate_targets(targets)
    if chunk_generations < 1 or outer_no_change_limit < 1:
        raise ValueError("CHC stopping parameters must be positive")
    if not initial_masks:
        raise ValueError("initial_masks must not be empty")

    search_seed = int(seed) + 1_000_003
    random.seed(search_seed)
    np.random.seed(search_seed)

    dataset = pair.dataset
    evolution = pair.evolution
    gaqx_individual = copy.deepcopy(dataset)
    gaqx_individual.set_instances(pair.prepared.active_instances)
    toolbox = evolution.create_toolbox(
        "feature_selection",
        "validation",
        gaqx_individual,
        [],
    )
    population = [
        pair.deap_creator.Individual(list(mask)) for mask in initial_masks
    ]
    if any(len(individual) != 41 for individual in population):
        raise ValueError("OLD initial masks must contain 41 bits")

    original_evaluate = toolbox.evaluate
    active_nfe = 0
    full_validation_nfe = 0
    total_optimizer_nfe = 0
    best_active = float("-inf")
    nfe_to_target: Dict[str, Optional[int]] = {
        _target_key(target): None for target in target_values
    }

    def counted_active_evaluate(individual):
        nonlocal active_nfe, total_optimizer_nfe, best_active
        value = original_evaluate(individual)
        active_nfe += 1
        total_optimizer_nfe += 1
        score = float(value[0])
        best_active = max(best_active, score)
        for target in target_values:
            key = _target_key(target)
            if nfe_to_target[key] is None and best_active >= target:
                nfe_to_target[key] = total_optimizer_nfe
        return value

    toolbox.unregister("evaluate")
    toolbox.register("evaluate", counted_active_evaluate)

    evaluated_population = []
    best_full = float("-inf")
    best_mask: Optional[Tuple[int, ...]] = None
    no_change = 0
    distance = 41 // 4
    chunks = 0

    while no_change < outer_no_change_limit:
        no_change += 1
        _, population, distance = evolution.CHC(
            gaqx_individual,
            toolbox,
            distance,
            population,
            max_generations=chunk_generations,
            verbose=0,
        )
        chunks += 1
        for individual in population:
            if individual not in evaluated_population:
                evaluated_population.append(individual)
                score = float(
                    evolution.evaluate(
                        individual,
                        "feature_selection",
                        "validation",
                        dataset,
                    )[0]
                )
                full_validation_nfe += 1
                total_optimizer_nfe += 1
                if score > best_full:
                    best_full = score
                    best_mask = tuple(int(value) for value in individual)
                    no_change = 0
        if chunks > 100:
            raise RuntimeError("OLD CHC-QX exceeded the chunk safety limit")

    if best_mask is None or not any(best_mask):
        raise RuntimeError("OLD CHC-QX produced no valid best feature mask")
    selected = tuple(index for index, bit in enumerate(best_mask) if bit)
    test_accuracy = float(
        evolution.evaluate(
            list(best_mask),
            "feature_selection",
            "test",
            dataset,
        )[0]
    )
    if active_nfe < len(initial_masks):
        raise RuntimeError("OLD NFE counter missed initial population evaluations")
    if total_optimizer_nfe != active_nfe + full_validation_nfe:
        raise RuntimeError("OLD total logical NFE is inconsistent")

    return OldRunResult(
        seed=int(seed),
        search_seed=search_seed,
        active_sample_size=int(pair.prepared.active_instances.size),
        active_indices_sha256=str(
            pair.prepared.metadata["active_indices_sha256"]
        ),
        selected_features=selected,
        validation_accuracy=best_full,
        test_accuracy=test_accuracy,
        active_nfe=active_nfe,
        full_validation_nfe=full_validation_nfe,
        optimizer_nfe=total_optimizer_nfe,
        chunks=chunks,
        final_distance=int(distance),
        active_nfe_to_target=nfe_to_target,
        best_active_fitness=best_active,
    )


def _base_objective(pair: PreparedPair) -> FeatureSelectionObjective:
    return FeatureSelectionObjective(
        pair.prepared.x_train[pair.prepared.active_instances],
        pair.prepared.y_train[pair.prepared.active_instances],
        pair.prepared.x_validation,
        pair.prepared.y_validation,
    )


def run_hybrid_variant_v2(
    pair: PreparedPair,
    *,
    seed: int,
    initial_masks: Sequence[Mask],
    budget: int,
    workers: int,
    reset: bool = True,
    targets: Iterable[float] = DEFAULT_TARGETS,
    exact_first_hit: bool = False,
) -> Dict[str, Any]:
    """Run Hybrid 1, optionally with exact sequential first-hit NFE."""

    base = _base_objective(pair)
    tracker: Optional[SequentialTargetObjective]
    if exact_first_hit:
        if workers != 1:
            raise ValueError("exact first-hit Hybrid NFE requires workers=1")
        tracker = SequentialTargetObjective(base, targets)
        objective = tracker
    else:
        tracker = None
        objective = base

    result = run_reset_lambda_ga(
        objective,
        dimension=41,
        seed=int(seed) + 1_000_003,
        max_evaluations=budget,
        workers=workers,
        update_factor=1.5,
        reset=reset,
        initial_masks=initial_masks,
    )
    if tracker is not None and tracker.calls != result.evaluations:
        raise RuntimeError("Hybrid objective-call count disagrees with logical NFE")
    selected = tuple(
        index for index, bit in enumerate(result.best_mask) if bit
    )
    return {
        "seed": int(seed),
        "search_seed": int(seed) + 1_000_003,
        "budget": int(budget),
        "workers": int(workers),
        "reset": bool(reset),
        "exact_first_hit": bool(exact_first_hit),
        "selected_features": list(selected),
        "selected_feature_count": len(selected),
        "validation_accuracy": float(result.best_fitness[0]),
        "test_accuracy": final_test_accuracy(
            pair.prepared,
            result.best_mask,
        ),
        "evaluations": int(result.evaluations),
        "generations": int(result.generations),
        "reset_events": int(result.reset_events),
        "nfe_to_target": (
            dict(tracker.first_hit)
            if tracker is not None
            else {_target_key(target): None for target in _validate_targets(targets)}
        ),
        "best_evaluated_primary": (
            float(tracker.best_primary)
            if tracker is not None
            else None
        ),
        "best_mask": list(result.best_mask),
    }


def run_paired_seed_v2(
    upstream,
    *,
    seed: int,
    active_sample_size: int = DEFAULT_ACTIVE_SAMPLE_SIZE,
    initial_population: int = 50,
    h1_budget: int = 400,
    h3_budget: int = 2_500,
    h1_workers: int = 4,
    targets: Iterable[float] = DEFAULT_TARGETS,
) -> Dict[str, Any]:
    pair = prepare_fixed_pair(
        upstream,
        seed=seed,
        active_sample_size=active_sample_size,
    )
    search_seed = int(seed) + 1_000_003
    initial_masks = source_density_population(
        initial_population,
        41,
        np.random.default_rng(search_seed + 99),
    )
    old = run_old_chcqx_v2(
        pair,
        seed=seed,
        initial_masks=initial_masks,
        targets=targets,
    )
    hybrid_h1 = run_hybrid_variant_v2(
        pair,
        seed=seed,
        initial_masks=initial_masks,
        budget=h1_budget,
        workers=h1_workers,
        reset=True,
        targets=targets,
        exact_first_hit=False,
    )
    hybrid_h3 = run_hybrid_variant_v2(
        pair,
        seed=seed,
        initial_masks=initial_masks,
        budget=h3_budget,
        workers=1,
        reset=True,
        targets=targets,
        exact_first_hit=True,
    )
    return {
        "schema": "eu26-21-old-hybrid-paired-row-v2",
        "seed": int(seed),
        "active_sample_size": int(pair.prepared.active_instances.size),
        "active_indices_sha256": pair.prepared.metadata[
            "active_indices_sha256"
        ],
        "baseline_validation_accuracy": (
            pair.prepared.baseline_validation_accuracy
        ),
        "baseline_test_accuracy": pair.prepared.baseline_test_accuracy,
        "initial_population": int(initial_population),
        "initial_masks_sha256": hashlib.sha256(
            np.asarray(initial_masks, dtype=np.uint8).tobytes(order="C")
        ).hexdigest(),
        "old": asdict(old),
        "hybrid_h1": hybrid_h1,
        "hybrid_h3": hybrid_h3,
    }

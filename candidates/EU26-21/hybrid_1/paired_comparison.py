"""Paired OLD CHC-QX versus Hybrid 1 comparison with exact logical NFE.

The already reproduced author-source OLD endpoint remains unchanged. This
module adds a controlled comparison profile in which OLD and Hybrid 1 receive:

* the same Census-Income encoding and 60/20/20 split;
* the same deterministic active training sample;
* the same 50 initial feature masks;
* the same held-out validation and test partitions.

OLD uses the pinned public ``Evolution.CHC`` implementation. Hybrid 1 uses the
independent reset self-adjusting ``(1+(lambda,lambda))`` implementation. The
logical NFE counter records every wrapper feature-mask objective call; wall
clock time never enters the scientific comparison.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import copy
import hashlib
from pathlib import Path
import random
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from sklearn.tree import DecisionTreeClassifier

from .census import FeatureSelectionObjective, PreparedCensus, final_test_accuracy
from .core import Mask, RunResult, run_reset_lambda_ga, source_density_population

EXPECTED_UPSTREAM_COMMIT = "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6"
DEFAULT_ACTIVE_SAMPLE_SIZE = 14_964
DEFAULT_TARGETS = (0.945, 0.946, 0.947)


@dataclass(frozen=True)
class PreparedPair:
    dataset: Any
    evolution: Any
    deap_creator: Any
    prepared: PreparedCensus


@dataclass(frozen=True)
class OldRunResult:
    seed: int
    search_seed: int
    active_sample_size: int
    active_indices_sha256: str
    selected_features: Tuple[int, ...]
    validation_accuracy: float
    test_accuracy: float
    active_nfe: int
    full_validation_nfe: int
    optimizer_nfe: int
    chunks: int
    final_distance: int
    active_nfe_to_target: Mapping[str, Optional[int]]
    best_active_fitness: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def _target_key(target: float) -> str:
    return f"{float(target):.6f}"


def _validate_targets(targets: Iterable[float]) -> Tuple[float, ...]:
    values = tuple(sorted(set(float(value) for value in targets)))
    if not values or any(not 0.0 <= value <= 1.0 for value in values):
        raise ValueError("targets must be distinct probabilities in [0,1]")
    return values


def _candidate_sample_sizes(train_rows: int) -> Tuple[int, ...]:
    values: List[int] = []
    sample_size = train_rows // 2
    while sample_size > 5_000:
        values.append(int(sample_size))
        sample_size //= 2
    return tuple(values)


def prepare_fixed_pair(
    upstream: Path,
    *,
    seed: int,
    active_sample_size: int = DEFAULT_ACTIVE_SAMPLE_SIZE,
) -> PreparedPair:
    """Prepare one deterministic paired Census protocol.

    The active size 14,964 is the authenticated size in the executed author
    notebook. Candidate indices are generated in the public source order
    (n/2, n/4, ...), but no wall-clock timing ratio is used to choose among
    them. This removes the known hardware-dependent source decision before
    comparing optimizers.
    """

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    if isinstance(active_sample_size, bool) or not isinstance(active_sample_size, int):
        raise TypeError("active_sample_size must be an integer")

    root = upstream.resolve()
    commit = _git(root, "rev-parse", "HEAD")
    if commit != EXPECTED_UPSTREAM_COMMIT:
        raise RuntimeError(f"unexpected upstream commit: {commit}")
    code_dir = root / "code"
    dataset_path = root / "data" / "census-income.data"
    if not code_dir.is_dir() or not dataset_path.is_file():
        raise RuntimeError("pinned source or Census-Income data is missing")

    random.seed(seed)
    np.random.seed(seed)
    sys.path.insert(0, str(code_dir))
    try:
        from Dataset import Dataset  # type: ignore
        from Evolution import Evolution  # type: ignore
        from deap import creator as deap_creator  # type: ignore

        dataset = Dataset(
            str(dataset_path),
            ",",
            -1,
            divide_dataset=False,
            header=None,
        )
        dataset.divide_dataset(
            DecisionTreeClassifier(random_state=0),
            normalize=True,
            shuffle=False,
            all_features=True,
            all_instances=True,
            evaluate=True,
            partial_sample=False,
        )

        # Reproduce the source-controlled feature-mask population generation
        # before its progressive active-sample candidates.
        controlled_population = []
        for _ in range(10):
            controlled = copy.copy(dataset)
            controlled.divide_dataset(
                dataset.clf,
                normalize=True,
                shuffle=False,
                all_features=False,
                all_instances=True,
                evaluate=True,
                partial_sample=False,
            )
            controlled_population.append(controlled)

        candidates: Dict[int, np.ndarray] = {}
        for size in _candidate_sample_sizes(int(dataset.X_train.shape[0])):
            sampled = copy.copy(dataset)
            sampled.divide_dataset(
                dataset.clf,
                normalize=True,
                shuffle=False,
                all_features=True,
                all_instances=True,
                evaluate=False,
                partial_sample=size,
            )
            candidates[size] = np.asarray(sampled.instances, dtype=int).copy()
    finally:
        try:
            sys.path.remove(str(code_dir))
        except ValueError:
            pass

    if dataset.X.shape != (199_523, 41):
        raise RuntimeError(f"unexpected encoded shape: {dataset.X.shape}")
    split_sizes = (
        int(dataset.X_train.shape[0]),
        int(dataset.X_val.shape[0]),
        int(dataset.X_test.shape[0]),
    )
    if split_sizes != (119_713, 39_905, 39_905):
        raise RuntimeError(f"unexpected split sizes: {split_sizes}")
    if active_sample_size not in candidates:
        raise ValueError(
            f"active size {active_sample_size} is not in {sorted(candidates)}"
        )
    active = candidates[active_sample_size]
    if active.size != active_sample_size or len(np.unique(active)) != active.size:
        raise RuntimeError("active sample is not a unique index vector")
    active_hash = hashlib.sha256(
        np.asarray(active, dtype="<i8").tobytes(order="C")
    ).hexdigest()

    prepared = PreparedCensus(
        x_train=np.asarray(dataset.X_train, dtype=float),
        y_train=np.asarray(dataset.y_train),
        x_validation=np.asarray(dataset.X_val, dtype=float),
        y_validation=np.asarray(dataset.y_val),
        x_test=np.asarray(dataset.X_test, dtype=float),
        y_test=np.asarray(dataset.y_test),
        active_instances=active,
        baseline_validation_accuracy=float(dataset.ValidationAccuracy),
        baseline_test_accuracy=float(dataset.TestAccuracy),
        metadata={
            "upstream_commit": commit,
            "dataset_rows": 199_523,
            "features": 41,
            "split_sizes": list(split_sizes),
            "active_sample_size": active_sample_size,
            "active_indices_sha256": active_hash,
            "controlled_individuals": len(controlled_population),
            "active_sampling": "fixed_author_notebook_size_14964",
            "candidate_sample_sizes": list(sorted(candidates, reverse=True)),
        },
    )
    return PreparedPair(
        dataset=dataset,
        evolution=Evolution,
        deap_creator=deap_creator,
        prepared=prepared,
    )


def run_old_chcqx(
    pair: PreparedPair,
    *,
    seed: int,
    initial_masks: Sequence[Mask],
    targets: Iterable[float] = DEFAULT_TARGETS,
    chunk_generations: int = 10,
    outer_no_change_limit: int = 2,
) -> OldRunResult:
    """Run the pinned public CHC-QX search and count exact logical NFE."""

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
    best_active = float("-inf")
    nfe_to_target: Dict[str, Optional[int]] = {
        _target_key(target): None for target in target_values
    }

    def counted_evaluate(individual):
        nonlocal active_nfe, best_active
        value = original_evaluate(individual)
        active_nfe += 1
        score = float(value[0])
        best_active = max(best_active, score)
        for target in target_values:
            key = _target_key(target)
            if nfe_to_target[key] is None and best_active >= target:
                nfe_to_target[key] = active_nfe
        return value

    toolbox.unregister("evaluate")
    toolbox.register("evaluate", counted_evaluate)

    evaluated_population = []
    best_full = float("-inf")
    best_mask: Optional[Tuple[int, ...]] = None
    no_change = 0
    distance = 41 // 4
    chunks = 0
    full_validation_nfe = 0

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
        optimizer_nfe=active_nfe + full_validation_nfe,
        chunks=chunks,
        final_distance=int(distance),
        active_nfe_to_target=nfe_to_target,
        best_active_fitness=best_active,
    )


def hybrid_nfe_to_targets(
    result: RunResult,
    *,
    targets: Iterable[float] = DEFAULT_TARGETS,
    initial_evaluations: int,
) -> Dict[str, Optional[int]]:
    """Return first logical NFE at which the accepted parent reaches targets."""

    target_values = _validate_targets(targets)
    if initial_evaluations < 1 or initial_evaluations > result.evaluations:
        raise ValueError("invalid initial_evaluations")
    initial_primary = (
        result.trace[0].parent_primary_before
        if result.trace
        else result.best_fitness[0]
    )
    output: Dict[str, Optional[int]] = {}
    for target in target_values:
        key = _target_key(target)
        if initial_primary >= target:
            output[key] = initial_evaluations
            continue
        reached: Optional[int] = None
        for row in result.trace:
            parent_after = (
                row.candidate_primary
                if row.accepted
                else row.parent_primary_before
            )
            if parent_after >= target:
                reached = int(row.evaluations)
                break
        output[key] = reached
    return output


def run_hybrid_variant(
    pair: PreparedPair,
    *,
    seed: int,
    initial_masks: Sequence[Mask],
    budget: int,
    workers: int,
    reset: bool = True,
    targets: Iterable[float] = DEFAULT_TARGETS,
) -> Dict[str, Any]:
    objective = FeatureSelectionObjective(
        pair.prepared.x_train[pair.prepared.active_instances],
        pair.prepared.y_train[pair.prepared.active_instances],
        pair.prepared.x_validation,
        pair.prepared.y_validation,
    )
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
    selected = tuple(
        index for index, bit in enumerate(result.best_mask) if bit
    )
    return {
        "seed": int(seed),
        "search_seed": int(seed) + 1_000_003,
        "budget": int(budget),
        "workers": int(workers),
        "reset": bool(reset),
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
        "nfe_to_target": hybrid_nfe_to_targets(
            result,
            targets=targets,
            initial_evaluations=len(initial_masks),
        ),
        "best_mask": list(result.best_mask),
    }


def run_paired_seed(
    upstream: Path,
    *,
    seed: int,
    active_sample_size: int = DEFAULT_ACTIVE_SAMPLE_SIZE,
    initial_population: int = 50,
    h1_budget: int = 400,
    h3_budget: int = 2_500,
    workers: int = 1,
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
    old = run_old_chcqx(
        pair,
        seed=seed,
        initial_masks=initial_masks,
        targets=targets,
    )
    hybrid_h1 = run_hybrid_variant(
        pair,
        seed=seed,
        initial_masks=initial_masks,
        budget=h1_budget,
        workers=workers,
        reset=True,
        targets=targets,
    )
    hybrid_h3 = run_hybrid_variant(
        pair,
        seed=seed,
        initial_masks=initial_masks,
        budget=h3_budget,
        workers=workers,
        reset=True,
        targets=targets,
    )
    return {
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
        "old": old.to_dict(),
        "hybrid_h1": hybrid_h1,
        "hybrid_h3": hybrid_h3,
    }

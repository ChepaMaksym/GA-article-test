"""Census-Income bridge and feature-selection fitness for Hybrid 1.

The public CHC-QX source is invoked only to reproduce its data protocol and
active-sample choice.  The feature-subset optimizer itself is entirely the
independent Hybrid 1 implementation in :mod:`hybrid_1.core`.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
from pathlib import Path
import random
import subprocess
import sys
from typing import Any, Dict, Sequence, Tuple

import numpy as np
from sklearn.tree import DecisionTreeClassifier

from .core import Fitness, Mask

EXPECTED_UPSTREAM_COMMIT = "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6"
FROZEN_ACTIVE_SAMPLE_SIZES = {
    1: 7482,
    2: 7482,
    3: 14964,
    4: 7482,
    5: 14964,
    6: 14964,
    7: 7482,
    8: 14964,
    9: 7482,
    10: 14964,
}


@dataclass(frozen=True)
class PreparedCensus:
    x_train: np.ndarray
    y_train: np.ndarray
    x_validation: np.ndarray
    y_validation: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray
    active_instances: np.ndarray
    baseline_validation_accuracy: float
    baseline_test_accuracy: float
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class FeatureSelectionObjective:
    """Validation accuracy first; fewer selected features break ties."""

    x_active: np.ndarray
    y_active: np.ndarray
    x_validation: np.ndarray
    y_validation: np.ndarray
    classifier_seed: int = 0

    def __call__(self, mask: Mask) -> Fitness:
        selected = np.flatnonzero(np.asarray(mask, dtype=int))
        if selected.size == 0:
            return 0.0, -1.0
        model = DecisionTreeClassifier(random_state=self.classifier_seed)
        model.fit(
            self.x_active[:, selected],
            self.y_active,
        )
        predicted = model.predict(self.x_validation[:, selected])
        accuracy = float(np.mean(predicted == self.y_validation))
        sparsity = -float(selected.size) / float(len(mask))
        return accuracy, sparsity


def final_test_accuracy(
    prepared: PreparedCensus,
    mask: Sequence[int],
    classifier_seed: int = 0,
) -> float:
    selected = np.flatnonzero(np.asarray(mask, dtype=int))
    if selected.size == 0:
        return 0.0
    model = DecisionTreeClassifier(random_state=classifier_seed)
    model.fit(prepared.x_train[:, selected], prepared.y_train)
    predicted = model.predict(prepared.x_test[:, selected])
    return float(np.mean(predicted == prepared.y_test))


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def prepare_author_census(upstream: Path, seed: int) -> PreparedCensus:
    """Freeze the OLD source data split and active-sampling stage for Hybrid 1."""

    root = upstream.resolve()
    commit = _git(root, "rev-parse", "HEAD")
    if commit != EXPECTED_UPSTREAM_COMMIT:
        raise RuntimeError("unexpected CHC-QX upstream commit: " + commit)
    code_dir = root / "code"
    dataset_path = root / "data" / "census-income.data"
    if not code_dir.is_dir() or not dataset_path.is_file():
        raise RuntimeError("pinned CHC-QX source or Census data is missing")

    random.seed(seed)
    np.random.seed(seed)
    sys.path.insert(0, str(code_dir))
    try:
        from Dataset import Dataset  # type: ignore
        from Evolution import Evolution  # type: ignore

        dataset = Dataset(
            str(dataset_path),
            ",",
            -1,
            divide_dataset=False,
            header=None,
        )
        classifier = DecisionTreeClassifier(random_state=0)
        dataset.divide_dataset(
            classifier,
            normalize=True,
            shuffle=False,
            all_features=True,
            all_instances=True,
            evaluate=True,
            partial_sample=False,
        )
        if seed in FROZEN_ACTIVE_SAMPLE_SIZES:
            # Recreate the source random stream, but replace its hardware-time
            # stopping decision with the active-sample size observed in the
            # passing OLD seed ledger. This makes the Hybrid 1 applied protocol
            # reproducible across machines while preserving source generation.
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

            candidates = {}
            sample_size = dataset.X_train.shape[0] // 2
            while sample_size > 5000:
                sampled = copy.copy(dataset)
                sampled.divide_dataset(
                    dataset.clf,
                    normalize=True,
                    shuffle=False,
                    all_features=True,
                    all_instances=True,
                    evaluate=False,
                    partial_sample=sample_size,
                )
                candidates[int(sample_size)] = np.asarray(
                    sampled.instances, dtype=int
                ).copy()
                sample_size //= 2
            frozen_size = FROZEN_ACTIVE_SAMPLE_SIZES[seed]
            if frozen_size not in candidates:
                raise RuntimeError("frozen active-sample size is unavailable")
            selected_instances = candidates[frozen_size]
            active_protocol = "frozen_passing_old_size_ledger"
        else:
            selected_instances, controlled_population = Evolution.select_instances(
                10,
                dataset,
                minimum_sample_size=5000,
            )
            active_protocol = "author_source_progressive_halving"
    finally:
        try:
            sys.path.remove(str(code_dir))
        except ValueError:
            pass

    if dataset.X.shape != (199_523, 41):
        raise RuntimeError("unexpected encoded Census shape")
    split_sizes = (
        int(dataset.X_train.shape[0]),
        int(dataset.X_val.shape[0]),
        int(dataset.X_test.shape[0]),
    )
    if split_sizes != (119_713, 39_905, 39_905):
        raise RuntimeError("unexpected Census split sizes")
    active = np.asarray(selected_instances, dtype=int)
    if active.ndim != 1 or active.size < 5000:
        raise RuntimeError("invalid active-sampling result")
    if active.min() < 0 or active.max() >= split_sizes[0]:
        raise RuntimeError("active-sampling indices escaped the training split")

    return PreparedCensus(
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
            "active_sample_size": int(active.size),
            "controlled_individuals": int(len(controlled_population)),
            "data_protocol": "author_source_contiguous_60_20_20",
            "active_sampling": active_protocol,
            "frozen_active_sample_size": (
                FROZEN_ACTIVE_SAMPLE_SIZES.get(seed)
            ),
        },
    )

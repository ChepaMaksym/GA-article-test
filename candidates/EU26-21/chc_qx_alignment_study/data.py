"""Training-only corrected Census input and source-style QX sample selection.

No holdout arrays can appear in the training or scoring objects. The official
test loader is a separate late-stage function, called only after mask freezing.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import random
import time
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.tree import DecisionTreeClassifier

from corrected_applied.data_protocol import (
    CLASSIFIER_SEED, INSTANCE_WEIGHT_RAW_INDEX, PREDICTIVE_RAW_INDICES,
    SPLIT_SEED_BASE, TARGET_RAW_INDEX, TRANSFORMED_FEATURE_NAMES,
    TRANSFORMED_PREDICTIVE_RAW_INDICES, VALIDATION_FRACTION,
    _binary_target, _build_preprocessor, _read_raw, _weights,
)
from chc_qx_alignment_study.contract import (
    canonical_sha256, file_sha256, require, scalar_score, validate_mask,
)


def array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    header = f"{array.dtype.str}:{array.shape}".encode("ascii")
    return hashlib.sha256(header + array.tobytes(order="C")).hexdigest()


def readonly(value: np.ndarray) -> np.ndarray:
    value.setflags(write=False)
    return value


@dataclass(frozen=True, slots=True)
class TrainingPrepared:
    x_train: np.ndarray
    y_train: np.ndarray
    weight_train: np.ndarray
    x_validation: np.ndarray
    y_validation: np.ndarray
    weight_validation: np.ndarray
    train_raw_indices: np.ndarray
    validation_raw_indices: np.ndarray
    feature_names: tuple[str, ...]
    preprocessor: Any
    train_probe_raw: Any
    metadata: dict[str, Any]


def prepare_training(train_path: Path, *, seed: int) -> TrainingPrepared:
    require(type(seed) is int, "seed must be an integer")
    raw = _read_raw(train_path, 199_523)
    y_all = _binary_target(raw.iloc[:, TARGET_RAW_INDEX])
    weights_all = _weights(raw.iloc[:, INSTANCE_WEIGHT_RAW_INDEX])
    features = raw.iloc[:, list(PREDICTIVE_RAW_INDICES)].copy()
    splitter = StratifiedShuffleSplit(n_splits=1, test_size=VALIDATION_FRACTION,
                                     random_state=SPLIT_SEED_BASE + seed)
    train_index, validation_index = next(splitter.split(np.zeros(len(y_all)), y_all))
    preprocessor = _build_preprocessor()
    x_train = np.asarray(preprocessor.fit_transform(features.iloc[train_index]), dtype=float)
    x_validation = np.asarray(preprocessor.transform(features.iloc[validation_index]), dtype=float)
    require(x_train.shape[1] == x_validation.shape[1] == 40, "preprocessing changed mask dimension")
    require(np.isfinite(x_train).all() and np.isfinite(x_validation).all(), "nonfinite prepared features")
    y_train, y_validation = y_all[train_index], y_all[validation_index]
    weight_train, weight_validation = weights_all[train_index], weights_all[validation_index]
    arrays = {"x_train": x_train, "y_train": y_train, "weight_train": weight_train,
              "x_validation": x_validation, "y_validation": y_validation,
              "weight_validation": weight_validation,
              "train_raw_indices": np.asarray(train_index, dtype=np.int64),
              "validation_raw_indices": np.asarray(validation_index, dtype=np.int64)}
    metadata = {"schema": "eu26-21-qx-training-only-data-v1", "seed": seed,
                "train_file_sha256": file_sha256(train_path), "train_file_rows": len(raw),
                "train_partition_rows": len(train_index), "validation_partition_rows": len(validation_index),
                "split_seed": SPLIT_SEED_BASE + seed, "feature_names": list(TRANSFORMED_FEATURE_NAMES),
                "transformed_raw_indices": list(TRANSFORMED_PREDICTIVE_RAW_INDICES),
                "instance_weight_as_predictor": False, "instance_weight_as_sample_weight": True,
                "preprocessing_fit_scope": "internal_training_only", "test_arrays_loaded": False,
                "array_hashes": {name: array_sha256(value) for name, value in arrays.items()},
                "train_positive_count": int(np.sum(y_train)),
                "validation_positive_count": int(np.sum(y_validation))}
    return TrainingPrepared(**{name: readonly(value) for name, value in arrays.items()},
                            feature_names=TRANSFORMED_FEATURE_NAMES, preprocessor=preprocessor,
                            train_probe_raw=features.iloc[train_index[:8]].copy(), metadata=metadata)


@dataclass(frozen=True, slots=True)
class ScalarValidationObjective:
    x_training: np.ndarray
    y_training: np.ndarray
    weight_training: np.ndarray
    x_validation: np.ndarray
    y_validation: np.ndarray
    weight_validation: np.ndarray

    def measured(self, mask: Sequence[int], *, clock: Callable[[], float] = time.perf_counter) -> tuple[float, float]:
        selected = np.flatnonzero(validate_mask(mask))
        if not len(selected):
            return 0.0, 0.0
        x_training = self.x_training[:, selected]
        x_validation = self.x_validation[:, selected]
        model = DecisionTreeClassifier(random_state=CLASSIFIER_SEED)
        before = clock()
        model.fit(x_training, self.y_training, sample_weight=self.weight_training)
        predicted = model.predict(x_validation)
        duration = float(clock() - before)
        score = scalar_score(float(balanced_accuracy_score(self.y_validation, predicted,
                                                          sample_weight=self.weight_validation)))
        return score, duration

    def __call__(self, mask: Sequence[int]) -> float:
        return self.measured(mask)[0]


def objective_for(prepared: TrainingPrepared, rows: Sequence[int] | None = None) -> ScalarValidationObjective:
    if rows is None:
        x_train, y_train, weight_train = prepared.x_train, prepared.y_train, prepared.weight_train
    else:
        indices = np.asarray(rows)
        require(indices.ndim == 1 and len(indices) > 1 and indices.dtype.kind in "iu",
                "active row positions must be a nonempty integer vector")
        require(len(np.unique(indices)) == len(indices) and indices.min() >= 0
                and indices.max() < len(prepared.y_train), "active row positions invalid")
        x_train = readonly(prepared.x_train[indices])
        y_train = readonly(prepared.y_train[indices])
        weight_train = readonly(prepared.weight_train[indices])
    return ScalarValidationObjective(x_train, y_train, weight_train, prepared.x_validation,
                                     prepared.y_validation, prepared.weight_validation)


def source_density_masks(count: int, *, seed: int, nonempty: bool) -> tuple[tuple[int, ...], ...]:
    require(type(count) is int and count > 0 and type(seed) is int, "invalid density generation parameters")
    python_rng = random.Random(seed)
    numpy_rng = np.random.RandomState(seed)
    masks = []
    for _ in range(count):
        while True:
            zero_probability = python_rng.uniform(0.0, 1.0)
            mask = tuple(int(value) for value in numpy_rng.choice(
                [0, 1], 40, p=[zero_probability, 1.0 - zero_probability],
            ))
            if not nonempty or sum(mask):
                masks.append(mask)
                break
    return tuple(masks)


def select_active_rows(prepared: TrainingPrepared, *, seed: int,
                       clock: Callable[[], float] = time.perf_counter,
                       measured_score: Callable[[Sequence[int], tuple[int, ...]], tuple[float, float]] | None = None,
                       minimum_rows: int = 5000) -> dict[str, Any]:
    """Freeze progressive halving using raw Spearman and symmetric fit timers.

    The injected score/clock is solely a deterministic unit-fixture seam. The
    production entrypoint always uses the registered threshold 5000 and q=10.
    """
    controls = source_density_masks(10, seed=seed + 2000003, nonempty=True)
    row_rng = np.random.RandomState(seed + 2000003)
    # The source consumes NumPy draws for control masks before sampling rows.
    control_python_rng = random.Random(seed + 2000003)
    reproduced = []
    for _ in range(10):
        while True:
            zero_probability = control_python_rng.uniform(0.0, 1.0)
            mask = tuple(int(value) for value in row_rng.choice([0, 1], 40,
                         p=[zero_probability, 1.0 - zero_probability]))
            if sum(mask):
                reproduced.append(mask)
                break
    require(tuple(reproduced) == controls, "sampler control stream identity mismatch")
    full_rows = np.arange(len(prepared.y_train), dtype=np.int64)

    def measure(rows: np.ndarray) -> tuple[list[float], list[float]]:
        objective = objective_for(prepared, rows)
        outcomes = [(objective.measured(mask, clock=clock) if measured_score is None
                     else measured_score(rows.tolist(), mask)) for mask in controls]
        return [scalar_score(score) for score, _ in outcomes], [float(duration) for _, duration in outcomes]

    full_scores, full_durations = measure(full_rows)
    finite_times = (all(math.isfinite(value) and value > 0 for value in full_durations)
                    and math.isfinite(sum(full_durations)))
    full_time = float(sum(full_durations)) if finite_times else None
    payload: dict[str, Any] = {"status": "NOT_EVALUABLE_SAMPLER", "selection_seed": seed + 2000003,
                               "control_masks": [list(mask) for mask in controls], "full_scores": full_scores,
                               "full_fit_prediction_seconds": full_time,
                               "full_durations_seconds": [value if math.isfinite(value) else None for value in full_durations],
                               "timer_scope": "sum_q_tree_fit_and_validation_prediction", "q": 10,
                               "trials": [], "selected_rows": None, "sampler_validation_calls": 10,
                               "test_predictions": 0}
    if not finite_times:
        payload["reason"] = "nonpositive_or_nonfinite_full_fit_prediction_time"
        return payload
    size = len(full_rows) // 2
    best = float("inf")
    selected: np.ndarray | None = None
    while size > minimum_rows:
        rows = np.asarray(row_rng.choice(len(full_rows), size, replace=False), dtype=np.int64)
        sample_scores, durations = measure(rows)
        payload["sampler_validation_calls"] += 10
        finite_sample = (all(math.isfinite(value) and value > 0 for value in durations)
                         and math.isfinite(sum(durations)))
        approx_time = float(sum(durations)) if finite_sample else None
        rho = float(spearmanr(full_scores, sample_scores).statistic)
        valid = finite_sample and math.isfinite(rho)
        criterion = 1.0 - rho + approx_time / full_time if valid else None
        valid = bool(valid and criterion is not None and math.isfinite(criterion))
        if not valid:
            criterion = None
        improving = bool(valid and criterion < best)
        trial = {"size": size, "row_positions_sha256": array_sha256(rows),
                 "scores": sample_scores, "rho": rho if math.isfinite(rho) else None,
                 "rho_defined": math.isfinite(rho), "fit_prediction_seconds": approx_time,
                 "durations_seconds": [value if math.isfinite(value) else None for value in durations],
                 "criterion": criterion, "strictly_improving": improving}
        payload["trials"].append(trial)
        if not valid:
            payload["reason"] = "undefined_spearman_or_invalid_sample_time_or_criterion"
            return payload
        if not improving:
            break
        best, selected = float(criterion), rows
        size //= 2
    if selected is None:
        payload["reason"] = "no_registered_sampler_candidate"
        return payload
    payload.update({"status": "PASS_PREPARATION", "reason": "frozen_finite_sampler_choice",
                    "selected_rows": [int(index) for index in selected],
                    "selected_raw_row_ids": [int(index) for index in prepared.train_raw_indices[selected]],
                    "selected_rows_sha256": array_sha256(selected), "selected_row_count": len(selected),
                    "selected_criterion": best, "control_masks_sha256": canonical_sha256(payload["control_masks"])})
    return payload


@dataclass(frozen=True, slots=True)
class TerminalPrepared:
    x_train: np.ndarray
    y_train: np.ndarray
    weight_train: np.ndarray
    x_validation: np.ndarray
    y_validation: np.ndarray
    weight_validation: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray
    weight_test: np.ndarray
    feature_names: tuple[str, ...]
    preprocessor: Any
    train_probe_raw: Any


def load_terminal_holdout(prepared: TrainingPrepared, test_path: Path, *,
                          expected_test_sha256: str) -> TerminalPrepared:
    """Late-stage loader: this type must never be passed to search or sampling."""
    require(file_sha256(test_path) == expected_test_sha256, "test data hash mismatch")
    raw = _read_raw(test_path, 99_762)
    x_test = np.asarray(prepared.preprocessor.transform(raw.iloc[:, list(PREDICTIVE_RAW_INDICES)]), dtype=float)
    require(x_test.shape[1] == 40 and np.isfinite(x_test).all(), "invalid transformed holdout")
    return TerminalPrepared(prepared.x_train, prepared.y_train, prepared.weight_train,
                            prepared.x_validation, prepared.y_validation, prepared.weight_validation,
                            readonly(x_test), readonly(_binary_target(raw.iloc[:, TARGET_RAW_INDEX])),
                            readonly(_weights(raw.iloc[:, INSTANCE_WEIGHT_RAW_INDEX])),
                            prepared.feature_names, prepared.preprocessor, prepared.train_probe_raw)

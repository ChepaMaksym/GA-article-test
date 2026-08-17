"""Corrected Census-Income protocol for the applied validation track.

This module deliberately does *not* replace the already authenticated
public-source OLD reproduction.  It defines an additional applied profile that
addresses four limitations of the source-compatible experiment:

* the official UCI ``census-income.test`` file is the final held-out test set;
* the instance-weight column (raw index 24) is excluded from feature masks;
* instance weights are supplied to the classifier and weighted metrics;
* feature selection optimizes weighted balanced accuracy instead of accuracy.

The 40-bit predictive mask preserves one bit per non-weight UCI input variable.
Categorical variables use train-fitted ordinal encoding and unseen test values
map to ``-1``.  Numeric preprocessing and imputers are also fitted on the
training partition only.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from hybrid_1.core import Fitness, Mask, validate_mask

RAW_COLUMN_COUNT = 42
RAW_FEATURE_COUNT = 41
INSTANCE_WEIGHT_RAW_INDEX = 24
TARGET_RAW_INDEX = 41
PREDICTIVE_RAW_INDICES = tuple(
    index for index in range(RAW_FEATURE_COUNT) if index != INSTANCE_WEIGHT_RAW_INDEX
)
PREDICTIVE_DIMENSION = len(PREDICTIVE_RAW_INDICES)
ACTIVE_SAMPLE_SIZE = 14_964
VALIDATION_FRACTION = 0.20
SPLIT_SEED_BASE = 2_026_081_700
ACTIVE_SEED_BASE = 2_026_081_800
CLASSIFIER_SEED = 0

RAW_FEATURE_NAMES = (
    "age",
    "class_of_worker",
    "industry_code",
    "occupation_code",
    "education",
    "wage_per_hour",
    "enrolled_in_education_last_week",
    "marital_status",
    "major_industry_code",
    "major_occupation_code",
    "race",
    "hispanic_origin",
    "sex",
    "member_of_labor_union",
    "reason_for_unemployment",
    "full_or_part_time_employment_status",
    "capital_gains",
    "capital_losses",
    "dividends_from_stocks",
    "tax_filer_status",
    "region_of_previous_residence",
    "state_of_previous_residence",
    "detailed_household_and_family_status",
    "detailed_household_summary",
    "instance_weight",
    "migration_code_change_in_msa",
    "migration_code_change_in_region",
    "migration_code_move_within_region",
    "lived_in_house_one_year_ago",
    "migration_previous_residence_in_sunbelt",
    "persons_worked_for_employer",
    "family_members_under_18",
    "country_of_birth_father",
    "country_of_birth_mother",
    "country_of_birth_self",
    "citizenship",
    "own_business_or_self_employed",
    "veterans_questionnaire",
    "veterans_benefits",
    "weeks_worked_in_year",
    "year",
)
PREDICTIVE_FEATURE_NAMES = tuple(
    RAW_FEATURE_NAMES[index] for index in PREDICTIVE_RAW_INDICES
)
# Semantically continuous/count variables from the UCI/Keras metadata.
NUMERIC_RAW_INDICES = (0, 5, 16, 17, 18, 30, 39)
NUMERIC_PREDICTIVE_POSITIONS = tuple(
    PREDICTIVE_RAW_INDICES.index(index) for index in NUMERIC_RAW_INDICES
)
CATEGORICAL_PREDICTIVE_POSITIONS = tuple(
    index
    for index in range(PREDICTIVE_DIMENSION)
    if index not in NUMERIC_PREDICTIVE_POSITIONS
)
# ColumnTransformer emits numeric columns first and categorical columns second.
# This explicit mapping keeps every mask bit traceable to its raw UCI variable.
TRANSFORMED_PREDICTIVE_RAW_INDICES = tuple(NUMERIC_RAW_INDICES) + tuple(
    PREDICTIVE_RAW_INDICES[index]
    for index in CATEGORICAL_PREDICTIVE_POSITIONS
)
TRANSFORMED_FEATURE_NAMES = tuple(
    RAW_FEATURE_NAMES[index] for index in TRANSFORMED_PREDICTIVE_RAW_INDICES
)


@dataclass(frozen=True)
class PreparedCorrectedCensus:
    x_train: np.ndarray
    y_train: np.ndarray
    weight_train: np.ndarray
    x_validation: np.ndarray
    y_validation: np.ndarray
    weight_validation: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray
    weight_test: np.ndarray
    active_instances: np.ndarray
    feature_names: Tuple[str, ...]
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class WeightedBalancedFeatureObjective:
    """Weighted balanced accuracy first; fewer features break exact ties."""

    x_active: np.ndarray
    y_active: np.ndarray
    weight_active: np.ndarray
    x_validation: np.ndarray
    y_validation: np.ndarray
    weight_validation: np.ndarray
    classifier_seed: int = CLASSIFIER_SEED

    def __call__(self, mask: Mask) -> Fitness:
        validated = validate_mask(mask, self.x_active.shape[1])
        selected = np.flatnonzero(np.asarray(validated, dtype=int))
        if selected.size == 0:
            return 0.0, -1.0
        model = DecisionTreeClassifier(random_state=self.classifier_seed)
        model.fit(
            self.x_active[:, selected],
            self.y_active,
            sample_weight=self.weight_active,
        )
        predicted = model.predict(self.x_validation[:, selected])
        score = float(
            balanced_accuracy_score(
                self.y_validation,
                predicted,
                sample_weight=self.weight_validation,
            )
        )
        sparsity = -float(selected.size) / float(len(validated))
        return score, sparsity


class WeightedDatasetAdapter:
    """Minimal Dataset.py-compatible adapter for the source CHC search.

    The adapter intentionally exposes only methods used by ``Evolution.CHC``
    and ``Evolution.evaluate``.  Its ``ValidationAccuracy`` and ``TestAccuracy``
    fields mean weighted balanced accuracy in the corrected applied profile.
    """

    def __init__(self, prepared: PreparedCorrectedCensus) -> None:
        self.X_train = prepared.x_train
        self.y_train = prepared.y_train
        self.X_val = prepared.x_validation
        self.y_val = prepared.y_validation
        self.X_test = prepared.x_test
        self.y_test = prepared.y_test
        self.weight_train = prepared.weight_train
        self.weight_val = prepared.weight_validation
        self.weight_test = prepared.weight_test
        self.features = list(range(self.X_train.shape[1]))
        self.instances = list(range(self.X_train.shape[0]))
        self._base_classifier = DecisionTreeClassifier(random_state=CLASSIFIER_SEED)
        self.clf = clone(self._base_classifier)
        self.ValidationAccuracy = float("nan")
        self.TestAccuracy = float("nan")

    def __copy__(self) -> "WeightedDatasetAdapter":
        result = type(self).__new__(type(self))
        result.__dict__ = self.__dict__.copy()
        result.features = list(self.features)
        result.instances = list(self.instances)
        result.clf = clone(self._base_classifier)
        return result

    def set_features(self, selected_features: Sequence[int]) -> None:
        selected = [int(index) for index in selected_features]
        if not selected or len(selected) != len(set(selected)):
            raise ValueError("selected features must be non-empty and unique")
        if min(selected) < 0 or max(selected) >= self.X_train.shape[1]:
            raise ValueError("selected feature escaped corrected dimension")
        self.features = selected

    def set_instances(self, selected_instances: Sequence[int]) -> None:
        selected = [int(index) for index in selected_instances]
        if not selected or len(selected) != len(set(selected)):
            raise ValueError("selected instances must be non-empty and unique")
        if min(selected) < 0 or max(selected) >= self.X_train.shape[0]:
            raise ValueError("selected instance escaped training partition")
        self.instances = selected

    def fit_classifier(self) -> None:
        self.clf = clone(self._base_classifier)
        self.clf.fit(
            self.X_train[np.asarray(self.instances, dtype=int)][:, self.features],
            self.y_train[np.asarray(self.instances, dtype=int)],
            sample_weight=self.weight_train[np.asarray(self.instances, dtype=int)],
        )

    def set_validation_accuracy(self) -> None:
        predicted = self.clf.predict(self.X_val[:, self.features])
        self.ValidationAccuracy = float(
            balanced_accuracy_score(
                self.y_val,
                predicted,
                sample_weight=self.weight_val,
            )
        )

    def set_test_accuracy(self) -> None:
        predicted = self.clf.predict(self.X_test[:, self.features])
        self.TestAccuracy = float(
            balanced_accuracy_score(
                self.y_test,
                predicted,
                sample_weight=self.weight_test,
            )
        )

    def get_validation_accuracy(self) -> float:
        return self.ValidationAccuracy

    def get_test_accuracy(self) -> float:
        return self.TestAccuracy


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_raw(path: Path, expected_rows: int) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    frame = pd.read_csv(
        path,
        header=None,
        skipinitialspace=True,
        na_values=["?", " ?"],
        keep_default_na=True,
        low_memory=False,
    )
    if frame.shape != (expected_rows, RAW_COLUMN_COUNT):
        raise ValueError(
            "unexpected Census file shape: {0}, expected ({1}, {2})".format(
                frame.shape, expected_rows, RAW_COLUMN_COUNT
            )
        )
    return frame


def _binary_target(values: pd.Series) -> np.ndarray:
    normalized = values.astype(str).str.strip().str.rstrip(".")
    positive = normalized.str.contains("50000+", regex=False)
    negative = normalized.str.contains("- 50000", regex=False)
    if not bool((positive | negative).all()):
        unknown = sorted(set(normalized[~(positive | negative)].tolist()))
        raise ValueError("unknown Census target values: {0}".format(unknown[:5]))
    return positive.astype(np.int8).to_numpy()


def _weights(values: pd.Series) -> np.ndarray:
    numeric = pd.to_numeric(values, errors="raise").to_numpy(dtype=float)
    if numeric.ndim != 1 or not np.isfinite(numeric).all() or np.any(numeric <= 0):
        raise ValueError("instance weights must be positive finite values")
    return numeric


def _build_preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="most_frequent")),
            (
                "ordinal",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                    encoded_missing_value=-1,
                ),
            ),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric, list(NUMERIC_PREDICTIVE_POSITIONS)),
            (
                "categorical",
                categorical,
                list(CATEGORICAL_PREDICTIVE_POSITIONS),
            ),
        ],
        remainder="drop",
        sparse_threshold=0.0,
        verbose_feature_names_out=False,
    )


def prepare_corrected_census(
    train_path: Path,
    official_test_path: Path,
    *,
    seed: int,
    active_sample_size: int = ACTIVE_SAMPLE_SIZE,
) -> PreparedCorrectedCensus:
    """Create one stratified, weight-aware corrected applied protocol."""

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    if active_sample_size < 2:
        raise ValueError("active sample size must be at least two")

    train_raw = _read_raw(train_path, 199_523)
    test_raw = _read_raw(official_test_path, 99_762)

    train_y_all = _binary_target(train_raw.iloc[:, TARGET_RAW_INDEX])
    test_y = _binary_target(test_raw.iloc[:, TARGET_RAW_INDEX])
    train_weight_all = _weights(train_raw.iloc[:, INSTANCE_WEIGHT_RAW_INDEX])
    test_weight = _weights(test_raw.iloc[:, INSTANCE_WEIGHT_RAW_INDEX])

    train_features_raw = train_raw.iloc[:, list(PREDICTIVE_RAW_INDICES)].copy()
    test_features_raw = test_raw.iloc[:, list(PREDICTIVE_RAW_INDICES)].copy()
    if train_features_raw.shape[1] != PREDICTIVE_DIMENSION:
        raise RuntimeError("instance-weight exclusion did not produce 40 features")

    splitter = StratifiedShuffleSplit(
        n_splits=1,
        test_size=VALIDATION_FRACTION,
        random_state=SPLIT_SEED_BASE + seed,
    )
    train_index, validation_index = next(
        splitter.split(np.zeros(train_y_all.shape[0]), train_y_all)
    )

    preprocessor = _build_preprocessor()
    x_train = np.asarray(
        preprocessor.fit_transform(train_features_raw.iloc[train_index]),
        dtype=float,
    )
    x_validation = np.asarray(
        preprocessor.transform(train_features_raw.iloc[validation_index]),
        dtype=float,
    )
    x_test = np.asarray(preprocessor.transform(test_features_raw), dtype=float)

    if (
        x_train.shape[1] != PREDICTIVE_DIMENSION
        or x_validation.shape[1] != PREDICTIVE_DIMENSION
        or x_test.shape[1] != PREDICTIVE_DIMENSION
    ):
        raise RuntimeError("corrected preprocessing changed the 40-bit dimension")
    if not all(np.isfinite(array).all() for array in (x_train, x_validation, x_test)):
        raise RuntimeError("preprocessing produced non-finite values")

    y_train = train_y_all[train_index]
    y_validation = train_y_all[validation_index]
    weight_train = train_weight_all[train_index]
    weight_validation = train_weight_all[validation_index]

    if active_sample_size >= y_train.shape[0]:
        raise ValueError("active sample must be smaller than training partition")
    active_splitter = StratifiedShuffleSplit(
        n_splits=1,
        train_size=active_sample_size,
        random_state=ACTIVE_SEED_BASE + seed,
    )
    active_index, _ = next(
        active_splitter.split(np.zeros(y_train.shape[0]), y_train)
    )
    active_index = np.asarray(active_index, dtype=int)
    if active_index.size != active_sample_size or len(np.unique(active_index)) != active_index.size:
        raise RuntimeError("invalid corrected active sample")

    metadata: Dict[str, Any] = {
        "schema": "eu26-21-corrected-census-v1",
        "seed": seed,
        "train_file_rows": int(train_raw.shape[0]),
        "official_test_file_rows": int(test_raw.shape[0]),
        "raw_columns": RAW_COLUMN_COUNT,
        "raw_features_including_weight": RAW_FEATURE_COUNT,
        "instance_weight_raw_index": INSTANCE_WEIGHT_RAW_INDEX,
        "predictive_dimension": PREDICTIVE_DIMENSION,
        "feature_names": list(TRANSFORMED_FEATURE_NAMES),
        "train_partition_rows": int(train_index.size),
        "validation_partition_rows": int(validation_index.size),
        "active_sample_size": int(active_index.size),
        "split_seed": SPLIT_SEED_BASE + seed,
        "active_sample_seed": ACTIVE_SEED_BASE + seed,
        "train_file_sha256": _sha256(train_path),
        "official_test_file_sha256": _sha256(official_test_path),
        "active_indices_sha256": hashlib.sha256(
            np.asarray(active_index, dtype="<i8").tobytes(order="C")
        ).hexdigest(),
        "train_positive_count": int(np.sum(y_train)),
        "validation_positive_count": int(np.sum(y_validation)),
        "test_positive_count": int(np.sum(test_y)),
        "objective": "weighted_balanced_accuracy_then_sparsity",
        "official_test_used": True,
        "instance_weight_as_predictor": False,
        "instance_weight_as_sample_weight": True,
    }
    return PreparedCorrectedCensus(
        x_train=x_train,
        y_train=np.asarray(y_train, dtype=np.int8),
        weight_train=np.asarray(weight_train, dtype=float),
        x_validation=x_validation,
        y_validation=np.asarray(y_validation, dtype=np.int8),
        weight_validation=np.asarray(weight_validation, dtype=float),
        x_test=x_test,
        y_test=np.asarray(test_y, dtype=np.int8),
        weight_test=np.asarray(test_weight, dtype=float),
        active_instances=active_index,
        feature_names=TRANSFORMED_FEATURE_NAMES,
        metadata=metadata,
    )


def _mcc_from_confusion(tn: float, fp: float, fn: float, tp: float) -> float:
    numerator = tp * tn - fp * fn
    denominator = math.sqrt(
        (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    )
    return 0.0 if denominator == 0.0 else float(numerator / denominator)


def _metric_block(
    y_true: np.ndarray,
    predicted: np.ndarray,
    positive_probability: np.ndarray,
    sample_weight: Optional[np.ndarray],
) -> Dict[str, Any]:
    matrix = confusion_matrix(
        y_true,
        predicted,
        labels=[0, 1],
        sample_weight=sample_weight,
    ).astype(float)
    tn, fp, fn, tp = (float(value) for value in matrix.ravel())
    class_zero_weight = float(np.sum(sample_weight[y_true == 0])) if sample_weight is not None else float(np.sum(y_true == 0))
    class_one_weight = float(np.sum(sample_weight[y_true == 1])) if sample_weight is not None else float(np.sum(y_true == 1))
    total_weight = class_zero_weight + class_one_weight
    return {
        "accuracy": float(accuracy_score(y_true, predicted, sample_weight=sample_weight)),
        "balanced_accuracy": float(
            balanced_accuracy_score(y_true, predicted, sample_weight=sample_weight)
        ),
        "precision_positive": float(
            precision_score(
                y_true,
                predicted,
                pos_label=1,
                zero_division=0,
                sample_weight=sample_weight,
            )
        ),
        "recall_positive": float(
            recall_score(
                y_true,
                predicted,
                pos_label=1,
                zero_division=0,
                sample_weight=sample_weight,
            )
        ),
        "f1_positive": float(
            f1_score(
                y_true,
                predicted,
                pos_label=1,
                zero_division=0,
                sample_weight=sample_weight,
            )
        ),
        "mcc": _mcc_from_confusion(tn, fp, fn, tp),
        "roc_auc": float(
            roc_auc_score(y_true, positive_probability, sample_weight=sample_weight)
        ),
        "average_precision": float(
            average_precision_score(
                y_true,
                positive_probability,
                sample_weight=sample_weight,
            )
        ),
        "no_information_rate": (
            max(class_zero_weight, class_one_weight) / total_weight
        ),
        "confusion_matrix": [[tn, fp], [fn, tp]],
        "negative_support": class_zero_weight,
        "positive_support": class_one_weight,
    }


def evaluate_mask_on_official_test(
    prepared: PreparedCorrectedCensus,
    mask: Sequence[int],
) -> Dict[str, Any]:
    """Fit on corrected training data and report weighted and unweighted metrics."""

    validated = validate_mask(mask, PREDICTIVE_DIMENSION)
    selected = np.flatnonzero(np.asarray(validated, dtype=int))
    if selected.size == 0:
        raise ValueError("official-test evaluation requires a non-empty mask")
    model = DecisionTreeClassifier(random_state=CLASSIFIER_SEED)
    model.fit(
        prepared.x_train[:, selected],
        prepared.y_train,
        sample_weight=prepared.weight_train,
    )
    predicted = model.predict(prepared.x_test[:, selected])
    probability = model.predict_proba(prepared.x_test[:, selected])
    classes = [int(value) for value in model.classes_.tolist()]
    if 1 not in classes:
        raise RuntimeError("classifier did not expose positive-class probability")
    positive_probability = probability[:, classes.index(1)]
    return {
        "selected_feature_count": int(selected.size),
        "selected_predictive_indices": [int(value) for value in selected.tolist()],
        "selected_raw_indices": [
            int(TRANSFORMED_PREDICTIVE_RAW_INDICES[index]) for index in selected.tolist()
        ],
        "selected_feature_names": [
            TRANSFORMED_FEATURE_NAMES[index] for index in selected.tolist()
        ],
        "unweighted": _metric_block(
            prepared.y_test,
            predicted,
            positive_probability,
            None,
        ),
        "weighted": _metric_block(
            prepared.y_test,
            predicted,
            positive_probability,
            prepared.weight_test,
        ),
    }

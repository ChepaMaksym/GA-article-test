"""Persist each terminal model and verify its own round trip without test access.

Only bytes just serialized by this process are loaded. Reaggregation hashes
these bundles but never deserializes downloaded pickle/joblib objects.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np

from corrected_applied.data_protocol import evaluate_mask_on_official_test


SCHEMA = "eu26-21-common-bridge-model-evidence-v1"


def _digest(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array)
    header = json.dumps(
        {"dtype": value.dtype.str, "shape": list(value.shape)}, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(header + value.tobytes()).hexdigest()


def evaluate_and_persist(
    prepared: Any, mask: Sequence[int], *, path: Path, seed: int, arm: str,
    provenance: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence: dict[str, Any] = {}

    def retain(model: Any, selected: np.ndarray) -> None:
        if prepared.preprocessor is None or prepared.train_probe_raw is None:
            raise ValueError("terminal model evidence requires fitted preprocessing")
        probe_raw = prepared.train_probe_raw
        probe = np.asarray(prepared.preprocessor.transform(probe_raw), dtype=float)
        if probe.shape != (8, 40) or not np.array_equal(probe, prepared.x_train[:8]):
            raise ValueError("non-test probe does not reproduce training preprocessing")
        prediction = model.predict(probe[:, selected])
        probability = model.predict_proba(probe[:, selected])
        bundle = {
            "schema": SCHEMA, "seed": seed, "arm": arm,
            "provenance": dict(provenance), "mask": list(mask),
            "feature_names": list(prepared.feature_names),
            "preprocessor": prepared.preprocessor, "classifier": model,
            "selected_indices": selected.tolist(),
        }
        buffer = BytesIO()
        joblib.dump(bundle, buffer, compress=3)
        content = buffer.getvalue()
        # No arbitrary path or external artifact is ever accepted for loading.
        restored = joblib.load(BytesIO(content))  # nosec B301: our own in-memory dump
        restored_probe = np.asarray(restored["preprocessor"].transform(probe_raw), dtype=float)
        restored_selected = restored["selected_indices"]
        restored_prediction = restored["classifier"].predict(restored_probe[:, restored_selected])
        restored_probability = restored["classifier"].predict_proba(restored_probe[:, restored_selected])
        if not (
            np.array_equal(probe, restored_probe)
            and np.array_equal(prediction, restored_prediction)
            and np.array_equal(probability, restored_probability)
        ):
            raise ValueError("terminal model/preprocessing reload changed predictions")
        path.write_bytes(content)
        if path.read_bytes() != content:
            raise ValueError("persisted terminal bundle differs from verified bytes")
        evidence.update({
            "schema": SCHEMA, "file": path.name,
            "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
            "seed": seed, "arm": arm, "mask": list(mask),
            "selected_feature_names": [prepared.feature_names[index] for index in selected],
            "classifier": "DecisionTreeClassifier(random_state=0)",
            "classifier_parameters": model.get_params(deep=False),
            "preprocessing_fit_partition": "internal_training_only",
            "terminal_fit_partition": "internal_training_only",
            "reload_verification": "PASS_EXACT_NON_TEST_PROBE",
            "probe_source": "first_8_internal_training_rows",
            "probe_rows": 8, "probe_transformed_sha256": _digest(probe),
            "probe_prediction_sha256": _digest(prediction),
            "probe_probability_sha256": _digest(probability),
            "test_access_during_reload": False,
        })

    metrics = evaluate_mask_on_official_test(prepared, mask, model_sink=retain)
    if not evidence:
        raise ValueError("terminal evaluator failed to retain a model")
    return metrics, evidence

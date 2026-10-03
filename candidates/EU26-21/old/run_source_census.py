#!/usr/bin/env python3
"""Run one pinned author-source CHC-QX Census-Income OLD endpoint."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from typing import Any

import numpy as np

EXPECTED_COMMIT = "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6"
RESULT_PREFIX = "EU26_21_SOURCE_RESULT="


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def run(upstream: Path, seed: int) -> tuple[dict[str, Any], str]:
    root = upstream.resolve()
    commit = git(root, "rev-parse", "HEAD")
    if commit != EXPECTED_COMMIT:
        raise RuntimeError(f"unexpected upstream commit: {commit}")

    code_dir = root / "code"
    dataset_path = root / "data" / "census-income.data"
    source_path = code_dir / "Evolution.py"
    dataset_source_path = code_dir / "Dataset.py"
    notebook_path = code_dir / "Example.ipynb"
    for path in (dataset_path, source_path, dataset_source_path, notebook_path):
        if not path.is_file():
            raise RuntimeError(f"required upstream artifact missing: {path}")

    random.seed(seed)
    np.random.seed(seed)
    sys.path.insert(0, str(code_dir))

    from sklearn.tree import DecisionTreeClassifier
    from Dataset import Dataset
    from Evolution import Evolution

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

    if dataset.X.shape != (199_523, 41):
        raise RuntimeError(f"unexpected encoded Census shape: {dataset.X.shape}")
    split_sizes = [
        int(dataset.X_train.shape[0]),
        int(dataset.X_val.shape[0]),
        int(dataset.X_test.shape[0]),
    ]
    if split_sizes != [119_713, 39_905, 39_905]:
        raise RuntimeError(f"unexpected split sizes: {split_sizes}")
    labels, counts = np.unique(dataset.y, return_counts=True)
    if len(labels) != 2:
        raise RuntimeError(f"unexpected target labels: {labels.tolist()}")

    capture: dict[str, Any] = {}
    original_select_instances = Evolution.select_instances
    original_chc = Evolution.CHC
    chunk_d_values: list[int] = []
    chunk_improvement_rows: list[int] = []

    def select_instances_capture(
        n_individual: int,
        baseline_individual: Any,
        minimum_sample_size: int = 5000,
    ):
        selected, baseline_population = original_select_instances(
            n_individual,
            baseline_individual,
            minimum_sample_size=minimum_sample_size,
        )
        capture["meta_model_sample_size"] = int(len(selected))
        capture["controlled_individuals"] = int(len(baseline_population))
        return selected, baseline_population

    def chc_capture(*args: Any, **kwargs: Any):
        log, population, d = original_chc(*args, **kwargs)
        chunk_d_values.append(int(d))
        chunk_improvement_rows.append(int(len(log)))
        return log, population, d

    Evolution.select_instances = staticmethod(select_instances_capture)
    Evolution.CHC = staticmethod(chc_capture)

    console = io.StringIO()
    started = time.perf_counter()
    try:
        with redirect_stdout(console):
            log, baseline_full_data = Evolution.CHCqx(
                dataset,
                10,
                10,
                2,
                population_size=50,
                verbose=0,
            )
    finally:
        Evolution.select_instances = staticmethod(original_select_instances)
        Evolution.CHC = staticmethod(original_chc)
    elapsed = time.perf_counter() - started

    if log.empty:
        raise RuntimeError("author CHC-QX returned an empty improvement log")
    if len(baseline_full_data) != 10:
        raise RuntimeError(
            f"unexpected controlled-population size: {len(baseline_full_data)}"
        )
    feature_mask = [int(value) for value in list(log.iloc[-1]["ind"])]
    if len(feature_mask) != 41 or any(value not in (0, 1) for value in feature_mask):
        raise RuntimeError("invalid final binary feature mask")
    selected_features = [
        int(index) for index, value in enumerate(feature_mask) if value == 1
    ]
    if not selected_features:
        raise RuntimeError("CHC-QX returned an empty feature subset")

    validation_fitness = float(log.iloc[-1]["fitness"])
    test_accuracy = float(
        Evolution.evaluate(
            feature_mask,
            "feature_selection",
            "test",
            dataset,
        )[0]
    )
    if not 0.0 <= validation_fitness <= 1.0 or not 0.0 <= test_accuracy <= 1.0:
        raise RuntimeError("invalid accuracy endpoint")

    meta_model_sample_size = int(capture.get("meta_model_sample_size", 0))
    if not 5_000 <= meta_model_sample_size <= split_sizes[0]:
        raise RuntimeError(
            f"invalid meta-model sample size: {meta_model_sample_size}"
        )
    if not chunk_d_values:
        raise RuntimeError("CHC-QX did not execute a CHC chunk")

    result: dict[str, Any] = {
        "schema": "eu26-21-census-source-v1",
        "profile": "author_source_seeded",
        "seed": int(seed),
        "upstream_commit": commit,
        "dataset_rows": int(dataset.X.shape[0]),
        "raw_features": int(dataset.X.shape[1]),
        "target_labels": [int(value) for value in labels.tolist()],
        "target_counts": [int(value) for value in counts.tolist()],
        "split_sizes": split_sizes,
        "baseline_validation_accuracy": float(dataset.ValidationAccuracy),
        "baseline_test_accuracy": float(dataset.TestAccuracy),
        "meta_model_sample_size": meta_model_sample_size,
        "controlled_individuals": int(capture["controlled_individuals"]),
        "evolution_control_frequency": 10,
        "outer_no_change_limit": 2,
        "population_size": 50,
        "chc_chunk_count": int(len(chunk_d_values)),
        "chc_chunk_final_d": chunk_d_values,
        "chc_chunk_improvement_rows": chunk_improvement_rows,
        "improvement_rows": int(len(log)),
        "validation_fitness": validation_fitness,
        "test_accuracy": test_accuracy,
        "selected_feature_count": int(len(selected_features)),
        "selected_features": selected_features,
        "feature_mask": feature_mask,
        "elapsed_seconds": float(elapsed),
        "source_sha256": sha256(source_path),
        "dataset_source_sha256": sha256(dataset_source_path),
        "notebook_sha256": sha256(notebook_path),
        "data_sha256": sha256(dataset_path),
        "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
    }
    return result, console.getvalue()


def validate(result: dict[str, Any]) -> None:
    expected = {
        "schema": "eu26-21-census-source-v1",
        "profile": "author_source_seeded",
        "upstream_commit": EXPECTED_COMMIT,
        "dataset_rows": 199_523,
        "raw_features": 41,
        "split_sizes": [119_713, 39_905, 39_905],
        "controlled_individuals": 10,
        "evolution_control_frequency": 10,
        "outer_no_change_limit": 2,
        "population_size": 50,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise RuntimeError(f"source invariant failed: {key}={result.get(key)!r}")
    if len(result.get("target_labels", [])) != 2:
        raise RuntimeError("source invariant failed: target labels")
    if sum(result.get("target_counts", [])) != 199_523:
        raise RuntimeError("source invariant failed: target counts")
    if not 0.0 <= float(result["baseline_test_accuracy"]) <= 1.0:
        raise RuntimeError("invalid baseline test accuracy")
    if not 0.0 <= float(result["test_accuracy"]) <= 1.0:
        raise RuntimeError("invalid CHC-QX test accuracy")
    selected = result.get("selected_features")
    if not isinstance(selected, list) or not selected:
        raise RuntimeError("missing selected features")
    if selected != sorted(set(selected)) or min(selected) < 0 or max(selected) > 40:
        raise RuntimeError("invalid selected feature indices")
    if result.get("selected_feature_count") != len(selected):
        raise RuntimeError("selected feature count mismatch")
    if int(result.get("meta_model_sample_size", 0)) < 5_000:
        raise RuntimeError("invalid meta-model sample size")
    if int(result.get("chc_chunk_count", 0)) <= 0:
        raise RuntimeError("invalid CHC chunk accounting")
    for key in (
        "source_sha256",
        "dataset_source_sha256",
        "notebook_sha256",
        "data_sha256",
    ):
        value = result.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise RuntimeError(f"invalid hash field {key}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--log-file", type=Path)
    args = parser.parse_args()

    result, console = run(args.upstream, args.seed)
    validate(result)
    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        args.log_file.write_text(console, encoding="utf-8")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(RESULT_PREFIX + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Aggregate the corrected 30-seed applied experiment.

A negative or null hypothesis is a scientific result and does not make this
program fail.  Only malformed, incomplete, or inconsistent evidence raises an
error.  Primary H1 uses weighted balanced accuracy on the official UCI test
file.  H8 is an explicitly paired reset/no-reset ablation and is reported as
positive, negative, or no-clear-effect without forcing a desired sign.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, List, Mapping, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hybrid_1.run_old_hybrid_comparison import _bca_quantiles
else:
    from hybrid_1.run_old_hybrid_comparison import _bca_quantiles

RUNS = 30
H1_MARGIN = 0.001  # 0.10 percentage point
BOOTSTRAP_RESAMPLES = 50_000
PRIMARY_METRIC = "balanced_accuracy"
METRICS = (
    "accuracy",
    "balanced_accuracy",
    "precision_positive",
    "recall_positive",
    "f1_positive",
    "mcc",
    "roc_auc",
    "average_precision",
)


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values))


def _bca(values: Sequence[float], seed: int) -> Dict[str, Any]:
    if len(values) != RUNS:
        raise ValueError("BCa input must contain exactly 30 paired values")
    quantiles = _bca_quantiles(
        values,
        alphas=(0.025, 0.05, 0.975),
        seed=seed,
        resamples=BOOTSTRAP_RESAMPLES,
    )
    return {
        "point_median": _median(values),
        "two_sided_95": [quantiles["0.025000"], quantiles["0.975000"]],
        "two_sided_95_lower": quantiles["0.025000"],
        "two_sided_95_upper": quantiles["0.975000"],
        "one_sided_95_lower": quantiles["0.050000"],
        "values": [float(value) for value in values],
    }


def _metrics(result: Mapping[str, Any], weighted: bool = True) -> Mapping[str, Any]:
    official = result.get("official_test_metrics")
    if not isinstance(official, Mapping):
        raise ValueError("missing official-test metrics")
    block = official.get("weighted" if weighted else "unweighted")
    if not isinstance(block, Mapping):
        raise ValueError("missing metric block")
    return block


def _selected_count(result: Mapping[str, Any]) -> int:
    official = result.get("official_test_metrics")
    if not isinstance(official, Mapping):
        raise ValueError("missing official-test result")
    return int(official.get("selected_feature_count", 0))


def _validate_metric_block(block: Mapping[str, Any], label: str) -> None:
    for metric in METRICS:
        value = float(block.get(metric, float("nan")))
        if not math.isfinite(value):
            raise ValueError("{0}: non-finite {1}".format(label, metric))
        if metric != "mcc" and not 0.0 <= value <= 1.0:
            raise ValueError("{0}: invalid {1}".format(label, metric))
        if metric == "mcc" and not -1.0 <= value <= 1.0:
            raise ValueError("{0}: invalid MCC".format(label))
    matrix = block.get("confusion_matrix")
    if (
        not isinstance(matrix, list)
        or len(matrix) != 2
        or any(not isinstance(row, list) or len(row) != 2 for row in matrix)
    ):
        raise ValueError("{0}: invalid confusion matrix".format(label))
    if any(float(value) < 0.0 for row in matrix for value in row):
        raise ValueError("{0}: negative confusion-matrix cell".format(label))


def validate_row(row: Mapping[str, Any], seed: int) -> None:
    if row.get("schema") != "eu26-21-corrected-applied-row-v1":
        raise ValueError("seed {0}: row schema mismatch".format(seed))
    if int(row.get("seed", -1)) != seed:
        raise ValueError("seed {0}: seed mismatch".format(seed))
    protocol = row.get("protocol")
    if not isinstance(protocol, Mapping):
        raise ValueError("seed {0}: protocol missing".format(seed))
    required_protocol = {
        "official_test_file_rows": 99_762,
        "train_file_rows": 199_523,
        "raw_columns": 42,
        "instance_weight_raw_index": 24,
        "predictive_dimension": 40,
        "active_sample_size": 14_964,
        "official_test_used": True,
        "instance_weight_as_predictor": False,
        "instance_weight_as_sample_weight": True,
        "objective": "weighted_balanced_accuracy_then_sparsity",
    }
    for key, expected in required_protocol.items():
        if protocol.get(key) != expected:
            raise ValueError(
                "seed {0}: protocol {1}={2!r}, expected {3!r}".format(
                    seed, key, protocol.get(key), expected
                )
            )
    for digest_name in (
        "train_file_sha256",
        "official_test_file_sha256",
        "active_indices_sha256",
    ):
        digest = protocol.get(digest_name)
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("seed {0}: invalid {1}".format(seed, digest_name))
    initial_digest = row.get("initial_masks_sha256")
    if not isinstance(initial_digest, str) or len(initial_digest) != 64:
        raise ValueError("seed {0}: invalid initial mask digest".format(seed))

    baseline = row.get("baseline")
    old = row.get("old")
    h1 = row.get("hybrid_h1")
    reset = row.get("hybrid_reset")
    no_reset = row.get("hybrid_no_reset")
    if not all(isinstance(value, Mapping) for value in (baseline, old, h1, reset, no_reset)):
        raise ValueError("seed {0}: optimizer result missing".format(seed))
    assert isinstance(baseline, Mapping)
    assert isinstance(old, Mapping)
    assert isinstance(h1, Mapping)
    assert isinstance(reset, Mapping)
    assert isinstance(no_reset, Mapping)

    if h1.get("reset") is not True or reset.get("reset") is not True:
        raise ValueError("seed {0}: reset-enabled result is not marked reset".format(seed))
    if no_reset.get("reset") is not False:
        raise ValueError("seed {0}: no-reset result is not marked no-reset".format(seed))
    if int(h1.get("budget", -1)) != 400:
        raise ValueError("seed {0}: H1 budget mismatch".format(seed))
    if int(reset.get("budget", -1)) != 2_500 or int(no_reset.get("budget", -1)) != 2_500:
        raise ValueError("seed {0}: ablation budget mismatch".format(seed))
    if int(reset.get("workers", -1)) != 1 or int(no_reset.get("workers", -1)) != 1:
        raise ValueError("seed {0}: ablation must be sequential".format(seed))
    if int(old.get("optimizer_nfe", 0)) != int(old.get("active_nfe", -1)) + int(old.get("full_validation_nfe", -1)):
        raise ValueError("seed {0}: OLD NFE accounting mismatch".format(seed))

    for name, result in (
        ("baseline", baseline),
        ("old", old),
        ("hybrid_h1", h1),
        ("hybrid_reset", reset),
        ("hybrid_no_reset", no_reset),
    ):
        official = result.get("official_test_metrics")
        if not isinstance(official, Mapping):
            raise ValueError("seed {0}: {1} metrics missing".format(seed, name))
        count = int(official.get("selected_feature_count", 0))
        if not 1 <= count <= 40:
            raise ValueError("seed {0}: {1} feature count invalid".format(seed, name))
        _validate_metric_block(_metrics(result, weighted=True), "seed {0} {1} weighted".format(seed, name))
        _validate_metric_block(_metrics(result, weighted=False), "seed {0} {1} unweighted".format(seed, name))


def _series(rows: Sequence[Mapping[str, Any]], key: str, metric: str, weighted: bool = True) -> List[float]:
    return [float(_metrics(row[key], weighted=weighted)[metric]) for row in rows]  # type: ignore[index]


def _metric_summary(rows: Sequence[Mapping[str, Any]], key: str) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for weighting in ("weighted", "unweighted"):
        use_weight = weighting == "weighted"
        output[weighting] = {
            metric: {
                "mean": float(statistics.fmean(_series(rows, key, metric, use_weight))),
                "median": _median(_series(rows, key, metric, use_weight)),
                "values": _series(rows, key, metric, use_weight),
            }
            for metric in METRICS
        }
    counts = [_selected_count(row[key]) for row in rows]  # type: ignore[index]
    output["selected_feature_count"] = {
        "mean": float(statistics.fmean(counts)),
        "median": _median([float(value) for value in counts]),
        "values": counts,
    }
    return output


def _paired_interval(rows: Sequence[Mapping[str, Any]], left: str, right: str, metric: str, seed: int) -> Dict[str, Any]:
    differences = [
        float(_metrics(row[left])[metric]) - float(_metrics(row[right])[metric])  # type: ignore[index]
        for row in rows
    ]
    return _bca(differences, seed)


def _plot_results(rows: Sequence[Mapping[str, Any]], report: Mapping[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    old = np.asarray(_series(rows, "old", PRIMARY_METRIC), dtype=float)
    h1 = np.asarray(_series(rows, "hybrid_h1", PRIMARY_METRIC), dtype=float)
    reset = np.asarray(_series(rows, "hybrid_reset", PRIMARY_METRIC), dtype=float)
    no_reset = np.asarray(_series(rows, "hybrid_no_reset", PRIMARY_METRIC), dtype=float)
    seeds = np.arange(1, RUNS + 1)

    figure, axis = plt.subplots(figsize=(6.5, 5.5))
    axis.scatter(old, h1)
    lower = min(float(old.min()), float(h1.min()))
    upper = max(float(old.max()), float(h1.max()))
    axis.plot([lower, upper], [lower, upper], linestyle="--")
    axis.set_xlabel("OLD weighted balanced accuracy")
    axis.set_ylabel("Hybrid H1 weighted balanced accuracy")
    axis.set_title("Paired official-test quality: OLD vs Hybrid H1")
    figure.tight_layout()
    figure.savefig(output_dir / "paired_old_vs_hybrid_balanced_accuracy.png", dpi=180)
    plt.close(figure)

    differences = (h1 - old) * 100.0
    figure, axis = plt.subplots(figsize=(8.0, 4.5))
    axis.scatter(seeds, differences)
    axis.axhline(-H1_MARGIN * 100.0, linestyle="--", label="-0.10 pp margin")
    axis.axhline(0.0, linewidth=0.8)
    axis.set_xlabel("Seed")
    axis.set_ylabel("Hybrid - OLD, percentage points")
    axis.set_title("Paired H1 differences with non-inferiority margin")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_dir / "paired_h1_difference_margin.png", dpi=180)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(6.5, 5.5))
    axis.scatter(no_reset, reset)
    lower = min(float(no_reset.min()), float(reset.min()))
    upper = max(float(no_reset.max()), float(reset.max()))
    axis.plot([lower, upper], [lower, upper], linestyle="--")
    axis.set_xlabel("Hybrid no-reset weighted balanced accuracy")
    axis.set_ylabel("Hybrid reset weighted balanced accuracy")
    axis.set_title("Reset-specific paired ablation")
    figure.tight_layout()
    figure.savefig(output_dir / "paired_reset_vs_no_reset.png", dpi=180)
    plt.close(figure)

    old_counts = [_selected_count(row["old"]) for row in rows]  # type: ignore[index]
    h1_counts = [_selected_count(row["hybrid_h1"]) for row in rows]  # type: ignore[index]
    reset_counts = [_selected_count(row["hybrid_reset"]) for row in rows]  # type: ignore[index]
    no_reset_counts = [_selected_count(row["hybrid_no_reset"]) for row in rows]  # type: ignore[index]
    figure, axis = plt.subplots(figsize=(7.0, 4.8))
    axis.boxplot(
        [old_counts, h1_counts, reset_counts, no_reset_counts],
        labels=["OLD", "Hybrid H1", "Reset", "No reset"],
    )
    axis.set_ylabel("Selected predictive features")
    axis.set_title("Feature-subset distributions (instance weight excluded)")
    figure.tight_layout()
    figure.savefig(output_dir / "feature_count_boxplot.png", dpi=180)
    plt.close(figure)

    metric_labels = ["Balanced acc.", "F1+", "MCC", "ROC-AUC", "PR-AUC"]
    metric_keys = ["balanced_accuracy", "f1_positive", "mcc", "roc_auc", "average_precision"]
    algorithms = ["baseline", "old", "hybrid_h1"]
    x = np.arange(len(metric_keys))
    width = 0.24
    figure, axis = plt.subplots(figsize=(9.0, 5.0))
    for index, algorithm in enumerate(algorithms):
        medians = [
            float(report["metrics"][algorithm]["weighted"][metric]["median"])  # type: ignore[index]
            for metric in metric_keys
        ]
        axis.bar(x + (index - 1) * width, medians, width, label=algorithm)
    axis.set_xticks(x)
    axis.set_xticklabels(metric_labels)
    axis.set_ylabel("Weighted metric")
    axis.set_title("Official-test weighted metrics")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_dir / "weighted_metric_medians.png", dpi=180)
    plt.close(figure)


def evaluate(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if len(rows) != RUNS:
        raise ValueError("corrected campaign requires exactly 30 rows")
    for seed, row in enumerate(rows, start=1):
        validate_row(row, seed)
    if [int(row["seed"]) for row in rows] != list(range(1, RUNS + 1)):
        raise ValueError("seed ledger is not 1..30")

    test_hashes = {str(row["protocol"]["official_test_file_sha256"]) for row in rows}  # type: ignore[index]
    train_hashes = {str(row["protocol"]["train_file_sha256"]) for row in rows}  # type: ignore[index]
    if len(test_hashes) != 1 or len(train_hashes) != 1:
        raise ValueError("dataset hashes differ across seeds")

    h1_interval = _paired_interval(rows, "hybrid_h1", "old", PRIMARY_METRIC, 2026081801)
    h1_pass = float(h1_interval["two_sided_95_lower"]) >= -H1_MARGIN
    feature_differences = [
        _selected_count(row["hybrid_h1"]) - _selected_count(row["old"])  # type: ignore[index]
        for row in rows
    ]
    h2_point = _median([float(value) for value in feature_differences])
    h2_decision = (
        "PASS" if h1_pass and h2_point <= 0.0 else "BLOCKED_BY_H1" if not h1_pass else "FAIL"
    )

    reset_interval = _paired_interval(
        rows,
        "hybrid_reset",
        "hybrid_no_reset",
        PRIMARY_METRIC,
        2026081802,
    )
    reset_lower = float(reset_interval["two_sided_95_lower"])
    reset_upper = float(reset_interval["two_sided_95_upper"])
    if reset_lower > 0.0:
        reset_decision = "POSITIVE_CONFIDENCE"
    elif reset_upper < 0.0:
        reset_decision = "NEGATIVE_CONFIDENCE"
    else:
        reset_decision = "NO_CLEAR_EFFECT"

    reset_events = [int(row["hybrid_reset"]["reset_events"]) for row in rows]  # type: ignore[index]
    margin_sensitivity = {
        f"{margin * 100.0:.2f}_percentage_point": (
            float(h1_interval["two_sided_95_lower"]) >= -margin
        )
        for margin in (0.0005, 0.0010, 0.0015, 0.0020)
    }

    metrics = {
        key: _metric_summary(rows, key)
        for key in ("baseline", "old", "hybrid_h1", "hybrid_reset", "hybrid_no_reset")
    }
    report: Dict[str, Any] = {
        "schema": "eu26-21-corrected-applied-report-v1",
        "claim_status": "PASS_PROTOCOL_RESULTS_AVAILABLE",
        "protocol": {
            "runs": RUNS,
            "seed_ledger": list(range(1, RUNS + 1)),
            "official_test_rows": 99_762,
            "source_train_rows": 199_523,
            "predictive_dimension": 40,
            "instance_weight_raw_index": 24,
            "instance_weight_as_predictor": False,
            "instance_weight_as_sample_weight": True,
            "primary_metric": "weighted_balanced_accuracy",
            "h1_margin": H1_MARGIN,
            "bootstrap_method": "paired median BCa",
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "official_test_file_sha256": next(iter(test_hashes)),
            "train_file_sha256": next(iter(train_hashes)),
            "split_variability": "stratified train/validation split changes with seed",
        },
        "metrics": metrics,
        "h1_corrected": {
            "decision": "PASS_CONFIDENCE_BOUND" if h1_pass else "FAIL_NONINFERIORITY",
            "metric": "weighted_balanced_accuracy",
            "margin": H1_MARGIN,
            "paired_hybrid_minus_old": h1_interval,
            "margin_sensitivity": margin_sensitivity,
        },
        "h2_corrected": {
            "decision": h2_decision,
            "paired_hybrid_minus_old_feature_count_median": h2_point,
            "paired_values": feature_differences,
        },
        "h8_reset_ablation": {
            "decision": reset_decision,
            "metric": "weighted_balanced_accuracy",
            "paired_reset_minus_no_reset": reset_interval,
            "runs_with_reset_event": sum(value > 0 for value in reset_events),
            "total_reset_events": sum(reset_events),
            "reset_event_counts": reset_events,
            "interpretation": (
                "This is the reset-specific Census result. It is kept even if null or negative."
            ),
        },
        "rows": list(rows),
    }
    return report


def _write_csv(rows: Sequence[Mapping[str, Any]], path: Path) -> None:
    fields = [
        "seed",
        "baseline_weighted_balanced_accuracy",
        "old_weighted_balanced_accuracy",
        "hybrid_h1_weighted_balanced_accuracy",
        "hybrid_h1_minus_old",
        "reset_weighted_balanced_accuracy",
        "no_reset_weighted_balanced_accuracy",
        "reset_minus_no_reset",
        "baseline_weighted_f1",
        "old_weighted_f1",
        "hybrid_h1_weighted_f1",
        "old_features",
        "hybrid_h1_features",
        "reset_features",
        "no_reset_features",
        "old_nfe",
        "h1_nfe",
        "reset_nfe",
        "no_reset_nfe",
        "reset_events",
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            old_ba = float(_metrics(row["old"])[PRIMARY_METRIC])  # type: ignore[index]
            h1_ba = float(_metrics(row["hybrid_h1"])[PRIMARY_METRIC])  # type: ignore[index]
            reset_ba = float(_metrics(row["hybrid_reset"])[PRIMARY_METRIC])  # type: ignore[index]
            no_reset_ba = float(_metrics(row["hybrid_no_reset"])[PRIMARY_METRIC])  # type: ignore[index]
            writer.writerow({
                "seed": int(row["seed"]),
                "baseline_weighted_balanced_accuracy": float(_metrics(row["baseline"])[PRIMARY_METRIC]),  # type: ignore[index]
                "old_weighted_balanced_accuracy": old_ba,
                "hybrid_h1_weighted_balanced_accuracy": h1_ba,
                "hybrid_h1_minus_old": h1_ba - old_ba,
                "reset_weighted_balanced_accuracy": reset_ba,
                "no_reset_weighted_balanced_accuracy": no_reset_ba,
                "reset_minus_no_reset": reset_ba - no_reset_ba,
                "baseline_weighted_f1": float(_metrics(row["baseline"])["f1_positive"]),  # type: ignore[index]
                "old_weighted_f1": float(_metrics(row["old"])["f1_positive"]),  # type: ignore[index]
                "hybrid_h1_weighted_f1": float(_metrics(row["hybrid_h1"])["f1_positive"]),  # type: ignore[index]
                "old_features": _selected_count(row["old"]),  # type: ignore[index]
                "hybrid_h1_features": _selected_count(row["hybrid_h1"]),  # type: ignore[index]
                "reset_features": _selected_count(row["hybrid_reset"]),  # type: ignore[index]
                "no_reset_features": _selected_count(row["hybrid_no_reset"]),  # type: ignore[index]
                "old_nfe": int(row["old"]["optimizer_nfe"]),  # type: ignore[index]
                "h1_nfe": int(row["hybrid_h1"]["evaluations"]),  # type: ignore[index]
                "reset_nfe": int(row["hybrid_reset"]["evaluations"]),  # type: ignore[index]
                "no_reset_nfe": int(row["hybrid_no_reset"]["evaluations"]),  # type: ignore[index]
                "reset_events": int(row["hybrid_reset"]["reset_events"]),  # type: ignore[index]
            })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows_dir", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--plots-dir", type=Path, required=True)
    args = parser.parse_args()

    candidates = sorted(args.rows_dir.resolve().rglob("seed-*.json"))
    if len(candidates) != RUNS:
        raise SystemExit(
            "expected 30 corrected seed rows, found {0}".format(len(candidates))
        )
    by_seed: Dict[int, Mapping[str, Any]] = {}
    for path in candidates:
        row = json.loads(path.read_text(encoding="utf-8"))
        seed = int(row.get("seed", -1))
        if seed in by_seed:
            raise SystemExit("duplicate corrected row for seed {0}".format(seed))
        by_seed[seed] = row
    if sorted(by_seed) != list(range(1, RUNS + 1)):
        raise SystemExit("corrected seed ledger is incomplete")
    rows = [by_seed[seed] for seed in range(1, RUNS + 1)]
    report = evaluate(rows)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(rows, args.output_csv)
    _plot_results(rows, report, args.plots_dir)

    print(json.dumps({
        "claim_status": report["claim_status"],
        "h1_corrected": report["h1_corrected"],
        "h2_corrected": report["h2_corrected"],
        "h8_reset_ablation": report["h8_reset_ablation"],
        "official_test_file_sha256": report["protocol"]["official_test_file_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

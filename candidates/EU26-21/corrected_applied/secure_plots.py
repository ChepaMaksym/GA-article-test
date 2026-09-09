"""Scientific plots for the modern corrected applied profile."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import aggregate as base


def plot_results(
    rows: Sequence[Mapping[str, Any]],
    report: Mapping[str, Any],
    output_dir: Path,
) -> None:
    """Create paired and distribution plots without implying seed-time trends."""

    output_dir.mkdir(parents=True, exist_ok=True)
    old = np.asarray(base._series(rows, "old", base.PRIMARY_METRIC), dtype=float)
    h1 = np.asarray(
        base._series(rows, "hybrid_h1", base.PRIMARY_METRIC), dtype=float
    )
    reset = np.asarray(
        base._series(rows, "hybrid_reset", base.PRIMARY_METRIC), dtype=float
    )
    no_reset = np.asarray(
        base._series(rows, "hybrid_no_reset", base.PRIMARY_METRIC), dtype=float
    )
    seeds = np.arange(1, base.RUNS + 1)

    figure, axis = plt.subplots(figsize=(6.5, 5.5))
    axis.scatter(old, h1)
    lower = min(float(old.min()), float(h1.min()))
    upper = max(float(old.max()), float(h1.max()))
    axis.plot([lower, upper], [lower, upper], linestyle="--")
    axis.set_xlabel("OLD weighted balanced accuracy")
    axis.set_ylabel("Hybrid H1 weighted balanced accuracy")
    axis.set_title("Paired official-test quality: OLD vs Hybrid H1")
    figure.tight_layout()
    figure.savefig(
        output_dir / "paired_old_vs_hybrid_balanced_accuracy.png",
        dpi=180,
    )
    plt.close(figure)

    differences = (h1 - old) * 100.0
    figure, axis = plt.subplots(figsize=(8.0, 4.5))
    axis.scatter(seeds, differences)
    axis.axhline(
        -base.H1_MARGIN * 100.0,
        linestyle="--",
        label="-0.10 pp margin",
    )
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
    axis.set_title("Reset-specific paired Census ablation")
    figure.tight_layout()
    figure.savefig(output_dir / "paired_reset_vs_no_reset.png", dpi=180)
    plt.close(figure)

    old_counts = [base._selected_count(row["old"]) for row in rows]
    h1_counts = [base._selected_count(row["hybrid_h1"]) for row in rows]
    reset_counts = [
        base._selected_count(row["hybrid_reset"]) for row in rows
    ]
    no_reset_counts = [
        base._selected_count(row["hybrid_no_reset"]) for row in rows
    ]
    figure, axis = plt.subplots(figsize=(7.0, 4.8))
    axis.boxplot(
        [old_counts, h1_counts, reset_counts, no_reset_counts],
        tick_labels=["OLD", "Hybrid H1", "Reset", "No reset"],
    )
    axis.set_ylabel("Selected predictive features")
    axis.set_title("Feature subsets; instance weight excluded")
    figure.tight_layout()
    figure.savefig(output_dir / "feature_count_boxplot.png", dpi=180)
    plt.close(figure)

    metric_labels = ["Balanced acc.", "F1+", "MCC", "ROC-AUC", "PR-AUC"]
    metric_keys = [
        "balanced_accuracy",
        "f1_positive",
        "mcc",
        "roc_auc",
        "average_precision",
    ]
    algorithms = ["baseline", "old", "hybrid_h1"]
    x = np.arange(len(metric_keys))
    width = 0.24
    figure, axis = plt.subplots(figsize=(9.0, 5.0))
    for index, algorithm in enumerate(algorithms):
        medians = [
            float(
                report["metrics"][algorithm]["weighted"][metric]["median"]
            )
            for metric in metric_keys
        ]
        axis.bar(x + (index - 1) * width, medians, width, label=algorithm)
    axis.set_xticks(x, metric_labels)
    axis.set_ylabel("Weighted metric")
    axis.set_title("Official-test weighted metric profile")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_dir / "weighted_metric_medians.png", dpi=180)
    plt.close(figure)

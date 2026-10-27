"""Post hoc target93 review of saved histories; no new GA evaluations."""
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path
from statistics import fmean

from . import authority as a
from .review import PROFILES, TASKS, SEEDS, NAMES, COLORS, family_values, target_query, validate_rectangle

TARGETS = (93, 95, 99)


def target_stats(rows, target):
    a.ci_only()
    observations = [{**r, "first": target_query(r["record_events"], r["optimum"], target)} for r in rows]
    qvalues = sorted({0, 5000, *(r["first"] for r in observations if r["first"] is not None)})
    curve = [{"q": q, "fraction": fmean(family_values(observations,
        lambda r: int(r["first"] is not None and r["first"] <= q)).values())} for q in qvalues]
    return {"target_percent": target, "attained": sum(r["first"] is not None for r in observations),
        "not_attained": sum(r["first"] is None for r in observations), "denominator": len(rows),
        "restricted_mean_queries": fmean(family_values(observations, lambda r: 5000 if r["first"] is None else r["first"]).values()),
        "family_attainment_fraction": family_values(observations, lambda r: int(r["first"] is not None)),
        "curve": curve}


def validate_target_order(events, optimum):
    values = [target_query(events, optimum, t) for t in TARGETS]
    for lower, higher in zip(values, values[1:]):
        a.require(higher is None or (lower is not None and lower <= higher), "inconsistent target attainment order")
    return values


def execute(output):
    a.ci_only()
    with gzip.open(a.SOURCE / "compact_records.json.gz", "rt", encoding="utf-8") as stream:
        all_rows = json.load(stream)
    validate_rectangle(all_rows, TASKS, SEEDS, tuple(range(32)), a.SOURCE_SHA)
    rows = [r for r in all_rows if r["profile"] in PROFILES]
    del all_rows
    validate_rectangle(rows, TASKS, SEEDS, PROFILES, a.SOURCE_SHA)
    source = a.read(a.SOURCE / "series_summary.json")
    cells = []
    endpoints = []
    for row in rows:
        times = validate_target_order(row["record_events"], row["optimum"])
        endpoints.append({"task": row["task"], "family": row["family"], "seed": row["seed"], "profile": row["profile"],
                          "first_targets": dict(zip(map(str, TARGETS), times)), "final_gap_percent": row["final_gap_percent"]})
    for profile in PROFILES:
        subset = [r for r in rows if r["profile"] == profile]
        targets = {str(t): target_stats(subset, t) for t in TARGETS}
        historic = next(c for c in source["profile_cells"] if c["profile"] == profile and c["start"] == "bank")
        gap = fmean(family_values(subset, lambda r: r["final_gap_percent"]).values())
        a.require(math.isclose(gap, historic["mean_final_gap_percent"], rel_tol=0, abs_tol=1e-12), "historical gap changed")
        for t in ("95", "99"):
            a.require(targets[t]["attained"] == historic["targets"][t]["attained"] and
                      math.isclose(targets[t]["restricted_mean_queries"], historic["targets"][t]["restricted_mean_queries"],
                                   rel_tol=0, abs_tol=1e-9), "historical target endpoint changed")
        cells.append({"profile": profile, "name": NAMES[profile], "runs": len(subset),
                      "mean_final_gap_percent": gap, "targets": targets})
    summary = {"status": "COMPLETE_VERIFIED_TARGET93_REVIEW", "post_hoc_descriptive": True,
        "protocol": "GA-KNAPSACK-MUTATION-POPULATION-TARGET93-V1", "source_run_id": a.SOURCE_RUN,
        "source_sha": a.SOURCE_SHA, "input_hashes": a.INPUT_HASHES, "reviewed_saved_runs": len(rows),
        "families": 10, "cells": cells, "targets": list(TARGETS), "new_search_evaluations": 0,
        "new_primary_tests": 0, "bootstrap_resamples": 0, "historical_endpoints_unchanged": True,
        "time_definition": "first attainment at q in [0,5000]; nonattainment remains None, restricted mean uses 5000",
        "weighting": "repeat -> task -> family; equal weight for ten index families"}
    a.write(Path(output) / "targets_summary.json", summary)
    a.write(Path(output) / "target_endpoints.json", endpoints)
    return summary


def render(summary, directory):
    a.ci_only()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    a.require(summary["status"] == "COMPLETE_VERIFIED_TARGET93_REVIEW", "unverified target93 source")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "savefig.dpi": 180})
    fig, ax = plt.subplots(figsize=(9.2, 4.3), constrained_layout=True)
    for cell in summary["cells"]:
        stats = cell["targets"]["93"]
        curve = stats["curve"]
        ax.step([p["q"] for p in curve], [100*p["fraction"] for p in curve], where="post", linewidth=1.8,
            color=COLORS[cell["profile"]], label=f"{cell['name']}: {stats['attained']}/900")
    ax.set(xlim=(0, 5000), ylim=(0, 100), xlabel="Нові оцінювання", ylabel="Досягли 93% OPT, % запусків")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=.2)
    ax.legend(fontsize=9, loc="lower right")
    for ext in (".png", ".svg"):
        fig.savefig(directory / ("07_target93"+ext), bbox_inches="tight")
    plt.close(fig)
    return {"file": "07_target93.png", "xlabel": "Нові оцінювання", "ylabel": "Досягли 93% OPT, % запусків",
            "xlim": [0, 5000], "ylim": [0, 100], "inside_title": "", "post_hoc_descriptive": True,
            "caption": "Досягнення 93% OPT, тобто відставання не більше 7%. По900 запусків на варіант; недосягнення залишено у знаменнику. Додатковий поріг обрано після перегляду результатів."}

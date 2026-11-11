"""Render existing aggregates in CI without search, solvers or new statistics."""
import argparse
import csv
import json
import os
from pathlib import Path

from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha, write_json

HERE = Path(__file__).resolve().parent


def main():
    require(os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test"
            and os.environ.get("GITHUB_REF") == "refs/heads/research/mutation-grid100-report-20261111"
            and os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "Unregistered report-only execution")
    seal = read_json(HERE / "source_manifest.json")
    root = HERE.parents[2]
    for entry in seal["files"]:
        require(sha(root / entry["path"]) == entry["sha256"], "Frozen presentation source differs")
    authority = read_json(HERE / "authorization.json")
    require(authority.get("status") == "WITHIN_APPROVED_TUNING_ALLOWANCE"
            and authority["completed_tuning_runner_minutes"] + authority["report_timeout_minutes"]
            <= authority["total_runner_minutes_authorized"]
            and authority["completed_tuning_artifact_bytes"] + authority["report_output_cap_bytes"]
            <= authority["total_artifact_bytes_authorized"], "Report exceeds the approved tuning allowance")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), "Preserve existing report figures")
    selection = read_json(args.inputs / "selection.json")
    require(selection.get("status") == "SELECTED_BEFORE_VALIDATION"
            and selection.get("independent_validation_started") is False
            and sha(args.inputs / "validated_records.json.gz") == selection["source_records_sha256"],
            "Frozen tuning selection or source records differ")
    with (args.inputs / "all-configurations.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))
    values = {(int(r["mu"]), int(r["pc_percentage"]), int(r["mutation_basis_points"])): r for r in rows}
    old = {(mu, pc, 100) for mu in (10, 15, 20, 25) for pc in (70, 80, 90, 100)}
    mutation = {(mu, 100, bp) for mu in (10, 15, 20) for bp in (25, 50, 75, 100, 150, 200)}
    require(len(rows) == len(values) == 31 and set(values) == old | mutation
            and all(int(r["runs"]) == 90 for r in rows), "Aggregate inventory differs")
    chosen = {role: tuple(selection["selections"][role][k] for k in ("mu", "pc_percentage", "mutation_basis_points"))
              for role in ("quality", "speed")}
    require(all(c in values for c in chosen.values()), "Selected aggregate is absent")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    args.out.mkdir(parents=True)
    rates = (25, 50, 75, 100, 150, 200)
    all_gaps = [float(values[c][f"mean_gap_{q}_percent"]) for c in mutation for q in (50000, 100000)]
    low, high = min(all_gaps), max(all_gaps)
    for metric, name, label in (
        ("mean_gap_50000_percent", "mutation-gap-50000", "Середнє відставання, %"),
        ("mean_gap_100000_percent", "mutation-gap-100000", "Середнє відставання, %"),
        ("mean_restricted_t93", "mutation-time93", "Оцінювання до 93% OPT"),
    ):
        matrix = np.array([[float(values[(mu, 100, bp)][metric]) for bp in rates] for mu in (10, 15, 20)])
        fig, ax = plt.subplots(figsize=(10, 4.8), layout="constrained")
        image = ax.imshow(matrix, cmap="YlGnBu", aspect="auto",
                          vmin=low if "gap" in metric else None, vmax=high if "gap" in metric else None)
        bottom, top = image.get_clim()
        for i in range(3):
            for j in range(6):
                value = matrix[i, j]
                color = "white" if top > bottom and (value - bottom) / (top - bottom) > .57 else "#132238"
                text = f"{value:.3f}" if "gap" in metric else f"{value:.1f}"
                ax.text(j, i, text.replace(".", ","), ha="center", va="center", color=color, fontsize=12)
        ax.set_xticks(range(6), ("0,25", "0,5", "0,75", "1", "1,5", "2"))
        ax.set_yticks(range(3), ("10", "15", "20"))
        ax.set_xlabel("Імовірність мутації біта, %")
        ax.set_ylabel("Популяція, особин")
        fig.colorbar(image, ax=ax, label=label)
        for extension in ("png", "svg"):
            fig.savefig(args.out / f"{name}.{extension}", dpi=200)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 5.5), layout="constrained")
    for group, marker, color, label in (
        (old, "o", "#4774a5", "Мутація 1%"),
        (mutation - old, "s", "#ba522d", "Інші значення мутації"),
    ):
        ax.scatter([float(values[c]["mean_restricted_t93"]) for c in sorted(group)],
                   [float(values[c]["mean_gap_100000_percent"]) for c in sorted(group)],
                   marker=marker, color=color, label=label, s=35)
    for role, color, symbol, label, text_at in (
        ("quality", "#2b753b", "*", "Вибір за кінцевою якістю", (1600, .65)),
        ("speed", "#734b9f", "D", "Вибір за швидкістю до 93%", (1600, .4)),
    ):
        config = chosen[role]
        row = values[config]
        xy = (float(row["mean_restricted_t93"]), float(row["mean_gap_100000_percent"]))
        ax.scatter(*xy, marker=symbol, color=color, edgecolors="black", linewidths=.5, s=120, label=label, zorder=5)
        description = f"{config[0]} особин; схрещування {config[1]}%; мутація {config[2] / 100:g}%"
        ax.annotate(description, xy=xy, xytext=text_at,
                    arrowprops={"arrowstyle": "->", "color": color}, color=color, fontsize=9,
                    bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": color, "alpha": .95})
    ax.set_xlabel("Середнє число оцінювань до 93% OPT")
    ax.set_ylabel("Кінцеве середнє відставання, %")
    ax.grid(alpha=.2)
    ax.legend(loc="upper left", fontsize=9)
    for extension in ("png", "svg"):
        fig.savefig(args.out / f"speed-and-quality.{extension}", dpi=200)
    plt.close(fig)
    profiles = {"quality": values[chosen["quality"]], "speed": values[chosen["speed"]],
                "control15": values[(15, 100, 100)], "control10": values[(10, 90, 100)],
                "control20": values[(20, 90, 100)]}
    write_json(args.out / "report-data.json", {"schema": "mutation-tuning-presentation-v1",
               "upstream_run_id": 42994492163, "selection": selection, "profiles": profiles,
               "aggregates_sha256": sha(args.inputs / "all-configurations.csv"),
               "new_search_runs": 0, "new_statistical_tests": 0})
    require(sum(p.stat().st_size for p in args.out.rglob("*") if p.is_file()) < 16 * 1024**2,
            "Report figure output exceeds its resource cap")
    print("Rendered four corrected figures from frozen aggregates; no new search or statistical tests.")


if __name__ == "__main__":
    main()

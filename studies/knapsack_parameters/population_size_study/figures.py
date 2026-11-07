"""CI-only theoretical curves; no empirical GA outcomes are fabricated."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from .mathematics import (generation_accounting, minimum_representation_population,
                          population_domain, representation_probability)
from .io_utils import write_manifest


def mathematical_figures(output):
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("Scientific figures are built only in GitHub Actions")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Use a new output directory")
    representation_rows, accounting_rows = [], []
    colors = ("#1764a5", "#c04b23", "#2b8a57")
    maximum = max(minimum_representation_population(n, "0.9999") for n in (100, 200, 500)) + 2
    figure, axis = plt.subplots(figsize=(7.5, 4.5), layout="constrained")
    for n, color in zip((100, 200, 500), colors):
        values = []
        for mu in range(2, maximum + 1):
            probability = representation_probability(n, mu)
            representation_rows.append({"n": n, "mu": mu, "probability": probability})
            values.append(100 * probability)
        axis.plot(range(2, maximum + 1), values, color=color, label=f"{n} предметів")
    axis.set(xlabel="Початкова популяція, особин", ylabel="Представлено обидва значення бітів, %",
             ylim=(0, 100), xlim=(2, maximum))
    axis.legend()
    axis.grid(alpha=.2)
    for suffix in ("png", "svg"):
        figure.savefig(output / f"initial_representation.{suffix}", dpi=180)
    plt.close(figure)
    figure, axis = plt.subplots(figsize=(7.5, 4.5), layout="constrained")
    for total, color in zip((5000, 10000, 20000, 50000), (*colors, "#7954a1")):
        limit = population_domain(total)[1]
        populations = sorted({2, limit, *map(int, np.geomspace(2, limit, 300))})
        generations = []
        for mu in populations:
            row = generation_accounting(mu, total)
            accounting_rows.append({"mu": mu, **row})
            generations.append(row["complete_generations"])
        axis.plot(populations, generations, color=color, label=f"{total:,} оцінювань".replace(",", " "))
    axis.set(xlabel="Початкова популяція, особин", ylabel="Завершені покоління", xscale="log", yscale="log")
    axis.legend()
    axis.grid(alpha=.2)
    for suffix in ("png", "svg"):
        figure.savefig(output / f"generation_accounting.{suffix}", dpi=180)
    plt.close(figure)
    for filename, rows in (("representation.csv", representation_rows), ("generation_accounting.csv", accounting_rows)):
        with (output / filename).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "figure_notes.json").write_text(json.dumps({
        "kind": "theoretical_not_empirical", "ga_runs": 0,
        "representation_assumptions": "One empty mask; independent fair bits in all other masks",
        "rounding": "A floating-point value close to one is not a certainty guarantee",
        "representation_plot_limit": "Visual range ends after the 0.9999 representation level; not a recommended population",
        "generation_assumptions": "Constant population, one elite, initial evaluations included"}, indent=2), encoding="utf-8")
    write_manifest(output)
    return {"status": "THEORETICAL_CURVES_VERIFIED_BY_SOFTWARE_FIXTURES", "ga_runs": 0,
            "figures": 2, "representation_rows": len(representation_rows), "accounting_rows": len(accounting_rows)}

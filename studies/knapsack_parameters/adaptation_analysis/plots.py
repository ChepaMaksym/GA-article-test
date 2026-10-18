"""Prospective CI-only, question-led figures for verified adaptation summaries.

Constant data are explicit tables, absent data are NA/NOT_RUN, and deferred
lambda is labelled BLOCKED rather than drawn as measured zero performance.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .analysis import DEFERRED, METHODS, _ci_only, _require


LABELS = {"classical": "Класичний", "adaptive_mutation": "Адапт. мутація",
          "adaptive_crossover": "Адапт. схрещування", "unbalanced_gap": "Gap без пам'яті",
          "balanced_gap": "Gap із пам'яттю", "lambda_fixed": "λ сталий — BLOCKED",
          "lambda_own": "λ власний — BLOCKED"}
COLORS = dict(zip(METHODS, ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"), strict=True))


def _panel(axis, values, rows, columns, title, *, vmin, vmax, counts=None, percent=False):
    """Draw a shared-scale matrix or an explicit constant-value table."""
    data = np.asarray([[np.nan if value is None else value for value in row] for row in values], dtype=float)
    finite = data[np.isfinite(data)]
    axis.set_title(title, fontsize=11)
    if not finite.size:
        axis.axis("off")
        axis.text(0.5, 0.5, "NA — немає оцінених даних", ha="center", va="center", transform=axis.transAxes)
        return None
    labels = []
    for i, line in enumerate(data):
        text_line = []
        for j, value in enumerate(line):
            if not np.isfinite(value):
                text = "BLOCKED" if columns[j] in DEFERRED else "NA"
            else:
                text = f"{value:.2f}{'%' if percent else ''}"
                if counts is not None:
                    text += f"\nN={counts[i][j]}"
            text_line.append(text)
        labels.append(text_line)
    if np.all(finite == finite[0]):
        axis.axis("off")
        table = axis.table(cellText=labels, rowLabels=rows,
                           colLabels=[LABELS.get(column, str(column)) for column in columns],
                           loc="center", cellLoc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.8)
        axis.text(0.5, 0.02, "Сталі значення: показано таблицю, а не порожню карту", ha="center",
                  va="bottom", fontsize=8, transform=axis.transAxes)
        return None
    cmap = __import__("matplotlib").colormaps["viridis"].copy()
    cmap.set_bad("#eeeeee")
    mesh = axis.imshow(np.ma.masked_invalid(data), aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
    axis.set_xticks(range(len(columns)), [LABELS.get(column, str(column)) for column in columns], rotation=30, ha="right", fontsize=8)
    axis.set_yticks(range(len(rows)), rows, fontsize=9)
    for i, line in enumerate(labels):
        for j, text in enumerate(line):
            value = data[i, j]
            midpoint = (vmin + vmax) / 2
            axis.text(j, i, text, ha="center", va="center", fontsize=7,
                      color="white" if np.isfinite(value) and value < midpoint else "black")
    return mesh


def render_report(summary, output):
    """Render only complete, verified pilot/main data; never launch analysis."""
    _ci_only()
    _require(type(summary) is dict and summary.get("schema") == "ga-adaptation-series-summary-v1", "unknown summary schema")
    if summary.get("status") not in ("COMPLETE_VERIFIED_MAIN", "COMPLETE_VERIFIED_PILOT"):
        return {"status": "NOT_RENDERED", "reason": summary.get("status", "UNKNOWN"), "files": []}
    _require(bool(summary.get("family_cells")) and bool(summary.get("method_summaries")), "complete summary has no data")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    destination = Path(output).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    names = ["01_family_gap.png", "02_equal_budget_targets.png", "03_controller_activity.png"]
    if summary.get("example_rows"):
        names.append("04_prespecified_trajectory.png")
    _require(not any((destination / name).exists() for name in names), "refusing to overwrite a scientific figure")
    figures = []
    cells = summary["family_cells"]
    lookup = {(cell["start"], cell["family"], cell["method"]): cell for cell in cells}
    families = sorted({cell["family"] for cell in cells})
    columns = list(METHODS) + list(DEFERRED)
    all_gaps = [cell["mean_final_gap_percent"] for cell in cells]
    shared_gap_max = max(all_gaps) if max(all_gaps) > 0 else 1
    fig, axes = plt.subplots(1, 2, figsize=(17, max(5, len(families) * 0.48)), constrained_layout=True)
    for axis, start in zip(axes, ("bank", "cloned"), strict=True):
        values, counts = [], []
        for family in families:
            values.append([lookup.get((start, family, method), {}).get("mean_final_gap_percent") for method in columns])
            counts.append([lookup.get((start, family, method), {}).get("runs", 0) for method in columns])
        mesh = _panel(axis, values, families, columns,
                      f"Який кінцевий результат? Початок: {start}",
                      vmin=0, vmax=shared_gap_max, counts=counts, percent=True)
        if mesh is not None:
            fig.colorbar(mesh, ax=axis, label="Відставання від OPT, %; менше — краще")
    fig.suptitle("Сімейства мають рівну вагу; λ заблокований, а не оцінений нулем")
    fig.savefig(destination / names[0], dpi=170)
    plt.close(fig)
    figures.append(names[0])

    methods = { (row["start"], row["method"]): row for row in summary["method_summaries"] }
    fig, axes = plt.subplots(1, 2, figsize=(14, 7), constrained_layout=True)
    queries = [0, 1000, 2500, 5000]
    for axis, start in zip(axes, ("bank", "cloned"), strict=True):
        measure = "attainment_99" if start == "bank" else "escape_frequency"
        matrix = [[100 * methods[(start, method)]["observations"][i][measure] for i in range(4)] for method in METHODS]
        counts = [[methods[(start, method)]["runs"]] * 4 for method in METHODS]
        mesh = _panel(axis, matrix, [LABELS[method] for method in METHODS], [str(query) for query in queries],
                      "Як швидко досягаємо 99% OPT?" if start == "bank" else "Як швидко знаходимо кращий за центр набір?",
                      vmin=0, vmax=100, counts=counts, percent=True)
        axis.set_xlabel("Нові оцінювання; початок у точці 0")
        if mesh is not None:
            fig.colorbar(mesh, ax=axis, label="Сімейно-зважена частка, %")
    fig.suptitle("Невиходи залишаються в знаменнику; 99% OPT не означає точного оптимуму")
    fig.savefig(destination / names[1], dpi=170)
    plt.close(fig)
    figures.append(names[1])

    activities = (("adaptive_mutation", "mean_p_m", "Мутація p_m"),
                  ("adaptive_crossover", "mean_p_c", "Схрещування p_c"),
                  ("balanced_gap", "memory_switch_fraction", "Вибори, змінені пам'яттю"))
    fig, axes = plt.subplots(2, 3, figsize=(18, max(8, len(families) * 0.65)), constrained_layout=True)
    for column, (method, key, label) in enumerate(activities):
        observed = [100 * window[key] for cell in cells if cell["method"] == method
                    for window in cell["windows"] if window[key] is not None]
        low, high = (min(observed), max(observed)) if observed else (0, 1)
        if low == high:
            high = low + 1
        for row_index, start in enumerate(("bank", "cloned")):
            matrix = []
            counts = []
            for family in families:
                cell = lookup.get((start, family, method))
                matrix.append([100 * window[key] if window[key] is not None else None for window in cell["windows"]]
                              if cell else [None] * 10)
                counts.append([500 * cell["runs"]] * 10 if cell else [0] * 10)
            axis = axes[row_index, column]
            mesh = _panel(axis, matrix, families, [f"{i + 1}" for i in range(10)],
                          f"{label}: {start}", vmin=low, vmax=high, percent=True, counts=counts)
            axis.set_xlabel("Вікно по 500 нових оцінювань")
            if mesh is not None:
                fig.colorbar(mesh, ax=axis, label="%")
    fig.suptitle("Що фактично змінювалося? N — нові запити; пам'ять — післяпошукова діагностика, не доказ якості")
    fig.savefig(destination / names[2], dpi=170)
    plt.close(fig)
    figures.append(names[2])

    if summary.get("example_rows"):
        fig, axes = plt.subplots(2, 3, figsize=(17, 9), constrained_layout=True, sharex="col", sharey="col")
        for row_index, start in enumerate(("bank", "cloned")):
            for run in summary["example_rows"]:
                if run["start"] != start:
                    continue
                label = LABELS[run["method"]]
                record = run["record_events"]
                x = [event["query"] for event in record] + [run["budget"]]
                y = [100 * event["profit"] / run["optimum"] for event in record] + [100 * run["final_best_profit"] / run["optimum"]]
                axes[row_index, 0].step(x, y, where="post", label=label, color=COLORS[run["method"]])
                population = run["population_trace"]
                axes[row_index, 1].plot([point["query"] for point in population],
                                        [100 * point["mean_feasible_profit"] / run["optimum"]
                                         if point["mean_feasible_profit"] is not None else np.nan for point in population], label=label, color=COLORS[run["method"]])
                axes[row_index, 2].plot([point["query"] for point in population],
                                        [point["normalized_hamming"] for point in population], label=label, color=COLORS[run["method"]])
            for column, title in enumerate(("Рекорд, % OPT", "Середня допустима цінність, % OPT", "Різноманітність: нормована відстань")):
                axis = axes[row_index, column]
                axis.set_title(f"{start}: {title}")
                axis.set_xlabel("Нові оцінювання")
                axis.grid(alpha=0.25)
        axes[0, 0].legend(fontsize=8)
        fig.suptitle("Наперед визначений UC-s000, seed 85001; різні показники не змішуються")
        fig.savefig(destination / names[3], dpi=170)
        plt.close(fig)
        figures.append(names[3])
    return {"status": "RENDERED_VERIFIED_DATA", "source_status": summary["status"], "files": figures,
            "deferred": {method: "BLOCKED_LAMBDA_REPLICATION" for method in DEFERRED}}

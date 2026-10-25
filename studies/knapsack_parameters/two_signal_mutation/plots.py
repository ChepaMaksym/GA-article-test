"""Five question-led, title-free figures from verified two-signal summaries.

No search, replay or bootstrap is performed by the presentation layer.  Empty
operator strata remain numerical counts, never measured zero probabilities.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .analysis import METHODS, DISTANCE_LABELS, _ci_only, _require


LABELS = {"fixed": "Стала мутація", "adaptive_mutation": "Сигнал застою", "two_signal": "Два сигнали"}
COLORS = {"fixed": "#222222", "adaptive_mutation": "#0072B2", "two_signal": "#D55E00"}
STYLES = {"fixed": "-", "adaptive_mutation": "--", "two_signal": "-."}


def _save(plt, figure, path):
    _require(not path.exists(), "refusing to overwrite an existing figure")
    _require(not figure._suptitle or not figure._suptitle.get_text(), "figure titles are prohibited")
    _require(all(not axis.get_title() for axis in figure.axes), "panel titles are prohibited")
    figure.savefig(path, dpi=200)
    plt.close(figure)
    return path.name


def _style(axis):
    axis.set_xlim(0, 5000)
    axis.set_xlabel("Нові оцінювання")
    axis.grid(alpha=.25, linewidth=.6)
    axis.set_axisbelow(True)


def _heatmap(fig, axis, values, rows, columns, label, *, maximum=100, reverse=False):
    data = np.asarray([[np.nan if value is None else value for value in line] for line in values], dtype=float)
    finite = data[np.isfinite(data)]
    cell_text = [["н/в" if value is None else f"{value:.2f}".replace(".", ",") for value in line] for line in values]
    if not len(finite) or np.all(finite == finite[0]):
        axis.set_axis_off()
        table = axis.table(cellText=cell_text, rowLabels=rows, colLabels=columns,
                           loc="center", cellLoc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.65)
        # Metric is an axis label, not a decorative image title.
        axis.set_xlabel(label)
        axis.xaxis.label.set_visible(True)
        return
    cmap = __import__("matplotlib").colormaps["viridis_r" if reverse else "viridis"].copy()
    cmap.set_bad("#eeeeee")
    image = axis.imshow(np.ma.masked_invalid(data), aspect="auto", cmap=cmap, vmin=0, vmax=maximum)
    axis.set_xticks(range(len(columns)), columns, rotation=25, ha="right", fontsize=9)
    axis.set_yticks(range(len(rows)), rows, fontsize=9)
    for i, line in enumerate(cell_text):
        for j, text in enumerate(line):
            axis.text(j, i, text, ha="center", va="center", fontsize=8,
                      bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none", "pad": 1.1})
    fig.colorbar(image, ax=axis, label=label, shrink=.86)


def render_report(summary, output):
    """Render the five registered topics, always retaining the fixed example."""
    _ci_only()
    _require(type(summary) is dict and summary.get("schema") == "ga-two-signal-series-summary-v1" and
             summary.get("status") in ("COMPLETE_VERIFIED_MAIN", "COMPLETE_VERIFIED_PILOT"),
             "only complete independently verified summaries may be plotted")
    _require(summary.get("runs") == (2700 if summary["scope"] == "main" else 24), "wrong series size")
    example = summary["prespecified_example"]
    expected_task, expected_seed = ("UC-s010", 94001) if summary["scope"] == "main" else ("UC-s000", 93999)
    _require(example["task"] == expected_task and example["seed"] == expected_seed and example["start"] == "bank" and
             {row["method"] for row in example["rows"]} == set(METHODS), "the fixed example was replaced")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "figure.facecolor": "white", "axes.facecolor": "white", "pdf.fonttype": 42})
    destination = Path(output).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    planned = ("01_target_attainment.png", "02_population_dynamics.png", "03_mutation_signals.png",
               "04_crossover_productivity.png", "05_problem_structure.png")
    _require(not any((destination / name).exists() for name in planned), "refusing to overwrite scientific figures")
    files, tables = [], []

    # Only the bank start is in the random-search comparison; cloned technical
    # controls remain separate numerical rows in the pilot summary.
    indexed = {row["method"]: row for row in summary["method_summaries"] if row["start"] == "bank"}
    _require(set(indexed) == set(METHODS), "missing random-start method summary")
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.6), layout="constrained")
    for axis, target in zip(axes, (95, 99), strict=True):
        for method in METHODS:
            points = indexed[method]["targets"][str(target)]["curve"]
            axis.step([point["q"] for point in points], [100 * point["fraction"] for point in points],
                      where="post", label=LABELS[method], color=COLORS[method], linestyle=STYLES[method], linewidth=1.8)
        axis.set_ylabel(f"Досягнуто {target}% OPT, % запусків")
        axis.set_ylim(0, 100)
        _style(axis)
        axis.legend(fontsize=9)
    files.append(_save(plt, fig, destination / planned[0]))

    examples = {row["method"]: row for row in example["rows"]}
    fig, axes = plt.subplots(4, 1, figsize=(9.2, 10.8), sharex=True, layout="constrained")
    for method in METHODS:
        row, color, style = examples[method], COLORS[method], STYLES[method]
        record = row["record_events"]
        x, y = [point["q"] for point in record], [100 * point["profit"] / row["optimum"] for point in record]
        if x[-1] < 5000:
            x, y = x + [5000], y + [y[-1]]
        axes[0].step(x, y, where="post", color=color, linestyle=style, label=LABELS[method], linewidth=1.7)
        population = [point for point in row["population_trace"] if point["complete"]]
        # Extend the last committed state through the terminal prefix without
        # manufacturing a new committed population at q=5000.
        population = population + [{**population[-1], "q": 5000}]
        for axis, key, multiple in ((axes[1], "mean_feasible_profit", 100 / row["optimum"]),
                                   (axes[2], "unique_fraction", 100),
                                   (axes[3], "mean_pairwise_hamming", 1)):
            axis.step([point["q"] for point in population],
                      [None if point[key] is None else point[key] * multiple for point in population],
                      where="post", color=color, linestyle=style, label=LABELS[method], linewidth=1.7)
    for axis, label in zip(axes, ("Рекорд, % OPT", "Середня допустима\nцінність, % OPT",
                                  "Унікальні маски, %", "Попарна відстань, біти"), strict=True):
        axis.set_ylabel(label)
        _style(axis)
        axis.legend(fontsize=8)
    axes[2].set_ylim(0, 100)
    files.append(_save(plt, fig, destination / planned[1]))

    fig, axes = plt.subplots(3, 1, figsize=(9.2, 8.7), sharex=True, layout="constrained")
    event_labels = {"STAGNATION_DOUBLE": "Дозволене підвищення", "GATE_DENIED": "Відхилене підвищення"}
    for method in METHODS:
        row, color, style = examples[method], COLORS[method], STYLES[method]
        trace = row["generation_trace"]
        # p_m is displayed at the queries which actually used it.  p_m_next is
        # never retroactively attached to the generation which calculated it.
        axes[0].step([0] + [point["start_q"] for point in trace] + [5000],
                     [1.0] + [100 * point["p_m"] for point in trace] + [100 * trace[-1]["p_m"]],
                     where="post", color=color, linestyle=style, label=LABELS[method], linewidth=1.7)
        axes[1].plot([point["q"] for point in trace if point["complete"]],
                     [point["mean_novelty"] for point in trace if point["complete"]],
                     color=color, linestyle=style, label=LABELS[method], linewidth=1.5)
        method_index = METHODS.index(method)
        for event, marker in (("STAGNATION_DOUBLE", "^"), ("GATE_DENIED", "x")):
            points = [point for point in trace if point["complete"] and point["controller_event"] == event]
            if points:
                axes[2].scatter([point["q"] for point in points], [method_index] * len(points),
                                 marker=marker, color=color, s=30,
                                 label=event_labels[event] if method == "two_signal" else None)
    axes[0].set_ylabel("Мутація біта, %")
    axes[0].set_yticks((1, 2, 4, 8))
    axes[0].set_ylim(.5, 8.5)
    axes[1].set_ylabel("Середній сигнал r(d)")
    axes[1].set_ylim(-.03, 1.03)
    axes[1].axhline(.5, color="#777777", linewidth=1, linestyle=":", label="Поріг 0,5")
    axes[2].set_yticks(range(3), [LABELS[method] for method in METHODS])
    axes[2].set_ylim(-.5, 2.5)
    axes[2].set_ylabel("Подія керування")
    for axis in axes:
        _style(axis)
        if axis.get_legend_handles_labels()[0]:
            axis.legend(fontsize=8)
    event_counts = [{"method": method, "event": event,
                     "count": sum(point["controller_event"] == event for point in examples[method]["generation_trace"]
                                  if point["complete"])}
                    for method in METHODS for event in event_labels]
    if not any(row["count"] for row in event_counts):
        axes[2].set_axis_off()
        counts = {(row["method"], row["event"]): row["count"] for row in event_counts}
        table = axes[2].table(cellText=[[counts[(method, event)] for event in event_labels] for method in METHODS],
                              rowLabels=[LABELS[method] for method in METHODS],
                              colLabels=list(event_labels.values()), loc="center", cellLoc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.6)
    tables.append({"name": "example_controller_event_counts", "rows": event_counts})
    files.append(_save(plt, fig, destination / planned[2]))

    operator_cells = [cell for cell in summary["operator_cells"] if cell["start"] == "bank"]
    operators = {(cell["method"], cell["distance_bin"]): cell for cell in operator_cells}
    _require(len(operators) == 3 * len(DISTANCE_LABELS), "missing operator strata")
    empty = [cell for cell in operator_cells if cell["crossed"] == 0]
    if empty:
        tables.append({"name": "empty_crossover_strata", "rows": empty})
    if any(cell["crossed"] for cell in operator_cells):
        fig, axes = plt.subplots(3, 1, figsize=(10.6, 9.8), layout="constrained")
        for axis, key, label in ((axes[0], "novel_fraction", "Нові щодо обох батьків, % схрещувань"),
                                 (axes[1], "feasible_fraction", "Допустимі, % схрещувань"),
                                 (axes[2], "better_both_fraction", "Допустимі кращі за обох батьків, % схрещувань")):
            values = [[None if operators[(method, distance)][key] is None else 100 * operators[(method, distance)][key]
                       for distance in DISTANCE_LABELS] for method in METHODS]
            _heatmap(fig, axis, values, [LABELS[method] for method in METHODS], list(DISTANCE_LABELS), label)
            axis.set_xlabel("Відстань між батьками, біти")
        files.append(_save(plt, fig, destination / planned[3]))
    else:
        tables.append({"name": "crossover_productivity_no_applied_crossovers", "rows": operator_cells})

    types = {(cell["class_label"], cell["method"]): cell for cell in summary["type_cells"] if cell["start"] == "bank"}
    _require(len(types) == 9, "missing task-type comparison")
    fig, axes = plt.subplots(3, 1, figsize=(9.6, 10.2), layout="constrained")
    for axis, key, label, multiplier, reverse in (
        (axes[0], "mean_final_gap_percent", "Кінцеве відставання від OPT, %", 1, True),
        (axes[1], "mean_final_capacity_fraction", "Заповнення місткості рекордом, %", 100, False),
        (axes[2], "mean_infeasible_fraction", "Недопустимі кандидати, %", 100, True)):
        values = [[types[(kind, method)][key] * multiplier for method in METHODS] for kind in ("UC", "WC", "SC")]
        maximum = max(max(line) for line in values) if multiplier == 1 else 100
        _heatmap(fig, axis, values, ["Некорельовані", "Слабко корельовані", "Сильно корельовані"],
                 [LABELS[method] for method in METHODS], label, maximum=max(maximum, 1e-12), reverse=reverse)
        axis.set_ylabel("Тип задачі")
    files.append(_save(plt, fig, destination / planned[4]))
    return {"status": "RENDERED", "files": files, "tables": tables,
            "figure_start": "bank", "prespecified_task": expected_task, "prespecified_seed": expected_seed,
            "technical_pilot_only": summary["scope"] == "pilot",
            "new_search_evaluations": 0, "new_bootstrap_replicates": 0}

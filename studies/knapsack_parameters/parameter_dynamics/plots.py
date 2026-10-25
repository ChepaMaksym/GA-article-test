"""Title-free scientific figures from complete, independently verified records."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .analysis import FIELDS, PRIMARY, ci_only, require

LABELS = {"p_m": "Мутація біта, %", "p_c": "Схрещування, %", "target_mu": "Цільова популяція, осіб",
          "tournament_size": "Турнір, осіб", "elite_count": "Еліта, осіб"}
SHORT = ("Мутація", "Схрещування", "Популяція", "Турнір", "Елітизм")
COLORS = {0: "#1765a0", 31: "#b54620"}
NAMES = {0: "Сталі параметри", 31: "П’ять адаптацій"}


def finish(axis, xlabel=None, ylabel=None):
    if xlabel:
        axis.set_xlabel(xlabel)
    if ylabel:
        axis.set_ylabel(ylabel)
    axis.grid(alpha=.2)
    axis.spines[["top", "right"]].set_visible(False)


def render_report(summary, directory):
    ci_only()
    require(summary.get("status") in ("COMPLETE_VERIFIED_PILOT", "COMPLETE_VERIFIED_MAIN"), "Incomplete figure source")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 10,
                         "savefig.dpi": 180, "axes.formatter.useoffset": False})
    figures, tables = [], []

    def save(fig, name, caption):
        require(all(not ax.get_title() for ax in fig.axes), "Inside-figure headings are forbidden")
        fig.savefig(directory / name, bbox_inches="tight")
        plt.close(fig)
        figures.append({"number": len(figures) + 1, "file": name, "caption": caption})

    examples = sorted(summary["prespecified_examples"], key=lambda r: r["profile"])
    fig, axes = plt.subplots(5, 1, figsize=(8, 10), sharex=True, constrained_layout=True)
    for row in examples:
        generations = row["example_trace"]["generations"]
        x = [gen["start_q"] - 1 for gen in generations] + [5000]
        for field, ax in zip(FIELDS, axes, strict=True):
            scale = 100 if field in ("p_m", "p_c") else 1
            y = [scale * gen["parameters_before"][field] for gen in generations]
            ax.step(x, y + [y[-1]], where="post", color=COLORS[row["profile"]], label=NAMES[row["profile"]])
            if field == "target_mu" and row["profile"] == 31:
                actual = [gen["actual_parent_mu"] for gen in generations]
                ax.step(x, actual + [actual[-1]], where="post", color="#444444", linestyle=":", label="Фактична батьківська популяція")
    for field, ax in zip(FIELDS, axes, strict=True):
        finish(ax, ylabel=LABELS[field])
    axes[0].legend(loc="best")
    axes[2].legend(loc="best", fontsize=8)
    finish(axes[-1], "Нові оцінювання")
    save(fig, "01_parameters.png", "Застосовані параметри за кількістю нових оцінювань у наперед визначеному прикладі. Цільовий і фактичний розміри популяції показано окремо.")

    fig, axes = plt.subplots(4, 1, figsize=(8, 9), sharex=True, constrained_layout=True)
    for row in examples:
        profile, optimum = row["profile"], row["optimum"]
        events = row["record_events"]
        axes[0].step([e["q"] for e in events] + [5000], [100 * e["profit"] / optimum for e in events] +
                     [100 * events[-1]["profit"] / optimum], where="post", color=COLORS[profile], label=NAMES[profile])
        points = [p for p in row["example_trace"]["population"] if p["complete"]]
        for ax, field, scale in ((axes[1], "mean_feasible_profit", 100 / optimum),
                                 (axes[2], "unique_fraction", 100), (axes[3], "mean_pairwise_hamming", 1)):
            y = [None if p[field] is None else p[field] * scale for p in points]
            ax.step([p["q"] for p in points] + [5000], y + [y[-1]], where="post", color=COLORS[profile])
    for ax, label in zip(axes, ("Рекорд, % OPT", "Середня допустима\nцінність, % OPT", "Унікальні маски, %", "Середня відстань, бітів"), strict=True):
        finish(ax, ylabel=label)
    axes[0].legend()
    finish(axes[-1], "Нові оцінювання")
    save(fig, "02_population.png", "Рекорд, середня допустима цінність і два показники різноманітності. Популяційні показники стосуються лише завершених поколінь.")

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.7), sharey=True, constrained_layout=True)
    for target, ax in zip(("95", "99"), axes, strict=True):
        for row in summary["profile_cells"]:
            if row["start"] != "bank" or row["profile"] not in (0, 31):
                continue
            curve = row["targets"][target]["curve"]
            ax.step([p["q"] for p in curve], [100 * p["fraction"] for p in curve], where="post",
                    color=COLORS[row["profile"]], label=f"{NAMES[row['profile']]}: {target}% OPT")
        finish(ax, "Нові оцінювання")
        ax.set_ylim(-1, 101)
        ax.legend(fontsize=8)
    finish(axes[0], ylabel="Досягли заданої якості, % запусків")
    save(fig, "03_targets.png", "Частка досягнення 95% і 99% точного оптимуму з випадкового початку. Недосягнення залишено в знаменнику; сімейства мають рівну вагу.")

    intervals = summary["primary_analysis"]["intervals"]
    if intervals:
        defined = [row for row in intervals if row["lower"] is not None and row["upper"] is not None]
        for row in intervals:
            if row not in defined:
                tables.append({"kind": "undefined_primary_interval", **row})
        if defined:
            fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
            labels = {**dict(zip(PRIMARY[:5], SHORT, strict=True)), 31: "Усі правила"}
            for index, row in enumerate(defined):
                ax.plot([row["lower"], row["upper"]], [index, index], color="#1765a0")
                ax.plot(row["estimate_gap_points"], index, "o", color="#1765a0")
            ax.set_yticks(range(len(defined)), [labels[row["profile"]] for row in defined])
            ax.axvline(0, color="black", linewidth=.8)
            finish(ax, "Відставання контролю мінус адаптації, в.п.")
            save(fig, "04_effects.png", "Шість первинних порівнянь з інтервалами BCa рівня 1 − 0,05/6. Додатний ефект означає менше відставання адаптивного варіанта.")
    else:
        tables.append({"kind": "primary_analysis", "status": "Не обчислено: технічний пілот"})

    matrix = np.full((5, 5), np.nan)
    for row in summary["interactions"]:
        i, j = FIELDS.index(row["first"]), FIELDS.index(row["second"])
        matrix[i, j] = matrix[j, i] = row["effect_gap_points"]
    limit = float(np.nanmax(np.abs(matrix)))
    if limit:
        fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)
        shown = ax.imshow(np.ma.masked_invalid(matrix), cmap="RdBu_r", vmin=-limit, vmax=limit)
        ax.set_xticks(range(5), SHORT, rotation=30, ha="right")
        ax.set_yticks(range(5), SHORT)
        for i in range(5):
            for j in range(5):
                if i != j:
                    ax.text(j, i, f"{matrix[i,j]:.2f}", ha="center", va="center", fontsize=9,
                            bbox={"facecolor": "white", "alpha": .7, "edgecolor": "none", "pad": 1})
        fig.colorbar(shown, ax=ax, label="Взаємодія відставань, в.п.")
        save(fig, "05_interactions.png", "Описові попарні взаємодії: g₁₁ − g₁₀ − g₀₁ + g₀₀. Інші три механізми усереднено. Від’ємне значення означає нижче відставання, ніж адитивне очікування.")
    else:
        tables.append({"kind": "constant_interactions", "value": 0, "pairs": 10})

    selected = [0, *PRIMARY]
    matrix = np.array([[next(row["mean_final_gap_percent"] for row in summary["type_cells"]
                             if row["start"] == "bank" and row["class_label"] == label and row["profile"] == profile)
                        for profile in selected] for label in ("UC", "WC", "SC")])
    if np.ptp(matrix):
        fig, ax = plt.subplots(figsize=(10, 3.3), constrained_layout=True)
        shown = ax.imshow(matrix, cmap="viridis_r", vmin=0, vmax=float(matrix.max()), aspect="auto")
        ax.set_yticks(range(3), ("UC", "WC", "SC"))
        ax.set_xticks(range(7), ("Сталі", *SHORT, "Усі правила"), rotation=25, ha="right")
        for i in range(3):
            for j in range(7):
                ax.text(j, i, f"{matrix[i,j]:.2f}", ha="center", va="center", fontsize=9,
                        bbox={"facecolor": "white", "alpha": .7, "edgecolor": "none", "pad": 1})
        fig.colorbar(shown, ax=ax, label="Відставання від OPT, %")
        save(fig, "06_task_types.png", "Кінцева якість за типом задачі для сталого контролю, п’яти окремих адаптацій і спільного керування. Випадковий початок.")
    else:
        tables.append({"kind": "constant_type_quality", "value": float(matrix[0, 0])})
    return {"schema": "parameter-dynamics-rendering-v1", "figures": figures, "numerical_tables": tables,
            "inside_titles": False, "registered_example": {key: examples[0][key] for key in ("task", "seed", "start")},
            "scientific_superiority_from_pilot": False}

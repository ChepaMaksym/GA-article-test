"""Descriptive CI reporting; never a search or a superiority test.

The pilot is not authorized merely because this module exists. The outer CI
driver must authenticate the registered phase, resource permission, exact SHA,
inputs and independent journal verification before calling ``build_report``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


METHODS = ("fixed", "adaptive_mutation")
LABELS = {"fixed": "Стала мутація", "adaptive_mutation": "Адаптивна мутація"}
COLORS = {"fixed": "#2166ac", "adaptive_mutation": "#b2182b"}
STARTS = {"cloned": "копії центра", "bank": "випадковий банк"}


def _require(condition, message):
    if not condition:
        raise ValueError("Invalid mutation-population report: " + message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "CI only")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test", "repository")
    _require(os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover", "branch")


def _money(value):
    return "—" if value is None else str(value)


def _data(summary, logs):
    rows = summary.get("results")
    _require(isinstance(rows, list) and len(rows) == 16, "expected sixteen technical pilot runs")
    expected = {(task, start, method) for task in ("UC-s000", "WC-s001", "SC-s005", "SC-s000")
                for start in STARTS for method in METHODS}
    seen, descriptions = set(), []
    for row in rows:
        identity = row["task"], row["start"], row["method"]
        _require(identity in expected - seen and row["seed"] == 86001, "duplicate or unregistered pilot identity")
        seen.add(identity)
        log, observed = logs[identity], row["observations"]
        _require(log["method"] == row["method"] and log["budget"] == 5000 and
                 len(log["candidates"]) == 5000 and log["summary"] == row["summary"] and
                 log["summary"]["new_calls"] == log["summary"]["physical_evaluations"] == 5000,
                 "journal binding or accounting")
        _require(observed["budget"] == 5000 and observed["method"] == row["method"] and
                 observed["final_record"]["profit"] == log["summary"]["best_profit"], "observer binding")
        records = [value["profit"] for value in log["initial_scores"] if value["feasible"]]
        _require(records and max(records) == observed["initial_record"]["profit"], "initial record")
        initial, final, optimum = max(records), observed["final_record"]["profit"], observed["external_optimum"]
        _require(type(optimum) is int and 0 < optimum and initial <= final <= optimum, "external optimum")
        first = next((candidate["call"] for candidate in log["candidates"]
                      if candidate["feasible"] and candidate["profit"] > observed["reference_profit"]), None)
        _require(first == observed["first_escape"] and observed["escaped"] == (first is not None) and
                 observed["capped_calls"] == (5000 if first is None else first), "escape/censoring reconstruction")
        descriptions.append({"task": row["task"], "start": row["start"], "method": row["method"],
            "seed": row["seed"], "external_optimum": optimum,
            "initial_record": initial, "final_record": final, "record_gain": final - initial,
            "initial_gap_percent": 100 * (optimum - initial) / optimum,
            "final_gap_percent": 100 * (optimum - final) / optimum,
            "first_improvement_call": first, "improved": first is not None,
            "restricted_calls": 5000 if first is None else first,
            "censored": first is None,
            "interpretation": ("GLOBAL_NEGATIVE_CONTROL" if row["start"] == "cloned" and initial == optimum
                               else "CERTIFIED_CENTER_ESCAPE" if row["start"] == "cloned"
                               else "INITIAL_BANK_RECORD_IMPROVEMENT"),
            "targets": observed["targets"], "new_calls": 5000,
            "duplicate_calls": log["summary"]["duplicate_calls"],
            "infeasible_calls": log["summary"]["infeasible_calls"],
            "final_mutation_probability": log["summary"]["final_mutation_probability"]})
    _require(seen == expected and set(logs) == expected, "incomplete or extra reporting evidence")
    return descriptions


def _setup_plotting():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.titlesize": 12, "axes.labelsize": 10,
                         "figure.facecolor": "white", "axes.facecolor": "white",
                         "axes.spines.top": False, "axes.spines.right": False})
    return plt


def _draw_trajectories(output, logs, indexed):
    plt = _setup_plotting()
    names = []
    for start in STARTS:
        fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True, constrained_layout=True)
        for method in METHODS:
            log = logs[("UC-s000", start, method)]
            observation = indexed[("UC-s000", start, method)]["observations"]
            optimum = observation["external_optimum"]
            events = log["generations"]
            x = [0] + [event["end_call"] for event in events]
            probability = [events[0]["p_m"]] + [event["p_m_next"] for event in events]
            axes[0].step(x, [100 * p for p in probability], where="post",
                         color=COLORS[method], label=LABELS[method])
            record = observation["record_trace"]
            axes[1].step([point["call"] for point in record],
                         [100 * point["profit"] / optimum for point in record],
                         where="post", color=COLORS[method], label=LABELS[method])
            population = observation["population_trace"]
            axes[2].plot([point["call"] for point in population],
                         [None if point["feasible_mean"]["value"] is None else
                          100 * point["feasible_mean"]["value"] / optimum for point in population],
                         color=COLORS[method], label=LABELS[method])
        axes[0].set_title("Як реагує мутація? Популяція 30, схрещування 90%")
        axes[0].set_ylabel("Мутація біта, %")
        axes[1].set_title("Чи зростає найкращий знайдений результат?")
        axes[1].set_ylabel("Рекорд, % OPT")
        axes[2].set_title("Яка середня якість допустимих особин популяції?")
        axes[2].set_ylabel("Середня цінність, % OPT")
        axes[2].set_xlabel("Нові оцінювання; відомий початок — точка 0")
        for ax in axes:
            ax.grid(alpha=.2)
            ax.legend(loc="best")
            ax.set_xlim(0, 5000)
        fig.suptitle(f"UC-s000, seed 86001: {STARTS[start]}. Технічний приклад")
        name = f"uc-s000-{start}-mutation-and-quality.png"
        fig.savefig(output / name, dpi=170)
        plt.close(fig)
        names.append(name)
    return names


def _draw_final_gaps(output, descriptions):
    plt = _setup_plotting()
    conditions = [(task, start) for task in ("UC-s000", "WC-s001", "SC-s005", "SC-s000") for start in STARTS]
    fig, ax = plt.subplots(figsize=(11, 7), constrained_layout=True)
    lookup = {(row["task"], row["start"], row["method"]): row for row in descriptions}
    for i, (task, start) in enumerate(conditions):
        for j, method in enumerate(METHODS):
            row, y = lookup[(task, start, method)], i + (-.12 if j == 0 else .12)
            initial, final = row["initial_gap_percent"], row["final_gap_percent"]
            ax.plot([initial, final], [y, y], color=COLORS[method], alpha=.7)
            ax.scatter([initial], [y], facecolors="none", edgecolors=COLORS[method], marker="o")
            ax.scatter([final], [y], color=COLORS[method], marker="o", label=LABELS[method] if i == 0 else None)
    ax.set_yticks(range(len(conditions)), [f"{task}: {STARTS[start]}" for task, start in conditions])
    ax.invert_yaxis()
    ax.set_xlabel("Відставання від точного оптимуму, %; менше — краще")
    ax.set_title("Що змінилося за 5000 нових оцінювань?\nПорожнє коло — початок; заповнене — кінцевий рекорд")
    ax.grid(axis="x", alpha=.2)
    ax.legend()
    name = "initial-versus-final-gap.png"
    fig.savefig(output / name, dpi=170)
    plt.close(fig)
    return name


def _draw_attainment(output, descriptions):
    plt = _setup_plotting()
    conditions = [(task, start) for task in ("UC-s000", "WC-s001", "SC-s005", "SC-s000") for start in STARTS]
    lookup = {(row["task"], row["start"], row["method"]): row for row in descriptions}
    fig, axes = plt.subplots(1, 2, figsize=(14, 7), sharey=True, constrained_layout=True)
    for ax, target in zip(axes, ("95", "99"), strict=True):
        for i, (task, start) in enumerate(conditions):
            for j, method in enumerate(METHODS):
                row = lookup[(task, start, method)]
                endpoint = row["targets"][target]
                first, reached = endpoint["first_call"], endpoint["reached"]
                _require(reached == (first is not None), "target censoring")
                ax.scatter([first if reached else 5000], [i + (-.12 if j == 0 else .12)],
                           marker="o" if reached else "x", color=COLORS[method], s=45,
                           label=LABELS[method] if i == 0 else None)
        ax.set_title(f"Коли вперше досягнуто {target}% OPT?")
        ax.set_xlabel("Нові оцінювання; × біля 5000 — не досягнуто")
        ax.set_xlim(-100, 5150)
        ax.grid(alpha=.2)
        ax.legend(loc="best")
    axes[0].set_yticks(range(len(conditions)), [f"{task}: {STARTS[start]}" for task, start in conditions])
    axes[0].invert_yaxis()
    fig.suptitle("Один технічний seed: точки окремих запусків, не оцінка частоти успіху")
    name = "target-attainment-and-nonattainment.png"
    fig.savefig(output / name, dpi=170)
    plt.close(fig)
    return name


def build_report(output, summary, logs):
    """Write only a complete, independently verified sixteen-run pilot report.

    ``logs`` maps (task, start, method) to the unmodified verified search log.
    Each summary result binds ``observations`` and the engine's ``summary`` to
    the same identity. Population adaptation remains a blocked reserved profile.
    """
    _ci_only()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    targets = ["REPORT_UK.md", "descriptive_report.json", "uc-s000-cloned-mutation-and-quality.png",
               "uc-s000-bank-mutation-and-quality.png", "initial-versus-final-gap.png",
               "target-attainment-and-nonattainment.png"]
    _require(not any((output / name).exists() for name in targets), "existing reports are not overwritten")
    descriptions = _data(summary, logs)
    indexed = {(row["task"], row["start"], row["method"]): row for row in summary["results"]}
    figures = _draw_trajectories(output, logs, indexed)
    figures.append(_draw_final_gaps(output, descriptions))
    figures.append(_draw_attainment(output, descriptions))
    report = {"schema": "mutation-population-descriptive-report-v1",
              "protocol_id": "GA-KNAPSACK-MUTATION-POPULATION-V1",
              "status": "DESCRIPTIVE_TECHNICAL_PILOT", "search_seed": 86001,
              "runs": 16, "new_evaluations": 80000,
              "bootstrap_performed": False, "superiority_tested": False,
              "adaptive_population_implemented": False,
              "figures": figures, "results": descriptions}
    (output / "descriptive_report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Стала й адаптивна мутація: технічний пілот", "",
             "Порівняно власну мутаційну евристику зі сталою мутацією 1% на біт; популяція 30 і схрещування 90% незмінні.", "",
             "Завершено 16 запусків по 5000 нових оцінювань: 80 000 пошукових запитів. Початкові та незалежні перевірні оцінювання обліковуються окремо.", "",
             "Це новий технічний seed 86001. Історичні 16 запусків не додано до цієї вибірки. Адаптація популяції не реалізована та не підмінена сталою конфігурацією.", "",
             "## Що отримано", "",
             "| Задача | Початок | Метод | Початковий рекорд | Кінцевий рекорд | Перше поліпшення | Кінцеве відставання, % |",
             "|---|---|---|---:|---:|---:|---:|"]
    for row in descriptions:
        lines.append(f"| {row['task']} | {STARTS[row['start']]} | {LABELS[row['method']]} | "
                     f"{row['initial_record']} | {row['final_record']} | {_money(row['first_improvement_call'])} | "
                     f"{row['final_gap_percent']:.4f} |")
    lines.extend(["", "«—» означає відсутність поліпшення, а не поліпшення на запиті 5000. Для копій неглобального сертифікованого центра це вихід; для банку — поліпшення його початкового рекорду. Глобальний центр є негативним контролем.", "",
                  "## Графіки: питання й відповідь", ""])
    for i, name in enumerate(figures, 1):
        lines.extend([f"![Рисунок {i}]({name})", ""])
    lines.extend(["Мутація показана окремо від рекорду й середньої якості допустимих особин. Рекорд не знижується за означенням; середня якість може погіршуватися. Незавершений префікс враховано в рекорді, але він не є новою популяцією.", "",
                  "## Точний оптимум: без порожнього графіка", "",
                  "| Задача | Початок | Метод | Досягнуто 100% OPT | Перший запит |", "|---|---|---|---|---:|"])
    for row in descriptions:
        target = row["targets"]["100"]
        lines.append(f"| {row['task']} | {STARTS[row['start']]} | {LABELS[row['method']]} | "
                     f"{'так' if target['reached'] else 'ні'} | {_money(target['first_call'])} |")
    lines.extend(["", "## Межі висновків", "",
                  "*Один технічний seed перевіряє реалізацію й доказові журнали, а не статистичну перевагу. Бутстреп, p-значення та кореляції переваги не обчислювалися. Адаптація мутації не розпізнає локальну чи глобальну оптимальність; невихід не є доказом глобальності. Порівняння потребує окремо дозволеної багатоповторної серії. Власна евристика не називається відтворенням статті.*", ""])
    (output / "REPORT_UK.md").write_text("\n".join(lines), encoding="utf-8")
    return report

"""Descriptive, common-target speed and paired-value analysis of the fixed grid.

No search, optimal solver, significance test or adaptive controller is used.
The outer replay/transport contract authenticates the histories; this module
independently checks their compact structure and endpoint consistency.
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
import json
from numbers import Integral
from pathlib import Path

from .analysis import (BASELINE, BUDGET, CROSSOVERS, MUTATIONS,
                       POPULATIONS, PROTOCOL, SEEDS, TASKS, _ci_only,
                       configuration_id)


TARGETS = (95, 99, 100)
AXES = ("p_m", "p_c", "population_size")
LEVELS = (MUTATIONS, CROSSOVERS, POPULATIONS)


def _require(condition, message):
    if not condition:
        raise ValueError("Basic-parameters speed analysis: " + message)


def _integer(value, minimum, label):
    _require(isinstance(value, Integral) and not isinstance(value, bool) and value >= minimum, label)
    return int(value)


def _exact(value):
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def validate_history(row, optimum):
    """Return copied strict record points; never fill gaps or invent attainment.

    The initial empty mask is the first evaluated mask. Subsequent points occur
    only after a strictly greater feasible value, including an incomplete final
    generation. Equal values do not reset the first attainment time.
    """
    optimum = _integer(optimum, 1, "positive external optimum")
    history = row.get("record_history")
    _require(type(history) is list and bool(history), "missing record history")
    size = _integer(row.get("population_size"), 2, "population size")
    _require(size in POPULATIONS, "unregistered population")
    _require(type(row.get("budget")) is int and row["budget"] == BUDGET and
             type(row.get("logical_requests")) is int and row["logical_requests"] == BUDGET,
             "history budget")
    points = []
    previous_request, previous_profit = 0, -1
    for point in history:
        _require(type(point) is dict and set(point) == {"request", "profit"}, "record point fields")
        request = _integer(point["request"], 1, "record request")
        profit = _integer(point["profit"], 0, "record profit")
        _require(previous_request < request <= BUDGET, "record requests not strictly increasing/in budget")
        _require(previous_profit < profit <= optimum, "record profits not strict or above exact optimum")
        points.append({"request": request, "profit": profit})
        previous_request, previous_profit = request, profit
    _require(points[0] == {"request": 1, "profit": 0}, "first request must be the known empty bank mask")
    _require(type(row.get("best_profit")) is int and type(row.get("best_request")) is int and
             points[-1] == {"request": row["best_request"], "profit": row["best_profit"]},
             "history final value/first attainment disagrees with verified best")
    initial = _integer(row.get("initial_best_profit"), 0, "initial record")
    prefix_best = max(point["profit"] for point in points if point["request"] <= size)
    _require(prefix_best == initial, "history initial-prefix record")
    _require((points[-1]["request"] <= size) == (initial == points[-1]["profit"]),
             "first attainment versus initialization")
    return points


def first_at_least(history, target, denominator=1):
    """First request at a shared exact integer threshold, or None if not hit."""
    target = _integer(target, 0, "integer target numerator")
    denominator = _integer(denominator, 1, "target denominator")
    return next((point["request"] for point in history
                 if denominator * point["profit"] >= target), None)


def hierarchical_mean(values):
    """Equal seeds -> equal tasks -> equal families; values keyed by task,seed."""
    _require(bool(values), "empty family weighting")
    task_values = defaultdict(list)
    for (task, seed), value in values.items():
        _require(type(task) is str and "-s" in task and type(seed) is int, "weighting identity")
        task_values[task].append(Fraction(value))
    family_values = defaultdict(list)
    for task, points in task_values.items():
        family_values[task.split("-", 1)[1]].append(sum(points, Fraction()) / len(points))
    families = {family: sum(points, Fraction()) / len(points)
                for family, points in family_values.items()}
    return sum(families.values(), Fraction()) / len(families), families


def weighted_ecdf(times):
    """All runs remain in the denominator; nonhits are not events at 5000."""
    _require(bool(times), "empty speed curve")
    task_sizes = defaultdict(int)
    family_tasks = defaultdict(set)
    for task, seed in times:
        task_sizes[task] += 1
        family_tasks[task.split("-", 1)[1]].add(task)
    event_weights = defaultdict(Fraction)
    raw_hits = 0
    for (task, seed), time in times.items():
        if time is None:
            continue
        time = _integer(time, 1, "target attainment request")
        _require(time <= BUDGET, "target hit beyond budget")
        family = task.split("-", 1)[1]
        weight = Fraction(1, len(family_tasks) * len(family_tasks[family]) * task_sizes[task])
        event_weights[time] += weight
        raw_hits += 1
    cumulative = Fraction()
    points = [{"request": 0, "fraction": 0.0, "fraction_exact": _exact(0)}]
    for request, weight in sorted(event_weights.items()):
        cumulative += weight
        points.append({"request": request, "fraction": float(cumulative), "fraction_exact": _exact(cumulative)})
    if points[-1]["request"] != BUDGET:
        points.append({"request": BUDGET, "fraction": float(cumulative), "fraction_exact": _exact(cumulative)})
    return {"points": points, "reached": raw_hits, "not_reached": len(times) - raw_hits,
            "run_count": len(times), "family_weighted_reached_fraction": float(cumulative),
            "family_weighted_reached_fraction_exact": _exact(cumulative)}


def analyze(rows, instances, optima):
    """Check a complete authenticated 37500-row development rectangle."""
    _ci_only()
    _require(type(rows) is list and len(rows) == 37500, "expected 37500 development runs")
    _require(set(instances) == set(optima) == set(TASKS), "wrong development task/optimum identities")
    optimum_values = {task: _integer(optima[task], 1, "external exact optimum") for task in TASKS}
    for task, instance in instances.items():
        n = instance["n"] if isinstance(instance, dict) else instance.n
        _require(type(n) is int and n == 100, "registered dimension")
    grid = tuple((p_m, p_c, size) for p_m in MUTATIONS for p_c in CROSSOVERS for size in POPULATIONS)
    expected = {(task, seed, config) for task in TASKS for seed in SEEDS for config in grid}
    by_config = defaultdict(dict)
    seen = set()
    sources, implementations = set(), set()
    for row in rows:
        _require(type(row) is dict and row.get("protocol_id") == PROTOCOL and row.get("phase") == "main",
                 "wrong protocol or non-development run")
        task, seed = row.get("instance_id"), row.get("repeat_seed")
        _require(type(task) is str and type(seed) is int, "run identity")
        for field in ("p_m", "p_c"):
            _require(type(row.get(field)) in (int, float), "numeric parameter: " + field)
        config = (Fraction(str(row["p_m"])), Fraction(str(row["p_c"])), row.get("population_size"))
        identity = task, seed, config
        _require(identity in expected and identity not in seen, "duplicate or unregistered identity")
        seen.add(identity)
        _require(row.get("configuration_id") == configuration_id(*config), "configuration identifier")
        _require(row.get("verified") is True and row.get("verification_status") == "PASS_REPLAY",
                 "history not bound to independent replay")
        sources.add(row.get("source_manifest_sha256"))
        implementations.add(row.get("implementation_commit_sha"))
        points = validate_history(row, optimum_values[task])
        by_config[config][(task, seed)] = {"row": row, "history": points,
            "targets": {str(q): first_at_least(points, q * optimum_values[task], 100) for q in TARGETS}}
    _require(seen == expected and len(sources) == len(implementations) == 1 and
             None not in sources and None not in implementations, "incomplete/mixed source rectangle")
    baseline = by_config[BASELINE]
    for task in TASKS:
        for seed in SEEDS:
            prefixes = []
            for size in POPULATIONS:
                histories = [by_config[config][(task, seed)]["history"] for config in grid if config[2] == size]
                prefix = [[point for point in history if point["request"] <= size] for history in histories]
                _require(all(value == prefix[0] for value in prefix), "shared initial bank history differs by configuration")
                prefixes.append(prefix[0])
            for size, first, second in zip(POPULATIONS, prefixes, prefixes[1:]):
                # A larger bank extends the same evaluations, not merely the same final value.
                _require(first == [point for point in second if point["request"] <= size], "nested initial histories disagree")

    runs, configurations = [], []
    for config in grid:
        comparisons = {name: {} for name in ("higher", "equal", "lower")}
        target_times = {str(q): {} for q in TARGETS}
        baseline_times = {}
        for pair, value in by_config[config].items():
            row = value["row"]
            baseline_profit = baseline[pair]["row"]["best_profit"]
            delta = row["best_profit"] - baseline_profit
            relation = "higher" if delta > 0 else "lower" if delta < 0 else "equal"
            for name in comparisons:
                comparisons[name][pair] = int(relation == name)
            for q in TARGETS:
                target_times[str(q)][pair] = value["targets"][str(q)]
            baseline_time = first_at_least(value["history"], baseline_profit)
            baseline_times[pair] = baseline_time
            runs.append({"instance_id": pair[0], "repeat_seed": pair[1], "configuration_id": configuration_id(*config),
                "target_times": value["targets"], "baseline_final_profit": baseline_profit,
                "first_at_least_baseline_final": baseline_time, "relation_to_baseline": relation,
                "best_profit": row["best_profit"], "first_final_value": row["best_request"],
                "initial_best_profit": row["initial_best_profit"]})
        rates = {}
        for name, values in comparisons.items():
            mean, families = hierarchical_mean(values)
            rates[name] = {"count": sum(values.values()), "fraction": float(mean), "fraction_exact": _exact(mean),
                "family_fractions": [{"family": family, "fraction": float(value), "fraction_exact": _exact(value)}
                                     for family, value in sorted(families.items())]}
        configurations.append({"configuration_id": configuration_id(*config), "p_m": float(config[0]),
            "p_c": float(config[1]), "population_size": config[2], "paired_runs": 300,
            "paired_results": rates, "targets": {q: weighted_ecdf(times) for q, times in target_times.items()},
            "baseline_final_target": weighted_ecdf(baseline_times)})
    config_lookup = {row["configuration_id"]: row for row in configurations}
    conditional = []
    for axis, levels in enumerate(LEVELS):
        points = []
        for level in levels:
            config = list(BASELINE)
            config[axis] = level
            point = config_lookup[configuration_id(*config)]
            points.append(point)
        conditional.append({"varying_parameter": AXES[axis],
            "fixed_parameters": {AXES[i]: float(BASELINE[i]) if i < 2 else BASELINE[i]
                                 for i in range(3) if i != axis}, "points": points})
    grouped = defaultdict(list)
    for config in grid:
        value = by_config[config][("UC-s000", 81001)]
        row = value["row"]
        grouped[row["best_profit"]].append({"configuration_id": configuration_id(*config),
            "p_m": float(config[0]), "p_c": float(config[1]), "population_size": config[2],
            "first_attainment": row["best_request"], "baseline": config == BASELINE})
    return {"schema": "basic-parameters-speed-descriptive-v1", "protocol_id": PROTOCOL,
        "scope": "DEVELOPMENT_FIXED_GRID_ONLY", "runs": len(rows), "budget": BUDGET,
        "targets_percent": list(TARGETS), "baseline_id": configuration_id(*BASELINE),
        "source_manifest_sha256": next(iter(sources)), "implementation_sha": next(iter(implementations)),
        "weighting": "seeds -> task -> classes within family -> ten equal families",
        "configurations": configurations, "conditional_panels": conditional,
        "run_targets": runs, "example": {"instance_id": "UC-s000", "repeat_seed": 81001,
            "configuration_count": 125, "same_final_value_groups": [{"profit": profit, "configurations": configs}
                    for profit, configs in sorted(grouped.items())]},
        "superiority_tested": False, "statistical_equivalence_tested": False,
        "bootstrap_resamples": 0, "holdout_statistics_performed": False,
        "history_authentication": "Outer independent full-journal replay plus file/transport checks required; compact checks cannot prove unreported events absent.",
        "limitations": ["Development data only; no independent holdout superiority claim.",
                        "Not reaching a target is None, not a fabricated hit at the budget.",
                        "Equal final integer values do not imply equal masks or statistical equivalence.",
                        "Initial-prefix evaluations are included; larger populations have a different initialization cost.",
                        "Early attainment of a poor own final value does not imply faster attainment of shared quality."]}


def write_report(report, output):
    """Write question-driven figures and Ukrainian descriptive answers in CI."""
    _ci_only()
    _require(report.get("schema") == "basic-parameters-speed-descriptive-v1" and
             report.get("scope") == "DEVELOPMENT_FIXED_GRID_ONLY", "wrong report scope")
    import matplotlib.pyplot as plt
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    labels = {"p_m": "Мутація біта", "p_c": "Схрещування", "population_size": "Популяція"}
    figures = []
    for q in TARGETS:
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.7), layout="constrained")
        for axis, panel in zip(axes, report["conditional_panels"], strict=True):
            parameter = panel["varying_parameter"]
            for point in panel["points"]:
                level = point[parameter]
                label = f"{level:g}" if parameter == "population_size" else f"{100 * level:g}%"
                curve = point["targets"][str(q)]["points"]
                axis.step([item["request"] for item in curve], [100 * item["fraction"] for item in curve],
                          where="post", label=label, linewidth=1.7)
            fixed = "; ".join(f"{labels[key]} {value:g}" if key == "population_size" else
                              f"{labels[key]} {100 * value:g}%" for key, value in panel["fixed_parameters"].items())
            axis.set_title(f"Змінюємо: {labels[parameter].lower()}\n{fixed}", fontsize=10)
            axis.set_xlabel("Загальні оцінювання, включно з початком")
            axis.set_ylabel(f"Досягли ≥{q}% OPT, % запусків")
            axis.set_xlim(1, BUDGET)
            axis.set_ylim(0, 100)
            axis.legend(title=labels[parameter], fontsize=8, title_fontsize=8)
            axis.grid(alpha=0.25)
        fig.suptitle(f"Який параметр пришвидшує досягнення однакової якості? Ціль {q}% OPT", fontsize=13)
        path = f"speed-target-{q}.png"
        fig.savefig(output / path, dpi=170)
        plt.close(fig)
        figures.append(path)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), layout="constrained")
    for axis, panel in zip(axes, report["conditional_panels"], strict=True):
        parameter = panel["varying_parameter"]
        points = panel["points"]
        x = list(range(len(points)))
        bottom = [0.0] * len(points)
        for name, label, color in (("lower", "Нижча цінність", "#999999"),
                                   ("equal", "Точно така сама", "#66a5d4"),
                                   ("higher", "Вища цінність", "#215b38")):
            height = [100 * point["paired_results"][name]["fraction"] for point in points]
            axis.bar(x, height, bottom=bottom, label=label, color=color)
            bottom = [first + second for first, second in zip(bottom, height, strict=True)]
        axis.set_xticks(x, [f"{point[parameter]:g}" if parameter == "population_size" else
                           f"{100 * point[parameter]:g}%" for point in points])
        axis.set_xlabel(labels[parameter] + "; два інші параметри опорні")
        axis.set_ylabel("Парні результати, %")
        axis.set_ylim(0, 100)
        axis.grid(axis="y", alpha=0.2)
    axes[-1].legend(fontsize=8, loc="upper left", bbox_to_anchor=(1, 1))
    fig.suptitle("За яких параметрів кінцевий результат збігається? Порівняння з 1%; 90%; 30")
    path = "same-result-vs-baseline.png"
    fig.savefig(output / path, dpi=170)
    plt.close(fig)
    figures.append(path)

    fig, axis = plt.subplots(figsize=(10, 6), layout="constrained")
    groups = report["example"]["same_final_value_groups"]
    baseline = None
    for group in groups:
        configs = group["configurations"]
        times = [row["first_attainment"] for row in configs]
        axis.plot([min(times), max(times)], [group["profit"]] * 2, color="#aaaaaa", linewidth=1)
        axis.scatter(times, [group["profit"]] * len(times), s=22, alpha=0.65, color="#333333")
        for row in configs:
            if row["baseline"]:
                baseline = row["first_attainment"], group["profit"]
    if baseline is not None:
        axis.scatter([baseline[0]], [baseline[1]], s=100, marker="*", color="#0875ad", zorder=3,
                     label="Опорний ГА: мутація 1%; схрещування 90%; популяція 30")
        axis.legend(fontsize=8)
    axis.set_xlim(0, BUDGET)
    axis.set_xlabel("Перший загальний запит до власної кінцевої цінності")
    axis.set_ylabel("Кінцева ціла цінність набору")
    axis.set_title("Чи однакова цінність досягається за різних витрат?\nUC-s000, seed 81001: усі 125 конфігурацій")
    axis.grid(alpha=0.25)
    path = "same-value-attainment-UC-s000-81001.png"
    fig.savefig(output / path, dpi=170)
    plt.close(fig)
    figures.append(path)

    saved = dict(report, figures=figures)
    (output / "speed_analysis.json").write_text(json.dumps(saved, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Параметри ГА: результат і витрати", "",
        "## Скільки оцінювань потрібно до однакової якості?", "",
        "Основний рисунок speed-target-99.png показує частку запусків, які вже досягли 99% точного оптимуму. "
        "Вона усереднена за повтореннями, задачами та рівноважними сімействами. Невиходи залишаються в знаменнику; "
        "недосягнення не перетворюється на досягнення на запиті 5000. Рисунки для 95% і 100% — перевірка чутливості, не вибір вигідного порогу.", "",
        "Вища лінія за однакової кількості оцінювань означає більше досягнень спільної цілі. Якщо лінії перетинаються, "
        "єдиного найшвидшого налаштування для всіх витрат немає. Плоска нульова лінія означає, що жоден запуск не досяг цієї цілі, а не відсутність даних.", "",
        "![Скільки оцінювань потрібно до 99% OPT?](speed-target-99.png)", "",
        "## За яких налаштувань цінність збігається?", "",
        "Кожну конфігурацію порівняно з опорною на тій самій задачі й seed: вища, точно однакова або нижча ціла кінцева цінність. "
        "Графік змінює один параметр; решта два — опорні. Повні 125 конфігурацій і абсолютні кількості пар збережено в speed_analysis.json. "
        "Це точні збіги спостережуваних значень, не тест статистичної еквівалентності й не гарантія однакових масок.", "",
        "![Коли результат збігається з опорним ГА?](same-result-vs-baseline.png)", "",
        "## Чи можна одержати ту саму цінність раніше?", "",
        "Показано всі 125 конфігурацій наперед обраного прикладу UC-s000, seed 81001. Горизонтальний рівень об'єднує однакові кінцеві цінності; "
        "кожна точка — конфігурація, збіги координат можуть накладатися. Повний склад груп і три параметри кожної точки є в JSON. "
        "Швидкий прихід до гіршої власної цінності не означає швидшого досягнення спільної якості: для цього потрібен попередній рисунок з OPT.", "",
        "![Однакова цінність за різних витрат](same-value-attainment-UC-s000-81001.png)", "",
        "## Короткі відповіді за конфігураціями", "",
        "| Мутація біта, % | Схрещування, % | Популяція | Досягли 99% OPT, % | Точно як опорний, % | Вище / нижче, % |", "|---:|---:|---:|---:|---:|---:|"]
    for config in report["configurations"]:
        rates = config["paired_results"]
        lines.append(f"| {100 * config['p_m']:g} | {100 * config['p_c']:g} | {config['population_size']} | "
                     f"{100 * config['targets']['99']['family_weighted_reached_fraction']:.2f} | "
                     f"{100 * rates['equal']['fraction']:.2f} | "
                     f"{100 * rates['higher']['fraction']:.2f} / {100 * rates['lower']['fraction']:.2f} |")
    lines += ["", "*Лише дослідницька стала сітка. Попередній відбір переможця, невідомі пошукові результати нових задач, "
              "адаптивний контролер, перевірка переваги та статистична еквівалентність тут не оцінюються. "
              "Початкові оцінювання входять до витрат: більша популяція вже спочатку переглядає більше масок.*", ""]
    (output / "PARAMETERS_RESULTS_UK.md").write_text("\n".join(lines), encoding="utf-8")
    return {"figures": figures, "report": "speed_analysis.json", "answers": "PARAMETERS_RESULTS_UK.md"}

"""Exploratory, family-weighted readout of already recorded GA trajectories.

No search, exact solver or adaptive controller is imported by this module.
Scientific reports and figures are written only by GitHub Actions.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import re
from statistics import mean


PROTOCOL_ID = "GA-KNAPSACK-STAGNATION-MECHANISMS-SECONDARY-V1"
CHECKPOINTS = (0, 1000, 2500, 5000)
PM_GRID = (0.0, 0.005, 0.01, 0.02, 0.03, 0.08)
SAMPLE_BUDGETS = (50, 100, 250)
STATES = ("N2_NOT_LOCAL", "N2_STRICT_NONGLOBAL", "N2_NONSTRICT_NONGLOBAL", "GLOBAL_OPTIMUM")
IMPROVEMENT_TYPES = ("add_one", "remove_one", "swap_one", "add_two", "remove_two")
ROOT = Path(__file__).resolve().parents[3]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _integer(value, minimum=0, maximum=None):
    return type(value) is int and value >= minimum and (maximum is None or value <= maximum)


def expected_identities():
    return {(f"{label}-s{index:03d}", seed) for label in ("UC", "WC", "SC")
            for index in range(10) for seed in range(93001, 93031)}


def average_ranks(values):
    """One-based average ranks, retaining the original observation order."""
    values = list(values)
    _require(all(_finite(value) for value in values), "Nonfinite rank observation")
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    first = 0
    while first < len(order):
        stop = first + 1
        while stop < len(order) and values[order[stop]] == values[order[first]]:
            stop += 1
        rank = (first + 1 + stop) / 2
        for position in order[first:stop]:
            ranks[position] = rank
        first = stop
    return ranks


def spearman(x, y):
    """Descriptive Spearman coefficient, with no p-value or imputation."""
    x, y = list(x), list(y)
    _require(len(x) == len(y), "Rank series lengths differ")
    rx, ry = average_ranks(x), average_ranks(y)
    if len(x) < 2:
        return {"status": "UNDEFINED", "rho": None, "n": len(x), "reason": "FEWER_THAN_TWO_UNITS"}
    mx, my = mean(rx), mean(ry)
    dx, dy = [value - mx for value in rx], [value - my for value in ry]
    vx, vy = sum(value * value for value in dx), sum(value * value for value in dy)
    if vx == 0 or vy == 0:
        return {"status": "UNDEFINED", "rho": None, "n": len(x), "reason": "CONSTANT_SERIES"}
    rho = sum(a * b for a, b in zip(dx, dy)) / math.sqrt(vx * vy)
    return {"status": "DEFINED", "rho": max(-1.0, min(1.0, rho)), "n": len(x), "reason": None}


def _validate_checkpoint(cp, q):
    _require(cp.get("q") == q and _integer(cp.get("stagnation_age"), maximum=q)
             and type(cp.get("stagnant")) is bool
             and cp["stagnant"] == (cp["stagnation_age"] >= 1000), "Invalid checkpoint or stagnation")
    b1, b2 = cp.get("b1"), cp.get("b2")
    _require(_integer(b1, maximum=100) and _integer(b2, maximum=4950)
             and cp.get("total_better") == b1 + b2, "Invalid improving-neighbor counts")
    _require(cp.get("state") in STATES
             and (cp["state"] == "N2_NOT_LOCAL") == (b1 + b2 > 0), "Neighbor state contradicts counts")
    _require(_integer(cp.get("slack")), "Invalid capacity slack")
    gains = [cp.get("min_positive_gain"), cp.get("max_positive_gain")]
    if b1 + b2:
        _require(all(_integer(value, 1) for value in gains) and gains[0] <= gains[1]
                 and _integer(cp.get("sum_positive_gain"), b1 + b2)
                 and gains[0] * (b1 + b2) <= cp["sum_positive_gain"] <= gains[1] * (b1 + b2),
                 "Invalid positive improvement gains")
    else:
        _require(gains == [None, None] and cp.get("sum_positive_gain") == 0,
                 "Absent improvements must retain undefined gains")
    types = cp.get("improvement_types", {})
    _require(set(types) == set(IMPROVEMENT_TYPES) and all(_integer(value) for value in types.values())
             and types["add_one"] + types["remove_one"] == b1
             and types["swap_one"] + types["add_two"] + types["remove_two"] == b2,
             "Invalid improving-neighbor type accounting")
    probabilities = cp.get("model_probabilities", [])
    _require(len(probabilities) == len(PM_GRID), "Incomplete mutation probability grid")
    for entry, p in zip(probabilities, PM_GRID):
        expected = b1 * p * (1 - p) ** 99 + b2 * p * p * (1 - p) ** 98
        _require(entry.get("p") == p and _finite(entry.get("probability"))
                 and 0 <= entry["probability"] <= 1
                 and math.isclose(entry["probability"], expected, rel_tol=1e-12, abs_tol=1e-14),
                 "Mutation model probability mismatch")
    detections = cp.get("detection_probabilities", [])
    _require(len(detections) == len(SAMPLE_BUDGETS), "Incomplete diagnostic sample grid")
    for entry, sample in zip(detections, SAMPLE_BUDGETS):
        available = 5050 - b1 - b2
        expected = 1.0 if sample > available else 1 - math.comb(available, sample) / math.comb(5050, sample)
        _require(entry.get("sample_size") == sample and _finite(entry.get("probability"))
                 and 0 <= entry["probability"] <= 1
                 and math.isclose(entry["probability"], expected, rel_tol=1e-10, abs_tol=1e-12),
                 "Diagnostic detection probability mismatch")


def _validate_operators(operators):
    groups = operators.get("groups", {})
    _require(set(groups) == {"all_new", "late_1000"}, "Missing operator observation windows")
    for name, count in (("all_new", 5000), ("late_1000", 1000)):
        group = groups[name]
        _require(group.get("candidate_count") == count, "Operator candidate accounting mismatch")
        fields = ("crossover_applied_count", "crossover_skipped_count", "premutation_better_count",
                  "final_record_count", "mutation_created_count", "mutation_preserved_count",
                  "mutation_lost_count", "mutation_neither_count", "premutation_feasible_count",
                  "final_feasible_count", "zero_mutation_count", "duplicate_count",
                  "record_present_in_population_count", "record_selected_candidate_count", "record_pending_count",
                  "record_absent_from_population_and_pending_count", "crossover_actual_change_from_first_parent_count",
                  "crossover_novel_to_both_parents_count")
        _require(all(_integer(group.get(field), maximum=count) for field in fields),
                 "Invalid operator counter")
        _require(group["crossover_applied_count"] + group["crossover_skipped_count"] == count,
                 "Crossover branches do not cover candidates")
        _require(_integer(group.get("record_selected_parent_slots"), maximum=2 * count)
                 and group["record_selected_candidate_count"] <= group["record_selected_parent_slots"]
                 <= 2 * group["record_selected_candidate_count"], "Invalid selected-parent slot count")
        conditioned = group.get("crossover_conditioned", {})
        _require(conditioned.get("candidate_count") == group["crossover_applied_count"]
                 and all(_integer(conditioned.get(key), maximum=conditioned["candidate_count"])
                         for key in ("feasible_parent_baseline_count", "undefined_parent_baseline_count",
                                     "premutation_better_than_parent_count", "final_better_than_parent_count"))
                 and conditioned["feasible_parent_baseline_count"] + conditioned["undefined_parent_baseline_count"]
                 == conditioned["candidate_count"]
                 and conditioned["premutation_better_than_parent_count"] <= conditioned["feasible_parent_baseline_count"]
                 and conditioned["final_better_than_parent_count"] <= conditioned["feasible_parent_baseline_count"],
                 "Invalid parent-relative crossover denominator")
        _require(group["crossover_actual_change_from_first_parent_count"] <= group["crossover_applied_count"]
                 and group["crossover_novel_to_both_parents_count"] <= group["crossover_actual_change_from_first_parent_count"],
                 "Crossover novelty exceeds branch count")
        created, preserved, lost, neither = [group[f"mutation_{kind}_count"]
                                            for kind in ("created", "preserved", "lost", "neither")]
        _require(created + preserved + lost + neither == count
                 and created + preserved == group["final_record_count"]
                 and preserved + lost == group["premutation_better_count"], "Mutation event accounting mismatch")
        transitions = group.get("feasibility_transitions", {})
        names = ("infeasible_to_infeasible", "infeasible_to_feasible", "feasible_to_infeasible", "feasible_to_feasible")
        _require(set(transitions) == set(names) and all(_integer(value, maximum=count) for value in transitions.values())
                 and sum(transitions.values()) == count
                 and transitions["feasible_to_infeasible"] + transitions["feasible_to_feasible"] == group["premutation_feasible_count"]
                 and transitions["infeasible_to_feasible"] + transitions["feasible_to_feasible"] == group["final_feasible_count"],
                 "Feasibility transition accounting mismatch")
    cps = operators.get("checkpoints", [])
    _require([cp.get("q") for cp in cps] == list(CHECKPOINTS), "Operator checkpoint coverage mismatch")
    for cp in cps:
        _require(type(cp.get("record_mask_present_in_population")) is bool
                 and _integer(cp.get("record_mask_copy_count"), maximum=30)
                 and cp["record_mask_present_in_population"] == (cp["record_mask_copy_count"] > 0),
                 "Invalid record-mask population presence")


def _weighted(rows, value, select=lambda row: True):
    """Ratio of family-weighted numerators/denominators, never selected-task means."""
    tasks = defaultdict(list)
    for row in rows:
        tasks[row["instance_id"]].append(row)
    families = defaultdict(list)
    for instance, repeats in sorted(tasks.items()):
        numerator = mean(value(row) if select(row) else 0.0 for row in repeats)
        denominator = mean(float(select(row)) for row in repeats)
        families[instance[3:]].append((numerator, denominator))
    family_values = []
    for family, cases in sorted(families.items()):
        numerator, denominator = mean(item[0] for item in cases), mean(item[1] for item in cases)
        family_values.append({"family": family, "numerator": numerator, "denominator": denominator,
                              "value": numerator / denominator if denominator else None})
    numerator = mean(item["numerator"] for item in family_values) if family_values else 0.0
    denominator = mean(item["denominator"] for item in family_values) if family_values else 0.0
    return {"status": "DEFINED" if denominator else "UNDEFINED", "value": numerator / denominator if denominator else None,
            "weighted_numerator": numerator, "weighted_denominator": denominator,
            "absolute_selected_runs": sum(bool(select(row)) for row in rows), "families": family_values}


def _cp(row):
    return row["checkpoints"][-1]


def summarize_features(rows, *, expected_identities=None):
    """Validate and summarize complete, independently checked source features."""
    rows = list(rows)
    registered = globals()["expected_identities"]()
    expected = registered if expected_identities is None else set(expected_identities)
    found, sources, common_source = set(), {}, None
    for row in rows:
        instance, seed = row.get("instance_id"), row.get("repeat_seed")
        _require(isinstance(instance, str) and re.fullmatch(r"(UC|WC|SC)-s00[0-9]", instance)
                 and _integer(seed, 93001, 93030) and row.get("family") == instance[3:], "Invalid source-run identity")
        identity = (instance, seed)
        _require(identity in expected, "Unexpected source-run identity")
        _require(identity not in found, "Duplicate source-run identity")
        found.add(identity)
        _require(row.get("status") == "PASS" and row.get("verified") is True,
                 "Unverified source features cannot be observations")
        source = row.get("source_identity")
        _require(isinstance(source, dict) and bool(source), "Missing original-source provenance")
        canonical = json.dumps(source, sort_keys=True, allow_nan=False)
        if common_source is None:
            common_source = canonical
        _require(common_source == canonical, "Mixed original-run provenance")
        if instance in sources:
            _require(sources[instance] == canonical, "Mixed source identity within instance")
        sources[instance] = canonical
        _require([cp.get("q") for cp in row.get("checkpoints", [])] == list(CHECKPOINTS),
                 "Incomplete checkpoint schedule")
        for cp, q in zip(row["checkpoints"], CHECKPOINTS):
            _validate_checkpoint(cp, q)
        _validate_operators(row.get("operators", {}))
    _require(found == expected, "Incomplete feature coverage; missing runs are not zero observations")
    rows.sort(key=lambda row: (row["instance_id"], row["repeat_seed"]))
    stagnant = lambda row: _cp(row)["stagnant"]
    improving = lambda row: _cp(row)["stagnant"] and _cp(row)["total_better"] > 0
    subsets = {"all_runs": lambda row: True, "all_stagnant": stagnant, "stagnant_with_improvement": improving}
    counts = {"runs": len(rows), "stagnant": sum(stagnant(row) for row in rows),
              "stagnant_with_improvement": sum(improving(row) for row in rows)}
    if expected == registered:
        _require(counts == {"runs": 900, "stagnant": 210, "stagnant_with_improvement": 202},
                 "Restored source counts differ from registered historical results")
    availability = {}
    for name, select in subsets.items():
        metrics = {key: _weighted(rows, lambda row, key=key: _cp(row)[key], select)
                   for key in ("b1", "b2", "total_better", "slack", "stagnation_age")}
        metrics["minimum_positive_gain"] = _weighted(rows, lambda row: _cp(row)["min_positive_gain"],
            lambda row, select=select: select(row) and _cp(row)["total_better"] > 0)
        metrics["maximum_positive_gain"] = _weighted(rows, lambda row: _cp(row)["max_positive_gain"],
            lambda row, select=select: select(row) and _cp(row)["total_better"] > 0)
        metrics["improvement_types"] = {kind: _weighted(rows, lambda row, kind=kind: _cp(row)["improvement_types"][kind], select)
                                         for kind in IMPROVEMENT_TYPES}
        metrics["mutation_model"] = [{"p": p, **_weighted(rows,
            lambda row, index=index: _cp(row)["model_probabilities"][index]["probability"], select)}
            for index, p in enumerate(PM_GRID)]
        metrics["detection"] = [{"sample_size": sample, **_weighted(rows,
            lambda row, index=index: _cp(row)["detection_probabilities"][index]["probability"], select)}
            for index, sample in enumerate(SAMPLE_BUDGETS)]
        availability[name] = metrics
    terminal_states = Counter({state: 0 for state in STATES})
    stagnant_states = Counter({state: 0 for state in STATES})
    for row in rows:
        terminal_states[_cp(row)["state"]] += 1
        if stagnant(row):
            stagnant_states[_cp(row)["state"]] += 1
    primary = _weighted(rows, lambda row: float(_cp(row)["total_better"] > 0), stagnant)
    primary.update(absolute_numerator=counts["stagnant_with_improvement"], absolute_denominator=counts["stagnant"])
    family_metrics = availability["all_runs"]
    y = [item["value"] for item in family_metrics["stagnation_age"]["families"]]
    correlations = []
    for key, x in (("b1", [item["value"] for item in family_metrics["b1"]["families"]]),
                   ("b2", [item["value"] for item in family_metrics["b2"]["families"]]),
                   ("mutation_probability_at_0.01", [item["value"] for item in family_metrics["mutation_model"][2]["families"]])):
        correlations.append({"x": key, "y": "stagnation_age", **spearman(x, y),
                             "unit": "equal-weight family means across all source runs", "p_value": None})
    operators = {}
    fields = ("crossover_applied_count", "crossover_skipped_count", "premutation_better_count",
              "final_record_count", "mutation_created_count", "mutation_preserved_count", "mutation_lost_count",
              "mutation_neither_count", "premutation_feasible_count", "final_feasible_count", "zero_mutation_count",
              "duplicate_count", "record_present_in_population_count", "record_selected_candidate_count",
              "record_pending_count", "record_absent_from_population_and_pending_count",
              "crossover_actual_change_from_first_parent_count", "crossover_novel_to_both_parents_count")
    for window, denominator in (("all_new", 5000), ("late_1000", 1000)):
        operators[window] = {field: {"absolute_count": sum(row["operators"]["groups"][window][field] for row in rows),
            "weighted_fraction": _weighted(rows, lambda row, field=field: row["operators"]["groups"][window][field] / denominator)["value"]}
            for field in fields}
        operators[window]["candidate_count"] = denominator * len(rows)
        operators[window]["record_selected_parent_slots"] = {
            "absolute_count": sum(row["operators"]["groups"][window]["record_selected_parent_slots"] for row in rows),
            "weighted_fraction_of_parent_slots": _weighted(rows,
                lambda row: row["operators"]["groups"][window]["record_selected_parent_slots"] / (2 * denominator))["value"]}
        parent_relative = {}
        for key in ("candidate_count", "feasible_parent_baseline_count", "undefined_parent_baseline_count",
                    "premutation_better_than_parent_count", "final_better_than_parent_count"):
            parent_relative[key] = {"absolute_count": sum(row["operators"]["groups"][window]["crossover_conditioned"][key] for row in rows),
                "weighted_fraction_of_all_candidates": _weighted(rows,
                    lambda row, key=key: row["operators"]["groups"][window]["crossover_conditioned"][key] / denominator)["value"]}
        defined_rate = parent_relative["feasible_parent_baseline_count"]["weighted_fraction_of_all_candidates"]
        for key in ("premutation_better_than_parent_count", "final_better_than_parent_count"):
            parent_relative[key]["conditional_fraction_defined_crossover_parents"] = (
                parent_relative[key]["weighted_fraction_of_all_candidates"] / defined_rate if defined_rate else None)
        operators[window]["crossover_conditioned"] = parent_relative
        operators[window]["feasibility_transitions"] = {
            key: {"absolute_count": sum(row["operators"]["groups"][window]["feasibility_transitions"][key] for row in rows),
                  "weighted_fraction": _weighted(rows, lambda row, key=key: row["operators"]["groups"][window]["feasibility_transitions"][key] / denominator)["value"]}
            for key in ("infeasible_to_infeasible", "infeasible_to_feasible", "feasible_to_infeasible", "feasible_to_feasible")}
    presence = [{"q": q, "mask_present_fraction": _weighted(rows,
        lambda row, index=index: float(row["operators"]["checkpoints"][index]["record_mask_present_in_population"]))["value"],
        "mean_mask_copies": _weighted(rows,
        lambda row, index=index: row["operators"]["checkpoints"][index]["record_mask_copy_count"])["value"]}
        for index, q in enumerate(CHECKPOINTS)]
    distribution = []
    bins = (("0", 0, 0), ("1", 1, 1), ("2", 2, 2), ("3–5", 3, 5), ("6–10", 6, 10),
            ("11–50", 11, 50), ("51–100", 51, 100), (">100", 101, 5050))
    for label, low, high in bins:
        distribution.append({"better_neighbors": label,
                             **{name: sum(select(row) and low <= _cp(row)["total_better"] <= high for row in rows)
                                for name, select in subsets.items()}})
    fixed = next((row for row in rows if (row["instance_id"], row["repeat_seed"]) == ("UC-s000", 93001)), None)
    return {"schema": "knapsack-stagnation-mechanisms-summary-v1", "protocol_id": PROTOCOL_ID,
            "status": "COMPLETE_EXPLORATORY" if expected == registered else "FIXTURE_SUBSET_ONLY",
            "counts": counts, "primary_restoration": primary, "state_counts": dict(terminal_states),
            "stagnant_state_counts": dict(stagnant_states), "availability": availability,
            "neighbor_distribution_absolute_runs": distribution, "operator_events": operators,
            "record_presence": presence, "spearman": correlations, "fixed_example": fixed,
            "source_identity_by_instance": {key: json.loads(value) for key, value in sources.items()},
            "new_search_evaluations": 0, "new_exact_solves": 0,
            "interpretation": "Exploratory secondary analysis of previously inspected outcomes; no causal or superiority claims",
            "bootstrap": False, "hypothesis_tests": False}


def _number(value, digits=2):
    return "невизначено" if value is None else f"{value:.{digits}f}".replace(".", ",")


def _figures(output, summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 10})
    figures = []
    stagnant = summary["availability"]["all_stagnant"]
    families = [entry["family"] for entry in stagnant["b1"]["families"]]
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.7), layout="constrained")
    x = np.arange(len(families))
    for offset, key, label, color in ((-.18, "b1", "Однобітні", "#32678e"), (.18, "b2", "Двобітні", "#d07b27")):
        values = [entry["value"] for entry in stagnant[key]["families"]]
        axes[0].bar(x + offset, [value if value is not None else 0 for value in values], .36,
                    label=label, color=color)
        for at, value in zip(x + offset, values):
            axes[0].annotate("н/в" if value is None else f"{value:.1f}", (at, value or 0),
                             xytext=(0, 3), textcoords="offset points", ha="center", fontsize=7)
    axes[0].set_xticks(x, families, rotation=45)
    axes[0].set_xlabel("Сімейство")
    axes[0].set_ylabel("Кращі сусіди на випадок застою, кількість")
    axes[0].legend(frameon=False)
    grid = np.asarray([[float("nan") if series["families"][i]["value"] is None
                        else 100 * series["families"][i]["value"]
                        for series in stagnant["mutation_model"]] for i in range(len(families))])
    image = axes[1].imshow(grid, aspect="auto", cmap="viridis", vmin=0)
    axes[1].set_xticks(range(len(PM_GRID)), [f"{100*p:g}" for p in PM_GRID])
    axes[1].set_yticks(range(len(families)), families)
    axes[1].set_xlabel("Мутація біта, %")
    axes[1].set_ylabel("Сімейство")
    for i in range(len(families)):
        for j in range(len(PM_GRID)):
            value = grid[i, j]
            axes[1].text(j, i, "н/в" if np.isnan(value) else f"{value:.3f}", ha="center", va="center", fontsize=7,
                         color="white" if not np.isnan(value) and value < np.nanmax(grid) / 2 else "black")
    fig.colorbar(image, ax=axes[1], label="Потрапляння до кращого сусіда, %")
    path = "availability.png"
    fig.savefig(output / path, dpi=180)
    plt.close(fig)
    figures.append((path, "Кращі одно- й двобітні сусіди та модель мутації маски-рекорду серед усіх випадків застою. Нулі збережено; н/в означає відсутність випадків застою в сімействі. Модель не є прогнозом успіху всього ГА."))

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.7), layout="constrained")
    for offset, window, label, color in ((-.18, "all_new", "Усі 5000", "#32678e"), (.18, "late_1000", "Останні 1000", "#d07b27")):
        group = summary["operator_events"][window]
        values = [100 * group[f"mutation_{kind}_count"]["weighted_fraction"] for kind in ("created", "preserved", "lost")]
        axes[0].bar(np.arange(3) + offset, values, .36, label=label, color=color)
        for at, value in zip(np.arange(3) + offset, values):
            axes[0].annotate(f"{value:.3f}", (at, value), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
        feasible = [100 * group[field]["weighted_fraction"] for field in ("premutation_feasible_count", "final_feasible_count")]
        axes[1].bar(np.arange(2) + offset, feasible, .36, label=label, color=color)
        for at, value in zip(np.arange(2) + offset, feasible):
            axes[1].annotate(f"{value:.1f}", (at, value), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
    axes[0].set_xticks(range(3), ["Створено", "Збережено", "Втрачено"])
    axes[0].set_xlabel("Подія під час мутації")
    axes[0].set_ylabel("Частка всіх кандидатів, %")
    axes[0].legend(frameon=False)
    axes[1].set_xticks(range(2), ["До мутації", "Після мутації"])
    axes[1].set_xlabel("Етап створення кандидата")
    axes[1].set_ylabel("Допустимі кандидати, %")
    axes[1].set_ylim(0, 105)
    axes[1].legend(frameon=False)
    path = "operator_events.png"
    fig.savefig(output / path, dpi=180)
    plt.close(fig)
    figures.append((path, "Події мутації відносно рекорду перед оцінюванням кандидата та допустимість до і після мутації. Збереження означає перевищення попереднього рекорду, не збереження всієї проміжної цінності. Втрата стосується лише неоціненого проміжного набору."))

    fig, ax = plt.subplots(figsize=(8.4, 4.8), layout="constrained")
    for subset, label, color in (("all_stagnant", "Усі випадки застою", "#32678e"),
                                  ("stagnant_with_improvement", "Застій із кращим сусідом", "#d07b27")):
        series = summary["availability"][subset]["detection"]
        if all(item["value"] is None for item in series):
            continue
        y = [100 * item["value"] for item in series]
        ax.plot(SAMPLE_BUDGETS, y, marker="o", label=label, color=color)
        for sample, value in zip(SAMPLE_BUDGETS, y):
            ax.annotate(f"{value:.2f}", (sample, value), xytext=(0, 7 if subset == "all_stagnant" else -13),
                        textcoords="offset points", ha="center", fontsize=9)
    ax.set_xlabel("Перевірені різні сусіди, кількість")
    ax.set_ylabel("Імовірність виявити покращення, %")
    ax.set_xticks(SAMPLE_BUDGETS)
    ax.set_ylim(0, 105)
    ax.grid(axis="y", alpha=.25)
    ax.legend(frameon=False)
    path = "sampling_detection.png"
    fig.savefig(output / path, dpi=180)
    plt.close(fig)
    figures.append((path, "Точна модель випадкової перевірки сусідів без повернення. Перша крива охоплює всі випадки застою, включно з нульовою кількістю покращень; друга умовна на наявності кращого сусіда. Це аналітичні ймовірності, не нові експерименти."))
    return figures


def write_report(output, rows, summary):
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific reports are CI-only")
    output = Path(output).resolve()
    _require(not output.is_relative_to(ROOT), "Scientific output must be outside checkout")
    _require(summary.get("status") == "COMPLETE_EXPLORATORY", "Incomplete source cannot become final report")
    output.mkdir(parents=True, exist_ok=True)
    figures = _figures(output, summary)
    availability, counts = summary["availability"], summary["counts"]
    primary = summary["primary_restoration"]
    lines = ["# Доступність покращень і причини застою генетичного алгоритму", "",
        "## Питання та метод", "",
        "Перевірено, скільки кращих допустимих сусідів залишається біля збереженого рекорду, як схрещування й мутація змінюють кандидатів та наскільки часто вибіркова перевірка здатна виявити доступне покращення.", "",
        "Вторинний аналіз використовує вже завершені 900 запусків звичайного генетичного алгоритму на 30 задачах рюкзака зі 100 предметами. Популяція дорівнює 30, мутація біта становить 1%, імовірність рівномірного схрещування 90%. Нового пошуку, адаптації параметрів і повторного визначення точних оптимумів не виконано.", "",
        "Попередні результати були відомі до постановки додаткових питань. Тому наведені залежності є дослідницькими, а не новою підтверджувальною перевіркою гіпотези. Усереднено повторення задачі, потім задачі сімейства; десять сімейств мають рівну вагу. Умовні показники отримано як відношення зваженого чисельника й знаменника.", "",
        "## Доступність покращень", "",
        f"Відновлено {counts['runs']} запусків. Застій тривалістю щонайменше 1000 оцінювань зафіксовано у {counts['stagnant']} випадках; у {counts['stagnant_with_improvement']} із них існував кращий допустимий одно- або двобітний сусід. Сімейно-зважена частка дорівнює {_number(100 * primary['value'])}%. Випадки без кращих сусідів не вилучено.", "",
        "Таблиця 1. Доступні покращення наприкінці пошуку", "",
        "| Вибірка | Запуски | Однобітні сусіди, середнє | Двобітні сусіди, середнє | Вільна місткість, середнє |",
        "|---|---:|---:|---:|---:|"]
    for name, label in (("all_runs", "Усі запуски"), ("all_stagnant", "Усі випадки застою"),
                         ("stagnant_with_improvement", "Застій із кращим сусідом")):
        item = availability[name]
        lines.append(f"| {label} | {item['b1']['absolute_selected_runs']} | {_number(item['b1']['value'])} | {_number(item['b2']['value'])} | {_number(item['slack']['value'])} |")
    selected = availability["stagnant_with_improvement"]
    lines += ["", f"Серед випадків застою з доступним покращенням середня найменша додатна зміна цінності становить {_number(selected['minimum_positive_gain']['value'])}, а середня найбільша {_number(selected['maximum_positive_gain']['value'])}. Це середні за окремими масками, не мінімум і максимум усієї серії.", "",
        "Таблиця 2. Тип кращого сусіда серед усіх випадків застою", "",
        "| Зміна набору | Кращі сусіди на випадок застою, середнє |", "|---|---:|"]
    for kind, label in (("add_one", "Додавання одного предмета"), ("remove_one", "Вилучення одного предмета"),
                         ("swap_one", "Обмін одного предмета на інший"), ("add_two", "Додавання двох предметів"),
                         ("remove_two", "Вилучення двох предметів")):
        lines.append(f"| {label} | {_number(availability['all_stagnant']['improvement_types'][kind]['value'])} |")
    lines += ["", "Нехай b₁ і b₂ означають кількість кращих допустимих сусідів із рівно однією та двома змінами бітів. Для незалежної мутації незмінної маски-рекорду ймовірність потрапити саме до таких сусідів становить:", "",
        "P≤₂(p) = b₁p(1 − p)⁹⁹ + b₂p²(1 − p)⁹⁸. (1)", "",
        "Формула враховує точні зміни без додаткових мутацій. Вона не описує весь генетичний алгоритм, інших батьків, схрещування чи переходи з трьома й більше змінами. Найбільше значення цієї моделі не є рекомендацією найкращої мутації для всього пошуку.", ""]
    for path, caption in figures[:1]:
        lines += [f"![{caption}]({path})", "", f"Рисунок 1. {caption}", ""]
    lines += ["## Роль схрещування та мутації", "",
        "Зі збережених операторних рішень відновлено проміжну маску після схрещування та остаточну маску після мутації. Обидва набори зіставлено з одним допустимим рекордом, відомим безпосередньо перед оцінюванням остаточного кандидата. Проміжні оцінки обчислено після пошуку; вони не керували алгоритмом.", "",
        "Мутація створює покращення, якщо проміжний набір не перевищував рекорд, а остаточний перевищив. Покращення зберігається, якщо обидва набори перевищують рекорд. Воно втрачається, якщо проміжний набір був кращим, але остаточний став недопустимим або не перевищив рекорд. Збереження не означає незмінності цінності проміжного набору.", "",
        "Таблиця 3. Події операторів та допустимість, частка кандидатів у відсотках", "",
        "| Показник | Усі 5000 оцінювань | Останні 1000 оцінювань |", "|---|---:|---:|"]
    for field, label in (("mutation_created_count", "Мутація створила покращення"),
                         ("mutation_preserved_count", "Мутація зберегла перевищення рекорду"),
                         ("mutation_lost_count", "Мутація втратила проміжне покращення"),
                         ("premutation_feasible_count", "Допустимість до мутації"),
                         ("final_feasible_count", "Допустимість після мутації"),
                         ("duplicate_count", "Повторно оцінені маски"),
                         ("record_selected_candidate_count", "Рекорд вибрано хоча б одним батьком")):
        values = [100 * summary["operator_events"][window][field]["weighted_fraction"] for window in ("all_new", "late_1000")]
        lines.append(f"| {label} | {_number(values[0], 3)} | {_number(values[1], 3)} |")
    path, caption = figures[1]
    lines += ["", f"![{caption}]({path})", "", f"Рисунок 2. {caption}", "",
        "Втрата проміжного покращення не означає відкидання вже оціненого рекорду відбором. Кожний кращий допустимий остаточний кандидат одразу врахований у рекорді, навіть якщо покоління не завершено. Відсутність першої маски-рекорду в завершеній популяції також не доводить помилки елітизму: кандидат може ще належати незавершеному поколінню, а за рівності цінностей може зберігатися інша маска.", "",
        "## Вибіркова перевірка сусідства", "",
        "Для рівноймовірної вибірки s різних сусідів із 5050, серед яких b = b₁ + b₂ кращі, імовірність знайти хоча б одне покращення дорівнює:", "",
        "Pвиявлення(s) = 1 − C(5050 − b, s) / C(5050, s). (2)", "",
        "Коли s перевищує кількість сусідів без покращення, імовірність дорівнює одиниці. За b = 0 вона дорівнює нулю. Обчислення є точним комбінаторним розрахунком, а не випадковим моделюванням.", "",
        "Таблиця 4. Імовірність виявлення покращення вибірковою перевіркою, %", "",
        "| Перевірені сусіди | Усі випадки застою | Застій із кращим сусідом |", "|---:|---:|---:|"]
    for index, sample in enumerate(SAMPLE_BUDGETS):
        values = [availability[name]["detection"][index]["value"] for name in ("all_stagnant", "stagnant_with_improvement")]
        lines.append(f"| {sample} | {_number(None if values[0] is None else 100 * values[0])} | {_number(None if values[1] is None else 100 * values[1])} |")
    path, caption = figures[2]
    lines += ["", f"![{caption}]({path})", "", f"Рисунок 3. {caption}", "",
        "Знайдений кращий сусід спростовує локальність маски у визначеному околі. Відсутність знахідки у неповній вибірці не підтверджує локального максимуму. Для використання діагностики під час нового пошуку її оцінювання потрібно включити до спільного бюджету.", "",
        "## Наперед визначений приклад", ""]
    fixed = summary["fixed_example"]
    _require(fixed is not None, "Missing prespecified UC-s000 example")
    lines += ["Для задачі UC-s000 використано повторення 93001 незалежно від його результату.", "",
        "Таблиця 5. Зміна доступності покращень у визначеному повторенні", "",
        "| Нові оцінювання | Тривалість застою | Кращі однобітні сусіди | Кращі двобітні сусіди | Рекордна маска в популяції |",
        "|---:|---:|---:|---:|---|"]
    for cp, presence in zip(fixed["checkpoints"], fixed["operators"]["checkpoints"]):
        lines.append(f"| {cp['q']} | {cp['stagnation_age']} | {cp['b1']} | {cp['b2']} | {'Так' if presence['record_mask_present_in_population'] else 'Ні'} |")
    lines += ["", "## Описові залежності", "",
        "Коефіцієнти Спірмена обчислено між десятьма сімейними середніми за всіма 900 запусками, не між мільйонами кандидатів і не лише відібраними випадками застою. Для однакових значень використано середні ранги. Сталий ряд має невизначений коефіцієнт, а не нуль.", "",
        "Таблиця 6. Описовий зв’язок доступності покращень із тривалістю застою", "",
        "| Показник | Коефіцієнт Спірмена | Сімейства |", "|---|---:|---:|"]
    labels = {"b1": "Кращі однобітні сусіди", "b2": "Кращі двобітні сусіди", "mutation_probability_at_0.01": "Модельна ймовірність за мутації 1%"}
    for item in summary["spearman"]:
        lines.append(f"| {labels[item['x']]} | {_number(item['rho'], 3)} | {item['n']} |")
    lines += ["", "Ці коефіцієнти не доводять причинного впливу кількості сусідів на застій. Зв’язки між параметрами, прямо задані формулою, не розглядаються як емпіричне відкриття. P-значення, бутстреп та додаткові перевірки переваги не обчислювалися.", "",
        "## Висновки та обмеження", "",
        "Наявність кращого сусіда та його фактичне знаходження є різними подіями. Імовірність мутаційного переходу залежить не лише від радіуса зміни, а й від кількості доступних покращень. Перевірка операторних проміжних станів показує, на якому етапі виникає або втрачається перевищення попереднього рекорду.", "",
        "Наведені результати стосуються однієї сталої конфігурації генетичного алгоритму, визначених задач, початків і бюджету. Повні сертифікати стосуються окремих масок, а не всієї популяції чи замкненості плато. Модель мутації, комбінаторні ймовірності та описові кореляції не підтверджують переваги адаптивного контролера. Наступний експеримент потребує окремого протоколу, контрольованого правила адаптації та обліку вартості діагностики.", "",
        "## Додаток. Походження й облік", "",
        "Використано незмінні журнали попередньої серії та незалежні сертифікати одно- й двобітного сусідства. Нових пошукових оцінювань і точних розв’язань не виконано. Повторне обчислення проміжних оцінок є витратою перевірки після пошуку, не прихованим продовженням алгоритму. Первинні висновки попередньої серії не переписано.", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    table_paths = {}
    for key, payload in (("family_features", {name: value for name, value in availability.items()}),
                         ("operator_events", summary["operator_events"]),
                         ("spearman", summary["spearman"]),
                         ("neighbor_distribution", summary["neighbor_distribution_absolute_runs"]),
                         ("fixed_example", fixed)):
        path = f"{key}.json"
        (output / path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        table_paths[key] = path
    return {"report": "report.md", "figures": [path for path, _ in figures], "tables": table_paths}

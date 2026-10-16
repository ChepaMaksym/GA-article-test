"""Exact development-grid selection and descriptive, conditional analysis.

No search kernel, production evaluator, bootstrap, or holdout analysis is used.
Transport identities and exact-optimum provenance remain the outer CI contract's
responsibility. Every reported best mask is nevertheless evaluated independently.
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
import json
import math
from numbers import Integral
import os
from pathlib import Path
import re


PROTOCOL = "GA-KNAPSACK-BASIC-PARAMETERS-V1"
MUTATIONS = (Fraction(0), Fraction(1, 200), Fraction(1, 100), Fraction(3, 100), Fraction(2, 25))
CROSSOVERS = (Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(9, 10), Fraction(1))
POPULATIONS = (10, 20, 30, 50, 100)
CLASSES = ("UC", "WC", "SC")
TASKS = tuple(f"{kind}-s{index:03d}" for kind in CLASSES for index in range(10))
SEEDS = tuple(range(81001, 81011))
BASELINE = (Fraction(1, 100), Fraction(9, 10), 30)
BUDGET = 5000


def _require(condition, message):
    if not condition:
        raise ValueError("Basic-parameters analysis: " + message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "CI-only analysis")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test", "wrong repository")
    _require(os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover", "wrong branch")


def _int(value, minimum, label):
    _require(isinstance(value, Integral) and not isinstance(value, bool) and value >= minimum, label)
    return int(value)


def _number(value, label):
    _require(type(value) in (int, float) and math.isfinite(value), label)
    return Fraction(str(value))


def _packed(value):
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def _unpacked(value):
    _require(type(value) is dict and set(value) == {"numerator", "denominator"}, "rational fields")
    _require(isinstance(value["numerator"], Integral) and not isinstance(value["numerator"], bool), "rational numerator")
    numerator = int(value["numerator"])
    denominator = _int(value["denominator"], 1, "rational denominator")
    return Fraction(numerator, denominator)


def _mean(values):
    values = list(values)
    _require(bool(values), "empty mean")
    return sum(values, Fraction(0)) / len(values)


def _token(value):
    return format(float(value), ".12g").replace(".", "p")


def configuration_id(p_m, p_c, population):
    """Independent transcription of the frozen kernel's configuration naming."""
    return f"m{_token(Fraction(p_m) * 100)}-c{_token(Fraction(p_c))}-n{population}"


def average_ranks(values):
    """One-based ranks, with exact average ranks for ties."""
    values = [Fraction(value) for value in values]
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [Fraction(0)] * len(values)
    first = 0
    while first < len(order):
        last = first + 1
        while last < len(order) and values[order[last]] == values[order[first]]:
            last += 1
        rank = Fraction(first + 1 + last, 2)
        for index in order[first:last]:
            ranks[index] = rank
        first = last
    return ranks


def descriptive_spearman(x, y):
    """A descriptive rank coefficient, with no p-value or independence claim."""
    _require(len(x) == len(y) and len(x) >= 2, "Spearman requires paired observations")
    a, b = average_ranks(x), average_ranks(y)
    centered_a = [value - _mean(a) for value in a]
    centered_b = [value - _mean(b) for value in b]
    var_a = sum((value * value for value in centered_a), Fraction(0))
    var_b = sum((value * value for value in centered_b), Fraction(0))
    if not var_a or not var_b:
        return {"status": "UNDEFINED", "rho": None, "n": len(x), "reason": "CONSTANT_SERIES",
                "inference": "DESCRIPTIVE_ONLY", "tie_rule": "AVERAGE_RANKS"}
    covariance = sum((first * second for first, second in zip(centered_a, centered_b, strict=True)), Fraction(0))
    return {"status": "DEFINED", "rho": float(covariance) / math.sqrt(float(var_a * var_b)),
            "n": len(x), "reason": None, "inference": "DESCRIPTIVE_ONLY", "tie_rule": "AVERAGE_RANKS"}


def rank_configurations(summaries):
    """Exact registered mean -> worst family -> population -> numeric tuple order."""
    _require(bool(summaries), "no configurations to rank")
    _require(len({row["configuration_id"] for row in summaries}) == len(summaries), "duplicate ranking identity")
    return sorted(summaries, key=lambda row: (
        _unpacked(row["mean_gap_exact"]), _unpacked(row["worst_family_gap_exact"]),
        row["population_size"], _unpacked(row["p_m_exact"]), _unpacked(row["p_c_exact"]),
        row["population_size"]))


def _instance(value):
    def take(name):
        return value[name] if isinstance(value, dict) else getattr(value, name)
    n, capacity = _int(take("n"), 1, "instance dimension"), _int(take("capacity"), 0, "capacity")
    _require(n == 100, "registered instances must have 100 items")
    weights, profits = list(take("weights")), list(take("profits"))
    _require(len(weights) == len(profits) == n, "raw instance lengths")
    return {"n": n, "capacity": capacity,
            "weights": [_int(v, 1, "item weight") for v in weights],
            "profits": [_int(v, 1, "item profit") for v in profits]}


def _witness(instance, mask):
    _require(type(mask) is str and len(mask) == instance["n"] and set(mask) <= {"0", "1"}, "best witness mask")
    weight = profit = 0
    for position, bit in enumerate(mask):
        if bit == "1":
            weight += instance["weights"][position]
            profit += instance["profits"][position]
    return weight, profit, weight <= instance["capacity"]


def aggregate(rows, instances, optima):
    """Validate all 37500 compact rows and return a JSON-safe development report."""
    _ci_only()
    _require(type(rows) is list and len(rows) == 37500, "expected exactly 37500 development runs")
    _require(set(instances) == set(optima) == set(TASKS), "development instance/optimum identities")
    raw = {task: _instance(instances[task]) for task in TASKS}
    optimum_values = {task: _int(optima[task], 1, "external exact optimum") for task in TASKS}
    _require(all(optimum_values[task] <= sum(raw[task]["profits"]) for task in TASKS), "impossible external optimum")
    grid = tuple((p_m, p_c, population) for p_m in MUTATIONS for p_c in CROSSOVERS for population in POPULATIONS)
    expected = {(task, seed, config) for task in TASKS for seed in SEEDS for config in grid}
    seen, implementation_shas, source_fingerprints = set(), set(), set()
    grouped = defaultdict(dict)
    initial_by_condition = {}
    logical_requests = physical_requests = 0
    required = {
        "protocol_id", "source_manifest_sha256", "instance_id", "class_label", "family", "index", "phase", "repeat_seed", "seed",
        "configuration_id", "mutation_numerator", "crossover_probability", "population_size", "p_m", "p_c", "N", "n",
        "best_mask", "best_weight", "best_profit", "best_request", "budget", "logical_requests",
        "physical_evaluations", "known_initial_requests", "complete_generations", "terminal_partial",
        "duplicate_count", "invalid_request_count", "initial_best_profit", "exact_optimum", "relative_gap",
        "verified", "verification_status", "verification", "implementation_commit_sha",
    }
    for row in rows:
        _require(type(row) is dict and required <= set(row), "compact row fields")
        _require(row["protocol_id"] == PROTOCOL, "wrong source protocol")
        task = row["instance_id"]
        _require(task in raw and row["phase"] == "main", "wrong task/phase or holdout search exposed")
        kind, family = task.split("-")
        index = int(family[1:])
        _require(row["class_label"] == kind and row["family"] == family and
                 type(row["index"]) is int and row["index"] == index, "task metadata mismatch")
        seed = _int(row["repeat_seed"], 0, "repeat seed")
        _require(type(row["seed"]) is int and row["seed"] == seed and seed in SEEDS, "seed identity")
        p_m, p_c = _number(row["p_m"], "mutation probability"), _number(row["p_c"], "crossover probability")
        population = _int(row["population_size"], 2, "population size")
        config = (p_m, p_c, population)
        identity = (task, seed, config)
        _require(identity in expected and identity not in seen, "duplicate or unregistered run identity")
        seen.add(identity)
        _require(row["configuration_id"] == configuration_id(*config) and
                 _number(row["mutation_numerator"], "mutation numerator") == 100 * p_m and
                 _number(row["crossover_probability"], "crossover alias") == p_c and
                 type(row["N"]) is int and row["N"] == population and
                 type(row["n"]) is int and row["n"] == 100, "configuration aliases")
        for field, value in (("budget", BUDGET), ("logical_requests", BUDGET),
                             ("physical_evaluations", BUDGET - population), ("known_initial_requests", population),
                             ("complete_generations", (BUDGET - population) // (population - 1))):
            _require(type(row[field]) is int and row[field] == value, "accounting: " + field)
        _require(type(row["terminal_partial"]) is bool and
                 row["terminal_partial"] == bool((BUDGET - population) % (population - 1)), "partial generation accounting")
        for field in ("duplicate_count", "invalid_request_count"):
            _require(_int(row[field], 0, field) <= BUDGET, field + " range")
        _require(row["verified"] is True and row["verification_status"] == "PASS_REPLAY", "unverified run")
        verdict = row["verification"]
        _require(type(verdict) is dict and verdict.get("status") == "PASS_REPLAY" and
                 verdict.get("rng_and_operator_replay_verified") is True and
                 type(verdict.get("exact_requests_verified")) is int and verdict["exact_requests_verified"] == BUDGET,
                 "independent replay verdict")
        sha = row["implementation_commit_sha"]
        _require(type(sha) is str and re.fullmatch(r"[0-9a-f]{40}", sha), "implementation SHA")
        implementation_shas.add(sha)
        fingerprint = row["source_manifest_sha256"]
        _require(type(fingerprint) is str and re.fullmatch(r"[0-9a-f]{64}", fingerprint), "source manifest hash")
        source_fingerprints.add(fingerprint)
        weight, profit, feasible = _witness(raw[task], row["best_mask"])
        _require(feasible and type(row["best_weight"]) is int and row["best_weight"] == weight and
                 type(row["best_profit"]) is int and row["best_profit"] == profit, "independent best witness evaluation")
        _require(type(row["exact_optimum"]) is int and row["exact_optimum"] == optimum_values[task] and
                 profit <= optimum_values[task], "external optimum or profit contradiction")
        request = _int(row["best_request"], 1, "best request")
        _require(request <= BUDGET, "best request beyond budget")
        initial = _int(row["initial_best_profit"], 0, "initial best profit")
        _require(initial <= profit, "record worsened below initialization")
        _require((request <= population) == (initial == profit), "first record occurrence versus initialization")
        if p_m == 0 and p_c == 0:
            _require(initial == profit, "copy-only configuration cannot improve its initial record")
        for field in ("best_mask", "best_weight", "best_profit", "best_request", "logical_requests", "physical_evaluations"):
            _require(verdict.get(field) == row[field], "compact row disagrees with replay: " + field)
        gap = Fraction(optimum_values[task] - profit, optimum_values[task])
        reported_gap = row["relative_gap"]
        _require(type(reported_gap) in (int, float) and math.isfinite(reported_gap) and
                 reported_gap == float(gap), "reported floating diagnostic gap")
        initial_key = (task, seed, population)
        if initial_key in initial_by_condition:
            _require(initial_by_condition[initial_key] == initial, "initial bank differs between parameter settings")
        else:
            initial_by_condition[initial_key] = initial
        grouped[config][(task, seed)] = {"gap": gap,
            "initial_gap": Fraction(optimum_values[task] - initial, optimum_values[task]),
            "invalid": Fraction(row["invalid_request_count"], BUDGET),
            "duplicates": Fraction(row["duplicate_count"], BUDGET),
            "initial": initial, "best": profit, "best_request": request}
        logical_requests += row["logical_requests"]
        physical_requests += row["physical_evaluations"]
    _require(seen == expected and len(implementation_shas) == len(source_fingerprints) == 1,
             "missing runs or mixed implementation/source SHAs")
    for task in TASKS:
        for seed in SEEDS:
            initial_values = [initial_by_condition[(task, seed, size)] for size in POPULATIONS]
            _require(initial_values == sorted(initial_values), "nested bank prefix record decreased with population")

    summaries = []
    for config in grid:
        data = grouped[config]
        family_metrics = {}
        for metric in ("gap", "initial_gap", "invalid", "duplicates"):
            task_means = {task: _mean(data[(task, seed)][metric] for seed in SEEDS) for task in TASKS}
            family_metrics[metric] = {
                f"s{index:03d}": _mean(task_means[f"{kind}-s{index:03d}"] for kind in CLASSES)
                for index in range(10)}
        mean_gap, worst_gap = _mean(family_metrics["gap"].values()), max(family_metrics["gap"].values())
        p_m, p_c, population = config
        summaries.append({"configuration_id": configuration_id(*config),
            "p_m": float(p_m), "p_c": float(p_c), "population_size": population,
            "p_m_exact": _packed(p_m), "p_c_exact": _packed(p_c),
            "run_count": 300, "task_count": 30, "family_count": 10,
            "mean_gap": float(mean_gap), "mean_gap_exact": _packed(mean_gap),
            "worst_family_gap": float(worst_gap), "worst_family_gap_exact": _packed(worst_gap),
            "family_gaps": [{"family": family, "mean_gap": float(value), "mean_gap_exact": _packed(value)}
                            for family, value in sorted(family_metrics["gap"].items())],
            "mean_initial_gap": float(_mean(family_metrics["initial_gap"].values())),
            "mean_initial_gap_exact": _packed(_mean(family_metrics["initial_gap"].values())),
            "mean_normalized_record_gain": float(_mean(family_metrics["initial_gap"].values()) - mean_gap),
            "mean_invalid_fraction": float(_mean(family_metrics["invalid"].values())),
            "mean_duplicate_fraction": float(_mean(family_metrics["duplicates"].values())),
            "complete_generations": (BUDGET - population) // (population - 1),
            "terminal_prefix_children": (BUDGET - population) % (population - 1)})
    ranked = rank_configurations(summaries)
    for rank, summary in enumerate(ranked, 1):
        summary["development_rank"] = rank
    lookup = {config: summary for config, summary in zip(grid, summaries, strict=True)}
    conditional = []
    axes = ("p_m", "p_c", "population_size")
    levels = (MUTATIONS, CROSSOVERS, POPULATIONS)
    for axis in range(3):
        other_axes = [index for index in range(3) if index != axis]
        for first in levels[other_axes[0]]:
            for second in levels[other_axes[1]]:
                configs = []
                for level in levels[axis]:
                    config_values = [None, None, None]
                    config_values[axis] = level
                    config_values[other_axes[0]], config_values[other_axes[1]] = first, second
                    configs.append(tuple(config_values))
                values = [_unpacked(lookup[config]["mean_gap_exact"]) for config in configs]
                anchor = values[list(levels[axis]).index(BASELINE[axis])]
                conditional.append({"varying_parameter": axes[axis],
                    "fixed_parameters": {axes[other_axes[0]]: float(first) if isinstance(first, Fraction) else first,
                                         axes[other_axes[1]]: float(second) if isinstance(second, Fraction) else second},
                    "reference_level": float(BASELINE[axis]),
                    "points": [{"level": float(config[axis]) if isinstance(config[axis], Fraction) else config[axis],
                                "configuration_id": configuration_id(*config), "mean_gap": float(value),
                                "mean_gap_exact": _packed(value),
                                "gap_difference_from_reference": float(value - anchor),
                                "gap_difference_from_reference_exact": _packed(value - anchor)}
                               for config, value in zip(configs, values, strict=True)],
                    "spearman": descriptive_spearman(list(levels[axis]), values),
                    "scope": "OTHER_TWO_PARAMETERS_FIXED; DEVELOPMENT_DESCRIPTIVE_ONLY"})
    example = {}
    for config in grid:
        value = grouped[config][("UC-s000", 81001)]
        example[configuration_id(*config)] = {"initial_best_profit": value["initial"],
            "best_profit": value["best"], "best_request": value["best_request"]}
    return {"schema": "basic-parameters-development-analysis-v1", "protocol_id": PROTOCOL,
        "scope": "DEVELOPMENT_FIXED_GRID_ONLY", "status": "COMPLETE_DEVELOPMENT_GRID",
        "runs": len(rows), "configuration_count": 125, "task_count": 30, "family_count": 10,
        "logical_requests": logical_requests, "physical_search_evaluations": physical_requests,
        "independent_best_witness_checks": len(rows), "implementation_sha": next(iter(implementation_shas)),
        "source_manifest_sha256": next(iter(source_fingerprints)),
        "weighting": "seeds -> task -> three classes per family -> ten equal families",
        "selection_rule": "exact mean gap; exact worst family gap; smaller population; numeric lexicographic (p_m,p_c,population)",
        "baseline_id": configuration_id(*BASELINE), "winner_id": ranked[0]["configuration_id"],
        "winner": ranked[0], "ranking": [row["configuration_id"] for row in ranked],
        "configurations": summaries, "conditional_effects": conditional,
        "example_expectations": example,
        "bootstrap_resamples": 0, "superiority_tested": False, "holdout_statistics_performed": False,
        "adaptive_controller_admitted_by_this_report": False,
        "evidence_scope": "Best witnesses independently evaluated; external optima and source transports must be authenticated by the outer contract.",
        "limitations": ["Selected on already known development families; not an unseen-test performance estimate.",
                       "Spearman describes five conditional configuration means, not independent runs or causal mechanisms.",
                       "Larger initial prefixes can improve the initial best; larger populations allow fewer generations at the same total budget.",
                       "A monotone best-so-far record is not evidence of superiority; no holdout inference is performed."]}


def _example_traces(report):
    supplied = report.get("example_trajectories")
    if supplied is None:
        return []
    _require(type(supplied) is list, "archived example traces must be a list")
    wanted = {report["baseline_id"], report["winner_id"]}
    configs = {row["configuration_id"]: row for row in report["configurations"]}
    selected = {}
    for trace in supplied:
        _require(type(trace) is dict and trace.get("instance_id") == "UC-s000" and
                 trace.get("repeat_seed") == 81001 and trace.get("configuration_id") in configs, "example trace identity")
        config_id = trace["configuration_id"]
        if config_id not in wanted:
            continue
        _require(config_id not in selected, "duplicate selected example trace")
        config = configs[config_id]
        _require(trace.get("p_m") == config["p_m"] and trace.get("p_c") == config["p_c"] and
                 trace.get("N") == config["population_size"], "example trace parameters")
        points = trace.get("points")
        population = config["population_size"]
        requests = [population] + list(range(2 * population - 1, BUDGET + 1, population - 1))
        if requests[-1] != BUDGET:
            requests.append(BUDGET)
        _require(type(points) is list and [point.get("request") for point in points] == requests,
                 "missing or fabricated example checkpoints")
        expectation = report["example_expectations"][config_id]
        _require(points[0]["record_profit"] == expectation["initial_best_profit"] and
                 points[-1]["record_profit"] == expectation["best_profit"], "example record endpoints")
        records = []
        for index, point in enumerate(points):
            records.append(_int(point["record_profit"], 0, "example record"))
            _require(type(point["generation"]) is int and point["generation"] == index, "example generation number")
            complete = index == 0 or point["request"] - points[index - 1]["request"] == population - 1
            _require(type(point["complete"]) is bool and point["complete"] == complete, "example partial flag")
            for field in ("unique_fraction", "feasible_fraction"):
                value = point[field]
                _require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
                         "example population fraction")
            _require(point["unique_fraction"] >= 1 / population, "example unique fraction is not a pairwise distance")
            mean = point["mean_feasible_profit"]
            _require((point["feasible_fraction"] == 0 and mean is None) or
                     (point["feasible_fraction"] > 0 and type(mean) in (int, float) and math.isfinite(mean) and
                      0 <= mean <= point["record_profit"]),
                     "example mean/feasible fraction")
            if not complete:
                _require(all(point[field] == points[index - 1][field] for field in
                             ("mean_feasible_profit", "unique_fraction", "feasible_fraction")), "partial prefix changed population statistics")
        _require(records == sorted(records), "example record decreased")
        selected[config_id] = trace
    _require(set(selected) == wanted, "required baseline/winner example missing")
    order = ([report["baseline_id"]] if len(wanted) == 1 else [report["baseline_id"], report["winner_id"]])
    return [selected[key] for key in order]


def write_report(report, output):
    """Write development-only figures/answers; optional histories must be archived."""
    _ci_only()
    _require(report.get("protocol_id") == PROTOCOL and report.get("scope") == "DEVELOPMENT_FIXED_GRID_ONLY",
             "wrong report scope")
    traces = _example_traces(report)
    import matplotlib.pyplot as plt
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    figures = []
    configs = report["configurations"]
    maximum = max((100 * row["mean_gap"] for row in configs), default=0) or 1
    for population in POPULATIONS:
        values = [[next(row["mean_gap"] * 100 for row in configs if
                        row["population_size"] == population and row["p_m"] == float(p_m) and row["p_c"] == float(p_c))
                   for p_c in CROSSOVERS] for p_m in MUTATIONS]
        fig, axis = plt.subplots(figsize=(7.5, 5), layout="constrained")
        artist = axis.imshow(values, origin="lower", vmin=0, vmax=maximum, cmap="viridis_r", aspect="auto")
        axis.set_xticks(range(5), [f"{100 * float(v):g}" for v in CROSSOVERS])
        axis.set_yticks(range(5), [f"{100 * float(v):g}" for v in MUTATIONS])
        axis.set_xlabel("Імовірність схрещування, %")
        axis.set_ylabel("Мутація одного біта, %")
        axis.set_title(f"Які сталі комбінації кращі? Популяція {population}")
        for i in range(5):
            for j in range(5):
                axis.text(j, i, f"{values[i][j]:.3g}", ha="center", va="center", color="black",
                          bbox={"facecolor": "white", "alpha": 0.65, "edgecolor": "none", "pad": 1})
        fig.colorbar(artist, ax=axis, label="Кінцеве відставання від OPT, %; менше краще")
        path = f"heatmap-N{population}.png"
        fig.savefig(output / path, dpi=160)
        plt.close(fig)
        figures.append(path)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), layout="constrained")
    parameter_names = ("p_m", "p_c", "population_size")
    baseline_values = {"p_m": 0.01, "p_c": 0.9, "population_size": 30}
    for axis, parameter in zip(axes, parameter_names, strict=True):
        for curve in report["conditional_effects"]:
            if curve["varying_parameter"] != parameter:
                continue
            highlighted = all(baseline_values[key] == value for key, value in curve["fixed_parameters"].items())
            multiplier = 1 if parameter == "population_size" else 100
            axis.plot([point["level"] * multiplier for point in curve["points"]],
                      [point["mean_gap"] * 100 for point in curve["points"]],
                      color="#155e9b" if highlighted else "#888888", alpha=1 if highlighted else 0.22,
                      marker="o" if highlighted else None, linewidth=2 if highlighted else 0.8,
                      label="Інші два параметри опорні" if highlighted else None)
        axis.set_xlabel({"p_m": "Мутація біта, %", "p_c": "Схрещування, %", "population_size": "Популяція"}[parameter])
        axis.set_ylabel("Кінцеве відставання, %")
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    fig.suptitle("Що змінюється за фіксованих інших параметрів? Сірі лінії — різні умови, не довірчі межі")
    fig.savefig(output / "conditional-effects.png", dpi=160)
    plt.close(fig)
    figures.append("conditional-effects.png")

    fig, axes = plt.subplots(2, 1, figsize=(8, 7), layout="constrained")
    anchor = [next(row for row in configs if row["population_size"] == size and row["p_m"] == 0.01 and row["p_c"] == 0.9)
              for size in POPULATIONS]
    axes[0].plot(POPULATIONS, [100 * row["mean_initial_gap"] for row in anchor], "o--", label="Початковий рекорд")
    axes[0].plot(POPULATIONS, [100 * row["mean_gap"] for row in anchor], "o-", label="Кінцевий рекорд")
    axes[0].set_ylabel("Відставання від OPT, %")
    axes[0].set_title("Що дала більша популяція? Мутація 1%, схрещування 90%")
    axes[0].legend()
    axes[1].plot(POPULATIONS, [row["complete_generations"] for row in anchor], "o-", color="#555555")
    axes[1].set_ylabel("Повні покоління")
    axes[1].set_title("Рівно 5000 загальних оцінювань, включно з початком")
    for axis in axes:
        axis.set_xlabel("Розмір популяції")
        axis.grid(alpha=0.25)
    fig.savefig(output / "population-budget.png", dpi=160)
    plt.close(fig)
    figures.append("population-budget.png")

    if traces:
        fig, axes = plt.subplots(3, 1, figsize=(10, 9), layout="constrained")
        for trace in traces:
            label = trace["configuration_id"]
            for axis, field in zip(axes, ("record_profit", "mean_feasible_profit", "unique_fraction"), strict=True):
                axis.plot([point["request"] for point in trace["points"]],
                          [point[field] for point in trace["points"]], label=label)
        for axis, label in zip(axes, ("Рекорд", "Середня цінність допустимих", "Частка унікальних масок"), strict=True):
            axis.set_ylabel(label)
            axis.set_xlabel("Загальні логічні оцінювання, включно з початком")
            axis.grid(alpha=0.25)
            axis.legend(fontsize=8)
        fig.suptitle("UC-s000, seed 81001: опорна конфігурація та дослідницький переможець; не holdout")
        fig.savefig(output / "example-UC-s000-81001.png", dpi=160)
        plt.close(fig)
        figures.append("example-UC-s000-81001.png")
    saved_report = {key: value for key, value in report.items() if key != "example_trajectories"}
    saved_report.update(figures=figures, example_trace_status="ARCHIVED_TRACES_PROVIDED" if traces else "NOT_PROVIDED")
    (output / "analysis.json").write_text(json.dumps(saved_report, ensure_ascii=False, sort_keys=True,
                                                   separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    winner = report["winner"]
    answers = ["# Сталі параметри: дослідницька сітка, не остаточний тест", "",
        f"Перевірено {report['runs']} запусків, {report['logical_requests']} загальних логічних оцінювань; 125 конфігурацій, 30 задач, 10 сімейств.", "",
        "## Яка комбінація обрана?", "",
        f"{report['winner_id']}: мутація {100 * winner['p_m']:g}%, схрещування {100 * winner['p_c']:g}%, популяція {winner['population_size']}. "
        f"Середнє відставання {100 * winner['mean_gap']:.6g}%. Вибір виконано точними раціональними числами за зареєстрованими нічиїми.", "",
        "Це найкраща точка цієї дослідницької сітки за цим критерієм, не універсальний оптимум і не оцінка переваги на нових задачах.", "",
        "## Як впливають три параметри?", "",
        "Теплові карти мають спільну шкалу. Кожна умовна крива змінює один параметр, фіксуючи решту двох; менше відставання краще. "
        "Описові різниці від опорного рівня й Спірмен з середніми рангами збережено в analysis.json. Сталий ряд має UNDEFINED, не нульову кореляцію. "
        "Коефіцієнт використовує п'ять умовних середніх, не 37500 незалежних задач; p-значень і нових тестів переваги немає.", "",
        "## Чому початковий і кінцевий рекорд показано окремо?", "",
        "Більша популяція отримує довший префікс того самого банку й може мати кращий початок. За однакового бюджету вона виконує менше повних поколінь. "
        "Монотонний рекорд є властивістю означення й елітизму; середня якість популяції та частка унікальних масок можуть змінюватися інакше. "
        "Частка унікальних масок — не середня відстань Геммінга.", "",
        "## Що залишається неперевіреним?", "",
        "Остаточні пошукові результати нових сімейств, адаптивний контролер, два первинні holdout-контрасти та їхні BCa-інтервали тут не обчислювалися. "
        "Вибір має бути зафіксований до остаточного пошуку; цей звіт не відкриває джерельний гейт адаптації. λ не використовується.", ""]
    if not traces:
        answers += ["Архівні траєкторії прикладу не надано; нових історій або інтерпольованих точок не створено.", ""]
    for figure in figures:
        answers += [f"![{figure}]({figure})", ""]
    (output / "RESULTS_UK.md").write_text("\n".join(answers), encoding="utf-8")
    return {"figures": figures, "example_trace_status": saved_report["example_trace_status"]}

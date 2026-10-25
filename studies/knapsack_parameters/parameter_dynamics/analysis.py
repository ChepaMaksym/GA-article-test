"""CI-only, prespecified analysis of five jointly controlled GA parameters.

Per-run records are deliberately bounded: only the two registered example
trajectories retain full population/generation histories. Raw candidate logs
remain separate evidence; a large main series need not hold them in memory.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import math
import os
import re
from statistics import NormalDist, fmean

import numpy as np

FIELDS = ("p_m", "p_c", "target_mu", "tournament_size", "elite_count")
PROFILES = tuple(range(32))
PRIMARY = (1, 2, 4, 8, 16, 31)
PILOT_TASKS = ("UC-s000", "WC-s001", "SC-s005", "SC-s000")
DISTANCE_BINS = ((0, 0), (1, 1), (2, 2), (3, 5), (6, 10), (11, 20), (21, 100))
DISTANCE_LABELS = ("0", "1", "2", "3–5", "6–10", "11–20", "21–100")
SCHEMA = "ga-parameter-dynamics-compact-run-v1"


def require(condition, message):
    if not condition:
        raise ValueError("Parameter dynamics analysis: " + message)


def ci_only():
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
            os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover",
            "scientific computation is restricted to registered CI")


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def gap(optimum, profit):
    require(integer(optimum, 1) and integer(profit) and profit <= optimum, "invalid external reference/record")
    return float(100 * Fraction(optimum - profit, optimum))


def record_at(events, q):
    value = None
    for event in events:
        if event["q"] > q:
            break
        value = event["profit"]
    require(value is not None, "record has no known beginning")
    return value


def parameter_metrics(generations, budget):
    """Query-weighted APPLIED values; next-generation requests are not backdated."""
    ci_only()
    levels = {field: Counter() for field in FIELDS}
    activity = {field: {"increases": 0, "decreases": 0, "unchanged_opportunities": 0,
                        "boundary_opportunities": 0, "opportunities": 0} for field in FIELDS}
    windows = [{"first_q": q, "last_q": min(budget, q + 499), "new_calls": 0,
                "parameters": dict.fromkeys(FIELDS, 0.0), "actual_parent_mu": 0.0}
               for q in range(1, budget + 1, 500)]
    previous = 0
    for gen in generations:
        left, right = gen["start_q"], gen["q"]
        require(left == previous + 1 and right >= left, "generation query coverage")
        previous = right
        theta = gen["parameters_before"]
        for field in FIELDS:
            require(number(theta[field]), "nonfinite applied parameter")
            levels[field][theta[field]] += right - left + 1
        for window in windows:
            overlap = max(0, min(right, window["last_q"]) - max(left, window["first_q"]) + 1)
            window["new_calls"] += overlap
            for field in FIELDS:
                window["parameters"][field] += overlap * theta[field]
            window["actual_parent_mu"] += overlap * gen["actual_parent_mu"]
        if gen["complete"]:
            for event in gen["parameter_events"]:
                field = event["field"]
                eligible = event["enabled"] and (field == "p_c" or gen["controller_event"] in ("SUCCESS", "STAGNATION"))
                delta = event["after"] - event["before"]
                activity[field]["increases"] += int(delta > 0)
                activity[field]["decreases"] += int(delta < 0)
                activity[field]["opportunities"] += int(eligible)
                activity[field]["unchanged_opportunities"] += int(eligible and delta == 0)
                activity[field]["boundary_opportunities"] += int(eligible and event["at_boundary"])
    require(previous == budget, "missing final query")
    for window in windows:
        count = window["last_q"] - window["first_q"] + 1
        require(window["new_calls"] == count, "incomplete parameter window")
        window["parameters"] = {key: value / count for key, value in window["parameters"].items()}
        window["actual_parent_mu"] /= count
    for field in FIELDS:
        require(sum(levels[field].values()) == budget, "parameter occupancy does not sum to budget")
        activity[field].update({"changed": bool(activity[field]["increases"] + activity[field]["decreases"]),
                               "query_weighted_mean": sum(value * count for value, count in levels[field].items()) / budget,
                               "query_occupancy": [{"value": value, "new_calls": count}
                                                   for value, count in sorted(levels[field].items())]})
    return activity, windows


def collapse_operators(source):
    result = []
    keys = ("total", "crossed", "novel_crossed", "feasible_crossed", "better_both_crossed")
    for label, (low, high) in zip(DISTANCE_LABELS, DISTANCE_BINS, strict=True):
        cell = {"distance_bin": label, **dict.fromkeys(keys, 0)}
        for old in source:
            if low <= old["distance"] <= high:
                for key in keys:
                    require(integer(old[key]), "invalid operator count")
                    cell[key] += old[key]
        require(all(cell[key] <= cell["crossed"] for key in keys[2:]) and cell["crossed"] <= cell["total"],
                "operator numerators exceed denominator")
        result.append(cell)
    return result


def extract_run(envelope):
    """Independently reconstruct before consulting any external OPT endpoint."""
    ci_only()
    from .verifier import verify_log

    required = {"task", "family", "start", "seed", "profile", "implementation_sha", "optimum", "log", "timings", "stage"}
    require(type(envelope) is dict and set(envelope) == required, "unexpected run envelope")
    task, profile, log = envelope["task"], envelope["profile"], envelope["log"]
    match = re.fullmatch(r"(UC|WC|SC)-(s\d{3})", task)
    require(match and match.group(2) == envelope["family"] and type(profile) is int and profile in PROFILES and
            log.get("profile") == profile and envelope["start"] in ("bank", "cloned") and
            envelope["stage"] in ("pilot", "main") and integer(envelope["seed"]), "run identity")
    require(re.fullmatch(r"[0-9a-f]{40}", envelope["implementation_sha"]), "implementation SHA")
    require(type(envelope["timings"]) is dict and all(value is None or integer(value)
            for value in envelope["timings"].values()), "invalid observational timings")
    verified = verify_log(log)
    require(verified["verification_status"] == "VERIFIED", "unverified journal")
    derived, problem = verified["derived_metrics"], log["problem"]
    require(log["budget"] == 5000 and problem["n"] == 100, "scientific run must be n100/5000new")
    events, generations, population = (derived[key] for key in ("record_events", "generation_trace", "population_trace"))
    initial, final = events[0]["profit"], events[-1]["profit"]
    optimum, budget = envelope["optimum"], log["budget"]
    gap(optimum, initial)
    activity, windows = parameter_metrics(generations, budget)
    completed = [point for point in population if point["complete"]]
    checkpoints = []
    for q in (0, 1000, 2500, 5000):
        point = next(point for point in reversed(completed) if point["q"] <= q)
        checkpoints.append({"query": q, "committed_population_q": point["q"],
                            **{key: point[key] for key in ("population_size", "mean_feasible_profit", "unique_fraction", "mean_pairwise_hamming")}})
    first_targets = {str(target): next((event["q"] for event in events if 100 * event["profit"] >= target * optimum), None)
                     for target in (95, 99)}
    first = log["generations"][0]
    # The next controller state is deliberately excluded: changes start only
    # AFTER this common first generation has been evaluated and committed.
    first_digest = digest({"candidates": log["candidates"][:29],
                           "population_before": first["population_before"], "population_after": first["population_after"],
                           "rng_before": first["rng_before"], "rng_after": first["rng_after"]})
    best_mask, best_call = log["summary"]["best_mask"], log["summary"]["best_call"]
    score = (next(score for mask, score in zip(log["initial_masks"], log["initial_scores"], strict=True) if mask == best_mask)
             if best_call == 0 else log["candidates"][best_call - 1])
    require(score["profit"] == final and score["feasible"] and score["weight"] <= problem["capacity"], "saved record witness")
    row = {"schema": SCHEMA, "verification_status": "VERIFIED",
           **{key: envelope[key] for key in ("task", "family", "start", "seed", "profile", "stage", "implementation_sha")},
           "class_label": match.group(1), "budget": budget, "n": 100, "optimum": optimum,
           "capacity": problem["capacity"], "problem_sha256": digest(problem), "journal_sha256": digest(log),
           "initial_population_sha256": digest({"masks": log["initial_masks"], "scores": log["initial_scores"]}),
           "initial_rng_sha256": digest(log["rng_initial"]), "first_generation_sha256": first_digest,
           "initial_best_profit": initial, "final_best_profit": final, "final_best_mask": best_mask,
           "final_best_weight": score["weight"], "final_gap_percent": gap(optimum, final),
           "final_capacity_fraction": score["weight"] / problem["capacity"],
           "first_targets": first_targets, "record_events": events,
           "activity": activity, "parameter_windows": windows, "population_checkpoints": checkpoints,
           "operator_bins": collapse_operators(derived["operator_bins"]),
           "infeasible_fraction": log["summary"]["infeasible_calls"] / budget,
           "duplicate_fraction": log["summary"]["duplicate_calls"] / budget,
           "full_generations": log["summary"]["full_generations"], "partial_children": log["summary"]["partial_children"],
           "controller_events": dict(Counter(gen["controller_event"] for gen in generations)),
           "stagnation_overshoot": sum(gen["stagnation_overshoot"] for gen in generations if gen["complete"]),
           "kernel_timing_ns": log["timing_ns"], "timings": dict(envelope["timings"]),
           "accounting": {key: verified[key] for key in ("independent_score_checks", "initial_score_checks", "final_score_checks", "premutation_score_checks")}}
    example_task, example_seed = ("UC-s000", 96999) if envelope["stage"] == "pilot" else ("UC-s020", 97001)
    if task == example_task and envelope["seed"] == example_seed and envelope["start"] == "bank" and profile in (0, 31):
        row["example_trace"] = {"population": population, "generations": generations}
    return row


def mean_by_family(rows, getter):
    tasks = defaultdict(list)
    for row in rows:
        value = getter(row)
        if value is not None:
            require(number(value), "nonfinite family observation")
            tasks[(row["family"], row["task"])].append(value)
    families = defaultdict(list)
    for (family, _), values in tasks.items():
        families[family].append(fmean(values))
    return {family: fmean(values) for family, values in sorted(families.items())}


def weighted_mean(rows, getter):
    values = mean_by_family(rows, getter)
    return fmean(values.values()) if values else None


def target_summary(rows, target):
    """Exact grouping weights and a linear-time weighted empirical CDF."""
    tasks = defaultdict(list)
    for row in rows:
        tasks[(row["family"], row["task"])].append(row)
    family_tasks = Counter(family for family, _ in tasks)
    increments = defaultdict(float)
    attained = 0
    for (family, _), entries in tasks.items():
        weight = 1 / (len(family_tasks) * family_tasks[family] * len(entries))
        for row in entries:
            q = row["first_targets"][str(target)]
            if q is not None:
                attained += 1
                increments[q] += weight
    cumulative, curve = 0.0, []
    for q in sorted({0, 5000, *increments}):
        cumulative += increments[q]
        curve.append({"q": q, "fraction": min(1.0, cumulative)})
    return {"attained": attained, "not_attained": len(rows) - attained, "curve": curve,
            "restricted_mean_queries": weighted_mean(rows, lambda r: r["first_targets"][str(target)]
                                                      if r["first_targets"][str(target)] is not None else 5000)}


def expected_identities(scope):
    if scope == "pilot":
        return {(task, start, 96999, profile) for task in PILOT_TASKS for start in ("cloned", "bank") for profile in PROFILES}
    require(scope == "main", "unknown series scope")
    return {(f"{label}-s{index:03d}", "bank", seed, profile) for index in range(20, 30)
            for label in ("UC", "WC", "SC") for seed in range(97001, 97031) for profile in PROFILES}


def validate_rows(rows, scope, expected_sha=None):
    expected, seen, implementations = expected_identities(scope), set(), set()
    pairs, problems = defaultdict(list), {}
    for row in rows:
        identity = tuple(row[key] for key in ("task", "start", "seed", "profile"))
        require(identity in expected and identity not in seen and row.get("schema") == SCHEMA and
                row.get("verification_status") == "VERIFIED" and row.get("stage") == scope,
                "duplicate, foreign, unverified or incompatible compact record")
        seen.add(identity)
        implementations.add(row["implementation_sha"])
        require(integer(row["profile"]) and row["budget"] == 5000 and row["n"] == 100 and
                row["family"] == row["task"][3:] and row["class_label"] == row["task"][:2], "record metadata")
        require(row["final_gap_percent"] == gap(row["optimum"], row["final_best_profit"]), "gap changed")
        require(type(row["final_best_mask"]) is str and len(row["final_best_mask"]) == 100 and
                set(row["final_best_mask"]) <= {"0", "1"}, "invalid saved witness")
        for target in ("95", "99"):
            q = row["first_targets"][target]
            require(q is None or integer(q) and q <= 5000, "invalid first attainment")
        for field in FIELDS:
            item = row["activity"][field]
            require(sum(point["new_calls"] for point in item["query_occupancy"]) == 5000 and
                    item["changed"] == bool(item["increases"] + item["decreases"]), "inconsistent activity")
            if not row["profile"] & (1 << FIELDS.index(field)):
                require(not item["changed"] and len(item["query_occupancy"]) == 1, "disabled parameter changed")
        require(len(row["operator_bins"]) == 7 and sum(cell["total"] for cell in row["operator_bins"]) == 5000,
                "operator query accounting")
        key = (row["problem_sha256"], row["optimum"], row["capacity"])
        require(row["task"] not in problems or problems[row["task"]] == key, "mixed problem reference")
        problems[row["task"]] = key
        pairs[identity[:3]].append(row)
    require(seen == expected, f"incomplete {scope} rectangle: {len(seen)}/{len(expected)}")
    require(len(implementations) == 1 and (expected_sha is None or implementations == {expected_sha}), "mixed source SHA")
    for entries in pairs.values():
        require(len(entries) == 32 and all(len({row[key] for row in entries}) == 1 for key in
                ("initial_population_sha256", "initial_rng_sha256", "initial_best_profit", "first_generation_sha256")),
                "profiles did not share the beginning and first generation")


def family_bca(vectors, *, replicates=50000, seed=97031):
    ci_only()
    values = np.asarray(vectors, dtype=float)
    require(values.ndim == 2 and values.shape[1] == 6 and len(values) >= 5 and np.isfinite(values).all(), "family x6 effects required")
    require(type(replicates) is int and replicates > 1 and type(seed) is int, "bootstrap settings")
    n, estimates = len(values), values.mean(axis=0)
    indices = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed]))).integers(0, n, size=(replicates, n))
    distribution = values[indices].mean(axis=1)
    jackknife = (values.sum(axis=0) - values) / (n - 1)
    confidence, normal = 1 - .05 / 6, NormalDist()
    tails = (normal.inv_cdf((1 - confidence) / 2), normal.inv_cdf(1 - (1 - confidence) / 2))
    result = {"status": "PERFORMED_MAIN_ONLY", "method": "BCa", "unit": "whole_family", "family_count": n,
              "replicates": replicates, "seed": seed, "confidence_each": confidence, "nominal_joint_confidence": .95,
              "resample_index_sha256": hashlib.sha256(indices.astype("<i8", copy=False).tobytes()).hexdigest(),
              "quantile_method": "linear", "bias_ties": "half_weight", "intervals": []}
    for column, profile in enumerate(PRIMARY):
        estimate, boot = float(estimates[column]), distribution[:, column]
        item = {"profile": profile, "estimate_gap_points": estimate, "lower": None, "upper": None,
                "status": "DESCRIPTIVE_ONLY", "reason": "degenerate_or_undefined_BCa", "positive_effect_supported": False}
        delta = jackknife[:, column].mean() - jackknife[:, column]
        denominator = 6 * float(np.sum(delta ** 2)) ** 1.5
        fraction = (np.count_nonzero(boot < estimate) + .5 * np.count_nonzero(boot == estimate)) / replicates
        if denominator and math.isfinite(denominator) and 0 < fraction < 1 and not np.all(boot == boot[0]):
            acceleration, bias = float(np.sum(delta ** 3)) / denominator, normal.inv_cdf(float(fraction))
            adjusted = []
            for tail in tails:
                divisor = 1 - acceleration * (bias + tail)
                adjusted.append(normal.cdf(bias + (bias + tail) / divisor) if divisor else math.nan)
            if all(math.isfinite(p) and 0 < p < 1 for p in adjusted) and adjusted[0] < adjusted[1]:
                low, high = map(float, np.quantile(boot, adjusted, method="linear"))
                if low < high and math.isfinite(low + high):
                    item.update({"lower": low, "upper": high, "status": "INFERENTIAL_BCA", "reason": None,
                                 "positive_effect_supported": low > 0, "negative_effect_supported": high < 0,
                                 "bias_correction": bias, "acceleration": acceleration, "adjusted_quantiles": adjusted})
        result["intervals"].append(item)
    return result


def summarize(rows):
    return {"runs": len(rows), "families": len({row["family"] for row in rows}), "tasks": len({row["task"] for row in rows}),
            "mean_final_gap_percent": weighted_mean(rows, lambda row: row["final_gap_percent"]),
            "mean_infeasible_fraction": weighted_mean(rows, lambda row: row["infeasible_fraction"]),
            "mean_duplicate_fraction": weighted_mean(rows, lambda row: row["duplicate_fraction"]),
            "mean_final_capacity_fraction": weighted_mean(rows, lambda row: row["final_capacity_fraction"]),
            "mean_full_generations": weighted_mean(rows, lambda row: row["full_generations"]),
            "targets": {str(target): target_summary(rows, target) for target in (95, 99)}}


def aggregate(records, *, scope, expected_sha=None):
    ci_only()
    rows = sorted(records, key=lambda row: (row["task"], row["start"], row["seed"], row["profile"]))
    validate_rows(rows, scope, expected_sha)
    groups = defaultdict(list)
    for row in rows:
        groups[(row["start"], row["profile"])].append(row)
    cells, family_cells, type_cells, activity_cells, operator_cells, timing_cells = [], [], [], [], [], []
    by_start_family_profile = {}
    for (start, profile), entries in sorted(groups.items()):
        cells.append({"start": start, "profile": profile, **summarize(entries)})
        family_values = mean_by_family(entries, lambda r: r["final_gap_percent"])
        for family, value in family_values.items():
            by_start_family_profile[(start, family, profile)] = value
            family_cells.append({"start": start, "profile": profile, "family": family, "mean_final_gap_percent": value,
                                 "runs": sum(row["family"] == family for row in entries)})
        for label in ("UC", "WC", "SC"):
            selected = [row for row in entries if row["class_label"] == label]
            if selected:
                type_cells.append({"start": start, "profile": profile, "class_label": label, **summarize(selected)})
        for field in FIELDS:
            activity_cells.append({"start": start, "profile": profile, "field": field,
                                   "runs": len(entries), "changed_runs": sum(row["activity"][field]["changed"] for row in entries),
                                   "changed_fraction": weighted_mean(entries, lambda r: int(r["activity"][field]["changed"])),
                                   **{key: sum(row["activity"][field][key] for row in entries)
                                      for key in ("increases", "decreases", "opportunities", "unchanged_opportunities", "boundary_opportunities")},
                                   "query_weighted_mean": weighted_mean(entries, lambda r: r["activity"][field]["query_weighted_mean"])})
        for index, label in enumerate(DISTANCE_LABELS):
            counts = {key: sum(row["operator_bins"][index][key] for row in entries)
                      for key in ("total", "crossed", "novel_crossed", "feasible_crossed", "better_both_crossed")}
            denom = counts["crossed"]
            operator_cells.append({"start": start, "profile": profile, "distance_bin": label, **counts,
                                   **{key: counts[count] / denom if denom else None for key, count in
                                      (("novel_fraction", "novel_crossed"), ("feasible_fraction", "feasible_crossed"),
                                       ("better_both_fraction", "better_both_crossed"))}, "independent_sample_claim": False})
        for source in ("timings", "kernel_timing_ns"):
            names = {key for row in entries for key in row[source]} - {"preparation_ns"}
            for metric in sorted(names):
                selected = [row for row in entries if row[source].get(metric) is not None]
                timing_cells.append({"start": start, "profile": profile, "source": source, "metric": metric,
                                     "known_observations": len(selected), "unknown_observations": len(entries) - len(selected),
                                     "mean_ns": weighted_mean(selected, lambda r: r[source][metric]) if selected else None})
    families = sorted({row["family"] for row in rows if row["start"] == "bank"})
    effects = [{"family": family, "effects": {str(profile): by_start_family_profile[("bank", family, 0)] -
               by_start_family_profile[("bank", family, profile)] for profile in PRIMARY}} for family in families]
    if scope == "main":
        primary = family_bca([[row["effects"][str(profile)] for profile in PRIMARY] for row in effects])
    else:
        primary = {"status": "NOT_PERFORMED_TECHNICAL_PILOT", "replicates": 0, "intervals": []}
    primary.update({"family_effects": effects, "positive_direction": "control gap minus adaptive gap, percentage points",
                    "practical_advantage_established": False, "practical_effect_threshold": None})
    interactions = []
    for first in range(5):
        for second in range(first + 1, 5):
            base_profiles = [p for p in PROFILES if not p & (1 << first) and not p & (1 << second)]
            values = []
            for family in families:
                get = lambda p: by_start_family_profile[("bank", family, p)]
                values.append(fmean(get(p | 1 << first | 1 << second) - get(p | 1 << first) -
                                    get(p | 1 << second) + get(p) for p in base_profiles))
            interactions.append({"first": FIELDS[first], "second": FIELDS[second], "effect_gap_points": fmean(values),
                                 "family_values": dict(zip(families, values, strict=True)), "role": "DESCRIPTIVE_ONLY",
                                 "contrast": "g11-g10-g01+g00", "other_profiles_averaged": 8})
    examples = [row for row in rows if "example_trace" in row]
    require(len(examples) == 2 and {row["profile"] for row in examples} == {0, 31}, "registered example missing")
    return {"schema": "ga-parameter-dynamics-series-v1", "scope": scope,
            "status": "COMPLETE_VERIFIED_MAIN" if scope == "main" else "COMPLETE_VERIFIED_PILOT",
            "implementation_sha": rows[0]["implementation_sha"], "runs": len(rows),
            "new_search_evaluations": len(rows) * 5000, "new_search_during_aggregation": False,
            "weighting": "equal repeats -> equal tasks within family -> equal families",
            "profile_cells": cells, "family_cells": family_cells, "type_cells": type_cells,
            "activity_cells": activity_cells, "operator_cells": operator_cells, "timing_cells": timing_cells,
            "primary_analysis": primary, "interactions": interactions, "prespecified_examples": examples,
            "limitations": ["Own predefined heuristics, not article replication or established novelty.",
                            "Actual population size and next target size are different states.",
                            "Novel masks and more diverse populations need not improve quality.",
                            "Technical pilot outcomes do not establish scientific superiority.",
                            "Signals were measured in all instrumented profiles; costs are not zero.",
                            "Six primary contrasts do not rank all profiles inferentially."]}

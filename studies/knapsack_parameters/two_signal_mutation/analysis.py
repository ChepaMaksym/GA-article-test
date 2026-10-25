"""Registered CI-only analysis of the two-signal mutation comparison.

The search never receives an optimum.  This module receives the external
reference only after an independent replay.  Technical-pilot descriptions
cannot be promoted to the confirmatory main-series analysis.
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
import hashlib
import json
import math
import os
import re
from statistics import NormalDist, fmean

import numpy as np


METHODS = ("fixed", "adaptive_mutation", "two_signal")
CONTRASTS = ("fixed_gap_minus_two_signal_gap", "adaptive_gap_minus_two_signal_gap")
PILOT_TASKS = ("UC-s000", "WC-s001", "SC-s005", "SC-s000")
DISTANCE_BINS = ((0, 0), (1, 1), (2, 2), (3, 5), (6, 10), (11, 20), (21, 100))
DISTANCE_LABELS = ("0", "1", "2", "3–5", "6–10", "11–20", "21–100")
SCHEMA = "ga-two-signal-compact-run-v1"


def _require(condition, message):
    if not condition:
        raise ValueError("Two-signal analysis: " + message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true" and
             os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
             os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover",
             "execution is restricted to the registered CI environment")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _integer(value, lower=0):
    return type(value) is int and value >= lower


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _gap(optimum, profit):
    _require(_integer(optimum, 1) and _integer(profit) and profit <= optimum,
             "invalid external optimum or feasible record")
    return float(100 * Fraction(optimum - profit, optimum))


def _record_at(events, query):
    previous = None
    for event in events:
        if event["q"] > query:
            break
        previous = event["profit"]
    _require(previous is not None, "record history has no known beginning")
    return previous


def carried_population_mean(trace, cutoff, key):
    """Mean of the last *completed* population at q=1,...,cutoff.

    A completed population at q=29 is used at q=29, not at q=30.
    An uncommitted terminal prefix is never a population replacement.
    """
    _ci_only()
    points = [point for point in trace if point["complete"] and point["q"] <= cutoff]
    _require(_integer(cutoff, 1) and points and points[0]["q"] == 0,
             "missing initial population or invalid early-window cutoff")
    _require(all(a["q"] < b["q"] for a, b in zip(points, points[1:])),
             "population trace must be strictly ordered")
    total, count = 0.0, 0
    for index, point in enumerate(points):
        left = max(1, point["q"])
        right = min(cutoff, points[index + 1]["q"] - 1 if index + 1 < len(points) else cutoff)
        if left <= right:
            _require(_number(point[key]), "nonfinite population metric")
            total += (right - left + 1) * point[key]
            count += right - left + 1
    _require(count == cutoff, "population trace does not cover the early window")
    return total / cutoff


def extract_run(envelope):
    """Replay one raw journal once, then create its externally scored record.

    ``timings`` contains observational wall-clock measurements from the driver;
    unknown times remain None.  Preparation is a shared-condition cost and is
    not multiplied by three profiles in the analysis.
    """
    _ci_only()
    required = {"task", "family", "start", "seed", "method", "implementation_sha",
                "optimum", "log", "timings"}
    _require(type(envelope) is dict and required <= set(envelope) and
             set(envelope) <= required | {"phase", "task_index"}, "unexpected envelope fields")
    task, method, log = envelope["task"], envelope["method"], envelope["log"]
    match = re.fullmatch(r"(UC|WC|SC)-(s\d{3})", task) if type(task) is str else None
    _require(match is not None and envelope["family"] == match.group(2), "task/family mismatch")
    _require(method in METHODS and log.get("method") == method and
             envelope["start"] in ("bank", "cloned") and _integer(envelope["seed"]),
             "invalid method, start or seed")
    _require(type(envelope["implementation_sha"]) is str and
             re.fullmatch(r"[0-9a-f]{40}", envelope["implementation_sha"]), "invalid implementation SHA")
    timings = envelope["timings"]
    _require(type(timings) is dict and all(type(name) is str and
             (value is None or _integer(value)) for name, value in timings.items()),
             "observational timings must be nonnegative integer nanoseconds or unknown")
    from .verifier import verify_log

    receipt = verify_log(log)
    _require(receipt.get("verification_status") == "VERIFIED", "journal has not passed independent replay")
    derived = receipt["derived_metrics"]
    events = derived["record_events"]
    budget = log["budget"]
    optimum = envelope["optimum"]
    initial, final = events[0]["profit"], events[-1]["profit"]
    _gap(optimum, initial)
    final_gap = _gap(optimum, final)
    half = budget // 2
    _require(half > 0, "analysis requires at least two new queries")
    early_novelty = []
    generations = []
    for point in derived["generation_trace"]:
        distances = point["parent_distances"]
        left, right = point["start_q"], point["q"]
        _require(len(distances) == right - left + 1, "selected-pair trace does not cover its queries")
        for offset, distance in enumerate(distances):
            if left + offset <= half:
                early_novelty.append(0.0 if distance == 0 else float(1 - Fraction(1, 2 ** (distance - 1))))
        generations.append({key: value for key, value in point.items() if key != "parent_distances"})
    _require(len(early_novelty) == half, "early parent-pair window is incomplete")
    initial_masks, initial_scores = log["initial_masks"], log["initial_scores"]
    best_mask = log["summary"]["best_mask"]
    problem = log["problem"]
    # Reuse an already independently replayed score, not another fitness call.
    best_call = log["summary"]["best_call"]
    if best_call == 0:
        best_score = next(score for mask, score in zip(initial_masks, initial_scores, strict=True) if mask == best_mask)
    else:
        best_score = log["candidates"][best_call - 1]
        _require(best_score["mask"] == best_mask, "saved record witness differs from its query")
    best_weight = best_score["weight"]
    _require(_integer(problem["capacity"], 1), "capacity must be positive for the occupancy diagnostic")
    _require(best_weight <= problem["capacity"], "saved feasible record exceeds capacity")
    first = {str(target): next((point["q"] for point in events
                               if 100 * point["profit"] >= target * optimum), None)
             for target in (95, 99)}
    population = derived["population_trace"]
    accounting = {name: receipt.get(name) for name in
                  ("independent_score_checks", "initial_score_checks", "final_score_checks", "premutation_score_checks")}
    early = {"mean_novelty": fmean(early_novelty),
             "mean_pairwise_hamming": carried_population_mean(population, half, "mean_pairwise_hamming"),
             "unique_fraction": carried_population_mean(population, half, "unique_fraction")}
    return {"schema": SCHEMA, "verification_status": "VERIFIED",
            **{name: envelope[name] for name in ("task", "family", "start", "seed", "method", "implementation_sha")},
            "class_label": match.group(1), "budget": budget, "n": problem["n"],
            "problem_sha256": _digest(problem), "journal_sha256": _digest(log),
            "initial_population_sha256": _digest({"masks": initial_masks, "scores": initial_scores}),
            "initial_rng_sha256": _digest(log["rng_initial"]),
            "optimum": optimum, "capacity": problem["capacity"],
            "initial_best_profit": initial, "final_best_profit": final,
            "final_best_weight": best_weight, "final_capacity_fraction": best_weight / problem["capacity"],
            "final_gap_percent": final_gap, "first_targets": first,
            "record_events": events, "population_trace": population, "generation_trace": generations,
            "operator_bins": derived["operator_bins"], "early": early,
            "late_gain_gap_points": _gap(optimum, _record_at(events, half)) - final_gap,
            "infeasible_fraction": log["summary"]["infeasible_calls"] / budget,
            "duplicate_fraction": log["summary"]["duplicate_calls"] / budget,
            "timings": dict(timings), "kernel_timing_ns": dict(log["timing_ns"]),
            "accounting": {"new_search_evaluations": budget,
                           "initial_known_positions": len(initial_masks), **accounting}}


def expected_identities(scope):
    _ci_only()
    _require(scope in ("pilot", "main"), "unknown analysis scope")
    if scope == "pilot":
        conditions = [(task, start) for task in PILOT_TASKS for start in ("cloned", "bank")]
        seeds = (93999,)
    else:
        conditions = [(f"{kind}-s{index:03d}", "bank") for index in range(10, 20) for kind in ("UC", "WC", "SC")]
        seeds = range(94001, 94031)
    return {(task, start, seed, method) for task, start in conditions for seed in seeds for method in METHODS}


def _validate_rows(rows, scope, expected_sha):
    expected = expected_identities(scope)
    seen, implementations, pairs, problems = set(), set(), defaultdict(list), {}
    for row in rows:
        _require(type(row) is dict and row.get("schema") == SCHEMA and
                 row.get("verification_status") == "VERIFIED", "unverified or unknown compact record")
        identity = tuple(row.get(key) for key in ("task", "start", "seed", "method"))
        _require(identity in expected and identity not in seen, "foreign or duplicate run identity")
        seen.add(identity)
        task = row["task"]
        _require(row.get("family") == task.split("-")[1] and row.get("class_label") == task.split("-")[0],
                 "mislabelled task, class or family")
        _require(row.get("budget") == 5000 and row.get("n") == 100 and
                 row["accounting"].get("new_search_evaluations") == 5000 and
                 row["accounting"].get("initial_known_positions") == 30, "incomplete scientific budget")
        sha = row.get("implementation_sha")
        _require(type(sha) is str and re.fullmatch(r"[0-9a-f]{40}", sha), "invalid source SHA")
        implementations.add(sha)
        for name in ("problem_sha256", "journal_sha256", "initial_population_sha256", "initial_rng_sha256"):
            _require(type(row.get(name)) is str and re.fullmatch(r"[0-9a-f]{64}", row[name]),
                     "invalid compact provenance digest")
        _require(_number(row.get("final_gap_percent")) and
                 row["final_gap_percent"] == _gap(row["optimum"], row["final_best_profit"]),
                 "stored final quality differs from external reference")
        _gap(row["optimum"], row["initial_best_profit"])
        _require(row["initial_best_profit"] <= row["final_best_profit"], "record decreased")
        records = row["record_events"]
        _require(records and records[0] == {"q": 0, "profit": row["initial_best_profit"]} and
                 records[-1]["profit"] == row["final_best_profit"] and
                 all(_integer(point["q"]) and point["q"] <= 5000 and _integer(point["profit"]) for point in records) and
                 all(a["q"] < b["q"] and a["profit"] < b["profit"] for a, b in zip(records, records[1:])),
                 "invalid strict-record history")
        for target in (95, 99):
            first = next((point["q"] for point in records if 100 * point["profit"] >= target * row["optimum"]), None)
            _require(row["first_targets"].get(str(target)) == first, "target attainment mismatch")
        _require(all(_number(row.get(key)) and 0 <= row[key] <= 1 for key in
                     ("infeasible_fraction", "duplicate_fraction", "final_capacity_fraction")),
                 "invalid candidate or capacity fraction")
        _require(_integer(row.get("capacity"), 1) and _integer(row.get("final_best_weight")) and
                 row["final_best_weight"] <= row["capacity"] and
                 row["final_capacity_fraction"] == row["final_best_weight"] / row["capacity"],
                 "capacity diagnostic does not match the verified record witness")
        _require(all(_number(row["early"].get(key)) for key in
                     ("mean_novelty", "mean_pairwise_hamming", "unique_fraction")) and
                 _number(row.get("late_gain_gap_points")), "nonfinite early/late diagnostic")
        _require(0 <= row["early"]["mean_novelty"] <= 1 and
                 0 <= row["early"]["unique_fraction"] <= 1 and
                 0 <= row["early"]["mean_pairwise_hamming"] <= 100,
                 "early signals are outside their mathematical range")
        _require(row["late_gain_gap_points"] == _gap(row["optimum"], _record_at(records, 2500)) - row["final_gap_percent"],
                 "late gain differs from the saved record history")
        for timings in (row["timings"], row["kernel_timing_ns"]):
            _require(type(timings) is dict and all(value is None or _integer(value) for value in timings.values()),
                     "invalid or fabricated timing observation")
        population = row["population_trace"]
        completed = [point for point in population if point["complete"]]
        _require([point["q"] for point in completed] == list(range(0, 4989, 29)),
                 "completed population timeline is incomplete")
        _require(len(row["generation_trace"]) == 173 and
                 [point["q"] for point in row["generation_trace"]] == list(range(29, 4989, 29)) + [5000] and
                 all(point["complete"] for point in row["generation_trace"][:-1]) and
                 row["generation_trace"][-1]["complete"] is False,
                 "complete generations or terminal prefix are missing")
        _require(carried_population_mean(population, 2500, "mean_pairwise_hamming") == row["early"]["mean_pairwise_hamming"],
                 "early diversity does not use the last completed populations")
        operators = row["operator_bins"]
        _require([cell["distance"] for cell in operators] == list(range(101)) and
                 sum(cell["total"] for cell in operators) == 5000,
                 "operator distances do not cover all 5000 selected pairs")
        for cell in operators:
            _require(all(_integer(cell[key]) for key in
                         ("total", "crossed", "novel_crossed", "feasible_crossed", "better_both_crossed")) and
                     all(cell[key] <= cell["crossed"] for key in
                         ("novel_crossed", "feasible_crossed", "better_both_crossed")) and
                     cell["crossed"] <= cell["total"] and
                     cell["better_both_crossed"] <= cell["feasible_crossed"],
                     "operator numerator exceeds its conditional denominator")
        pairs[identity[:3]].append(row)
        problem_identity = row["problem_sha256"], row["optimum"], row["capacity"]
        _require(task not in problems or problems[task] == problem_identity, "mixed problem/reference identities")
        problems[task] = problem_identity
    _require(seen == expected, f"incomplete {scope} series: {len(seen)}/{len(expected)}")
    _require(len(implementations) == 1 and (expected_sha is None or implementations == {expected_sha}),
             "mixed or unexpected implementation SHA")
    for entries in pairs.values():
        _require(len(entries) == 3 and len({row["initial_population_sha256"] for row in entries}) == 1 and
                 len({row["initial_rng_sha256"] for row in entries}) == 1 and
                 len({row["initial_best_profit"] for row in entries}) == 1,
                 "paired methods do not share the same beginning and streams")


def average_ranks(values):
    _ci_only()
    values = list(values)
    _require(values and all(_number(value) for value in values), "rank values must be finite")
    order, ranks = sorted(range(len(values)), key=values.__getitem__), [0.0] * len(values)
    first = 0
    while first < len(order):
        last = first + 1
        while last < len(order) and values[order[last]] == values[order[first]]:
            last += 1
        for index in order[first:last]:
            ranks[index] = (first + 1 + last) / 2
        first = last
    return ranks


def descriptive_spearman(x, y):
    _ci_only()
    _require(len(x) == len(y) and len(x) >= 2, "paired family vectors are required")
    a, b = average_ranks(x), average_ranks(y)
    metadata = {"family_count": len(a), "role": "DESCRIPTIVE_ONLY", "p_value": None, "causal_claim": False}
    if len(set(a)) == 1 or len(set(b)) == 1:
        return {**metadata, "status": "UNDEFINED", "rho": None, "reason": "constant_series"}
    da, db = [v - fmean(a) for v in a], [v - fmean(b) for v in b]
    rho = sum(i * j for i, j in zip(da, db, strict=True)) / math.sqrt(sum(i * i for i in da) * sum(j * j for j in db))
    return {**metadata, "status": "DEFINED", "rho": rho, "reason": None}


def _undefined(name, estimate, reason):
    return {"contrast_id": name, "estimate_gap_points": float(estimate), "lower": None, "upper": None,
            "status": "DESCRIPTIVE_ONLY", "reason": reason, "positive_effect_supported": False}


def family_bca(vectors, *, replicates=50000, seed=94031, confidence=0.975):
    """Two registered contrasts, common family resamples, no fallback interval.

    Nondefault arguments exist for small synthetic CI fixtures only.
    """
    _ci_only()
    values = np.asarray(vectors, dtype=float)
    _require(values.ndim == 2 and values.shape[1] == 2 and len(values) > 0 and np.isfinite(values).all(),
             "a finite family x 2 effect matrix is required")
    _require(type(replicates) is int and replicates > 1 and type(seed) is int and
             0 < confidence < 1, "invalid BCa settings")
    n, estimates = len(values), values.mean(axis=0)
    output = {"method": "BCa", "unit": "whole family", "family_count": n, "replicates": replicates,
              "seed": seed, "confidence_each": confidence, "nominal_joint_confidence": 1 - 2 * (1 - confidence),
              "positive_direction": "control gap minus two-signal gap, percentage points",
              "quantile_method": "linear", "ties": "half weight for bias correction",
              "resample_index_sha256": None, "intervals": []}
    if n < 5:
        output["intervals"] = [_undefined(name, value, "fewer_than_five_families")
                               for name, value in zip(CONTRASTS, estimates, strict=True)]
        return output
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed])))
    indices = generator.integers(0, n, size=(replicates, n))
    output["resample_index_sha256"] = hashlib.sha256(indices.astype("<i8", copy=False).tobytes()).hexdigest()
    bootstrap = values[indices].mean(axis=1)
    jackknife = (values.sum(axis=0) - values) / (n - 1)
    normal, alpha = NormalDist(), 1 - confidence
    tails = (normal.inv_cdf(alpha / 2), normal.inv_cdf(1 - alpha / 2))
    for column, name in enumerate(CONTRASTS):
        estimate, distribution = float(estimates[column]), bootstrap[:, column]
        delta = jackknife[:, column].mean() - jackknife[:, column]
        denominator = 6 * float(np.sum(delta ** 2)) ** 1.5
        fraction = (np.count_nonzero(distribution < estimate) + .5 * np.count_nonzero(distribution == estimate)) / replicates
        if np.all(distribution == distribution[0]) or not denominator or not math.isfinite(denominator) or not 0 < fraction < 1:
            output["intervals"].append(_undefined(name, estimate, "degenerate_or_undefined_BCa"))
            continue
        acceleration, z0 = float(np.sum(delta ** 3)) / denominator, normal.inv_cdf(float(fraction))
        adjusted = []
        for tail in tails:
            divisor = 1 - acceleration * (z0 + tail)
            adjusted.append(normal.cdf(z0 + (z0 + tail) / divisor) if divisor else math.nan)
        if not all(math.isfinite(p) and 0 < p < 1 for p in adjusted) or adjusted[0] >= adjusted[1]:
            output["intervals"].append(_undefined(name, estimate, "invalid_adjusted_quantiles"))
            continue
        low, high = map(float, np.quantile(distribution, adjusted, method="linear"))
        if not math.isfinite(low + high) or low >= high:
            output["intervals"].append(_undefined(name, estimate, "degenerate_or_reversed_interval"))
            continue
        output["intervals"].append({"contrast_id": name, "estimate_gap_points": estimate,
                                    "lower": low, "upper": high, "status": "INFERENTIAL_BCA", "reason": None,
                                    "positive_effect_supported": low > 0, "negative_effect_supported": high < 0,
                                    "bias_correction": z0, "acceleration": acceleration,
                                    "bias_fraction": float(fraction), "adjusted_quantiles": adjusted})
    return output


def mean_by_family(rows, getter):
    """Equal repeats -> equal tasks within a family -> equal families."""
    _ci_only()
    tasks = defaultdict(list)
    for row in rows:
        value = getter(row)
        if value is not None:
            _require(_number(value), "nonfinite family observation")
            tasks[(row["family"], row["task"])].append(value)
    families = defaultdict(list)
    for (family, _), values in tasks.items():
        families[family].append(fmean(values))
    return {family: fmean(values) for family, values in sorted(families.items())}


def _mean(rows, getter):
    values = mean_by_family(rows, getter)
    return fmean(values.values()) if values else None


def _summarize(entries):
    targets = {}
    for target in (95, 99):
        key = str(target)
        queries = sorted({0, 5000, *(row["first_targets"][key] for row in entries if row["first_targets"][key] is not None)})
        targets[key] = {"attained": sum(row["first_targets"][key] is not None for row in entries),
                        "not_attained": sum(row["first_targets"][key] is None for row in entries),
                        "restricted_mean_queries": _mean(entries, lambda row: row["first_targets"][key]
                                                         if row["first_targets"][key] is not None else 5000),
                        "curve": [{"q": q, "fraction": _mean(entries, lambda row, q=q:
                                  int(row["first_targets"][key] is not None and row["first_targets"][key] <= q))}
                                  for q in queries]}
    return {"runs": len(entries), "tasks": len({row["task"] for row in entries}),
            "families": len({row["family"] for row in entries}),
            "mean_final_gap_percent": _mean(entries, lambda row: row["final_gap_percent"]),
            "mean_final_capacity_fraction": _mean(entries, lambda row: row["final_capacity_fraction"]),
            "mean_infeasible_fraction": _mean(entries, lambda row: row["infeasible_fraction"]),
            "mean_duplicate_fraction": _mean(entries, lambda row: row["duplicate_fraction"]), "targets": targets}


def _operator_cells(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["start"], row["method"])].append(row)
    result = []
    for (start, method), entries in sorted(groups.items()):
        for label, (lower, upper) in zip(DISTANCE_LABELS, DISTANCE_BINS, strict=True):
            counts = dict.fromkeys(("total", "crossed", "novel_crossed", "feasible_crossed", "better_both_crossed"), 0)
            for row in entries:
                for cell in row["operator_bins"]:
                    if lower <= cell["distance"] <= upper:
                        _require(all(_integer(cell[key]) for key in counts) and
                                 all(cell[key] <= cell["crossed"] for key in ("novel_crossed", "feasible_crossed", "better_both_crossed")) and
                                 cell["crossed"] <= cell["total"], "invalid operator numerator or denominator")
                        for key in counts:
                            counts[key] += cell[key]
            denominator = counts["crossed"]
            result.append({"start": start, "method": method, "distance_bin": label, **counts,
                           "novel_fraction": counts["novel_crossed"] / denominator if denominator else None,
                           "feasible_fraction": counts["feasible_crossed"] / denominator if denominator else None,
                           "better_both_fraction": counts["better_both_crossed"] / denominator if denominator else None,
                           "weighting": "pooled descriptive candidate counts conditional on applied crossover",
                           "independent_sample_claim": False})
    return result


def _timing_cells(rows):
    result = []
    for method in METHODS:
        selected = [row for row in rows if row["method"] == method]
        for source in ("timings", "kernel_timing_ns"):
            names = sorted({name for row in selected for name in row[source]})
            for name in names:
                # Preparation belongs to a condition, not to each method.
                if name == "preparation_ns":
                    continue
                known = [row for row in selected if row[source].get(name) is not None]
                result.append({"method": method, "source": source, "metric": name,
                               "known_observations": len(known), "unknown_observations": len(selected) - len(known),
                               "mean_ns": _mean(known, lambda row: row[source][name]) if known else None})
    preparation = {}
    for row in rows:
        key = row["task"], row["start"], row["seed"]
        value = row["timings"].get("preparation_ns")
        if value is not None:
            _require(key not in preparation or preparation[key] == value, "shared preparation timings conflict")
            preparation[key] = value
    return {"profile_metrics": result, "shared_preparation_conditions": len(preparation),
            "shared_preparation_total_ns": sum(preparation.values()) if preparation else None,
            "scope_note": "observational timings; nested scopes are not added; unknown is not zero"}


def aggregate(records, *, scope, expected_sha=None):
    """Summarize the exact pilot or main rectangle, never a favorable subset."""
    _ci_only()
    rows = list(records)
    _validate_rows(rows, scope, expected_sha)
    rows.sort(key=lambda row: (row["task"], row["start"], row["seed"], row["method"]))
    family_cells, method_cells, type_cells = [], [], []
    for start in sorted({row["start"] for row in rows}):
        for method in METHODS:
            entries = [row for row in rows if row["start"] == start and row["method"] == method]
            method_cells.append({"start": start, "method": method, **_summarize(entries)})
            for family in sorted({row["family"] for row in entries}):
                family_rows = [row for row in entries if row["family"] == family]
                family_cells.append({"start": start, "method": method, "family": family, **_summarize(family_rows)})
            for kind in ("UC", "WC", "SC"):
                type_rows = [row for row in entries if row["class_label"] == kind]
                if type_rows:
                    type_cells.append({"start": start, "method": method, "class_label": kind, **_summarize(type_rows)})
    main = scope == "main"
    correlations = []
    if main:
        families = sorted({row["family"] for row in rows})
        by_method = {method: [row for row in rows if row["method"] == method] for method in METHODS}
        gaps = {method: mean_by_family(entries, lambda row: row["final_gap_percent"])
                for method, entries in by_method.items()}
        vectors = [[gaps["fixed"][family] - gaps["two_signal"][family],
                    gaps["adaptive_mutation"][family] - gaps["two_signal"][family]] for family in families]
        primary = family_bca(vectors)
        primary["family_effects"] = [{"family": family, "effects": dict(zip(CONTRASTS, vector, strict=True))}
                                    for family, vector in zip(families, vectors, strict=True)]
        primary["advantage_over_both_controls_supported"] = all(interval["positive_effect_supported"] for interval in primary["intervals"])
        primary["practical_advantage_established"] = False
        primary["practical_effect_threshold"] = None
        for method, entries in by_method.items():
            gains = mean_by_family(entries, lambda row: row["late_gain_gap_points"])
            for signal in ("mean_novelty", "mean_pairwise_hamming"):
                early = mean_by_family(entries, lambda row, signal=signal: row["early"][signal])
                x, y = [early[family] for family in families], [gains[family] for family in families]
                correlations.append({"method": method, "early_signal": signal,
                                     "late_outcome": "gap_2500_minus_gap_5000_points", "families": families,
                                     "x": x, "y": y, **descriptive_spearman(x, y)})
    else:
        primary = {"status": "NOT_PERFORMED_TECHNICAL_PILOT", "bootstrap_replicates": 0,
                   "intervals": [], "advantage_over_both_controls_supported": False,
                   "practical_advantage_established": False}
    example_task, example_seed = ("UC-s010", 94001) if main else ("UC-s000", 93999)
    examples = [row for row in rows if row["task"] == example_task and row["seed"] == example_seed and row["start"] == "bank"]
    _require(len(examples) == 3, "the prespecified example is missing")
    return {"schema": "ga-two-signal-series-summary-v1", "scope": scope,
            "status": "COMPLETE_VERIFIED_MAIN" if main else "COMPLETE_VERIFIED_PILOT",
            "implementation_sha": rows[0]["implementation_sha"], "runs": len(rows),
            "new_search_evaluations": len(rows) * 5000, "new_evaluations_during_aggregation": 0,
            "weighting": "equal repetitions, equal tasks within family, equal families",
            "family_cells": family_cells, "method_summaries": method_cells, "type_cells": type_cells,
            "primary_analysis": primary, "correlations": correlations,
            "operator_cells": _operator_cells(rows), "costs": _timing_cells(rows),
            "prespecified_example": {"task": example_task, "seed": example_seed, "start": "bank", "rows": examples},
            "limitations": ["A standard GA is already an evolutionary algorithm.",
                            "Parental novelty is not offspring quality or a certificate of local optimality.",
                            "Post-search crossover diagnostics do not control the search.",
                            "Correlations are descriptive, not causal.",
                            "A technical pilot does not establish superiority."]}

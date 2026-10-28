"""Registered CI analysis of adaptive versus open-loop tournament control.

Donor runs are independently checked and retained by the driver, but are not
recipients in the primary comparison. Inference resamples entire families.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
from statistics import NormalDist, fmean

import numpy as np


SCHEMA = "ga-knapsack-tournament-feedback-compact-v1"
PROFILES = ("k2", "k3", "k4", "k5", "adaptive", "replay")
PRIMARY_CONTROLS = ("k2", "k3", "k4", "k5", "replay")
PILOT_TASKS = ("UC-s000", "WC-s001", "SC-s005", "SC-s000")
LABELS = {"k2": "Сталий турнір 2", "k3": "Сталий турнір 3", "k4": "Сталий турнір 4",
          "k5": "Сталий турнір 5", "adaptive": "Адаптивний турнір", "replay": "Донорський розклад"}
COLORS = {"k2": "#1765a0", "k3": "#5698c4", "k4": "#30653b", "k5": "#72a546",
          "adaptive": "#c65024", "replay": "#8755a4"}
DISTANCE_BINS = ((0, 0), (1, 1), (2, 2), (3, 5), (6, 10), (11, 20), (21, 100))
DISTANCE_LABELS = ("0", "1", "2", "3–5", "6–10", "11–20", "21–100")


def require(condition, message):
    if not condition:
        raise ValueError("Tournament feedback analysis: " + message)


def ci_only():
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
            os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover",
            "scientific computation is restricted to registered CI")


def digest(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def gap(optimum, profit):
    require(integer(optimum, 1) and integer(profit) and profit <= optimum, "invalid optimum or feasible record")
    return float(100 * Fraction(optimum - profit, optimum))


def record_at(events, q):
    value = None
    for event in events:
        if event["q"] > q:
            break
        value = event["profit"]
    require(value is not None, "record has no known beginning")
    return value


def mean_by_family(rows, getter):
    """Equal repeats within task, equal tasks within family, equal families."""
    tasks = defaultdict(list)
    for row in rows:
        value = getter(row)
        if value is not None:
            require(number(value), "nonfinite observation")
            tasks[(row["family"], row["task"])].append(value)
    families = defaultdict(list)
    for (family, _task), values in tasks.items():
        families[family].append(fmean(values))
    return {family: fmean(values) for family, values in sorted(families.items())}


def weighted_mean(rows, getter):
    values = mean_by_family(rows, getter)
    return fmean(values.values()) if values else None


def target_summary(rows, target):
    """CDF includes every nonhit in its denominator and preserves q=0/5000."""
    tasks = defaultdict(list)
    for row in rows:
        tasks[(row["family"], row["task"])].append(row)
    family_tasks = Counter(family for family, _task in tasks)
    increments = defaultdict(float)
    attained = 0
    for (family, _task), entries in tasks.items():
        weight = 1 / (len(family_tasks) * family_tasks[family] * len(entries))
        for row in entries:
            q = row["first_targets"][str(target)]
            require(q is None or integer(q) and q <= 5000, "invalid first attainment")
            if q is not None:
                attained += 1
                increments[q] += weight
    cumulative, curve = 0.0, []
    for q in sorted({0, 5000, *increments}):
        cumulative += increments[q]
        curve.append({"q": q, "fraction": min(1.0, cumulative)})
    return {"attained": attained, "not_attained": len(rows) - attained,
            "observations": len(rows), "curve": curve,
            "restricted_mean_queries": weighted_mean(rows, lambda row:
                row["first_targets"][str(target)] if row["first_targets"][str(target)] is not None else 5000)}


def tournament_activity(generations, budget, profile):
    """Weight APPLIED tournament sizes by queries, including the final prefix."""
    occupancy = Counter()
    activity = {"increases": 0, "decreases": 0, "opportunities": 0,
                "unchanged_opportunities": 0, "boundary_opportunities": 0}
    windows = [{"first_q": q, "last_q": min(budget, q + 499), "new_calls": 0,
                "applied_tournament_sum": 0} for q in range(1, budget + 1, 500)]
    previous = 0
    for generation in generations:
        left, right = generation["start_q"], generation["q"]
        require(left == previous + 1 and right >= left, "generation query coverage")
        previous = right
        before = generation["parameters_before"]["tournament_size"]
        require(integer(before, 2) and before <= 5, "applied tournament bounds")
        occupancy[before] += right - left + 1
        for window in windows:
            overlap = max(0, min(right, window["last_q"]) - max(left, window["first_q"]) + 1)
            window["new_calls"] += overlap
            window["applied_tournament_sum"] += overlap * before
        if generation["complete"]:
            after = generation["parameters_after"]["tournament_size"]
            eligible = (profile == "replay" or profile == "adaptive" and
                        generation["controller_event"] in ("SUCCESS", "STAGNATION"))
            activity["increases"] += int(after > before)
            activity["decreases"] += int(after < before)
            activity["opportunities"] += int(eligible)
            activity["unchanged_opportunities"] += int(eligible and after == before)
            activity["boundary_opportunities"] += int(eligible and after in (2, 5))
    require(previous == budget and sum(occupancy.values()) == budget, "missing applied queries")
    for window in windows:
        require(window["new_calls"] == window["last_q"] - window["first_q"] + 1, "incomplete parameter window")
        window["mean_applied_tournament"] = window.pop("applied_tournament_sum") / window["new_calls"]
    activity.update({"changed": bool(activity["increases"] + activity["decreases"]),
                     "query_weighted_mean": sum(k * count for k, count in occupancy.items()) / budget,
                     "query_occupancy": [{"value": k, "new_calls": occupancy[k]} for k in sorted(occupancy)]})
    return activity, windows


def collapse_operators(source):
    keys = ("total", "crossed", "novel_crossed", "feasible_crossed", "better_both_crossed")
    result = []
    for label, (low, high) in zip(DISTANCE_LABELS, DISTANCE_BINS, strict=True):
        cell = {"distance_bin": label, **dict.fromkeys(keys, 0)}
        for old in source:
            if low <= old["distance"] <= high:
                for key in keys:
                    require(integer(old[key]), "invalid operator count")
                    cell[key] += old[key]
        require(all(cell[key] <= cell["crossed"] for key in keys[2:]) and cell["crossed"] <= cell["total"],
                "operator numerator exceeds denominator")
        result.append(cell)
    return result


def extract_run(envelope):
    """Verify the full raw journal before computing any external OPT metric."""
    ci_only()
    from .verifier import verify_log

    fields = {"task", "family", "start", "seed", "profile", "stage", "implementation_sha",
              "optimum", "log", "timings"}
    require(type(envelope) is dict and set(envelope) == fields, "unexpected envelope fields")
    task, profile, log = envelope["task"], envelope["profile"], envelope["log"]
    match = re.fullmatch(r"(UC|WC|SC)-(s\d{3})", task)
    require(match and match.group(2) == envelope["family"] and profile in PROFILES and
            log.get("profile") == profile and envelope["start"] in ("bank", "cloned") and
            envelope["stage"] in ("pilot", "main") and integer(envelope["seed"]), "run identity")
    require(re.fullmatch(r"[0-9a-f]{40}", envelope["implementation_sha"]), "implementation SHA")
    require(type(envelope["timings"]) is dict and all(value is None or integer(value)
            for value in envelope["timings"].values()), "invalid observational timings")
    receipt = verify_log(log)
    require(receipt["verification_status"] == "VERIFIED", "journal not verified")
    require(log["budget"] == 5000 and log["problem"]["n"] == 100 and log["problem"]["capacity"] > 0,
            "scientific log must be n100/5000new/positive capacity")
    derived, problem = receipt["derived_metrics"], log["problem"]
    events, generations, population = (derived[key] for key in ("record_events", "generation_trace", "population_trace"))
    initial, final, optimum = events[0]["profit"], events[-1]["profit"], envelope["optimum"]
    gap(optimum, initial)
    activity, windows = tournament_activity(generations, 5000, profile)
    completed = [point for point in population if point["complete"]]
    checkpoints = []
    for q in (0, 1000, 2500, 5000):
        point = next(point for point in reversed(completed) if point["q"] <= q)
        checkpoints.append({"query": q, "committed_population_q": point["q"],
                            **{key: point[key] for key in ("population_size", "mean_feasible_profit", "unique_fraction",
                                                         "mean_pairwise_hamming", "feasible_fraction")}})
    first_targets = {str(target): next((event["q"] for event in events
                    if 100 * event["profit"] >= target * optimum), None) for target in (95, 99)}
    first_generation = log["generations"][0]
    first_digest = digest({"candidates": log["candidates"][:29],
                           **{key: first_generation[key] for key in ("population_before", "population_after",
                                                                     "rng_before", "rng_after")}})
    best_mask, best_call = log["summary"]["best_mask"], log["summary"]["best_call"]
    best_score = (next(score for mask, score in zip(log["initial_masks"], log["initial_scores"], strict=True)
                       if mask == best_mask) if best_call == 0 else log["candidates"][best_call - 1])
    require(best_score["profit"] == final and best_score["feasible"], "saved best witness")
    row = {"schema": SCHEMA, "verification_status": "VERIFIED",
           **{key: envelope[key] for key in ("task", "family", "start", "seed", "profile", "stage", "implementation_sha")},
           "class_label": match.group(1), "budget": 5000, "n": 100, "optimum": optimum,
           "capacity": problem["capacity"], "problem_sha256": digest(problem), "journal_sha256": digest(log),
           "initial_population_sha256": digest({"masks": log["initial_masks"], "scores": log["initial_scores"]}),
           "initial_rng_sha256": digest(log["rng_initial"]), "first_generation_sha256": first_digest,
           "initial_best_profit": initial, "final_best_profit": final, "final_best_mask": best_mask,
           "final_best_weight": best_score["weight"], "final_gap_percent": gap(optimum, final),
           "final_capacity_fraction": best_score["weight"] / problem["capacity"],
           "first_targets": first_targets, "record_events": events,
           "activity": {"tournament_size": activity}, "parameter_windows": windows,
           "population_checkpoints": checkpoints, "operator_bins": collapse_operators(derived["operator_bins"]),
           "infeasible_fraction": log["summary"]["infeasible_calls"] / 5000,
           "duplicate_fraction": log["summary"]["duplicate_calls"] / 5000,
           "full_generations": log["summary"]["full_generations"], "partial_children": log["summary"]["partial_children"],
           "controller_events": dict(Counter(generation["controller_event"] for generation in generations)),
           "kernel_timing_ns": dict(log["timing_ns"]), "timings": dict(envelope["timings"]),
           "accounting": {key: receipt[key] for key in ("independent_score_checks", "initial_score_checks",
                                                       "final_score_checks", "premutation_score_checks")}}
    example_task, example_seed = ("UC-s000", 109999) if envelope["stage"] == "pilot" else ("UC-s040", 110001)
    if task == example_task and envelope["seed"] == example_seed and envelope["start"] == "bank":
        row["example_trace"] = {"population": population, "generations": generations}
    return row


def expected_identities(scope):
    if scope == "pilot":
        return {(task, start, 109999, profile) for task in PILOT_TASKS for start in ("cloned", "bank") for profile in PROFILES}
    require(scope == "main", "unknown series scope")
    return {(f"{label}-s{index:03d}", "bank", seed, profile) for index in range(40, 50)
            for label in ("UC", "WC", "SC") for seed in range(110001, 110031) for profile in PROFILES}


def validate_rows(rows, scope, expected_sha=None):
    expected, seen, implementations = expected_identities(scope), set(), set()
    pairs, problems = defaultdict(list), {}
    for row in rows:
        identity = tuple(row[key] for key in ("task", "start", "seed", "profile"))
        require(identity in expected and identity not in seen and row.get("schema") == SCHEMA and
                row.get("verification_status") == "VERIFIED" and row.get("stage") == scope and
                row.get("role", "recipient") == "recipient", "duplicate, foreign, donor or unverified compact record")
        seen.add(identity)
        require(re.fullmatch(r"[0-9a-f]{40}", row["implementation_sha"]), "invalid compact source SHA")
        implementations.add(row["implementation_sha"])
        require(row["budget"] == 5000 and row["n"] == 100 and row["family"] == row["task"][3:] and
                row["class_label"] == row["task"][:2] and row["full_generations"] == 172 and row["partial_children"] == 12,
                "record metadata or query accounting")
        require(row["final_gap_percent"] == gap(row["optimum"], row["final_best_profit"]), "changed final gap")
        require(type(row["final_best_mask"]) is str and len(row["final_best_mask"]) == 100 and
                set(row["final_best_mask"]) <= {"0", "1"}, "invalid saved witness")
        for name in ("problem_sha256", "journal_sha256", "initial_population_sha256", "initial_rng_sha256", "first_generation_sha256"):
            require(re.fullmatch(r"[0-9a-f]{64}", row[name]), "invalid compact evidence hash")
        events = row["record_events"]
        require(type(events) is list and bool(events) and events[0] == {"q": 0, "profit": row["initial_best_profit"]},
                "missing initial record")
        previous_q, previous_profit = -1, -1
        for event in events:
            require(type(event) is dict and set(event) == {"q", "profit"} and integer(event["q"]) and
                    event["q"] <= 5000 and event["q"] > previous_q and integer(event["profit"]) and
                    event["profit"] > previous_profit, "record trajectory not strictly improving")
            gap(row["optimum"], event["profit"])
            previous_q, previous_profit = event["q"], event["profit"]
        require(events[-1]["profit"] == row["final_best_profit"], "record endpoint differs from summary")
        for target in (95, 99):
            expected_first = next((event["q"] for event in events if 100 * event["profit"] >= target * row["optimum"]), None)
            require(row["first_targets"][str(target)] == expected_first, "changed first attainment")
        activity = row["activity"]["tournament_size"]
        occupancy = activity["query_occupancy"]
        require(bool(occupancy) and sum(item["new_calls"] for item in occupancy) == 5000 and
                len({item["value"] for item in occupancy}) == len(occupancy) and
                all(integer(item["new_calls"], 1) and integer(item["value"], 2) and item["value"] <= 5 for item in occupancy),
                "invalid applied parameter occupancy")
        require(activity["changed"] == bool(activity["increases"] + activity["decreases"]) and
                activity["query_weighted_mean"] == sum(item["value"] * item["new_calls"] for item in occupancy) / 5000,
                "inconsistent tournament activity")
        if row["profile"].startswith("k"):
            require(not activity["changed"] and occupancy == [{"value": int(row["profile"][1:]), "new_calls": 5000}],
                    "static tournament changed")
        require(len(row["operator_bins"]) == 7 and sum(cell["total"] for cell in row["operator_bins"]) == 5000,
                "operator query accounting")
        reference = (row["problem_sha256"], row["optimum"], row["capacity"])
        require(row["task"] not in problems or problems[row["task"]] == reference, "mixed problem reference")
        problems[row["task"]] = reference
        pairs[identity[:3]].append(row)
    require(seen == expected, f"incomplete {scope} rectangle: {len(seen)}/{len(expected)}")
    require(len(implementations) == 1 and (expected_sha is None or implementations == {expected_sha}), "mixed source SHA")
    for entries in pairs.values():
        require(len(entries) == 6 and all(len({row[key] for row in entries}) == 1 for key in
                ("initial_population_sha256", "initial_rng_sha256", "initial_best_profit")), "different known beginning")
        first_pair = [row for row in entries if row["profile"] in ("k2", "adaptive", "replay")]
        require(len({row["first_generation_sha256"] for row in first_pair}) == 1,
                "k2/adaptive/replay first generation differs")


def family_effect_vectors(rows):
    values = {profile: mean_by_family([row for row in rows if row["profile"] == profile],
                                    lambda row: row["final_gap_percent"]) for profile in PROFILES}
    families = sorted(values["adaptive"])
    require(all(sorted(item) == families for item in values.values()), "different family coverage across controls")
    return [{"family": family, "effects": {control: values[control][family] - values["adaptive"][family]
            for control in PRIMARY_CONTROLS}} for family in families]


def family_bca(vectors, *, replicates=50000, seed=112001):
    ci_only()
    values = np.asarray(vectors, dtype=float)
    require(values.ndim == 2 and values.shape[1] == 5 and len(values) >= 5 and np.isfinite(values).all(),
            "finite family x five effects required")
    require(type(replicates) is int and replicates > 1 and type(seed) is int, "bootstrap settings")
    n, estimates = len(values), values.mean(axis=0)
    indices = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed]))).integers(0, n, size=(replicates, n))
    distribution = values[indices].mean(axis=1)
    jackknife = (values.sum(axis=0) - values) / (n - 1)
    confidence, normal = 1 - .05 / 5, NormalDist()
    tails = (normal.inv_cdf((1 - confidence) / 2), normal.inv_cdf(1 - (1 - confidence) / 2))
    result = {"status": "PERFORMED_MAIN_ONLY", "method": "BCa", "unit": "whole_family", "family_count": n,
              "replicates": replicates, "seed": seed, "confidence_each": confidence, "nominal_joint_confidence": .95,
              "resample_index_sha256": hashlib.sha256(indices.astype("<i8", copy=False).tobytes()).hexdigest(),
              "quantile_method": "linear", "bias_ties": "half_weight", "intervals": []}
    for column, control in enumerate(PRIMARY_CONTROLS):
        estimate, boot = float(estimates[column]), distribution[:, column]
        item = {"control": control, "estimate_gap_points": estimate, "lower": None, "upper": None,
                "status": "DESCRIPTIVE_ONLY", "reason": "degenerate_or_undefined_BCa",
                "positive_effect_supported": False, "negative_effect_supported": False}
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
    result["advantage_over_all_five_supported"] = all(item["positive_effect_supported"] for item in result["intervals"])
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
    for (start, profile), entries in sorted(groups.items()):
        cells.append({"start": start, "profile": profile, **summarize(entries)})
        for family, value in mean_by_family(entries, lambda row: row["final_gap_percent"]).items():
            family_cells.append({"start": start, "profile": profile, "family": family, "mean_final_gap_percent": value,
                                 "runs": sum(row["family"] == family for row in entries)})
        for label in ("UC", "WC", "SC"):
            selected = [row for row in entries if row["class_label"] == label]
            if selected:
                type_cells.append({"start": start, "profile": profile, "class_label": label, **summarize(selected)})
        activity_cells.append({"start": start, "profile": profile, "field": "tournament_size", "runs": len(entries),
                               "changed_runs": sum(row["activity"]["tournament_size"]["changed"] for row in entries),
                               "changed_fraction": weighted_mean(entries, lambda row: int(row["activity"]["tournament_size"]["changed"])),
                               **{key: sum(row["activity"]["tournament_size"][key] for row in entries)
                                  for key in ("increases", "decreases", "opportunities", "unchanged_opportunities", "boundary_opportunities")},
                               "query_weighted_mean": weighted_mean(entries, lambda row: row["activity"]["tournament_size"]["query_weighted_mean"]),
                               "query_occupancy": [{"value": k, "new_calls": sum(next((item["new_calls"] for item in row["activity"]["tournament_size"]["query_occupancy"]
                                                        if item["value"] == k), 0) for row in entries)} for k in range(2, 6)]})
        for index, label in enumerate(DISTANCE_LABELS):
            counts = {key: sum(row["operator_bins"][index][key] for row in entries)
                      for key in ("total", "crossed", "novel_crossed", "feasible_crossed", "better_both_crossed")}
            denominator = counts["crossed"]
            operator_cells.append({"start": start, "profile": profile, "distance_bin": label, **counts,
                                   **{key: counts[count] / denominator if denominator else None for key, count in
                                      (("novel_fraction", "novel_crossed"), ("feasible_fraction", "feasible_crossed"),
                                       ("better_both_fraction", "better_both_crossed"))}, "independent_sample_claim": False})
        for source in ("timings", "kernel_timing_ns"):
            names = {key for row in entries for key in row[source]} - {"preparation_ns"}
            for metric in sorted(names):
                selected = [row for row in entries if row[source].get(metric) is not None]
                timing_cells.append({"start": start, "profile": profile, "source": source, "metric": metric,
                                     "known_observations": len(selected), "unknown_observations": len(entries) - len(selected),
                                     "mean_ns": weighted_mean(selected, lambda row: row[source][metric]) if selected else None})
    effect_rows = family_effect_vectors([row for row in rows if row["start"] == "bank"])
    if scope == "main":
        require(len(effect_rows) == 10, "ten main families required")
        primary = family_bca([[item["effects"][control] for control in PRIMARY_CONTROLS] for item in effect_rows])
    else:
        primary = {"status": "NOT_PERFORMED_TECHNICAL_PILOT", "replicates": 0, "intervals": [],
                   "advantage_over_all_five_supported": False}
    primary.update({"family_effects": effect_rows, "positive_direction": "control gap minus adaptive gap, percentage points",
                    "practical_advantage_established": False, "practical_effect_threshold": None})
    examples = [row for row in rows if "example_trace" in row]
    require(len(examples) == 6 and {row["profile"] for row in examples} == set(PROFILES), "registered example missing")
    return {"schema": "ga-knapsack-tournament-feedback-series-v1", "scope": scope,
            "status": "COMPLETE_VERIFIED_MAIN" if scope == "main" else "COMPLETE_VERIFIED_PILOT",
            "implementation_sha": rows[0]["implementation_sha"], "recipient_runs": len(rows),
            "runs": len(rows), "new_search_evaluations": len(rows) * 5000,
            "donor_costs_included_in_recipient_search_budget": False,
            "donor_cost_reporting": "Separate donor manifests and phase receipts; never added twice to recipient wall time.",
            "new_search_during_aggregation": False,
            "weighting": "equal repeats -> equal tasks within family -> equal families",
            "profile_cells": cells, "family_cells": family_cells, "type_cells": type_cells,
            "activity_cells": activity_cells, "operator_cells": operator_cells, "timing_cells": timing_cells,
            "primary_analysis": primary, "prespecified_examples": examples,
            "limitations": ["Own historical heuristic; not article numerical replication or established novelty.",
                            "Donor schedules are independent; realized mean tournament sizes need not match.",
                            "A replay effect concerns this schedule distribution, not every possible open-loop schedule.",
                            "Only ten new families support primary family-level inference.",
                            "Pilot outcomes establish technical readiness, not scientific superiority.",
                            "No minimum practically useful effect was set.",
                            "Logging, validation and donor costs are separately measured and are not zero."]}


def render_report(summary, output):
    """Scientific plots: axes, units, data and legends only; captions external."""
    ci_only()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    figures = []

    def save(fig, name, caption):
        fig.tight_layout()
        path = output / (name + ".png")
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        figures.append({"file": path.name, "caption_uk": caption, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    bank = {cell["profile"]: cell for cell in summary["profile_cells"] if cell["start"] == "bank"}
    for target in (95, 99):
        if not any(bank[profile]["targets"][str(target)]["attained"] for profile in PROFILES):
            continue  # Counts remain in the summary; no empty scientific plot.
        fig, ax = plt.subplots(figsize=(9, 5))
        for profile in PROFILES:
            curve = bank[profile]["targets"][str(target)]["curve"]
            ax.step([point["q"] for point in curve], [100 * point["fraction"] for point in curve],
                    where="post", color=COLORS[profile], label=LABELS[profile], linewidth=1.7)
        top = 100 if target == 95 else min(100, max(5, 5 * math.ceil(max(100 * bank[profile]["targets"][str(target)]["curve"][-1]["fraction"]
                                                                        for profile in PROFILES) / 5)))
        ax.set(xlabel="Нові оцінювання", ylabel=f"Досягли {target}% оптимуму, % запусків", xlim=(0, 5000), ylim=(0, top))
        ax.grid(alpha=.2)
        ax.legend(fontsize=9)
        save(fig, "attainment_" + str(target), f"Частка досягнення {target}% точного оптимуму; недосягнення залишено у знаменнику. Вертикальна шкала 0–{top}%.")

    examples = {row["profile"]: row for row in summary["prespecified_examples"]}
    shown = ("k2", "adaptive", "replay")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for profile in shown:
        row = examples[profile]
        generations = row["example_trace"]["generations"]
        x = [0] + [generation["q"] for generation in generations]
        # q=0..29 uses the first applied value; a next value begins only after q=29.
        y = [generations[0]["parameters_before"]["tournament_size"]] + [generation["parameters_after"]["tournament_size"] for generation in generations]
        ax.step(x, y, where="post", label=LABELS[profile], color=COLORS[profile], linewidth=1.8)
    ax.set(xlabel="Нові оцінювання", ylabel="Розмір турніру, учасників", xlim=(0, 5000), yticks=[2, 3, 4, 5], ylim=(1.8, 5.2))
    ax.grid(alpha=.2)
    ax.legend(fontsize=9)
    save(fig, "tournament_trajectory", "Застосований розмір турніру для наперед визначеного прикладу. Нове значення починає діяти після завершення покоління.")

    fig, axes = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    for profile in shown:
        row, color = examples[profile], COLORS[profile]
        events = row["record_events"]
        axes[0].step([point["q"] for point in events] + [5000],
                     [100 * point["profit"] / row["optimum"] for point in events] + [100 * events[-1]["profit"] / row["optimum"]],
                     where="post", label=LABELS[profile], color=color)
        population = row["example_trace"]["population"]
        axes[1].plot([point["q"] for point in population], [point["unique_fraction"] for point in population], color=color)
        axes[2].plot([point["q"] for point in population], [point["mean_pairwise_hamming"] for point in population], color=color)
    axes[0].set(ylabel="Рекорд, % оптимуму")
    axes[0].legend(fontsize=9)
    axes[1].set(ylabel="Частка унікальних масок", ylim=(0, 1.03))
    axes[2].set(xlabel="Нові оцінювання", ylabel="Середня відстань, бітів", xlim=(0, 5000))
    for ax in axes:
        ax.grid(alpha=.2)
    save(fig, "search_and_diversity", "Рекорд та різноманітність завершених популяцій наперед визначеного прикладу. Префікс останнього покоління не змінює популяцію.")

    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for profile in shown:
        row, color = examples[profile], COLORS[profile]
        population = row["example_trace"]["population"]
        axes[0].plot([point["q"] for point in population],
                     [100 * point["mean_feasible_profit"] / row["optimum"]
                      if point["mean_feasible_profit"] is not None else math.nan for point in population],
                     label=LABELS[profile], color=color)
        axes[1].plot([point["q"] for point in population], [100 * point["feasible_fraction"] for point in population], color=color)
    axes[0].set(ylabel="Середня допустима цінність, % OPT")
    axes[0].legend(fontsize=9)
    axes[1].set(xlabel="Нові оцінювання", ylabel="Допустимі особини, %", xlim=(0, 5000), ylim=(0, 102))
    for ax in axes:
        ax.grid(alpha=.2)
    save(fig, "population_quality", "Середня цінність допустимих особин та частка допустимих особин завершеної популяції. Ці показники не є історичним рекордом.")

    intervals = summary["primary_analysis"]["intervals"]
    if intervals:
        fig, ax = plt.subplots(figsize=(8.5, 5))
        for index, item in enumerate(intervals):
            ax.plot(item["estimate_gap_points"], index, "o", color=COLORS["adaptive"])
            if item["lower"] is not None:
                ax.plot([item["lower"], item["upper"]], [index, index], color=COLORS["adaptive"], linewidth=2)
        ax.axvline(0, color="black", linewidth=.8)
        ax.set(yticks=range(5), yticklabels=[LABELS[item["control"]] for item in intervals],
               xlabel="Відставання контролю мінус адаптації, в. п.", ylabel="Контроль для порівняння")
        ax.grid(alpha=.2)
        save(fig, "primary_effects", "П’ять первинних ефектів із сімейними BCa-інтервалами 99%. Додатний ефект означає менше кінцеве відставання адаптивного варіанта. Вироджені інтервали не відображаються як перевірка переваги.")

    families = sorted({cell["family"] for cell in summary["family_cells"] if cell["start"] == "bank"})
    lookup = {(cell["family"], cell["profile"]): cell["mean_final_gap_percent"]
              for cell in summary["family_cells"] if cell["start"] == "bank"}
    matrix = np.array([[lookup[(family, profile)] for profile in PROFILES] for family in families])
    fig, ax = plt.subplots(figsize=(11, max(3.5, .45 * len(families))))
    image = ax.imshow(matrix, cmap="YlGnBu", aspect="auto", vmin=0, vmax=max(1, float(matrix.max())))
    ax.set(xticks=range(6), xticklabels=[LABELS[profile].replace(" ", "\n", 1) for profile in PROFILES],
           yticks=range(len(families)), yticklabels=families, xlabel="Керування турніром", ylabel="Сімейство задач")
    for y in range(len(families)):
        for x in range(6):
            ax.text(x, y, f"{matrix[y, x]:.2f}", ha="center", va="center",
                    color="white" if matrix[y, x] > matrix.max() * .6 else "black", fontsize=9)
    fig.colorbar(image, ax=ax, label="Кінцеве відставання, %; менше краще")
    save(fig, "family_quality", "Середнє кінцеве відставання за сімействами; повторення та задачі усереднено послідовно. Усі шість варіантів показано без добору сприятливих випадків.")
    (output / "figure_manifest.json").write_text(json.dumps({"figures": figures}, ensure_ascii=False, indent=2), encoding="utf-8")
    return figures


render = render_report

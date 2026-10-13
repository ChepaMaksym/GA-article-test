"""Registered paired/family analysis of independently verified compact rows.

This module has no search interface and imports no private production operator.
The two registered inferential endpoints are the only superiority assessments.
Missing runs are not failures, zeros, or bootstrap observations.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import math
import re
from statistics import NormalDist
from typing import Callable, Mapping, Sequence

import numpy as np

from .contract import ci_only


PROTOCOL = "GA-DIVERSITY-CROSSOVER-MAIN-V1"
METHODS = ("baseline", "directed", "repeated", "mutation_control")
MODELS = ("Flat", "OneMax", "Jump4", "Jump8")
CLASSES = ("UC", "WC", "SC")
FAMILIES = tuple(f"s{i:03d}" for i in range(10))
KNAPSACK = tuple(f"{kind}-{family}" for kind in CLASSES for family in FAMILIES)
TASKS = MODELS + KNAPSACK
CENTERS = ("UC-s000", "UC-s002", "UC-s003", "UC-s004", "UC-s009",
           "WC-s001", "WC-s002", "WC-s004", "WC-s005", "WC-s006",
           "WC-s007", "WC-s008", "WC-s009", "SC-s005")
GLOBAL_CENTERS = tuple(task for task in KNAPSACK if task not in CENTERS)
SEEDS = tuple(range(71001, 71031))
DIAGNOSTIC_SEED = 71901
BUDGET = 5000
EXPECTED_RUNS = 6304


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def expected_identities() -> set[tuple[str, str, str, int]]:
    """Independent reconstruction of the registered physical-run rectangle."""
    identities = {(task, start, method, seed)
                  for task in MODELS for start in ("cloned", "bank")
                  for method in METHODS for seed in SEEDS}
    identities.update((task, "bank", method, seed)
                      for task in KNAPSACK for method in METHODS for seed in SEEDS)
    identities.update((task, "cloned", method, seed)
                      for task in CENTERS for method in METHODS for seed in SEEDS)
    identities.update((task, "cloned", method, DIAGNOSTIC_SEED)
                      for task in GLOBAL_CENTERS for method in METHODS)
    require(len(identities) == EXPECTED_RUNS, "registered rectangle arithmetic differs")
    return identities


def identity(row: Mapping) -> tuple[str, str, str, int]:
    require(all(name in row for name in ("task", "start", "method", "seed")),
            "compact row lacks run identity")
    require(type(row["seed"]) is int, "run seed must be an integer, not boolean")
    require(all(isinstance(row[name], str) for name in ("task", "start", "method")),
            "run identity names must be strings")
    return row["task"], row["start"], row["method"], row["seed"]


def count(value, name: str, maximum: int | None = None) -> int:
    require(type(value) is int and value >= 0 and (maximum is None or value <= maximum),
            f"invalid integer count: {name}")
    return value


def finite(value, name: str) -> float:
    require(type(value) in (int, float) and math.isfinite(value), f"nonfinite number: {name}")
    return float(value)


def conditional_fraction(numerator: int, denominator: int) -> dict:
    count(numerator, "conditional numerator")
    count(denominator, "conditional denominator")
    require(numerator <= denominator, "conditional numerator exceeds denominator")
    return {"status": "DEFINED" if denominator else "NOT_APPLICABLE",
            "value": numerator / denominator if denominator else None,
            "numerator": numerator, "denominator": denominator}


def validate_complete_row(row: Mapping) -> None:
    """Validate endpoint semantics independently of a VERIFIED status string."""
    task, start, method, seed = identity(row)
    require(row.get("verification_status") == "VERIFIED", "unverified complete row")
    require(row.get("series") == ("diagnostic" if seed == DIAGNOSTIC_SEED else "main"),
            "main/diagnostic series mismatch")
    search = row["search"]
    actual_method = "baseline" if method == "mutation_control" else method
    require(search.get("method") == actual_method and search.get("status") == "COMPLETE",
            "search method/status mismatch")
    for name in ("budget", "new_calls", "physical_calls"):
        require(type(search.get(name)) is int and search[name] == BUDGET,
                "each complete search requires exactly 5000 new physical calls")
    steps = count(search["steps"], "steps", BUDGET)
    completed = count(search["completed_steps"], "completed steps", steps)
    partial = count(search["incomplete_steps"], "incomplete steps", 1)
    require(steps == completed + partial and steps > 0, "step accounting differs")
    count(search["accepted_steps"], "accepted steps", completed)
    cross_steps = count(search["crossover_steps"], "crossover steps", steps)
    feasible = count(search["candidate_feasible"], "feasible candidates", BUDGET)
    invalid = count(search["invalid_candidates"], "invalid candidates", BUDGET)
    require(feasible + invalid == BUDGET, "candidate feasibility does not partition budget")
    count(search["duplicate_candidates"], "duplicate candidates", BUDGET)
    initial_record, final_record = search["initial_record"], search["record"]
    for label, record in (("initial", initial_record), ("terminal", final_record)):
        score = record["score"]
        value = count(score["value"], f"{label} record value")
        require(score.get("feasible") is True and score.get("key") == [1, value],
                "record must be an independently verified feasible value")
        require(isinstance(record.get("mask"), str) and len(record["mask"]) == 100
                and set(record["mask"]) <= {"0", "1"}, "invalid record genotype")
        count(record["call"], f"{label} record call", BUDGET)
    initial, final = initial_record["score"]["value"], final_record["score"]["value"]
    require(initial_record["call"] == 0 and final >= initial, "record lost initial incumbent")
    require(row.get("initial_value") == initial, "initial value alias differs")
    first = search["first_improvement_call"]
    if final > initial:
        require(type(first) is int and 1 <= first <= final_record["call"] <= BUDGET,
                "improving record lacks a valid first evaluated improvement")
    else:
        require(first is None and final_record["call"] == 0, "unchanged record has an improvement time")
    expected_applicable = start == "cloned" and (task in CENTERS or task in ("Jump4", "Jump8"))
    require(row.get("escape_applicable") is expected_applicable, "escape applicability mismatch")
    expected_escape = first is not None if expected_applicable else None
    require(row.get("escape") is expected_escape, "escape flag differs from evaluated first improvement")
    require(row.get("escape_call") == (first if expected_applicable else None), "escape time differs")
    if task == "Flat":
        require(initial == final == 0 and first is None, "Flat cannot have quality improvement")
    if task.startswith("Jump"):
        target = 100 + int(task[4:])
        require(initial == 100 and final in (100, target), "Jump plateau/global endpoint differs")
    elif task == "OneMax":
        require(final <= 100, "OneMax exceeds dimension")
    optimum = row.get("exact_optimum")
    if task == "Flat":
        require(optimum is None and row.get("relative_gap") is None,
                "Flat quality gap is not applicable")
    elif task in MODELS:
        expected_optimum = 100 if task == "OneMax" else 100 + int(task[4:])
        require(optimum == expected_optimum, "model posthoc optimum mismatch")
    else:
        require(type(optimum) is int and optimum > 0 and final <= optimum,
                "missing/inconsistent external exact optimum")
    if optimum is not None:
        require(math.isclose(finite(row.get("relative_gap"), "relative gap"),
                             (optimum - final) / optimum, rel_tol=1e-12, abs_tol=1e-15),
                "posthoc gap differs from terminal record")
    if seed == DIAGNOSTIC_SEED:
        require(task in GLOBAL_CENTERS and initial == final == optimum and first is None,
                "global negative control is inconsistent with exact optimum")
    product = row["productivity"]
    cross = count(product["crossover_candidates"], "crossover candidates", BUDGET)
    both = count(product["both_parents_feasible_candidates"], "both feasible parents", cross)
    before = count(product["pre_mutation_feasible"], "feasible intermediate candidates", cross)
    pre = count(product["pre_mutation_better_than_both"], "U_pre", min(both, before))
    post = count(product["post_mutation_better_than_both"], "U_post", min(both, feasible))
    require(cross_steps <= cross <= (4 if method == "repeated" else 1) * cross_steps,
            "crossover candidate/step accounting differs")
    require(BUDGET == (steps - cross_steps) + cross, "mutation/crossover query partition differs")
    if method != "repeated":
        require(steps == BUDGET and partial == 0 and cross == cross_steps,
                "single-candidate profile has batch accounting")
    if method == "mutation_control":
        require(cross_steps == cross == both == before == pre == post == 0,
                "mutation branch cannot create two-parent crossover events")
    if task == "Flat":
        require(pre == post == 0, "Flat cannot have candidates better than both parents")
    expected_conditional = "DEFINED" if both else "NOT_APPLICABLE"
    require(product.get("conditional_status") == expected_conditional,
            "zero conditional denominator must be NOT_APPLICABLE")
    for name, numerator in (("pre_mutation_better_fraction", pre),
                            ("post_mutation_better_fraction", post)):
        if both:
            require(math.isclose(finite(product.get(name), name), numerator / both,
                                 rel_tol=1e-12, abs_tol=1e-15), "conditional fraction differs")
        else:
            require(product.get(name) is None, "undefined conditional fraction must be null")
    for alias, original in (("U_post", post), ("U_pre", pre), ("both_parents_feasible", both)):
        if alias in product:
            require(type(product[alias]) is int and product[alias] == original,
                    "productivity alias differs")
    if "verification_calls" in row:
        require(type(row["verification_calls"]) is int
                and row["verification_calls"] == 30 + BUDGET + cross,
                "independent verification call accounting differs")
    directed = row["directed_activity"]
    dsteps = count(directed["steps"], "directed steps", cross_steps)
    active = count(directed["active_steps"], "active genotype changes", dsteps)
    positions = count(directed["changed_position_steps"], "changed parent positions", dsteps)
    require(active <= positions, "genotype change cannot exceed position change")
    require(dsteps == (cross_steps if method == "directed" else 0), "directed branch count differs")
    require(search["directed_active_steps"] == active and search["directed_changed_steps"] == positions,
            "directed activity differs from search summary")
    metrics = search["metrics"]
    for name in ("unique_fraction", "diversity", "feasible_fraction"):
        require(0 <= finite(metrics[name], name) <= 1, "terminal metric outside [0,1]")
    require(metrics["unique_fraction"] >= 1 / 30 and metrics["feasible_fraction"] >= 1 / 30,
            "elitist population cannot be empty or lose all feasible members")
    require(0 <= finite(metrics["mean_feasible_value"], "terminal feasible mean") <= final,
            "population feasible mean exceeds evaluated record")


def validate_rows(rows: Sequence[Mapping]) -> dict:
    """Reject mixed/duplicated/unregistered evidence; expose missing data explicitly."""
    expected = expected_identities()
    seen, complete, hashes = set(), set(), set()
    incomplete = []
    for row in rows:
        key = identity(row)
        require(key in expected, "unregistered task/start/method/seed")
        require(key not in seen, "duplicate physical run identity")
        seen.add(key)
        sha = row.get("implementation_sha")
        require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha) is not None,
                "missing or invalid implementation commit SHA")
        hashes.add(sha)
        if row.get("status") == "COMPLETE":
            validate_complete_row(row)
            complete.add(key)
        else:
            incomplete.append({"identity": list(key), "status": row.get("status", "MISSING_STATUS")})
    require(len(hashes) <= 1, "mixed implementation SHA fingerprints")
    order = lambda key: (TASKS.index(key[0]), ("cloned", "bank").index(key[1]), key[3], METHODS.index(key[2]))
    missing = sorted(expected - seen, key=order)
    return {"status": "COMPLETE_MAIN" if complete == expected else "INCOMPLETE_MAIN",
            "expected_runs": EXPECTED_RUNS, "observed_runs": len(seen), "complete_runs": len(complete),
            "missing_identities": [list(key) for key in missing], "incomplete_runs": incomplete,
            "implementation_sha": next(iter(hashes)) if hashes else None,
            "completed_search_calls": len(complete) * BUDGET,
            "main_complete_runs": sum(key[3] != DIAGNOSTIC_SEED for key in complete),
            "diagnostic_complete_runs": sum(key[3] == DIAGNOSTIC_SEED for key in complete)}


def mcnemar_exact(b: int, c: int) -> float:
    """Exact registered two-sided binomial McNemar; no asymptotic approximation."""
    count(b, "directed-only successes")
    count(c, "baseline-only successes")
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def bca_mean(values: Sequence[float], *, seed: int, resamples: int = 50000,
             confidence: float = 0.975, unit: str = "whole_family") -> dict:
    """BCa mean with whole-unit draws/jackknife, half-weight ties, linear quantiles.

    Parameters other than the registered defaults exist for deterministic CI
    fixtures only. Scientific analyze() fixes all settings before reading rows.
    No percentile/normal fallback or zero-width interval is produced.
    """
    x = np.asarray(values, dtype=np.float64)
    require(x.ndim == 1 and len(x) >= 2 and np.isfinite(x).all(), "BCa needs finite whole-unit values")
    require(type(seed) is int and seed >= 0 and type(resamples) is int and resamples > 1,
            "invalid bootstrap seed/count")
    require(0 < confidence < 1, "invalid bootstrap confidence")
    estimate, n = float(x.mean()), len(x)
    result = {"method": "BCa", "estimate": estimate, "lower": None, "upper": None,
              "status": "UNDEFINED_BCA", "reason": None, "confidence": confidence,
              "resamples": resamples, "seed": seed, "unit_count": n,
              "bootstrap_unit": unit, "jackknife_unit": unit,
              "rng": f"PCG64(SeedSequence([{seed}]))", "ties": "half_weight",
              "quantile_method": "linear", "resample_index_sha256": None}
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed])))
    indices = rng.integers(0, n, size=(resamples, n), dtype=np.int64)
    result["resample_index_sha256"] = hashlib.sha256(indices.astype("<i8", copy=False).tobytes()).hexdigest()
    distribution = x[indices].mean(axis=1)
    if np.all(distribution == distribution[0]):
        result["reason"] = "constant_bootstrap_distribution"
        return result
    jackknife = (x.sum() - x) / (n - 1)
    delta = jackknife.mean() - jackknife
    denominator = 6 * float(np.sum(delta ** 2)) ** 1.5
    if denominator == 0 or not math.isfinite(denominator):
        result["reason"] = "zero_or_nonfinite_jackknife_variation"
        return result
    acceleration = float(np.sum(delta ** 3)) / denominator
    fraction = (np.count_nonzero(distribution < estimate) + 0.5 * np.count_nonzero(distribution == estimate)) / resamples
    if not math.isfinite(acceleration) or not 0 < fraction < 1:
        result["reason"] = "nonfinite_bias_or_acceleration"
        return result
    normal = NormalDist()
    z0 = normal.inv_cdf(float(fraction))
    tails = (normal.inv_cdf((1 - confidence) / 2), normal.inv_cdf((1 + confidence) / 2))
    adjusted = []
    for tail in tails:
        divisor = 1 - acceleration * (z0 + tail)
        adjusted.append(math.nan if divisor == 0 or not math.isfinite(divisor)
                        else normal.cdf(z0 + (z0 + tail) / divisor))
    if not all(math.isfinite(q) and 0 < q < 1 for q in adjusted) or adjusted[0] >= adjusted[1]:
        result["reason"] = "invalid_adjusted_quantiles"
        return result
    low, high = map(float, np.quantile(distribution, adjusted, method="linear"))
    if not math.isfinite(low) or not math.isfinite(high) or low >= high:
        result["reason"] = "nonfinite_reversed_or_degenerate_interval"
        return result
    result.update(status="DEFINED_BCA", lower=low, upper=high, reason=None,
                  bias_correction=z0, bias_fraction=float(fraction), acceleration=acceleration,
                  adjusted_quantiles=adjusted)
    return result


def family_values(rows: Sequence[Mapping], extractor: Callable[[Mapping], float]) -> list[dict]:
    """Equal seeds within task, tasks within family; never weight by row count."""
    by_task = defaultdict(list)
    for row in rows:
        require(row["task"] in KNAPSACK, "family averaging requires a registered KPLIB task")
        by_task[row["task"]].append(finite(extractor(row), "family observation"))
    require(bool(by_task), "family averaging requires observations")
    by_family = defaultdict(list)
    for task in sorted(by_task):
        by_family[task.split("-")[1]].append((task, math.fsum(by_task[task]) / len(by_task[task])))
    return [{"family": family, "tasks": [task for task, _ in by_family[family]],
             "task_count": len(by_family[family]),
             "value": math.fsum(value for _, value in by_family[family]) / len(by_family[family])}
            for family in sorted(by_family)]


def equal_family_mean(rows: Sequence[Mapping], extractor: Callable[[Mapping], float]) -> float:
    families = family_values(rows, extractor)
    return math.fsum(entry["value"] for entry in families) / len(families)


def escape_observation(row: Mapping) -> dict:
    """Distinguish right-censored nonexit from an observed exit at query 5000."""
    if not row["escape_applicable"]:
        return {"status": "NOT_APPLICABLE", "event": None, "call": None,
                "restricted_calls": None, "censored": None}
    event = row["escape"]
    call = row["escape_call"]
    require(type(event) is bool and ((type(call) is int and 1 <= call <= BUDGET) if event else call is None),
            "invalid event/censoring pair")
    return {"status": "OBSERVED_EXIT" if event else "RIGHT_CENSORED_NONEXIT", "event": event,
            "call": call, "restricted_calls": call if event else BUDGET, "censored": not event}


def summarize_group(rows: Sequence[Mapping]) -> dict:
    require(bool(rows) and all(row["status"] == "COMPLETE" for row in rows), "descriptive group needs complete rows")
    n = len(rows)
    mean = lambda getter: math.fsum(float(getter(row)) for row in rows) / n
    cross = sum(row["productivity"]["crossover_candidates"] for row in rows)
    both = sum(row["productivity"]["both_parents_feasible_candidates"] for row in rows)
    pre = sum(row["productivity"]["pre_mutation_better_than_both"] for row in rows)
    post = sum(row["productivity"]["post_mutation_better_than_both"] for row in rows)
    applicable = [escape_observation(row) for row in rows if row["escape_applicable"]]
    gaps = [row["relative_gap"] for row in rows if row["relative_gap"] is not None]
    flat = all(row["task"] == "Flat" for row in rows)
    return {"runs": n, "new_calls": n * BUDGET, "inference": "DESCRIPTIVE_ONLY",
            "initial_record_mean": mean(lambda row: row["search"]["initial_record"]["score"]["value"]),
            "terminal_record_mean": mean(lambda row: row["search"]["record"]["score"]["value"]),
            "quality_improvement_status": "NOT_APPLICABLE_FLAT" if flat else "DESCRIPTIVE_ONLY",
            "mean_record_gain": None if flat else mean(lambda row: row["search"]["record"]["score"]["value"] - row["initial_value"]),
            "mean_relative_gap": math.fsum(gaps) / len(gaps) if gaps else None,
            "escape_applicable_runs": len(applicable),
            "escapes": sum(item["event"] for item in applicable) if applicable else None,
            "nonexits": sum(item["censored"] for item in applicable) if applicable else None,
            "escape_rate": sum(item["event"] for item in applicable) / len(applicable) if applicable else None,
            "mean_restricted_calls": math.fsum(item["restricted_calls"] for item in applicable) / len(applicable) if applicable else None,
            "crossover_candidates": cross, "both_parents_feasible_candidates": both,
            "U_pre": pre, "U_post": post, "q_per_budget": post / (n * BUDGET),
            "conditional_productivity_pooled": conditional_fraction(post, both),
            "crossover_query_fraction": cross / (n * BUDGET),
            "candidate_feasible_fraction": mean(lambda row: row["search"]["candidate_feasible"] / BUDGET),
            "invalid_candidates": sum(row["search"]["invalid_candidates"] for row in rows),
            "duplicate_candidates": sum(row["search"]["duplicate_candidates"] for row in rows),
            "accepted_replacements": sum(row["search"]["accepted_steps"] for row in rows),
            "incomplete_batches": sum(row["search"]["incomplete_steps"] for row in rows),
            "mean_terminal_feasible_value": mean(lambda row: row["search"]["metrics"]["mean_feasible_value"]),
            "mean_terminal_unique_fraction": mean(lambda row: row["search"]["metrics"]["unique_fraction"]),
            "mean_terminal_D": mean(lambda row: row["search"]["metrics"]["diversity"]),
            "directed_active_steps": sum(row["directed_activity"]["active_steps"] for row in rows),
            "directed_changed_position_steps": sum(row["directed_activity"]["changed_position_steps"] for row in rows)}


def analyze(rows: Sequence[Mapping]) -> dict:
    """Analyze only the complete registered rectangle, in GitHub Actions."""
    ci_only()
    rows = list(rows)
    completeness = validate_rows(rows)
    result = {"schema_version": "diversity-main-analysis-v1", "protocol_id": PROTOCOL,
              **completeness, "primary": None, "descriptive_groups": [],
              "local_family_summaries": [], "knapsack_bank_method_summaries": [],
              "primary_claim_count": 2, "secondary_inference": "DESCRIPTIVE_ONLY_NO_ADDITIONAL_P_VALUES",
              "practical_superiority_authorized": False, "adaptive_parameters": False,
              "incomplete_rows_treated_as_zero": False}
    if result["status"] != "COMPLETE_MAIN":
        return result
    indexed = {identity(row): row for row in rows}
    paired, table = [], {"both_fail": 0, "directed_only": 0, "baseline_only": 0, "both_succeed": 0}
    for seed in SEEDS:
        baseline = indexed[("Jump4", "cloned", "baseline", seed)]
        directed = indexed[("Jump4", "cloned", "directed", seed)]
        a, b = baseline["escape"], directed["escape"]
        key = "both_succeed" if a and b else "baseline_only" if a else "directed_only" if b else "both_fail"
        table[key] += 1
        paired.append({"seed": seed, "baseline": int(a), "directed": int(b), "difference": int(b) - int(a),
                       "baseline_call": baseline["escape_call"], "directed_call": directed["escape_call"]})
    delta_j = math.fsum(pair["difference"] for pair in paired) / len(SEEDS)
    p = mcnemar_exact(table["directed_only"], table["baseline_only"])
    h1 = {"id": "H1", "task": "Jump4", "start": "cloned", "unit": "whole_paired_seed",
          "paired_count": 30, "paired_table": table, "pairs": paired, "estimate": delta_j,
          "estimate_percentage_points": 100 * delta_j, "test": "exact_two_sided_mcnemar",
          "exact_p": p, "alpha": 0.025, "nominal_superiority_supported": delta_j > 0 and p < 0.025,
          "supplementary_bca": bca_mean([pair["difference"] for pair in paired], seed=72001, unit="whole_paired_seed")}
    task_contrasts, paired_k = [], []
    for task in KNAPSACK:
        differences = []
        for seed in SEEDS:
            baseline = indexed[(task, "bank", "baseline", seed)]["productivity"]["post_mutation_better_than_both"]
            repeated = indexed[(task, "bank", "repeated", seed)]["productivity"]["post_mutation_better_than_both"]
            difference = (repeated - baseline) / BUDGET
            differences.append(difference)
            paired_k.append({"task": task, "seed": seed, "baseline_U_post": baseline,
                             "repeated_U_post": repeated, "difference": difference})
        task_contrasts.append({"task": task, "paired_seed_count": 30,
                               "value": math.fsum(differences) / len(SEEDS)})
    family_contrasts = family_values(task_contrasts, lambda entry: entry["value"])
    require(len(family_contrasts) == 10 and all(entry["task_count"] == 3 for entry in family_contrasts),
            "H2 requires all three classes in each of ten families")
    interval_k = bca_mean([entry["value"] for entry in family_contrasts], seed=72002, unit="whole_family")
    supported_k = interval_k["status"] == "DEFINED_BCA" and interval_k["lower"] > 0
    h2 = {"id": "H2", "start": "bank", "comparison": "repeated-minus-baseline", "unit": "whole_family",
          "estimate": math.fsum(entry["value"] for entry in family_contrasts) / 10,
          "aggregation": "paired_seed_to_task_to_three_class_family_to_equal_ten_family_mean",
          "pairs": paired_k, "task_contrasts": task_contrasts, "family_contrasts": family_contrasts,
          "bca": interval_k, "nominal_superiority_supported": supported_k,
          "inference_status": "NOMINAL_POSITIVE_EVIDENCE" if supported_k else
                              "NO_POSITIVE_EVIDENCE" if interval_k["status"] == "DEFINED_BCA" else "DESCRIPTIVE_ONLY_UNDEFINED_BCA"}
    result["primary"] = {"H1": h1, "H2": h2}
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["task"], row["start"], row["method"], row["series"])].append(row)
    order = lambda item: (TASKS.index(item[0]), ("cloned", "bank").index(item[1]), METHODS.index(item[2]))
    result["descriptive_groups"] = [{"task": key[0], "start": key[1], "method": key[2], "series": key[3],
                                     **summarize_group(grouped[key])} for key in sorted(grouped, key=order)]
    for method in METHODS:
        local = [row for row in rows if row["task"] in CENTERS and row["start"] == "cloned" and row["method"] == method]
        families = family_values(local, lambda row: int(row["escape"]))
        require(len(families) == 10, "local descriptive endpoint lacks a family")
        result["local_family_summaries"].append({"method": method, "runs": len(local),
            "raw_escapes": sum(row["escape"] for row in local), "families": families,
            "equal_family_escape_rate": math.fsum(entry["value"] for entry in families) / 10,
            "equal_family_restricted_calls": equal_family_mean(local, lambda row: escape_observation(row)["restricted_calls"]),
            "strict_centers": {"task_count": 13, **summarize_group([row for row in local if row["task"] != "SC-s005"])},
            "plateau": {"task": "SC-s005", **summarize_group([row for row in local if row["task"] == "SC-s005"])},
            "inference": "DESCRIPTIVE_ONLY"})
        bank = [row for row in rows if row["task"] in KNAPSACK and row["start"] == "bank" and row["method"] == method]
        result["knapsack_bank_method_summaries"].append({"method": method, **summarize_group(bank),
            "equal_family_q": equal_family_mean(bank, lambda row: row["productivity"]["post_mutation_better_than_both"] / BUDGET),
            "equal_family_crossover_query_fraction": equal_family_mean(bank, lambda row: row["productivity"]["crossover_candidates"] / BUDGET),
            "equal_family_candidate_feasible_fraction": equal_family_mean(bank, lambda row: row["search"]["candidate_feasible"] / BUDGET)})
    result["nominal_primary_superiority_claims"] = {"H1": h1["nominal_superiority_supported"], "H2": supported_k}
    return result

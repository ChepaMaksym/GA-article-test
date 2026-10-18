"""Prospective CI-only analysis of independently verified adaptation journals.

No search, exact solver or production evaluator is imported.  Lambda remains
blocked; missing runs and undefined correlations are never encoded as zeros.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
from statistics import NormalDist, fmean

import numpy as np


METHODS = ("classical", "adaptive_mutation", "adaptive_crossover", "unbalanced_gap", "balanced_gap")
DEFERRED = ("lambda_fixed", "lambda_own")
CONTRASTS = (("adaptive_mutation", "classical"), ("adaptive_crossover", "classical"),
             ("balanced_gap", "unbalanced_gap"))
_REGISTRY_SHA = "7e9b8fc893889426e2d3b57610e3a91c09263fcdff488cf15a2b84efe1bdc70f"
_DATA_MANIFEST_SHA = "528fee8da7d7cb776fb851e6a05949133830e9533c4091cbb4e8698ac19fb0df"
_ENVELOPE = {"task", "family", "start", "seed", "method", "implementation_sha", "log", "optimum", "center_profit"}
_IDENTITY = ("task", "start", "seed", "method")
_ROW_FIELDS = set(("schema verification_status task start seed method family implementation_sha budget journal_sha256 "
                   "initial_population_sha256 initial_rng_sha256 problem_sha256 input_binding "
                   "optimum center_profit initial_best_profit final_best_profit final_gap_percent escaped first_escape "
                   "capped_escape_calls first_99 observations windows early late record_events population_trace diagnostics accounting").split())


def _require(condition, message):
    if not condition:
        raise ValueError("Adaptation analysis: " + message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "execution is CI-only")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test", "wrong repository")
    _require(os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover", "wrong branch")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _score(problem, mask):
    _require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"}, "invalid mask")
    weight = sum(problem["weights"][i] for i, bit in enumerate(mask) if bit == "1")
    profit = sum(problem["profits"][i] for i, bit in enumerate(mask) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _population(refs, masks, scores, n, query):
    selected_masks = [masks[ref] for ref in refs]
    feasible = [scores[ref]["profit"] for ref in refs if scores[ref]["feasible"]]
    mu = len(refs)
    # Counting differing unordered pairs locus by locus is independent of the
    # candidate or archive selection rules and includes duplicate individuals.
    differences = sum(sum(mask[i] == "1" for mask in selected_masks) *
                      (mu - sum(mask[i] == "1" for mask in selected_masks)) for i in range(n))
    denominator = n * mu * (mu - 1) // 2
    return {"query": query, "mu": mu, "feasible_fraction": len(feasible) / mu,
            "mean_feasible_profit": fmean(feasible) if feasible else None,
            "unique_genotypes": len(set(selected_masks)),
            "normalized_hamming": differences / denominator if denominator else 0.0}


def _parent_concentration(parent_pairs):
    uses = Counter(mask for pair in parent_pairs for mask in pair)
    denominator = 2 * len(parent_pairs)
    return {"parent_uses": denominator, "unique_parents": len(uses),
            "maximum_parent_share": max(uses.values()) / denominator if denominator else None}


def extract_run(envelope):
    """Verify then compact one run; small positive budgets are CI fixtures only."""
    _ci_only()
    _require(type(envelope) is dict and set(envelope) == _ENVELOPE, "envelope fields differ")
    _require(type(envelope["task"]) is str, "task must be a string")
    match = re.fullmatch(r"(UC|WC|SC)-(s\d{3})", envelope["task"])
    _require(match is not None and envelope["family"] == match.group(2), "task/family mismatch")
    _require(envelope["start"] in ("bank", "cloned"), "invalid start")
    _require(type(envelope["seed"]) is int and envelope["seed"] >= 0, "invalid seed")
    _require(envelope["method"] in METHODS, "unsupported or blocked method")
    _require(type(envelope["implementation_sha"]) is str and
             re.fullmatch(r"[0-9a-f]{40}", envelope["implementation_sha"]), "invalid implementation SHA")
    optimum, center = envelope["optimum"], envelope["center_profit"]
    _require(type(optimum) is int and optimum > 0, "external optimum must be a positive integer")
    _require((envelope["start"] == "bank" and center is None) or
             (envelope["start"] == "cloned" and type(center) is int and 0 <= center <= optimum), "invalid center")
    from .comparison import verify_profile_log

    log = envelope["log"]
    receipt = verify_profile_log(envelope["method"], log)
    _require(receipt.get("verification_status", receipt.get("status")) == "VERIFIED", "log was not verified")
    cases, _ = _cases()
    _require(envelope["task"] in cases, "task absent from frozen case order")
    task_index = cases[envelope["task"]]["case_order_index"]
    start_index = 0 if envelope["start"] == "cloned" else 1
    initial_states = {}
    for channel, name in enumerate(("initialization", "selection", "branch", "crossover", "mutation", "ties")):
        bit_generator = np.random.PCG64(np.random.SeedSequence([envelope["seed"], task_index, start_index, channel]))
        initial_states[name] = deepcopy(bit_generator.state)
    _require(_canonical(log["rng_initial"]) == _canonical(initial_states),
             "initial RNG states do not match declared seed/task/start")
    problem, budget = log["problem"], log["budget"]
    _require(type(budget) is int and budget > 0, "invalid budget")
    input_binding = "SOFTWARE_FIXTURE_NOT_KPLIB"
    if budget == 5000:
        _bind_scientific_input(envelope)
        input_binding = "KPLIB_BYTES_AND_REGISTERED_INITIAL_STATE"
    masks = list(log["initial_masks"])
    scores = [_score(problem, mask) for mask in masks]
    if envelope["start"] == "cloned":
        _require(len(set(masks)) == 1 and all(item["feasible"] and item["profit"] == center for item in scores),
                 "cloned initial population differs from stated center")
    initial_best = max(item["profit"] for item in scores if item["feasible"])
    best = initial_best
    records = [best]
    record_events = [{"query": 0, "profit": best}]
    population_trace = [_population(list(range(len(masks))), masks, scores, problem["n"], 0)]
    applied_pm, applied_pc, feasible_flags, parent_pairs, archive_sizes, memory_switches = [], [], [], [], [], []
    generation_by_number = {event["generation"]: event for event in log["generations"]}
    for candidate in log["candidates"]:
        event = generation_by_number[candidate["generation"]]
        raw = _score(problem, candidate["mask"])
        _require(all(candidate[key] == raw[key] and type(candidate[key]) is type(raw[key]) for key in raw),
                 "raw score differs after independent log replay")
        if "parent_masks" in candidate:
            parents = list(candidate["parent_masks"])
        else:
            parents = [masks[event["population_before"][position]] for position in candidate["parent_indices"]]
        parent_pairs.append(parents)
        applied_pm.append(float(event["p_m"]))
        applied_pc.append(float(event.get("p_c", 0.9)))
        feasible_flags.append(raw["feasible"])
        if "plan" in event:
            plan = event["plan"]
            archive_sizes.append(len(plan["archive"]))
            actual = candidate["selection_event"]
            if envelope["method"] == "balanced_gap" and not actual["singleton"]:
                draws = actual["tournament_draws"]
                # Shadow only the first parent.  A different winner could need
                # a different neighbor draw; none is generated by diagnostics.
                shadow_first = draws[0]
                for drawn in draws[1:]:
                    if plan["gaps"][drawn] > plan["gaps"][shadow_first]:
                        shadow_first = drawn
                memory_switches.append(shadow_first != actual["first_index"])
            else:
                memory_switches.append(False)
        else:
            archive_sizes.append(None)
            memory_switches.append(None)
        if raw["feasible"] and raw["profit"] > best:
            best = raw["profit"]
            record_events.append({"query": candidate["call"], "profit": best})
        _require(best <= optimum, "record exceeds external exact optimum")
        records.append(best)
        masks.append(candidate["mask"])
        scores.append(raw)
        if candidate["call"] == event["end_call"] and event["complete"]:
            population_trace.append(_population(event["population_after"], masks, scores,
                                                problem["n"], candidate["call"]))
    _require(len(records) == budget + 1 and len(log["candidates"]) == budget, "incomplete records")
    _require(initial_best <= optimum, "initial record exceeds external optimum")
    first_escape = (next((q for q in range(1, budget + 1) if records[q] > center), None)
                    if center is not None else None)
    first_99 = next((q for q, profit in enumerate(records) if 100 * profit >= 99 * optimum), None)
    queries = sorted({0, min(1000, budget), min(2500, budget), budget})
    observations = [{"query": q, "best_profit": records[q], "gap_percent": 100 * (optimum - records[q]) / optimum,
                     "attained_99": 100 * records[q] >= 99 * optimum,
                     "escaped": records[q] > center if center is not None else None} for q in queries]
    windows = []
    for start in range(0, budget, 500):
        end = min(start + 500, budget)
        archive = [value for value in archive_sizes[start:end] if value is not None]
        switches = [value for value in memory_switches[start:end] if value is not None]
        windows.append({"first_query": start + 1, "last_query": end, "queries": end - start,
                        "mean_p_m": fmean(applied_pm[start:end]), "mean_p_c": fmean(applied_pc[start:end]),
                        "feasible_fraction": fmean(feasible_flags[start:end]),
                        "mean_archive_size": fmean(archive) if archive else None,
                        "memory_switch_fraction": fmean(switches) if switches else None,
                        **_parent_concentration(parent_pairs[start:end])})
    half = budget // 2
    early = {"mean_p_m": fmean(applied_pm[:half]) if half else None,
             "mean_p_c": fmean(applied_pc[:half]) if half else None,
             "feasible_fraction": fmean(feasible_flags[:half]) if half else None,
             **_parent_concentration(parent_pairs[:half])}
    late = {"gain_over_optimum": (records[-1] - records[half]) / optimum,
            "feasible_fraction": fmean(feasible_flags[half:]),
            **_parent_concentration(parent_pairs[half:])}
    return {"schema": "ga-adaptation-compact-run-v1", "verification_status": "VERIFIED",
            **{key: envelope[key] for key in _IDENTITY}, "family": envelope["family"],
            "implementation_sha": envelope["implementation_sha"], "budget": budget,
            "journal_sha256": hashlib.sha256(_canonical(log)).hexdigest(),
            "initial_population_sha256": hashlib.sha256(_canonical({"masks": log["initial_masks"], "scores": log["initial_scores"]})).hexdigest(),
            "initial_rng_sha256": hashlib.sha256(_canonical(log["rng_initial"])).hexdigest(),
            "problem_sha256": hashlib.sha256(_canonical(problem)).hexdigest(),
            "input_binding": input_binding,
            "optimum": optimum, "center_profit": center, "initial_best_profit": initial_best,
            "final_best_profit": best, "final_gap_percent": 100 * (optimum - best) / optimum,
            "escaped": first_escape is not None if center is not None else None,
            "first_escape": first_escape,
            "capped_escape_calls": (first_escape if first_escape is not None else budget) if center is not None else None,
            "first_99": first_99, "observations": observations, "windows": windows,
            "early": early, "late": late, "record_events": record_events,
            "population_trace": population_trace,
            "diagnostics": {"infeasible_candidates": sum(not flag for flag in feasible_flags),
                            "duplicate_candidates": sum(child["duplicate"] for child in log["candidates"]),
                            "strict_record_improvements": len(record_events) - 1},
            "accounting": {"search_queries": budget, "known_score_checks": len(log["initial_masks"]),
                           "analysis_raw_score_checks": budget + len(log["initial_masks"]),
                           "diagnostic_new_fitness_evaluations": 0}}


def average_ranks(values):
    _ci_only()
    values = list(values)
    _require(bool(values) and all(type(x) in (int, float) and math.isfinite(x) for x in values), "invalid rank values")
    result = [0.0] * len(values)
    order = sorted(range(len(values)), key=values.__getitem__)
    first = 0
    while first < len(order):
        last = first + 1
        while last < len(order) and values[order[last]] == values[order[first]]:
            last += 1
        for index in order[first:last]:
            result[index] = (first + 1 + last) / 2
        first = last
    return result


def descriptive_spearman(x, y):
    _ci_only()
    _require(len(x) == len(y) and len(x) >= 2, "correlations require paired family values")
    a, b = average_ranks(x), average_ranks(y)
    meta = {"n_families": len(x), "p_value": None, "causal_claim": False, "role": "descriptive_only"}
    if len(set(a)) == 1 or len(set(b)) == 1:
        return {**meta, "status": "UNDEFINED", "rho": None, "reason": "constant_series"}
    da = [value - fmean(a) for value in a]
    db = [value - fmean(b) for value in b]
    rho = sum(i * j for i, j in zip(da, db, strict=True)) / math.sqrt(sum(i * i for i in da) * sum(j * j for j in db))
    return {**meta, "status": "DESCRIPTIVE", "rho": min(1.0, max(-1.0, rho)), "reason": None}


def _cases():
    path = Path(__file__).resolve().parents[3] / "studies/knapsack_parameters/evidence/run-37637475385/registry.json"
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == _REGISTRY_SHA, "historical registry checksum differs")
    registry = json.loads(raw)
    cases = {case["instance_id"]: case for case in registry["cases"]}
    expected = {f"{group}-s{index:03d}" for group in ("UC", "WC", "SC") for index in range(10)}
    _require(set(cases) == expected and len(registry["cases"]) == 30, "historical task registry is incomplete")
    order = registry.get("case_order")
    _require(type(order) is list and len(order) == 30 and set(order) == set(cases),
             "historical global case order is incomplete or duplicated")
    # Historical index is the sNNN index WITHIN each class (0..9), not
    # the global task/RNG index (0..29). Keep both meanings distinct.
    cases = {task: {**cases[task], "case_order_index": index} for index, task in enumerate(order)}
    admitted = {task for task, case in cases.items() if case["status"] in ("ADMITTED_STRICT_LOCAL", "ADMITTED_PLATEAU_LOCAL")}
    _require(len(admitted) == 14, "historical admitted center set differs")
    return cases, admitted


@lru_cache(maxsize=30)
def _registered_problem_bytes(task):
    """Immutable canonical problem, authenticated against retained input bytes."""
    cases, _ = _cases()
    _require(task in cases, "unregistered KPLIB task")
    root = Path(__file__).resolve().parents[3]
    manifest_raw = (root / "studies/knapsack_parameters/inputs/data_manifest.json").read_bytes()
    _require(hashlib.sha256(manifest_raw).hexdigest() == _DATA_MANIFEST_SHA, "input manifest checksum differs")
    source = cases[task]["payload"]["source_identity"]["source_path"]
    matches = [row for row in json.loads(manifest_raw)["source_files"] if row["source_path"] == source]
    _require(len(matches) == 1 and matches[0]["status"] == "PASS_SOURCE", "unverified source file")
    base = (root / "studies/knapsack_parameters/inputs/source").resolve()
    path = (base / source).resolve()
    _require(path.is_relative_to(base) and not path.is_symlink(), "unsafe source path")
    raw = path.read_bytes()
    _require(len(raw) == matches[0]["bytes"] and hashlib.sha256(raw).hexdigest() == matches[0]["sha256"],
             "KPLIB source byte identity differs")
    values = [int(item) for item in raw.decode("utf-8").split()]
    _require(len(values) == 202 and values[0] == 100 and values[1] > 0 and
             all(item > 0 for item in values[2:]), "malformed registered KPLIB input")
    return _canonical({"n": 100, "capacity": values[1], "profits": values[2::2], "weights": values[3::2]})


def _bind_scientific_input(envelope):
    """Read/replay a registered start, never run GA or an exact optimizer."""
    log = envelope["log"]
    cases, _ = _cases()
    task, start, seed = envelope["task"], envelope["start"], envelope["seed"]
    case = cases[task]
    _require(_canonical(log["problem"]) == _registered_problem_bytes(task),
             "scientific journal problem does not match frozen KPLIB bytes")
    _require(envelope["optimum"] == case["payload"]["exact"]["confirmed_optimum"], "wrong registered optimum")
    if seed == 86001:
        _require(task in ("UC-s000", "WC-s001", "SC-s005", "SC-s000"), "unregistered pilot task")
        preparation_seed = 86000
    else:
        _require(85001 <= seed <= 85030, "unregistered scientific seed")
        preparation_seed = 85000
        if start == "cloned":
            _require(case["status"] in ("ADMITTED_STRICT_LOCAL", "ADMITTED_PLATEAU_LOCAL"),
                     "nonadmitted main center")
    if start == "cloned":
        center = case["payload"]["certificate"]["center"]
        expected = [center["mask"]] * 30
        _require(envelope["center_profit"] == center["profit"], "registered center profit differs")
    else:
        # Reconstruct the recorded initialization RNG, not a new search or bank.
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
            [preparation_seed, seed, case["case_order_index"], 1, 0])))
        expected = ["0" * 100] + ["".join("1" if bit else "0" for bit in rng.random(100) < 0.5)
                                    for _ in range(29)]
    _require(log["initial_masks"] == expected, "initial population differs from registered bank or certified mask")


def expected_identities(scope):
    _ci_only()
    cases, admitted = _cases()
    _require(scope in ("main", "pilot"), "unknown analysis scope")
    if scope == "main":
        conditions = [(task, "bank") for task in sorted(cases)] + [(task, "cloned") for task in sorted(admitted)]
        seeds = range(85001, 85031)
    else:
        conditions = [(task, start) for task in ("UC-s000", "WC-s001", "SC-s005", "SC-s000") for start in ("cloned", "bank")]
        seeds = (86001,)
    return {(task, start, seed, method) for task, start in conditions for seed in seeds for method in METHODS}


def _mean_by_task(rows, getter):
    tasks = defaultdict(list)
    for row in rows:
        value = getter(row)
        if value is not None:
            tasks[row["task"]].append(value)
    return fmean(fmean(values) for values in tasks.values()) if tasks else None


def _family_cells(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["family"], row["start"], row["method"])].append(row)
    result = []
    for (family, start, method), entries in sorted(groups.items()):
        observations = [{"query": q,
                         "attainment_99": _mean_by_task(entries, lambda row, i=i: row["observations"][i]["attained_99"]),
                         "escape_frequency": _mean_by_task(entries, lambda row, i=i: row["observations"][i]["escaped"])}
                        for i, q in enumerate((0, 1000, 2500, 5000))]
        windows = []
        for i in range(10):
            window = {"first_query": i * 500 + 1, "last_query": (i + 1) * 500}
            for key in ("mean_p_m", "mean_p_c", "feasible_fraction", "mean_archive_size", "memory_switch_fraction", "maximum_parent_share", "unique_parents"):
                window[key] = _mean_by_task(entries, lambda row, key=key, i=i: row["windows"][i][key])
            windows.append(window)
        result.append({"family": family, "start": start, "method": method, "tasks": len({row["task"] for row in entries}),
                       "runs": len(entries), "mean_final_gap_percent": _mean_by_task(entries, lambda row: row["final_gap_percent"]),
                       "escape_frequency": _mean_by_task(entries, lambda row: row["escaped"]),
                       "mean_capped_escape_calls": _mean_by_task(entries, lambda row: row["capped_escape_calls"]),
                       "infeasible_fraction": _mean_by_task(entries, lambda row: row["diagnostics"]["infeasible_candidates"] / row["budget"]),
                       "duplicate_fraction": _mean_by_task(entries, lambda row: row["diagnostics"]["duplicate_candidates"] / row["budget"]),
                       "strict_record_fraction": _mean_by_task(entries, lambda row: row["diagnostics"]["strict_record_improvements"] / row["budget"]),
                       "observations": observations, "windows": windows})
    return result


def _undefined(contrast, estimate, reason):
    return {"contrast": contrast, "estimate": estimate, "lower": None, "upper": None,
            "status": "DESCRIPTIVE_ONLY", "reason": reason, "positive_effect_supported": False}


def family_bca(vectors, *, replicates=50000, seed=85031, confidence=0.9875):
    """Three active contrasts, common family draws; fourth remains blocked.

    Optional nondefault arguments exist only for CI fixtures.  Main-series
    analysis always calls the registered defaults after completeness checks.
    """
    _ci_only()
    values = np.asarray(vectors, dtype=float)
    _require(values.ndim == 2 and values.shape[1] == 3 and len(values) > 0 and np.isfinite(values).all(), "invalid family x 3 contrasts")
    _require(type(replicates) is int and replicates > 1 and 0 < confidence < 1, "invalid BCa settings")
    names = [f"{a}-minus-{b}" for a, b in CONTRASTS]
    n = len(values)
    result = {"method": "BCa", "unit": "whole family", "family_count": n,
              "resamples": replicates, "seed": seed, "confidence_each": confidence,
              "multiplicity": "four registered contrasts; lambda remains blocked, not replaced",
              "resample_index_sha256": None, "intervals": []}
    if n < 5:
        result["intervals"] = [_undefined(name, float(value), "fewer_than_five_families")
                               for name, value in zip(names, values.mean(axis=0), strict=True)]
    else:
        generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed])))
        indices = generator.integers(n, size=(replicates, n))
        result["resample_index_sha256"] = hashlib.sha256(indices.astype("<i8", copy=False).tobytes()).hexdigest()
        distribution = values[indices].mean(axis=1)
        jack = (values.sum(axis=0) - values) / (n - 1)
        normal, alpha = NormalDist(), 1 - confidence
        for col, name in enumerate(names):
            estimate = float(values[:, col].mean())
            samples = distribution[:, col]
            delta = jack[:, col].mean() - jack[:, col]
            denom = 6 * float(np.sum(delta ** 2)) ** 1.5
            fraction = (float(np.count_nonzero(samples < estimate)) + 0.5 * float(np.count_nonzero(samples == estimate))) / replicates
            if np.all(samples == samples[0]) or denom == 0 or not 0 < fraction < 1:
                result["intervals"].append(_undefined(name, estimate, "degenerate_or_undefined_BCa"))
                continue
            acceleration = float(np.sum(delta ** 3)) / denom
            z0 = normal.inv_cdf(fraction)
            tails = [normal.inv_cdf(alpha / 2), normal.inv_cdf(1 - alpha / 2)]
            adjusted = []
            for tail in tails:
                divisor = 1 - acceleration * (z0 + tail)
                adjusted.append(normal.cdf(z0 + (z0 + tail) / divisor) if divisor else math.nan)
            if not all(math.isfinite(p) and 0 < p < 1 for p in adjusted) or adjusted[0] >= adjusted[1]:
                result["intervals"].append(_undefined(name, estimate, "invalid_adjusted_quantiles"))
                continue
            low, high = map(float, np.quantile(samples, adjusted, method="linear"))
            if not math.isfinite(low + high) or low >= high:
                result["intervals"].append(_undefined(name, estimate, "degenerate_interval"))
                continue
            result["intervals"].append({"contrast": name, "estimate": estimate, "lower": low, "upper": high,
                                        "status": "INFERENTIAL_BCA", "reason": None,
                                        "positive_effect_supported": low > 0, "adjusted_quantiles": adjusted})
    result["intervals"].append({"contrast": "lambda_own-minus-lambda_fixed", "status": "BLOCKED_LAMBDA_REPLICATION",
                                "estimate": None, "lower": None, "upper": None, "positive_effect_supported": False})
    return result


def _correlations(rows):
    bank = [row for row in rows if row["start"] == "bank"]
    family_groups = defaultdict(list)
    for row in bank:
        family_groups[(row["family"], row["method"])].append(row)
    families = sorted({row["family"] for row in bank})
    _require(len(families) == 10, "main correlations need all ten families")
    means = {}
    for key, entries in family_groups.items():
        means[key] = {"p_m": _mean_by_task(entries, lambda row: row["early"]["mean_p_m"]),
                      "p_c": _mean_by_task(entries, lambda row: row["early"]["mean_p_c"]),
                      "F1": _mean_by_task(entries, lambda row: row["early"]["feasible_fraction"]),
                      "C1": _mean_by_task(entries, lambda row: row["early"]["maximum_parent_share"]),
                      "G2": _mean_by_task(entries, lambda row: row["late"]["gain_over_optimum"]),
                      "F2": _mean_by_task(entries, lambda row: row["late"]["feasible_fraction"])}
    correlations = []
    for method, parameter in (("adaptive_mutation", "p_m"), ("adaptive_crossover", "p_c")):
        for outcome in ("G2", "F2"):
            x = [means[(family, method)][parameter] for family in families]
            y = [means[(family, method)][outcome] for family in families]
            correlations.append({"question": f"{method}:{parameter}_early_vs_{outcome}", "families": families,
                                 "x": x, "y": y, **descriptive_spearman(x, y)})
    delta_g = [means[(f, "balanced_gap")]["G2"] - means[(f, "unbalanced_gap")]["G2"] for f in families]
    for signal in ("C1", "F1"):
        x = [(means[(f, "unbalanced_gap")][signal] - means[(f, "balanced_gap")][signal])
             if signal == "C1" else (means[(f, "balanced_gap")][signal] - means[(f, "unbalanced_gap")][signal])
             for f in families]
        correlations.append({"question": f"archive_delta_{signal}_vs_delta_G2", "families": families,
                             "x": x, "y": delta_g, **descriptive_spearman(x, delta_g)})
    correlations.append({"question": "lambda_parameter_vs_later_improvement", "status": "BLOCKED_LAMBDA_REPLICATION",
                         "rho": None, "p_value": None, "causal_claim": False})
    return correlations


def _validate_compact(row):
    """Check compact endpoints and exact event-derived claims before pooling."""
    _require(type(row) is dict and set(row) == _ROW_FIELDS and
             row["schema"] == "ga-adaptation-compact-run-v1" and row["verification_status"] == "VERIFIED",
             "compact schema or verification status differs")
    for key in ("journal_sha256", "initial_population_sha256", "initial_rng_sha256", "problem_sha256"):
        _require(type(row[key]) is str and re.fullmatch(r"[0-9a-f]{64}", row[key]), "invalid checksum " + key)
    optimum, center, budget = row["optimum"], row["center_profit"], row["budget"]
    _require(type(optimum) is int and optimum > 0 and type(budget) is int and budget == 5000, "invalid compact optimum or budget")
    _require(row["input_binding"] == "KPLIB_BYTES_AND_REGISTERED_INITIAL_STATE", "compact input is not scientifically bound")
    _require((row["start"] == "bank" and center is None) or
             (row["start"] == "cloned" and type(center) is int and 0 <= center <= optimum), "invalid compact center")
    _require(type(row["record_events"]) is list and bool(row["record_events"]), "missing record events")
    previous_query, previous_profit = -1, -1
    for index, event in enumerate(row["record_events"]):
        _require(type(event) is dict and set(event) == {"query", "profit"}, "record event fields differ")
        q, profit = event["query"], event["profit"]
        _require(type(q) is int and previous_query < q <= budget and type(profit) is int and previous_profit < profit <= optimum,
                 "record events are noninteger, nonmonotone or above OPT")
        _require(index != 0 or q == 0, "record must begin at query zero")
        previous_query, previous_profit = q, profit
    _require(type(row["initial_best_profit"]) is int and type(row["final_best_profit"]) is int and
             row["initial_best_profit"] == row["record_events"][0]["profit"] and
             row["final_best_profit"] == previous_profit, "record endpoint differs")
    _require(row["final_gap_percent"] == 100 * (optimum - previous_profit) / optimum, "compact final gap differs")
    expected_99 = next((event["query"] for event in row["record_events"] if 100 * event["profit"] >= 99 * optimum), None)
    _require(row["first_99"] == expected_99 and type(row["first_99"]) is type(expected_99), "99% endpoint differs")
    expected_escape = (next((event["query"] for event in row["record_events"] if event["profit"] > center), None)
                       if center is not None else None)
    _require(row["first_escape"] == expected_escape and type(row["first_escape"]) is type(expected_escape), "escape endpoint differs")
    expected_flag = expected_escape is not None if center is not None else None
    expected_capped = (expected_escape if expected_escape is not None else budget) if center is not None else None
    _require(type(row["escaped"]) is type(expected_flag) and row["escaped"] == expected_flag, "escape flag differs")
    _require(type(row["capped_escape_calls"]) is type(expected_capped) and
             row["capped_escape_calls"] == expected_capped, "capped escape endpoint differs")
    _require(type(row["observations"]) is list and len(row["observations"]) == 4, "observation count differs")
    for q, observation in zip((0, 1000, 2500, 5000), row["observations"], strict=True):
        value = next(event["profit"] for event in reversed(row["record_events"]) if event["query"] <= q)
        expected = {"query": q, "best_profit": value, "gap_percent": 100 * (optimum - value) / optimum,
                    "attained_99": 100 * value >= 99 * optimum, "escaped": value > center if center is not None else None}
        _require(_canonical(observation) == _canonical(expected), "compact observation differs")
    _require(type(row["windows"]) is list and len(row["windows"]) == 10, "window count differs")
    for i, window in enumerate(row["windows"]):
        _require(window["first_query"] == i * 500 + 1 and window["last_query"] == (i + 1) * 500 and
                 window["queries"] == 500 and window["parent_uses"] == 1000, "query-weighted window boundaries differ")
        for field in ("mean_p_m", "mean_p_c", "feasible_fraction", "maximum_parent_share"):
            _require(type(window[field]) in (int, float) and 0 <= window[field] <= 1, "invalid window fraction")
        for field in ("mean_archive_size", "memory_switch_fraction"):
            _require(window[field] is None or (type(window[field]) in (int, float) and window[field] >= 0), "invalid optional window value")
        _require(window["memory_switch_fraction"] is None or window["memory_switch_fraction"] <= 1,
                 "memory switch frequency exceeds one")
    _require(type(row["diagnostics"]) is dict and set(row["diagnostics"]) ==
             {"infeasible_candidates", "duplicate_candidates", "strict_record_improvements"}, "diagnostic fields differ")
    _require(all(type(value) is int and 0 <= value <= budget for value in row["diagnostics"].values()), "diagnostic count invalid")
    _require(row["diagnostics"]["strict_record_improvements"] == len(row["record_events"]) - 1, "strict improvement count differs")
    _canonical(row)


def _summarize_rows(rows, *, scope="main", raw_verified=False):
    """Internal aggregation. Tests may supply labelled constructed fixtures."""
    _ci_only()
    _require(type(rows) is list, "compact rows must be a list")
    expected = expected_identities(scope)
    base = {"schema": "ga-adaptation-series-summary-v1", "scope": scope, "expected_runs": len(expected),
            "received_runs": len(rows), "deferred": {method: "BLOCKED_LAMBDA_REPLICATION" for method in DEFERRED},
            "family_cells": [], "statistics": None, "correlations": [], "example_rows": []}
    if not rows:
        return {**base, "status": "NOT_RUN", "active_profiles": {method: "NOT_RUN" for method in METHODS}}
    cases, _ = _cases()
    found = set()
    shas = set()
    starts = {}
    for row in rows:
        _validate_compact(row)
        identity = tuple(row.get(key) for key in _IDENTITY)
        _require(identity in expected, "unregistered run identity")
        _require(identity not in found, "duplicate run identity")
        found.add(identity)
        case = cases[row["task"]]
        _require(row["family"] == case["family"] and row["budget"] == 5000, "family or budget differs")
        _require(row["problem_sha256"] == hashlib.sha256(_registered_problem_bytes(row["task"])).hexdigest(),
                 "compact problem identity differs from frozen KPLIB")
        _require(row["optimum"] == case["payload"]["exact"]["confirmed_optimum"], "external optimum differs from registry")
        if row["start"] == "cloned":
            _require(row["center_profit"] == case["payload"]["certificate"]["center"]["profit"], "center differs from registry")
        else:
            _require(row["center_profit"] is None, "bank row has a center")
        _require(type(row["implementation_sha"]) is str and re.fullmatch(r"[0-9a-f]{40}", row["implementation_sha"]), "invalid row SHA")
        shas.add(row["implementation_sha"])
        condition = (row["task"], row["start"], row["seed"])
        paired_identity = (row["initial_population_sha256"], row["initial_rng_sha256"])
        _require(condition not in starts or starts[condition] == paired_identity,
                 "paired initial population or RNG differs across methods")
        starts[condition] = paired_identity
        _canonical(row)
    _require(len(shas) == 1, "mixed implementation SHAs")
    missing = expected - found
    if missing:
        return {**base, "status": "INCOMPLETE", "missing_runs": len(missing),
                "missing_examples": [list(identity) for identity in sorted(missing)[:20]],
                "implementation_sha": next(iter(shas))}
    if not raw_verified:
        return {**base, "status": "COMPLETE_COMPACT_REQUIRES_RAW_VERIFICATION",
                "implementation_sha": next(iter(shas)), "statistics": None,
                "reason": "Compact VERIFIED strings/checksums alone do not authenticate source journals"}
    cells = _family_cells(rows)
    summaries = []
    for start in ("bank", "cloned"):
        for method in METHODS:
            selected = [cell for cell in cells if cell["start"] == start and cell["method"] == method]
            actual = [row for row in rows if row["start"] == start and row["method"] == method]
            summaries.append({"start": start, "method": method, "families": len(selected), "runs": len(actual),
                              "absolute_escapes": sum(row["escaped"] for row in actual) if start == "cloned" else None,
                              "absolute_infeasible_candidates": sum(row["diagnostics"]["infeasible_candidates"] for row in actual),
                              "absolute_duplicate_candidates": sum(row["diagnostics"]["duplicate_candidates"] for row in actual),
                              "absolute_strict_record_improvements": sum(row["diagnostics"]["strict_record_improvements"] for row in actual),
                              "family_weighted_infeasible_fraction": fmean(cell["infeasible_fraction"] for cell in selected),
                              "family_weighted_duplicate_fraction": fmean(cell["duplicate_fraction"] for cell in selected),
                              "family_weighted_strict_record_fraction": fmean(cell["strict_record_fraction"] for cell in selected),
                              "mean_final_gap_percent": fmean(cell["mean_final_gap_percent"] for cell in selected),
                              "escape_frequency": fmean(cell["escape_frequency"] for cell in selected) if start == "cloned" else None,
                              "observations": [{"query": q,
                                                "attainment_99": fmean(cell["observations"][i]["attainment_99"] for cell in selected),
                                                "escape_frequency": fmean(cell["observations"][i]["escape_frequency"] for cell in selected) if start == "cloned" else None}
                                               for i, q in enumerate((0, 1000, 2500, 5000))]})
    statistics = None
    correlations = []
    if scope == "main":
        rates = {(cell["family"], cell["method"]): cell["escape_frequency"] for cell in cells if cell["start"] == "cloned"}
        families = sorted({family for family, _ in rates})
        vectors = [[rates[(family, a)] - rates[(family, b)] for a, b in CONTRASTS] for family in families]
        statistics = family_bca(vectors)
        statistics["families"] = families
        statistics["family_contrasts"] = vectors
        correlations = _correlations(rows)
    return {**base, "status": "COMPLETE_VERIFIED_MAIN" if scope == "main" else "COMPLETE_VERIFIED_PILOT",
            "implementation_sha": next(iter(shas)), "family_cells": cells, "method_summaries": summaries,
            "statistics": statistics, "correlations": correlations,
            "example_rows": [deepcopy(row) for row in rows if row["task"] == "UC-s000" and row["seed"] == 85001],
            "interpretation": "family-weighted; pilot descriptive only; correlations are not causal; lambda blocked"}


def summarize_series(rows, *, scope="main"):
    """Structural compact audit only; never promote supplied receipts to evidence."""
    return _summarize_rows(rows, scope=scope, raw_verified=False)


def summarize_verified_envelopes(envelopes, *, scope="main"):
    """Preferred public entry: independently replay all raw logs before pooling.

    Input bytes, recorded initialization and all search operators are replayed;
    compact-only receipts cannot enable scientific statistics or rendering.
    The execution driver must still bind the artifact and implementation SHA.
    """
    _ci_only()
    _require(isinstance(envelopes, Iterable) and not isinstance(envelopes, (dict, str, bytes)),
             "envelopes must be an iterable of raw run records")
    maximum = len(expected_identities(scope))
    rows = []
    for envelope in envelopes:
        _require(len(rows) < maximum, "too many source journals for the registered series")
        rows.append(extract_run(envelope))
    summary = _summarize_rows(rows, scope=scope, raw_verified=True)
    summary["raw_log_verification"] = "ALL_SUPPLIED_LOGS_INDEPENDENTLY_REPLAYED"
    summary["raw_logs_replayed"] = len(rows)
    return summary

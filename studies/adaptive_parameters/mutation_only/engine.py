"""Own generation-level mutation heuristic with fixed population and crossover.

This is not a published controller or a numerical article replication.  Search
is CI-only; neither exact optima nor locality certificates are accepted here.
No frozen historical implementation is imported or modified.
"""

from __future__ import annotations

from copy import deepcopy
import math
import os

import numpy as np


SCHEMA = "ga-adaptive-mutation-only-log-v1"
MU = 30
PC = 0.9
CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
METHODS = ("fixed", "adaptive_mutation")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, name, minimum=0):
    _require(type(value) is int and value >= minimum,
             f"{name} must be an integer >= {minimum}")


def _problem(problem):
    _require(isinstance(problem, dict) and
             set(problem) == {"n", "weights", "profits", "capacity"},
             "Problem accepts only n, weights, profits and capacity; oracle metadata is forbidden")
    n = problem["n"]
    _integer(n, "n", 2)
    _integer(problem["capacity"], "capacity")
    for name in ("weights", "profits"):
        values = problem[name]
        _require(isinstance(values, (list, tuple)) and len(values) == n,
                 f"{name} must contain exactly n positive integers")
        for value in values:
            _integer(value, name, 1)


def _mask(mask, n):
    _require(isinstance(mask, str) and len(mask) == n and not set(mask) - {"0", "1"},
             "Mask must be an n-bit binary string")


def _evaluate(problem, mask):
    # Python integer sums avoid overflow and retain original item order.
    weight = sum(w for w, bit in zip(problem["weights"], mask) if bit == "1")
    profit = sum(v for v, bit in zip(problem["profits"], mask) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def evaluate(problem, mask):
    """Exact evaluation, without repair or caching; drivers authorize execution."""
    _problem(problem)
    _mask(mask, problem["n"])
    return _evaluate(problem, mask)


def _key(score, capacity):
    return (1, score["profit"]) if score["feasible"] else (0, capacity - score["weight"])


def _pick(indices, rng):
    # Duplicate tournament entries remain separate equally likely occurrences.
    return indices[0] if len(indices) == 1 else indices[int(rng.integers(len(indices)))]


def _states(rngs):
    return {name: deepcopy(rngs[name].bit_generator.state) for name in CHANNELS}


def make_rngs(seed, task_index, start_index):
    """Six separate PCG64 streams; method name is deliberately absent."""
    for name, value in (("seed", seed), ("task_index", task_index), ("start_index", start_index)):
        _integer(value, name)
    return {name: np.random.Generator(np.random.PCG64(
        np.random.SeedSequence([seed, task_index, start_index, channel])))
        for channel, name in enumerate(CHANNELS)}


def update_mutation(n, p, s, success, method="adaptive_mutation"):
    """Update only after a completed generation; ties are not strict successes."""
    _integer(n, "n", 2)
    _integer(s, "stagnation")
    lower, upper = 1 / n, min(8 / n, 0.5)
    _require(s < 5 and type(success) is bool and method in METHODS,
             "Invalid controller state, success flag or method")
    _require(isinstance(p, (int, float)) and not isinstance(p, bool) and
             math.isfinite(p) and lower <= p <= upper, "Mutation probability outside controller bounds")
    if method == "fixed":
        return lower, 0, "FIXED"
    if success:
        return max(lower, p / 2), 0, "SUCCESS_HALVE"
    if s + 1 == 5:
        return min(upper, p * 2), 0, "STAGNATION_DOUBLE"
    return float(p), s + 1, "NO_CHANGE"


def run_search(problem, initial_masks, initial_scores, method, rngs, budget=5000):
    """Run exactly budget new evaluations after the known initial population.

    Initial score validation is reported separately from physical search calls.
    A completed generation replaces all non-elite slots, including worse or
    infeasible children.  An unfinished terminal prefix updates only the record.
    """
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "Search execution is CI-only")
    _problem(problem)
    _integer(budget, "budget", 1)
    _require(method in METHODS, "Unknown mutation-only method")
    _require(isinstance(initial_masks, list) and isinstance(initial_scores, list) and
             len(initial_masks) == len(initial_scores) == MU, "Exactly 30 known initial masks and scores required")
    _require(isinstance(rngs, dict) and set(rngs) == set(CHANNELS), "Exactly six named RNG channels required")
    _require(all(isinstance(rngs[name], np.random.Generator) and
                 isinstance(rngs[name].bit_generator, np.random.PCG64) for name in CHANNELS),
             "All channels must be PCG64 generators")
    _require(len({id(rngs[name]) for name in CHANNELS}) == len(CHANNELS) and
             len({id(rngs[name].bit_generator) for name in CHANNELS}) == len(CHANNELS),
             "RNG channels may not alias")
    n, capacity = problem["n"], problem["capacity"]
    masks, scores = list(initial_masks), []
    for mask, known in zip(masks, initial_scores):
        _mask(mask, n)
        _require(isinstance(known, dict) and set(known) == {"weight", "profit", "feasible"},
                 "Known scores must contain only weight, profit and feasible")
        _require(type(known["weight"]) is int and type(known["profit"]) is int and
                 type(known["feasible"]) is bool and known["weight"] >= 0 and known["profit"] >= 0,
                 "Known scores must use nonnegative exact integers and a Boolean feasibility flag")
        actual = _evaluate(problem, mask)
        _require(actual == known, "Known initial score disagrees with the exact input mask")
        scores.append(actual)
    canonical_problem = {"n": n, "weights": list(problem["weights"]),
                         "profits": list(problem["profits"]), "capacity": capacity}
    rng_initial = _states(rngs)
    log = {"schema": SCHEMA, "method": method, "problem": canonical_problem,
           "initial_masks": list(masks), "initial_scores": deepcopy(scores),
           "rng_initial": rng_initial, "budget": budget,
           "candidates": [], "generations": [], "summary": None, "rng_final": None}
    population = list(range(MU))
    seen = set(masks)
    best_mask = best_profit = best_call = None
    for mask, score in zip(masks, scores):
        if score["feasible"] and (best_profit is None or score["profit"] > best_profit):
            best_mask, best_profit, best_call = mask, score["profit"], 0
    probability, stagnation = 1 / n, 0
    calls = full_generations = partial_children = duplicate_calls = infeasible_calls = 0
    while calls < budget:
        generation = len(log["generations"]) + 1
        before = list(population)
        states_before = _states(rngs)
        record_before = best_profit
        p_before, s_before = probability, stagnation
        keys = [_key(scores[reference], capacity) for reference in before]
        elite_key = max(keys)
        elite_index = _pick([i for i, key in enumerate(keys) if key == elite_key], rngs["ties"])
        elite_reference = before[elite_index]
        start_call = calls + 1
        child_references = []
        for _ in range(min(MU - 1, budget - calls)):
            tournaments, parents = [], []
            for _parent in range(2):
                pair = [int(rngs["selection"].integers(MU)), int(rngs["selection"].integers(MU))]
                tournaments.append(pair)
                a, b = pair
                winner = (_pick(pair, rngs["ties"]) if keys[a] == keys[b]
                          else a if keys[a] > keys[b] else b)
                parents.append(winner)
            a, b = masks[before[parents[0]]], masks[before[parents[1]]]
            has_crossover = bool(rngs["branch"].random() < PC)
            if has_crossover:
                choices = rngs["crossover"].random(n) < 0.5
                pre = "".join(a[i] if choices[i] else b[i] for i in range(n))
            else:
                pre = a
            mutation_bits = [i for i, changed in enumerate(rngs["mutation"].random(n) < p_before) if changed]
            bits = list(pre)
            for index in mutation_bits:
                bits[index] = "0" if bits[index] == "1" else "1"
            mask = "".join(bits)
            score = _evaluate(problem, mask)
            calls += 1
            duplicate = mask in seen
            duplicate_calls += int(duplicate)
            infeasible_calls += int(not score["feasible"])
            seen.add(mask)
            if score["feasible"] and (best_profit is None or score["profit"] > best_profit):
                best_mask, best_profit, best_call = mask, score["profit"], calls
            reference = len(masks)
            masks.append(mask)
            scores.append(score)
            child_references.append(reference)
            log["candidates"].append({
                "call": calls, "generation": generation, "tournaments": tournaments,
                "parent_indices": parents, "crossover": has_crossover, "pre_mask": pre,
                "mutation_bits": mutation_bits, "mask": mask, **score,
                "duplicate": duplicate, "record_profit": best_profit, "record_call": best_call})
        complete = len(child_references) == MU - 1
        if complete:
            population = [elite_reference] + child_references
            full_generations += 1
            success = best_profit is not None and (record_before is None or best_profit > record_before)
            probability, stagnation, event = update_mutation(n, p_before, s_before, success, method)
        else:
            partial_children = len(child_references)
            probability, stagnation, event = p_before, s_before, "PARTIAL_NO_UPDATE"
        log["generations"].append({
            "generation": generation, "start_call": start_call, "end_call": calls,
            "complete": complete, "population_before": before, "elite_index": elite_index,
            "p_m": p_before, "stagnation_before": s_before, "record_before": record_before,
            "record_after": best_profit, "p_m_next": probability, "stagnation_after": stagnation,
            "controller_event": event, "population_after": list(population),
            "rng_before": states_before, "rng_after": _states(rngs)})
    log["summary"] = {
        "new_calls": calls, "physical_evaluations": calls, "known_score_validation_evaluations": MU,
        "duplicate_calls": duplicate_calls, "infeasible_calls": infeasible_calls,
        "full_generations": full_generations, "partial_children": partial_children,
        "best_mask": best_mask, "best_profit": best_profit, "best_call": best_call,
        "final_population": list(population), "final_mutation_probability": probability}
    log["rng_final"] = _states(rngs)
    return log

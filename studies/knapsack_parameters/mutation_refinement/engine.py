"""Registered fixed, legacy and gentle mutation rules of one generational GA.

The construction is copied from the unchanged parameter_dynamics engine, with
only the registered mutation configuration substituted. Novelty is logged for
historical replay; it does not control any parameter. Search receives no oracle
metadata and does not import any historical implementation. This prospective
module does not grant execution authority or a scientific resource budget.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import math
import os
from time import perf_counter_ns

import numpy as np


SCHEMA = "ga-knapsack-mutation-refinement-log-v1"
INITIAL_MU = 30
NEW_EVALUATION_BUDGET = 5000
FAILED_QUERY_THRESHOLD = 145
CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
METHODS = ("fixed_0.005", "fixed_0.01", "fixed_0.02", "legacy", "gentle")
FIXED_PROBABILITIES = {"fixed_0.005": 0.005, "fixed_0.01": 0.01, "fixed_0.02": 0.02}
PARAMETER_NAMES = ("p_m", "p_c", "target_mu", "tournament_size", "elite_count")
STATIC_BOUNDS = {"p_c": (0.1, 0.9), "target_mu": (10, 100),
                 "tournament_size": (2, 5), "elite_count": (1, 5)}
TIMING_COMPONENTS = ("validation", "selection", "variation", "evaluation", "signal", "controller", "log_assembly")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, name, minimum=0):
    _require(type(value) is int and value >= minimum, f"{name} must be an integer >= {minimum}")


def _ci():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "Search execution is GitHub-Actions only")


def _method(method):
    _require(type(method) is str and method in METHODS, "Unknown registered mutation method")


def mutation_bounds(method):
    """Return registered bounds; a fixed method has a singleton interval."""
    _method(method)
    if method in FIXED_PROBABILITIES:
        probability = FIXED_PROBABILITIES[method]
        return probability, probability
    return (0.01, 0.08) if method == "legacy" else (0.005, 0.02)


def default_parameters(method="fixed_0.01"):
    _method(method)
    return {"p_m": FIXED_PROBABILITIES.get(method, 0.01), "p_c": 0.9,
            "target_mu": INITIAL_MU, "tournament_size": 2, "elite_count": 1}


def _parameters(parameters, method):
    _method(method)
    _require(type(parameters) is dict and set(parameters) == set(PARAMETER_NAMES), "Invalid parameter vector")
    initial = default_parameters(method)
    lower, upper = mutation_bounds(method)
    probability = parameters["p_m"]
    _require(type(probability) in (int, float) and math.isfinite(probability),
             "Mutation probability must be a finite number")
    _require(lower <= probability <= upper, "Mutation probability outside registered bounds")
    for name in PARAMETER_NAMES[1:]:
        value = parameters[name]
        if name == "p_c":
            _require(type(value) in (int, float) and math.isfinite(value), "Probability must be finite")
        else:
            _integer(value, name, 1)
        _require(value == initial[name], "Fixed construction changed: " + name)


def _problem(problem):
    _require(isinstance(problem, dict) and set(problem) == {"n", "weights", "profits", "capacity"},
             "Only n, weights, profits and capacity are accepted; oracle metadata is forbidden")
    _integer(problem["n"], "n", 2)
    _integer(problem["capacity"], "capacity")
    for name in ("weights", "profits"):
        _require(isinstance(problem[name], (list, tuple)) and len(problem[name]) == problem["n"],
                 "Wrong problem-vector length")
        for value in problem[name]:
            _integer(value, name, 1)


def _mask(mask, n):
    _require(isinstance(mask, str) and len(mask) == n and not set(mask) - {"0", "1"}, "Invalid binary mask")


def _evaluate(problem, mask):
    weight = sum(w for w, bit in zip(problem["weights"], mask) if bit == "1")
    profit = sum(v for v, bit in zip(problem["profits"], mask) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def evaluate(problem, mask):
    """Uncached CI-only evaluation; separate execution authority is required."""
    _ci()
    _problem(problem)
    _mask(mask, problem["n"])
    return _evaluate(problem, mask)


def _key(score, capacity):
    return (1, score["profit"]) if score["feasible"] else (0, capacity - score["weight"])


def _pick(occurrences, generator):
    # Repeated tournament entries remain distinct winning occurrences. A sole
    # winning occurrence consumes no tie random number, as in historical code.
    return occurrences[0] if len(occurrences) == 1 else occurrences[int(generator.integers(len(occurrences)))]


def _states(rngs):
    return {name: deepcopy(rngs[name].bit_generator.state) for name in CHANNELS}


def make_rngs(seed, task_index, start_index):
    """Six isolated historical streams; method is absent from their identity."""
    for name, value in (("seed", seed), ("task_index", task_index), ("start_index", start_index)):
        _integer(value, name)
    return {name: np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [seed, task_index, start_index, channel]))) for channel, name in enumerate(CHANNELS)}


def novelty_probability(distance):
    """Historical observational metric, never an input to mutation decisions."""
    _integer(distance, "parent distance")
    return Fraction(0) if distance == 0 else Fraction(1) - Fraction(1, 1 << (distance - 1))


def novelty_statistics(distances):
    _require(isinstance(distances, list) and bool(distances), "Parent distances are required")
    total = sum((novelty_probability(distance) for distance in distances), Fraction(0))
    mean = total / len(distances)
    return {"novelty_sum_numerator": total.numerator, "novelty_sum_denominator": total.denominator,
            "novelty_mean_numerator": mean.numerator, "novelty_mean_denominator": mean.denominator}


def update_parameters(parameters, failed_queries, success, new_calls, method):
    """Update after a complete 29-child generation without consuming RNG.

    A strict record success preempts the threshold and resets the counter.
    Boundary events remain events even when clipping leaves p unchanged.
    """
    _parameters(parameters, method)
    _integer(failed_queries, "failed_queries")
    _require(failed_queries < FAILED_QUERY_THRESHOLD and type(success) is bool, "Invalid controller state")
    _integer(new_calls, "new_calls", 1)
    _require(new_calls == 29, "Controller update requires all 29 children of a complete generation")
    accumulated = 0 if success else failed_queries + new_calls
    event = "SUCCESS" if success else "STAGNATION" if accumulated >= FAILED_QUERY_THRESHOLD else "NO_CHANGE"
    after_count = accumulated if event == "NO_CHANGE" else 0
    overshoot = accumulated - FAILED_QUERY_THRESHOLD if event == "STAGNATION" else 0
    after = dict(parameters)
    lower, upper = mutation_bounds(method)
    enabled = method in ("legacy", "gentle")
    if enabled:
        factor = 2 if method == "legacy" else 1.25
        if event == "SUCCESS":
            after["p_m"] = max(lower, parameters["p_m"] / factor)
        elif event == "STAGNATION":
            after["p_m"] = min(upper, parameters["p_m"] * factor)
    _parameters(after, method)
    bounds = {"p_m": (lower, upper), **STATIC_BOUNDS}
    events = []
    for name in PARAMETER_NAMES:
        previous, following = parameters[name], after[name]
        events.append({"field": name, "enabled": enabled and name == "p_m", "before": previous,
                       "after": following, "direction": "increase" if following > previous else
                       "decrease" if following < previous else "unchanged",
                       "at_boundary": following in bounds[name]})
    return {"parameters": after, "event": event, "failed_queries_accumulated": accumulated,
            "failed_queries_after": after_count, "stagnation_overshoot": overshoot, "parameter_events": events}


def run_search(problem, initial_masks, initial_scores, method, rngs, budget=5000):
    """Evaluate exactly budget new candidates in CI; default is the frozen 5000.

    Smaller budgets support instructional CI fixtures. Initial score validation
    is accounted separately. A terminal incomplete generation updates only the
    all-evaluated feasible record, never the population or controller.
    """
    run_started = perf_counter_ns()
    timed = {name: 0 for name in TIMING_COMPONENTS}
    started = perf_counter_ns()
    _ci()
    _problem(problem)
    _method(method)
    _integer(budget, "budget", 1)
    _require(budget <= NEW_EVALUATION_BUDGET, "Budget exceeds the registered 5000 new evaluations")
    _require(isinstance(initial_masks, list) and isinstance(initial_scores, list) and
             len(initial_masks) == len(initial_scores) == INITIAL_MU, "Exactly 30 known initial positions required")
    _require(isinstance(rngs, dict) and set(rngs) == set(CHANNELS), "Exactly six RNG channels required")
    _require(all(isinstance(rngs[name], np.random.Generator) and
                 isinstance(rngs[name].bit_generator, np.random.PCG64) for name in CHANNELS),
             "All channels must be PCG64 generators")
    _require(len({id(rngs[name]) for name in CHANNELS}) == 6 and
             len({id(rngs[name].bit_generator) for name in CHANNELS}) == 6, "RNG channels may not alias")
    n, capacity = problem["n"], problem["capacity"]
    masks, scores = list(initial_masks), []
    for mask, known in zip(initial_masks, initial_scores):
        _mask(mask, n)
        _require(type(known) is dict and set(known) == {"weight", "profit", "feasible"} and
                 type(known["weight"]) is int and type(known["profit"]) is int and
                 type(known["feasible"]) is bool and known["weight"] >= 0 and known["profit"] >= 0,
                 "Invalid known exact score")
        actual = _evaluate(problem, mask)
        _require(actual == known, "Known initial score differs from exact data")
        scores.append(actual)
    canonical_problem = {"n": n, "weights": list(problem["weights"]),
                         "profits": list(problem["profits"]), "capacity": capacity}
    initial_states = _states(rngs)
    parameters, failed_queries = default_parameters(method), 0
    timed["validation"] += perf_counter_ns() - started
    started = perf_counter_ns()
    log = {"schema": SCHEMA, "method": method, "problem": canonical_problem,
           "initial_masks": list(masks), "initial_scores": deepcopy(scores), "rng_initial": initial_states,
           "budget": budget, "candidates": [], "generations": [], "summary": None, "rng_final": None}
    population, seen = list(range(INITIAL_MU)), set(masks)
    best_mask = best_profit = best_call = None
    for mask, score in zip(masks, scores):
        if score["feasible"] and (best_profit is None or score["profit"] > best_profit):
            best_mask, best_profit, best_call = mask, score["profit"], 0
    calls = full_generations = partial_children = duplicate_calls = infeasible_calls = 0
    timed["log_assembly"] += perf_counter_ns() - started
    while calls < budget:
        started = perf_counter_ns()
        generation = len(log["generations"]) + 1
        before, states_before = list(population), _states(rngs)
        actual_mu = len(before)
        params_before, count_before = dict(parameters), failed_queries
        record_before = best_profit
        keys = [_key(scores[reference], capacity) for reference in before]
        start_call = calls + 1
        requested = params_before["target_mu"] - params_before["elite_count"]
        child_references, parent_distances = [], []
        timed["log_assembly"] += perf_counter_ns() - started
        started = perf_counter_ns()
        available = list(range(actual_mu))
        elite_indices, elite_references = [], []
        for _ in range(params_before["elite_count"]):
            best_key = max(keys[index] for index in available)
            elite_index = _pick([index for index in available if keys[index] == best_key], rngs["ties"])
            elite_indices.append(elite_index)
            elite_references.append(before[elite_index])
            available.remove(elite_index)
        timed["selection"] += perf_counter_ns() - started
        for _ in range(min(requested, budget - calls)):
            started = perf_counter_ns()
            tournaments, parents = [], []
            for _parent in range(2):
                entries = [int(rngs["selection"].integers(actual_mu)) for _ in range(params_before["tournament_size"])]
                tournaments.append(entries)
                top = max(keys[index] for index in entries)
                parents.append(_pick([index for index in entries if keys[index] == top], rngs["ties"]))
            a, b = masks[before[parents[0]]], masks[before[parents[1]]]
            timed["selection"] += perf_counter_ns() - started
            started = perf_counter_ns()
            distance = sum(first != second for first, second in zip(a, b))
            parent_distances.append(distance)
            timed["signal"] += perf_counter_ns() - started
            started = perf_counter_ns()
            has_crossover = bool(rngs["branch"].random() < params_before["p_c"])
            if has_crossover:
                choices = rngs["crossover"].random(n) < 0.5
                pre = "".join(a[i] if choices[i] else b[i] for i in range(n))
            else:
                pre = a
            mutation_bits = [i for i, changed in enumerate(rngs["mutation"].random(n) < params_before["p_m"]) if changed]
            bits = list(pre)
            for index in mutation_bits:
                bits[index] = "0" if bits[index] == "1" else "1"
            mask = "".join(bits)
            timed["variation"] += perf_counter_ns() - started
            started = perf_counter_ns()
            score = _evaluate(problem, mask)
            timed["evaluation"] += perf_counter_ns() - started
            started = perf_counter_ns()
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
                "parent_indices": parents, "parent_distance": distance, "crossover": has_crossover,
                "pre_mask": pre, "mutation_bits": mutation_bits, "mask": mask, **score,
                "duplicate": duplicate, "record_profit": best_profit, "record_call": best_call})
            timed["log_assembly"] += perf_counter_ns() - started
        started = perf_counter_ns()
        novelty = novelty_statistics(parent_distances)
        timed["signal"] += perf_counter_ns() - started
        complete = len(child_references) == requested
        if complete:
            started = perf_counter_ns()
            population = elite_references + child_references
            full_generations += 1
            success = best_profit is not None and (record_before is None or best_profit > record_before)
            timed["log_assembly"] += perf_counter_ns() - started
            started = perf_counter_ns()
            result = update_parameters(params_before, count_before, success, requested, method)
            parameters, failed_queries = result["parameters"], result["failed_queries_after"]
            timed["controller"] += perf_counter_ns() - started
        else:
            partial_children = len(child_references)
            success = None
            result = {"event": "PARTIAL_NO_UPDATE", "failed_queries_accumulated": count_before,
                      "failed_queries_after": count_before, "stagnation_overshoot": None, "parameter_events": []}
            parameters, failed_queries = dict(params_before), count_before
        started = perf_counter_ns()
        log["generations"].append({
            "generation": generation, "start_call": start_call, "end_call": calls, "complete": complete,
            "population_before": before, "actual_parent_mu": actual_mu, "parameters_before": params_before,
            "parameters_after": dict(parameters), "elite_indices": elite_indices, "elite_references": elite_references,
            "requested_offspring": requested, "failed_queries_before": count_before,
            "failed_queries_accumulated": result["failed_queries_accumulated"], "failed_queries_after": failed_queries,
            "stagnation_overshoot": result["stagnation_overshoot"], "record_before": record_before,
            "record_after": best_profit, "success": success, "controller_event": result["event"],
            "population_after": list(population), "parent_distances": list(parent_distances), **novelty,
            "parameter_events": result["parameter_events"], "rng_before": states_before, "rng_after": _states(rngs)})
        timed["log_assembly"] += perf_counter_ns() - started
    started = perf_counter_ns()
    log["summary"] = {"new_calls": calls, "physical_evaluations": calls,
                      "known_score_validation_evaluations": INITIAL_MU, "duplicate_calls": duplicate_calls,
                      "infeasible_calls": infeasible_calls, "full_generations": full_generations,
                      "partial_children": partial_children, "best_mask": best_mask, "best_profit": best_profit,
                      "best_call": best_call, "final_population": list(population),
                      "final_parameters": dict(parameters), "final_failed_queries": failed_queries}
    log["rng_final"] = _states(rngs)
    timed["log_assembly"] += perf_counter_ns() - started
    timed["total"] = perf_counter_ns() - run_started
    log["timing_ns"] = timed
    return log

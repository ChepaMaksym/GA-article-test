"""Registered tournament-only feedback and open-loop controls.

No historical search module is imported or modified.  The search interface
accepts problem data and known initial scores, never optimum/locality metadata.
The common operator trace is retained from the historical implementation.
Only tournament control differs. Recipient/donor identity and frozen schedule
transport are bound by the external driver, never by an optimum-aware core.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import math
import os
from time import perf_counter_ns

import numpy as np


SCHEMA = "ga-knapsack-tournament-feedback-log-v1"
PROFILES = ("k2", "k3", "k4", "k5", "adaptive", "replay")
INITIAL_MU = 30
FAILED_QUERY_THRESHOLD = 145
CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
PARAMETER_NAMES = ("p_m", "p_c", "target_mu", "tournament_size", "elite_count")
# Retain historical event-boundary metadata for exact baseline/adaptive trace
# comparisons. _parameters separately enforces this study's fixed values.
PARAMETER_BOUNDS = {"p_m": (0.01, 0.08), "p_c": (0.1, 0.9), "target_mu": (10, 100),
                    "tournament_size": (2, 5), "elite_count": (1, 5)}
TIMING_COMPONENTS = ("validation", "selection", "variation", "evaluation", "signal", "controller", "log_assembly")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, name, minimum=0):
    _require(type(value) is int and value >= minimum, f"{name} must be an integer >= {minimum}")


def _profile(profile):
    _require(type(profile) is str and profile in PROFILES, "Unknown registered tournament profile")


def default_parameters(profile="k2"):
    _profile(profile)
    return {"p_m": 0.01, "p_c": 0.9, "target_mu": 30,
            "tournament_size": int(profile[1:]) if profile.startswith("k") else 2, "elite_count": 1}


def _parameters(parameters, profile):
    _profile(profile)
    _require(type(parameters) is dict and set(parameters) == set(PARAMETER_NAMES), "Invalid parameter vector")
    initial = default_parameters(profile)
    for name in PARAMETER_NAMES:
        value = parameters[name]
        lower, upper = PARAMETER_BOUNDS[name]
        if name in ("p_m", "p_c"):
            _require(type(value) in (int, float) and math.isfinite(value), "Probability must be a finite number")
        else:
            _integer(value, name, 1)
        _require(lower <= value <= upper, "Parameter outside registered bounds: " + name)
        _require((name == "tournament_size" and profile in ("adaptive", "replay")) or value == initial[name],
                 "Fixed parameter changed: " + name)
    _require(parameters["elite_count"] < parameters["target_mu"], "No new offspring position")


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
    """Uncached exact evaluation; callers authorize its execution separately."""
    _problem(problem)
    _mask(mask, problem["n"])
    return _evaluate(problem, mask)


def _key(score, capacity):
    return (1, score["profit"]) if score["feasible"] else (0, capacity - score["weight"])


def _pick(occurrences, generator):
    # Do not consume a tie random number when there is one winning occurrence.
    return occurrences[0] if len(occurrences) == 1 else occurrences[int(generator.integers(len(occurrences)))]


def _states(rngs):
    return {name: deepcopy(rngs[name].bit_generator.state) for name in CHANNELS}


def make_rngs(seed, task_index, start_index):
    for name, value in (("seed", seed), ("task_index", task_index), ("start_index", start_index)):
        _integer(value, name)
    return {name: np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [seed, task_index, start_index, channel]))) for channel, name in enumerate(CHANNELS)}


def novelty_probability(distance):
    _integer(distance, "parent distance")
    return Fraction(0) if distance == 0 else Fraction(1) - Fraction(1, 1 << (distance - 1))


def novelty_statistics(distances):
    _require(isinstance(distances, list) and bool(distances), "Parent distances are required")
    total = sum((novelty_probability(distance) for distance in distances), Fraction(0))
    mean = total / len(distances)
    return {"novelty_sum_numerator": total.numerator, "novelty_sum_denominator": total.denominator,
            "novelty_mean_numerator": mean.numerator, "novelty_mean_denominator": mean.denominator}


def scheduled_k(schedule, generation_index):
    """Open-loop lookup; it receives no fitness, success, or population signal.

    On an exactly completed final generation there is no further applied
    value. The final value is held for bookkeeping, not extrapolated.
    """
    _require(type(schedule) in (list, tuple) and bool(schedule), "A nonempty frozen schedule is required")
    _integer(generation_index, "generation_index")
    _require(all(type(value) is int and 2 <= value <= 5 for value in schedule),
             "Schedule values must be integer tournament sizes from 2 through 5")
    return schedule[min(generation_index, len(schedule) - 1)]


def validate_schedule(schedule, budget):
    _integer(budget, "budget", 1)
    _require(type(schedule) in (list, tuple) and len(schedule) == (budget + 28) // 29,
             "Schedule must contain exactly one applied value per full or partial generation")
    _require(scheduled_k(schedule, 0) == 2, "A donor schedule must start at tournament size two")
    return tuple(schedule)


def update_parameters(parameters, failed_queries, success, new_calls, novelty_mean, profile,
                      *, schedule=None, completed_generation=1):
    """Complete-generation bookkeeping and registered tournament policy.

    Static/replay choices are computed separately from current signals.
    Shared event bookkeeping is observational for these open-loop profiles.
    The exact historical controller is retained for ``adaptive``.
    """
    _parameters(parameters, profile)
    _integer(failed_queries, "failed_queries")
    _require(failed_queries < FAILED_QUERY_THRESHOLD and type(success) is bool, "Invalid controller state")
    _integer(new_calls, "new_calls", 1)
    _require(new_calls == parameters["target_mu"] - parameters["elite_count"],
             "Controller update requires all registered offspring of a complete generation")
    _require(isinstance(novelty_mean, Fraction) and 0 <= novelty_mean <= 1, "An exact novelty mean is required")
    accumulated = 0 if success else failed_queries + new_calls
    event = "SUCCESS" if success else "STAGNATION" if accumulated >= FAILED_QUERY_THRESHOLD else "NO_CHANGE"
    after_count = accumulated if event == "NO_CHANGE" else 0
    overshoot = accumulated - FAILED_QUERY_THRESHOLD if event == "STAGNATION" else 0
    _integer(completed_generation, "completed_generation", 1)
    after = dict(parameters)
    if profile == "adaptive":
        if event == "SUCCESS":
            after["tournament_size"] = min(5, parameters["tournament_size"] + 1)
        elif event == "STAGNATION":
            after["tournament_size"] = max(2, parameters["tournament_size"] - 1)
    elif profile == "replay":
        after["tournament_size"] = scheduled_k(schedule, completed_generation)
    else:
        after["tournament_size"] = default_parameters(profile)["tournament_size"]
    _parameters(after, profile)
    events = []
    for name in PARAMETER_NAMES:
        previous, following = parameters[name], after[name]
        events.append({"field": name, "enabled": name == "tournament_size" and profile in ("adaptive", "replay"),
                       "before": previous,
                       "after": following, "direction": "increase" if following > previous else
                       "decrease" if following < previous else "unchanged",
                       "at_boundary": following in PARAMETER_BOUNDS[name]})
    return {"parameters": after, "event": event, "failed_queries_accumulated": accumulated,
            "failed_queries_after": after_count, "stagnation_overshoot": overshoot, "parameter_events": events}


def run_search(problem, initial_masks, initial_scores, profile, rngs, budget=5000, schedule=None):
    """Evaluate exactly ``budget`` new candidates; retain a terminal prefix."""
    run_started = perf_counter_ns()
    timed = {name: 0 for name in TIMING_COMPONENTS}
    started = perf_counter_ns()
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "Search execution is GitHub-Actions only")
    _problem(problem)
    _profile(profile)
    _integer(budget, "budget", 1)
    if profile == "replay":
        schedule = validate_schedule(schedule, budget)
    else:
        _require(schedule is None, "Only replay may receive a donor schedule")
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
    parameters, failed_queries = default_parameters(profile), 0
    timed["validation"] += perf_counter_ns() - started
    started = perf_counter_ns()
    log = {"schema": SCHEMA, "profile": profile, "schedule": list(schedule) if schedule is not None else None,
           "problem": canonical_problem,
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
        mean = Fraction(novelty["novelty_mean_numerator"], novelty["novelty_mean_denominator"])
        timed["signal"] += perf_counter_ns() - started
        complete = len(child_references) == requested
        if complete:
            started = perf_counter_ns()
            population = elite_references + child_references
            full_generations += 1
            success = best_profit is not None and (record_before is None or best_profit > record_before)
            timed["log_assembly"] += perf_counter_ns() - started
            started = perf_counter_ns()
            result = update_parameters(params_before, count_before, success, requested, mean, profile,
                                       schedule=schedule, completed_generation=generation)
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


def extract_schedule(log):
    """Return applied donor values only; no masks, scores, or signals escape.

    The driver must independently verify the donor and bind its task, bank,
    search seed, source SHA and frozen schedule checksum before recipients.
    """
    _require(type(log) is dict and log.get("schema") == SCHEMA and log.get("profile") == "adaptive",
             "Only an adaptive donor journal can produce a schedule")
    budget = log.get("budget")
    _integer(budget, "budget", 1)
    _require(type(log.get("generations")) is list and
             len(log["generations"]) == (budget + 28) // 29, "Incomplete donor generation coverage")
    values = []
    for number, generation in enumerate(log["generations"], 1):
        _require(type(generation) is dict and generation.get("generation") == number and
                 type(generation.get("parameters_before")) is dict, "Invalid donor generation")
        values.append(generation["parameters_before"].get("tournament_size"))
    return list(validate_schedule(values, budget))

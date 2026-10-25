"""Three mutation-control profiles of the same generational binary GA.

The two-signal controller is an explicitly registered research heuristic, not
an article replication.  Search is CI-only.  Historical kernels are neither
imported nor modified, and no optimum or locality oracle is accepted here.
"""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import math
import os
from time import perf_counter_ns

import numpy as np


SCHEMA = "ga-two-signal-mutation-log-v1"
MU = 30
PC = 0.9
CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
METHODS = ("fixed", "adaptive_mutation", "two_signal")
TIMING_COMPONENTS = ("validation", "selection", "variation", "evaluation",
                     "signal", "controller", "log_assembly")


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
    # Python integer sums retain exact arithmetic and original item order.
    weight = sum(w for w, bit in zip(problem["weights"], mask) if bit == "1")
    profit = sum(v for v, bit in zip(problem["profits"], mask) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def evaluate(problem, mask):
    """Exact uncached evaluation; callers separately authorize CI execution."""
    _problem(problem)
    _mask(mask, problem["n"])
    return _evaluate(problem, mask)


def _key(score, capacity):
    return (1, score["profit"]) if score["feasible"] else (0, capacity - score["weight"])


def _pick(indices, rng):
    # Repeated tournament entries remain separate equally likely occurrences.
    return indices[0] if len(indices) == 1 else indices[int(rng.integers(len(indices)))]


def _states(rngs):
    return {name: deepcopy(rngs[name].bit_generator.state) for name in CHANNELS}


def make_rngs(seed, task_index, start_index):
    """Six separate PCG64 streams; the profile name is deliberately absent."""
    for name, value in (("seed", seed), ("task_index", task_index), ("start_index", start_index)):
        _integer(value, name)
    return {name: np.random.Generator(np.random.PCG64(
        np.random.SeedSequence([seed, task_index, start_index, channel])))
        for channel, name in enumerate(CHANNELS)}


def novelty_probability(distance):
    """Exact chance of a uniform-crossover mask unlike both parents.

    This describes crossover BEFORE mutation and says nothing about fitness
    or feasibility.  No floating-point comparison is used for the gate.
    """
    _integer(distance, "parent distance")
    return Fraction(0, 1) if distance == 0 else Fraction(1, 1) - Fraction(1, 1 << (distance - 1))


def novelty_statistics(distances):
    """Return reduced exact sum and mean for all selected parent pairs."""
    _require(isinstance(distances, list) and bool(distances),
             "At least one parent distance is required")
    total = sum((novelty_probability(distance) for distance in distances), Fraction(0, 1))
    mean = total / len(distances)
    return {"novelty_sum_numerator": total.numerator,
            "novelty_sum_denominator": total.denominator,
            "novelty_mean_numerator": mean.numerator,
            "novelty_mean_denominator": mean.denominator}


def update_mutation(n, p, s, success, method="adaptive_mutation", novelty_mean=None):
    """Update after a full generation, preserving the historical control rule.

    Small n is supported for instructional tests with the historical bounds;
    the registered scientific driver admits only n=100.  A denied fifth-failure
    intervention resets the counter, just as an allowed intervention does.
    """
    _integer(n, "n", 2)
    _integer(s, "stagnation")
    lower, upper = 1 / n, min(8 / n, 0.5)
    _require(s < 5 and type(success) is bool and method in METHODS,
             "Invalid controller state, success flag or method")
    _require(isinstance(p, (int, float)) and not isinstance(p, bool) and
             math.isfinite(p) and lower <= p <= upper,
             "Mutation probability outside controller bounds")
    if method == "two_signal":
        _require(isinstance(novelty_mean, Fraction) and 0 <= novelty_mean <= 1,
                 "Two-signal controller requires an exact Fraction in [0,1]")
    if method == "fixed":
        return lower, 0, "FIXED"
    if success:
        return max(lower, p / 2), 0, "SUCCESS_HALVE"
    if s + 1 == 5:
        if method == "two_signal" and novelty_mean > Fraction(1, 2):
            return float(p), 0, "GATE_DENIED"
        return min(upper, p * 2), 0, "STAGNATION_DOUBLE"
    return float(p), s + 1, "NO_CHANGE"


def run_search(problem, initial_masks, initial_scores, method, rngs, budget=5000):
    """Run exactly budget NEW evaluations after the known population.

    All 29 children replace non-elite slots after a full generation, including
    worse or infeasible children.  A final unfinished prefix updates the record
    only.  Signals are measured in all profiles as separately timed research
    observations.  ``timing_ns`` is nondeterministic metadata, not replay state.
    """
    run_started = perf_counter_ns()
    timed = {name: 0 for name in TIMING_COMPONENTS}
    validation_started = perf_counter_ns()
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "Search execution is CI-only")
    _problem(problem)
    _integer(budget, "budget", 1)
    _require(method in METHODS, "Unknown two-signal mutation method")
    _require(isinstance(initial_masks, list) and isinstance(initial_scores, list) and
             len(initial_masks) == len(initial_scores) == MU,
             "Exactly 30 known initial masks and scores required")
    _require(isinstance(rngs, dict) and set(rngs) == set(CHANNELS),
             "Exactly six named RNG channels required")
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
    timed["validation"] += perf_counter_ns() - validation_started
    assembly_started = perf_counter_ns()
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
    timed["log_assembly"] += perf_counter_ns() - assembly_started
    while calls < budget:
        assembly_started = perf_counter_ns()
        generation = len(log["generations"]) + 1
        before = list(population)
        states_before = _states(rngs)
        record_before = best_profit
        p_before, s_before = probability, stagnation
        keys = [_key(scores[reference], capacity) for reference in before]
        start_call = calls + 1
        child_references, parent_distances = [], []
        timed["log_assembly"] += perf_counter_ns() - assembly_started
        selection_started = perf_counter_ns()
        elite_key = max(keys)
        elite_index = _pick([i for i, key in enumerate(keys) if key == elite_key], rngs["ties"])
        elite_reference = before[elite_index]
        timed["selection"] += perf_counter_ns() - selection_started
        for _ in range(min(MU - 1, budget - calls)):
            selection_started = perf_counter_ns()
            tournaments, parents = [], []
            for _parent in range(2):
                pair = [int(rngs["selection"].integers(MU)), int(rngs["selection"].integers(MU))]
                tournaments.append(pair)
                a, b = pair
                winner = (_pick(pair, rngs["ties"]) if keys[a] == keys[b]
                          else a if keys[a] > keys[b] else b)
                parents.append(winner)
            a, b = masks[before[parents[0]]], masks[before[parents[1]]]
            timed["selection"] += perf_counter_ns() - selection_started
            signal_started = perf_counter_ns()
            distance = sum(first != second for first, second in zip(a, b))
            parent_distances.append(distance)
            timed["signal"] += perf_counter_ns() - signal_started
            variation_started = perf_counter_ns()
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
            timed["variation"] += perf_counter_ns() - variation_started
            evaluation_started = perf_counter_ns()
            score = _evaluate(problem, mask)
            timed["evaluation"] += perf_counter_ns() - evaluation_started
            assembly_started = perf_counter_ns()
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
                "parent_indices": parents, "parent_distance": distance,
                "crossover": has_crossover, "pre_mask": pre,
                "mutation_bits": mutation_bits, "mask": mask, **score,
                "duplicate": duplicate, "record_profit": best_profit, "record_call": best_call})
            timed["log_assembly"] += perf_counter_ns() - assembly_started
        signal_started = perf_counter_ns()
        novelty = novelty_statistics(parent_distances)
        mean_novelty = Fraction(novelty["novelty_mean_numerator"], novelty["novelty_mean_denominator"])
        timed["signal"] += perf_counter_ns() - signal_started
        complete = len(child_references) == MU - 1
        if complete:
            assembly_started = perf_counter_ns()
            population = [elite_reference] + child_references
            full_generations += 1
            success = best_profit is not None and (record_before is None or best_profit > record_before)
            timed["log_assembly"] += perf_counter_ns() - assembly_started
            controller_started = perf_counter_ns()
            gate_allows = mean_novelty <= Fraction(1, 2)
            probability, stagnation, event = update_mutation(
                n, p_before, s_before, success, method, mean_novelty)
            timed["controller"] += perf_counter_ns() - controller_started
        else:
            partial_children = len(child_references)
            probability, stagnation, event = p_before, s_before, "PARTIAL_NO_UPDATE"
            gate_allows = None
        assembly_started = perf_counter_ns()
        log["generations"].append({
            "generation": generation, "start_call": start_call, "end_call": calls,
            "complete": complete, "population_before": before, "elite_index": elite_index,
            "p_m": p_before, "stagnation_before": s_before, "record_before": record_before,
            "record_after": best_profit, "p_m_next": probability, "stagnation_after": stagnation,
            "controller_event": event, "population_after": list(population),
            "parent_distances": list(parent_distances), **novelty,
            "gate_allows_increase": gate_allows,
            "rng_before": states_before, "rng_after": _states(rngs)})
        timed["log_assembly"] += perf_counter_ns() - assembly_started
    assembly_started = perf_counter_ns()
    log["summary"] = {
        "new_calls": calls, "physical_evaluations": calls, "known_score_validation_evaluations": MU,
        "duplicate_calls": duplicate_calls, "infeasible_calls": infeasible_calls,
        "full_generations": full_generations, "partial_children": partial_children,
        "best_mask": best_mask, "best_profit": best_profit, "best_call": best_call,
        "final_population": list(population), "final_mutation_probability": probability}
    log["rng_final"] = _states(rngs)
    timed["log_assembly"] += perf_counter_ns() - assembly_started
    timed["total"] = perf_counter_ns() - run_started
    log["timing_ns"] = timed
    return log

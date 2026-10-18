"""Own genotype-novelty feedback for crossover, with a fixed mutation rate.

The rule is an explicitly registered research heuristic, not an article
replication.  Historical helpers and RNG constructors remain unchanged.
Execution, including software fixtures, is restricted to the registered CI.
"""

from __future__ import annotations

from copy import deepcopy
import math
import os

import numpy as np

from studies.adaptive_parameters.mutation_only import engine as historical


SCHEMA = "ga-adaptive-crossover-log-v1"
METHODS = ("fixed_crossover", "adaptive_crossover")
MU = 30
INITIAL_CROSSOVER = 0.9
LOWER_CROSSOVER = 0.1
UPPER_CROSSOVER = 0.9


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "Search execution is CI-only")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
             os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover",
             "Search execution requires the registered repository and branch")


def novelty_probability(d, n):
    """Probability uniform crossover alone differs from both binary parents.

    Their Hamming distance is d.  This concerns genotype novelty, not fitness,
    feasibility or the final child after mutation.
    """
    historical._integer(n, "n", 2)
    historical._integer(d, "parent distance")
    _require(d <= n, "Parent distance cannot exceed n")
    if d == 0:
        return 0.0
    # For exceptionally large d the small power underflows in float64.  Avoid
    # converting an arbitrarily large integer exponent to a platform C int.
    return 1.0 if d >= 1076 else 1.0 - math.ldexp(1.0, 1 - d)


def update_crossover(n, current_p, distances, complete=True, method="adaptive_crossover"):
    """Return (next p_c, observed mean novelty or None, controller event).

    Every selected pair contributes, even if the crossover branch was not
    used.  A terminal prefix reports its working signal but changes no state.
    """
    historical._integer(n, "n", 2)
    _require(method in METHODS, "Unknown crossover method")
    _require(type(complete) is bool, "complete must be bool")
    _require(isinstance(current_p, (int, float)) and not isinstance(current_p, bool) and
             math.isfinite(current_p) and LOWER_CROSSOVER <= current_p <= UPPER_CROSSOVER,
             "Crossover probability must be finite and within [0.1, 0.9]")
    _require(isinstance(distances, (list, tuple)), "Distances must be a list or tuple")
    novelty = [novelty_probability(distance, n) for distance in distances]
    mean = math.fsum(novelty) / len(novelty) if novelty else None
    if not complete:
        return float(current_p), mean, "PARTIAL_NO_UPDATE"
    if mean is None:
        return float(current_p), None, "NO_PAIRS"
    if method == "fixed_crossover":
        return INITIAL_CROSSOVER, mean, "FIXED"
    return LOWER_CROSSOVER + 0.8 * mean, mean, "DIVERSITY_FEEDBACK"


def _validate_rngs(rngs):
    channels = historical.CHANNELS
    _require(isinstance(rngs, dict) and set(rngs) == set(channels),
             "Exactly six named RNG channels are required")
    _require(all(isinstance(rngs[name], np.random.Generator) and
                 isinstance(rngs[name].bit_generator, np.random.PCG64) for name in channels),
             "All channels must be PCG64 generators")
    _require(len({id(rngs[name]) for name in channels}) == len(channels) and
             len({id(rngs[name].bit_generator) for name in channels}) == len(channels),
             "RNG channels may not alias")


def run_search(problem, initial_masks, initial_scores, method, rngs, budget=5000):
    """Run exactly budget new queries; only p_c can change after full blocks.

    The population, tournaments, mutation, elitism and conditional RNG calls
    match the historical fixed GA.  A partial block updates the record only.
    """
    _ci_only()
    historical._problem(problem)
    historical._integer(budget, "budget", 1)
    _require(method in METHODS, "Unknown crossover method")
    _require(isinstance(initial_masks, list) and isinstance(initial_scores, list) and
             len(initial_masks) == len(initial_scores) == MU,
             "Exactly 30 known initial masks and scores are required")
    _validate_rngs(rngs)
    n, capacity = problem["n"], problem["capacity"]
    masks, scores = list(initial_masks), []
    for mask, known in zip(masks, initial_scores):
        historical._mask(mask, n)
        _require(isinstance(known, dict) and set(known) == {"weight", "profit", "feasible"},
                 "Known scores must contain only weight, profit and feasible")
        _require(type(known["weight"]) is int and type(known["profit"]) is int and
                 type(known["feasible"]) is bool and known["weight"] >= 0 and known["profit"] >= 0,
                 "Known scores require exact nonnegative integers and Boolean feasibility")
        actual = historical._evaluate(problem, mask)
        _require(actual == known, "Known initial score disagrees with the exact mask")
        scores.append(actual)
    _require(any(score["feasible"] for score in scores),
             "At least one feasible initial mask is required; no hidden restart is allowed")
    canonical_problem = {"n": n, "weights": list(problem["weights"]),
                         "profits": list(problem["profits"]), "capacity": capacity}
    log = {
        "schema": SCHEMA, "method": method, "problem": canonical_problem,
        "initial_masks": list(masks), "initial_scores": deepcopy(scores),
        "rng_initial": historical._states(rngs), "budget": budget,
        "candidates": [], "generations": [], "summary": None, "rng_final": None,
    }
    population = list(range(MU))
    seen = set(masks)
    best_mask = best_profit = best_call = None
    for mask, score in zip(masks, scores):
        if score["feasible"] and (best_profit is None or score["profit"] > best_profit):
            best_mask, best_profit, best_call = mask, score["profit"], 0
    mutation_probability, crossover_probability = 1 / n, INITIAL_CROSSOVER
    calls = full_generations = partial_children = duplicate_calls = infeasible_calls = 0
    while calls < budget:
        generation = len(log["generations"]) + 1
        before = list(population)
        rng_before = historical._states(rngs)
        record_before, p_before = best_profit, crossover_probability
        keys = [historical._key(scores[reference], capacity) for reference in before]
        elite_key = max(keys)
        elite_index = historical._pick(
            [index for index, key in enumerate(keys) if key == elite_key], rngs["ties"]
        )
        elite_reference = before[elite_index]
        start_call = calls + 1
        child_references, distances = [], []
        for _ in range(min(MU - 1, budget - calls)):
            tournaments, parents = [], []
            for _parent in range(2):
                pair = [int(rngs["selection"].integers(MU)),
                        int(rngs["selection"].integers(MU))]
                tournaments.append(pair)
                a, b = pair
                winner = (historical._pick(pair, rngs["ties"]) if keys[a] == keys[b]
                          else a if keys[a] > keys[b] else b)
                parents.append(winner)
            a, b = masks[before[parents[0]]], masks[before[parents[1]]]
            distance = sum(left != right for left, right in zip(a, b))
            distances.append(distance)
            crosses = bool(rngs["branch"].random() < p_before)
            if crosses:
                choices = rngs["crossover"].random(n) < 0.5
                pre = "".join(a[index] if choices[index] else b[index] for index in range(n))
            else:
                pre = a
            mutation_bits = [index for index, changed in
                             enumerate(rngs["mutation"].random(n) < mutation_probability) if changed]
            bits = list(pre)
            for index in mutation_bits:
                bits[index] = "0" if bits[index] == "1" else "1"
            mask = "".join(bits)
            # No fitness cache: duplicate and infeasible candidates are scored.
            score = historical._evaluate(problem, mask)
            calls += 1
            duplicate = mask in seen
            duplicate_calls += int(duplicate)
            infeasible_calls += int(not score["feasible"])
            seen.add(mask)
            if score["feasible"] and score["profit"] > best_profit:
                best_mask, best_profit, best_call = mask, score["profit"], calls
            reference = len(masks)
            masks.append(mask)
            scores.append(score)
            child_references.append(reference)
            log["candidates"].append({
                "call": calls, "generation": generation, "tournaments": tournaments,
                "parent_indices": parents, "parent_distance": distance,
                "crossover": crosses, "pre_mask": pre, "mutation_bits": mutation_bits,
                "mask": mask, **score, "duplicate": duplicate,
                "record_profit": best_profit, "record_call": best_call,
            })
        complete = len(child_references) == MU - 1
        crossover_probability, mean_novelty, event = update_crossover(
            n, p_before, distances, complete=complete, method=method
        )
        if complete:
            population = [elite_reference] + child_references
            full_generations += 1
        else:
            partial_children = len(child_references)
        log["generations"].append({
            "generation": generation, "start_call": start_call, "end_call": calls,
            "complete": complete, "population_before": before, "elite_index": elite_index,
            "p_m": mutation_probability, "p_c": p_before, "parent_distances": list(distances),
            "mean_novelty": mean_novelty, "record_before": record_before,
            "record_after": best_profit, "p_c_next": crossover_probability,
            "controller_event": event, "population_after": list(population),
            "rng_before": rng_before, "rng_after": historical._states(rngs),
        })
    log["summary"] = {
        "new_calls": calls, "physical_evaluations": calls,
        "known_score_validation_evaluations": MU,
        "duplicate_calls": duplicate_calls, "infeasible_calls": infeasible_calls,
        "full_generations": full_generations, "partial_children": partial_children,
        "best_mask": best_mask, "best_profit": best_profit, "best_call": best_call,
        "final_population": list(population), "final_mutation_probability": mutation_probability,
        "final_crossover_probability": crossover_probability,
    }
    log["rng_final"] = historical._states(rngs)
    return log

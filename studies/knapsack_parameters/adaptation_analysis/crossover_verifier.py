"""Independent replay of the own adaptive-crossover journal.

Only helpers from the historically independent mutation verifier are reused.
Neither the production GA nor any production controller is imported.  The
novelty signal is reconstructed as exact rational arithmetic before rounding.
"""
from __future__ import annotations

from fractions import Fraction
import math

from studies.adaptive_parameters.mutation_only.verifier import (
    _choose, _ci_only, _fields, _integer, _key, _problem, _restore,
    _same, _score, _states,
)


SCHEMA = "ga-adaptive-crossover-log-v1"
METHODS = ("fixed_crossover", "adaptive_crossover")
MU = 30
TOP_FIELDS = {"schema", "method", "problem", "initial_masks", "initial_scores",
              "rng_initial", "budget", "candidates", "generations", "summary", "rng_final"}
CHILD_FIELDS = {"call", "generation", "tournaments", "parent_indices", "crossover",
                "pre_mask", "mutation_bits", "mask", "weight", "profit", "feasible",
                "duplicate", "record_profit", "record_call", "parent_distance"}
GEN_FIELDS = {"generation", "start_call", "end_call", "complete", "population_before",
              "elite_index", "p_m", "p_c", "parent_distances", "mean_novelty",
              "record_before", "record_after", "p_c_next", "controller_event",
              "population_after", "rng_before", "rng_after"}


def _require(condition, message):
    if not condition:
        raise ValueError("Invalid adaptive-crossover journal: " + message)


def _float_same(actual, expected, label):
    if expected is None:
        _same(actual, None, label)
        return
    _require(type(actual) is float and math.isfinite(actual) and
             math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), label)


def _reference_mean(distances, n):
    """Mean of exact r(d), not r(mean(d)) and not a production function."""
    _require(type(distances) is list and type(n) is int and n >= 2,
             "invalid signal input")
    if not distances:
        return None
    total = Fraction(0)
    for distance in distances:
        _require(type(distance) is int and 0 <= distance <= n, "invalid parent distance")
        if distance > 0:
            total += Fraction(1) - Fraction(1, 2 ** (distance - 1))
    return total / len(distances)


def verify_log(log):
    """Reconstruct raw evaluations, operators, state, signal and exact call count.

    The verifier checks journal semantics.  Frozen source SHA, input provenance,
    registered seeds and execution-resource permission belong to an outer gate.
    Small positive budgets below are allowed for future CI software fixtures.
    """
    _ci_only()
    _fields(log, TOP_FIELDS, "adaptive crossover top-level")
    _same(log["schema"], SCHEMA, "adaptive crossover schema")
    method = log["method"]
    _require(type(method) is str and method in METHODS, "unknown crossover method")
    problem = _problem(log["problem"])
    n, capacity = problem["n"], problem["capacity"]
    budget = log["budget"]
    _integer(budget, 1, "new crossover query budget")
    _require(type(log["initial_masks"]) is list and len(log["initial_masks"]) == MU,
             "30 initial masks required")
    _require(type(log["initial_scores"]) is list and len(log["initial_scores"]) == MU,
             "30 initial scores required")
    _require(type(log["candidates"]) is list and len(log["candidates"]) == budget,
             "candidate completeness")
    _require(type(log["generations"]) is list and
             len(log["generations"]) == (budget + 28) // 29, "generation completeness")

    masks = list(log["initial_masks"])
    scores = [_score(problem, mask) for mask in masks]
    for supplied, expected in zip(log["initial_scores"], scores, strict=True):
        _fields(supplied, {"weight", "profit", "feasible"}, "known initial score")
        _same(supplied, expected, "independent initial score")
    _require(any(score["feasible"] for score in scores), "no feasible initial mask")
    population = list(range(MU))
    seen = set(masks)
    record_mask = record_profit = record_call = None
    for mask, score in zip(masks, scores, strict=True):
        if score["feasible"] and (record_profit is None or score["profit"] > record_profit):
            record_mask, record_profit, record_call = mask, score["profit"], 0

    generators = _restore(log["rng_initial"])
    crossover_probability = 0.9
    mutation_probability = 1 / n
    calls = duplicates = infeasible = full_generations = partial_children = 0
    for number, event in enumerate(log["generations"], 1):
        _fields(event, GEN_FIELDS, "crossover generation")
        count = min(29, budget - calls)
        complete = count == 29
        _same(event["generation"], number, "generation number")
        _same(event["start_call"], calls + 1, "generation start")
        _same(event["end_call"], calls + count, "generation end")
        _same(event["complete"], complete, "generation completeness")
        _same(event["population_before"], population, "population before")
        _same(event["p_m"], mutation_probability, "fixed mutation probability")
        # Carrying a previously applied value performs no new arithmetic.
        _same(event["p_c"], crossover_probability, "applied crossover probability")
        _require(0.1 <= event["p_c"] <= 0.9, "applied crossover outside bounds")
        # Replay uses the recorded, independently validated applied float.
        # Ideal rational arithmetic can differ from production by one ulp.
        applied_probability = event["p_c"]
        _same(event["record_before"], record_profit, "record before")
        _same(event["rng_before"], _states(generators), "RNG before elite selection")

        keys = [_key(scores[reference], capacity) for reference in population]
        largest = max(keys)
        elite_index = _choose([index for index, key in enumerate(keys) if key == largest],
                              generators["ties"])
        _same(event["elite_index"], elite_index, "elite tie resolution")
        references, distances = [], []
        for _ in range(count):
            child = log["candidates"][calls]
            _fields(child, CHILD_FIELDS, "crossover candidate")
            tournaments, parents = [], []
            for _parent in range(2):
                entries = [int(generators["selection"].integers(MU)),
                           int(generators["selection"].integers(MU))]
                tournaments.append(entries)
                winner = max(keys[position] for position in entries)
                parents.append(_choose([position for position in entries if keys[position] == winner],
                                       generators["ties"]))
            first = masks[population[parents[0]]]
            second = masks[population[parents[1]]]
            distance = sum(first[position] != second[position] for position in range(n))
            distances.append(distance)
            crosses = bool(generators["branch"].random() < applied_probability)
            if crosses:
                choices = generators["crossover"].random(n) < 0.5
                pre_mask = "".join(first[position] if choices[position] else second[position]
                                   for position in range(n))
            else:
                pre_mask = first
            flags = generators["mutation"].random(n) < mutation_probability
            mutation_bits = [index for index, changed in enumerate(flags) if changed]
            mask = "".join(("0" if bit == "1" else "1") if flags[index] else bit
                           for index, bit in enumerate(pre_mask))
            score = _score(problem, mask)
            duplicate = mask in seen
            seen.add(mask)
            duplicates += int(duplicate)
            infeasible += int(not score["feasible"])
            calls += 1
            if score["feasible"] and (record_profit is None or score["profit"] > record_profit):
                record_mask, record_profit, record_call = mask, score["profit"], calls
            expected_child = {
                "call": calls, "generation": number, "tournaments": tournaments,
                "parent_indices": parents, "crossover": crosses, "pre_mask": pre_mask,
                "mutation_bits": mutation_bits, "mask": mask, **score,
                "duplicate": duplicate, "record_profit": record_profit,
                "record_call": record_call, "parent_distance": distance,
            }
            _same(child, expected_child, f"raw candidate replay at query {calls}")
            references.append(len(masks))
            masks.append(mask)
            scores.append(score)

        mean_fraction = _reference_mean(distances, n)
        mean_value = None if mean_fraction is None else float(mean_fraction)
        _same(event["parent_distances"], distances, "all pairs, including uncrossed parents")
        _float_same(event["mean_novelty"], mean_value, "independent rational novelty mean")
        _same(event["record_after"], record_profit, "record after")
        if complete:
            next_population = [population[elite_index], *references]
            if method == "fixed_crossover":
                expected_probability, feedback = 0.9, "FIXED"
            else:
                expected_probability = float(Fraction(1, 10) + Fraction(4, 5) * mean_fraction)
                feedback = "DIVERSITY_FEEDBACK"
            full_generations += 1
        else:
            expected_probability, feedback = applied_probability, "PARTIAL_NO_UPDATE"
            next_population = list(population)
            partial_children = count
        if not complete or method == "fixed_crossover":
            _same(event["p_c_next"], expected_probability, "unchanged/fixed crossover probability")
        else:
            _float_same(event["p_c_next"], expected_probability, "independent next crossover probability")
        _require(0.1 <= event["p_c_next"] <= 0.9, "next crossover outside bounds")
        _same(event["controller_event"], feedback, "controller event")
        _same(event["population_after"], next_population, "population after")
        _same(event["rng_after"], _states(generators), "RNG after generation")
        crossover_probability = event["p_c_next"]
        population = next_population

    _same(log["rng_final"], _states(generators), "final RNG")
    summary = {
        "new_calls": budget, "physical_evaluations": budget,
        "known_score_validation_evaluations": MU, "duplicate_calls": duplicates,
        "infeasible_calls": infeasible, "full_generations": full_generations,
        "partial_children": partial_children, "best_mask": record_mask,
        "best_profit": record_profit, "best_call": record_call,
        "final_population": list(population), "final_mutation_probability": mutation_probability,
        "final_crossover_probability": crossover_probability,
    }
    _same(log["summary"], summary, "independently reconstructed final summary")
    return {
        "verification_status": "VERIFIED", "new_calls": calls,
        "independent_score_checks": MU + calls, "completed_generations": full_generations,
        "partial_generations": int(partial_children > 0), "duplicate_candidates": duplicates,
        "record_profit": record_profit, "record_call": record_call,
        "final_population_refs": population, "final_p_m": mutation_probability,
        "final_p_c": crossover_probability, "summary": summary,
    }

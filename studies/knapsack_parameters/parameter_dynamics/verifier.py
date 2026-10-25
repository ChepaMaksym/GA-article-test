"""Independent CI replay of five-parameter GA journals.

The producer's evaluator, selector, controller and population metrics are not
imported. Intermediate crossover fitness is evaluated only here, after search.
Execution SHA, input/seed identity and artifact transport are bound by the
driver; this verifier accepts no optimum or local-neighborhood certificate.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import json
import os

import numpy as np


SCHEMA = "ga-knapsack-parameter-dynamics-log-v1"
CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
PARAMETER_NAMES = ("p_m", "p_c", "target_mu", "tournament_size", "elite_count")
INITIAL = {"p_m": 0.01, "p_c": 0.9, "target_mu": 30,
           "tournament_size": 2, "elite_count": 1}
BOUNDS = {"p_m": (0.01, 0.08), "p_c": (0.1, 0.9), "target_mu": (10, 100),
          "tournament_size": (2, 5), "elite_count": (1, 5)}
TOP_FIELDS = {"schema", "profile", "problem", "initial_masks", "initial_scores", "rng_initial",
              "budget", "candidates", "generations", "summary", "rng_final", "timing_ns"}
GEN_FIELDS = {
    "generation", "start_call", "end_call", "complete", "population_before", "actual_parent_mu",
    "parameters_before", "parameters_after", "elite_indices", "elite_references", "requested_offspring",
    "failed_queries_before", "failed_queries_accumulated", "failed_queries_after", "stagnation_overshoot",
    "record_before", "record_after", "success", "controller_event", "population_after", "parent_distances",
    "novelty_sum_numerator", "novelty_sum_denominator", "novelty_mean_numerator",
    "novelty_mean_denominator", "parameter_events", "rng_before", "rng_after",
}
CHILD_FIELDS = {
    "call", "generation", "tournaments", "parent_indices", "parent_distance", "crossover", "pre_mask",
    "mutation_bits", "mask", "weight", "profit", "feasible", "duplicate", "record_profit", "record_call",
}
TIMING_FIELDS = {"validation", "selection", "variation", "evaluation", "signal", "controller",
                 "log_assembly", "total"}


def _require(condition, message):
    if not condition:
        raise ValueError("Invalid parameter-dynamics journal: " + message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "GitHub Actions required")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test", "wrong repository")
    _require(os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover", "wrong branch")


def _same(actual, expected, label):
    try:
        first = json.dumps(actual, sort_keys=True, separators=(",", ":"), allow_nan=False)
        second = json.dumps(expected, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid parameter-dynamics journal: non-JSON " + label) from exc
    _require(first == second, label)


def _fields(value, fields, label):
    _require(type(value) is dict and set(value) == fields, label + " fields")


def _integer(value, minimum, label):
    _require(type(value) is int and value >= minimum, label)


def _problem(value):
    _fields(value, {"n", "weights", "profits", "capacity"}, "problem")
    _integer(value["n"], 2, "chromosome length")
    _integer(value["capacity"], 0, "capacity")
    for name in ("weights", "profits"):
        _require(type(value[name]) is list and len(value[name]) == value["n"], name + " length")
        for entry in value[name]:
            _integer(entry, 1, name + " positive integer")
    return value


def _score(problem, mask):
    _require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"}, "binary mask")
    weight = profit = 0
    for position, bit in enumerate(mask):
        if bit == "1":
            weight += problem["weights"][position]
            profit += problem["profits"][position]
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _key(score, capacity):
    return (1, score["profit"]) if score["feasible"] else (0, capacity - score["weight"])


def _choose(entries, generator):
    # Repeated tournament positions remain repeated tie entries.
    return entries[0] if len(entries) == 1 else entries[int(generator.integers(len(entries)))]


def _states(generators):
    return {name: copy.deepcopy(generators[name].bit_generator.state) for name in CHANNELS}


def _restore(value):
    _fields(value, set(CHANNELS), "RNG channels")
    generators = {}
    for name in CHANNELS:
        state = value[name]
        _require(type(state) is dict and state.get("bit_generator") == "PCG64", "PCG64 state")
        try:
            bit_generator = np.random.PCG64(0)
            bit_generator.state = copy.deepcopy(state)
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            raise ValueError("Invalid parameter-dynamics journal: RNG " + name) from exc
        generators[name] = np.random.Generator(bit_generator)
    _same(_states(generators), value, "lossless RNG restoration")
    return generators


def _reference_mean(distances, n):
    _require(type(distances) is list and bool(distances), "nonempty selected-pair list")
    total = Fraction(0)
    for distance in distances:
        _require(type(distance) is int and 0 <= distance <= n, "parent distance")
        if distance:
            total += Fraction(1) - Fraction(1, 2 ** (distance - 1))
    return total / len(distances)


def _reference_update(parameters, failed_before, success, count, profile, mean):
    """Independent simultaneous update from the registered old state."""
    if success:
        accumulated, failed_after, overshoot, event = 0, 0, 0, "SUCCESS"
    else:
        accumulated = failed_before + count
        if accumulated >= 145:
            failed_after, overshoot, event = 0, accumulated - 145, "STAGNATION"
        else:
            failed_after, overshoot, event = accumulated, 0, "NO_CHANGE"
    after = copy.deepcopy(parameters)
    for bit, field in enumerate(PARAMETER_NAMES):
        if not profile & (1 << bit):
            after[field] = INITIAL[field]
            continue
        old = parameters[field]
        if field == "p_c":
            after[field] = float(Fraction(1, 10) + Fraction(4, 5) * mean)
        elif event == "SUCCESS":
            if field == "p_m":
                after[field] = max(0.01, old / 2)
            elif field == "target_mu":
                after[field] = max(10, (old + 1) // 2)
            else:
                after[field] = min(5, old + 1)
        elif event == "STAGNATION":
            if field == "p_m":
                after[field] = min(0.08, old * 2)
            elif field == "target_mu":
                after[field] = min(100, old * 2)
            elif field == "tournament_size":
                after[field] = max(2, old - 1)
            else:
                after[field] = max(1, old - 1)
    events = []
    for bit, field in enumerate(PARAMETER_NAMES):
        before, next_value = parameters[field], after[field]
        events.append({"field": field, "enabled": bool(profile & (1 << bit)),
                       "before": before, "after": next_value,
                       "direction": "increase" if next_value > before else "decrease" if next_value < before else "unchanged",
                       "at_boundary": next_value in BOUNDS[field]})
    return {"parameters_after": after, "failed_queries_accumulated": accumulated,
            "failed_queries_after": failed_after, "stagnation_overshoot": overshoot,
            "controller_event": event, "parameter_events": events}


def _population_point(q, complete, population, masks, scores, record_mask, n):
    selected = [masks[reference] for reference in population]
    size = len(selected)
    _require(size >= 2, "population metric denominator")
    feasible = [scores[reference] for reference in population if scores[reference]["feasible"]]
    different_pairs = 0
    for position in range(n):
        ones = sum(mask[position] == "1" for mask in selected)
        different_pairs += ones * (size - ones)
    return {"q": q, "complete": complete, "population_size": size,
            "unique_masks": len(set(selected)), "unique_fraction": len(set(selected)) / size,
            "mean_pairwise_hamming": different_pairs / (size * (size - 1) // 2),
            "feasible_fraction": len(feasible) / size,
            "mean_feasible_profit": sum(score["profit"] for score in feasible) / len(feasible) if feasible else None,
            "record_in_population": record_mask is not None and record_mask in selected}


def _validate_timings(value):
    _fields(value, TIMING_FIELDS, "timing")
    for name in TIMING_FIELDS:
        _integer(value[name], 0, "nonnegative integer timing " + name)
    _require(value["total"] >= sum(duration for name, duration in value.items() if name != "total"),
             "disjoint timing scopes exceed total")


def verify_log(log):
    """Replay a complete dynamic journal, including its final partial block.

    Small n/budgets support educational CI fixtures. The driver binds real
    n100/budget5000/task/seed identities independently; no optimum is accepted.
    """
    _ci_only()
    _fields(log, TOP_FIELDS, "top-level")
    _same(log["schema"], SCHEMA, "schema")
    profile = log["profile"]
    _integer(profile, 0, "profile")
    _require(profile <= 31, "profile bound")
    problem = _problem(log["problem"])
    n, capacity = problem["n"], problem["capacity"]
    budget = log["budget"]
    _integer(budget, 1, "new-query budget")
    _validate_timings(log["timing_ns"])
    _require(type(log["initial_masks"]) is list and len(log["initial_masks"]) == 30, "30 initial masks")
    _require(type(log["initial_scores"]) is list and len(log["initial_scores"]) == 30, "30 initial scores")
    _require(type(log["candidates"]) is list and len(log["candidates"]) == budget, "complete candidate list")
    _require(type(log["generations"]) is list and bool(log["generations"]), "nonempty generation list")

    masks = list(log["initial_masks"])
    scores = [_score(problem, mask) for mask in masks]
    for supplied, actual in zip(log["initial_scores"], scores, strict=True):
        _fields(supplied, {"weight", "profit", "feasible"}, "known initial score")
        _same(supplied, actual, "independently evaluated initial score")
    population = list(range(30))
    seen = set(masks)
    record_mask = record_profit = record_call = None
    for mask, score in zip(masks, scores, strict=True):
        if score["feasible"] and (record_profit is None or score["profit"] > record_profit):
            record_mask, record_profit, record_call = mask, score["profit"], 0

    record_events = [{"q": 0, "profit": record_profit}]
    population_trace = [_population_point(0, True, population, masks, scores, record_mask, n)]
    generation_trace, candidate_metrics = [], []
    operator_bins = [{"distance": distance, "total": 0, "crossed": 0, "novel_crossed": 0,
                      "feasible_crossed": 0, "better_both_crossed": 0} for distance in range(n + 1)]
    generators = _restore(log["rng_initial"])
    parameters, failed = copy.deepcopy(INITIAL), 0
    calls = duplicates = infeasible = full_generations = partial_children = 0
    for number, event in enumerate(log["generations"], 1):
        _require(calls < budget, "extra generation after exhausted budget")
        _fields(event, GEN_FIELDS, "generation")
        quota = parameters["target_mu"] - parameters["elite_count"]
        count = min(quota, budget - calls)
        complete = count == quota
        for name, expected in (
                ("generation", number), ("start_call", calls + 1), ("end_call", calls + count),
                ("complete", complete), ("population_before", population), ("actual_parent_mu", len(population)),
                ("parameters_before", parameters), ("requested_offspring", quota),
                ("failed_queries_before", failed), ("record_before", record_profit), ("rng_before", _states(generators))):
            _same(event[name], expected, name + " before generation")
        record_before_generation = record_profit
        keys = [_key(scores[reference], capacity) for reference in population]
        remaining = list(range(len(population)))
        elite_indices = []
        for _ in range(parameters["elite_count"]):
            winning_key = max(keys[position] for position in remaining)
            elite = _choose([position for position in remaining if keys[position] == winning_key], generators["ties"])
            elite_indices.append(elite)
            remaining.remove(elite)
        elite_refs = [population[position] for position in elite_indices]
        _same(event["elite_indices"], elite_indices, "sequential elite tie resolution")
        _same(event["elite_references"], elite_refs, "elite references")
        references, distances = [], []
        for _ in range(count):
            child = log["candidates"][calls]
            _fields(child, CHILD_FIELDS, "candidate")
            tournaments, parents = [], []
            for _parent in range(2):
                positions = [int(generators["selection"].integers(len(population)))
                             for _ in range(parameters["tournament_size"])]
                tournaments.append(positions)
                winning_key = max(keys[position] for position in positions)
                parents.append(_choose([position for position in positions if keys[position] == winning_key], generators["ties"]))
            parent_refs = [population[position] for position in parents]
            first, second = [masks[reference] for reference in parent_refs]
            distance = sum(first[position] != second[position] for position in range(n))
            distances.append(distance)
            crossed = bool(generators["branch"].random() < parameters["p_c"])
            if crossed:
                choices = generators["crossover"].random(n) < 0.5
                pre_mask = "".join(first[position] if choices[position] else second[position] for position in range(n))
            else:
                pre_mask = first
            mutation_flags = generators["mutation"].random(n) < parameters["p_m"]
            mutation_bits = [position for position, changed in enumerate(mutation_flags) if changed]
            mask = "".join(("0" if bit == "1" else "1") if mutation_flags[position] else bit
                           for position, bit in enumerate(pre_mask))
            score = _score(problem, mask)
            # Independent POSTSEARCH evaluation; never available to the producer.
            pre_score = _score(problem, pre_mask)
            pre_novel = pre_mask != first and pre_mask != second
            pre_better_both = pre_score["feasible"] and all(
                _key(pre_score, capacity) > _key(scores[reference], capacity) for reference in parent_refs)
            pre_above_record = pre_score["feasible"] and (record_profit is None or pre_score["profit"] > record_profit)
            strict_record = score["feasible"] and (record_profit is None or score["profit"] > record_profit)
            duplicate = mask in seen
            seen.add(mask)
            duplicates += int(duplicate)
            infeasible += int(not score["feasible"])
            calls += 1
            if strict_record:
                record_mask, record_profit, record_call = mask, score["profit"], calls
                record_events.append({"q": calls, "profit": record_profit})
            expected_child = {"call": calls, "generation": number, "tournaments": tournaments,
                              "parent_indices": parents, "parent_distance": distance, "crossover": crossed,
                              "pre_mask": pre_mask, "mutation_bits": mutation_bits, "mask": mask, **score,
                              "duplicate": duplicate, "record_profit": record_profit, "record_call": record_call}
            _same(child, expected_child, "candidate replay at query " + str(calls))
            bucket = operator_bins[distance]
            bucket["total"] += 1
            if crossed:
                bucket["crossed"] += 1
                bucket["novel_crossed"] += int(pre_novel)
                bucket["feasible_crossed"] += int(pre_score["feasible"])
                bucket["better_both_crossed"] += int(pre_better_both)
            candidate_metrics.append({"q": calls, "parent_refs": parent_refs, "parent_distance": distance,
                                      "crossed": crossed, "pre_weight": pre_score["weight"], "pre_profit": pre_score["profit"],
                                      "pre_feasible": pre_score["feasible"], "pre_novel": pre_novel,
                                      "pre_better_both": pre_better_both, "duplicate": duplicate, "strict_record": strict_record,
                                      "mutation_created_record": strict_record and not pre_above_record,
                                      "mutation_preserved_record": strict_record and pre_above_record,
                                      "mutation_lost_record": pre_above_record and not strict_record})
            references.append(len(masks))
            masks.append(mask)
            scores.append(score)

        mean = _reference_mean(distances, n)
        total = mean * len(distances)
        exact_values = {"parent_distances": distances, "novelty_sum_numerator": total.numerator,
                        "novelty_sum_denominator": total.denominator, "novelty_mean_numerator": mean.numerator,
                        "novelty_mean_denominator": mean.denominator, "record_after": record_profit}
        for name, expected in exact_values.items():
            _same(event[name], expected, "exact generation " + name)
        if complete:
            success = record_profit is not None and (record_before_generation is None or record_profit > record_before_generation)
            update = _reference_update(parameters, failed, success, count, profile, mean)
            next_population = elite_refs + references
            full_generations += 1
        else:
            success = None
            update = {"parameters_after": copy.deepcopy(parameters), "failed_queries_accumulated": failed,
                      "failed_queries_after": failed, "stagnation_overshoot": None,
                      "controller_event": "PARTIAL_NO_UPDATE", "parameter_events": []}
            next_population = list(population)
            partial_children = count
        _same(event["success"], success, "completed-generation success")
        for name, expected in update.items():
            _same(event[name], expected, "independent controller " + name)
        _same(event["population_after"], next_population, "committed population")
        _same(event["rng_after"], _states(generators), "RNG after generation")
        generation_trace.append({"q": calls, "start_q": calls - count + 1, "complete": complete,
                                 "actual_parent_mu": len(population), "requested_offspring": quota,
                                 "parameters_before": copy.deepcopy(parameters), **copy.deepcopy(update),
                                 "failed_queries_before": failed, "success": success,
                                 "mean_novelty": float(mean), "parent_distances": distances})
        population = next_population
        parameters, failed = update["parameters_after"], update["failed_queries_after"]
        population_trace.append(_population_point(calls, complete, population, masks, scores, record_mask, n))

    _same(calls, budget, "generation coverage of all queries")
    _same(log["rng_final"], _states(generators), "final RNG states")
    summary = {"new_calls": budget, "physical_evaluations": budget, "known_score_validation_evaluations": 30,
               "duplicate_calls": duplicates, "infeasible_calls": infeasible, "full_generations": full_generations,
               "partial_children": partial_children, "best_mask": record_mask, "best_profit": record_profit,
               "best_call": record_call, "final_population": list(population), "final_parameters": parameters,
               "final_failed_queries": failed}
    _same(log["summary"], summary, "independently reconstructed summary")
    return {"verification_status": "VERIFIED", "new_calls": calls, "independent_score_checks": 30 + 2 * calls,
            "initial_score_checks": 30, "final_score_checks": calls, "premutation_score_checks": calls,
            "completed_generations": full_generations, "partial_generations": int(partial_children > 0),
            "duplicate_candidates": duplicates, "record_profit": record_profit, "record_call": record_call,
            "final_population_refs": population, "final_parameters": copy.deepcopy(parameters),
            "final_failed_queries": failed, "summary": summary,
            "timing_status": "OBSERVATIONAL_VALIDATED_NOT_RECONSTRUCTED", "timing_ns": copy.deepcopy(log["timing_ns"]),
            "derived_metrics": {"record_events": record_events, "population_trace": population_trace,
                                "generation_trace": generation_trace, "operator_bins": operator_bins,
                                "candidate_metrics": candidate_metrics}}

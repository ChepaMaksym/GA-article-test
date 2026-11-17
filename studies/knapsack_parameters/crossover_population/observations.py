"""Post-search observations on the total-evaluation scale.

Authorized local derivative of retained observations, exact source SHA256:
b2ad589f47264f4e9247df4481be3f68e2146c00f52bac4b22897b72a79c1a0b.
Changes: new schema/contract plus legacy-schema admission for retained 90%
controls, explicit fixed-parameter validation and a 100000 final checkpoint.
Evaluation, phase reconstruction, diversity and attainment formulas are retained.
This module never calls the search, an exact solver or a producer helper.
"""
from __future__ import annotations

from copy import deepcopy
import math
import os


CHECKPOINTS = (5000, 10000, 20000, 50000, 100000)


def _require(condition, message):
    if not condition:
        raise ValueError("Invalid population observation: " + message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "GitHub Actions required")


def population_metrics(references, masks, scores, item_count):
    """Compute exact average pairwise Hamming distance using allele counts.

    For each position, ones*(size-ones) is the number of unordered pairs with
    different bits. No quadratic pair enumeration or additional evaluation occurs.
    """
    _require(type(references) is list and len(references) >= 2, "a completed population of size at least two is required")
    _require(type(item_count) is int and item_count >= 2, "invalid item count")
    _require(all(type(ref) is int and 0 <= ref < len(masks) == len(scores) for ref in references),
             "population references are outside the retained evaluations")
    selected = [masks[ref] for ref in references]
    _require(all(type(mask) is str and len(mask) == item_count and set(mask) <= {"0", "1"} for mask in selected),
             "a population mask is malformed")
    size = len(selected)
    one_counts = [0] * item_count
    for mask in selected:
        for position, bit in enumerate(mask):
            one_counts[position] += int(bit == "1")
    hamming_sum = sum(ones * (size - ones) for ones in one_counts)
    unordered_pairs = size * (size - 1) // 2
    feasible = [scores[ref]["profit"] for ref in references if scores[ref]["feasible"]]
    unique_count = len(set(selected))
    return {"population_size": size, "unique_count": unique_count,
            "unique_fraction": unique_count / size, "feasible_count": len(feasible),
            "feasible_fraction": len(feasible) / size,
            "mean_feasible_profit": sum(feasible) / len(feasible) if feasible else None,
            "pairwise_hamming_sum": hamming_sum, "unordered_pairs": unordered_pairs,
            "mean_pairwise_hamming": hamming_sum / unordered_pairs}


def extract(log, total_budget, reference_optimum, *, checkpoints=CHECKPOINTS):
    """Reconstruct checkpoints after search without passing OPT to the producer.

    Initial candidates occupy q=1..mu. Offspring call j occupies q=mu+j.
    At q<mu no completed initial population exists. Within a generation, all
    evaluated offspring contribute to the record but only a completed block
    replaces the population. The caller independently verifies the full journal.
    """
    _require(type(log) is dict and log.get("schema") in (
        "ga-knapsack-configured-fixed-log-v1", "ga-knapsack-population-crossover-log-v1"),
        "configured fixed or population-crossover journal required")
    if log["schema"] == "ga-knapsack-population-crossover-log-v1":
        _require(log.get("configuration_contract") == "population-crossover-v1", "new configuration contract required")
    else:
        _require("configuration_contract" not in log, "legacy contract must remain unchanged")
    problem = log.get("problem")
    _require(type(problem) is dict and type(problem.get("n")) is int and problem["n"] >= 2,
             "a valid chromosome dimension is required")
    parameters = log.get("initial_parameters")
    _require(type(parameters) is dict and set(parameters) == {
        "p_m", "p_c", "target_mu", "tournament_size", "elite_count"}, "fixed parameters required")
    _require(type(parameters["p_m"]) in (int, float) and parameters["p_m"] == 1 / problem["n"],
             "dimension-normalized mutation required")
    _require(type(parameters["p_c"]) in (int, float) and math.isfinite(parameters["p_c"])
             and 0 <= parameters["p_c"] <= 1, "finite crossover in [0,1] required")
    _require(type(log.get("profile")) is int and log["profile"] == 0
             and type(parameters["tournament_size"]) is int and parameters["tournament_size"] == 2
             and type(parameters["elite_count"]) is int and parameters["elite_count"] == 1,
             "fixed profile zero, two-way selection and single elite required")
    if log["schema"] == "ga-knapsack-configured-fixed-log-v1":
        _require(parameters["p_c"] == 0.9, "legacy crossover must be 90%")
    _require(type(total_budget) is int and total_budget > 0, "positive total budget required")
    _require(type(reference_optimum) is int and reference_optimum > 0, "a positive external exact optimum is required")
    initial_size = log.get("initial_population_size")
    _require(type(initial_size) is int and initial_size >= 2
             and initial_size == parameters["target_mu"], "invalid initial size")
    _require(log.get("budget") == len(log["candidates"]) == total_budget - initial_size,
             "initial and offspring evaluations do not exhaust the total budget")
    _require(len(log["initial_masks"]) == len(log["initial_scores"]) == initial_size,
             "initial evaluations are incomplete")
    _require(all(type(q) is int and 0 <= q <= total_budget for q in checkpoints)
             and len(checkpoints) == len(set(checkpoints)), "invalid or repeated checkpoints")
    item_count = log["problem"]["n"]
    masks = list(log["initial_masks"]) + [row["mask"] for row in log["candidates"]]
    scores = list(log["initial_scores"]) + [{key: row[key] for key in ("weight", "profit", "feasible")}
                                          for row in log["candidates"]]
    events = []
    record_profit = record_mask = None
    for q, (mask, score) in enumerate(zip(masks, scores, strict=True), 1):
        _require(type(score["profit"]) is int and type(score["feasible"]) is bool, "invalid recorded score types")
        if score["feasible"] and (record_profit is None or score["profit"] > record_profit):
            record_profit, record_mask = score["profit"], mask
            _require(record_profit <= reference_optimum, "a retained feasible value exceeds the external optimum")
            events.append({"q": q, "profit": record_profit, "mask": record_mask,
                           "phase": "initializing" if q <= initial_size else "search"})

    def record_at(q):
        eligible = [event for event in events if event["q"] <= q]
        return eligible[-1] if eligible else None

    population_trace = []
    initial_refs = list(range(initial_size))
    population_trace.append({"q": initial_size, "generation": 0,
                             **population_metrics(initial_refs, masks, scores, item_count)})
    generation_trace = []
    for number, generation in enumerate(log["generations"], 1):
        _require(generation["generation"] == number, "generation order differs")
        _require(type(generation["start_call"]) is int and type(generation["end_call"]) is int
                 and 1 <= generation["start_call"] <= generation["end_call"] <= log["budget"],
                 "generation call bounds are invalid")
        if generation["complete"]:
            population_trace.append({"q": initial_size + generation["end_call"], "generation": number,
                                     **population_metrics(generation["population_after"], masks, scores, item_count)})
        generation_trace.append({"generation": number, "start_q": initial_size + generation["start_call"],
                                 "end_q": initial_size + generation["end_call"], "complete": generation["complete"],
                                 "requested_offspring": generation["requested_offspring"],
                                 "evaluated_offspring": generation["end_call"] - generation["start_call"] + 1,
                                 "parent_population_size": generation["actual_parent_mu"]})

    observations = []
    for q in checkpoints:
        record = record_at(q)
        base = {"q": q, "record_profit": record["profit"] if record else None,
                "record_mask": record["mask"] if record else None,
                "record_total_q": record["q"] if record else None,
                "gap_percent": (100 * (reference_optimum - record["profit"]) / reference_optimum
                                if record else None)}
        if q < initial_size:
            observations.append({**base, "phase": "initializing", "initial_evaluations": q,
                                 "offspring_evaluations": 0, "completed_generations": 0,
                                 "completed_population": None, "population_total_q": None,
                                 "population_metrics": None, "partial_initial_count": q,
                                 "partial_initial_references": list(range(q)),
                                 "partial_offspring_count": 0, "partial_offspring_references": [],
                                 "parameters": None, "failed_queries": None})
            continue
        new_queries = q - initial_size
        population = list(initial_refs)
        population_q = initial_size
        completed = failed = 0
        parameters = deepcopy(log["initial_parameters"])
        pending = []
        for generation in log["generations"]:
            if generation["start_call"] > new_queries:
                break
            if generation["complete"] and generation["end_call"] <= new_queries:
                population = list(generation["population_after"])
                population_q = initial_size + generation["end_call"]
                parameters = deepcopy(generation["parameters_after"])
                failed = generation["failed_queries_after"]
                completed += 1
                pending = []
            else:
                final_call = min(new_queries, generation["end_call"])
                pending = list(range(initial_size + generation["start_call"] - 1,
                                     initial_size + final_call))
                break
        observations.append({**base, "phase": "search", "initial_evaluations": initial_size,
                             "offspring_evaluations": new_queries, "completed_generations": completed,
                             "completed_population": population, "population_total_q": population_q,
                             "population_metrics": population_metrics(population, masks, scores, item_count),
                             "partial_initial_count": 0, "partial_initial_references": [],
                             "partial_offspring_count": len(pending), "partial_offspring_references": pending,
                             "parameters": parameters, "failed_queries": failed})
    targets = {}
    for threshold in (93, 95, 99):
        hit = next((row["q"] for row in events if 100 * row["profit"] >= threshold * reference_optimum), None)
        targets[str(threshold)] = {"first_total_evaluation": hit, "attained": hit is not None,
                                   "restricted_evaluations": hit if hit is not None else total_budget}
    _require(record_profit is not None, "no feasible record was retained")
    return {"schema": "population-crossover-observations-v1", "total_evaluations": total_budget,
            "initial_evaluations": initial_size, "new_evaluations": log["budget"],
            "optimum": reference_optimum, "record_events": events, "checkpoints": observations,
            "population_trace": population_trace, "generation_trace": generation_trace,
            "targets": targets, "final_best_profit": record_profit,
            "final_gap_percent": 100 * (reference_optimum - record_profit) / reference_optimum,
            "completed_generations": sum(bool(row["complete"]) for row in log["generations"]),
            "terminal_partial_offspring": log["summary"]["partial_children"],
            "search_evaluations_performed": 0}

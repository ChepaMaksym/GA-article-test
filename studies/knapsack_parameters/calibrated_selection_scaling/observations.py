"""Postsearch measurements on total evaluations, including every initial query.

This module performs no search, statistical inference or plotting. The caller
must independently replay the journal before extracting these observations.
"""
from __future__ import annotations

from copy import deepcopy

from .common import ci_only, require
from .configuration import LOG_SCHEMA, TOTAL_EVALUATIONS


CHECKPOINTS = (5000, 10000, 20000, 50000, 100000)
TARGETS = (93, 95, 99)


def population_metrics(references, masks, scores, item_count):
    """Use allele counts for exact pairwise sums; normalize by item count."""
    ci_only()
    require(type(references) is list and len(references) >= 2 and
            type(item_count) is int and item_count >= 2, "Invalid population metric denominator")
    require(len(masks) == len(scores) and all(type(ref) is int and 0 <= ref < len(masks) for ref in references),
            "Population reference is outside retained evaluations")
    selected = [masks[reference] for reference in references]
    require(all(type(mask) is str and len(mask) == item_count and set(mask) <= {"0", "1"} for mask in selected),
            "Malformed population mask")
    mu = len(selected)
    pairs = mu * (mu - 1) // 2
    hamming = sum(ones * (mu - ones) for ones in
                  (sum(mask[position] == "1" for mask in selected) for position in range(item_count)))
    feasible = [scores[reference]["profit"] for reference in references if scores[reference]["feasible"]]
    unique = len(set(selected))
    return {"population_size": mu, "unique_count": unique, "unique_fraction": unique / mu,
            "duplicate_positions": mu - unique, "duplicate_fraction": (mu - unique) / mu,
            "feasible_count": len(feasible), "feasible_fraction": len(feasible) / mu,
            "mean_feasible_profit": sum(feasible) / len(feasible) if feasible else None,
            "pairwise_hamming_sum": hamming, "unordered_pairs": pairs,
            "mean_pairwise_hamming": hamming / pairs,
            "normalized_diversity": hamming / (pairs * item_count)}


def extract(log, total_budget, reference_optimum, *, checkpoints=CHECKPOINTS):
    """Include q=1..mu, prescribed checkpoints and the terminal evaluation.

    T is the first total evaluation with 100*profit >= target*OPT, using exact
    integer comparisons. A miss is right censored and contributes the restricted
    value B=100000; attainment is retained to distinguish a miss from a hit at B.
    Partial offspring update the best record, but never commit a population or
    update the selection controller.
    """
    ci_only()
    require(type(log) is dict and log.get("schema") == LOG_SCHEMA, "Calibrated-selection journal required")
    require(type(total_budget) is int and total_budget > 0 and type(reference_optimum) is int and
            reference_optimum > 0, "Invalid total budget or external optimum")
    mu = log.get("initial_population_size")
    require(type(mu) is int and mu >= 2 and len(log["initial_masks"]) == len(log["initial_scores"]) == mu,
            "Initial evaluations are incomplete")
    require(log["budget"] == len(log["candidates"]) == total_budget - mu,
            "Total evaluations must count initialization")
    require(all(type(q) is int and 0 <= q <= total_budget for q in checkpoints) and
            len(checkpoints) == len(set(checkpoints)), "Invalid or repeated checkpoint")
    requested = sorted(set(checkpoints) | set(range(1, mu + 1)) | {total_budget})
    n = log["problem"]["n"]
    masks = list(log["initial_masks"]) + [row["mask"] for row in log["candidates"]]
    scores = list(log["initial_scores"]) + [{key: row[key] for key in ("weight", "profit", "feasible")}
                                          for row in log["candidates"]]
    records, seen, duplicate_prefix, infeasible_prefix = [], set(), [0], [0]
    record = None
    for q, (mask, score) in enumerate(zip(masks, scores, strict=True), 1):
        require(type(score["profit"]) is int and type(score["feasible"]) is bool, "Malformed retained score")
        duplicate_prefix.append(duplicate_prefix[-1] + int(mask in seen))
        infeasible_prefix.append(infeasible_prefix[-1] + int(not score["feasible"]))
        seen.add(mask)
        if score["feasible"]:
            require(score["profit"] <= reference_optimum, "Feasible journal value exceeds the certified optimum")
            if record is None or score["profit"] > record["profit"]:
                record = {"q": q, "profit": score["profit"], "mask": mask,
                          "phase": "initialization" if q <= mu else "offspring"}
                records.append(record)
    require(record is not None, "No feasible record was retained")
    initial_refs = list(range(mu))
    population_trace = [{"q": mu, "generation": 0, "complete": True,
                         **population_metrics(initial_refs, masks, scores, n)}]
    generation_trace = []
    updates = {"SUCCESS": 0, "STAGNATION": 0, "NO_SIGNAL": 0, "PARTIAL_NO_UPDATE": 0}
    effective_changes = 0
    for number, generation in enumerate(log["generations"], 1):
        require(generation["generation"] == number and
                1 <= generation["start_call"] <= generation["end_call"] <= log["budget"],
                "Generation order or bounds changed")
        start, end = mu + generation["start_call"], mu + generation["end_call"]
        complete = generation["complete"]
        require(type(complete) is bool, "Malformed complete-generation flag")
        event = generation["controller_event"]
        updates[event] = updates.get(event, 0) + 1
        changed = generation["parameters_after"]["tournament_size"] != generation["parameters_before"]["tournament_size"]
        effective_changes += int(changed)
        retained_population = generation["population_after"]
        point = population_metrics(retained_population, masks, scores, n)
        population_trace.append({"q": end, "generation": number, "complete": complete,
                                 "population_committed": complete, **point})
        generation_trace.append({"generation": number, "start_q": start, "end_q": end,
                                 "complete": complete, "evaluated_offspring": end - start + 1,
                                 "requested_offspring": generation["requested_offspring"],
                                 "parent_population_size": generation["actual_parent_mu"],
                                 "parameters_before": deepcopy(generation["parameters_before"]),
                                 "parameters_after": deepcopy(generation["parameters_after"]),
                                 "controller_event": event, "effective_k_change": changed,
                                 "success": generation["success"],
                                 "failed_evaluations_before": generation["failed_queries_before"],
                                 "failed_evaluations_accumulated": generation["failed_queries_accumulated"],
                                 "failed_evaluations_after": generation["failed_queries_after"],
                                 "stagnation_overshoot": generation["stagnation_overshoot"],
                                 "duplicate_offspring": duplicate_prefix[end] - duplicate_prefix[start - 1],
                                 "infeasible_offspring": infeasible_prefix[end] - infeasible_prefix[start - 1],
                                 "population": point})
    observations = []
    event_cursor = generation_cursor = 0
    current_record = None
    population, population_q = initial_refs, mu
    parameters, failed, completed = deepcopy(log["initial_parameters"]), 0, 0
    for q in requested:
        while event_cursor < len(records) and records[event_cursor]["q"] <= q:
            current_record = records[event_cursor]
            event_cursor += 1
        base = {"q": q, "record_profit": current_record["profit"] if current_record else None,
                "record_mask": current_record["mask"] if current_record else None,
                "record_total_q": current_record["q"] if current_record else None,
                "gap_percent": 100 * (reference_optimum - current_record["profit"]) / reference_optimum
                               if current_record else None,
                "duplicate_evaluations": duplicate_prefix[q], "infeasible_evaluations": infeasible_prefix[q]}
        if q < mu:
            observations.append({**base, "phase": "initialization", "initial_evaluations": q,
                                 "offspring_evaluations": 0, "completed_generations": 0,
                                 "completed_population": None, "population_total_q": None,
                                 "population_metrics": None, "partial_initial_references": list(range(q)),
                                 "partial_offspring_references": [], "parameters": None, "failed_evaluations": None})
            continue
        while generation_cursor < len(log["generations"]):
            generation = log["generations"][generation_cursor]
            if not generation["complete"] or mu + generation["end_call"] > q:
                break
            population = list(generation["population_after"])
            population_q = mu + generation["end_call"]
            parameters = deepcopy(generation["parameters_after"])
            failed = generation["failed_queries_after"]
            completed += 1
            generation_cursor += 1
        pending = []
        if generation_cursor < len(log["generations"]):
            generation = log["generations"][generation_cursor]
            last = min(q - mu, generation["end_call"])
            if last >= generation["start_call"]:
                pending = list(range(mu + generation["start_call"] - 1, mu + last))
        observations.append({**base, "phase": "search", "initial_evaluations": mu,
                             "offspring_evaluations": q - mu, "completed_generations": completed,
                             "completed_population": list(population), "population_total_q": population_q,
                             "population_metrics": population_metrics(population, masks, scores, n),
                             "partial_initial_references": [], "partial_offspring_references": pending,
                             "parameters": deepcopy(parameters), "failed_evaluations": failed})
    targets = {}
    for threshold in TARGETS:
        hit = next((event["q"] for event in records if 100 * event["profit"] >= threshold * reference_optimum), None)
        targets[str(threshold)] = {"first_total_evaluation": hit, "attained": hit is not None,
                                   "restricted_T": hit if hit is not None else total_budget,
                                   "restricted_evaluations": hit if hit is not None else total_budget,
                                   "restriction_budget": total_budget}
    return {"schema": "calibrated-selection-observations-v1", "total_evaluations": total_budget,
            "initial_evaluations": mu, "new_evaluations": log["budget"], "optimum": reference_optimum,
            "record_events": records, "checkpoints": observations, "population_trace": population_trace,
            "generation_trace": generation_trace, "targets": targets,
            "final_best_profit": record["profit"],
            "final_gap_percent": 100 * (reference_optimum - record["profit"]) / reference_optimum,
            "controller_activity": {"events": updates, "effective_k_changes": effective_changes},
            "duplicate_evaluations": duplicate_prefix[-1], "infeasible_evaluations": infeasible_prefix[-1],
            "completed_generations": sum(row["complete"] for row in log["generations"]),
            "terminal_partial_offspring": log["summary"]["partial_children"],
            "timing_ns": deepcopy(log["timing_ns"]), "timing_status": "OBSERVATIONAL_NOT_RECONSTRUCTED",
            "search_evaluations_performed": 0, "statistical_inference_performed": False,
            "plots_generated": False}

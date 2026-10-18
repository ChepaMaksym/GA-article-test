"""Independent replay of the explicitly admitted knapsack archive transfer.

No production engine, evaluator, archive or selector is imported.  The archive
reference functions below come from the independent operator verifier, not
from the production operator.  No optimum or locality certificate is used.
"""

from __future__ import annotations

from copy import deepcopy
import json

import numpy as np

from .verifier import (
    _ci_only,
    _expected_event,
    _expected_plan,
    _rebuild_archive,
    _same,
)


_CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
_TOP = {
    "schema", "method", "problem", "initial_masks", "initial_scores",
    "initial_archive", "rng_initial", "budget", "candidates", "generations",
    "summary", "rng_final",
}
_CHILD = {
    "call", "generation", "parent_indices", "parent_masks", "parent_scores",
    "selection_event", "crossover", "pre_mask", "mutation_bits", "mask",
    "weight", "profit", "feasible", "duplicate", "record_profit", "record_call",
}
_GENERATION = {
    "generation", "start_call", "end_call", "complete", "population_before",
    "elite_index", "elite_reference", "p_m", "p_c", "record_before", "record_after",
    "archive_before", "plan", "working_counts", "archive_after_selection",
    "archive_after", "population_after", "rng_before", "rng_after",
}


def _require(condition, message):
    if not condition:
        raise ValueError("Independent knapsack archive verification: " + message)


def _fields(value, names, label):
    _require(type(value) is dict and set(value) == names, label + " fields differ")


def _exact(found, expected, label):
    """Canonical JSON retains integer/Boolean and integer/float distinctions."""
    try:
        left = json.dumps(found, sort_keys=True, separators=(",", ":"), allow_nan=False)
        right = json.dumps(expected, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("Independent knapsack archive verification: invalid JSON " + label) from error
    _require(left == right, label + " differs")


def _problem(raw):
    _fields(raw, {"n", "weights", "profits", "capacity"}, "problem")
    _require(type(raw["n"]) is int and raw["n"] >= 2, "invalid chromosome length")
    _require(type(raw["capacity"]) is int and 0 <= raw["capacity"] <= 200000,
             "invalid or excessive capacity")
    for key in ("weights", "profits"):
        _require(type(raw[key]) is list and len(raw[key]) == raw["n"], key + " length")
        _require(all(type(value) is int and value > 0 for value in raw[key]),
                 key + " must contain positive exact integers")
        _require(sum(raw[key]) <= 200000, key + " exceeds admitted normalization bound")
    return raw


def _score(problem, mask):
    _require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"},
             "invalid binary mask")
    weight = profit = 0
    for position, bit in enumerate(mask):
        if bit == "1":
            weight += problem["weights"][position]
            profit += problem["profits"][position]
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _point(problem, mask, score):
    _require(score["feasible"], "infeasible point sent to reference archive")
    return {
        "id": mask,
        "objectives": [-score["profit"] / sum(problem["profits"]),
                       score["weight"] / max(1, problem["capacity"])],
        "selected": 0,
    }


def _states(generators):
    return {name: deepcopy(generators[name].bit_generator.state) for name in _CHANNELS}


def _restore(raw):
    _fields(raw, set(_CHANNELS), "RNG channels")
    result = {}
    for name in _CHANNELS:
        _require(type(raw[name]) is dict and raw[name].get("bit_generator") == "PCG64",
                 "non-PCG64 state")
        try:
            bit_generator = np.random.PCG64(0)
            bit_generator.state = deepcopy(raw[name])
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            raise ValueError("Independent knapsack archive verification: invalid RNG state") from error
        result[name] = np.random.Generator(bit_generator)
    _exact(_states(result), raw, "lossless state restoration")
    return result


def verify_archive_log(log):
    """Replay every raw score, operator choice, archive update and query count."""
    _ci_only()
    _fields(log, _TOP, "log")
    _exact(log["schema"], "bntga-knapsack-archive-log-v1", "log schema")
    _require(log["method"] in ("unbalanced_gap", "balanced_gap"), "unknown archive profile")
    balanced = log["method"] == "balanced_gap"
    problem = _problem(log["problem"])
    budget = log["budget"]
    _require(type(budget) is int and budget >= 1, "invalid query budget")
    _require(type(log["initial_masks"]) is list and len(log["initial_masks"]) == 30,
             "exactly 30 initial masks required")
    _require(type(log["initial_scores"]) is list and len(log["initial_scores"]) == 30,
             "exactly 30 initial scores required")
    _require(type(log["candidates"]) is list and len(log["candidates"]) == budget,
             "incomplete candidate journal")
    _require(type(log["generations"]) is list and
             len(log["generations"]) == (budget + 28) // 29,
             "incomplete generation journal")

    masks = list(log["initial_masks"])
    scores = [_score(problem, mask) for mask in masks]
    for supplied, score in zip(log["initial_scores"], scores, strict=True):
        _fields(supplied, {"weight", "profit", "feasible"}, "initial score")
        _exact(supplied, score, "raw initial evaluation")
    _require(any(score["feasible"] for score in scores), "no feasible initial solution")
    archive = _rebuild_archive([
        _point(problem, mask, score)
        for mask, score in zip(masks, scores, strict=True) if score["feasible"]
    ])
    _same(log["initial_archive"], archive, "initial normalized archive")
    known_scores = {mask: score for mask, score in zip(masks, scores, strict=True)}
    seen = set(masks)
    population = list(range(30))
    record_mask = record_profit = record_call = None
    for mask, score in zip(masks, scores, strict=True):
        if score["feasible"] and (record_profit is None or score["profit"] > record_profit):
            record_mask, record_profit, record_call = mask, score["profit"], 0
    generators = _restore(log["rng_initial"])
    calls = duplicates = infeasible = complete_generations = partial_children = 0

    for number, generation in enumerate(log["generations"], 1):
        _fields(generation, _GENERATION, "generation")
        child_count = min(29, budget - calls)
        complete = child_count == 29
        _exact(generation["generation"], number, "generation index")
        _exact(generation["start_call"], calls + 1, "generation first query")
        _exact(generation["end_call"], calls + child_count, "generation last query")
        _exact(generation["complete"], complete, "generation completeness")
        _exact(generation["population_before"], population, "population before")
        _exact(generation["rng_before"], _states(generators), "RNG before generation")
        _same(generation["archive_before"], archive, "archive before generation")
        _exact(generation["p_m"], 1 / problem["n"], "fixed mutation probability")
        _exact(generation["p_c"], 0.9, "fixed crossover probability")
        _exact(generation["record_before"], record_profit, "record before generation")

        order = [
            (1, scores[reference]["profit"]) if scores[reference]["feasible"]
            else (0, problem["capacity"] - scores[reference]["weight"])
            for reference in population
        ]
        elite_options = [index for index, value in enumerate(order) if value == max(order)]
        elite_index = (elite_options[0] if len(elite_options) == 1
                       else elite_options[int(generators["ties"].integers(len(elite_options)))])
        elite_reference = population[elite_index]
        _exact(generation["elite_index"], elite_index, "elite index")
        _exact(generation["elite_reference"], elite_reference, "elite reference")
        dimension = int(generators["selection"].integers(2)) if len(archive) > 1 else None
        plan = _expected_plan(archive, dimension, balanced)
        _same(generation["plan"], plan, "frozen plan")
        counts = {point["id"]: point["selected"] for point in archive}
        child_references = []
        new_points = []

        for _ in range(child_count):
            child = log["candidates"][calls]
            _fields(child, _CHILD, "candidate")
            draws, side = [], None
            if len(archive) > 1:
                draws = [int(generators["selection"].integers(len(archive)))
                         for _draw in range(2)]
                first = draws[0]
                if plan["priorities"][draws[1]] > plan["priorities"][first]:
                    first = draws[1]
                if first not in (0, len(archive) - 1):
                    side = int(generators["selection"].integers(2))
            event = _expected_event(plan, counts, draws, side)
            counts = event["counts_after"]
            parents = [event["first_id"], event["second_id"]]
            parent_scores = [known_scores[mask] for mask in parents]
            crosses = bool(generators["branch"].random() < 0.9)
            if crosses:
                choose_first = generators["crossover"].random(problem["n"]) < 0.5
                pre_mask = "".join(parents[0][i] if choose_first[i] else parents[1][i]
                                   for i in range(problem["n"]))
            else:
                pre_mask = parents[0]
            changed = generators["mutation"].random(problem["n"]) < 1 / problem["n"]
            mutation_bits = [i for i, flag in enumerate(changed) if flag]
            mask = "".join(("0" if bit == "1" else "1") if changed[i] else bit
                           for i, bit in enumerate(pre_mask))
            score = _score(problem, mask)
            duplicate = mask in seen
            seen.add(mask)
            duplicates += int(duplicate)
            infeasible += int(not score["feasible"])
            calls += 1
            if score["feasible"] and (record_profit is None or score["profit"] > record_profit):
                record_mask, record_profit, record_call = mask, score["profit"], calls
            expected = {
                "call": calls, "generation": number,
                "parent_indices": [event["first_index"], event["second_index"]],
                "parent_masks": parents, "parent_scores": parent_scores,
                "selection_event": event, "crossover": crosses, "pre_mask": pre_mask,
                "mutation_bits": mutation_bits, "mask": mask, **score,
                "duplicate": duplicate, "record_profit": record_profit, "record_call": record_call,
            }
            _same(child["selection_event"], event, "candidate selection event")
            _exact({key: value for key, value in child.items() if key != "selection_event"},
                   {key: value for key, value in expected.items() if key != "selection_event"},
                   f"candidate raw operators at query {calls}")
            child_references.append(len(masks))
            masks.append(mask)
            scores.append(score)
            known_scores[mask] = score
            if score["feasible"]:
                new_points.append(_point(problem, mask, score))

        temporary_archive = [{**point, "selected": counts[point["id"]]} for point in archive]
        _same(generation["working_counts"], counts, "working counters")
        _same(generation["archive_after_selection"], temporary_archive, "temporary archive counters")
        _exact(generation["record_after"], record_profit, "record after generation")
        if complete:
            population = [elite_reference, *child_references]
            archive = _rebuild_archive(new_points, temporary_archive)
            complete_generations += 1
        else:
            partial_children = child_count
        _same(generation["archive_after"], archive, "committed archive including terminal prefix rule")
        _exact(generation["population_after"], population, "committed population")
        _exact(generation["rng_after"], _states(generators), "RNG after generation")

    summary = {
        "new_calls": budget, "physical_evaluations": budget,
        "known_score_validation_evaluations": 30, "duplicate_calls": duplicates,
        "infeasible_calls": infeasible, "full_generations": complete_generations,
        "partial_children": partial_children, "best_mask": record_mask,
        "best_profit": record_profit, "best_call": record_call,
        "final_population": population, "final_archive": archive,
        "archive_size": len(archive), "final_mutation_probability": 1 / problem["n"],
    }
    _same(log["summary"], summary, "independent final summary")
    _exact(log["rng_final"], _states(generators), "final RNG state")
    return {
        "verification_status": "VERIFIED", "new_calls": calls,
        "independent_score_checks": 30 + calls,
        "completed_generations": complete_generations,
        "partial_generations": int(partial_children > 0),
        "archive_size": len(archive), "summary": summary,
    }


def verify_log(log):
    """Verify a transfer log or delegate only an unchanged classical fixed log."""
    _ci_only()
    _require(type(log) is dict, "log must be a dictionary")
    if log.get("schema") == "bntga-knapsack-archive-log-v1":
        return verify_archive_log(log)
    _require(log.get("schema") == "ga-adaptive-mutation-only-log-v1" and
             log.get("method") == "fixed", "unsupported classical log or adaptive profile")
    _problem(log.get("problem"))
    from studies.adaptive_parameters.mutation_only.verifier import verify_log as verify_classical

    receipt = verify_classical(log)
    _require(any(score["feasible"] for score in log["initial_scores"]),
             "classical transfer control also requires a feasible initial solution")
    return receipt

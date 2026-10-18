"""CI-only, B-NTGA-inspired auxiliary-archive transfer for binary knapsack.

Only parent selection uses the two-dimensional feasible archive.  The final
target remains maximum feasible profit.  This is not the complete author GA
or a numerical replication of the article.  The caller supplies the unchanged
mutation_only.engine.make_rngs streams; no optimum or certificate is accepted.
"""

from __future__ import annotations

from copy import deepcopy
import os

import numpy as np

from studies.adaptive_parameters.mutation_only.engine import CHANNELS

from .operator import freeze_selection, select_pair, update_archive


SCHEMA = "bntga-knapsack-archive-log-v1"
MU = 30
PC = 0.9
RESOURCE_BOUND = 200000


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, name, minimum=0):
    _require(type(value) is int and value >= minimum,
             f"{name} must be an integer >= {minimum}")


def _problem(problem):
    _require(isinstance(problem, dict) and
             set(problem) == {"n", "weights", "profits", "capacity"},
             "Only n, weights, profits and capacity are accepted; oracle metadata is forbidden")
    _integer(problem["n"], "n", 2)
    _integer(problem["capacity"], "capacity")
    _require(problem["capacity"] <= RESOURCE_BOUND, "Capacity exceeds the transfer resource bound")
    for name in ("weights", "profits"):
        values = problem[name]
        _require(isinstance(values, (list, tuple)) and len(values) == problem["n"],
                 f"{name} must contain exactly n positive integers")
        for value in values:
            _integer(value, name, 1)
        _require(sum(values) <= RESOURCE_BOUND, f"Sum of {name} exceeds the transfer resource bound")


def _mask(mask, n):
    _require(isinstance(mask, str) and len(mask) == n and not set(mask) - {"0", "1"},
             "Mask must be an n-bit binary string")


def _score(problem, mask):
    # Every search query calls this function, including duplicate masks.
    weight = sum(value for value, bit in zip(problem["weights"], mask) if bit == "1")
    profit = sum(value for value, bit in zip(problem["profits"], mask) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _known_score(value):
    _require(isinstance(value, dict) and set(value) == {"weight", "profit", "feasible"},
             "Known scores must contain only weight, profit and feasible")
    _integer(value["weight"], "known weight")
    _integer(value["profit"], "known profit")
    _require(type(value["feasible"]) is bool, "Known feasibility must be bool")


def _quality(score, capacity):
    return (1, score["profit"]) if score["feasible"] else (0, capacity - score["weight"])


def _states(rngs):
    return {name: deepcopy(rngs[name].bit_generator.state) for name in CHANNELS}


def _point(problem, mask, score):
    _require(score["feasible"], "Only feasible known points enter the auxiliary archive")
    return {
        "id": mask,
        "objectives": [-score["profit"] / sum(problem["profits"]),
                       score["weight"] / max(1, problem["capacity"])],
        "selected": 0,
    }


def _rngs(rngs):
    _require(isinstance(rngs, dict) and set(rngs) == set(CHANNELS),
             "Exactly six named RNG channels are required")
    _require(all(isinstance(rngs[name], np.random.Generator) and
                 isinstance(rngs[name].bit_generator, np.random.PCG64) for name in CHANNELS),
             "All channels must be PCG64 generators")
    _require(len({id(rngs[name]) for name in CHANNELS}) == len(CHANNELS) and
             len({id(rngs[name].bit_generator) for name in CHANNELS}) == len(CHANNELS),
             "RNG channels may not alias")


def _pair(plan, counts, selection_rng):
    if len(plan["archive"]) == 1:
        return select_pair(plan, counts, [], None)
    draws = [int(selection_rng.integers(len(plan["archive"]))) for _ in range(2)]
    # The first tournament draw wins a priority tie.  Determine whether the
    # source's conditional neighbor draw is required before consuming it.
    winner = draws[0]
    if plan["priorities"][draws[1]] > plan["priorities"][winner]:
        winner = draws[1]
    side = None
    if 0 < winner < len(plan["archive"]) - 1:
        side = int(selection_rng.integers(2))
    return select_pair(plan, counts, draws, side)


def run_archive_search(problem, initial_masks, initial_scores, balanced, rngs, budget=5000):
    """Execute exactly budget new evaluations, with evaluator-free selection.

    Known initial scores are independently recomputed and counted separately.
    A full generation commits counters and all feasible children to the
    archive, and commits elite + 29 children to the population.  A terminal
    incomplete generation commits neither, while retaining every evaluated
    candidate, working counter and record in the journal.
    """
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "Search execution is CI-only")
    _problem(problem)
    _integer(budget, "budget", 1)
    _require(type(balanced) is bool, "balanced must be bool")
    _require(isinstance(initial_masks, list) and isinstance(initial_scores, list) and
             len(initial_masks) == len(initial_scores) == MU,
             "Exactly 30 known initial masks and scores are required")
    _rngs(rngs)
    n, capacity = problem["n"], problem["capacity"]
    masks, scores = list(initial_masks), []
    # This mapping is only metadata for already evaluated archive parents.
    # It never answers a search query: every child is scored again below.
    known_by_mask = {}
    for mask, known in zip(masks, initial_scores):
        _mask(mask, n)
        _known_score(known)
        actual = _score(problem, mask)
        _require(actual == known, "Known initial score disagrees with the exact mask")
        scores.append(actual)
        known_by_mask[mask] = deepcopy(actual)
    _require(any(score["feasible"] for score in scores),
             "At least one feasible initial mask is required; no hidden restart is allowed")
    archive = update_archive([
        _point(problem, mask, score)
        for mask, score in zip(masks, scores) if score["feasible"]
    ])
    canonical_problem = {"n": n, "weights": list(problem["weights"]),
                         "profits": list(problem["profits"]), "capacity": capacity}
    method = "balanced_gap" if balanced else "unbalanced_gap"
    log = {
        "schema": SCHEMA, "method": method, "problem": canonical_problem,
        "initial_masks": list(masks), "initial_scores": deepcopy(scores),
        "initial_archive": deepcopy(archive), "rng_initial": _states(rngs),
        "budget": budget, "candidates": [], "generations": [],
        "summary": None, "rng_final": None,
    }
    population = list(range(MU))
    seen = set(masks)
    best_mask = best_profit = best_call = None
    for mask, score in zip(masks, scores):
        if score["feasible"] and (best_profit is None or score["profit"] > best_profit):
            best_mask, best_profit, best_call = mask, score["profit"], 0
    calls = full_generations = partial_children = duplicate_calls = infeasible_calls = 0
    probability = 1 / n
    while calls < budget:
        generation = len(log["generations"]) + 1
        before = list(population)
        archive_before = deepcopy(archive)
        rng_before = _states(rngs)
        record_before = best_profit
        keys = [_quality(scores[reference], capacity) for reference in before]
        best_key = max(keys)
        elite_ties = [index for index, key in enumerate(keys) if key == best_key]
        elite_index = (elite_ties[0] if len(elite_ties) == 1
                       else elite_ties[int(rngs["ties"].integers(len(elite_ties)))])
        elite_reference = before[elite_index]
        dimension = int(rngs["selection"].integers(2)) if len(archive) > 1 else None
        plan = freeze_selection(archive, dimension, balanced)
        working_counts = {point["id"]: point["selected"] for point in archive}
        child_references = []
        start_call = calls + 1
        for _ in range(min(MU - 1, budget - calls)):
            event = _pair(plan, working_counts, rngs["selection"])
            working_counts = dict(event["counts_after"])
            a, b = event["first_id"], event["second_id"]
            parent_scores = [deepcopy(known_by_mask[a]), deepcopy(known_by_mask[b])]
            has_crossover = bool(rngs["branch"].random() < PC)
            if has_crossover:
                choices = rngs["crossover"].random(n) < 0.5
                pre = "".join(a[index] if choices[index] else b[index] for index in range(n))
            else:
                pre = a
            mutation_bits = [index for index, changed in
                             enumerate(rngs["mutation"].random(n) < probability) if changed]
            bits = list(pre)
            for index in mutation_bits:
                bits[index] = "0" if bits[index] == "1" else "1"
            mask = "".join(bits)
            score = _score(problem, mask)
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
            known_by_mask[mask] = deepcopy(score)
            child_references.append(reference)
            log["candidates"].append({
                "call": calls, "generation": generation,
                "parent_indices": [event["first_index"], event["second_index"]],
                "parent_masks": [a, b], "parent_scores": parent_scores,
                "selection_event": event, "crossover": has_crossover,
                "pre_mask": pre, "mutation_bits": mutation_bits, "mask": mask,
                **score, "duplicate": duplicate,
                "record_profit": best_profit, "record_call": best_call,
            })
        complete = len(child_references) == MU - 1
        after_selection = deepcopy(archive_before)
        for point in after_selection:
            point["selected"] = working_counts[point["id"]]
        if complete:
            population = [elite_reference] + child_references
            archive = update_archive([
                _point(problem, masks[reference], scores[reference])
                for reference in child_references if scores[reference]["feasible"]
            ], existing=after_selection)
            full_generations += 1
        else:
            partial_children = len(child_references)
        log["generations"].append({
            "generation": generation, "start_call": start_call, "end_call": calls,
            "complete": complete, "population_before": before,
            "elite_index": elite_index, "elite_reference": elite_reference,
            "p_m": probability, "p_c": PC,
            "record_before": record_before, "record_after": best_profit,
            "archive_before": archive_before, "plan": plan,
            "working_counts": dict(working_counts),
            "archive_after_selection": after_selection,
            "archive_after": deepcopy(archive),
            "population_after": list(population),
            "rng_before": rng_before, "rng_after": _states(rngs),
        })
    log["summary"] = {
        "new_calls": calls, "physical_evaluations": calls,
        "known_score_validation_evaluations": MU,
        "duplicate_calls": duplicate_calls, "infeasible_calls": infeasible_calls,
        "full_generations": full_generations, "partial_children": partial_children,
        "best_mask": best_mask, "best_profit": best_profit, "best_call": best_call,
        "final_population": list(population), "final_archive": deepcopy(archive),
        "archive_size": len(archive), "final_mutation_probability": probability,
    }
    log["rng_final"] = _states(rngs)
    return log

"""Post-search observations, reconstructed without production scoring functions.

Exact optima and N2 diagnostics belong here, never in the search interface.
The input journal must also pass the independent operator/RNG replay in
search.run_profile.  This module independently recomputes its masks and records.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import combinations
import os


def _require(condition, message):
    if not condition:
        raise ValueError("Invalid post-search observation: " + message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "GitHub Actions is required")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test",
             "Wrong repository")
    _require(os.environ.get("GITHUB_REF") ==
             "refs/heads/research/masters-ga-diversity-crossover", "Wrong branch")


def _problem(problem):
    _require(type(problem) is dict and set(problem) == {"n", "weights", "profits", "capacity"},
             "Problem contains unknown or oracle fields")
    _require(type(problem["n"]) is int and problem["n"] >= 2, "Invalid dimension")
    _require(type(problem["capacity"]) is int and problem["capacity"] >= 0,
             "Invalid capacity")
    for field in ("weights", "profits"):
        _require(isinstance(problem[field], (list, tuple)) and
                 len(problem[field]) == problem["n"] and
                 all(type(value) is int and value > 0 for value in problem[field]),
                 "Invalid " + field)


def _score(problem, mask):
    _require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"},
             "Invalid binary mask")
    weight = profit = 0
    for position in range(problem["n"]):
        if mask[position] == "1":
            weight += problem["weights"][position]
            profit += problem["profits"][position]
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _key(score, capacity):
    return (1, score["profit"]) if score["feasible"] else (0, capacity - score["weight"])


def _fraction(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def _population_metrics(problem, masks, scores, references, call, generation):
    selected_masks = [masks[reference] for reference in references]
    selected_scores = [scores[reference] for reference in references]
    mu = len(references)
    feasible = [score["profit"] for score in selected_scores if score["feasible"]]
    # Each differing unordered pair contributes once at its differing bit.
    # Duplicate genotype positions remain separate population members.
    distance_sum = 0
    for position in range(problem["n"]):
        ones = sum(mask[position] == "1" for mask in selected_masks)
        distance_sum += ones * (mu - ones)
    return {"call": call, "generation": generation, "mu": mu,
            "feasible_count": len(feasible), "feasible_fraction": len(feasible) / mu,
            "feasible_mean": _fraction(sum(feasible), len(feasible)),
            "unique_genotypes": len(set(selected_masks)),
            "normalized_hamming": _fraction(distance_sum, problem["n"] * mu * (mu - 1) // 2),
            "population_best_profit": max(feasible) if feasible else None}


def summarize_log(log, external_optimum, checkpoints=(0, 1000, 2500, 5000),
                  reference_profit=None):
    """Observe all evaluated candidates, including an unfinished final generation.

    ``reference_profit`` defaults to the best known initial feasible value.
    Supplying the certified center profit after a cloned run is also supported.
    Checkpoints outside a small CI fixture's budget are omitted, not extrapolated.
    """
    _ci_only()
    _require(type(log) is dict, "Journal must be a dictionary")
    problem = log["problem"]
    _problem(problem)
    _require(type(external_optimum) is int and external_optimum > 0, "Invalid external optimum")
    budget = log["budget"]
    _require(type(budget) is int and budget > 0 and len(log["candidates"]) == budget,
             "Incomplete candidate journal")
    _require(log["method"] in ("fixed", "adaptive_mutation"), "Unimplemented profile")
    _require(len(log["initial_masks"]) == len(log["initial_scores"]) == 30,
             "Exactly 30 initial positions required")
    _require(all(type(point) is int and point >= 0 for point in checkpoints), "Invalid checkpoint")
    observed_points = sorted({0, budget, *(point for point in checkpoints if point <= budget)})

    masks = list(log["initial_masks"])
    scores = [_score(problem, mask) for mask in masks]
    for supplied, expected in zip(log["initial_scores"], scores, strict=True):
        _require(type(supplied) is dict and set(supplied) == set(expected) and
                 all(type(supplied[name]) is type(value) and supplied[name] == value
                     for name, value in expected.items()), "Initial scores differ")
    best_mask = best_profit = best_call = None
    for mask, score in zip(masks, scores, strict=True):
        if score["feasible"] and (best_profit is None or score["profit"] > best_profit):
            best_mask, best_profit, best_call = mask, score["profit"], 0
    initial_profit = best_profit
    if reference_profit is None:
        reference_profit = initial_profit
    _require(reference_profit is None or
             type(reference_profit) is int and 0 <= reference_profit <= external_optimum,
             "Invalid post-search reference profit")

    def record(call):
        _require(best_profit is None or best_profit <= external_optimum,
                 "Feasible record exceeds external exact optimum")
        return {"call": call, "mask": best_mask, "profit": best_profit,
                "gap": None if best_profit is None else
                (external_optimum - best_profit) / external_optimum,
                "last_improvement_call": best_call}

    record_trace = [record(0)]
    targets = {str(target): {"reached": False, "first_call": None} for target in (95, 99, 100)}

    def update_targets(call):
        if best_profit is not None:
            for target, result in targets.items():
                if not result["reached"] and 100 * best_profit >= int(target) * external_optimum:
                    result.update({"reached": True, "first_call": call})

    update_targets(0)
    candidate_trace = []
    first_escape = None
    seen = set(masks)
    duplicates = infeasible = 0
    strict_success_calls = []
    for call, child in enumerate(log["candidates"], 1):
        _require(type(child.get("call")) is int and child["call"] == call,
                 "Nonconsecutive candidate calls")
        score = _score(problem, child["mask"])
        _require(all(type(child.get(name)) is type(value) and child[name] == value
                     for name, value in score.items()), "Candidate score mismatch")
        duplicate = child["mask"] in seen
        _require(type(child["duplicate"]) is bool and child["duplicate"] == duplicate,
                 "Duplicate accounting mismatch")
        seen.add(child["mask"])
        duplicates += int(duplicate)
        infeasible += int(not score["feasible"])
        if score["feasible"] and (best_profit is None or score["profit"] > best_profit):
            best_mask, best_profit, best_call = child["mask"], score["profit"], call
            strict_success_calls.append(call)
        if first_escape is None and score["feasible"] and (
                reference_profit is None or score["profit"] > reference_profit):
            first_escape = call
        _require(child["record_profit"] == best_profit and child["record_call"] == best_call,
                 "Recorded best state differs from independent reconstruction")
        masks.append(child["mask"])
        scores.append(score)
        candidate_trace.append({"call": call, "generation": child["generation"],
                                "mask": child["mask"], **score, "duplicate": duplicate,
                                "crossover": child["crossover"],
                                "mutation_count": len(child["mutation_bits"])})
        record_trace.append(record(call))
        update_targets(call)
    _require(log["summary"]["best_mask"] == best_mask and
             log["summary"]["best_profit"] == best_profit and
             log["summary"]["best_call"] == best_call, "Final record mismatch")
    _require(log["summary"]["new_calls"] == budget and
             log["summary"]["duplicate_calls"] == duplicates and
             log["summary"]["infeasible_calls"] == infeasible, "Final accounting mismatch")

    references = list(range(30))
    population_trace = [_population_metrics(problem, masks, scores, references, 0, 0)]
    mutation_trace = []
    previous_end = 0
    partial_evaluations = full_generations = 0
    for index, event in enumerate(log["generations"], 1):
        start, end = event["start_call"], event["end_call"]
        _require(event["generation"] == index and start == previous_end + 1 and
                 type(end) is int and start <= end <= budget, "Invalid generation intervals")
        _require(event["population_before"] == references, "Population reconstruction mismatch")
        child_count = end - start + 1
        complete = child_count == 29
        _require(1 <= child_count <= 29 and event["complete"] is complete and
                 (complete or end == budget), "Invalid partial generation")
        _require(all(child["generation"] == index
                     for child in log["candidates"][start - 1:end]),
                 "Candidate belongs to a different generation")
        elite = event["elite_index"]
        _require(type(elite) is int and 0 <= elite < 30, "Invalid elite position")
        keys = [_key(scores[reference], problem["capacity"]) for reference in references]
        _require(keys[elite] == max(keys), "Elite is not population-best")
        if complete:
            references = [references[elite], *range(30 + start - 1, 30 + end)]
            full_generations += 1
            population_trace.append(_population_metrics(problem, masks, scores, references, end, index))
        else:
            partial_evaluations = child_count
        _require(event["population_after"] == references, "Wrong population update")
        mutation_trace.append({"generation": index, "start_call": start, "end_call": end,
                               "complete": complete, "p_m": event["p_m"],
                               "p_m_next": event["p_m_next"],
                               "event": event["controller_event"],
                               "stagnation_before": event["stagnation_before"],
                               "stagnation_after": event["stagnation_after"],
                               "record_before": event["record_before"],
                               "record_after": event["record_after"]})
        previous_end = end
    _require(previous_end == budget and log["summary"]["final_population"] == references,
             "Incomplete final population reconstruction")

    snapshots = []
    cursor = 0
    for point in observed_points:
        while cursor + 1 < len(population_trace) and population_trace[cursor + 1]["call"] <= point:
            cursor += 1
        state = record_trace[point]
        last = state["last_improvement_call"]
        snapshots.append({"call": point, "record": deepcopy(state),
                          "population": deepcopy(population_trace[cursor]),
                          "last_strict_improvement_call": last,
                          "stagnant_1000": point >= 1000 and
                          (last is None or point - last >= 1000)})
    accounting = {"new_search_evaluations": budget,
                  "known_initial_positions": 30,
                  "independent_candidate_and_initial_scores": budget + 30,
                  "duplicate_queries": duplicates, "infeasible_queries": infeasible,
                  "full_generations": full_generations,
                  "partial_generation_evaluations": partial_evaluations,
                  "n2_diagnostic_evaluations": 0}
    return {"schema": "mutation-population-observations-v1", "method": log["method"],
            "budget": budget, "external_optimum": external_optimum,
            "reference_profit": reference_profit, "initial_record": record_trace[0],
            "final_record": record_trace[-1], "first_escape": first_escape,
            "first_escape_call": first_escape, "first_improvement_call": first_escape,
            "capped_calls": first_escape if first_escape is not None else budget,
            "escaped": first_escape is not None,
            "targets": targets, "attainment": deepcopy(targets),
            "candidate_trace": candidate_trace, "record_trace": record_trace,
            "population_trace": population_trace,
            "full_generation_metrics": deepcopy(population_trace),
            "mutation_trace": mutation_trace, "checkpoints": snapshots,
            "snapshots": deepcopy(snapshots), "strict_success_calls": strict_success_calls,
            "accounting": accounting}


def certify_n2(problem, mask, external_optimum=None):
    """Independently score a feasible center and every one/two-bit neighbor.

    This returns evidence, not a search signal.  The caller may deduplicate
    repeated observed masks before requesting certificates, but no neighbor
    evaluation is copied from the search journal or a local-ascent cache.
    """
    _ci_only()
    _problem(problem)
    center = {"mask": mask, **_score(problem, mask)}
    _require(center["feasible"], "An infeasible mask cannot be a feasible local maximum")
    _require(external_optimum is None or type(external_optimum) is int and
             external_optimum >= center["profit"], "Invalid external optimum")
    neighbors = []
    better = equal = infeasible = 0
    for radius in (1, 2):
        for changed in combinations(range(problem["n"]), radius):
            bits = list(mask)
            for index in changed:
                bits[index] = "0" if bits[index] == "1" else "1"
            neighbor_mask = "".join(bits)
            score = _score(problem, neighbor_mask)
            if score["feasible"]:
                _require(external_optimum is None or score["profit"] <= external_optimum,
                         "Neighbor exceeds exact external optimum")
                better += int(score["profit"] > center["profit"])
                equal += int(score["profit"] == center["profit"])
            else:
                infeasible += 1
            neighbors.append({"flipped_bits": list(changed), "mask": neighbor_mask, **score,
                              "infeasibility_reason": None if score["feasible"] else
                              "CAPACITY_EXCEEDED"})
    expected_count = problem["n"] + problem["n"] * (problem["n"] - 1) // 2
    _require(len(neighbors) == expected_count and
             len({row["mask"] for row in neighbors}) == expected_count,
             "Incomplete or duplicate N2 neighborhood")
    locality = ("N2_NOT_LOCAL" if better else "N2_PLATEAU" if equal else "N2_STRICT_LOCAL")
    global_status = ("UNKNOWN" if external_optimum is None else
                     "GLOBAL" if center["profit"] == external_optimum else "NONGLOBAL")
    return {"schema": "mutation-population-n2-certificate-v1", "n": problem["n"],
            "center": center, "neighbors": neighbors, "neighbor_count": len(neighbors),
            "better_feasible_count": better, "equal_feasible_count": equal,
            "infeasible_count": infeasible, "locality": locality,
            "global_status": global_status, "external_optimum": external_optimum,
            "nonglobal_local": better == 0 and global_status == "NONGLOBAL",
            "independent_evaluations": 1 + len(neighbors)}

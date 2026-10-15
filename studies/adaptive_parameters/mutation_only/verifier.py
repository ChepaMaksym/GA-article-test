"""Independent replay of mutation-only journals; no production engine imports.

This validates semantics, RNG consumption, and accounting, not transport identity.
The CI driver must separately bind the implementation and inputs to their hashes.
"""
from __future__ import annotations

import copy
import json
import os

import numpy as np


SCHEMA = "ga-adaptive-mutation-only-log-v1"
CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
MU = 30
TOP_FIELDS = {
    "schema", "method", "problem", "initial_masks", "initial_scores", "rng_initial",
    "budget", "candidates", "generations", "summary", "rng_final",
}
GEN_FIELDS = {
    "generation", "start_call", "end_call", "complete", "population_before",
    "elite_index", "p_m", "stagnation_before", "record_before", "record_after",
    "p_m_next", "stagnation_after", "controller_event", "population_after",
    "rng_before", "rng_after",
}
CHILD_FIELDS = {
    "call", "generation", "tournaments", "parent_indices", "crossover", "pre_mask",
    "mutation_bits", "mask", "weight", "profit", "feasible", "duplicate",
    "record_profit", "record_call",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("Invalid mutation-only journal: " + message)


def _ci_only() -> None:
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "GitHub Actions is required")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test", "wrong repository")
    _require(os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover",
             "wrong branch")


def _same(actual, expected, label: str) -> None:
    """Canonical JSON comparison also distinguishes Boolean and integer fields."""
    try:
        actual_json = json.dumps(actual, sort_keys=True, separators=(",", ":"), allow_nan=False)
        expected_json = json.dumps(expected, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid mutation-only journal: non-JSON " + label) from exc
    _require(actual_json == expected_json, label)


def _fields(value, expected: set[str], label: str) -> None:
    _require(type(value) is dict and set(value) == expected, label + " fields")


def _integer(value, minimum: int, label: str) -> None:
    _require(type(value) is int and value >= minimum, label)


def _problem(value: dict) -> dict:
    _fields(value, {"n", "weights", "profits", "capacity"}, "problem")
    _integer(value["n"], 2, "chromosome length")
    _integer(value["capacity"], 0, "capacity")
    for field in ("weights", "profits"):
        _require(type(value[field]) is list and len(value[field]) == value["n"], field + " length")
        for entry in value[field]:
            _integer(entry, 1, field + " entry")
    return value


def _score(problem: dict, mask: str) -> dict:
    _require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"},
             "binary mask")
    weight = profit = 0
    for i, bit in enumerate(mask):
        if bit == "1":
            weight += problem["weights"][i]
            profit += problem["profits"][i]
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _key(score: dict, capacity: int) -> tuple[int, int]:
    return (1, score["profit"]) if score["feasible"] else (0, capacity - score["weight"])


def _states(rngs: dict) -> dict:
    return {name: copy.deepcopy(rngs[name].bit_generator.state) for name in CHANNELS}


def _restore(value: dict) -> dict:
    _fields(value, set(CHANNELS), "RNG channels")
    restored = {}
    for name in CHANNELS:
        state = value[name]
        _require(type(state) is dict and state.get("bit_generator") == "PCG64", "PCG64 state")
        try:
            bit_generator = np.random.PCG64(0)
            bit_generator.state = copy.deepcopy(state)
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            raise ValueError("Invalid mutation-only journal: RNG state " + name) from exc
        restored[name] = np.random.Generator(bit_generator)
    _same(_states(restored), value, "lossless RNG restoration")
    return restored


def _choose(options: list[int], rng: np.random.Generator) -> int:
    # A unique winner consumes no tie RNG; duplicate tournament positions are
    # deliberately retained, and an equal pair therefore consumes a tie draw.
    return options[0] if len(options) == 1 else options[int(rng.integers(len(options)))]


def _feedback(n: int, probability: float, stagnant: int, success: bool, method: str):
    """An independent transcription of the registered rule, not engine.update_mutation."""
    lower, upper = 1 / n, min(8 / n, 0.5)
    if method == "fixed":
        return lower, 0, "FIXED"
    if success:
        return max(lower, probability / 2), 0, "SUCCESS_HALVE"
    if stagnant == 4:
        return min(upper, probability * 2), 0, "STAGNATION_DOUBLE"
    return probability, stagnant + 1, "NO_CHANGE"


def verify_log(log: dict) -> dict:
    """Replay a complete journal, raising ValueError on any semantic mismatch.

    Small positive budgets are supported for CI fixtures. Registered pilot
    completeness (5000 calls, named tasks/seeds and source SHA) belongs to the
    driver's outer contract and is not inferred from this self-contained log.
    """
    _ci_only()
    _fields(log, TOP_FIELDS, "top-level")
    _same(log["schema"], SCHEMA, "schema")
    method = log["method"]
    _require(type(method) is str and method in ("fixed", "adaptive_mutation"), "method")
    problem = _problem(log["problem"])
    budget = log["budget"]
    _integer(budget, 1, "budget")
    _require(type(log["initial_masks"]) is list and len(log["initial_masks"]) == MU, "30 initial masks")
    _require(type(log["initial_scores"]) is list and len(log["initial_scores"]) == MU, "30 initial scores")
    _require(type(log["candidates"]) is list and len(log["candidates"]) == budget,
             "candidate completeness")
    _require(type(log["generations"]) is list and len(log["generations"]) == (budget + MU - 2) // (MU - 1),
             "generation completeness")

    masks = list(log["initial_masks"])
    scores = [_score(problem, mask) for mask in masks]
    for supplied, score in zip(log["initial_scores"], scores, strict=True):
        _fields(supplied, {"weight", "profit", "feasible"}, "initial score")
        _same(supplied, score, "independent initial evaluation")
    population = list(range(MU))
    seen = set(masks)
    record_mask = record_profit = record_call = None
    for mask, score in zip(masks, scores, strict=True):
        if score["feasible"] and (record_profit is None or score["profit"] > record_profit):
            record_mask, record_profit, record_call = mask, score["profit"], 0

    rngs = _restore(log["rng_initial"])
    probability, stagnant = 1 / problem["n"], 0
    calls = duplicates = infeasible = full_generations = partial_children = 0
    for generation_number, event in enumerate(log["generations"], 1):
        _fields(event, GEN_FIELDS, "generation")
        child_count = min(MU - 1, budget - calls)
        complete = child_count == MU - 1
        _same(event["generation"], generation_number, "generation number")
        _same(event["start_call"], calls + 1, "generation start call")
        _same(event["end_call"], calls + child_count, "generation end call")
        _same(event["complete"], complete, "generation completeness flag")
        _same(event["population_before"], population, "population before")
        _same(event["p_m"], probability, "generation mutation probability")
        _same(event["stagnation_before"], stagnant, "generation counter before")
        _same(event["record_before"], record_profit, "record frozen before children")
        _same(event["rng_before"], _states(rngs), "RNG before elite selection")
        record_before = record_profit

        keys = [_key(scores[ref], problem["capacity"]) for ref in population]
        best_key = max(keys)
        elite_index = _choose([i for i, key in enumerate(keys) if key == best_key], rngs["ties"])
        _same(event["elite_index"], elite_index, "elite tournament tie resolution")
        child_refs = []
        for _ in range(child_count):
            child = log["candidates"][calls]
            _fields(child, CHILD_FIELDS, "candidate")
            tournaments, parents = [], []
            for _parent in range(2):
                positions = [int(rngs["selection"].integers(MU)), int(rngs["selection"].integers(MU))]
                tournaments.append(positions)
                winning_key = max(keys[position] for position in positions)
                parents.append(_choose([position for position in positions if keys[position] == winning_key],
                                       rngs["ties"]))
            crosses = bool(rngs["branch"].random() < 0.9)
            first, second = masks[population[parents[0]]], masks[population[parents[1]]]
            if crosses:
                choices = rngs["crossover"].random(problem["n"]) < 0.5
                pre_mask = "".join(first[i] if choices[i] else second[i] for i in range(problem["n"]))
            else:
                pre_mask = first
            flags = rngs["mutation"].random(problem["n"]) < probability
            mutation_bits = [i for i, changed in enumerate(flags) if changed]
            result = "".join(("0" if bit == "1" else "1") if flags[i] else bit
                             for i, bit in enumerate(pre_mask))
            score = _score(problem, result)
            duplicate = result in seen
            seen.add(result)
            duplicates += int(duplicate)
            infeasible += int(not score["feasible"])
            calls += 1
            if score["feasible"] and (record_profit is None or score["profit"] > record_profit):
                record_mask, record_profit, record_call = result, score["profit"], calls
            expected_child = {
                "call": calls, "generation": generation_number, "tournaments": tournaments,
                "parent_indices": parents, "crossover": crosses, "pre_mask": pre_mask,
                "mutation_bits": mutation_bits, "mask": result, **score,
                "duplicate": duplicate, "record_profit": record_profit, "record_call": record_call,
            }
            _same(child, expected_child, "candidate replay at call " + str(calls))
            child_refs.append(len(masks))
            masks.append(result)
            scores.append(score)

        _same(event["record_after"], record_profit, "record after children")
        if complete:
            success = record_profit is not None and (record_before is None or record_profit > record_before)
            next_probability, next_stagnant, controller_event = _feedback(
                problem["n"], probability, stagnant, success, method)
            next_population = [population[elite_index], *child_refs]
            full_generations += 1
        else:
            next_probability, next_stagnant, controller_event = probability, stagnant, "PARTIAL_NO_UPDATE"
            next_population = population[:]
            partial_children = child_count
        _same(event["p_m_next"], next_probability, "next mutation probability")
        _same(event["stagnation_after"], next_stagnant, "next stagnation counter")
        _same(event["controller_event"], controller_event, "controller event")
        _same(event["population_after"], next_population, "population after")
        _same(event["rng_after"], _states(rngs), "RNG after generation")
        population, probability, stagnant = next_population, next_probability, next_stagnant

    _same(log["rng_final"], _states(rngs), "final RNG state")
    summary = {
        "new_calls": budget, "physical_evaluations": budget,
        "known_score_validation_evaluations": MU, "duplicate_calls": duplicates,
        "infeasible_calls": infeasible, "full_generations": full_generations,
        "partial_children": partial_children, "best_mask": record_mask,
        "best_profit": record_profit, "best_call": record_call,
        "final_population": population[:],
        "final_mutation_probability": probability,
    }
    _same(log["summary"], summary, "summary independently reconstructed")
    return {
        "verification_status": "VERIFIED", "new_calls": calls,
        "independent_score_checks": MU + calls, "completed_generations": full_generations,
        "partial_generations": int(partial_children > 0), "duplicate_candidates": duplicates,
        "record_profit": record_profit, "record_call": record_call,
        "final_population_refs": population, "final_p_m": probability,
        "final_stagnation": stagnant, "summary": summary,
    }

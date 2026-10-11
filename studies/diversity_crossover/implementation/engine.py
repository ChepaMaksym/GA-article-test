"""CI-only steady-state GA for the registered technical pilot.

This module deliberately has no access to registries, exact optima or certificates.
All objective queries, including duplicates and an unfinished final batch, are logged.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Callable

import numpy as np

from .contract import ci_only


CHANNELS = ("initialization", "parents", "branch", "crossover", "mutation", "ties")
METHODS = ("baseline", "directed", "repeated")
SCHEMA_VERSION = 1


def _integer(value: object, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _problem(problem: dict) -> None:
    if not isinstance(problem, dict):
        raise ValueError("problem must be a dictionary")
    kind = problem.get("kind")
    fields = {"flat": {"kind", "n"}, "onemax": {"kind", "n"},
              "jump": {"kind", "n", "k"},
              "knapsack": {"kind", "n", "weights", "profits", "capacity"}}
    if kind not in fields or set(problem) != fields[kind]:
        raise ValueError("unknown problem fields; oracle metadata is forbidden")
    n = _integer(problem["n"], "n", 1)
    if kind == "jump":
        k = _integer(problem["k"], "k", 1)
        if k >= n:
            raise ValueError("Jump requires 1 <= k < n")
    if kind == "knapsack":
        _integer(problem["capacity"], "capacity")
        for name in ("weights", "profits"):
            values = problem[name]
            if not isinstance(values, (list, tuple)) or len(values) != n:
                raise ValueError(f"{name} must contain n integers")
            for value in values:
                _integer(value, name, 1)


def _mask(mask: str, n: int) -> None:
    if not isinstance(mask, str) or len(mask) != n or set(mask) - {"0", "1"}:
        raise ValueError("mask must be an n-bit binary string")


def _score(problem: dict, mask: str) -> dict:
    kind = problem["kind"]
    ones = mask.count("1")
    if kind == "knapsack":
        weight = sum(w for w, bit in zip(problem["weights"], mask) if bit == "1")
        value = sum(v for v, bit in zip(problem["profits"], mask) if bit == "1")
        feasible = weight <= problem["capacity"]
        key = [1, value] if feasible else [0, problem["capacity"] - weight]
        return {"key": key, "weight": weight, "value": value, "feasible": feasible}
    if kind == "flat":
        value = 0
    elif kind == "onemax":
        value = ones
    else:
        n, k = problem["n"], problem["k"]
        value = k + ones if ones <= n - k or ones == n else n - ones
    return {"key": [1, value], "weight": None, "value": value, "feasible": True}


def evaluate(problem: dict, mask: str) -> dict:
    """One physical objective query; no cache and no repair."""
    ci_only()
    _problem(problem)
    _mask(mask, problem["n"])
    return _score(problem, mask)


def make_rngs(task_index: int, start_index: int, seed: int = 70001,
              initialization_state: dict | None = None) -> dict:
    ci_only()
    for name, value in (("task_index", task_index), ("start_index", start_index), ("seed", seed)):
        _integer(value, name)
    result = {name: np.random.Generator(np.random.PCG64(
        np.random.SeedSequence([seed, task_index, start_index, i])))
        for i, name in enumerate(CHANNELS)}
    if initialization_state is not None:
        if initialization_state.get("bit_generator") != "PCG64":
            raise ValueError("initialization state must be PCG64")
        result["initialization"].bit_generator.state = copy.deepcopy(initialization_state)
    return result


def rng_states(rngs: dict) -> dict:
    return {name: copy.deepcopy(rngs[name].bit_generator.state) for name in CHANNELS}


def population_hash(population: list[str]) -> str:
    return hashlib.sha256(json.dumps(population, separators=(",", ":")).encode("utf-8")).hexdigest()


def metrics(population: list[str], scores: list[dict]) -> dict:
    ci_only()
    if not population or len(population) != len(scores):
        raise ValueError("population and scores must have the same positive length")
    mu, n = len(population), len(population[0])
    if not n:
        raise ValueError("empty chromosomes are forbidden")
    for mask in population:
        _mask(mask, n)
    # Each locus contributes a*(mu-a) differing unordered pairs.
    counts = np.frombuffer("".join(population).encode("ascii"), dtype=np.uint8).reshape(mu, n)
    ones = np.sum(counts == ord("1"), axis=0, dtype=np.int64)
    pair_sum = int(np.sum(ones * (mu - ones)))
    diversity = 0.0 if mu == 1 else 2.0 * pair_sum / (mu * (mu - 1) * n)
    values = [score["value"] for score in scores if score["feasible"]]
    return {"unique_fraction": len(set(population)) / mu,
            "diversity": diversity, "feasible_fraction": len(values) / mu,
            "mean_feasible_value": sum(values) / len(values) if values else None}


def _pick(indices: list[int], rng: np.random.Generator) -> int:
    return indices[0] if len(indices) == 1 else indices[int(rng.integers(len(indices)))]


def _score_shape(score: dict, kind: str) -> None:
    if not isinstance(score, dict) or set(score) != {"key", "weight", "value", "feasible"}:
        raise ValueError("invalid known score schema")
    if type(score["feasible"]) is not bool or type(score["value"]) is not int:
        raise ValueError("known score must use exact integer values")
    key = score["key"]
    if not isinstance(key, list) or len(key) != 2 or any(type(v) is not int for v in key):
        raise ValueError("known score key must contain two integers")
    if key[0] != int(score["feasible"]):
        raise ValueError("score feasibility disagrees with ordering key")
    if score["feasible"] and key[1] != score["value"]:
        raise ValueError("feasible ordering key disagrees with value")
    if kind == "knapsack":
        _integer(score["weight"], "known weight")
    elif score["weight"] is not None or not score["feasible"]:
        raise ValueError("model-function scores must be feasible with null weight")


def run_search(problem: dict, initial_masks: list[str], initial_scores: list[dict],
               method: str, rngs: dict, sink: Callable[[dict], None],
               budget: int = 5000, pc: float = 0.9) -> dict:
    """Execute new queries only. Known initial scores are never re-evaluated here."""
    ci_only()
    _problem(problem)
    _integer(budget, "budget", 1)
    if method not in METHODS:
        raise ValueError("unknown method")
    if type(pc) not in (int, float) or not 0 <= pc <= 1:
        raise ValueError("pc must be between zero and one")
    if not initial_masks or len(initial_masks) != len(initial_scores):
        raise ValueError("known initial population and scores must match")
    if set(rngs) != set(CHANNELS):
        raise ValueError("exactly six RNG channels are required")
    for name in CHANNELS:
        if not isinstance(rngs[name], np.random.Generator) or not isinstance(rngs[name].bit_generator, np.random.PCG64):
            raise ValueError("every channel must be an independent PCG64 generator")
    if len({id(rngs[name]) for name in CHANNELS}) != len(CHANNELS):
        raise ValueError("RNG channels may not alias")
    population = list(initial_masks)
    scores = copy.deepcopy(initial_scores)
    n, mu = problem["n"], len(population)
    for mask, score in zip(population, scores):
        _mask(mask, n)
        _score_shape(score, problem["kind"])
    best_index = max(range(mu), key=lambda i: tuple(scores[i]["key"]))
    record = {"mask": population[best_index], "score": copy.deepcopy(scores[best_index]), "call": 0}
    initial_record = copy.deepcopy(record)
    seen = set(population)
    calls = steps = completed_steps = incomplete_steps = accepted_steps = 0
    candidate_feasible = duplicate_candidates = crossover_steps = 0
    directed_changed_steps = directed_active_steps = 0
    first_improvement_call = None
    checkpoint_calls = {0, budget} | {x for x in (1000, 2500, 5000) if x <= budget}

    def checkpoint() -> None:
        sink({"event": "checkpoint", "call": calls,
              "stage": "AFTER_EVALUATION_BEFORE_REPLACEMENT",
              "population": list(population), "scores": copy.deepcopy(scores),
              "metrics": metrics(population, scores), "record": copy.deepcopy(record)})

    sink({"event": "initial", "schema_version": SCHEMA_VERSION,
          "problem": copy.deepcopy(problem), "method": method,
          "params": {"mu": mu, "n": n, "budget": budget, "pc": float(pc),
                     "mutation_probability": 1 / n, "repeated_offspring": 4},
          "population": list(population), "scores": copy.deepcopy(scores),
          "rng_start": rng_states(rngs), "initial_record": copy.deepcopy(record)})
    checkpoint()
    while calls < budget:
        steps += 1
        before = rng_states(rngs)
        first = int(rngs["parents"].integers(mu))
        has_crossover = bool(pc == 1 or (pc != 0 and rngs["branch"].random() < pc))
        parents, anchor, eligible = [first], None, []
        changed = active = False
        distance = None
        if has_crossover:
            second = int(rngs["parents"].integers(mu))
            if method == "directed":
                anchor = second
                eligible = [i for i in range(mu) if scores[i]["key"] == scores[anchor]["key"]]
                distances = [sum(a != b for a, b in zip(population[first], population[i])) for i in eligible]
                largest = max(distances)
                second = _pick([i for i, d in zip(eligible, distances) if d == largest], rngs["ties"])
                changed = second != anchor
                active = population[second] != population[anchor]
            parents.append(second)
            distance = sum(a != b for a, b in zip(population[first], population[second]))
        planned = 4 if method == "repeated" and has_crossover else 1
        crossover_steps += int(has_crossover)
        directed_changed_steps += int(changed)
        directed_active_steps += int(active)
        sink({"event": "step", "step": steps, "calls_before": calls, "rng_before": before,
              "parent_indices": parents, "anchor_index": anchor, "eligible_indices": eligible,
              "has_crossover": has_crossover, "planned_offspring": planned,
              "directed_changed": changed, "directed_active": active, "parent_distance": distance})
        candidates = []
        for slot in range(min(planned, budget - calls)):
            if has_crossover:
                choices = rngs["crossover"].random(n) < 0.5
                pre = "".join(population[parents[0]][i] if choices[i] else population[parents[1]][i] for i in range(n))
            else:
                pre = population[first]
            mutation_bits = np.flatnonzero(rngs["mutation"].random(n) < 1 / n).tolist()
            characters = list(pre)
            for index in mutation_bits:
                characters[index] = "1" if characters[index] == "0" else "0"
            mask = "".join(characters)
            score = _score(problem, mask)
            calls += 1
            duplicate = mask in seen
            duplicate_candidates += int(duplicate)
            seen.add(mask)
            candidate_feasible += int(score["feasible"])
            if tuple(score["key"]) > tuple(record["score"]["key"]):
                record = {"mask": mask, "score": copy.deepcopy(score), "call": calls}
            if first_improvement_call is None and tuple(score["key"]) > tuple(initial_record["score"]["key"]):
                first_improvement_call = calls
            candidates.append((mask, score))
            sink({"event": "candidate", "step": steps, "slot": slot, "call": calls,
                  "mask": mask, "pre_mutation_mask": pre, "mutation_bits": mutation_bits,
                  "score": score, "duplicate": duplicate, "record": copy.deepcopy(record)})
            if calls in checkpoint_calls:
                checkpoint()
        completed = len(candidates) == planned
        selected = replacement = None
        accepted = False
        if completed:
            completed_steps += 1
            best_key = max(tuple(score["key"]) for _, score in candidates)
            selected = _pick([i for i, (_, score) in enumerate(candidates) if tuple(score["key"]) == best_key], rngs["ties"])
            worst_key = min(tuple(score["key"]) for score in scores)
            if best_key >= worst_key:
                replacement = _pick([i for i in range(mu) if tuple(scores[i]["key"]) == worst_key], rngs["ties"])
                population[replacement], scores[replacement] = candidates[selected]
                accepted = True
                accepted_steps += 1
        else:
            incomplete_steps += 1
        sink({"event": "finish_step", "step": steps, "call_after": calls,
              "rng_after": rng_states(rngs), "completed": completed,
              "selected_slot": selected, "accepted": accepted, "replacement_index": replacement,
              "population_hash": population_hash(population), "metrics": metrics(population, scores),
              "record": copy.deepcopy(record)})
    summary = {"status": "COMPLETE", "method": method, "budget": budget,
               "new_calls": calls, "physical_calls": calls, "steps": steps,
               "completed_steps": completed_steps, "incomplete_steps": incomplete_steps,
               "accepted_steps": accepted_steps, "crossover_steps": crossover_steps,
               "candidate_feasible": candidate_feasible, "invalid_candidates": calls - candidate_feasible,
               "duplicate_candidates": duplicate_candidates,
               "directed_changed_steps": directed_changed_steps, "directed_active_steps": directed_active_steps,
               "initial_record": initial_record, "record": copy.deepcopy(record),
               "first_improvement_call": first_improvement_call,
               "population_hash": population_hash(population), "metrics": metrics(population, scores),
               "rng_final": rng_states(rngs)}
    sink({"event": "terminal", "summary": copy.deepcopy(summary)})
    return summary

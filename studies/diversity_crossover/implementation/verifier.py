"""Independent, post-search replay of the technical-pilot event stream.

This module deliberately does not import the search engine.  Evaluation,
selection, genetic operators, replacement and population statistics are
reconstructed here from the recorded PCG64 states.  Its computations are
verification costs, never additional search objective calls.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Iterable

import numpy as np


CHANNELS = ("initialization", "parents", "branch", "crossover", "mutation", "ties")
METHODS = ("baseline", "directed", "repeated", "mutation_control")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _mask(mask: str, n: int) -> None:
    _require(isinstance(mask, str) and len(mask) == n and set(mask) <= {"0", "1"},
             "Invalid binary mask or bit ordering/length")


def independent_score(problem: dict, mask: str) -> dict:
    """Compute a score directly from integer inputs, without the engine."""
    from .contract import ci_only

    ci_only()
    kind = problem.get("kind")
    allowed_fields = {"flat": {"kind", "n"}, "onemax": {"kind", "n"},
                      "jump": {"kind", "n", "k"},
                      "knapsack": {"kind", "n", "weights", "profits", "capacity"}}
    _require(kind in allowed_fields and set(problem) == allowed_fields[kind],
             "Unknown objective fields, including forbidden oracle metadata")
    n = problem["n"]
    _require(type(n) is int and n > 0, "Invalid dimension")
    _mask(mask, n)
    if kind == "knapsack":
        weights, values, capacity = problem["weights"], problem["profits"], problem["capacity"]
        _require(len(weights) == len(values) == n, "Invalid item vectors")
        _require(type(capacity) is int and capacity >= 0, "Invalid capacity")
        _require(all(type(w) is int and w > 0 for w in weights), "Invalid integer weights")
        _require(all(type(v) is int and v > 0 for v in values), "Invalid integer values")
        chosen = [i for i, bit in enumerate(mask) if bit == "1"]
        weight = sum(weights[i] for i in chosen)
        value = sum(values[i] for i in chosen)
        feasible = weight <= capacity
        return {"key": [1, value] if feasible else [0, capacity - weight],
                "weight": weight, "value": value, "feasible": feasible}
    ones = mask.count("1")
    if kind == "flat":
        value = 0
    elif kind == "onemax":
        value = ones
    elif kind == "jump":
        k = problem["k"]
        _require(type(k) is int and 1 <= k < n, "Invalid Jump gap")
        value = k + ones if ones <= n - k or ones == n else n - ones
    else:
        raise ValueError("Unknown objective kind")
    return {"key": [1, value], "weight": None, "value": value, "feasible": True}


def independent_metrics(masks: list[str], scores: list[dict]) -> dict:
    """Position-weighted population statistics, including duplicate copies."""
    from .contract import ci_only

    ci_only()
    _require(bool(masks) and len(masks) == len(scores), "Empty or inconsistent population")
    mu, n = len(masks), len(masks[0])
    for mask in masks:
        _mask(mask, n)
    # Each locus contributes c*(mu-c) to the unordered Hamming-pair sum.
    pair_sum = sum((count := locus.count("1")) * (mu - count) for locus in zip(*masks))
    diversity = 0.0 if mu == 1 else 2.0 * pair_sum / (mu * (mu - 1) * n)
    feasible_values = [score["value"] for score in scores if score["feasible"]]
    return {"unique_fraction": len(set(masks)) / mu,
            "diversity": diversity,
            "feasible_fraction": len(feasible_values) / mu,
            "mean_feasible_value": (math.fsum(feasible_values) / len(feasible_values)
                                    if feasible_values else None)}


def _key(score: dict) -> tuple[int, int]:
    return tuple(score["key"])


def _same(actual, expected, label: str) -> None:
    _require(actual == expected, f"Replay discrepancy: {label}")


def _score_same(actual: dict, expected: dict, label: str) -> None:
    _require(isinstance(actual, dict) and set(actual) == {"key", "weight", "value", "feasible"},
             "Invalid score schema")
    _require(type(actual["feasible"]) is bool and type(actual["value"]) is int and
             (actual["weight"] is None or type(actual["weight"]) is int), "Non-integer score fields")
    _require(isinstance(actual["key"], list) and len(actual["key"]) == 2 and
             all(type(item) is int for item in actual["key"]), "Invalid exact ordering key")
    _same(actual, expected, label)


def _metrics_same(actual: dict, expected: dict, label: str) -> None:
    _same(set(actual), set(expected), label + " fields")
    for name, value in expected.items():
        if value is None:
            _same(actual[name], None, label + " " + name)
        else:
            _require(isinstance(actual[name], (float, int)) and
                     math.isclose(actual[name], value, rel_tol=1e-12, abs_tol=1e-12),
                     f"Replay discrepancy: {label} {name}")


def _states(generators: dict) -> dict:
    return {name: generators[name].bit_generator.state for name in CHANNELS}


def _restore(states: dict) -> dict:
    _same(set(states), set(CHANNELS), "RNG channel set")
    generators = {}
    for name in CHANNELS:
        _same(states[name].get("bit_generator"), "PCG64", "RNG type")
        bit_generator = np.random.PCG64()
        bit_generator.state = states[name]
        generators[name] = np.random.Generator(bit_generator)
    return generators


def _pick(indices: list[int], rng: np.random.Generator) -> int:
    _require(bool(indices), "Empty selection tie class")
    return indices[0] if len(indices) == 1 else indices[int(rng.integers(len(indices)))]


def _population_hash(population: list[str]) -> str:
    return hashlib.sha256(json.dumps(population, separators=(",", ":")).encode("utf-8")).hexdigest()


def _trace_row(call: int, record: dict, metrics: dict) -> dict:
    return {"call": call, "best_value": record["score"]["value"],
            "best_key": list(record["score"]["key"]), "record_mask": record["mask"],
            "record_call": record["call"], **metrics}


def verify_frozen_header(problem: dict, initial_event: dict, bank: dict,
                         method: str, pc: float, budget: int = 5000) -> dict:
    """Bind a journal to the frozen start and registered seed, before replay.

    Replay alone proves consistency with recorded states, not their provenance.
    This independent check does not invoke preparation/engine functions and
    performs no objective queries; replay subsequently verifies known scores.
    """
    from .contract import ci_only

    ci_only()
    tasks = ("Flat", "OneMax", "Jump4", "Jump8", "UC-s000", "WC-s001", "SC-s005", "SC-s000")
    starts = ("cloned", "bank")
    _same(bank.get("schema_version"), "diversity-pilot-bank-v1", "frozen bank schema")
    _same(bank.get("protocol_id"), "GA-DIVERSITY-CROSSOVER-TECHNICAL-PILOT-V1", "frozen protocol")
    _require(type(bank.get("seed")) is int and bank["seed"] == 70001, "Unregistered pilot seed")
    _require(type(bank.get("task_index")) is int and 0 <= bank["task_index"] < len(tasks),
             "Invalid frozen task index")
    _require(type(bank.get("start_index")) is int and 0 <= bank["start_index"] < len(starts),
             "Invalid frozen start index")
    _same(bank.get("task"), tasks[bank["task_index"]], "frozen task identity")
    _same(bank.get("start"), starts[bank["start_index"]], "frozen start identity")
    _require(type(bank.get("n")) is int and bank["n"] == 100 and
             type(bank.get("mu")) is int and bank["mu"] == 30, "Unregistered frozen dimensions")
    _require(method in ("baseline", "directed", "repeated"), "Unknown engine method")
    _require(type(budget) is int and budget == 5000, "Unregistered pilot budget")
    _require(type(pc) in (float, int) and pc in (0, 0.9), "Unregistered pilot crossover probability")
    _same(problem, bank.get("problem"), "frozen objective")
    _same(problem.get("n"), 100, "frozen objective dimension")
    model_expectations = {"Flat": ("flat", None), "OneMax": ("onemax", None),
                          "Jump4": ("jump", 4), "Jump8": ("jump", 8)}
    task = bank["task"]
    if task in model_expectations:
        kind, gap = model_expectations[task]
        _same(problem.get("kind"), kind, "frozen model kind")
        _same(set(problem), {"kind", "n"} if gap is None else {"kind", "n", "k"}, "frozen model fields")
        if gap is not None:
            _same(problem.get("k"), gap, "frozen model gap")
    else:
        _same(problem.get("kind"), "knapsack", "frozen knapsack kind")
        _same(set(problem), {"kind", "n", "weights", "profits", "capacity"}, "frozen knapsack fields")
    population, scores = bank.get("masks"), bank.get("scores")
    _require(isinstance(population, list) and isinstance(scores, list) and
             len(population) == len(scores) == 30, "Frozen population incomplete")
    for mask, score in zip(population, scores):
        _mask(mask, 100)
        _score_same(score, score, "frozen known score schema")
    _same(initial_event.get("event"), "initial", "frozen initial event")
    _same(initial_event.get("schema_version"), 1, "frozen event schema")
    _same(initial_event.get("method"), method, "frozen method")
    _same(initial_event.get("problem"), problem, "frozen journal objective")
    _same(initial_event.get("population"), population, "frozen journal population")
    _same(initial_event.get("scores"), scores, "frozen journal known scores")
    _same(initial_event.get("params"), {"mu": 30, "n": 100, "budget": budget,
                                       "pc": float(pc), "mutation_probability": 0.01,
                                       "repeated_offspring": 4}, "frozen journal parameters")
    expected_states = {}
    for channel, name in enumerate(CHANNELS):
        generator = np.random.PCG64(np.random.SeedSequence(
            [70001, bank["task_index"], bank["start_index"], channel]))
        expected_states[name] = generator.state
    _same(bank.get("initialization_before"), expected_states["initialization"],
          "frozen initialization seed")
    after = bank.get("initialization_after")
    _require(isinstance(after, dict) and after.get("bit_generator") == "PCG64",
             "Invalid prepared initialization state")
    expected_states["initialization"] = after
    # State assignment validates the recorded PCG64 state shape independently.
    _restore(expected_states)
    _same(initial_event.get("rng_start"), expected_states, "frozen six-channel RNG identity")
    best_index = max(range(30), key=lambda i: _key(scores[i]))
    _same(initial_event.get("initial_record"),
          {"mask": population[best_index], "score": scores[best_index], "call": 0},
          "frozen initial record")
    return {"status": "VERIFIED_FROZEN_HEADER", "task": task, "start": bank["start"],
            "method": method, "seed": 70001, "objective_evaluations": 0}


def verify_journal(problem: dict, records: Iterable[dict]) -> dict:
    """Verify a complete journal in order; incomplete/tampered streams fail closed."""
    from .contract import ci_only

    ci_only()
    events = iter(records)
    try:
        initial = next(events)
    except StopIteration as error:
        raise ValueError("Missing initial event") from error
    _same(initial.get("event"), "initial", "first event")
    _same(initial.get("schema_version"), 1, "schema version")
    _same(initial.get("problem"), problem, "objective identity")
    method = initial["method"]
    _require(method in METHODS, "Unknown method")
    params = initial["params"]
    population = list(initial["population"])
    mu, n, budget, pc = params["mu"], params["n"], params["budget"], params["pc"]
    _require(type(mu) is int and mu > 0 and len(population) == mu, "Invalid population size")
    _same(n, problem["n"], "objective dimension")
    _require(type(budget) is int and budget > 0, "Invalid objective-call budget")
    _require(isinstance(pc, (int, float)) and 0 <= pc <= 1, "Invalid crossover probability")
    _require(math.isclose(params["mutation_probability"], 1 / n, rel_tol=0, abs_tol=1e-15),
             "Mutation probability differs from 1/n")
    _same(params["repeated_offspring"], 4, "offspring batch size")
    if method == "mutation_control":
        _same(pc, 0, "mutation-only control")
    scores = [independent_score(problem, mask) for mask in population]
    _require(len(initial["scores"]) == mu, "Wrong initial score count")
    for actual, expected in zip(initial["scores"], scores):
        _score_same(actual, expected, "initial scores")
    best_index = max(range(mu), key=lambda i: _key(scores[i]))
    record = {"mask": population[best_index], "score": scores[best_index], "call": 0}
    _same(initial["initial_record"], record, "initial record")
    initial_record = record
    rng = _restore(initial["rng_start"])
    seen = set(population)
    verification_initial, verification_candidates, verification_intermediates = mu, 0, 0
    calls = steps = completed_steps = partial_steps = replacements = duplicates = crossover_steps = 0
    feasible_candidates = record_improvements = 0
    first_improvement = None
    trace = [_trace_row(0, record, independent_metrics(population, scores))]
    checkpoint_calls = {0, budget, *(c for c in (1000, 2500, 5000) if c <= budget)}
    checkpoints_seen = set()
    pending_checkpoint = 0
    current = None
    step_candidates = []
    product = Counter()
    directed = Counter()
    terminal = None
    for event in events:
        _require(terminal is None, "Events after terminal event")
        kind = event.get("event")
        if kind == "checkpoint":
            _require(pending_checkpoint is not None and event["call"] == pending_checkpoint,
                     "Unexpected or out-of-order checkpoint")
            _same(event["stage"], "AFTER_EVALUATION_BEFORE_REPLACEMENT", "checkpoint stage")
            _same(event["population"], population, "checkpoint population")
            _same(event["scores"], scores, "checkpoint scores")
            _same(event["record"], record, "checkpoint record")
            _metrics_same(event["metrics"], independent_metrics(population, scores), "checkpoint metrics")
            _require(event["call"] not in checkpoints_seen, "Duplicate checkpoint")
            checkpoints_seen.add(event["call"])
            pending_checkpoint = None
            continue
        _require(pending_checkpoint is None, "Required checkpoint omitted")
        if kind == "step":
            _require(current is None and calls < budget, "Unexpected step start")
            steps += 1
            _same(event["step"], steps, "step numbering")
            _same(event["calls_before"], calls, "step call boundary")
            _same(event["rng_before"], _states(rng), "RNG state before step")
            first = int(rng["parents"].integers(mu))
            has_crossover = (False if pc == 0 else True if pc == 1
                             else bool(rng["branch"].random() < pc))
            parents, anchor, eligible = [first], None, []
            active = changed = False
            distance = None
            if has_crossover:
                second = int(rng["parents"].integers(mu))
                if method == "directed":
                    anchor = second
                    eligible = [i for i in range(mu) if _key(scores[i]) == _key(scores[anchor])]
                    distances = {i: sum(a != b for a, b in zip(population[first], population[i]))
                                 for i in eligible}
                    maximum = max(distances.values())
                    second = _pick([i for i in eligible if distances[i] == maximum], rng["ties"])
                    changed = second != anchor
                    active = population[second] != population[anchor]
                    directed["steps"] += 1
                    directed["active_steps"] += int(active)
                    directed["changed_position_steps"] += int(changed)
                    directed["eligible_positions_total"] += len(eligible)
                    directed["eligible_positions_max"] = max(directed["eligible_positions_max"], len(eligible))
                parents.append(second)
                distance = sum(a != b for a, b in zip(population[first], population[second]))
            planned = 4 if has_crossover and method == "repeated" else 1
            crossover_steps += int(has_crossover)
            _same(event["parent_indices"], parents, "parent selection")
            _same(event["anchor_index"], anchor, "second-parent anchor")
            _same(event["eligible_indices"], eligible, "directed tie class")
            _same(event["has_crossover"], has_crossover, "branch selection")
            _same(event["planned_offspring"], planned, "planned batch size")
            _same(event["directed_active"], active, "directed activity")
            _same(event["directed_changed"], changed, "directed position change")
            _same(event["parent_distance"], distance, "parent Hamming distance")
            current = {"event": event, "parents": parents, "planned": planned,
                       "has_crossover": has_crossover, "start_call": calls}
            step_candidates = []
        elif kind == "candidate":
            _require(current is not None and calls < budget and len(step_candidates) < current["planned"],
                     "Unexpected candidate")
            slot = len(step_candidates)
            _same(event["step"], steps, "candidate step")
            _same(event["slot"], slot, "candidate slot")
            first_mask = population[current["parents"][0]]
            pre_mask = first_mask
            if current["has_crossover"]:
                second_mask = population[current["parents"][1]]
                choices = rng["crossover"].random(n) < 0.5
                pre_mask = "".join(first_mask[i] if choices[i] else second_mask[i] for i in range(n))
            changed_bits = [int(i) for i in np.flatnonzero(rng["mutation"].random(n) < 1 / n)]
            bits = list(pre_mask)
            for bit in changed_bits:
                bits[bit] = "0" if bits[bit] == "1" else "1"
            candidate_mask = "".join(bits)
            _same(event["pre_mutation_mask"], pre_mask, "crossover/mutation input")
            _same(event["mutation_bits"], changed_bits, "mutation indices")
            _same(event["mask"], candidate_mask, "candidate genotype")
            score = independent_score(problem, candidate_mask)
            verification_candidates += 1
            _score_same(event["score"], score, "candidate score")
            calls += 1
            _same(event["call"], calls, "objective-call index")
            duplicate = candidate_mask in seen
            _same(event["duplicate"], duplicate, "duplicate accounting")
            duplicates += int(duplicate)
            seen.add(candidate_mask)
            feasible_candidates += int(score["feasible"])
            if _key(score) > _key(record["score"]):
                record = {"mask": candidate_mask, "score": score, "call": calls}
                record_improvements += 1
                if first_improvement is None and _key(score) > _key(initial_record["score"]):
                    first_improvement = calls
            _same(event["record"], record, "best evaluated record")
            if current["has_crossover"]:
                product["crossover_candidates"] += 1
                pre_score = independent_score(problem, pre_mask)
                verification_intermediates += 1
                product["pre_mutation_feasible"] += int(pre_score["feasible"])
                parent_scores = [scores[i] for i in current["parents"]]
                if all(s["feasible"] for s in parent_scores):
                    product["both_parents_feasible_candidates"] += 1
                    parent_best = max(s["value"] for s in parent_scores)
                    product["pre_mutation_better_than_both"] += int(pre_score["feasible"] and pre_score["value"] > parent_best)
                    product["post_mutation_better_than_both"] += int(score["feasible"] and score["value"] > parent_best)
            step_candidates.append({"mask": candidate_mask, "score": score})
            if calls in checkpoint_calls:
                pending_checkpoint = calls
        elif kind == "finish_step":
            _require(current is not None, "Finish without a step")
            expected_count = min(current["planned"], budget - current["start_call"])
            _same(len(step_candidates), expected_count, "completed candidate count")
            completed = expected_count == current["planned"]
            selected = replacement = None
            accepted = False
            if completed:
                completed_steps += 1
                best_key = max(_key(child["score"]) for child in step_candidates)
                selected = _pick([i for i, child in enumerate(step_candidates) if _key(child["score"]) == best_key], rng["ties"])
                worst_key = min(_key(score) for score in scores)
                if best_key >= worst_key:
                    accepted = True
                    replacement = _pick([i for i in range(mu) if _key(scores[i]) == worst_key], rng["ties"])
                    population[replacement] = step_candidates[selected]["mask"]
                    scores[replacement] = step_candidates[selected]["score"]
                    replacements += 1
            else:
                partial_steps += 1
                _same(calls, budget, "partial batch only at budget boundary")
            _same(event["step"], steps, "finish step number")
            _same(event["call_after"], calls, "finish call boundary")
            _same(event["completed"], completed, "batch completion")
            _same(event["selected_slot"], selected, "selected child")
            _same(event["accepted"], accepted, "replacement decision")
            _same(event["replacement_index"], replacement, "replacement position")
            _same(event["population_hash"], _population_hash(population), "population identity")
            metrics = independent_metrics(population, scores)
            _metrics_same(event["metrics"], metrics, "finish population metrics")
            _same(event["record"], record, "finish best record")
            _same(event["rng_after"], _states(rng), "RNG state after step")
            trace.append(_trace_row(calls, record, metrics))
            current = None
        elif kind == "terminal":
            _require(current is None and calls == budget, "Premature terminal event")
            _same(checkpoints_seen, checkpoint_calls, "checkpoint completeness")
            terminal = event
        else:
            raise ValueError("Unknown journal event")
    _require(terminal is not None, "Missing terminal event")
    # The terminal's scientific/accounting fields are checked below independently.
    summary = _terminal_summary(initial, calls, steps, completed_steps, partial_steps,
                                replacements, duplicates, feasible_candidates,
                                record_improvements, first_improvement, record,
                                population, scores, rng, crossover_steps, directed)
    _same(terminal["summary"], summary, "terminal reconstruction")
    denominator = product["both_parents_feasible_candidates"]
    productivity = {name: int(product[name]) for name in (
        "crossover_candidates", "pre_mutation_feasible", "both_parents_feasible_candidates",
        "pre_mutation_better_than_both", "post_mutation_better_than_both")}
    productivity.update({"conditional_status": "DEFINED" if denominator else "NOT_APPLICABLE",
                         "pre_mutation_better_fraction": product["pre_mutation_better_than_both"] / denominator if denominator else None,
                         "post_mutation_better_fraction": product["post_mutation_better_than_both"] / denominator if denominator else None})
    return {"status": "VERIFIED", "summary": summary,
            "verification_calls": verification_initial + verification_candidates + verification_intermediates,
            "verification_call_breakdown": {"initial": verification_initial,
                                             "final_candidates": verification_candidates,
                                             "crossover_intermediates": verification_intermediates},
            "trace": trace, "productivity": productivity,
            "directed_activity": {name: int(directed[name]) for name in (
                "steps", "active_steps", "changed_position_steps", "eligible_positions_total", "eligible_positions_max")}}


def _terminal_summary(initial: dict, calls: int, steps: int, completed_steps: int,
                      partial_steps: int, replacements: int, duplicates: int,
                      feasible_candidates: int, record_improvements: int,
                      first_improvement: int | None, record: dict,
                      population: list[str], scores: list[dict], rng: dict,
                      crossover_steps: int, directed: Counter) -> dict:
    """Exact terminal interface is intentionally centralized for schema review."""
    return {"status": "COMPLETE", "method": initial["method"],
            "budget": initial["params"]["budget"], "new_calls": calls,
            "physical_calls": calls, "steps": steps,
            "completed_steps": completed_steps, "incomplete_steps": partial_steps,
            "accepted_steps": replacements, "crossover_steps": crossover_steps,
            "candidate_feasible": feasible_candidates, "invalid_candidates": calls - feasible_candidates,
            "duplicate_candidates": duplicates,
            "directed_changed_steps": int(directed["changed_position_steps"]),
            "directed_active_steps": int(directed["active_steps"]),
            "initial_record": initial["initial_record"],
            "first_improvement_call": first_improvement, "record": record,
            "population_hash": _population_hash(population),
            "metrics": independent_metrics(population, scores), "rng_final": _states(rng)}

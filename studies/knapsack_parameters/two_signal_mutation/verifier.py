"""CI-only independent reconstruction of the two-signal mutation journal.

No production evaluator, parent selector, or feedback function is imported.
Premutation evaluations are performed here, after search, and cannot influence
the producer.  Hash-bound transport identity and resource permission remain
the responsibility of the execution driver.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import json
import os

import numpy as np


SCHEMA = "ga-two-signal-mutation-log-v1"
METHODS = ("fixed", "adaptive_mutation", "two_signal")
CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
MU = 30
TOP_FIELDS = {
    "schema", "method", "problem", "initial_masks", "initial_scores", "rng_initial",
    "budget", "candidates", "generations", "summary", "rng_final", "timing_ns",
}
GEN_FIELDS = {
    "generation", "start_call", "end_call", "complete", "population_before",
    "elite_index", "p_m", "stagnation_before", "record_before", "record_after",
    "p_m_next", "stagnation_after", "controller_event", "population_after",
    "rng_before", "rng_after", "parent_distances", "novelty_sum_numerator",
    "novelty_sum_denominator", "novelty_mean_numerator", "novelty_mean_denominator",
    "gate_allows_increase",
}
CHILD_FIELDS = {
    "call", "generation", "tournaments", "parent_indices", "crossover", "pre_mask",
    "mutation_bits", "mask", "weight", "profit", "feasible", "duplicate",
    "record_profit", "record_call", "parent_distance",
}
TIMING_FIELDS = {
    "validation", "selection", "variation", "evaluation", "signal", "controller",
    "log_assembly", "total",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("Invalid two-signal journal: " + message)


def _ci_only() -> None:
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "GitHub Actions is required")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test",
             "wrong repository")
    _require(os.environ.get("GITHUB_REF") ==
             "refs/heads/research/masters-ga-diversity-crossover", "wrong branch")


def _same(actual, expected, label: str) -> None:
    """Strict JSON comparison rejects nonfinite numbers and bool/int swaps."""
    try:
        left = json.dumps(actual, sort_keys=True, separators=(",", ":"), allow_nan=False)
        right = json.dumps(expected, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid two-signal journal: non-JSON " + label) from exc
    _require(left == right, label)


def _fields(value, expected: set[str], label: str) -> None:
    _require(type(value) is dict and set(value) == expected, label + " fields")


def _integer(value, minimum: int, label: str) -> None:
    _require(type(value) is int and value >= minimum, label)


def _problem(value: dict) -> dict:
    _fields(value, {"n", "weights", "profits", "capacity"}, "problem")
    _integer(value["n"], 2, "chromosome length")
    _integer(value["capacity"], 0, "capacity")
    for name in ("weights", "profits"):
        _require(type(value[name]) is list and len(value[name]) == value["n"], name + " length")
        for entry in value[name]:
            _integer(entry, 1, name + " entry")
    return value


def _score(problem: dict, mask: str) -> dict:
    _require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"},
             "binary mask")
    weight = profit = 0
    for index, bit in enumerate(mask):
        if bit == "1":
            weight += problem["weights"][index]
            profit += problem["profits"][index]
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _key(score: dict, capacity: int) -> tuple[int, int]:
    return (1, score["profit"]) if score["feasible"] else (0, capacity - score["weight"])


def _states(generators: dict) -> dict:
    return {name: copy.deepcopy(generators[name].bit_generator.state) for name in CHANNELS}


def _restore(value: dict) -> dict:
    _fields(value, set(CHANNELS), "RNG channels")
    result = {}
    for name in CHANNELS:
        state = value[name]
        _require(type(state) is dict and state.get("bit_generator") == "PCG64", "PCG64 state")
        try:
            bit_generator = np.random.PCG64(0)
            bit_generator.state = copy.deepcopy(state)
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            raise ValueError("Invalid two-signal journal: RNG state " + name) from exc
        result[name] = np.random.Generator(bit_generator)
    _same(_states(result), value, "lossless RNG restoration")
    return result


def _choose(positions: list[int], generator: np.random.Generator) -> int:
    # Equal tournament entries remain separate entries and consume a tie draw.
    return positions[0] if len(positions) == 1 else positions[int(generator.integers(len(positions)))]


def _reference_mean(distances: list[int], n: int) -> Fraction:
    """Exact mean of r(d), including pairs that did not cross."""
    _require(type(n) is int and n >= 2 and type(distances) is list and bool(distances),
             "nonempty distance list")
    total = Fraction(0)
    for distance in distances:
        _require(type(distance) is int and 0 <= distance <= n, "parent distance")
        if distance:
            total += Fraction(1) - Fraction(1, 2 ** (distance - 1))
    return total / len(distances)


def _feedback(n: int, probability: float, stagnant: int, success: bool,
              method: str, mean: Fraction) -> tuple[float, int, str]:
    """Independent transcription of the registered rule and exact gate."""
    lower, upper = 1 / n, min(8 / n, 0.5)
    if method == "fixed":
        return lower, 0, "FIXED"
    if success:
        return max(lower, probability / 2), 0, "SUCCESS_HALVE"
    if stagnant == 4:
        if method == "two_signal" and mean > Fraction(1, 2):
            return probability, 0, "GATE_DENIED"
        return min(upper, probability * 2), 0, "STAGNATION_DOUBLE"
    return probability, stagnant + 1, "NO_CHANGE"


def _population_point(q: int, complete: bool, population: list[int], masks: list[str],
                      scores: list[dict], record_mask: str | None, n: int) -> dict:
    selected_masks = [masks[reference] for reference in population]
    selected_scores = [scores[reference] for reference in population]
    feasible_scores = [score for score in selected_scores if score["feasible"]]
    different_pairs = 0
    for index in range(n):
        ones = sum(mask[index] == "1" for mask in selected_masks)
        different_pairs += ones * (MU - ones)
    return {
        "q": q, "complete": complete, "unique_masks": len(set(selected_masks)),
        "unique_fraction": len(set(selected_masks)) / MU,
        "mean_pairwise_hamming": different_pairs / (MU * (MU - 1) // 2),
        "feasible_fraction": len(feasible_scores) / MU,
        "mean_feasible_profit": (sum(score["profit"] for score in feasible_scores) /
                                 len(feasible_scores)) if feasible_scores else None,
        "record_in_population": record_mask is not None and record_mask in selected_masks,
    }


def _validate_timings(value: dict) -> None:
    """Observational time is validated, never independently claimed reconstructed."""
    _fields(value, TIMING_FIELDS, "timing")
    for name in TIMING_FIELDS:
        _integer(value[name], 0, "nonnegative integer timing " + name)
    _require(value["total"] >= sum(duration for name, duration in value.items() if name != "total"),
             "disjoint timing scopes exceed total")


def verify_log(log: dict) -> dict:
    """Reconstruct all operators, counters, committed populations and diagnostics.

    Tiny budgets and n>=2 support CI software fixtures only. The driver binds
    registered task/seed/n=100/budget=5000/implementation identity externally.
    There is deliberately no exact-optimum input or threshold-hit calculation.
    """
    _ci_only()
    _fields(log, TOP_FIELDS, "top-level")
    _same(log["schema"], SCHEMA, "schema")
    method = log["method"]
    _require(type(method) is str and method in METHODS, "method")
    problem = _problem(log["problem"])
    n, capacity = problem["n"], problem["capacity"]
    budget = log["budget"]
    _integer(budget, 1, "new-query budget")
    _validate_timings(log["timing_ns"])
    _require(type(log["initial_masks"]) is list and len(log["initial_masks"]) == MU,
             "30 initial masks")
    _require(type(log["initial_scores"]) is list and len(log["initial_scores"]) == MU,
             "30 known initial scores")
    _require(type(log["candidates"]) is list and len(log["candidates"]) == budget,
             "candidate completeness")
    _require(type(log["generations"]) is list and
             len(log["generations"]) == (budget + 28) // 29, "generation completeness")

    masks = list(log["initial_masks"])
    scores = [_score(problem, mask) for mask in masks]
    for supplied, score in zip(log["initial_scores"], scores, strict=True):
        _fields(supplied, {"weight", "profit", "feasible"}, "known initial score")
        _same(supplied, score, "independently evaluated known initial score")
    population = list(range(MU))
    seen = set(masks)
    record_mask = record_profit = record_call = None
    for mask, score in zip(masks, scores, strict=True):
        if score["feasible"] and (record_profit is None or score["profit"] > record_profit):
            record_mask, record_profit, record_call = mask, score["profit"], 0

    record_events = [{"q": 0, "profit": record_profit}]
    population_trace = [_population_point(0, True, population, masks, scores, record_mask, n)]
    generation_trace, candidate_metrics = [], []
    operator_bins = [{"distance": distance, "total": 0, "crossed": 0,
                      "novel_crossed": 0, "feasible_crossed": 0, "better_both_crossed": 0}
                     for distance in range(n + 1)]
    generators = _restore(log["rng_initial"])
    probability, stagnant = 1 / n, 0
    calls = duplicates = infeasible = full_generations = partial_children = 0
    for number, event in enumerate(log["generations"], 1):
        _fields(event, GEN_FIELDS, "generation")
        count = min(29, budget - calls)
        complete = count == 29
        for name, expected in (("generation", number), ("start_call", calls + 1),
                               ("end_call", calls + count), ("complete", complete),
                               ("population_before", population), ("p_m", probability),
                               ("stagnation_before", stagnant), ("record_before", record_profit),
                               ("rng_before", _states(generators))):
            _same(event[name], expected, name + " before generation")
        record_before_generation = record_profit
        keys = [_key(scores[reference], capacity) for reference in population]
        winning_key = max(keys)
        elite_index = _choose([index for index, key in enumerate(keys) if key == winning_key],
                              generators["ties"])
        _same(event["elite_index"], elite_index, "elite tie resolution")
        references, distances = [], []
        for _ in range(count):
            child = log["candidates"][calls]
            _fields(child, CHILD_FIELDS, "candidate")
            tournaments, parents = [], []
            for _parent in range(2):
                positions = [int(generators["selection"].integers(MU)),
                             int(generators["selection"].integers(MU))]
                tournaments.append(positions)
                winner = max(keys[position] for position in positions)
                parents.append(_choose([position for position in positions if keys[position] == winner],
                                       generators["ties"]))
            parent_refs = [population[position] for position in parents]
            first, second = [masks[reference] for reference in parent_refs]
            distance = sum(first[index] != second[index] for index in range(n))
            distances.append(distance)
            crossed = bool(generators["branch"].random() < 0.9)
            if crossed:
                choices = generators["crossover"].random(n) < 0.5
                pre_mask = "".join(first[index] if choices[index] else second[index]
                                   for index in range(n))
            else:
                pre_mask = first
            mutation_flags = generators["mutation"].random(n) < probability
            mutation_bits = [index for index, changed in enumerate(mutation_flags) if changed]
            mask = "".join(("0" if bit == "1" else "1") if mutation_flags[index] else bit
                           for index, bit in enumerate(pre_mask))
            score = _score(problem, mask)
            # This additional evaluation is independent POSTSEARCH work. The
            # producer logged only a mask and was never allowed to query it.
            pre_score = _score(problem, pre_mask)
            pre_novel = pre_mask != first and pre_mask != second
            pre_better_both = pre_score["feasible"] and all(
                _key(pre_score, capacity) > _key(scores[reference], capacity)
                for reference in parent_refs)
            pre_above_record = pre_score["feasible"] and (
                record_profit is None or pre_score["profit"] > record_profit)
            strict_record = score["feasible"] and (
                record_profit is None or score["profit"] > record_profit)
            duplicate = mask in seen
            seen.add(mask)
            duplicates += int(duplicate)
            infeasible += int(not score["feasible"])
            calls += 1
            if strict_record:
                record_mask, record_profit, record_call = mask, score["profit"], calls
                record_events.append({"q": calls, "profit": record_profit})
            expected_child = {
                "call": calls, "generation": number, "tournaments": tournaments,
                "parent_indices": parents, "crossover": crossed, "pre_mask": pre_mask,
                "mutation_bits": mutation_bits, "mask": mask, **score,
                "duplicate": duplicate, "record_profit": record_profit,
                "record_call": record_call, "parent_distance": distance,
            }
            _same(child, expected_child, "candidate replay at query " + str(calls))
            bucket = operator_bins[distance]
            bucket["total"] += 1
            if crossed:
                bucket["crossed"] += 1
                bucket["novel_crossed"] += int(pre_novel)
                bucket["feasible_crossed"] += int(pre_score["feasible"])
                bucket["better_both_crossed"] += int(pre_better_both)
            candidate_metrics.append({
                "q": calls, "parent_refs": parent_refs, "parent_distance": distance,
                "crossed": crossed, "pre_weight": pre_score["weight"],
                "pre_profit": pre_score["profit"], "pre_feasible": pre_score["feasible"],
                "pre_novel": pre_novel, "pre_better_both": pre_better_both,
                "duplicate": duplicate, "strict_record": strict_record,
                "mutation_created_record": strict_record and not pre_above_record,
                "mutation_preserved_record": strict_record and pre_above_record,
                "mutation_lost_record": pre_above_record and not strict_record,
            })
            references.append(len(masks))
            masks.append(mask)
            scores.append(score)

        mean = _reference_mean(distances, n)
        total = mean * len(distances)
        exact_values = {
            "parent_distances": distances, "novelty_sum_numerator": total.numerator,
            "novelty_sum_denominator": total.denominator,
            "novelty_mean_numerator": mean.numerator,
            "novelty_mean_denominator": mean.denominator,
            "gate_allows_increase": mean <= Fraction(1, 2) if complete else None,
            "record_after": record_profit,
        }
        for name, expected in exact_values.items():
            _same(event[name], expected, "independent exact generation " + name)
        if complete:
            success = record_profit is not None and (
                record_before_generation is None or record_profit > record_before_generation)
            next_probability, next_stagnant, feedback = _feedback(
                n, probability, stagnant, success, method, mean)
            next_population = [population[elite_index], *references]
            full_generations += 1
        else:
            next_probability, next_stagnant, feedback = probability, stagnant, "PARTIAL_NO_UPDATE"
            next_population = list(population)
            partial_children = count
        for name, expected in (("p_m_next", next_probability),
                               ("stagnation_after", next_stagnant),
                               ("controller_event", feedback),
                               ("population_after", next_population),
                               ("rng_after", _states(generators))):
            _same(event[name], expected, name + " after generation")
        generation_trace.append({
            "q": calls, "start_q": calls - count + 1, "complete": complete,
            "p_m": probability, "p_m_next": next_probability,
            "stagnation_before": stagnant, "stagnation_after": next_stagnant,
            "mean_novelty": float(mean), "parent_distances": distances,
            "gate_allows_increase": exact_values["gate_allows_increase"],
            "controller_event": feedback,
        })
        population, probability, stagnant = next_population, next_probability, next_stagnant
        population_trace.append(_population_point(calls, complete, population, masks, scores,
                                                  record_mask, n))

    _same(log["rng_final"], _states(generators), "final RNG states")
    summary = {
        "new_calls": budget, "physical_evaluations": budget,
        "known_score_validation_evaluations": MU, "duplicate_calls": duplicates,
        "infeasible_calls": infeasible, "full_generations": full_generations,
        "partial_children": partial_children, "best_mask": record_mask,
        "best_profit": record_profit, "best_call": record_call,
        "final_population": list(population), "final_mutation_probability": probability,
    }
    _same(log["summary"], summary, "independently reconstructed summary")
    return {
        "verification_status": "VERIFIED", "new_calls": calls,
        "independent_score_checks": MU + 2 * calls, "initial_score_checks": MU,
        "final_score_checks": calls, "premutation_score_checks": calls,
        "completed_generations": full_generations,
        "partial_generations": int(partial_children > 0), "duplicate_candidates": duplicates,
        "record_profit": record_profit, "record_call": record_call,
        "final_population_refs": population, "final_p_m": probability,
        "final_stagnation": stagnant, "summary": summary,
        "timing_status": "OBSERVATIONAL_VALIDATED_NOT_RECONSTRUCTED",
        "timing_ns": copy.deepcopy(log["timing_ns"]),
        "derived_metrics": {
            "record_events": record_events, "population_trace": population_trace,
            "generation_trace": generation_trace, "operator_bins": operator_bins,
            "candidate_metrics": candidate_metrics,
        },
    }

"""Published complete generations; the only arm difference is applied lambda."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any, Callable

import numpy as np

from local_optima.generation import run_generation
from lambda_response_study.oracle import expected_lambda, mask, score, validate_trace

def run_search(objective: Callable, *, problem: str, arm: str, initial_mask,
               initial_score: float, search_seed: int, on_generation_completed=None) -> dict[str, Any]:
    if problem not in ("onemax", "census") or arm not in ("adaptive", "fixed10"):
        raise ValueError("unknown problem or arm")
    if type(search_seed) is not int or search_seed < 0:
        raise ValueError("search_seed must be nonnegative integer")
    parent, value = mask(initial_mask), score(initial_score)
    if problem == "onemax" and (sum(parent) or value):
        raise ValueError("OneMax initial state must be zero")
    if problem == "census" and sum(parent) != 1:
        raise ValueError("Census initial state must be a single-feature mask")
    rng = np.random.default_rng(search_seed)
    initial_rng = deepcopy(rng.bit_generator.state)
    initial = {"mask": list(parent), "score": value, "lambda": 10.0, "call": 0}
    lam, best, records, generations = 10.0, value, [], []
    known, seen = {parent: value}, set()

    def evaluate(child):
        child = mask(child)
        observed = score(objective(child))
        if child in known and known[child] != observed:
            raise ValueError("identical mask received different deterministic scores")
        known[child] = observed
        seen.add(child)
        return observed

    for number in range(1, 21):
        rng_before = deepcopy(rng.bit_generator.state)
        result = run_generation(evaluate, parent=parent, parent_fitness=value,
                                lambda_real=lam, rng=rng, update_factor=1.5,
                                reset=False, call_offset=len(records))
        applied = result.lambda_after if arm == "adaptive" else 10.0
        expected = expected_lambda(lam, strict_success=result.selection.candidate_fitness[0] > value, arm=arm)
        for raw in result.evaluations:
            item = asdict(raw)
            s = item.pop("fitness")[0]
            best = max(best, s)
            item.update({"mask": list(raw.mask), "generation": number, "score": s,
                         "feature_count": sum(raw.mask), "best_so_far_score": best,
                         "kind": "onemax" if problem == "onemax" else
                         ("classification" if sum(raw.mask) else "empty_penalty")})
            records.append(item)
        selection = result.selection
        event = {
            "generation": number, "calls_before": result.call_offset, "calls_after": result.calls_after,
            "parent_before": list(parent), "parent_score_before": value,
            "parent_after": list(result.parent_after), "parent_score_after": result.parent_fitness_after[0],
            "candidate_mask": list(selection.candidate), "candidate_score": selection.candidate_fitness[0],
            "strict_success": result.strict_success, "accepted": result.accepted,
            "parent_changed": result.parent_changed, "lambda_before": lam,
            "proposed_lambda_after": result.lambda_after, "applied_lambda_after": applied,
            "expected_lambda_after": expected, "lambda_residual": applied - expected,
            "score_delta_pp": 100 * (selection.candidate_fitness[0] - value),
            "lambda_delta_percent": 100 * (applied / lam - 1),
            "offspring_count": result.offspring_count, "mutation_probability": result.mutation_probability,
            "crossover_probability": result.crossover_probability, "mutation_strength": result.mutation_strength,
            "selected_mutant_index": selection.selected_mutant_index,
            "selected_mutant_mask": list(selection.selected_mutant),
            "selected_mutant_score": selection.selected_mutant_fitness[0],
            "candidate_phase": selection.candidate_phase, "candidate_phase_index": selection.candidate_phase_index,
            "eligible_count": selection.eligible_count, "reset_event": result.reset_event,
            "RNG_state_before": rng_before, "RNG_state_after": deepcopy(rng.bit_generator.state),
        }
        generations.append(event)
        parent, value, lam = result.parent_after, result.parent_fitness_after[0], applied
        if on_generation_completed is not None:
            on_generation_completed({"problem": problem, "arm": arm, "completed_generations": number,
                                     "physical_calls": len(records), "parent_score": value, "lambda": lam})
    result = {"schema": "eu26-21-lambda-response-search-v1", "problem": problem, "arm": arm,
              "search_seed": search_seed, "initial": initial, "final": {"mask": list(parent), "score": value, "lambda": lam},
              "evaluations": records, "generation_trace": generations,
              "rng_initial_state": initial_rng, "rng_final_state": deepcopy(rng.bit_generator.state),
              "counts": {"physical_calls": len(records),
                        "actual_tree_fits": sum(bool(sum(r["mask"])) for r in records) if problem == "census" else 0,
                        "unique_masks": len(seen), "duplicate_queries": len(records) - len(seen)},
              "model_check": {"generation_count": 20, "mismatches": 0,
                              "max_abs_residual": max(abs(r["lambda_residual"]) for r in generations)}}
    validate_trace(result)
    return result

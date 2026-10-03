"""Prospective, budget-exact adaptive/fixed-lambda searches.

Only the lambda update differs between the two arms. The known certified
parent in an escape run is a query at index zero, not an objective invocation.
Frozen historical runners are deliberately not modified or delegated to here.
"""
from __future__ import annotations

import hashlib
import json
import math
from numbers import Integral, Real
import statistics
from typing import Any, Callable, Sequence

import numpy as np

from hybrid_1.core import (
    Fitness, Mask, best_index, controls, make_crossovers, make_mutants, next_lambda,
)
from local_optima.generation import select_from_chosen_mutant


def validate_mask(mask: Sequence[int], dimension: int | None = None) -> Mask:
    """Reject coercible, nonbinary values before any scientific invocation."""
    values = tuple(mask)
    if len(values) < 2 or (dimension is not None and len(values) != dimension):
        raise ValueError("mask dimension must agree and be at least two")
    if any(
        isinstance(bit, (bool, np.bool_)) or not isinstance(bit, Integral)
        or bit not in (0, 1) for bit in values
    ):
        raise ValueError("mask entries must be binary integers")
    return tuple(int(bit) for bit in values)


def validate_fitness(value: Any) -> Fitness:
    components = value if isinstance(value, (tuple, list)) else (value, 0.0)
    if len(components) != 2:
        raise ValueError("fitness must be scalar or contain two components")
    if any(
        isinstance(item, (bool, np.bool_)) or not isinstance(item, Real)
        for item in components
    ):
        raise TypeError("fitness components must be nonboolean real numbers")
    score = (float(components[0]), float(components[1]))
    if not all(math.isfinite(item) for item in score):
        raise ValueError("fitness components must be finite")
    return score


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a nonboolean integer")
    result = int(value)
    if result < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return result


def _hash_mask(mask: Mask) -> str:
    encoded = json.dumps(list(mask), separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _terminal(mask: Mask, fitness: Fitness, call: int) -> dict[str, Any]:
    return {
        "call": call, "mask": list(mask), "mask_sha256": _hash_mask(mask),
        "fitness": list(fitness), "validation_weighted_balanced_accuracy": fitness[0],
        "negative_selected_feature_fraction": fitness[1],
        "selected_feature_count": sum(mask),
    }


def run_lambda_search(
    objective: Callable[[Mask], Any],
    *,
    seed: int,
    mode: str = "adaptive",
    budget: int = 400,
    initial_masks: Sequence[Sequence[int]] | None = None,
    initial_parent: Sequence[int] | None = None,
    initial_fitness: Any = None,
    lambda_initial: float = 1.0,
    update_factor: float = 1.5,
) -> dict[str, Any]:
    """Run identical search kernels, with either adaptive or fixed-one control.

    A comparison run supplies ordered initial masks whose calls are part of the
    limit. An escape run supplies a previously certified parent and score. Each
    generation has equal mutation/crossover counts, including the paired tail;
    truncating counts never changes p=lambda/n or c=1/lambda.
    """
    if not callable(objective):
        raise TypeError("objective must be callable")
    seed = _integer(seed, "seed")
    budget = _integer(budget, "budget", minimum=1)
    if mode not in ("adaptive", "fixed1"):
        raise ValueError("mode must be adaptive or fixed1")
    known_parent = initial_parent is not None
    if known_parent == (initial_masks is not None):
        raise ValueError("provide either initial masks or a known parent")
    if known_parent:
        if initial_fitness is None:
            raise ValueError("a known parent requires its certified fitness")
        parent = validate_mask(initial_parent)
        parent_fitness = validate_fitness(initial_fitness)
        masks: list[Mask] = []
        dimension = len(parent)
    else:
        if initial_fitness is not None:
            raise ValueError("initial fitness only belongs to a known parent")
        if not initial_masks:
            raise ValueError("initial masks must not be empty")
        dimension = len(initial_masks[0])
        masks = [validate_mask(mask, dimension) for mask in initial_masks]
        if len(masks) > budget:
            raise ValueError("initial masks exceed the objective-call limit")
    if (budget - len(masks)) % 2:
        raise ValueError("the mutant/crossover remainder must be even")
    if isinstance(lambda_initial, (bool, np.bool_)) or not isinstance(lambda_initial, Real):
        raise TypeError("initial lambda must be a nonboolean real number")
    controls(float(lambda_initial), dimension)
    if mode == "fixed1" and float(lambda_initial) != 1.0:
        raise ValueError("the fixed-one arm must start at lambda=1")
    if isinstance(update_factor, (bool, np.bool_)) or not isinstance(update_factor, Real):
        raise TypeError("update factor must be a nonboolean real number")
    factor = float(update_factor)
    if not math.isfinite(factor) or factor <= 1:
        raise ValueError("update factor must be finite and greater than one")

    rng = np.random.default_rng(seed)
    records: list[dict[str, Any]] = []
    generations: list[dict[str, Any]] = []
    terminal_mask = parent if known_parent else None
    terminal_fitness = parent_fitness if known_parent else None
    terminal_call: int | None = 0 if known_parent else None
    best_wba = parent_fitness[0] if known_parent else None
    start_wba = parent_fitness[0] if known_parent else None
    initial = _terminal(parent, parent_fitness, 0) if known_parent else None
    first_exit_call: int | None = None
    first_accepted_exit_call: int | None = None
    observed: dict[Mask, Fitness] = {parent: parent_fitness} if known_parent else {}

    def evaluate(mask: Mask, phase: str, phase_index: int, generation: int) -> Fitness:
        nonlocal terminal_mask, terminal_fitness, terminal_call, best_wba, first_exit_call
        if len(records) >= budget:
            raise RuntimeError("objective-call limit exhausted")
        score = validate_fitness(objective(mask))
        if mask in observed and observed[mask] != score:
            raise ValueError("deterministic objective did not reproduce a previously observed mask score")
        observed[mask] = score
        call = len(records) + 1
        improved = terminal_fitness is None or score > terminal_fitness
        if improved:
            terminal_mask, terminal_fitness, terminal_call = mask, score, call
        best_wba = score[0] if best_wba is None else max(best_wba, score[0])
        if known_parent and first_exit_call is None and score[0] > start_wba:
            first_exit_call = call
        records.append({
            "call": call, "phase": phase, "phase_index": phase_index,
            "generation": generation, "mask": list(mask), "mask_sha256": _hash_mask(mask),
            "fitness": list(score), "validation_weighted_balanced_accuracy": score[0],
            "negative_selected_feature_fraction": score[1], "selected_feature_count": sum(mask),
            "best_so_far_weighted_balanced_accuracy": best_wba,
            "terminal_best_update": improved,
        })
        return score

    if not known_parent:
        scores = [evaluate(mask, "initial_population", index, 0) for index, mask in enumerate(masks)]
        initial_index = best_index(scores, rng)
        parent, parent_fitness = masks[initial_index], scores[initial_index]
    else:
        initial_index = None
    lambda_real = float(lambda_initial)
    any_tail = False
    phase = "known_parent" if known_parent else "initial_population"

    while len(records) < budget:
        ctl = controls(lambda_real, dimension)
        count = min(ctl.offspring_count, (budget - len(records)) // 2)
        if count < 1:
            raise RuntimeError("unpaired objective invocation remains")
        truncated = count < ctl.offspring_count
        generation = len(generations) + 1
        calls_before = len(records)
        before_parent, before_score = parent, parent_fitness
        strength = int(rng.binomial(dimension, ctl.mutation_probability))
        mutants = make_mutants(parent, count=count, strength=strength, rng=rng)
        mutant_scores = [evaluate(mask, "mutation", index, generation) for index, mask in enumerate(mutants)]
        chosen_index = best_index(mutant_scores, rng)
        crossovers = make_crossovers(
            parent, mutants[chosen_index], count=count,
            probability=ctl.crossover_probability, rng=rng,
        )
        crossover_scores = [evaluate(mask, "crossover", index, generation) for index, mask in enumerate(crossovers)]
        selection = select_from_chosen_mutant(
            parent=parent, parent_fitness=parent_fitness,
            mutants=mutants, mutant_fitness=mutant_scores,
            selected_mutant_index=chosen_index, crossovers=crossovers,
            crossover_fitness=crossover_scores, rng=rng,
        )
        strict_success = selection.candidate_fitness > parent_fitness
        accepted = selection.candidate_fitness >= parent_fitness
        if accepted:
            parent, parent_fitness = selection.candidate, selection.candidate_fitness
        calls_after = len(records)
        accepted_at = calls_after if accepted and selection.eligible_count else None
        accepted_exit = bool(known_parent and accepted_at is not None and parent_fitness[0] > start_wba)
        if accepted_exit and first_accepted_exit_call is None:
            first_accepted_exit_call = calls_after
        if mode == "adaptive":
            lambda_after, reset_event = next_lambda(
                lambda_real, strict_success=strict_success, update_factor=factor,
                dimension=dimension, reset=False,
            )
            if reset_event:
                raise RuntimeError("reset-disabled arm emitted a reset")
        else:
            lambda_after = 1.0
        generation_records = records[calls_before:]
        generations.append({
            "generation": generation, "calls_before": calls_before, "calls_after": calls_after,
            "lambda_before": lambda_real, "lambda_after": lambda_after,
            "planned_offspring_count_per_phase": ctl.offspring_count,
            "evaluated_offspring_count_per_phase": count,
            "mutation_probability": ctl.mutation_probability,
            "crossover_probability": ctl.crossover_probability,
            "mutation_strength": strength, "parent_before": list(before_parent),
            "parent_fitness_before": list(before_score), "selected_mutant_index": chosen_index,
            "selected_mutant_mask": list(selection.selected_mutant),
            "selected_mutant_fitness": list(selection.selected_mutant_fitness),
            "candidate_mask": list(selection.candidate), "candidate_fitness": list(selection.candidate_fitness),
            "candidate_phase": selection.candidate_phase,
            "candidate_phase_index": selection.candidate_phase_index,
            "eligible_count": selection.eligible_count,
            "parent_after": list(parent), "parent_fitness_after": list(parent_fitness),
            "strict_success": strict_success, "accepted": accepted,
            "parent_changed": parent != before_parent, "accepted_at_call": accepted_at,
            "first_strict_improvement_call": next(
                (row["call"] for row in generation_records if tuple(row["fitness"]) > before_score), None,
            ),
            "first_higher_start_wba_call": next(
                (row["call"] for row in generation_records if known_parent and row["fitness"][0] > start_wba), None,
            ),
            "accepted_higher_start_wba": accepted_exit,
            "tail_truncated": truncated, "reset_event": False,
        })
        lambda_real = lambda_after
        any_tail = any_tail or truncated
        phase = "paired_mutant_crossover_tail" if truncated else "complete_lambda_generation"

    if terminal_mask is None or terminal_fitness is None or terminal_call is None:
        raise RuntimeError("search has no terminal mask")
    auc = statistics.fmean(row["best_so_far_weighted_balanced_accuracy"] for row in records)
    tail_auc = None if known_parent or len(masks) == budget else statistics.fmean(
        row["best_so_far_weighted_balanced_accuracy"] for row in records[len(masks):]
    )
    return {
        "schema": "eu26-21-local-optima-search-v1", "seed": seed,
        "arm": "lambda_adaptive" if mode == "adaptive" else "lambda_fixed1",
        "objective_calls": len(records), "initial_population_calls": len(masks),
        "initial": initial, "terminal": _terminal(terminal_mask, terminal_fitness, terminal_call),
        "normalized_auc_best_so_far_validation_wba_1_400": auc,
        "normalized_auc_best_so_far_validation_wba_51_400": tail_auc,
        "reset": False, "reset_events": 0, "termination_phase": phase,
        "terminal_state": {
            "generation_count": len(generations), "final_lambda": lambda_real,
            "parent_mask": list(parent), "parent_mask_sha256": _hash_mask(parent),
            "parent_fitness": list(parent_fitness), "tail_truncated": any_tail,
            "initial_parent_index": initial_index, "workers": 1,
        },
        "escape": None if not known_parent else {
            "first_exit_call": first_exit_call, "first_accepted_exit_call": first_accepted_exit_call,
            "censored": first_exit_call is None,
            "restricted_calls": budget if first_exit_call is None else first_exit_call,
        },
        "evaluations": records, "generation_trace": generations,
    }

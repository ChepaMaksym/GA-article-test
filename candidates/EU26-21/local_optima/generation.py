"""One auditable generation, separate from both frozen historical runners.

The caller supplies an already evaluated parent from the same deterministic
objective. This component does not define initialization, a run budget, a
partial-generation rule, an escape target, or a scientific seed campaign.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral, Real
from typing import Any, Callable, Protocol, Sequence

import numpy as np

from hybrid_1.core import (
    Fitness,
    Mask,
    best_index,
    controls,
    make_crossovers,
    make_mutants,
    next_lambda,
)


class RandomSource(Protocol):
    """NumPy Generator interface, also permitting controlled CI random tapes."""

    def binomial(self, *args: Any, **kwargs: Any) -> Any: ...

    def choice(self, *args: Any, **kwargs: Any) -> Any: ...

    def random(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class EvaluationRecord:
    call: int
    phase: str
    phase_index: int
    mask: Mask
    fitness: Fitness


@dataclass(frozen=True)
class GenerationSelection:
    selected_mutant_index: int
    selected_mutant: Mask
    selected_mutant_fitness: Fitness
    candidate: Mask
    candidate_fitness: Fitness
    candidate_phase: str
    candidate_phase_index: int | None
    eligible_count: int


@dataclass(frozen=True)
class GenerationResult:
    parent_before: Mask
    parent_fitness_before: Fitness
    parent_after: Mask
    parent_fitness_after: Fitness
    lambda_before: float
    lambda_after: float
    offspring_count: int
    mutation_probability: float
    crossover_probability: float
    mutation_strength: int
    selection: GenerationSelection
    strict_success: bool
    accepted: bool
    parent_changed: bool
    reset_event: bool
    call_offset: int
    calls_after: int
    objective_calls: int
    first_strict_improvement_call: int | None
    accepted_at_call: int | None
    evaluations: tuple[EvaluationRecord, ...]


def _mask(value: Sequence[int], dimension: int | None = None) -> Mask:
    values = tuple(value)
    if len(values) < 2 or (dimension is not None and len(values) != dimension):
        raise ValueError("mask dimension must agree and be at least two")
    if any(
        isinstance(bit, (bool, np.bool_))
        or not isinstance(bit, Integral)
        or bit not in (0, 1)
        for bit in values
    ):
        raise ValueError("mask entries must be binary integers")
    return tuple(int(bit) for bit in values)


def _fitness(value: Any) -> Fitness:
    components = value if isinstance(value, (tuple, list)) else (value, 0.0)
    if len(components) != 2:
        raise ValueError("fitness must be scalar or have two components")
    if any(
        isinstance(item, (bool, np.bool_)) or not isinstance(item, Real)
        for item in components
    ):
        raise TypeError("fitness components must be non-boolean real numbers")
    result = (float(components[0]), float(components[1]))
    if not all(math.isfinite(item) for item in result):
        raise ValueError("fitness components must be finite")
    return result


def _integer(value: Any, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a non-boolean integer")
    return int(value)


def _validate_rng(rng: RandomSource) -> None:
    if any(not callable(getattr(rng, name, None)) for name in ("choice", "binomial", "random")):
        raise TypeError("rng must provide choice, binomial and random methods")


def select_from_chosen_mutant(
    *,
    parent: Sequence[int],
    parent_fitness: Any,
    mutants: Sequence[Sequence[int]],
    mutant_fitness: Sequence[Any],
    selected_mutant_index: int,
    crossovers: Sequence[Sequence[int]],
    crossover_fitness: Sequence[Any],
    rng: RandomSource,
) -> GenerationSelection:
    """Reuse one chosen maximizer; only the final candidate is sampled here.

    Phase indices are zero-based. Parent copies are excluded, but all other
    duplicates remain distinct entries in the final sampling pool.
    """
    parent_mask = _mask(parent)
    parent_score = _fitness(parent_fitness)
    index = _integer(selected_mutant_index, "selected_mutant_index")
    if not mutants or len(mutants) != len(mutant_fitness):
        raise ValueError("mutant masks and fitness must be non-empty and aligned")
    if len(crossovers) != len(crossover_fitness):
        raise ValueError("crossover masks and fitness must be aligned")
    mutant_masks = tuple(_mask(mask, len(parent_mask)) for mask in mutants)
    mutant_scores = tuple(_fitness(score) for score in mutant_fitness)
    crossover_masks = tuple(_mask(mask, len(parent_mask)) for mask in crossovers)
    crossover_scores = tuple(_fitness(score) for score in crossover_fitness)
    if not 0 <= index < len(mutant_masks):
        raise ValueError("selected_mutant_index lies outside the mutant pool")
    if mutant_scores[index] != max(mutant_scores):
        raise ValueError("selected mutant must maximize mutant fitness")
    _validate_rng(rng)
    chosen_mask, chosen_score = mutant_masks[index], mutant_scores[index]
    pool = [(chosen_mask, chosen_score, "mutation", index)] + [
        (mask, score, "crossover", child_index)
        for child_index, (mask, score) in enumerate(zip(crossover_masks, crossover_scores))
    ]
    eligible = [item for item in pool if item[0] != parent_mask]
    if eligible:
        final_index = best_index([item[1] for item in eligible], rng)
        candidate, score, phase, phase_index = eligible[final_index]
    else:
        candidate, score, phase, phase_index = parent_mask, parent_score, "parent", None
    return GenerationSelection(
        index, chosen_mask, chosen_score, candidate, score, phase, phase_index, len(eligible)
    )


def run_generation(
    objective: Callable[[Mask], Any],
    *,
    parent: Sequence[int],
    parent_fitness: Any,
    lambda_real: float,
    update_factor: float,
    reset: bool,
    rng: RandomSource,
    call_offset: int = 0,
) -> GenerationResult:
    """Execute exactly one complete generation with an immutable query ledger.

    Static inputs are checked before objective calls or random draws. A bad
    objective return fails immediately after that invocation; a partial ledger
    is not returned as a successful generation. No parent reevaluation occurs.
    """
    if not callable(objective):
        raise TypeError("objective must be callable")
    parent_mask = _mask(parent)
    parent_score = _fitness(parent_fitness)
    offset = _integer(call_offset, "call_offset")
    if offset < 0:
        raise ValueError("call_offset must be non-negative")
    if isinstance(lambda_real, (bool, np.bool_)) or not isinstance(lambda_real, Real):
        raise TypeError("lambda must be a non-boolean real number")
    ctl = controls(float(lambda_real), len(parent_mask))
    if not isinstance(reset, bool):
        raise TypeError("reset must be boolean")
    if isinstance(update_factor, (bool, np.bool_)) or not isinstance(update_factor, Real):
        raise TypeError("update_factor must be a non-boolean real number")
    factor = float(update_factor)
    if not math.isfinite(factor) or factor <= 1.0:
        raise ValueError("update_factor must be finite and greater than one")
    _validate_rng(rng)

    records: list[EvaluationRecord] = []

    def evaluate(masks: Sequence[Mask], phase: str) -> list[Fitness]:
        scores: list[Fitness] = []
        for phase_index, mask in enumerate(masks):
            score = _fitness(objective(mask))
            records.append(EvaluationRecord(offset + len(records) + 1, phase, phase_index, mask, score))
            scores.append(score)
        return scores

    strength = int(rng.binomial(len(parent_mask), ctl.mutation_probability))
    mutants = make_mutants(parent_mask, count=ctl.offspring_count, strength=strength, rng=rng)
    mutant_scores = evaluate(mutants, "mutation")
    chosen_index = best_index(mutant_scores, rng)
    crossovers = make_crossovers(
        parent_mask, mutants[chosen_index], count=ctl.offspring_count,
        probability=ctl.crossover_probability, rng=rng,
    )
    crossover_scores = evaluate(crossovers, "crossover")
    selection = select_from_chosen_mutant(
        parent=parent_mask, parent_fitness=parent_score,
        mutants=mutants, mutant_fitness=mutant_scores,
        selected_mutant_index=chosen_index,
        crossovers=crossovers, crossover_fitness=crossover_scores, rng=rng,
    )
    strict_success = selection.candidate_fitness > parent_score
    accepted = selection.candidate_fitness >= parent_score
    parent_after = selection.candidate if accepted else parent_mask
    score_after = selection.candidate_fitness if accepted else parent_score
    lambda_after, reset_event = next_lambda(
        ctl.lambda_real, strict_success=strict_success, update_factor=factor,
        dimension=len(parent_mask), reset=reset,
    )
    first_improvement = next((row.call for row in records if row.fitness > parent_score), None)
    calls_after = offset + len(records)
    return GenerationResult(
        parent_before=parent_mask, parent_fitness_before=parent_score,
        parent_after=parent_after, parent_fitness_after=score_after,
        lambda_before=ctl.lambda_real, lambda_after=lambda_after,
        offspring_count=ctl.offspring_count,
        mutation_probability=ctl.mutation_probability,
        crossover_probability=ctl.crossover_probability, mutation_strength=strength,
        selection=selection, strict_success=strict_success, accepted=accepted,
        parent_changed=parent_after != parent_mask, reset_event=reset_event,
        call_offset=offset, calls_after=calls_after, objective_calls=len(records),
        first_strict_improvement_call=first_improvement,
        accepted_at_call=calls_after if accepted and selection.eligible_count else None,
        evaluations=tuple(records),
    )

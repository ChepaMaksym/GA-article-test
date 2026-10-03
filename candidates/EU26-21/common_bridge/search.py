"""Budget-exact searches for the frozen EU26-21 common bridge.

The two public search functions receive only a validation objective.  Dataset
preparation and the single terminal holdout evaluation live in ``run_seed`` so
that test data cannot enter either optimizer.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from numbers import Integral
import random
import statistics
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple

import numpy as np

from hybrid_1.core import (
    Fitness,
    Mask,
    Objective,
    best_index,
    controls,
    make_crossovers,
    make_mutants,
    next_lambda,
    normalize_fitness,
    validate_mask as _legacy_validate_mask,
)


DEFAULT_DIMENSION = 40
DEFAULT_BUDGET = 400


def validate_mask(mask: Sequence[int], dimension: Optional[int] = None) -> Mask:
    """Reject coercible strings/floats before the historical core casts to int."""
    values = tuple(mask)
    if any(
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, Integral)
        or value not in (0, 1)
        for value in values
    ):
        raise ValueError("mask entries must be binary integers")
    return _legacy_validate_mask(values, dimension)


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class EvaluationRecord:
    """One logical objective invocation; repeated masks remain separate."""

    call: int
    mask: Mask
    mask_sha256: str
    validation_weighted_balanced_accuracy: float
    negative_selected_feature_fraction: float
    selected_feature_count: int
    best_so_far_weighted_balanced_accuracy: float
    terminal_best_update: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mask"] = list(self.mask)
        return payload


class BudgetLedger:
    """Count, validate, and retain exactly one record per objective call.

    The ledger deliberately has no memoization path.  A duplicate mask invokes
    the supplied objective again and consumes another logical call.  The
    terminal optimizer result is the lexicographic maximum over the queried
    prefix; an exact full-fitness tie keeps the earlier call.
    """

    def __init__(
        self,
        objective: Objective,
        *,
        budget: int = DEFAULT_BUDGET,
        dimension: int = DEFAULT_DIMENSION,
    ) -> None:
        if not callable(objective):
            raise TypeError("objective must be callable")
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
            raise ValueError("budget must be a positive integer")
        if (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension < 2
        ):
            raise ValueError("dimension must be an integer of at least two")
        self._objective = objective
        self.budget = budget
        self.dimension = dimension
        self._records: list[EvaluationRecord] = []
        self._terminal_mask: Optional[Mask] = None
        self._terminal_fitness: Optional[Fitness] = None
        self._terminal_call: Optional[int] = None
        self._best_primary: Optional[float] = None

    @property
    def calls(self) -> int:
        return len(self._records)

    @property
    def remaining(self) -> int:
        return self.budget - self.calls

    @property
    def records(self) -> Tuple[EvaluationRecord, ...]:
        return tuple(self._records)

    @property
    def terminal_mask(self) -> Mask:
        if self._terminal_mask is None:
            raise RuntimeError("ledger has no evaluations")
        return self._terminal_mask

    @property
    def terminal_fitness(self) -> Fitness:
        if self._terminal_fitness is None:
            raise RuntimeError("ledger has no evaluations")
        return self._terminal_fitness

    @property
    def terminal_call(self) -> int:
        if self._terminal_call is None:
            raise RuntimeError("ledger has no evaluations")
        return self._terminal_call

    def evaluate(self, mask: Sequence[int]) -> Fitness:
        if self.calls >= self.budget:
            raise RuntimeError("objective-call budget exhausted")
        validated = validate_mask(mask, self.dimension)
        fitness = normalize_fitness(self._objective(validated))
        call = self.calls + 1
        terminal_update = (
            self._terminal_fitness is None or fitness > self._terminal_fitness
        )
        if terminal_update:
            self._terminal_mask = validated
            self._terminal_fitness = fitness
            self._terminal_call = call
        if self._best_primary is None or fitness[0] > self._best_primary:
            self._best_primary = fitness[0]
        self._records.append(
            EvaluationRecord(
                call=call,
                mask=validated,
                mask_sha256=_canonical_sha256(list(validated)),
                validation_weighted_balanced_accuracy=fitness[0],
                negative_selected_feature_fraction=fitness[1],
                selected_feature_count=sum(validated),
                best_so_far_weighted_balanced_accuracy=float(self._best_primary),
                terminal_best_update=terminal_update,
            )
        )
        return fitness

    def evaluate_many(self, masks: Sequence[Sequence[int]]) -> list[Fitness]:
        if len(masks) > self.remaining:
            raise RuntimeError("objective batch exceeds remaining call budget")
        return [self.evaluate(mask) for mask in masks]

    def normalized_auc(self, first_call: int = 1) -> float:
        if self.calls != self.budget:
            raise RuntimeError("AUC is defined only after the exact budget")
        if not 1 <= first_call <= self.budget:
            raise ValueError("AUC first call lies outside the ledger")
        values = [
            record.best_so_far_weighted_balanced_accuracy
            for record in self._records[first_call - 1 :]
        ]
        return float(statistics.fmean(values))


@dataclass(frozen=True)
class SearchResult:
    arm: str
    objective_calls: int
    initial_population_calls: int
    terminal_mask: Mask
    terminal_fitness: Fitness
    terminal_call: int
    normalized_auc_best_so_far_validation_wba_1_400: float
    normalized_auc_best_so_far_validation_wba_51_400: float
    reset: bool
    reset_events: int
    termination_phase: str
    terminal_state: Mapping[str, Any]
    evaluations: Tuple[EvaluationRecord, ...]
    generation_trace: Tuple[Mapping[str, Any], ...]

    def terminal_payload(self) -> dict[str, Any]:
        return {
            "call": self.terminal_call,
            "mask": list(self.terminal_mask),
            "mask_sha256": _canonical_sha256(list(self.terminal_mask)),
            "fitness": list(self.terminal_fitness),
            "validation_weighted_balanced_accuracy": self.terminal_fitness[0],
            "negative_selected_feature_fraction": self.terminal_fitness[1],
            "selected_feature_count": sum(self.terminal_mask),
        }

    def to_trace_dict(
        self,
        *,
        seed: int,
        provenance: Mapping[str, Any],
        pairing: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema": "eu26-21-common-bridge-trace-v1",
            "seed": seed,
            "arm": self.arm,
            "config_sha256": provenance["config_sha256"],
            "provenance": dict(provenance),
            "pairing": dict(pairing),
            "objective_calls": self.objective_calls,
            "initial_population_calls": self.initial_population_calls,
            "reset": self.reset,
            "reset_events": self.reset_events,
            "normalized_auc_best_so_far_validation_wba_1_400": (
                self.normalized_auc_best_so_far_validation_wba_1_400
            ),
            "normalized_auc_best_so_far_validation_wba_51_400": (
                self.normalized_auc_best_so_far_validation_wba_51_400
            ),
            "termination_phase": self.termination_phase,
            "terminal_state": dict(self.terminal_state),
            "terminal": self.terminal_payload(),
            "evaluations": [record.to_dict() for record in self.evaluations],
            "generation_trace": [dict(item) for item in self.generation_trace],
        }


HuxOperator = Callable[[Mask, Mask, random.Random], tuple[Mask, Mask]]
CataclysmicMutation = Callable[[Mask, float, random.Random], Mask]


@dataclass(frozen=True)
class _Candidate:
    mask: Mask
    fitness: Fitness


def _pinned_source_hux(
    first: Mask,
    second: Mask,
    rng: random.Random,
) -> tuple[Mask, Mask]:
    """Reproduce pinned ``Evolution.HUX(..., fixed=True)`` RNG semantics."""

    left = list(validate_mask(first))
    right = list(validate_mask(second, len(left)))
    differing = [index for index in range(len(left)) if left[index] != right[index]]
    if len(differing) <= 1:
        return tuple(left), tuple(right)

    # The pinned function draws a discarded random count before fixed HUX sets
    # the number to floor(HammingDistance / 2), once for each output child.
    rng.randrange(1, len(differing))
    count = len(differing) // 2
    first_positions = rng.sample(differing, count)
    child_first = list(left)
    for position in first_positions:
        child_first[position] = right[position]

    rng.randrange(1, len(differing))
    second_positions = rng.sample(differing, count)
    child_second = list(right)
    for position in second_positions:
        child_second[position] = left[position]
    return tuple(child_first), tuple(child_second)


def _pinned_source_cataclysmic_mutation(
    mask: Mask,
    probability: float,
    rng: random.Random,
) -> Mask:
    """Reproduce DEAP ``mutFlipBit(indpb=1/3)`` with an isolated stream."""

    validated = validate_mask(mask)
    return tuple(
        1 - value if rng.random() < probability else value
        for value in validated
    )


def _stable_best(
    candidates: Sequence[_Candidate],
    count: int,
) -> list[_Candidate]:
    if count < 1 or len(candidates) < count:
        raise ValueError("stable selection has insufficient candidates")
    return sorted(
        candidates,
        key=lambda candidate: (-candidate.fitness[0], -candidate.fitness[1]),
    )[:count]


def _search_result(
    *,
    arm: str,
    ledger: BudgetLedger,
    initial_population_calls: int,
    reset: bool,
    reset_events: int,
    termination_phase: str,
    terminal_state: Mapping[str, Any],
    generation_trace: Sequence[Mapping[str, Any]],
) -> SearchResult:
    if ledger.calls != ledger.budget:
        raise RuntimeError("search did not consume its exact objective-call budget")
    descriptive_first = 51 if ledger.budget >= 51 else 1
    return SearchResult(
        arm=arm,
        objective_calls=ledger.calls,
        initial_population_calls=initial_population_calls,
        terminal_mask=ledger.terminal_mask,
        terminal_fitness=ledger.terminal_fitness,
        terminal_call=ledger.terminal_call,
        normalized_auc_best_so_far_validation_wba_1_400=ledger.normalized_auc(1),
        normalized_auc_best_so_far_validation_wba_51_400=ledger.normalized_auc(
            descriptive_first
        ),
        reset=reset,
        reset_events=reset_events,
        termination_phase=termination_phase,
        terminal_state=dict(terminal_state),
        evaluations=ledger.records,
        generation_trace=tuple(dict(item) for item in generation_trace),
    )


def _validated_initial_masks(
    initial_masks: Sequence[Sequence[int]],
) -> tuple[list[Mask], int]:
    if not initial_masks:
        raise ValueError("initial masks must not be empty")
    dimension = len(initial_masks[0])
    if dimension < 2:
        raise ValueError("mask dimension must be at least two")
    return [validate_mask(mask, dimension) for mask in initial_masks], dimension


def run_harmonized_chc(
    objective: Objective,
    initial_masks: Sequence[Sequence[int]],
    *,
    seed: int,
    budget: int = DEFAULT_BUDGET,
    initial_distance: int = 10,
    cataclysmic_mutation_probability: float = 1.0 / 3.0,
    hux: Optional[HuxOperator] = None,
    cataclysmic_mutation: Optional[CataclysmicMutation] = None,
) -> SearchResult:
    """Run the harmonized pinned-source CHC state machine to an exact prefix."""

    masks, dimension = _validated_initial_masks(initial_masks)
    if len(masks) > budget:
        raise ValueError("initial population exceeds objective-call budget")
    if initial_distance < 0:
        raise ValueError("initial distance must be non-negative")
    if not 0.0 <= cataclysmic_mutation_probability <= 1.0:
        raise ValueError("cataclysmic mutation probability must lie in [0,1]")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")

    local_rng = random.Random(seed)
    hux_operator = hux or _pinned_source_hux
    mutation_operator = cataclysmic_mutation or _pinned_source_cataclysmic_mutation
    ledger = BudgetLedger(objective, budget=budget, dimension=dimension)
    population = [
        _Candidate(mask, fitness)
        for mask, fitness in zip(masks, ledger.evaluate_many(masks))
    ]
    history: list[Mask] = list(masks)
    distance = initial_distance
    restart_distance = dimension // 4
    generation = 0
    state_trace: list[dict[str, Any]] = []
    termination_phase = "initial_population"
    skipped_partial_update = False

    while ledger.remaining:
        generation += 1
        distance_before = distance
        shuffled = list(population)
        local_rng.shuffle(shuffled)
        fresh_masks: list[Mask] = []
        phase = "hux"

        for offset in range(0, len(shuffled) - 1, 2):
            left = shuffled[offset].mask
            right = shuffled[offset + 1].mask
            hamming_distance = sum(a != b for a, b in zip(left, right))
            if distance > 0 and hamming_distance > distance:
                first, second = hux_operator(left, right, local_rng)
                for child in (
                    validate_mask(first, dimension),
                    validate_mask(second, dimension),
                ):
                    if child not in history:
                        fresh_masks.append(child)
                        history.append(child)

        catastrophe = distance == 0
        if catastrophe:
            phase = "cataclysmic_mutation"
            distance = restart_distance
            fresh_masks = []
            best_parent = _stable_best(population, 1)[0]
            for _ in range(len(population)):
                mutant = validate_mask(
                    mutation_operator(
                        best_parent.mask,
                        cataclysmic_mutation_probability,
                        local_rng,
                    ),
                    dimension,
                )
                fresh_masks.append(mutant)
                history.append(mutant)

        calls_before = ledger.calls
        evaluated_count = min(len(fresh_masks), ledger.remaining)
        evaluated_masks = fresh_masks[:evaluated_count]
        fresh = [
            _Candidate(mask, fitness)
            for mask, fitness in zip(
                evaluated_masks,
                ledger.evaluate_many(evaluated_masks),
            )
        ]
        partial = evaluated_count < len(fresh_masks)
        if partial:
            skipped_partial_update = True
            termination_phase = "partial_chc_offspring_prefix"
            # A prefix is observable only through its objective records.  The
            # frozen rule forbids every state transition from that incomplete
            # generation, including the catastrophe distance reset.
            distance = distance_before
            state_trace.append(
                {
                    "generation": generation,
                    "phase": phase,
                    "distance_before": distance_before,
                    "distance_after": distance,
                    "generated_fresh_offspring": len(fresh_masks),
                    "evaluated_fresh_offspring": evaluated_count,
                    "calls_before": calls_before,
                    "calls_after": ledger.calls,
                    "partial_population_update_skipped": True,
                }
            )
            break

        old_masks = [candidate.mask for candidate in population]
        if catastrophe:
            population = _stable_best([_stable_best(population, 1)[0]] + fresh, len(population))
        else:
            population = _stable_best(population + fresh, len(population))
            if [candidate.mask for candidate in population] == old_masks:
                distance -= 1
        termination_phase = (
            "complete_cataclysmic_generation"
            if catastrophe
            else "complete_chc_generation"
        )
        state_trace.append(
            {
                "generation": generation,
                "phase": phase,
                "distance_before": distance_before,
                "distance_after": distance,
                "generated_fresh_offspring": len(fresh_masks),
                "evaluated_fresh_offspring": evaluated_count,
                "calls_before": calls_before,
                "calls_after": ledger.calls,
                "partial_population_update_skipped": False,
            }
        )

    return _search_result(
        arm="chc_harmonized",
        ledger=ledger,
        initial_population_calls=len(masks),
        reset=False,
        reset_events=0,
        termination_phase=termination_phase,
        terminal_state={
            "generation_count": generation,
            "final_distance": distance,
            "population_size": len(population),
            "partial_population_update_skipped": skipped_partial_update,
        },
        generation_trace=state_trace,
    )


def run_lambda_no_reset(
    objective: Objective,
    initial_masks: Sequence[Sequence[int]],
    *,
    seed: int,
    budget: int = DEFAULT_BUDGET,
    lambda_initial: float = 1.0,
    lambda_min: float = 1.0,
    lambda_max: Optional[float] = None,
    update_factor: float = 1.5,
) -> SearchResult:
    """Run reset-disabled (1+(lambda,lambda)) with a budget-exact paired tail."""

    masks, dimension = _validated_initial_masks(initial_masks)
    if len(masks) > budget:
        raise ValueError("initial population exceeds objective-call budget")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    maximum = float(dimension) if lambda_max is None else float(lambda_max)
    if lambda_min != 1.0 or maximum != float(dimension):
        raise ValueError("lambda bounds must be exactly [1, dimension]")
    if not 1.0 <= float(lambda_initial) <= maximum:
        raise ValueError("initial lambda lies outside its bounds")
    if (budget - len(masks)) % 2 != 0:
        raise ValueError("paired mutant/crossover tail requires an even remainder")

    local_rng = np.random.default_rng(seed)
    ledger = BudgetLedger(objective, budget=budget, dimension=dimension)
    starting_fitness = ledger.evaluate_many(masks)
    parent_index = best_index(starting_fitness, local_rng)
    parent = masks[parent_index]
    parent_fitness = starting_fitness[parent_index]
    lambda_real = float(lambda_initial)
    generation = 0
    state_trace: list[dict[str, Any]] = []
    tail_truncated = False
    termination_phase = "initial_population"

    while ledger.remaining:
        ctl = controls(lambda_real, dimension)
        planned_count = ctl.offspring_count
        actual_count = min(planned_count, ledger.remaining // 2)
        if actual_count < 1:
            raise RuntimeError("unpaired objective call remains")
        truncated = actual_count < planned_count
        mutation_strength = int(
            local_rng.binomial(dimension, ctl.mutation_probability)
        )
        calls_before = ledger.calls
        mutants = make_mutants(
            parent,
            count=actual_count,
            strength=mutation_strength,
            rng=local_rng,
        )
        mutant_fitness = ledger.evaluate_many(mutants)
        mutant_index = best_index(mutant_fitness, local_rng)
        selected_mutant = mutants[mutant_index]
        selected_mutant_fitness = mutant_fitness[mutant_index]
        crossovers = make_crossovers(
            parent,
            selected_mutant,
            count=actual_count,
            probability=ctl.crossover_probability,
            rng=local_rng,
        )
        crossover_fitness = ledger.evaluate_many(crossovers)

        parent_before = parent
        parent_fitness_before = parent_fitness

        final_masks = [selected_mutant] + list(crossovers)
        final_fitness = [selected_mutant_fitness] + list(crossover_fitness)
        eligible = [
            (mask, fitness)
            for mask, fitness in zip(final_masks, final_fitness)
            if mask != parent
        ]
        if eligible:
            eligible_fitness = [item[1] for item in eligible]
            candidate_index = best_index(eligible_fitness, local_rng)
            candidate, candidate_fitness = eligible[candidate_index]
        else:
            candidate, candidate_fitness = parent, parent_fitness

        strict_success = candidate_fitness > parent_fitness
        accepted = candidate_fitness >= parent_fitness
        if accepted:
            parent, parent_fitness = candidate, candidate_fitness
        lambda_after, reset_event = next_lambda(
            lambda_real,
            strict_success=strict_success,
            update_factor=update_factor,
            dimension=dimension,
            reset=False,
        )
        if reset_event:
            raise RuntimeError("reset-disabled arm emitted a reset event")
        generation += 1
        state_trace.append(
            {
                "generation": generation,
                "calls_before": calls_before,
                "calls_after": ledger.calls,
                "lambda_before": lambda_real,
                "lambda_after": lambda_after,
                "planned_offspring_count_per_phase": planned_count,
                "evaluated_offspring_count_per_phase": actual_count,
                "mutation_probability": ctl.mutation_probability,
                "crossover_probability": ctl.crossover_probability,
                "mutation_strength": mutation_strength,
                "parent_before": list(parent_before),
                "parent_fitness_before": list(parent_fitness_before),
                "selected_mutant_index": mutant_index,
                "candidate_mask": list(candidate),
                "candidate_fitness": list(candidate_fitness),
                "parent_after": list(parent),
                "strict_success": strict_success,
                "accepted": accepted,
                "tail_truncated": truncated,
            }
        )
        lambda_real = lambda_after
        tail_truncated = tail_truncated or truncated
        termination_phase = (
            "paired_mutant_crossover_tail"
            if truncated
            else "complete_lambda_generation"
        )

    return _search_result(
        arm="lambda_no_reset",
        ledger=ledger,
        initial_population_calls=len(masks),
        reset=False,
        reset_events=0,
        termination_phase=termination_phase,
        terminal_state={
            "generation_count": generation,
            "final_lambda": lambda_real,
            "parent_mask_sha256": _canonical_sha256(list(parent)),
            "parent_fitness": list(parent_fitness),
            "tail_truncated": tail_truncated,
            "workers": 1,
        },
        generation_trace=state_trace,
    )

"""Hybrid 1: reset self-adjusting (1+(lambda,lambda)) search on binary masks.

The module is a small independent implementation of the control mechanism used
in Algorithm 3 of Hevia Fajardo and Sudholt.  It is intentionally generic: the
objective can be Jump, OneMax, or the CHC-QX Census feature-selection fitness.

Scientific invariants
---------------------
* one real-valued lambda controls offspring count, mutation probability, and
  crossover bias;
* offspring count is nearest-integer with half rounded up;
* one mutation strength L~Bin(n, lambda/n) is shared by all mutants in a
  generation;
* the final pool is the selected best mutant plus crossover children;
* copies of the current parent are excluded from final selection;
* equal-fitness candidates may replace the parent, but only a strict
  lexicographic improvement is a success for lambda control;
* on a failed generation at lambda=n, reset lambda to one.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import math
from numbers import Real
from typing import Any, Callable, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

Mask = Tuple[int, ...]
Fitness = Tuple[float, float]
ObjectiveValue = Union[Fitness, float, int, np.floating, np.integer]
Objective = Callable[[Mask], ObjectiveValue]


@dataclass(frozen=True)
class Control:
    lambda_real: float
    offspring_count: int
    mutation_probability: float
    crossover_probability: float


@dataclass(frozen=True)
class GenerationSelection:
    best_mutant: Mask
    best_mutant_fitness: Fitness
    candidate: Mask
    candidate_fitness: Fitness
    eligible_count: int


@dataclass(frozen=True)
class GenerationTrace:
    generation: int
    evaluations: int
    lambda_before: float
    lambda_after: float
    offspring_count: int
    mutation_probability: float
    crossover_probability: float
    mutation_strength: int
    best_mutant_primary: float
    best_mutant_secondary: float
    parent_primary_before: float
    parent_secondary_before: float
    candidate_primary: float
    candidate_secondary: float
    strict_success: bool
    accepted: bool
    reset_event: bool
    parent_ones_after: int


@dataclass(frozen=True)
class RunResult:
    seed: int
    dimension: int
    workers: int
    evaluations: int
    generations: int
    reset_events: int
    best_mask: Mask
    best_fitness: Fitness
    solved: bool
    trace: Tuple[GenerationTrace, ...]

    def to_dict(self, include_trace: bool = True) -> dict:
        payload = asdict(self)
        if not include_trace:
            payload.pop("trace", None)
        return payload


def normalize_fitness(value: ObjectiveValue) -> Fitness:
    """Normalize scalar or two-component lexicographic fitness."""

    if isinstance(value, (tuple, list)):
        if len(value) != 2:
            raise ValueError("fitness sequence must contain exactly two values")
        first, second = value
    else:
        first, second = value, 0.0
    if not isinstance(first, Real) or not isinstance(second, Real):
        raise TypeError("fitness values must be real numbers")
    result = (float(first), float(second))
    if not all(math.isfinite(component) for component in result):
        raise ValueError("fitness values must be finite")
    return result


def round_half_up(value: float) -> int:
    """Nearest-integer rounding used by the printed algorithm."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("lambda must be a real number")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 1.0:
        raise ValueError("lambda must be finite and at least one")
    return max(1, int(math.floor(numeric + 0.5)))


def controls(lambda_real: float, dimension: int) -> Control:
    """Return m, p=lambda/n, and c=1/lambda."""

    if isinstance(dimension, bool) or not isinstance(dimension, int):
        raise TypeError("dimension must be an integer")
    if dimension < 2:
        raise ValueError("dimension must be at least two")
    if isinstance(lambda_real, bool) or not isinstance(lambda_real, Real):
        raise TypeError("lambda must be a real number")
    numeric = float(lambda_real)
    if not 1.0 <= numeric <= float(dimension):
        raise ValueError("lambda must lie in [1, dimension]")
    return Control(
        lambda_real=numeric,
        offspring_count=round_half_up(numeric),
        mutation_probability=numeric / float(dimension),
        crossover_probability=1.0 / numeric,
    )


def next_lambda(
    lambda_real: float,
    *,
    strict_success: bool,
    update_factor: float,
    dimension: int,
    reset: bool,
) -> Tuple[float, bool]:
    """Apply shrink, grow, or reset using the pre-generation lambda."""

    ctl = controls(lambda_real, dimension)
    if not isinstance(strict_success, bool) or not isinstance(reset, bool):
        raise TypeError("strict_success and reset must be boolean")
    if isinstance(update_factor, bool) or not isinstance(update_factor, Real):
        raise TypeError("update_factor must be a real number")
    factor = float(update_factor)
    if not math.isfinite(factor) or factor <= 1.0:
        raise ValueError("update_factor must be finite and greater than one")

    if strict_success:
        return max(1.0, ctl.lambda_real / factor), False
    if reset and ctl.lambda_real == float(dimension):
        return 1.0, True
    return min(
        float(dimension),
        ctl.lambda_real * factor ** 0.25,
    ), False


def validate_mask(mask: Sequence[int], dimension: Optional[int] = None) -> Mask:
    values = tuple(int(value) for value in mask)
    if dimension is not None and len(values) != dimension:
        raise ValueError("mask length does not match dimension")
    if not values:
        raise ValueError("mask must not be empty")
    if any(value not in (0, 1) for value in values):
        raise ValueError("mask must be binary")
    return values


def mutate_exact(parent: Sequence[int], positions: Iterable[int]) -> Mask:
    """Flip exactly the supplied distinct zero-based positions."""

    child = list(validate_mask(parent))
    seen = set()
    for raw in positions:
        if isinstance(raw, bool) or not isinstance(raw, (int, np.integer)):
            raise TypeError("mutation positions must be integers")
        position = int(raw)
        if position in seen or not 0 <= position < len(child):
            raise ValueError("positions must be distinct and inside the mask")
        seen.add(position)
        child[position] = 1 - child[position]
    return tuple(child)


def crossover_mask(
    parent: Sequence[int],
    mutant: Sequence[int],
    take_mutant: Sequence[bool],
) -> Mask:
    """Biased uniform crossover for one realized Bernoulli mask."""

    first = validate_mask(parent)
    second = validate_mask(mutant, len(first))
    if len(take_mutant) != len(first):
        raise ValueError("crossover mask length mismatch")
    return tuple(
        second[index] if bool(take_mutant[index]) else first[index]
        for index in range(len(first))
    )


def make_mutants(
    parent: Mask,
    *,
    count: int,
    strength: int,
    rng: np.random.Generator,
) -> List[Mask]:
    """Create ``count`` mutants, all at the same exact Hamming distance."""

    validated = validate_mask(parent)
    if count < 1:
        raise ValueError("mutant count must be positive")
    if not 0 <= strength <= len(validated):
        raise ValueError("mutation strength must lie in [0, dimension]")
    mutants: List[Mask] = []
    for _ in range(count):
        positions = (
            []
            if strength == 0
            else rng.choice(
                len(validated), size=strength, replace=False
            ).tolist()
        )
        mutants.append(mutate_exact(validated, positions))
    return mutants


def make_crossovers(
    parent: Mask,
    mutant: Mask,
    *,
    count: int,
    probability: float,
    rng: np.random.Generator,
) -> List[Mask]:
    """Create ordered biased-uniform crossover offspring."""

    validated_parent = validate_mask(parent)
    validated_mutant = validate_mask(mutant, len(validated_parent))
    if count < 1:
        raise ValueError("crossover count must be positive")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("crossover probability must lie in [0,1]")
    children: List[Mask] = []
    for _ in range(count):
        take_mutant = (
            rng.random(len(validated_parent)) < probability
        ).tolist()
        children.append(
            crossover_mask(validated_parent, validated_mutant, take_mutant)
        )
    return children


def _evaluate_one(arguments: Tuple[Objective, Mask]) -> Fitness:
    objective, mask = arguments
    return normalize_fitness(objective(mask))


def evaluate_many(
    objective: Objective,
    masks: Sequence[Mask],
    workers: int,
) -> List[Fitness]:
    """Evaluate in input order; worker count cannot alter random decisions."""

    if isinstance(workers, bool) or not isinstance(workers, int):
        raise TypeError("workers must be an integer")
    if workers < 1:
        raise ValueError("workers must be at least one")
    if not masks:
        return []
    if workers == 1:
        return [normalize_fitness(objective(mask)) for mask in masks]
    arguments = [(objective, mask) for mask in masks]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(_evaluate_one, arguments))


def best_index(fitness: Sequence[Fitness], rng: np.random.Generator) -> int:
    if not fitness:
        raise ValueError("fitness sequence must not be empty")
    best = max(fitness)
    tied = np.asarray(
        [index for index, score in enumerate(fitness) if score == best],
        dtype=int,
    )
    return int(rng.choice(tied))


def select_generation_candidate(
    *,
    parent: Mask,
    parent_fitness: Fitness,
    mutants: Sequence[Mask],
    mutant_fitness: Sequence[Fitness],
    crossovers: Sequence[Mask],
    crossover_fitness: Sequence[Fitness],
    rng: np.random.Generator,
) -> GenerationSelection:
    """Paper final-pool semantics, exposed for fixed-tape verification."""

    if not mutants or len(mutants) != len(mutant_fitness):
        raise ValueError("mutant masks and fitness must be non-empty and aligned")
    if len(crossovers) != len(crossover_fitness):
        raise ValueError("crossover masks and fitness must be aligned")

    mutant_index = best_index(mutant_fitness, rng)
    selected_mutant = mutants[mutant_index]
    selected_mutant_fitness = mutant_fitness[mutant_index]

    final_masks = [selected_mutant] + list(crossovers)
    final_fitness = [selected_mutant_fitness] + list(crossover_fitness)
    eligible = [
        (mask, score)
        for mask, score in zip(final_masks, final_fitness)
        if mask != parent
    ]
    if not eligible:
        return GenerationSelection(
            best_mutant=selected_mutant,
            best_mutant_fitness=selected_mutant_fitness,
            candidate=parent,
            candidate_fitness=parent_fitness,
            eligible_count=0,
        )

    eligible_masks = [item[0] for item in eligible]
    eligible_fitness = [item[1] for item in eligible]
    candidate_index = best_index(eligible_fitness, rng)
    return GenerationSelection(
        best_mutant=selected_mutant,
        best_mutant_fitness=selected_mutant_fitness,
        candidate=eligible_masks[candidate_index],
        candidate_fitness=eligible_fitness[candidate_index],
        eligible_count=len(eligible),
    )


def source_density_mask(dimension: int, rng: np.random.Generator) -> Mask:
    """CHC-QX source-compatible initial density mixture, never all-zero."""

    if dimension < 2:
        raise ValueError("dimension must be at least two")
    while True:
        zero_probability = float(rng.uniform(0.0, 1.0))
        values = rng.choice(
            np.asarray([0, 1], dtype=int),
            size=dimension,
            p=[zero_probability, 1.0 - zero_probability],
        )
        mask = tuple(int(value) for value in values.tolist())
        if any(mask):
            return mask


def source_density_population(
    population_size: int,
    dimension: int,
    rng: np.random.Generator,
) -> List[Mask]:
    if population_size < 1:
        raise ValueError("population_size must be positive")
    return [source_density_mask(dimension, rng) for _ in range(population_size)]


def run_reset_lambda_ga(
    objective: Objective,
    *,
    dimension: int,
    seed: int,
    max_evaluations: int,
    workers: int = 1,
    update_factor: float = 1.5,
    reset: bool = True,
    initial_mask: Optional[Mask] = None,
    initial_masks: Optional[Sequence[Mask]] = None,
    target_primary: Optional[float] = None,
) -> RunResult:
    """Run Hybrid 1 under a strict logical fitness-evaluation budget."""

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    if isinstance(max_evaluations, bool) or not isinstance(max_evaluations, int):
        raise TypeError("max_evaluations must be an integer")
    if max_evaluations < 1:
        raise ValueError("max_evaluations must be positive")
    controls(1.0, dimension)
    if initial_mask is not None and initial_masks is not None:
        raise ValueError("provide initial_mask or initial_masks, not both")

    rng = np.random.default_rng(seed)
    if initial_masks is not None:
        starting_masks = [validate_mask(mask, dimension) for mask in initial_masks]
        if not starting_masks:
            raise ValueError("initial_masks must not be empty")
    elif initial_mask is not None:
        starting_masks = [validate_mask(initial_mask, dimension)]
    else:
        starting_masks = [source_density_mask(dimension, rng)]

    if len(starting_masks) > max_evaluations:
        raise ValueError("initial population exceeds the evaluation budget")
    starting_fitness = evaluate_many(objective, starting_masks, workers)
    parent_index = best_index(starting_fitness, rng)
    parent = starting_masks[parent_index]
    parent_fitness = starting_fitness[parent_index]

    evaluations = len(starting_masks)
    lambda_real = 1.0
    generation = 0
    reset_events = 0
    trace: List[GenerationTrace] = []

    while evaluations < max_evaluations:
        if target_primary is not None and parent_fitness[0] >= target_primary:
            break
        ctl = controls(lambda_real, dimension)
        offspring_count = ctl.offspring_count
        logical_cost = 2 * offspring_count
        if evaluations + logical_cost > max_evaluations:
            break

        mutation_strength = int(
            rng.binomial(dimension, ctl.mutation_probability)
        )
        mutants = make_mutants(
            parent,
            count=offspring_count,
            strength=mutation_strength,
            rng=rng,
        )
        mutant_fitness = evaluate_many(objective, mutants, workers)
        mutant_index = best_index(mutant_fitness, rng)
        selected_mutant = mutants[mutant_index]

        crossovers = make_crossovers(
            parent,
            selected_mutant,
            count=offspring_count,
            probability=ctl.crossover_probability,
            rng=rng,
        )
        crossover_fitness = evaluate_many(objective, crossovers, workers)
        evaluations += logical_cost

        selection = select_generation_candidate(
            parent=parent,
            parent_fitness=parent_fitness,
            mutants=mutants,
            mutant_fitness=mutant_fitness,
            crossovers=crossovers,
            crossover_fitness=crossover_fitness,
            rng=rng,
        )
        parent_before = parent_fitness
        strict_success = selection.candidate_fitness > parent_fitness
        accepted = selection.candidate_fitness >= parent_fitness
        if accepted:
            parent = selection.candidate
            parent_fitness = selection.candidate_fitness

        lambda_after, reset_event = next_lambda(
            lambda_real,
            strict_success=strict_success,
            update_factor=update_factor,
            dimension=dimension,
            reset=reset,
        )
        reset_events += int(reset_event)
        generation += 1
        trace.append(
            GenerationTrace(
                generation=generation,
                evaluations=evaluations,
                lambda_before=lambda_real,
                lambda_after=lambda_after,
                offspring_count=offspring_count,
                mutation_probability=ctl.mutation_probability,
                crossover_probability=ctl.crossover_probability,
                mutation_strength=mutation_strength,
                best_mutant_primary=selection.best_mutant_fitness[0],
                best_mutant_secondary=selection.best_mutant_fitness[1],
                parent_primary_before=parent_before[0],
                parent_secondary_before=parent_before[1],
                candidate_primary=selection.candidate_fitness[0],
                candidate_secondary=selection.candidate_fitness[1],
                strict_success=strict_success,
                accepted=accepted,
                reset_event=reset_event,
                parent_ones_after=sum(parent),
            )
        )
        lambda_real = lambda_after

    solved = (
        target_primary is not None
        and parent_fitness[0] >= float(target_primary)
    )
    return RunResult(
        seed=seed,
        dimension=dimension,
        workers=workers,
        evaluations=evaluations,
        generations=generation,
        reset_events=reset_events,
        best_mask=parent,
        best_fitness=parent_fitness,
        solved=solved,
        trace=tuple(trace),
    )

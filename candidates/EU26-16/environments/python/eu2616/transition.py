from __future__ import annotations

import dataclasses
import math
import struct
from collections.abc import Iterable


DECIMAL_UPDATE = 0.02
SOURCE_STEP = struct.unpack("!f", struct.pack("!f", DECIMAL_UPDATE))[0]
GUARD_DOUBLE_STEP = struct.unpack("!f", struct.pack("!f", SOURCE_STEP * 2.0))[0]
GUARD_UPPER = struct.unpack("!f", struct.pack("!f", 1.0 - GUARD_DOUBLE_STEP))[0]
FITNESS_SCALE = 10_000
EARLY_STOP_PATIENCE = 10


def java_float(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Java-float emulation requires a finite value")
    try:
        return struct.unpack("!f", struct.pack("!f", value))[0]
    except OverflowError as error:
        raise ValueError("value is outside Java float range") from error


def java_math_round_float(value: float) -> int:
    value = java_float(value)
    return math.floor(value + 0.5)


def round_best_fitness(value: float) -> float:
    """Mirror Alg.java's float cast, multiply, Math.round, and divide."""

    current = java_float(value)
    current = java_float(current * FITNESS_SCALE)
    current = java_float(float(java_math_round_float(current)))
    return java_float(current / FITNESS_SCALE)


@dataclasses.dataclass(frozen=True)
class ControlState:
    crossover_probability: float
    mutation_probability: float
    best_average_fitness: float
    best_fitness: float
    last_best_generation: int

    def validate(self) -> None:
        probabilities = (self.crossover_probability, self.mutation_probability)
        if any(not math.isfinite(value) for value in probabilities):
            raise ValueError("operator probabilities must be finite")
        if any(value < 0.0 or value > 1.0 for value in probabilities):
            raise ValueError("operator probabilities must be within [0, 1]")
        if not math.isclose(sum(probabilities), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("crossover and mutation probabilities must sum to one")
        java_float(self.best_average_fitness)
        java_float(self.best_fitness)
        if isinstance(self.last_best_generation, bool) or not isinstance(
            self.last_best_generation, int
        ):
            raise ValueError("last_best_generation must be an integer")
        if self.last_best_generation < 0:
            raise ValueError("last_best_generation must be non-negative")


@dataclasses.dataclass(frozen=True)
class TransitionEvent:
    rounded_current_best_fitness: float
    best_fitness_improved: bool
    average_branch: str
    probabilities_changed: bool
    should_stop: bool
    stop_reason: str | None


def initial_state() -> ControlState:
    return ControlState(
        crossover_probability=0.5,
        mutation_probability=0.5,
        best_average_fitness=java_float(0.0),
        best_fitness=java_float(-1.0),
        last_best_generation=0,
    )


def transition_generation(
    state: ControlState,
    *,
    generation: int,
    current_best_fitness: float,
    current_average_fitness: float,
    max_generations: int,
    patience: int = EARLY_STOP_PATIENCE,
) -> tuple[ControlState, TransitionEvent]:
    """Apply the source-ordered `Alg.doControl()` scalar transition."""

    state.validate()
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        raise ValueError("generation must be a non-negative integer")
    if isinstance(max_generations, bool) or not isinstance(max_generations, int):
        raise ValueError("max_generations must be an integer")
    if max_generations <= 0:
        raise ValueError("max_generations must be positive")
    if isinstance(patience, bool) or not isinstance(patience, int) or patience <= 0:
        raise ValueError("patience must be a positive integer")

    rounded_best = round_best_fitness(current_best_fitness)
    best_fitness = java_float(state.best_fitness)
    last_best_generation = state.last_best_generation
    best_improved = rounded_best > best_fitness
    if best_improved:
        best_fitness = rounded_best
        last_best_generation = generation

    average = java_float(current_average_fitness)
    best_average = java_float(state.best_average_fitness)
    crossover = float(state.crossover_probability)
    mutation = float(state.mutation_probability)
    changed = False

    if average > best_average:
        branch = "improvement"
        # Source ordering is material: the historical mean changes even if the guard blocks.
        best_average = average
        if crossover < GUARD_UPPER and mutation >= GUARD_DOUBLE_STEP:
            crossover += DECIMAL_UPDATE
            mutation -= DECIMAL_UPDATE
            changed = True
    else:
        branch = "non_improvement"
        if mutation < GUARD_UPPER and crossover >= GUARD_DOUBLE_STEP:
            crossover -= DECIMAL_UPDATE
            mutation += DECIMAL_UPDATE
            changed = True

    next_state = ControlState(
        crossover_probability=crossover,
        mutation_probability=mutation,
        best_average_fitness=best_average,
        best_fitness=best_fitness,
        last_best_generation=last_best_generation,
    )
    next_state.validate()

    stagnated = generation >= last_best_generation + patience and best_fitness > 0.0
    maximum_reached = generation >= max_generations
    should_stop = stagnated or maximum_reached
    if maximum_reached:
        stop_reason = "max_generations"
    elif stagnated:
        stop_reason = "best_fitness_stagnation"
    else:
        stop_reason = None
    event = TransitionEvent(
        rounded_current_best_fitness=rounded_best,
        best_fitness_improved=best_improved,
        average_branch=branch,
        probabilities_changed=changed,
        should_stop=should_stop,
        stop_reason=stop_reason,
    )
    return next_state, event


def run_average_sequence(
    averages: Iterable[float],
    *,
    state: ControlState | None = None,
    best_fitness: float = 0.5,
    max_generations: int = 10_000,
) -> ControlState:
    current = state or initial_state()
    for generation, average in enumerate(averages, start=1):
        current, _ = transition_generation(
            current,
            generation=generation,
            current_best_fitness=best_fitness + generation / 10_000.0,
            current_average_fitness=average,
            max_generations=max_generations,
        )
    return current

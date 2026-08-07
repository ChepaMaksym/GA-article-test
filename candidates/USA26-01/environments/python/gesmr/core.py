"""Paper-formula clean-room implementation of one GESMR run.

The implementation follows Algorithm 1 and Eqs. (2)--(7) of Kumar et al.
(GECCO 2022).  The paper's explicit group intervals in Eq. (5) are used
for Eq. (4), avoiding the out-of-range endpoint produced by the printed
floor expression at ``i=N``.  See the candidate provenance record.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike, NDArray

Objective = Callable[[ArrayLike], NDArray[np.float64]]
FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


@dataclass(frozen=True)
class GESMRConfig:
    """Configuration with the paper defaults for analytic experiments.

    ``non_elite_size`` is the paper's ``N``; the full solution population
    therefore contains ``N + 1`` rows because one elite is retained.
    """

    non_elite_size: int = 100
    n_groups: int = 10
    solution_selection_rate: float = 0.5
    mr_selection_rate: float = 0.5
    meta_mutation_rate: float = 2.0
    initial_log10_mr_min: float = -3.0
    initial_log10_mr_max: float = 3.0

    def validate(self) -> None:
        if (
            isinstance(self.non_elite_size, bool)
            or not isinstance(self.non_elite_size, Integral)
            or self.non_elite_size < 1
        ):
            raise ValueError("non_elite_size must be a positive integer")
        if (
            isinstance(self.n_groups, bool)
            or not isinstance(self.n_groups, Integral)
            or self.n_groups < 1
        ):
            raise ValueError("n_groups must be a positive integer")
        if self.non_elite_size % self.n_groups != 0:
            raise ValueError("n_groups must divide non_elite_size exactly")
        self._integral_selection_count(
            self.solution_selection_rate,
            self.non_elite_size,
            "solution_selection_rate * non_elite_size",
        )
        self._integral_selection_count(
            self.mr_selection_rate,
            self.n_groups,
            "mr_selection_rate * n_groups",
        )
        if not np.isfinite(self.meta_mutation_rate) or self.meta_mutation_rate <= 0.0:
            raise ValueError("meta_mutation_rate must be finite and positive")
        if not np.isfinite(self.initial_log10_mr_min):
            raise ValueError("initial_log10_mr_min must be finite")
        if not np.isfinite(self.initial_log10_mr_max):
            raise ValueError("initial_log10_mr_max must be finite")
        if self.initial_log10_mr_min > self.initial_log10_mr_max:
            raise ValueError("initial mutation-rate interval is reversed")

    @staticmethod
    def _integral_selection_count(rate: float, size: int, label: str) -> int:
        if not np.isfinite(rate) or rate <= 0.0 or rate > 1.0:
            raise ValueError(f"{label.split(' * ')[0]} must lie in (0, 1]")
        exact = float(rate) * int(size)
        rounded = round(exact)
        if not np.isclose(exact, rounded, rtol=0.0, atol=1e-12):
            raise ValueError(f"{label} must be an integer; got {exact}")
        if rounded < 1:
            raise ValueError(f"{label} must select at least one parent")
        return int(rounded)

    @property
    def solution_parent_count(self) -> int:
        return self._integral_selection_count(
            self.solution_selection_rate,
            self.non_elite_size,
            "solution_selection_rate * non_elite_size",
        )

    @property
    def mr_parent_count(self) -> int:
        return self._integral_selection_count(
            self.mr_selection_rate,
            self.n_groups,
            "mr_selection_rate * n_groups",
        )

    @property
    def group_size(self) -> int:
        return self.non_elite_size // self.n_groups


@dataclass(frozen=True)
class RandomTape:
    """All random variates needed for one cross-environment GESMR step.

    Parent ranks are zero-based ranks in the corresponding sorted,
    truncated parent pool.  This representation is language-neutral.
    """

    solution_parent_ranks: IntArray
    solution_noise: FloatArray
    mr_parent_ranks: IntArray
    mr_uniform: FloatArray

    @classmethod
    def from_mapping(cls, value: Mapping[str, ArrayLike]) -> "RandomTape":
        return cls(
            solution_parent_ranks=np.asarray(value["solution_parent_ranks"]),
            solution_noise=np.asarray(value["solution_noise"], dtype=np.float64),
            mr_parent_ranks=np.asarray(value["mr_parent_ranks"]),
            mr_uniform=np.asarray(value["mr_uniform"], dtype=np.float64),
        )


@dataclass(frozen=True)
class StepResult:
    next_population: FloatArray
    next_fitness: FloatArray
    next_sigmas: FloatArray
    selected_parents: FloatArray
    selected_parent_fitness: FloatArray
    group_delta: FloatArray
    solution_parent_ranks: IntArray
    mr_parent_ranks: IntArray
    solution_noise: FloatArray
    mr_uniform: FloatArray


@dataclass(frozen=True)
class RunResult:
    final_population: FloatArray
    final_fitness: FloatArray
    final_sigmas: FloatArray
    best_fitness_history: FloatArray
    geometric_mean_sigma_history: FloatArray
    arithmetic_mean_sigma_history: FloatArray
    sigma_history: FloatArray
    objective_call_count: int
    objective_row_evaluation_count: int
    seed: int


def initial_mutation_rates(config: GESMRConfig = GESMRConfig()) -> FloatArray:
    """Return the paper's logarithmically spaced initial MR population."""

    config.validate()
    return np.logspace(
        config.initial_log10_mr_min,
        config.initial_log10_mr_max,
        config.n_groups,
        dtype=np.float64,
    )


def _evaluate(objective: Objective, population: FloatArray) -> FloatArray:
    values = np.asarray(objective(population), dtype=np.float64)
    if values.shape != (population.shape[0],):
        raise ValueError(
            "objective must return one value per population row; "
            f"expected {(population.shape[0],)}, got {values.shape}"
        )
    if not np.all(np.isfinite(values)):
        raise FloatingPointError("objective returned NaN or Inf")
    return values


def _validate_state(
    population: ArrayLike,
    sigmas: ArrayLike,
    config: GESMRConfig,
) -> tuple[FloatArray, FloatArray]:
    config.validate()
    pop = np.asarray(population, dtype=np.float64)
    mr = np.asarray(sigmas, dtype=np.float64).reshape(-1)
    expected_rows = config.non_elite_size + 1
    if pop.ndim != 2 or pop.shape[0] != expected_rows or pop.shape[1] < 1:
        raise ValueError(
            f"population must have shape ({expected_rows}, dimension>=1); got {pop.shape}"
        )
    if mr.shape != (config.n_groups,):
        raise ValueError(f"sigmas must have shape ({config.n_groups},); got {mr.shape}")
    if not np.all(np.isfinite(pop)):
        raise ValueError("population must be finite")
    if not np.all(np.isfinite(mr)) or np.any(mr <= 0.0):
        raise ValueError("all mutation rates must be finite and positive")
    return pop, mr


def _draw_or_validate_tape(
    rng: np.random.Generator | None,
    tape: RandomTape | Mapping[str, ArrayLike] | None,
    config: GESMRConfig,
    dimension: int,
) -> RandomTape:
    if tape is not None and rng is not None:
        raise ValueError("provide either rng or tape, not both")
    if tape is None:
        if rng is None:
            raise ValueError("an rng or a complete random tape is required")
        tape_value = RandomTape(
            solution_parent_ranks=rng.integers(
                0,
                config.solution_parent_count,
                size=config.non_elite_size,
                dtype=np.int64,
            ),
            solution_noise=rng.standard_normal((config.non_elite_size, dimension)),
            mr_parent_ranks=rng.integers(
                0,
                config.mr_parent_count,
                size=config.n_groups - 1,
                dtype=np.int64,
            ),
            mr_uniform=rng.uniform(-1.0, 1.0, size=config.n_groups - 1),
        )
    elif isinstance(tape, RandomTape):
        tape_value = tape
    else:
        tape_value = RandomTape.from_mapping(tape)

    parent_rank_values = np.asarray(tape_value.solution_parent_ranks).reshape(-1)
    noise = np.asarray(tape_value.solution_noise, dtype=np.float64)
    mr_parent_rank_values = np.asarray(tape_value.mr_parent_ranks).reshape(-1)
    mr_uniform = np.asarray(tape_value.mr_uniform, dtype=np.float64).reshape(-1)

    try:
        parent_rank_numbers = parent_rank_values.astype(np.float64)
        mr_parent_rank_numbers = mr_parent_rank_values.astype(np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("random-tape parent ranks must be integers") from exc
    if (
        not np.all(np.isfinite(parent_rank_numbers))
        or not np.all(parent_rank_numbers == np.floor(parent_rank_numbers))
        or not np.all(np.isfinite(mr_parent_rank_numbers))
        or not np.all(mr_parent_rank_numbers == np.floor(mr_parent_rank_numbers))
    ):
        raise ValueError("random-tape parent ranks must be integers")
    parent_ranks = parent_rank_numbers.astype(np.int64)
    mr_parent_ranks = mr_parent_rank_numbers.astype(np.int64)

    if parent_ranks.shape != (config.non_elite_size,):
        raise ValueError("random tape has the wrong number of solution parent ranks")
    if noise.shape != (config.non_elite_size, dimension):
        raise ValueError("random tape has the wrong Gaussian-noise shape")
    if mr_parent_ranks.shape != (config.n_groups - 1,):
        raise ValueError("random tape has the wrong number of MR parent ranks")
    if mr_uniform.shape != (config.n_groups - 1,):
        raise ValueError("random tape has the wrong number of MR uniform variates")
    if np.any(parent_ranks < 0) or np.any(parent_ranks >= config.solution_parent_count):
        raise ValueError("solution parent rank is outside the truncated parent pool")
    if np.any(mr_parent_ranks < 0) or np.any(mr_parent_ranks >= config.mr_parent_count):
        raise ValueError("MR parent rank is outside the truncated MR parent pool")
    if not np.all(np.isfinite(noise)):
        raise ValueError("Gaussian random tape must be finite")
    if not np.all(np.isfinite(mr_uniform)) or np.any(np.abs(mr_uniform) > 1.0):
        raise ValueError("MR mutation variates must lie in [-1, 1]")

    return RandomTape(parent_ranks, noise, mr_parent_ranks, mr_uniform)


def gesmr_step(
    population: ArrayLike,
    sigmas: ArrayLike,
    objective: Objective,
    config: GESMRConfig = GESMRConfig(),
    *,
    rng: np.random.Generator | None = None,
    tape: RandomTape | Mapping[str, ArrayLike] | None = None,
    current_fitness: ArrayLike | None = None,
) -> StepResult:
    """Execute one paper-order GESMR generation.

    The solution population is sorted and selected first; the ``N``
    non-elites are mutated in contiguous equal-sized MR groups; then the
    MR population is selected by each group's best objective change and
    log-uniformly meta-mutated.  No crossover or boundary clipping is used.
    """

    pop, mr = _validate_state(population, sigmas, config)
    variates = _draw_or_validate_tape(rng, tape, config, pop.shape[1])

    if current_fitness is None:
        fitness = _evaluate(objective, pop)
    else:
        fitness = np.asarray(current_fitness, dtype=np.float64).reshape(-1)
        if fitness.shape != (config.non_elite_size + 1,):
            raise ValueError("current_fitness must contain N+1 values")
        if not np.all(np.isfinite(fitness)):
            raise ValueError("current_fitness must be finite")
    solution_order = np.argsort(fitness, kind="stable")
    sorted_population = pop[solution_order]
    sorted_fitness = fitness[solution_order]

    parents = np.empty_like(pop)
    parent_fitness = np.empty(config.non_elite_size + 1, dtype=np.float64)
    parents[0] = sorted_population[0]
    parent_fitness[0] = sorted_fitness[0]
    parents[1:] = sorted_population[variates.solution_parent_ranks]
    parent_fitness[1:] = sorted_fitness[variates.solution_parent_ranks]

    group_sigmas = np.repeat(mr, config.group_size)
    next_population = np.empty_like(pop)
    next_population[0] = parents[0]
    next_population[1:] = parents[1:] + variates.solution_noise * group_sigmas[:, None]
    next_fitness = _evaluate(objective, next_population)

    child_delta = next_fitness[1:] - parent_fitness[1:]
    group_delta = child_delta.reshape(config.n_groups, config.group_size).min(axis=1)

    mr_order = np.argsort(group_delta, kind="stable")
    sorted_sigmas = mr[mr_order]
    next_sigmas = np.empty_like(mr)
    next_sigmas[0] = sorted_sigmas[0]
    mr_parents = sorted_sigmas[variates.mr_parent_ranks]
    next_sigmas[1:] = mr_parents * np.power(
        config.meta_mutation_rate,
        variates.mr_uniform,
    )
    if not np.all(np.isfinite(next_sigmas)) or np.any(next_sigmas <= 0.0):
        raise FloatingPointError("MR meta-mutation produced a non-positive or non-finite value")

    return StepResult(
        next_population=next_population,
        next_fitness=next_fitness,
        next_sigmas=next_sigmas,
        selected_parents=parents,
        selected_parent_fitness=parent_fitness,
        group_delta=group_delta,
        solution_parent_ranks=variates.solution_parent_ranks,
        mr_parent_ranks=variates.mr_parent_ranks,
        solution_noise=variates.solution_noise,
        mr_uniform=variates.mr_uniform,
    )


def run_gesmr(
    objective: Objective,
    dimension: int,
    initial_std: float,
    seed: int,
    generations: int,
    config: GESMRConfig = GESMRConfig(),
) -> RunResult:
    """Run GESMR with a frozen NumPy PCG64 seed contract.

    Python and MATLAB intentionally use their native documented RNGs for
    stochastic experiments.  Cross-environment transition equivalence is
    checked separately with the shared fixed-random-tape fixture.
    """

    config.validate()
    if isinstance(dimension, bool) or int(dimension) != dimension or dimension < 1:
        raise ValueError("dimension must be a positive integer")
    if not np.isfinite(initial_std) or initial_std <= 0.0:
        raise ValueError("initial_std must be finite and positive")
    if isinstance(seed, bool) or int(seed) != seed or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if isinstance(generations, bool) or int(generations) != generations or generations < 0:
        raise ValueError("generations must be a non-negative integer")

    rng = np.random.Generator(np.random.PCG64(int(seed)))
    population = rng.normal(
        loc=0.0,
        scale=float(initial_std),
        size=(config.non_elite_size + 1, int(dimension)),
    )
    sigmas = initial_mutation_rates(config)
    fitness = _evaluate(objective, population)

    best_history = np.empty(int(generations) + 1, dtype=np.float64)
    geometric_mean_sigma_history = np.empty(int(generations) + 1, dtype=np.float64)
    arithmetic_mean_sigma_history = np.empty(int(generations) + 1, dtype=np.float64)
    sigma_history = np.empty((int(generations) + 1, config.n_groups), dtype=np.float64)
    best_history[0] = np.min(fitness)
    geometric_mean_sigma_history[0] = np.exp(np.mean(np.log(sigmas)))
    arithmetic_mean_sigma_history[0] = np.mean(sigmas)
    sigma_history[0] = sigmas

    for generation in range(int(generations)):
        step = gesmr_step(
            population,
            sigmas,
            objective,
            config,
            rng=rng,
            current_fitness=fitness,
        )
        population = step.next_population
        fitness = step.next_fitness
        sigmas = step.next_sigmas
        best_history[generation + 1] = np.min(fitness)
        geometric_mean_sigma_history[generation + 1] = np.exp(np.mean(np.log(sigmas)))
        arithmetic_mean_sigma_history[generation + 1] = np.mean(sigmas)
        sigma_history[generation + 1] = sigmas

    # The clean-room evaluator follows the author artifact by evaluating
    # all N+1 rows initially and after every generation, including the elite.
    objective_call_count = int(generations) + 1
    objective_row_evaluation_count = (
        config.non_elite_size + 1
    ) * objective_call_count
    return RunResult(
        final_population=population,
        final_fitness=fitness,
        final_sigmas=sigmas,
        best_fitness_history=best_history,
        geometric_mean_sigma_history=geometric_mean_sigma_history,
        arithmetic_mean_sigma_history=arithmetic_mean_sigma_history,
        sigma_history=sigma_history,
        objective_call_count=objective_call_count,
        objective_row_evaluation_count=objective_row_evaluation_count,
        seed=int(seed),
    )

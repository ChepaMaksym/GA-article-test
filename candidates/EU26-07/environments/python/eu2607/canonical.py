"""Outcome-independent policy and fixed-tape transition semantics.

This is a non-vendored implementation of the paper specification. Source
compatibility observations are disclosed and never hidden as implicit defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Profile:
    name: str
    rounding: str
    final_pool: str
    jump_shortcuts: bool


PAPER_ALGORITHM3 = Profile(
    name="paper_algorithm3",
    rounding="nearest_half_up",
    final_pool="selected_best_mutant_plus_crossover_children",
    jump_shortcuts=False,
)
ARTIFACT_GENERIC = Profile(
    name="artifact_generic",
    rounding="python_ties_to_even",
    final_pool="all_mutants_plus_crossover_children",
    jump_shortcuts=False,
)
ARTIFACT_JUMP_OPTIMIZED = Profile(
    name="artifact_jump_optimized",
    rounding="python_ties_to_even",
    final_pool="all_mutants_plus_crossover_children",
    jump_shortcuts=True,
)
PROFILES = {p.name: p for p in (PAPER_ALGORITHM3, ARTIFACT_GENERIC, ARTIFACT_JUMP_OPTIMIZED)}


@dataclass(frozen=True)
class Controls:
    lambda_real: float
    offspring_count: int
    mutation_probability: float
    crossover_probability: float


@dataclass(frozen=True)
class FixedTapeResult:
    profile: str
    parent_before: int
    parent_after: int
    selected_mutant: int
    selected_candidate: int
    strict_success: bool
    lambda_before: float
    lambda_after: float
    logical_evaluations: int
    final_pool: tuple[int, ...]


def _require_int(name: str, value: int, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _require_real(name: str, value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _resolve_profile(profile: Profile | str) -> Profile:
    if isinstance(profile, str):
        try:
            return PROFILES[profile]
        except KeyError as exc:
            raise ValueError(f"unknown profile: {profile}") from exc
    if not isinstance(profile, Profile):
        raise TypeError("profile must be a registered Profile or its name")
    registered = PROFILES.get(profile.name)
    if registered != profile:
        raise ValueError("profile value does not exactly match a registered profile")
    return registered


def validate_problem(n: int, k: int) -> None:
    _require_int("n", n, 11)
    _require_int("k", k, 1)
    if k >= n:
        raise ValueError("k must be smaller than n")


def validate_bit_string(bit_string: int, n: int) -> None:
    _require_int("bit_string", bit_string, 0)
    if bit_string >= 1 << n:
        raise ValueError("bit_string is outside the n-bit domain")


def jump_fitness(bit_string: int, n: int, k: int) -> tuple[int, bool]:
    """Return the exact author/paper Jump_k fitness and optimum flag."""

    validate_problem(n, k)
    validate_bit_string(bit_string, n)
    ones = bit_string.bit_count()
    if ones <= n - k or ones == n:
        value = k + ones
    else:
        value = n - ones
    return value, value == n + k


def _validated_positions(positions: Iterable[int], n: int) -> tuple[int, ...]:
    materialized = tuple(positions)
    for position in materialized:
        _require_int("bit position", position, 0)
        if position >= n:
            raise ValueError("bit position is outside the n-bit domain")
    if len(set(materialized)) != len(materialized):
        raise ValueError("bit positions must be distinct")
    return materialized


def mutate_exact_positions(parent: int, n: int, positions: Iterable[int]) -> int:
    """Flip exactly the supplied distinct zero-based bit positions."""

    _require_int("n", n, 11)
    validate_bit_string(parent, n)
    chosen = _validated_positions(positions, n)
    mask = sum(1 << position for position in chosen)
    return parent ^ mask


def crossover_from_mutant_positions(
    parent: int,
    mutant: int,
    n: int,
    take_mutant_positions: Iterable[int],
) -> int:
    """Take mutant bits at a supplied Bernoulli-mask realization.

    Positions are zero-based from the least-significant bit.  Supplying the
    realized mask makes the biased-uniform crossover formula deterministic;
    the stochastic generator remains profile/environment specific.
    """

    _require_int("n", n, 11)
    validate_bit_string(parent, n)
    validate_bit_string(mutant, n)
    chosen = _validated_positions(take_mutant_positions, n)
    mask = sum(1 << position for position in chosen)
    return (parent & ~mask) | (mutant & mask)


def rounded_offspring(lambda_real: float, profile: Profile | str) -> int:
    """Round real lambda according to one frozen profile."""

    profile = _resolve_profile(profile)
    value = _require_real("lambda_real", lambda_real)
    if value < 1:
        raise ValueError("lambda_real must be >= 1")
    if profile.rounding == "nearest_half_up":
        result = math.floor(value + 0.5)
    elif profile.rounding == "python_ties_to_even":
        result = round(value)
    else:
        raise ValueError(f"unsupported rounding mode: {profile.rounding}")
    return max(1, int(result))


def controls(
    lambda_real: float,
    n: int,
    profile: Profile | str,
    *,
    crossover_coefficient: float = 1.0,
) -> Controls:
    _require_int("n", n, 11)
    profile = _resolve_profile(profile)
    value = _require_real("lambda_real", lambda_real)
    if not 1 <= value <= n:
        raise ValueError("lambda_real must lie in [1,n]")
    coefficient = _require_real("crossover_coefficient", crossover_coefficient)
    if coefficient != 1.0:
        raise ValueError("EU26-07 Algorithm 3 requires crossover coefficient 1")
    return Controls(
        lambda_real=value,
        offspring_count=rounded_offspring(value, profile),
        mutation_probability=value / n,
        crossover_probability=1.0 / value,
    )


def next_lambda(
    lambda_real: float,
    *,
    strict_success: bool,
    update_factor: float,
    lambda_max: float,
    reset: bool = True,
) -> float:
    """Apply shrink/reset/grow using the pre-generation real lambda."""

    value = _require_real("lambda_real", lambda_real)
    cap = _require_real("lambda_max", lambda_max)
    factor = _require_real("update_factor", update_factor)
    if value < 1 or cap < 1 or value > cap:
        raise ValueError("require 1 <= lambda_real <= lambda_max")
    if factor <= 1:
        raise ValueError("update_factor must be > 1")
    if not isinstance(strict_success, bool):
        raise TypeError("strict_success must be boolean")
    if not isinstance(reset, bool):
        raise TypeError("reset must be boolean")
    if strict_success:
        return max(value / factor, 1.0)
    if reset and value == cap:
        return 1.0
    return min(value * factor ** 0.25, cap)


def _best_by_fitness(
    candidates: Sequence[int],
    n: int,
    k: int,
    tie_choice: int,
) -> int:
    if not candidates:
        raise ValueError("candidate set must not be empty")
    scored = [(jump_fitness(x, n, k)[0], x) for x in candidates]
    best_value = max(value for value, _ in scored)
    best = [x for value, x in scored if value == best_value]
    _require_int("tie_choice", tie_choice, 0)
    if tie_choice >= len(best):
        raise ValueError("tie_choice is outside the best-candidate set")
    return best[tie_choice]


def fixed_tape_generation(
    *,
    parent: int,
    n: int,
    k: int,
    lambda_real: float,
    update_factor: float,
    profile: Profile | str,
    mutation_children: Iterable[int],
    crossover_children: Iterable[int],
    mutation_tie_choice: int = 0,
    final_tie_choice: int = 0,
) -> FixedTapeResult:
    """Execute selection and update from caller-supplied offspring.

    The fixed tape removes RNG mapping from cross-language formula tests while
    retaining the paper/source final-pool distinction.
    """

    profile = _resolve_profile(profile)
    validate_problem(n, k)
    validate_bit_string(parent, n)
    ctl = controls(lambda_real, n, profile)
    mutants = tuple(mutation_children)
    crossovers = tuple(crossover_children)
    if len(mutants) != ctl.offspring_count or len(crossovers) != ctl.offspring_count:
        raise ValueError("fixed tape must contain exactly m mutants and m crossovers")
    for value in mutants + crossovers:
        validate_bit_string(value, n)
    selected_mutant = _best_by_fitness(mutants, n, k, mutation_tie_choice)
    if profile.final_pool == "selected_best_mutant_plus_crossover_children":
        raw_pool = (selected_mutant,) + crossovers
    elif profile.final_pool == "all_mutants_plus_crossover_children":
        raw_pool = mutants + crossovers
    else:
        raise ValueError(f"unsupported final-pool mode: {profile.final_pool}")
    final_pool = tuple(value for value in raw_pool if value != parent)
    old_fitness = jump_fitness(parent, n, k)[0]
    if final_pool:
        selected_candidate = _best_by_fitness(final_pool, n, k, final_tie_choice)
    else:
        selected_candidate = parent
    selected_fitness = jump_fitness(selected_candidate, n, k)[0]
    strict_success = selected_fitness > old_fitness
    parent_after = selected_candidate if selected_fitness >= old_fitness else parent
    lambda_after = next_lambda(
        lambda_real,
        strict_success=strict_success,
        update_factor=update_factor,
        lambda_max=float(n),
        reset=True,
    )
    return FixedTapeResult(
        profile=profile.name,
        parent_before=parent,
        parent_after=parent_after,
        selected_mutant=selected_mutant,
        selected_candidate=selected_candidate,
        strict_success=strict_success,
        lambda_before=float(lambda_real),
        lambda_after=lambda_after,
        logical_evaluations=2 * ctl.offspring_count,
        final_pool=final_pool,
    )

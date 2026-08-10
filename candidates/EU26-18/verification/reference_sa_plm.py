#!/usr/bin/env python3
"""Dependency-free clean-room kernel for the EU26-18 method audit.

This module implements only the paper's novel numerical kernel:

* Algorithm 4's distribution-index update;
* Algorithm 2's polynomial mutation equation; and
* the update/crossover/mutation ordering at Algorithms 3 lines 6-10.

It deliberately does not claim to be the authors' jMetal implementation or a
complete NSGA-II reproduction.  Ambiguities that require an explicit profile
choice are named in ``REFERENCE_PROFILE`` and recorded in the verification
contract.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import multiprocessing
import platform
import sys
from typing import Iterable, Sequence


PROFILE_ID = "eu26-18-clean-room-kernel-v1"
ETA_LOWER = 1.0
ETA_UPPER = 100.0
REFERENCE_PROFILE = {
    "profile_id": PROFILE_ID,
    "repair_semantics": "clamp_to_nearest_bound_assumption",
    "algorithm_2_current_value": "undefined_x_c_interpreted_as_current_x",
    "parent_update_semantics": "selected_parent_objects_updated_in_place",
    "strategy_inheritance": "both_updated_parents_share_eta_so_children_inherit_eta",
    "crossover_scope": "decision_vector_crossover_is_external_to_this_kernel",
    "rng_scope": "deterministic_probe_inputs_are_not_an_author_rng_reconstruction",
}


@dataclass(frozen=True)
class NoveltyStepResult:
    """Observable state for Algorithms 3-4 around one offspring pair."""

    events: tuple[str, ...]
    parent_eta_before: tuple[float, ...]
    parent_eta_after: tuple[float, ...]
    child_eta: tuple[float, float]
    child_vectors: tuple[tuple[float, ...], tuple[float, ...]]


@dataclass(frozen=True)
class ProbeCaseResult:
    """One deterministic formula probe used by process-worker tests."""

    run_id: int
    parent_eta_before: tuple[float, float]
    perturbation: float
    eta_after: float
    coordinate_before: float
    mutation_uniform: float
    coordinate_after: float


def _require_finite(name: str, value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def clamp_to_bounds(value: float, lower: float, upper: float) -> float:
    """Apply the declared clean-room interpretation of paper ``repair``."""

    value = _require_finite("value", value)
    lower = _require_finite("lower", lower)
    upper = _require_finite("upper", upper)
    if not lower < upper:
        raise ValueError("lower must be strictly less than upper")
    return min(max(value, lower), upper)


def paper_mutation_probability(decision_dimension: int) -> float:
    """Return Section 4.2's ``p_m = 1/n`` for decision variables only."""

    if isinstance(decision_dimension, bool) or not isinstance(decision_dimension, int):
        raise TypeError("decision_dimension must be an integer")
    if decision_dimension < 1:
        raise ValueError("decision_dimension must be positive")
    return 1.0 / decision_dimension


def update_distribution_index(
    parent_etas: Sequence[float],
    gaussian_perturbation: float,
    lower: float = ETA_LOWER,
    upper: float = ETA_UPPER,
) -> tuple[float, tuple[float, ...]]:
    """Transcribe Algorithm 4 for a supplied realization of ``N(0, 1)``.

    The stochastic sampler is intentionally outside this function.  Supplying
    the realization makes the formula directly testable and avoids pretending
    that the paper specifies an RNG implementation or seed.
    """

    if not parent_etas:
        raise ValueError("at least one selected parent is required")
    checked = tuple(_require_finite("parent eta", eta) for eta in parent_etas)
    lower = _require_finite("lower", lower)
    upper = _require_finite("upper", upper)
    if not lower < upper:
        raise ValueError("lower must be strictly less than upper")
    if any(eta < lower or eta > upper for eta in checked):
        raise ValueError("parent eta is outside the declared bounds")
    perturbation = _require_finite("gaussian perturbation", gaussian_perturbation)

    averaged = math.fsum(checked) / len(checked)
    repaired = clamp_to_bounds(averaged + perturbation, lower, upper)
    return repaired, tuple(repaired for _ in checked)


def polynomial_mutation_coordinate(
    current: float,
    lower: float,
    upper: float,
    eta_m: float,
    mutation_uniform: float,
) -> float:
    """Evaluate Algorithm 2 lines 4-18 for one selected coordinate.

    The paper's line 11 uses an undefined symbol ``x_c``.  This clean-room
    profile interprets it as the current coordinate ``x``.  The interpretation
    is tested and disclosed; it is not presented as recovered author code.
    """

    current = _require_finite("current", current)
    lower = _require_finite("lower", lower)
    upper = _require_finite("upper", upper)
    eta_m = _require_finite("eta_m", eta_m)
    mutation_uniform = _require_finite("mutation_uniform", mutation_uniform)
    if not lower < upper:
        raise ValueError("lower must be strictly less than upper")
    if current < lower or current > upper:
        raise ValueError("current coordinate is outside its bounds")
    if eta_m < 0.0:
        raise ValueError("eta_m must be non-negative")
    if mutation_uniform < 0.0 or mutation_uniform > 1.0:
        raise ValueError("mutation_uniform must be in [0, 1]")

    span = upper - lower
    delta_1 = (current - lower) / span
    delta_2 = (upper - current) / span
    exponent = eta_m + 1.0
    inverse_exponent = 1.0 / exponent

    if mutation_uniform <= 0.5:
        base = (
            2.0 * mutation_uniform
            + (1.0 - 2.0 * mutation_uniform)
            * (1.0 - delta_1) ** exponent
        )
        delta_q = base**inverse_exponent - 1.0
    else:
        base = (
            2.0 * (1.0 - mutation_uniform)
            + 2.0
            * (mutation_uniform - 0.5)
            * (1.0 - delta_2) ** exponent
        )
        delta_q = 1.0 - base**inverse_exponent

    mutated = current + delta_q * span
    return clamp_to_bounds(mutated, lower, upper)


def mutate_vector(
    values: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
    eta_m: float,
    mutation_probability: float,
    gate_uniforms: Sequence[float],
    mutation_uniforms: Sequence[float],
) -> tuple[float, ...]:
    """Apply Algorithm 2 with all random draws supplied explicitly."""

    lengths = {
        len(values),
        len(lower_bounds),
        len(upper_bounds),
        len(gate_uniforms),
        len(mutation_uniforms),
    }
    if len(lengths) != 1:
        raise ValueError("all coordinate-wise inputs must have equal length")
    probability = _require_finite("mutation_probability", mutation_probability)
    if probability < 0.0 or probability > 1.0:
        raise ValueError("mutation_probability must be in [0, 1]")

    result: list[float] = []
    for index, value in enumerate(values):
        gate = _require_finite(f"gate_uniforms[{index}]", gate_uniforms[index])
        if gate < 0.0 or gate > 1.0:
            raise ValueError("gate uniforms must be in [0, 1]")
        if gate < probability:
            result.append(
                polynomial_mutation_coordinate(
                    value,
                    lower_bounds[index],
                    upper_bounds[index],
                    eta_m,
                    mutation_uniforms[index],
                )
            )
        else:
            result.append(_require_finite(f"values[{index}]", value))
    return tuple(result)


def algorithm_3_novelty_step(
    parent_etas: Sequence[float],
    gaussian_perturbation: float,
    crossover_children: Sequence[Sequence[float]],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
    mutation_probability: float,
    gate_uniforms: Sequence[Sequence[float]],
    mutation_uniforms: Sequence[Sequence[float]],
) -> NoveltyStepResult:
    """Execute and expose the paper's novel Algorithms 3-4 step ordering.

    Parent selection and SBX decision-vector crossover are external.  Their two
    child vectors are inputs here, so the function cannot be mistaken for a
    complete NSGA-II implementation.
    """

    if len(crossover_children) != 2:
        raise ValueError("Algorithm 3 expects an offspring pair")
    if len(gate_uniforms) != 2 or len(mutation_uniforms) != 2:
        raise ValueError("random inputs must be supplied for both children")

    eta, updated_parent_etas = update_distribution_index(
        parent_etas, gaussian_perturbation
    )
    child_1 = mutate_vector(
        crossover_children[0],
        lower_bounds,
        upper_bounds,
        eta,
        mutation_probability,
        gate_uniforms[0],
        mutation_uniforms[0],
    )
    child_2 = mutate_vector(
        crossover_children[1],
        lower_bounds,
        upper_bounds,
        eta,
        mutation_probability,
        gate_uniforms[1],
        mutation_uniforms[1],
    )
    return NoveltyStepResult(
        events=(
            "algorithm3.line6.select_parents_external",
            "algorithm3.line7.update_distribution_index",
            "algorithm3.line8.sbx_crossover_external",
            "algorithm3.line9.mutate_child1",
            "algorithm3.line10.mutate_child2",
            "algorithm3.line11.append_offspring_pair",
        ),
        parent_eta_before=tuple(float(eta_value) for eta_value in parent_etas),
        parent_eta_after=updated_parent_etas,
        child_eta=(eta, eta),
        child_vectors=(child_1, child_2),
    )


def _unit_interval(master_seed: int, run_id: int, slot: int) -> float:
    payload = f"{master_seed}:{run_id}:{slot}".encode("ascii")
    integer = int.from_bytes(sha256(payload).digest()[:8], "big")
    return integer / ((1 << 64) - 1)


def evaluate_probe_case(run_id: int, master_seed: int) -> ProbeCaseResult:
    """Evaluate a scheduling-independent deterministic formula probe."""

    parent_etas = (
        ETA_LOWER + (ETA_UPPER - ETA_LOWER) * _unit_interval(master_seed, run_id, 0),
        ETA_LOWER + (ETA_UPPER - ETA_LOWER) * _unit_interval(master_seed, run_id, 1),
    )
    # This bounded deterministic input exercises Algorithm 4 but is not labeled
    # as a reconstructed Gaussian RNG stream.
    perturbation = 8.0 * (_unit_interval(master_seed, run_id, 2) - 0.5)
    eta_after, _ = update_distribution_index(parent_etas, perturbation)
    coordinate_before = _unit_interval(master_seed, run_id, 3)
    mutation_uniform = _unit_interval(master_seed, run_id, 4)
    coordinate_after = polynomial_mutation_coordinate(
        coordinate_before, 0.0, 1.0, eta_after, mutation_uniform
    )
    return ProbeCaseResult(
        run_id=run_id,
        parent_eta_before=parent_etas,
        perturbation=perturbation,
        eta_after=eta_after,
        coordinate_before=coordinate_before,
        mutation_uniform=mutation_uniform,
        coordinate_after=coordinate_after,
    )


def _evaluate_probe_arguments(arguments: tuple[int, int]) -> ProbeCaseResult:
    run_id, master_seed = arguments
    return evaluate_probe_case(run_id, master_seed)


def canonical_probe_digests(
    results: Iterable[ProbeCaseResult],
) -> tuple[str, str]:
    """Return exact same-machine and rounded cross-machine digests."""

    ordered = sorted(results, key=lambda result: result.run_id)
    exact_rows = []
    rounded_rows = []
    for result in ordered:
        exact_rows.append(
            {
                "run_id": result.run_id,
                "parent_eta_before": [value.hex() for value in result.parent_eta_before],
                "perturbation": result.perturbation.hex(),
                "eta_after": result.eta_after.hex(),
                "coordinate_before": result.coordinate_before.hex(),
                "mutation_uniform": result.mutation_uniform.hex(),
                "coordinate_after": result.coordinate_after.hex(),
            }
        )
        rounded_rows.append(
            {
                "run_id": result.run_id,
                "parent_eta_before": [
                    format(value, ".12e") for value in result.parent_eta_before
                ],
                "perturbation": format(result.perturbation, ".12e"),
                "eta_after": format(result.eta_after, ".12e"),
                "coordinate_before": format(result.coordinate_before, ".12e"),
                "mutation_uniform": format(result.mutation_uniform, ".12e"),
                "coordinate_after": format(result.coordinate_after, ".12e"),
            }
        )
    exact = json.dumps(exact_rows, sort_keys=True, separators=(",", ":"))
    rounded = json.dumps(rounded_rows, sort_keys=True, separators=(",", ":"))
    return sha256(exact.encode("ascii")).hexdigest(), sha256(
        rounded.encode("ascii")
    ).hexdigest()


def run_probe_suite(
    worker_count: int,
    case_count: int = 96,
    master_seed: int = 20260810,
) -> dict[str, object]:
    """Run formula probes serially or with a spawn-based process pool."""

    if worker_count < 1:
        raise ValueError("worker_count must be positive")
    if case_count < 1:
        raise ValueError("case_count must be positive")
    arguments = [(run_id, master_seed) for run_id in range(case_count)]
    if worker_count == 1:
        results = [_evaluate_probe_arguments(argument) for argument in arguments]
    else:
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(
            max_workers=worker_count, mp_context=context
        ) as executor:
            results = list(executor.map(_evaluate_probe_arguments, arguments))
    exact_digest, rounded_digest = canonical_probe_digests(results)
    return {
        "workers": worker_count,
        "case_count": case_count,
        "master_seed": master_seed,
        "exact_digest": exact_digest,
        "quantized_digest": rounded_digest,
    }


def build_machine_report(
    worker_counts: Sequence[int] = (1, 2, 4),
    case_count: int = 96,
    master_seed: int = 20260810,
) -> dict[str, object]:
    """Create a canonical report and fail if worker scheduling changes results."""

    if not worker_counts:
        raise ValueError("at least one worker count is required")
    if len(set(worker_counts)) != len(worker_counts):
        raise ValueError("worker counts must be unique")
    runs = [
        run_probe_suite(worker_count, case_count, master_seed)
        for worker_count in worker_counts
    ]
    exact = {str(run["exact_digest"]) for run in runs}
    quantized = {str(run["quantized_digest"]) for run in runs}
    if len(exact) != 1 or len(quantized) != 1:
        raise RuntimeError("formula results changed with process-worker count")
    return {
        "schema_version": 1,
        "candidate_id": "EU26-18",
        "requirements_tag": "STRICT_ADAPTIVE_GA_2026-08-10",
        "profile": REFERENCE_PROFILE,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "byteorder": sys.byteorder,
        },
        "case_count": case_count,
        "master_seed": master_seed,
        "worker_runs": runs,
        "exact_worker_invariance": True,
        "exact_digest": runs[0]["exact_digest"],
        "quantized_digest": runs[0]["quantized_digest"],
    }


def result_as_json(result: NoveltyStepResult) -> str:
    """Canonical serializer used by tests and audit examples."""

    return json.dumps(asdict(result), sort_keys=True, separators=(",", ":"))

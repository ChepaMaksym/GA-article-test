"""Stateful scalar-WBA searches with the preregistered QX checkpoints.

This is a new adapter, not a replacement for any historical runner. Native
CHC chunks retain their population, distance and random streams, but native
offspring history restarts inside each call. Lambda chunks reuse complete
generations from the frozen, single-mutant-selection component.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import asdict
import math
from numbers import Integral, Real
import random
from types import SimpleNamespace
from typing import Any, Callable, Iterator, Sequence

import numpy as np

from hybrid_1.core import best_index
from local_optima.generation import run_generation


ARMS = ("chc_qx", "lambda_adaptive_qx", "lambda_fixed1_qx")
DIMENSION = 40
INITIAL_COUNT = 50
SEARCH_SEED_OFFSET = 1000003


def _mask(value: Sequence[int]) -> tuple[int, ...]:
    bits = tuple(value)
    if len(bits) != DIMENSION or any(
        isinstance(bit, (bool, np.bool_)) or not isinstance(bit, Integral)
        or bit not in (0, 1) for bit in bits
    ):
        raise ValueError("mask must contain exactly 40 binary integers")
    return tuple(int(bit) for bit in bits)


def _score(value: Any) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError("WBA must be a scalar nonboolean real number")
    score = float(value)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError("WBA must be finite and lie in [0, 1]")
    return score


def _integer(value: Any, name: str, minimum: int) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a nonboolean integer")
    result = int(value)
    if result < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return result


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


@contextmanager
def _source_random_stream(seed: int) -> Iterator[None]:
    """Isolate the globals required by the unchanged, single-threaded source."""
    previous_python = random.getstate()
    previous_numpy = np.random.get_state()
    try:
        random.seed(seed)
        np.random.seed(seed)
        yield
    finally:
        random.setstate(previous_python)
        np.random.set_state(previous_numpy)


def run_qx_search(
    *,
    arm: str,
    initial_masks: Sequence[Sequence[int]],
    initial_scores: Sequence[float],
    active_objective: Callable[[tuple[int, ...]], float],
    full_objective: Callable[[tuple[int, ...]], float],
    seed: int,
    evolution: Any = None,
    deap_creator: Any = None,
    chunk_generations: int = 10,
    no_change_limit: int = 2,
    max_chunks: int = 20,
    on_chunk_completed: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run one arm; all full scores remain outside its search transition.

    Ordered initialization was physically evaluated by the preparation stage.
    Here it costs 50 logical calls and zero physical calls. Subsequent active
    queries are never cached. Only immutable full-checkpoint masks are cached.
    The optional callback receives detached JSON-safe progress only after a
    complete checkpoint. Persistence callbacks must not consume random streams.
    """
    if arm not in ARMS:
        raise ValueError("unknown QX search arm")
    if not callable(active_objective) or not callable(full_objective):
        raise TypeError("both objectives must be callable")
    if on_chunk_completed is not None and not callable(on_chunk_completed):
        raise TypeError("on_chunk_completed must be callable or None")
    seed = _integer(seed, "seed", 0)
    chunk_generations = _integer(chunk_generations, "chunk_generations", 1)
    no_change_limit = _integer(no_change_limit, "no_change_limit", 1)
    max_chunks = _integer(max_chunks, "max_chunks", 1)
    if seed + SEARCH_SEED_OFFSET > 2**32 - 1:
        raise ValueError("source-compatible search seed exceeds RandomState range")
    masks = tuple(_mask(mask) for mask in initial_masks)
    scores = tuple(_score(score) for score in initial_scores)
    if len(masks) != INITIAL_COUNT or len(scores) != INITIAL_COUNT:
        raise ValueError("exactly 50 ordered initial masks and scores are required")
    if arm == "chc_qx" and (evolution is None or deap_creator is None):
        raise ValueError("native source Evolution and DEAP creator are required for CHC")
    observed: dict[tuple[int, ...], float] = {}
    for mask, score in zip(masks, scores):
        if mask in observed and observed[mask] != score:
            raise ValueError("duplicate initial mask has conflicting scalar scores")
        observed[mask] = score

    active_trace: list[dict[str, Any]] = []
    initial_best = 0.0
    for call, (mask, score) in enumerate(zip(masks, scores), 1):
        initial_best = max(initial_best, score)
        active_trace.append({
            "call": call, "mask": list(mask), "wba": score,
            "phase": "initial_replay", "chunk": 0, "physical": False,
            "best_so_far_wba": initial_best,
        })
    active_best = initial_best
    active_physical = 0
    chunk = 0
    generation_count = 0
    generation_trace: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    full_evaluations: list[dict[str, Any]] = []
    full_cache: dict[tuple[int, ...], tuple[float, int]] = {}
    checkpoint_visits = 0
    best_full = 0.0
    selected_mask: tuple[int, ...] | None = None
    selected_full_call: int | None = None
    no_change = 0
    snapshot: dict[str, Any] | None = None
    last_snapshot: dict[str, Any] | None = None
    lambda_real = 1.0
    parent: tuple[int, ...] | None = None
    parent_score: tuple[float, float] | None = None
    population: list[Any] = []
    distance = DIMENSION // 4
    initial_parent_index: int | None = None
    rng = None if arm == "chc_qx" else np.random.default_rng(seed + SEARCH_SEED_OFFSET)

    def evaluate_active(mask_value: Sequence[int], phase: str) -> float:
        nonlocal active_best, active_physical
        mask = _mask(mask_value)
        score = _score(active_objective(mask))
        active_physical += 1
        if mask in observed and observed[mask] != score:
            raise ValueError("deterministic active objective changed a known mask score")
        observed[mask] = score
        active_best = max(active_best, score)
        active_trace.append({
            "call": len(active_trace) + 1, "mask": list(mask), "wba": score,
            "phase": phase, "chunk": chunk, "physical": True,
            "best_so_far_wba": active_best,
        })
        return score

    context = _source_random_stream(seed + SEARCH_SEED_OFFSET) if arm == "chc_qx" else nullcontext()
    with context:
        if arm == "chc_qx":
            dataset = SimpleNamespace(features=list(range(DIMENSION)))
            toolbox = evolution.create_toolbox("feature_selection", "validation", dataset, [])
            toolbox.unregister("evaluate")
            toolbox.register("evaluate", lambda mask: (evaluate_active(mask, "chc_offspring"),))
            for mask, score in zip(masks, scores):
                individual = deap_creator.Individual(list(mask))
                if tuple(individual.fitness.weights) != (1.0,):
                    raise ValueError("source CHC fitness must maximize one scalar component")
                individual.fitness.values = (score,)
                population.append(individual)
        else:
            initial_parent_index = best_index([(score, 0.0) for score in scores], rng)
            parent = masks[initial_parent_index]
            parent_score = (scores[initial_parent_index], 0.0)

        while chunk < max_chunks:
            chunk += 1
            best_before = active_best
            calls_before = len(active_trace)
            if arm == "chc_qx":
                distance_before = distance
                _, population, distance_value = evolution.CHC(
                    dataset, toolbox, distance, population,
                    max_generations=chunk_generations, verbose=0,
                )
                distance = _integer(distance_value, "source distance", 0)
                if len(population) != INITIAL_COUNT:
                    raise ValueError("source CHC changed population size")
                candidates = []
                population_scores = []
                for individual in population:
                    mask = _mask(individual)
                    if not individual.fitness.valid or len(individual.fitness.values) != 1:
                        raise ValueError("source CHC returned invalid scalar fitness")
                    score = _score(individual.fitness.values[0])
                    if mask not in observed or observed[mask] != score:
                        raise ValueError("source population score is absent from active query ledger")
                    candidates.append(mask)
                    population_scores.append(score)
                center_index = population_scores.index(max(population_scores))
                center, center_score = candidates[center_index], population_scores[center_index]
                generation_count += chunk_generations
                generation_trace.append({
                    "phase": "native_chc_chunk", "chunk": chunk,
                    "completed_generations": chunk_generations,
                    "generation": generation_count, "distance_before": distance_before,
                    "distance_after": distance, "calls_before": calls_before,
                    "calls_after": len(active_trace), "best_active_before": best_before,
                    "best_active_after": active_best,
                })
            else:
                for _ in range(chunk_generations):
                    offset = len(active_trace)
                    phase_index = 0
                    offspring_count = int(math.floor(lambda_real + 0.5))

                    def scalar_objective(mask: tuple[int, ...]) -> float:
                        nonlocal phase_index
                        phase = "mutation" if phase_index < offspring_count else "crossover"
                        phase_index += 1
                        return evaluate_active(mask, phase)

                    result = run_generation(
                        scalar_objective, parent=parent, parent_fitness=parent_score,
                        lambda_real=lambda_real, update_factor=1.5, reset=False,
                        rng=rng, call_offset=offset,
                    )
                    if result.calls_after != len(active_trace) or result.reset_event:
                        raise RuntimeError("complete-generation ledger or reset invariant failed")
                    parent, parent_score = result.parent_after, result.parent_fitness_after
                    if parent_score[1] != 0.0:
                        raise RuntimeError("non-scalar fitness reached the search state")
                    lambda_real = result.lambda_after if arm == "lambda_adaptive_qx" else 1.0
                    generation_count += 1
                    record = asdict(result)
                    record.pop("evaluations")
                    record.update({
                        "generation": generation_count, "chunk": chunk,
                        "proposed_lambda_after": result.lambda_after,
                        "applied_lambda_after": lambda_real, "lambda_after": lambda_real,
                    })
                    generation_trace.append(_json_value(record))
                candidates = [parent]
                center, center_score = parent, parent_score[0]

            last_snapshot = {
                "mask": list(center), "active_wba": float(center_score),
                "chunk": chunk, "generation": generation_count,
                "whole_chunk_generations": chunk_generations,
                "best_active_before": best_before, "best_active_after": active_best,
                "reason": "stagnation_not_observed",
            }
            if snapshot is None and active_best <= best_before:
                snapshot = {**last_snapshot, "reason": "first_whole_chunk_without_active_gain"}

            no_change += 1
            full_before = len(full_evaluations)
            visits = []
            for mask in candidates:
                checkpoint_visits += 1
                cache_hit = mask in full_cache
                if not cache_hit:
                    score = _score(full_objective(mask))
                    full_call = len(full_evaluations) + 1
                    full_cache[mask] = (score, full_call)
                    full_evaluations.append({
                        "call": full_call, "mask": list(mask), "wba": score,
                        "phase": "full_checkpoint", "chunk": chunk,
                    })
                score, full_call = full_cache[mask]
                strict_gain = score > best_full
                if strict_gain:
                    best_full = score
                    selected_mask, selected_full_call = mask, full_call
                    no_change = 0
                elif selected_mask is not None and score == best_full and (
                    sum(mask), full_call
                ) < (sum(selected_mask), selected_full_call):
                    selected_mask, selected_full_call = mask, full_call
                visits.append({
                    "mask": list(mask), "wba": score, "full_call": full_call,
                    "cache_hit": cache_hit, "strict_full_gain": strict_gain,
                })
            checkpoints.append({
                "chunk": chunk, "generation": generation_count,
                "best_active_before": best_before, "best_active": active_best,
                "best_full": best_full, "no_change": no_change,
                "active_logical_calls": len(active_trace),
                "active_physical_calls": active_physical,
                "full_calls": len(full_evaluations),
                "new_full_calls": len(full_evaluations) - full_before,
                "checkpoint_visits": checkpoint_visits,
                "candidate_visits": visits,
            })
            chunk_stop_reason = (
                "full_no_change" if no_change >= no_change_limit
                else "censored_safety_cap" if chunk == max_chunks else None
            )
            if on_chunk_completed is not None:
                on_chunk_completed(_json_value({
                    "schema": "eu26-21-chc-qx-progress-v1", "arm": arm, "seed": seed,
                    "chunk": chunk, "generation": generation_count,
                    "active_logical_calls": len(active_trace),
                    "active_physical_calls": active_physical,
                    "full_calls": len(full_evaluations),
                    "checkpoint_visits": checkpoint_visits,
                    "current_lambda": None if arm == "chc_qx" else lambda_real,
                    "no_change": no_change, "best_active_wba": active_best,
                    "best_full_wba": best_full,
                    "selected_mask": None if selected_mask is None else list(selected_mask),
                    "stop_reason": chunk_stop_reason,
                    "censored": chunk_stop_reason == "censored_safety_cap",
                }))
            # Natural stopping wins if the last allowed checkpoint satisfies both.
            if no_change >= no_change_limit:
                outer_stop_reason = "full_no_change"
                break
        else:
            outer_stop_reason = "censored_safety_cap"

        if snapshot is None:
            snapshot = last_snapshot
        if snapshot is None:
            raise RuntimeError("no complete chunk produced a diagnostic snapshot")
        terminal_state = {
            "generation_count": generation_count, "initial_parent_index": initial_parent_index,
            "parent_mask": None if parent is None else list(parent),
            "parent_active_wba": None if parent_score is None else parent_score[0],
            "final_lambda": None if arm == "chc_qx" else lambda_real,
            "final_distance": distance if arm == "chc_qx" else None,
            "population": [] if arm != "chc_qx" else [
                {"mask": list(_mask(individual)), "active_wba": _score(individual.fitness.values[0])}
                for individual in population
            ],
            "no_change": no_change, "best_active_wba": active_best,
            "best_full_wba": best_full, "selected_full_call": selected_full_call,
            "outer_stop_reason": outer_stop_reason,
            "rng_state": rng.bit_generator.state if rng is not None else {
                "python_random": random.getstate(), "numpy_random_state": np.random.get_state(),
            },
        }
    no_full_winner = selected_mask is None
    return _json_value({
        "schema": "eu26-21-chc-qx-search-v1", "arm": arm, "seed": seed,
        "search_seed": seed + SEARCH_SEED_OFFSET,
        "status": "no_full_winner" if no_full_winner else "evaluable",
        "selected_mask": None if no_full_winner else list(selected_mask),
        "full_validation_wba": None if no_full_winner else best_full,
        "active_logical_calls": len(active_trace), "active_physical_calls": active_physical,
        "initial_logical_calls": INITIAL_COUNT, "initial_physical_calls": 0,
        "full_calls": len(full_evaluations), "checkpoint_visits": checkpoint_visits,
        "chunks": chunk, "terminal_state": terminal_state,
        "stop_reason": "no_full_winner" if no_full_winner else outer_stop_reason,
        "snapshot": snapshot, "active_trace": active_trace,
        "generation_trace": generation_trace, "checkpoints": checkpoints,
        "full_evaluations": full_evaluations, "reset": False,
        "equal_objective_budget": False,
    })

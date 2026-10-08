"""Registered fixed-parameter GA kernel; it has no access to exact optima.

Scientific invocation belongs exclusively to GitHub Actions. This module has
no command-line entry point and performs no computation on import.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Mapping

import numpy as np

CHANNELS = {"initialization": 0, "selection": 1, "crossover": 2,
            "mutation": 3, "tie": 4}
SCHEMA = "ga-knapsack-search-v1"


@dataclass(frozen=True)
class Config:
    mutation_numerator: float
    crossover_probability: float
    population_size: int

    def __post_init__(self):
        if not np.isfinite(self.mutation_numerator) or self.mutation_numerator < 0:
            raise ValueError("mutation numerator must be finite and nonnegative")
        if not np.isfinite(self.crossover_probability) or not 0 <= self.crossover_probability <= 1:
            raise ValueError("crossover probability outside [0,1]")
        if not isinstance(self.population_size, int) or isinstance(self.population_size, bool) or self.population_size < 2:
            raise ValueError("population size must be an integer at least two")

    @property
    def configuration_id(self) -> str:
        def token(value):
            return format(value, ".12g").replace(".", "p")
        return f"m{token(self.mutation_numerator)}-c{token(self.crossover_probability)}-n{self.population_size}"

    def as_dict(self) -> dict:
        return {"configuration_id": self.configuration_id,
                "mutation_numerator": float(self.mutation_numerator),
                "crossover_probability": float(self.crossover_probability),
                "population_size": self.population_size}


def configuration_id(config: Config) -> str:
    return config.configuration_id


def configurations() -> tuple[Config, ...]:
    return tuple(Config(m, c, n) for m in (0.5, 1.0, 3.0)
                 for c in (0.0, 0.5, 0.9) for n in (10, 30, 50))


def make_rngs(class_code: int, index: int, seed: int) -> dict:
    if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in (class_code, index, seed)):
        raise ValueError("RNG identity requires nonnegative integers")
    return {name: np.random.Generator(np.random.PCG64(
        np.random.SeedSequence([class_code, index, seed, channel])))
        for name, channel in CHANNELS.items()}


def rng_snapshot(rngs: Mapping) -> tuple[dict, str]:
    states = {name: deepcopy(rngs[name].bit_generator.state) for name in CHANNELS}
    raw = json.dumps(states, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return states, hashlib.sha256(raw).hexdigest()


def evaluate_masks(instance, masks) -> dict[str, np.ndarray]:
    """Exact int64 sums, after excluding overflow, in original item order."""
    bits = np.asarray(masks)
    if bits.ndim != 2 or bits.shape[1] != instance.n or not np.all((bits == 0) | (bits == 1)):
        raise ValueError("mask matrix must contain only n binary positions")
    profits, weights = tuple(instance.profits), tuple(instance.weights)
    if len(profits) != instance.n or len(weights) != instance.n or instance.capacity < 0:
        raise ValueError("inconsistent instance dimension or capacity")
    if any(not isinstance(v, (int, np.integer)) or isinstance(v, (bool, np.bool_)) or v <= 0 for v in profits + weights):
        raise ValueError("positive integer item values required")
    if max(sum(map(int, profits)), sum(map(int, weights)), int(instance.capacity)) > np.iinfo(np.int64).max:
        raise ValueError("exact int64 objective guard exceeded")
    work = bits.astype(np.int64, copy=False)
    weight = work @ np.asarray(weights, dtype=np.int64)
    profit = work @ np.asarray(profits, dtype=np.int64)
    return {"weight": weight, "profit": profit,
            "feasible": weight <= instance.capacity}


def _key(weight: int, profit: int, capacity: int) -> tuple[int, int]:
    return (1, int(profit)) if weight <= capacity else (0, capacity - int(weight))


def _metrics(population: np.ndarray, masks, weight, profit, feasible) -> dict:
    chosen = population.tolist()
    acceptable = [int(profit[i]) for i in chosen if feasible[i]]
    return {"diversity": len({masks[i].tobytes() for i in chosen}) / len(chosen),
            "mean_feasible_profit": sum(acceptable) / len(acceptable) if acceptable else None,
            "feasible_fraction": len(acceptable) / len(chosen)}


def run_search(instance, config: Config, initial_masks, initial_scores: Mapping,
               rngs: Mapping, *, budget: int = 5000) -> dict:
    """Run to the exact request limit, including shared known initialization.

    initial_scores maps weight/profit/feasible to one-dimensional arrays. The
    known scores are validated independently by the outer evidence verifier;
    they are not physically recalculated by this kernel. All array request
    references are zero-based; the recorded request number is one-based.
    """
    if not isinstance(instance.n, int) or isinstance(instance.n, bool) or instance.n <= 0:
        raise ValueError("instance dimension must be a positive integer")
    if not isinstance(instance.capacity, int) or isinstance(instance.capacity, bool) or instance.capacity < 0:
        raise ValueError("capacity must be a nonnegative integer")
    if len(instance.weights) != instance.n or len(instance.profits) != instance.n:
        raise ValueError("item arrays do not match mask dimension")
    if any(not isinstance(v, (int, np.integer)) or isinstance(v, (bool, np.bool_)) or v <= 0
           for v in tuple(instance.weights) + tuple(instance.profits)):
        raise ValueError("positive integer item values required")
    n, size = int(instance.n), config.population_size
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < size:
        raise ValueError("budget must include the full initial population")
    if budget > np.iinfo(np.int32).max:
        raise ValueError("request index storage bound exceeded")
    if not 0 <= config.mutation_numerator / n <= 1:
        raise ValueError("mutation probability outside [0,1]")
    if size > np.iinfo(np.int16).max:
        raise ValueError("population index storage bound exceeded")
    if set(rngs) != set(CHANNELS) or len({id(rngs[k]) for k in CHANNELS}) != len(CHANNELS):
        raise ValueError("five distinct isolated RNG channels required")
    if any(not isinstance(rngs[k].bit_generator, np.random.PCG64) for k in CHANNELS):
        raise ValueError("registered PCG64 channels required")
    first = np.asarray(initial_masks)
    if first.shape != (size, n) or not np.all((first == 0) | (first == 1)):
        raise ValueError("initial masks must be the exact population-sized prefix")
    if set(initial_scores) != {"weight", "profit", "feasible"}:
        raise ValueError("initial scores must contain weight, profit and feasible")
    if any(np.asarray(initial_scores[k]).shape != (size,) for k in initial_scores):
        raise ValueError("initial score arrays have wrong dimension")
    if any(np.asarray(initial_scores[k]).dtype.kind not in "iu" for k in ("weight", "profit")):
        raise ValueError("initial objective scores must be integer arrays")
    if any(np.any(np.asarray(initial_scores[k]) < 0) for k in ("weight", "profit")):
        raise ValueError("initial objective scores cannot be negative")
    if not np.array_equal(np.asarray(initial_scores["feasible"], dtype=bool),
                          np.asarray(initial_scores["weight"]) <= instance.capacity):
        raise ValueError("initial feasibility flag does not match its weight")
    if max(sum(map(int, instance.profits)), sum(map(int, instance.weights)), int(instance.capacity)) > np.iinfo(np.int64).max:
        raise ValueError("exact integer sum storage bound exceeded")
    packed_n = (n + 7) // 8
    requests = {
        "masks": np.zeros((budget, n), dtype=np.uint8),
        "weight": np.zeros(budget, dtype=np.int64),
        "profit": np.zeros(budget, dtype=np.int64),
        "feasible": np.zeros(budget, dtype=np.bool_),
        "request": np.arange(1, budget + 1, dtype=np.int32),
        "generation": np.zeros(budget, dtype=np.int32),
        "phase": np.zeros(budget, dtype=np.uint8),
        "duplicate": np.zeros(budget, dtype=np.bool_),
        "parents": np.full((budget, 2), -1, dtype=np.int16),
        "tournaments": np.full((budget, 2, 2), -1, dtype=np.int16),
        "crossover_applied": np.zeros(budget, dtype=np.bool_),
        "crossover_bits": np.zeros((budget, packed_n), dtype=np.uint8),
        "mutation_bits": np.zeros((budget, packed_n), dtype=np.uint8),
    }
    masks, weight, profit, feasible = (requests[k] for k in ("masks", "weight", "profit", "feasible"))
    masks[:size] = first
    for name in ("weight", "profit", "feasible"):
        requests[name][:size] = initial_scores[name]
    weights = np.asarray(instance.weights, dtype=np.int64)
    profits = np.asarray(instance.profits, dtype=np.int64)
    seen, best_ref = set(), None
    def record(ref):
        nonlocal best_ref
        identity = masks[ref].tobytes()
        requests["duplicate"][ref] = identity in seen
        seen.add(identity)
        if feasible[ref] and (best_ref is None or profit[ref] > profit[best_ref]):
            best_ref = ref
    for ref in range(size):
        record(ref)
    population = np.arange(size, dtype=np.int32)
    states, digest = rng_snapshot(rngs)
    generations = [{"generation": 0, "complete": True, "first_request": 1,
                    "last_request": size, "population_before": [],
                    "population_after": population.tolist(), "elite": None,
                    "metrics_before": None,
                    "metrics_after": _metrics(population, masks, weight, profit, feasible),
                    "rng_states": states, "rng_state_sha256": digest}]
    used, generation, completed, partial = size, 0, 0, False
    while used < budget:
        generation += 1
        before = population.copy()
        keys = [_key(weight[ref], profit[ref], instance.capacity) for ref in population]
        optimum = max(keys)
        tied = [j for j, key in enumerate(keys) if key == optimum]
        elite_position = tied[int(rngs["tie"].integers(0, len(tied)))] if len(tied) > 1 else tied[0]
        elite_ref = int(population[elite_position])
        first_ref = used
        child_refs = []
        for _ in range(min(size - 1, budget - used)):
            ref = used
            selected = []
            for parent in range(2):
                pair = rngs["selection"].integers(0, size, size=2)
                requests["tournaments"][ref, parent] = pair
                a, b = int(pair[0]), int(pair[1])
                if keys[a] == keys[b]:
                    winner = int(pair[int(rngs["tie"].integers(0, 2))])
                else:
                    winner = a if keys[a] > keys[b] else b
                selected.append(winner)
            requests["parents"][ref] = selected
            a, b = (masks[population[j]] for j in selected)
            applied = bool(rngs["crossover"].random() < config.crossover_probability)
            requests["crossover_applied"][ref] = applied
            if applied:
                choices = rngs["crossover"].random(n) < 0.5
                child = np.where(choices, a, b).astype(np.uint8)
                requests["crossover_bits"][ref] = np.packbits(choices, bitorder="big")
            else:
                child = a.copy()
            flips = rngs["mutation"].random(n) < config.mutation_numerator / n
            requests["mutation_bits"][ref] = np.packbits(flips, bitorder="big")
            child ^= flips.astype(np.uint8)
            masks[ref] = child
            weight[ref], profit[ref] = child @ weights, child @ profits
            feasible[ref] = weight[ref] <= instance.capacity
            requests["generation"][ref] = generation
            requests["phase"][ref] = 1
            record(ref)
            child_refs.append(ref)
            used += 1
        complete = len(child_refs) == size - 1
        if complete:
            population = np.asarray([elite_ref] + child_refs, dtype=np.int32)
            completed += 1
        else:
            partial = True
        states, digest = rng_snapshot(rngs)
        generations.append({"generation": generation, "complete": complete,
                            "first_request": first_ref + 1, "last_request": used,
                            "population_before": before.tolist(),
                            "population_after": population.tolist(),
                            "elite": {"population_index": elite_position, "request_ref": elite_ref},
                            "metrics_before": _metrics(before, masks, weight, profit, feasible),
                            "metrics_after": _metrics(population, masks, weight, profit, feasible),
                            "rng_states": states, "rng_state_sha256": digest})
    summary = {"schema_version": SCHEMA, "status": "COMPLETE", **config.as_dict(),
               "n": n, "p_m": config.mutation_numerator / n,
               "p_c": config.crossover_probability, "N": size,
               "budget": budget, "logical_requests": used,
               "physical_evaluations": used - size, "known_initial_requests": size,
               "complete_generations": completed, "terminal_partial": partial,
               "terminal_population_requests": population.tolist(),
               "best_mask": "".join(map(str, masks[best_ref].tolist())) if best_ref is not None else None,
               "best_weight": int(weight[best_ref]) if best_ref is not None else None,
               "best_profit": int(profit[best_ref]) if best_ref is not None else None,
               "best_request": int(best_ref + 1) if best_ref is not None else None,
               "duplicate_count": int(np.count_nonzero(requests["duplicate"])),
               "invalid_request_count": int(np.count_nonzero(~feasible)),
               "rng_states_start": generations[0]["rng_states"],
               "rng_states_terminal": generations[-1]["rng_states"],
               "rng_state_sha256_start": generations[0]["rng_state_sha256"],
               "rng_state_sha256_terminal": generations[-1]["rng_state_sha256"]}
    return {"summary": summary, "requests": requests, "generations": generations}

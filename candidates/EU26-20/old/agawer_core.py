"""Independent, testable OLD core for Nematzadeh et al. AGAwER.

This module intentionally contains no PR8 hybrid logic.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class AdaptiveState:
    pc: float = 0.9
    pm: float = 0.4
    stagnation: int = 0
    adaptation_clock: int = 0


def offspring_counts(n_pop: int, pc: float, pm: float) -> tuple[int, int]:
    """Paper Eqs./text: nc=2*ceil(Pc*nPop/2), nm=ceil(Pm*nPop)."""
    if n_pop <= 0:
        raise ValueError("n_pop must be positive")
    nc = 2 * math.ceil(pc * n_pop / 2)
    nm = math.ceil(pm * n_pop)
    return nc, nm


def update_adaptation(state: AdaptiveState, improved: bool) -> AdaptiveState:
    """Paper control: reset on improvement; adapt every 5 stagnant iterations.

    The paper gives the sequence Pc 0.9,0.6,0.3,0 and Pm 0.4,0.6,0.8,1
    over a 20-iteration stagnation horizon.
    """
    if improved:
        return AdaptiveState()
    stagnation = state.stagnation + 1
    clock = state.adaptation_clock + 1
    pc, pm = state.pc, state.pm
    if clock == 5:
        pc = max(0.0, round(pc - 0.3, 10))
        pm = min(1.0, round(pm + 0.2, 10))
        clock = 0
    return AdaptiveState(pc=pc, pm=pm, stagnation=stagnation, adaptation_clock=clock)


def should_stop(state: AdaptiveState, iteration: int, best_fitness: float, max_it: int = 100) -> bool:
    return state.stagnation >= 20 or iteration >= max_it or best_fitness >= 1.0


def variable_single_point_crossover(a: Sequence[int], b: Sequence[int], rng: random.Random) -> tuple[list[int], list[int]]:
    a, b = list(a), list(b)
    if not a or not b:
        raise ValueError("solutions must be non-empty")
    if len(a) == len(b) == 1:
        return a.copy(), b.copy()
    if len(a) == 1:
        cb = rng.randint(1, len(b) - 1)
        return _unique(a + b[cb:]), _unique(b[:cb] + a)
    if len(b) == 1:
        ca = rng.randint(1, len(a) - 1)
        return _unique(b + a[ca:]), _unique(a[:ca] + b)
    ca = rng.randint(1, len(a) - 1)
    cb = rng.randint(1, len(b) - 1)
    return _unique(a[:ca] + b[cb:]), _unique(b[:cb] + a[ca:])


def replacement_mutation(solution: Sequence[int], search_space: Iterable[int], rng: random.Random) -> list[int]:
    x = list(solution)
    if not x:
        raise ValueError("solution must be non-empty")
    available = sorted(set(search_space) - set(x))
    if not available:
        return x.copy()
    j = rng.randrange(len(x))
    y = x.copy()
    y[j] = rng.choice(available)
    return _unique(y)


def roulette_probabilities(fitness: Sequence[float]) -> np.ndarray:
    f = np.asarray(fitness, dtype=float)
    if np.any(f < 0):
        raise ValueError("fitness must be non-negative")
    total = float(f.sum())
    if total == 0:
        return np.full(len(f), 1.0 / len(f))
    return f / total


def average_minimum_distance(s1: np.ndarray, s2: np.ndarray) -> float:
    """Paper Algorithm 3, symmetric average of nearest-feature distances."""
    a = np.asarray(s1, dtype=float)
    b = np.asarray(s2, dtype=float)
    if a.ndim == 1:
        a = a[:, None]
    if b.ndim == 1:
        b = b[:, None]
    if len(a) == 0 or len(b) == 0:
        raise ValueError("solutions must contain features")
    d = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
    return float((d.min(axis=1).mean() + d.min(axis=0).mean()) / 2.0)


def max_population_distance(population: Sequence[np.ndarray]) -> float:
    best = 0.0
    for i in range(len(population)):
        for j in range(i + 1, len(population)):
            best = max(best, average_minimum_distance(population[i], population[j]))
    return best


def repository_radius(population: Sequence[np.ndarray], beta: float = 2.0) -> float:
    if beta <= 0:
        raise ValueError("beta must be positive")
    return max_population_distance(population) / beta


def _unique(xs: Sequence[int]) -> list[int]:
    return list(dict.fromkeys(xs))

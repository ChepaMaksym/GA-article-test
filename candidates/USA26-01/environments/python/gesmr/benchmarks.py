"""Vectorized analytic objectives used in the GESMR paper.

Every function accepts a two-dimensional ``(population, dimension)``
NumPy array and returns one objective value per row.  All are direct
minimization objectives; this module contains no inverse-model machinery.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray

Objective = Callable[[ArrayLike], NDArray[np.float64]]


def _as_population(x: ArrayLike) -> NDArray[np.float64]:
    population = np.asarray(x, dtype=np.float64)
    if population.ndim != 2:
        raise ValueError("benchmark input must have shape (population, dimension)")
    if population.shape[1] < 1:
        raise ValueError("benchmark dimension must be positive")
    if not np.all(np.isfinite(population)):
        raise ValueError("benchmark input must be finite")
    return population


def sphere(x: ArrayLike) -> NDArray[np.float64]:
    population = _as_population(x)
    return np.sum(population * population, axis=1)


def ackley(x: ArrayLike) -> NDArray[np.float64]:
    population = _as_population(x)
    mean_square = np.mean(population * population, axis=1)
    mean_cosine = np.mean(np.cos(2.0 * np.pi * population), axis=1)
    return (
        -20.0 * np.exp(-0.2 * np.sqrt(mean_square))
        - np.exp(mean_cosine)
        + 20.0
        + np.e
    )


def griewank(x: ArrayLike) -> NDArray[np.float64]:
    population = _as_population(x)
    divisors = np.sqrt(np.arange(1, population.shape[1] + 1, dtype=np.float64))
    return (
        np.sum(population * population, axis=1) / 4000.0
        - np.prod(np.cos(population / divisors), axis=1)
        + 1.0
    )


def rastrigin(x: ArrayLike) -> NDArray[np.float64]:
    population = _as_population(x)
    dimension = population.shape[1]
    return 10.0 * dimension + np.sum(
        population * population - 10.0 * np.cos(2.0 * np.pi * population),
        axis=1,
    )


def rosenbrock(x: ArrayLike) -> NDArray[np.float64]:
    population = _as_population(x)
    if population.shape[1] < 2:
        raise ValueError("Rosenbrock requires dimension >= 2")
    left = population[:, :-1]
    right = population[:, 1:]
    return np.sum(100.0 * (right - left * left) ** 2 + (1.0 - left) ** 2, axis=1)


BENCHMARKS: dict[str, Objective] = {
    "ackley": ackley,
    "griewank": griewank,
    "rastrigin": rastrigin,
    "rosenbrock": rosenbrock,
    "sphere": sphere,
}


def get_benchmark(name: str) -> Objective:
    """Return a benchmark by its case-insensitive canonical name."""

    key = name.strip().lower()
    try:
        return BENCHMARKS[key]
    except KeyError as exc:
        names = ", ".join(sorted(BENCHMARKS))
        raise ValueError(f"unknown benchmark {name!r}; choose one of: {names}") from exc

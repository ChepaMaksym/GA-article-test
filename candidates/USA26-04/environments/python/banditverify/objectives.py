"""Independent binary64 ports of the six Appendix A objectives."""

from __future__ import annotations

import math
from collections.abc import Iterable
from numbers import Real


def _vector(values: Iterable[Real], *, minimum_length: int = 1) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError("objective input must be a numeric vector")
    try:
        raw = tuple(values)
    except TypeError as exc:
        raise TypeError("objective input must be an iterable numeric vector") from exc
    if len(raw) < minimum_length:
        raise ValueError(f"objective requires at least {minimum_length} value(s)")
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in raw):
        raise TypeError("objective values must be real numbers, not booleans")
    vector = tuple(float(value) for value in raw)
    if not all(math.isfinite(value) for value in vector):
        raise ValueError("objective values must be finite")
    return vector


def ackley(values: Iterable[Real]) -> float:
    x = _vector(values)
    dimension = len(x)
    mean_square = math.fsum(value * value for value in x) / dimension
    mean_cosine = math.fsum(math.cos(2.0 * math.pi * value) for value in x) / dimension
    return (
        -20.0 * math.exp(-0.2 * math.sqrt(mean_square))
        - math.exp(mean_cosine)
        + 20.0
        + math.e
    )


def griewank(values: Iterable[Real]) -> float:
    x = _vector(values)
    cosine_product = 1.0
    for paper_index, value in enumerate(x, start=1):
        cosine_product *= math.cos(value / math.sqrt(paper_index))
    return math.fsum(value * value for value in x) / 4000.0 - cosine_product + 1.0


def rastrigin(values: Iterable[Real]) -> float:
    x = _vector(values)
    return 10.0 * len(x) + math.fsum(
        value * value - 10.0 * math.cos(2.0 * math.pi * value) for value in x
    )


def rosenbrock(values: Iterable[Real]) -> float:
    x = _vector(values, minimum_length=2)
    return math.fsum(
        100.0 * (right - left * left) ** 2 + (left - 1.0) ** 2
        for left, right in zip(x[:-1], x[1:])
    )


def sphere(values: Iterable[Real]) -> float:
    x = _vector(values)
    return math.fsum(value * value for value in x)


def linear(values: Iterable[Real]) -> float:
    return math.fsum(_vector(values))


OBJECTIVES = {
    "ackley": ackley,
    "griewank": griewank,
    "rastrigin": rastrigin,
    "rosenbrock": rosenbrock,
    "sphere": sphere,
    "linear": linear,
}


def evaluate_objective(name: str, values: Iterable[Real]) -> float:
    if not isinstance(name, str):
        raise TypeError("objective name must be a string")
    try:
        objective = OBJECTIVES[name.strip().lower()]
    except KeyError as exc:
        raise ValueError(f"unknown objective: {name!r}") from exc
    result = objective(values)
    if not math.isfinite(result):
        raise ArithmeticError("objective produced a non-finite result")
    return result

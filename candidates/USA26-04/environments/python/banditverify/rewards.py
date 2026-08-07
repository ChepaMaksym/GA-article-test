"""The three prospectively separated USA26-04 reward interpretations."""

from __future__ import annotations

import math
from collections.abc import Iterable
from numbers import Real


def _pair(parent: Iterable[Real], child: Iterable[Real]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if isinstance(parent, (str, bytes)) or isinstance(child, (str, bytes)):
        raise TypeError("errors must be numeric vectors")
    try:
        parent_raw = tuple(parent)
        child_raw = tuple(child)
    except TypeError as exc:
        raise TypeError("errors must be iterable numeric vectors") from exc
    if not parent_raw or len(parent_raw) != len(child_raw):
        raise ValueError("parent and child errors must be equal-length nonempty vectors")
    combined = parent_raw + child_raw
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in combined):
        raise TypeError("error entries must be real numbers, not booleans")
    parent_values = tuple(float(value) for value in parent_raw)
    child_values = tuple(float(value) for value in child_raw)
    if not all(math.isfinite(value) for value in parent_values + child_values):
        raise ValueError("error entries must be finite")
    return parent_values, child_values


def evaluate_reward(
    semantics: str,
    parent: Iterable[Real],
    child: Iterable[Real],
) -> float:
    """Evaluate one named interpretation without resolving the paper conflict."""

    parent_values, child_values = _pair(parent, child)
    if semantics == "P1":
        terms = (left - right for left, right in zip(parent_values, child_values))
    elif semantics in {"P2", "P3"}:
        if any(value <= -1.0 for value in parent_values + child_values):
            raise ValueError(f"{semantics} requires every error entry to be greater than -1")
        if semantics == "P2":
            terms = (
                math.log1p(left) - math.log1p(right)
                for left, right in zip(parent_values, child_values)
            )
        else:
            terms = (
                math.log1p(right) - math.log1p(left)
                for left, right in zip(parent_values, child_values)
            )
    else:
        raise ValueError("reward semantics must be exactly P1, P2, or P3")
    return math.fsum(terms) / len(parent_values)


def printed_eq2_literal(parent: Iterable[Real], child: Iterable[Real]) -> float:
    """Expose the printed 0..m divided-by-m expression, including singularity.

    For ``n`` supplied entries the paper's final index is ``m=n-1``. This
    function exists only as an ambiguity witness and is not a reward option.
    """

    parent_values, child_values = _pair(parent, child)
    divisor = len(parent_values) - 1
    if divisor == 0:
        raise ZeroDivisionError("printed Eq. (2) divides a one-entry vector by m=0")
    if any(value <= -1.0 for value in parent_values + child_values):
        raise ValueError("printed log expression requires every entry to be greater than -1")
    numerator = math.fsum(
        math.log1p(left) - math.log1p(right)
        for left, right in zip(parent_values, child_values)
    )
    return numerator / divisor

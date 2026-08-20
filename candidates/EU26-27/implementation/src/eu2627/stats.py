from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class CompatibilityReport:
    raw_count: int
    independent_count: int
    raw_median: float
    independent_median: float
    median_ratio: float
    median_ratio_ci95: tuple[float, float]
    kolmogorov_distance: float
    ratio_pass: bool
    kolmogorov_pass: bool
    complete_pass: bool
    overall_pass: bool

    def canonical(self) -> dict:
        return {
            "raw_count": self.raw_count,
            "independent_count": self.independent_count,
            "raw_median": self.raw_median,
            "independent_median": self.independent_median,
            "median_ratio": self.median_ratio,
            "median_ratio_ci95": list(self.median_ratio_ci95),
            "kolmogorov_distance": self.kolmogorov_distance,
            "ratio_pass": self.ratio_pass,
            "kolmogorov_pass": self.kolmogorov_pass,
            "complete_pass": self.complete_pass,
            "overall_pass": self.overall_pass,
        }


def _validate(values: Sequence[int | float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or len(array) == 0:
        raise ValueError(f"{name} must be a non-empty vector")
    if not np.all(np.isfinite(array)) or np.any(array <= 0):
        raise ValueError(f"{name} contains invalid endpoints")
    return array


def kolmogorov_distance(
    a: Sequence[int | float], b: Sequence[int | float]
) -> float:
    x = np.sort(_validate(a, "a"))
    y = np.sort(_validate(b, "b"))
    support = np.unique(np.concatenate([x, y]))
    fx = np.searchsorted(x, support, side="right") / len(x)
    fy = np.searchsorted(y, support, side="right") / len(y)
    return float(np.max(np.abs(fx - fy)))


def compare_distributions(
    raw: Sequence[int | float],
    independent: Sequence[int | float],
    *,
    bootstrap_seed: int = 270000,
    resamples: int = 20_000,
    ratio_bounds: tuple[float, float] = (0.90, 1.10),
    max_kolmogorov: float = 0.20,
    required_independent_count: int = 100,
) -> CompatibilityReport:
    if resamples < 1000:
        raise ValueError("resamples must be at least 1000")
    raw_array = _validate(raw, "raw")
    independent_array = _validate(independent, "independent")
    rng = np.random.Generator(np.random.PCG64DXSM(int(bootstrap_seed)))
    ratios = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        raw_sample = rng.choice(raw_array, size=len(raw_array), replace=True)
        independent_sample = rng.choice(
            independent_array, size=len(independent_array), replace=True
        )
        ratios[index] = np.median(independent_sample) / np.median(raw_sample)
    low, high = (float(value) for value in np.quantile(ratios, [0.025, 0.975]))
    raw_median = float(median(raw_array))
    independent_median = float(median(independent_array))
    distance = kolmogorov_distance(raw_array, independent_array)
    ratio_pass = low >= ratio_bounds[0] and high <= ratio_bounds[1]
    kolmogorov_pass = distance <= max_kolmogorov
    complete_pass = len(independent_array) == required_independent_count
    return CompatibilityReport(
        raw_count=len(raw_array),
        independent_count=len(independent_array),
        raw_median=raw_median,
        independent_median=independent_median,
        median_ratio=independent_median / raw_median,
        median_ratio_ci95=(low, high),
        kolmogorov_distance=distance,
        ratio_pass=ratio_pass,
        kolmogorov_pass=kolmogorov_pass,
        complete_pass=complete_pass,
        overall_pass=ratio_pass and kolmogorov_pass and complete_pass,
    )

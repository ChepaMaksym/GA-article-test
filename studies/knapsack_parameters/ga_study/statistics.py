"""Prespecified family-level analysis; scientific execution belongs to CI only.

The four contrasts operate on within-instance 30-seed escape frequencies.
Families, not repetitions or source classes, are the bootstrap/jackknife unit.
No percentile/normal fallback is used when the BCa interval is undefined.
"""

from __future__ import annotations

import hashlib
import math
from statistics import NormalDist
from typing import Mapping, Sequence

import numpy as np


CONTRAST_IDS = (
    "mutation_3_over_1",
    "crossover_09_over_0",
    "population_50_over_10",
    "mutation_crossover_interaction",
)
MUTATION_NUMERATORS = (0.5, 1.0, 3.0)
CROSSOVER_PROBABILITIES = (0.0, 0.5, 0.9)
POPULATION_SIZES = (10, 30, 50)


def factorial_contrasts(rates: np.ndarray) -> np.ndarray:
    """Return the four registered contrasts from pm x pc x N escape rates."""
    values = np.asarray(rates, dtype=np.float64)
    if values.shape != (3, 3, 3):
        raise ValueError("escape frequencies must have pm x pc x N shape (3,3,3)")
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
        raise ValueError("escape frequencies must be finite and between zero and one")
    return np.asarray(
        [
            np.mean(values[2, :, :] - values[1, :, :]),
            np.mean(values[:, 2, :] - values[:, 0, :]),
            np.mean(values[:, :, 2] - values[:, :, 0]),
            np.mean((values[2, 2, :] - values[1, 2, :])
                    - (values[2, 0, :] - values[1, 0, :])),
        ],
        dtype=np.float64,
    )


def grouped_family_contrasts(
    instance_rates: Mapping[str, np.ndarray],
    instance_metadata: Mapping[str, Mapping[str, str]],
) -> tuple[list[dict], np.ndarray]:
    """Average admitted source classes inside each family before weighting families."""
    if not instance_rates:
        raise ValueError("at least one admitted instance is required")
    grouped: dict[str, list[tuple[str, np.ndarray]]] = {}
    for instance_id in sorted(instance_rates):
        if instance_id not in instance_metadata:
            raise ValueError(f"missing family metadata for {instance_id}")
        family = instance_metadata[instance_id]["family"]
        grouped.setdefault(family, []).append(
            (instance_id, factorial_contrasts(instance_rates[instance_id]))
        )
    memberships, vectors = [], []
    for family in sorted(grouped):
        entries = grouped[family]
        vector = np.mean(np.stack([entry[1] for entry in entries]), axis=0)
        vectors.append(vector)
        memberships.append({
            "family": family,
            "instances": [entry[0] for entry in entries],
            "classes": [instance_metadata[entry[0]]["class_label"] for entry in entries],
            "admitted_class_count": len(entries),
            "contrasts": dict(zip(CONTRAST_IDS, map(float, vector), strict=True)),
        })
    return memberships, np.stack(vectors)


def bca_family_intervals(
    family_values: np.ndarray,
    *,
    replicates: int = 50_000,
    seed: int = 51031,
    confidence_level: float = 0.9875,
    minimum_families: int = 5,
) -> dict:
    """BCa intervals with shared family draws and whole-family jackknife.

    Nondefault arguments are for deterministic CI fixtures, never outcome-based
    changes to a scientific series. Bias correction gives half weight to ties.
    """
    values = np.asarray(family_values, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(CONTRAST_IDS) or not len(values):
        raise ValueError("family contrasts require a nonempty family x 4 matrix")
    if not np.isfinite(values).all():
        raise ValueError("family contrasts must be finite")
    if type(replicates) is not int or replicates <= 1:
        raise ValueError("bootstrap replicate count must be an integer greater than one")
    if not 0 < confidence_level < 1 or minimum_families < 2:
        raise ValueError("invalid BCa confidence or minimum family count")
    n = len(values)
    estimates = values.mean(axis=0)
    output = {
        "method": "BCa",
        "bootstrap_unit": "whole source-index family",
        "jackknife_unit": "whole source-index family",
        "family_count": n,
        "replicates": replicates,
        "seed": seed,
        "rng": "PCG64(SeedSequence([51031]))" if seed == 51031 else f"PCG64(SeedSequence([{seed}]))",
        "confidence_level_each": confidence_level,
        "multiplicity": "Bonferroni for four prespecified contrasts",
        "nominal_joint_confidence": 1 - 4 * (1 - confidence_level),
        "ties": "half weight in bias correction",
        "quantile_method": "linear",
        "resample_index_sha256": None,
        "intervals": [],
    }
    if n < minimum_families:
        for name, estimate in zip(CONTRAST_IDS, estimates, strict=True):
            output["intervals"].append(_descriptive(name, estimate, "fewer_than_five_families"))
        return output
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed])))
    indices = rng.integers(0, n, size=(replicates, n))
    output["resample_index_sha256"] = hashlib.sha256(
        indices.astype("<i8", copy=False).tobytes(order="C")
    ).hexdigest()
    samples = values[indices].mean(axis=1)
    jackknife = (values.sum(axis=0) - values) / (n - 1)
    normal = NormalDist()
    alpha = 1 - confidence_level
    z_tails = [normal.inv_cdf(alpha / 2), normal.inv_cdf(1 - alpha / 2)]
    for column, name in enumerate(CONTRAST_IDS):
        observed = float(estimates[column])
        distribution = samples[:, column]
        if np.all(distribution == distribution[0]):
            output["intervals"].append(_descriptive(name, observed, "degenerate_bootstrap_distribution"))
            continue
        jack = jackknife[:, column]
        delta = jack.mean() - jack
        denominator = 6 * float(np.sum(delta ** 2)) ** 1.5
        if denominator == 0 or not math.isfinite(denominator):
            output["intervals"].append(_descriptive(name, observed, "undefined_jackknife_acceleration"))
            continue
        acceleration = float(np.sum(delta ** 3)) / denominator
        bias_fraction = float(
            (np.count_nonzero(distribution < observed)
             + 0.5 * np.count_nonzero(distribution == observed)) / replicates
        )
        if not 0 < bias_fraction < 1:
            output["intervals"].append(_descriptive(name, observed, "nonfinite_bias_correction"))
            continue
        z0 = normal.inv_cdf(bias_fraction)
        adjusted = []
        for z_alpha in z_tails:
            divisor = 1 - acceleration * (z0 + z_alpha)
            if divisor == 0 or not math.isfinite(divisor):
                adjusted.append(math.nan)
            else:
                adjusted.append(normal.cdf(z0 + (z0 + z_alpha) / divisor))
        if (not all(math.isfinite(p) and 0 < p < 1 for p in adjusted)
                or adjusted[0] >= adjusted[1]):
            output["intervals"].append(_descriptive(name, observed, "invalid_adjusted_quantiles"))
            continue
        low, high = map(float, np.quantile(distribution, adjusted, method="linear"))
        if not (math.isfinite(low) and math.isfinite(high)) or low >= high:
            output["intervals"].append(_descriptive(name, observed, "nonfinite_reversed_or_degenerate_interval"))
            continue
        output["intervals"].append({
            "contrast_id": name,
            "estimate": observed,
            "lower": low,
            "upper": high,
            "status": "INFERENTIAL_BCA",
            "reason": None,
            "positive_effect_supported": low > 0,
            "negative_effect_supported": high < 0,
            "bias_correction": z0,
            "bias_fraction": bias_fraction,
            "acceleration": acceleration,
            "adjusted_quantiles": adjusted,
        })
    return output


def _descriptive(name: str, estimate: float, reason: str) -> dict:
    return {
        "contrast_id": name,
        "estimate": float(estimate),
        "lower": None,
        "upper": None,
        "status": "DESCRIPTIVE_ONLY",
        "reason": reason,
        "positive_effect_supported": False,
        "negative_effect_supported": False,
    }


def descriptive(values: Sequence[float | int]) -> dict:
    """Descriptive summaries only; never a substitute confidence interval."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or not len(array) or not np.isfinite(array).all():
        raise ValueError("descriptive values must be nonempty and finite")
    return {
        "count": len(array),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
    }

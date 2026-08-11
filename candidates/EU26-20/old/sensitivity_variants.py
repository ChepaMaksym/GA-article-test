#!/usr/bin/env python3
"""Preregistered diagnostic variants around the frozen OLD paper profile.

The primary implementation in ``paper_profile.py`` is not modified. This module
patches one documented ambiguity at a time, restores every global afterward,
and labels all outputs sensitivity-only. It contains no PR #8/HYBRID logic.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import math
import random
from typing import Any, Iterator, Sequence

import numpy as np
from sklearn.cluster import KMeans

import paper_profile as base


@dataclass(frozen=True)
class Variant:
    name: str
    numpy_rng: str = "pcg64"
    offspring_rounding: str = "paper_ceil"
    stop_after: int = 20
    geometry: str = "feature_vectors_euclidean"


VARIANTS: dict[str, Variant] = {
    "legacy_mt19937_rng": Variant(
        name="legacy_mt19937_rng",
        numpy_rng="legacy_mt19937",
    ),
    "source_rounding": Variant(
        name="source_rounding",
        offspring_rounding="source_round_ties_to_even",
    ),
    "source_stop19": Variant(
        name="source_stop19",
        stop_after=19,
    ),
    "numeric_identifier_geometry": Variant(
        name="numeric_identifier_geometry",
        geometry="numeric_identifiers_euclidean",
    ),
    "source_like_bundle": Variant(
        name="source_like_bundle",
        numpy_rng="legacy_mt19937",
        offspring_rounding="source_round_ties_to_even",
        stop_after=19,
        geometry="numeric_identifiers_euclidean",
    ),
}


class LegacyRandomAdapter:
    """Expose Generator-like methods over the Python 3.9-era MT19937 API."""

    def __init__(self, seed: int):
        self.random_state = np.random.RandomState(seed)

    def integers(self, low: int, high: int) -> int:
        return int(self.random_state.randint(low, high))

    def choice(self, values: Sequence[int], size: int, replace: bool) -> np.ndarray:
        return np.asarray(
            self.random_state.choice(values, size=size, replace=replace)
        )


class NumericIdentifierGeometry(base.FeatureGeometry):
    """Public-source geometry: Euclidean distance between numeric feature IDs."""

    def __init__(self, x: np.ndarray, search_space: Sequence[int]):
        self.x = np.asarray(x, dtype=float)
        self.search_space = base.normalize_features(search_space)
        if max(self.search_space) >= self.x.shape[1]:
            raise ValueError("search space outside dataset")
        self.index = {
            feature: index for index, feature in enumerate(self.search_space)
        }
        self.vectors = np.asarray(self.search_space, dtype=float).reshape(-1, 1)
        delta = self.vectors[:, None, :] - self.vectors[None, :, :]
        self.pairwise = np.linalg.norm(delta, axis=2)

    def clusters(
        self,
        repository_features: Sequence[int],
        n_clusters: int,
        random_state: Any,
        n_init: int,
    ) -> dict[int, list[int]]:
        features = base.normalize_features(repository_features)
        if not 1 <= n_clusters <= len(features):
            raise ValueError("invalid KMeans cluster count")
        indices = [self.index[feature] for feature in features]
        labels = KMeans(
            n_clusters=n_clusters,
            n_init=n_init,
            random_state=random_state,
        ).fit_predict(self.vectors[indices])
        groups: dict[int, list[int]] = {}
        for feature, label in zip(features, labels.tolist()):
            groups.setdefault(int(label), []).append(feature)
        return groups


def source_round_counts(n_pop: int, pc: float, pm: float) -> tuple[int, int]:
    if n_pop <= 0 or not 0.0 <= pc <= 1.0 or not 0.0 <= pm <= 1.0:
        raise ValueError("invalid population/rates")
    return 2 * round(pc * n_pop / 2.0), round(pm * n_pop)


def legacy_generate_diverse_candidates(
    population: Sequence[base.Individual],
    repository_features: Sequence[int],
    geometry: base.FeatureGeometry,
    py_rng: random.Random,
    np_rng: LegacyRandomAdapter,
    config: base.PaperConfig,
) -> tuple[list[tuple[int, ...]], dict[str, Any]]:
    """Algorithm 4 with KMeans consuming the same MT19937 stream."""
    try:
        repository = base.normalize_features(repository_features)
    except ValueError as exc:
        raise base.RepositoryGenerationError(
            "external repository has no unused features"
        ) from exc
    q = max(1, int(math.sqrt(len(repository))))
    clusters = geometry.clusters(
        repository,
        q,
        np_rng.random_state,
        config.kmeans_n_init,
    )
    labels = sorted(clusters)
    radius = geometry.max_population_distance(population) / config.beta
    candidates: list[tuple[int, ...]] = []
    attempts = 0
    while len(candidates) < config.n_pop:
        attempts += 1
        if attempts > config.repository_attempt_limit:
            raise base.RepositoryGenerationError(
                f"could not generate {config.n_pop} diverse candidates "
                f"within {config.repository_attempt_limit} attempts"
            )
        selected_labels = py_rng.sample(labels, py_rng.randint(1, len(labels)))
        candidate = tuple(
            py_rng.choice(clusters[label]) for label in selected_labels
        )
        average = float(
            np.mean(
                [
                    geometry.solution_distance(candidate, member.features)
                    for member in population
                ]
            )
        )
        if average > radius:
            candidates.append(base.normalize_features(candidate))
    return candidates, {
        "q": q,
        "radius": float(radius),
        "attempts": attempts,
        "kmeans_seed": "shared_legacy_mt19937",
        "repository_size": len(repository),
    }


@dataclass
class _Originals:
    default_rng: Any
    geometry: Any
    offspring_counts: Any
    generate_diverse: Any


@contextmanager
def patched_variant(variant: Variant) -> Iterator[None]:
    originals = _Originals(
        default_rng=base.np.random.default_rng,
        geometry=base.FeatureGeometry,
        offspring_counts=base.paper_offspring_counts,
        generate_diverse=base.generate_diverse_candidates,
    )
    try:
        if variant.numpy_rng == "legacy_mt19937":
            base.np.random.default_rng = lambda seed: LegacyRandomAdapter(seed)
            base.generate_diverse_candidates = legacy_generate_diverse_candidates
        elif variant.numpy_rng != "pcg64":
            raise ValueError(f"unsupported variant RNG: {variant.numpy_rng}")

        if variant.geometry == "numeric_identifiers_euclidean":
            base.FeatureGeometry = NumericIdentifierGeometry
        elif variant.geometry != "feature_vectors_euclidean":
            raise ValueError(f"unsupported variant geometry: {variant.geometry}")

        if variant.offspring_rounding == "source_round_ties_to_even":
            base.paper_offspring_counts = source_round_counts
        elif variant.offspring_rounding != "paper_ceil":
            raise ValueError(
                f"unsupported variant rounding: {variant.offspring_rounding}"
            )
        yield
    finally:
        base.np.random.default_rng = originals.default_rng
        base.FeatureGeometry = originals.geometry
        base.paper_offspring_counts = originals.offspring_counts
        base.generate_diverse_candidates = originals.generate_diverse


def run_variant(
    x: np.ndarray,
    y: np.ndarray,
    search_space: Sequence[int],
    seed: int,
    variant_name: str,
    repository_attempt_limit: int = 100_000,
) -> dict[str, Any]:
    if variant_name not in VARIANTS:
        raise ValueError(f"unknown sensitivity variant: {variant_name}")
    variant = VARIANTS[variant_name]
    config = base.PaperConfig(
        stop_after=variant.stop_after,
        repository_attempt_limit=repository_attempt_limit,
    )
    with patched_variant(variant):
        result = base.run_paper_profile(x, y, search_space, seed, config)
    result.update(
        {
            "schema": "eu26-20-colon-sensitivity-v1",
            "profile": "old_sensitivity_only",
            "variant": variant.name,
            "numpy_rng_mode": variant.numpy_rng,
            "offspring_rounding": variant.offspring_rounding,
            "stop_after": variant.stop_after,
            "geometry": variant.geometry,
            "primary_gate_eligible": False,
        }
    )
    return result

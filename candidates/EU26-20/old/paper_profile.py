#!/usr/bin/env python3
"""Independent clean-room OLD implementation of the printed CMF-AGAwER flow.

This module contains no PR #8 or HYBRID logic. The implementation follows the
frozen resolutions in PAPER_PROFILE.md and intentionally does not reproduce
known defects in the public notebook-style source.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
import random
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import (
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.tree import DecisionTreeClassifier


@dataclass(frozen=True)
class Evaluation:
    accuracy: float
    precision: float
    recall: float
    fscore: float
    mcc: float


@dataclass(frozen=True)
class Individual:
    features: tuple[int, ...]
    evaluation: Evaluation

    @property
    def fitness(self) -> float:
        return self.evaluation.accuracy


@dataclass(frozen=True)
class PaperConfig:
    n_pop: int = 10
    pc_initial: float = 0.9
    pm_initial: float = 0.4
    adapt_after: int = 5
    stop_after: int = 20
    max_iterations: int = 100
    beta: float = 2.0
    initial_min_features: int = 1
    initial_max_features: int = 10
    repository_attempt_limit: int = 100_000
    kmeans_n_init: int = 10


class RepositoryGenerationError(RuntimeError):
    """Raised when Algorithm 4 cannot satisfy its diversity condition."""


class FitnessEvaluator:
    """Paper fitness: deterministic unshuffled stratified 5-fold decision tree."""

    def __init__(self, x: np.ndarray, y: np.ndarray):
        self.x = np.asarray(x, dtype=float)
        self.y = np.asarray(y)
        if self.x.ndim != 2 or self.y.ndim != 1 or len(self.x) != len(self.y):
            raise ValueError("invalid X/y shapes")
        labels, counts = np.unique(self.y, return_counts=True)
        if len(labels) < 2 or int(counts.min()) < 5:
            raise ValueError("each class needs at least five observations")
        self.nfe = 0

    def evaluate(self, features: Sequence[int]) -> Evaluation:
        subset = normalize_features(features)
        if max(subset) >= self.x.shape[1]:
            raise ValueError("feature index outside dataset")
        x_subset = self.x[:, subset]
        cv = StratifiedKFold(n_splits=5, shuffle=False)
        accuracy: list[float] = []
        precision: list[float] = []
        recall: list[float] = []
        fscore: list[float] = []
        mcc: list[float] = []
        for train, test in cv.split(x_subset, self.y):
            model = DecisionTreeClassifier(random_state=42)
            model.fit(x_subset[train], self.y[train])
            predicted = model.predict(x_subset[test])
            truth = self.y[test]
            accuracy.append(float(np.mean(predicted == truth)))
            precision.append(
                float(precision_score(truth, predicted, pos_label=1, zero_division=0))
            )
            recall.append(
                float(recall_score(truth, predicted, pos_label=1, zero_division=0))
            )
            fscore.append(
                float(f1_score(truth, predicted, pos_label=1, zero_division=0))
            )
            mcc.append(float(matthews_corrcoef(truth, predicted)))
        self.nfe += 1
        return Evaluation(
            accuracy=round(float(np.mean(accuracy)), 2),
            precision=round(float(np.mean(precision)), 2),
            recall=round(float(np.mean(recall)), 2),
            fscore=round(float(np.mean(fscore)), 2),
            mcc=round(float(np.mean(mcc)), 2),
        )


class FeatureGeometry:
    """Feature-vector geometry required by printed Algorithms 2-4."""

    def __init__(self, x: np.ndarray, search_space: Sequence[int]):
        self.x = np.asarray(x, dtype=float)
        self.search_space = normalize_features(search_space)
        if max(self.search_space) >= self.x.shape[1]:
            raise ValueError("search space outside dataset")
        self.index = {feature: i for i, feature in enumerate(self.search_space)}
        vectors = self.x[:, self.search_space].T
        delta = vectors[:, None, :] - vectors[None, :, :]
        self.pairwise = np.linalg.norm(delta, axis=2)

    def solution_distance(
        self, first: Sequence[int], second: Sequence[int]
    ) -> float:
        a = [self.index[value] for value in normalize_features(first)]
        b = [self.index[value] for value in normalize_features(second)]
        distances = self.pairwise[np.ix_(a, b)]
        return float(
            (distances.min(axis=1).mean() + distances.min(axis=0).mean()) / 2.0
        )

    def max_population_distance(self, population: Sequence[Individual]) -> float:
        maximum = 0.0
        for i in range(len(population)):
            for j in range(i + 1, len(population)):
                maximum = max(
                    maximum,
                    self.solution_distance(
                        population[i].features, population[j].features
                    ),
                )
        return maximum

    def clusters(
        self,
        repository_features: Sequence[int],
        n_clusters: int,
        random_state: int,
        n_init: int,
    ) -> dict[int, list[int]]:
        features = normalize_features(repository_features)
        if not 1 <= n_clusters <= len(features):
            raise ValueError("invalid KMeans cluster count")
        vectors = self.x[:, features].T
        labels = KMeans(
            n_clusters=n_clusters,
            n_init=n_init,
            random_state=random_state,
        ).fit_predict(vectors)
        grouped: dict[int, list[int]] = {}
        for feature, label in zip(features, labels.tolist()):
            grouped.setdefault(int(label), []).append(feature)
        return grouped


def normalize_features(features: Iterable[int]) -> tuple[int, ...]:
    values = tuple(dict.fromkeys(int(value) for value in features))
    if not values:
        raise ValueError("solution must contain at least one feature")
    if min(values) < 0:
        raise ValueError("feature indices must be non-negative")
    return values


def paper_offspring_counts(n_pop: int, pc: float, pm: float) -> tuple[int, int]:
    if n_pop <= 0 or not 0.0 <= pc <= 1.0 or not 0.0 <= pm <= 1.0:
        raise ValueError("invalid population/rates")
    return 2 * math.ceil(pc * n_pop / 2.0), math.ceil(pm * n_pop)


def roulette_index(population: Sequence[Individual], rng: random.Random) -> int:
    if not population:
        raise ValueError("empty population")
    weights = np.asarray([member.fitness for member in population], dtype=float)
    total = float(weights.sum())
    probabilities = (
        np.full(len(population), 1.0 / len(population))
        if total <= 0.0
        else weights / total
    )
    cumulative = np.cumsum(probabilities)
    index = int(np.searchsorted(cumulative, rng.random(), side="right"))
    return min(index, len(population) - 1)


def variable_single_point_crossover(
    first: Sequence[int],
    second: Sequence[int],
    rng: random.Random,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    a = list(normalize_features(first))
    b = list(normalize_features(second))
    if len(a) == len(b) == 1:
        return tuple(a), tuple(b)
    if len(a) == 1:
        point_b = rng.randint(1, len(b) - 1)
        return normalize_features(a + b[point_b:]), normalize_features(b[:point_b] + a)
    if len(b) == 1:
        point_a = rng.randint(1, len(a) - 1)
        return normalize_features(b + a[point_a:]), normalize_features(a[:point_a] + b)
    point_a = rng.randint(1, len(a) - 1)
    point_b = rng.randint(1, len(b) - 1)
    return (
        normalize_features(a[:point_a] + b[point_b:]),
        normalize_features(b[:point_b] + a[point_a:]),
    )


def replacement_mutation(
    solution: Sequence[int],
    search_space: Sequence[int],
    rng: random.Random,
) -> tuple[int, ...]:
    current = list(normalize_features(solution))
    pool = normalize_features(search_space)
    available = sorted(set(pool) - set(current))
    if not available:
        raise ValueError("mutation has no unused replacement feature")
    position = rng.randrange(len(current))
    current[position] = rng.choice(available)
    return normalize_features(current)


def update_rates(
    pc: float,
    pm: float,
    stagnation: int,
    adaptation_clock: int,
    improved: bool,
    config: PaperConfig,
) -> tuple[float, float, int, int, bool]:
    """Return rates/counters after one completed iteration."""
    if improved:
        return config.pc_initial, config.pm_initial, 0, 0, False
    stagnation += 1
    adaptation_clock += 1
    adapted = False
    if adaptation_clock == config.adapt_after:
        pc = max(0.0, round(pc - 0.3, 10))
        pm = min(1.0, round(pm + 0.2, 10))
        adaptation_clock = 0
        adapted = True
    return pc, pm, stagnation, adaptation_clock, adapted


def truncate(population: Sequence[Individual], n_pop: int) -> list[Individual]:
    return sorted(population, key=lambda member: member.fitness, reverse=True)[:n_pop]


def evaluate_candidates(
    candidates: Sequence[Sequence[int]], evaluator: FitnessEvaluator
) -> list[Individual]:
    return [
        Individual(normalize_features(candidate), evaluator.evaluate(candidate))
        for candidate in candidates
    ]


def generate_diverse_candidates(
    population: Sequence[Individual],
    repository_features: Sequence[int],
    geometry: FeatureGeometry,
    py_rng: random.Random,
    np_rng: np.random.Generator,
    config: PaperConfig,
) -> tuple[list[tuple[int, ...]], dict[str, Any]]:
    try:
        repository = normalize_features(repository_features)
    except ValueError as exc:
        raise RepositoryGenerationError("external repository has no unused features") from exc
    q = max(1, int(math.sqrt(len(repository))))
    kmeans_seed = int(np_rng.integers(0, 2**31 - 1))
    clusters = geometry.clusters(
        repository, q, kmeans_seed, config.kmeans_n_init
    )
    labels = sorted(clusters)
    radius = geometry.max_population_distance(population) / config.beta
    candidates: list[tuple[int, ...]] = []
    attempts = 0
    while len(candidates) < config.n_pop:
        attempts += 1
        if attempts > config.repository_attempt_limit:
            raise RepositoryGenerationError(
                f"could not generate {config.n_pop} diverse candidates "
                f"within {config.repository_attempt_limit} attempts"
            )
        chosen_labels = py_rng.sample(labels, py_rng.randint(1, len(labels)))
        candidate = tuple(py_rng.choice(clusters[label]) for label in chosen_labels)
        average = float(
            np.mean(
                [
                    geometry.solution_distance(candidate, member.features)
                    for member in population
                ]
            )
        )
        if average > radius:
            candidates.append(normalize_features(candidate))
    return candidates, {
        "q": q,
        "radius": float(radius),
        "attempts": attempts,
        "kmeans_seed": kmeans_seed,
        "repository_size": len(repository),
    }


def _initial_subset(
    search_space: tuple[int, ...],
    np_rng: np.random.Generator,
    config: PaperConfig,
) -> tuple[int, ...]:
    upper = min(config.initial_max_features, len(search_space))
    if config.initial_min_features > upper:
        raise ValueError("invalid initial subset bounds")
    size = int(np_rng.integers(config.initial_min_features, upper + 1))
    return tuple(
        int(value)
        for value in np_rng.choice(search_space, size=size, replace=False).tolist()
    )


def run_paper_profile(
    x: np.ndarray,
    y: np.ndarray,
    search_space: Sequence[int],
    seed: int,
    config: PaperConfig | None = None,
) -> dict[str, Any]:
    config = config or PaperConfig()
    if config.n_pop != 10:
        raise ValueError("the frozen paper profile requires n_pop=10")
    if config.beta <= 0 or config.repository_attempt_limit <= 0:
        raise ValueError("invalid repository configuration")
    pool = normalize_features(search_space)
    py_rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    evaluator = FitnessEvaluator(x, y)
    geometry = FeatureGeometry(x, pool)

    population = evaluate_candidates(
        [_initial_subset(pool, np_rng, config) for _ in range(config.n_pop)],
        evaluator,
    )
    used = {feature for member in population for feature in member.features}
    repository_features = tuple(sorted(set(pool) - used))
    initial_candidates, initial_repo_diag = generate_diverse_candidates(
        population, repository_features, geometry, py_rng, np_rng, config
    )
    initial_repository_population = evaluate_candidates(initial_candidates, evaluator)
    repository_memory = max(
        initial_repository_population, key=lambda member: member.fitness
    )
    population = truncate(population + [repository_memory], config.n_pop)
    best = population[0]

    pc = config.pc_initial
    pm = config.pm_initial
    stagnation = 0
    adaptation_clock = 0
    adaptive_events = 0
    iteration = 0
    first_target_iteration = 0 if best.fitness >= 0.94 else None
    first_target_nfe = evaluator.nfe if first_target_iteration == 0 else None
    trace: list[dict[str, Any]] = [
        {
            "iteration": 0,
            "best_accuracy": best.fitness,
            "subset_length": len(best.features),
            "nfe": evaluator.nfe,
            "pc_next": pc,
            "pm_next": pm,
            "stagnation": stagnation,
            "adapted": False,
            "repository": initial_repo_diag,
        }
    ]

    while (
        iteration < config.max_iterations
        and stagnation < config.stop_after
        and best.fitness < 1.0
    ):
        iteration += 1
        pc_used, pm_used = pc, pm
        nc, nm = paper_offspring_counts(config.n_pop, pc_used, pm_used)
        used = {feature for member in population for feature in member.features}

        crossover_children: list[Individual] = []
        for _ in range(nc // 2):
            first = population[roulette_index(population, py_rng)]
            second = population[roulette_index(population, py_rng)]
            child_a, child_b = variable_single_point_crossover(
                first.features, second.features, py_rng
            )
            evaluated = evaluate_candidates([child_a, child_b], evaluator)
            crossover_children.extend(evaluated)
            for child in evaluated:
                used.update(child.features)

        mutation_children: list[Individual] = []
        for _ in range(nm):
            parent = population[py_rng.randrange(config.n_pop)]
            child = replacement_mutation(parent.features, pool, py_rng)
            evaluated = Individual(child, evaluator.evaluate(child))
            mutation_children.append(evaluated)
            used.update(child)

        repository_features = tuple(sorted(set(pool) - used))
        current_candidates, repository_diag = generate_diverse_candidates(
            population,
            repository_features,
            geometry,
            py_rng,
            np_rng,
            config,
        )
        current_repository_population = evaluate_candidates(
            current_candidates, evaluator
        )
        current_best = max(
            current_repository_population, key=lambda member: member.fitness
        )
        memory_child_a, memory_child_b = variable_single_point_crossover(
            current_best.features, repository_memory.features, py_rng
        )
        memory_candidates = [current_best] + evaluate_candidates(
            [memory_child_a, memory_child_b], evaluator
        )
        current_memory_best = max(memory_candidates, key=lambda member: member.fitness)
        if current_memory_best.fitness > repository_memory.fitness:
            repository_memory = current_memory_best

        previous_best = best.fitness
        population = truncate(
            population
            + crossover_children
            + mutation_children
            + [repository_memory],
            config.n_pop,
        )
        best = population[0]
        improved = best.fitness > previous_best
        pc, pm, stagnation, adaptation_clock, adapted = update_rates(
            pc, pm, stagnation, adaptation_clock, improved, config
        )
        adaptive_events += int(adapted)

        if first_target_iteration is None and best.fitness >= 0.94:
            first_target_iteration = iteration
            first_target_nfe = evaluator.nfe

        trace.append(
            {
                "iteration": iteration,
                "best_accuracy": best.fitness,
                "subset_length": len(best.features),
                "nfe": evaluator.nfe,
                "pc_used": pc_used,
                "pm_used": pm_used,
                "nc": nc,
                "nm": nm,
                "pc_next": pc,
                "pm_next": pm,
                "stagnation": stagnation,
                "adapted": adapted,
                "repository": repository_diag,
            }
        )

    if best != population[0]:
        raise RuntimeError("best individual is not the elitist population head")
    if evaluator.nfe != trace[-1]["nfe"]:
        raise RuntimeError("NFE trace diverged")

    return {
        "schema": "eu26-20-colon-paper-old-v1",
        "profile": "paper_cleanroom_feature_geometry",
        "seed": int(seed),
        "offspring_rounding": "paper_ceil",
        "geometry": "feature_vectors_euclidean",
        "kmeans_n_init": config.kmeans_n_init,
        "best_accuracy": best.fitness,
        "subset_length": len(best.features),
        "features": list(best.features),
        **asdict(best.evaluation),
        "nfe": evaluator.nfe,
        "iterations": iteration,
        "adaptive_events": adaptive_events,
        "final_pc": pc,
        "final_pm": pm,
        "stagnation": stagnation,
        "first_target_iteration": first_target_iteration,
        "first_target_nfe": first_target_nfe,
        "trace": trace,
    }


def load_colon(upstream: str | Any) -> tuple[np.ndarray, np.ndarray, tuple[int, ...]]:
    from pathlib import Path

    root = Path(upstream).resolve()
    dataset = root / "Datasets" / "Colon.xlsx"
    features_path = (
        root
        / "The top 50 features selected from each ranker (CEI, MI, and FR) and their concatenation (features.npy)"
        / "Colon"
        / "features.npy"
    )
    frame = pd.read_excel(dataset, header=None)
    if frame.shape != (62, 2001):
        raise ValueError(f"unexpected Colon shape {frame.shape}")
    labels = frame.iloc[:, -1].replace({"Normal": 1, "Tumor": 2}).to_numpy()
    x = frame.iloc[:, :-1].to_numpy(dtype=float)
    counts = sorted(np.unique(labels, return_counts=True)[1].tolist())
    if counts != [22, 40]:
        raise ValueError(f"unexpected Colon class counts {counts}")
    search_space = normalize_features(
        np.load(features_path, allow_pickle=False).reshape(-1).tolist()
    )
    if len(search_space) != 128:
        raise ValueError(f"unexpected search-space size {len(search_space)}")
    return x, labels, search_space


def baseline_accuracy(x: np.ndarray, y: np.ndarray) -> float:
    evaluator = FitnessEvaluator(x, y)
    value = evaluator.evaluate(tuple(range(x.shape[1]))).accuracy
    if evaluator.nfe != 1:
        raise RuntimeError("baseline evaluator accounting failed")
    return value

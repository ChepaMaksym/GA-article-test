from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
from typing import Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class MTSPInstance:
    coordinates: np.ndarray
    distances: np.ndarray
    salesmen: int
    seed: int

    @property
    def n_nodes(self) -> int:
        return int(self.coordinates.shape[0])

    @property
    def customers(self) -> tuple[int, ...]:
        return tuple(range(1, self.n_nodes))

    @property
    def digest(self) -> str:
        payload = np.asarray(self.coordinates, dtype="<f8").tobytes(order="C")
        return sha256(payload).hexdigest()


def make_uniform_instance(seed: int = 20240809, n_nodes: int = 50, salesmen: int = 10) -> MTSPInstance:
    if n_nodes < 3:
        raise ValueError("n_nodes must be >= 3")
    if not 1 <= salesmen < n_nodes:
        raise ValueError("salesmen must satisfy 1 <= salesmen < n_nodes")
    rng = np.random.default_rng(seed)
    coordinates = rng.uniform(0.0, 1.0, size=(n_nodes, 2)).astype(np.float64)
    delta = coordinates[:, None, :] - coordinates[None, :, :]
    distances = np.sqrt(np.sum(delta * delta, axis=2), dtype=np.float64)
    return MTSPInstance(coordinates, distances, salesmen, seed)


def assert_permutation(order: Sequence[int], n_customers: int) -> None:
    if len(order) != n_customers:
        raise ValueError(f"expected {n_customers} genes, got {len(order)}")
    if tuple(sorted(order)) != tuple(range(1, n_customers + 1)):
        raise ValueError("chromosome is not a permutation of customer ids")


def nearest_neighbor_order(instance: MTSPInstance) -> tuple[int, ...]:
    remaining = set(instance.customers)
    current = 0
    order: list[int] = []
    while remaining:
        nxt = min(remaining, key=lambda x: (instance.distances[current, x], x))
        order.append(nxt)
        remaining.remove(nxt)
        current = nxt
    return tuple(order)


def route_cost(route: Sequence[int], distances: np.ndarray) -> float:
    if not route:
        return 0.0
    total = float(distances[0, route[0]])
    for a, b in zip(route, route[1:]):
        total += float(distances[a, b])
    total += float(distances[route[-1], 0])
    return total


def _segment_costs(order: Sequence[int], distances: np.ndarray) -> np.ndarray:
    n = len(order)
    o = np.asarray(order, dtype=np.int64)
    seg = np.full((n, n + 1), np.inf, dtype=np.float64)
    for i in range(n):
        current = float(distances[0, o[i]] + distances[o[i], 0])
        seg[i, i + 1] = current
        for j in range(i + 2, n + 1):
            prev = int(o[j - 2])
            cur = int(o[j - 1])
            current = current - float(distances[prev, 0]) + float(distances[prev, cur]) + float(distances[cur, 0])
            seg[i, j] = current
    return seg


def split_minmax(order: Sequence[int], instance: MTSPInstance, *, return_routes: bool = False):
    assert_permutation(order, instance.n_nodes - 1)
    n = len(order)
    m = instance.salesmen
    seg = _segment_costs(order, instance.distances)
    dp = np.full((m + 1, n + 1), np.inf, dtype=np.float64)
    parent = np.full((m + 1, n + 1), -1, dtype=np.int64)
    dp[0, 0] = 0.0
    for r in range(1, m + 1):
        for j in range(r, n + 1):
            starts = np.arange(r - 1, j, dtype=np.int64)
            vals = np.maximum(dp[r - 1, starts], seg[starts, j])
            idx = int(np.argmin(vals))
            dp[r, j] = float(vals[idx])
            parent[r, j] = int(starts[idx])
    value = float(dp[m, n])
    if not return_routes:
        return value
    routes: list[tuple[int, ...]] = []
    j = n
    for r in range(m, 0, -1):
        i = int(parent[r, j])
        if i < 0:
            raise RuntimeError("split backtracking failed")
        routes.append(tuple(order[i:j]))
        j = i
    routes.reverse()
    return value, tuple(routes)


def brute_force_split_minmax(order: Sequence[int], distances: np.ndarray, salesmen: int) -> float:
    n = len(order)
    best = float("inf")
    for cuts in combinations(range(1, n), salesmen - 1):
        boundaries = (0,) + cuts + (n,)
        value = max(route_cost(order[boundaries[i]:boundaries[i + 1]], distances) for i in range(salesmen))
        best = min(best, value)
    return best


def order_digest(order: Sequence[int]) -> str:
    return sha256(np.asarray(order, dtype="<i4").tobytes()).hexdigest()


def population_digest(population: Iterable[Sequence[int]]) -> str:
    h = sha256()
    for order in population:
        h.update(np.asarray(order, dtype="<i4").tobytes())
    return h.hexdigest()

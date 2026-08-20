from __future__ import annotations

from typing import Sequence

import numpy as np

from .core import MTSPInstance, assert_permutation

def _reinsert(order: Sequence[int], rng: np.random.Generator) -> tuple[int, ...]:
    x = list(order)
    i, j = rng.choice(len(x), size=2, replace=False)
    gene = x.pop(int(i))
    x.insert(int(j), gene)
    return tuple(x)


def _exchange(order: Sequence[int], rng: np.random.Generator) -> tuple[int, ...]:
    x = list(order)
    i, j = rng.choice(len(x), size=2, replace=False)
    x[int(i)], x[int(j)] = x[int(j)], x[int(i)]
    return tuple(x)


def _oropt(order: Sequence[int], rng: np.random.Generator, length: int) -> tuple[int, ...]:
    x = list(order)
    if len(x) <= length:
        return tuple(x)
    start = int(rng.integers(0, len(x) - length + 1))
    block = x[start:start + length]
    del x[start:start + length]
    insert_at = int(rng.integers(0, len(x) + 1))
    x[insert_at:insert_at] = block
    return tuple(x)



def sample_edit(order: Sequence[int], move_index: int, rng: np.random.Generator) -> tuple[int, tuple[int, ...]]:
    n = len(order)
    if move_index == 0:
        i, j = (int(x) for x in rng.choice(n, size=2, replace=False))
        return move_index, (i, j)
    if move_index == 1:
        i, j = (int(x) for x in rng.choice(n, size=2, replace=False))
        return move_index, (i, j)
    if move_index in (2, 3):
        length = 2 if move_index == 2 else 3
        start = int(rng.integers(0, n - length + 1))
        insert_at = int(rng.integers(0, n - length + 1))
        return move_index, (start, insert_at)
    raise ValueError("invalid move index")


def apply_edit(order: Sequence[int], edit: tuple[int, tuple[int, ...]]) -> tuple[int, ...]:
    move_index, params = edit
    x = list(order)
    if move_index == 0:
        i, j = params
        gene = x.pop(i)
        x.insert(j, gene)
    elif move_index == 1:
        i, j = params
        x[i], x[j] = x[j], x[i]
    elif move_index in (2, 3):
        length = 2 if move_index == 2 else 3
        start, insert_at = params
        block = x[start:start + length]
        del x[start:start + length]
        insert_at = min(insert_at, len(x))
        x[insert_at:insert_at] = block
    else:
        raise ValueError("invalid move index")
    out = tuple(x)
    assert_permutation(out, len(order))
    return out

def apply_move(order: Sequence[int], move_index: int, rng: np.random.Generator) -> tuple[int, ...]:
    if move_index == 0:
        out = _reinsert(order, rng)
    elif move_index == 1:
        out = _exchange(order, rng)
    elif move_index == 2:
        out = _oropt(order, rng, 2)
    elif move_index == 3:
        out = _oropt(order, rng, 3)
    else:
        raise ValueError("invalid move index")
    assert_permutation(out, len(order))
    return out


def order_crossover(parent1: Sequence[int], parent2: Sequence[int], rng: np.random.Generator) -> tuple[int, ...]:
    n = len(parent1)
    a, b = sorted(int(x) for x in rng.choice(n, size=2, replace=False))
    if a == b:
        b = min(n, a + 1)
    child: list[int | None] = [None] * n
    child[a:b] = parent1[a:b]
    fill = [g for g in parent2 if g not in child]
    pos = [i for i, value in enumerate(child) if value is None]
    for i, g in zip(pos, fill):
        child[i] = g
    out = tuple(int(x) for x in child)
    assert_permutation(out, n)
    return out


def biased_permutation_crossover(parent: Sequence[int], mutant: Sequence[int], probability: float, rng: np.random.Generator) -> tuple[int, ...]:
    if not 0 < probability <= 1:
        raise ValueError("probability must be in (0,1]")
    n = len(parent)
    mask = rng.random(n) < probability
    if not mask.any():
        mask[int(rng.integers(0, n))] = True
    child: list[int | None] = [None] * n
    used: set[int] = set()
    for i in np.flatnonzero(mask):
        gene = int(mutant[int(i)])
        if gene not in used:
            child[int(i)] = gene
            used.add(gene)
    remaining = [int(g) for g in parent if int(g) not in used]
    it = iter(remaining)
    for i in range(n):
        if child[i] is None:
            child[i] = next(it)
    out = tuple(int(x) for x in child)
    if out == tuple(parent):
        # Force one mutant-derived structural difference without breaking closure.
        diff = [i for i, (a, b) in enumerate(zip(parent, mutant)) if a != b]
        if diff:
            i = diff[0]
            j = out.index(mutant[i])
            x = list(out)
            x[i], x[j] = x[j], x[i]
            out = tuple(x)
    assert_permutation(out, n)
    return out




def adjacency_surrogate(order: Sequence[int], instance: MTSPInstance) -> float:
    """Cheap structural surrogate used only to educate permutation edits.

    It is not a logical mTSP objective evaluation and is never used for final
    selection or hypothesis testing.
    """
    x = tuple(int(v) for v in order)
    if not x:
        return 0.0
    d = instance.distances
    value = float(d[0, x[0]])
    value += sum(float(d[a, b]) for a, b in zip(x, x[1:]))
    value += float(d[x[-1], 0])
    return value


def guided_move(
    order: Sequence[int],
    move_index: int,
    rng: np.random.Generator,
    instance: MTSPInstance,
    trials: int = 6,
) -> tuple[int, ...]:
    """Choose the structurally best of several legal edits of one move type."""
    if trials < 1:
        raise ValueError("trials must be positive")
    candidates = [apply_move(order, move_index, rng) for _ in range(trials)]
    return min(candidates, key=lambda x: (adjacency_surrogate(x, instance), x))

def positive_binomial(rng: np.random.Generator, n: int, p: float) -> int:
    if not 0 < p <= 1:
        raise ValueError("p must be in (0,1]")
    for _ in range(10000):
        value = int(rng.binomial(n, p))
        if value > 0:
            return value
    raise RuntimeError("positive binomial sampling failed")



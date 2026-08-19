import hashlib
import json
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

import pytest

from old.moea_isa_kernel import (
    FormulaCase,
    FormulaDomainError,
    crossover_count,
    interval_bounds,
    jaccard_similarity,
    matlab_round_nonnegative,
    roulette_index,
    state_index,
    update_probability_table,
)


def test_matlab_rounding():
    assert matlab_round_nonnegative(2.5) == 3
    assert matlab_round_nonnegative(2.49) == 2


def test_jaccard_state_boundaries():
    assert jaccard_similarity((1, 0, 1, 0), (1, 1, 0, 0)) == pytest.approx(1 / 3)
    assert state_index(0.05) == 1
    assert state_index(0.0500001) == 2
    assert state_index(1.0) == 20


def test_all_zero_parent_pair_fails_closed():
    with pytest.raises(FormulaDomainError):
        jaccard_similarity((0, 0), (0, 0))


def test_crossover_count_source_semantics():
    p1 = (1, 1, 0, 0, 1)
    p2 = (1, 0, 1, 0, 0)
    assert crossover_count(p1, p2, 1) == 1
    assert crossover_count(p1, p2, 5) == 2
    assert crossover_count(p1, p2, 10) == 3


def test_initial_intervals():
    assert interval_bounds(100, 1) == (1, 20)
    assert interval_bounds(100, 5) == (81, 100)
    assert interval_bounds(101, 2) == (21, 40)


def test_roulette_zero_floor():
    assert roulette_index((0, 0, 0), 0.0) == 1
    assert roulette_index((0, 0, 0), 0.999999) == 3
    assert roulette_index((0.9, 0.1), 0.89) == 1
    assert roulette_index((0.9, 0.1), 0.95) == 2


def test_probability_update_only_observed_cells():
    got = update_probability_table(
        [[0.0, 0.2], [0.4, 0.6]],
        [[0, 2], [1, 0]],
        [[0, 4], [1, 0]],
    )
    assert got[0] == pytest.approx([0.0, 0.29])
    assert got[1] == pytest.approx([0.58, 0.6])


CASES = [
    FormulaCase((1, 0, 1, 0), (1, 1, 0, 0), 1),
    FormulaCase((1, 1, 1, 0), (0, 1, 0, 1), 5),
    FormulaCase((1, 0, 0, 1), (0, 1, 1, 0), 10),
]


def _canonical(case):
    return case.canonical()


def _digest(rows):
    payload = json.dumps(rows, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def test_worker_invariance():
    serial = [_canonical(case) for case in CASES]
    ctx = mp.get_context("spawn")
    for workers in (1, 2, 4):
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
            parallel = list(pool.map(_canonical, CASES))
        assert parallel == serial
        assert _digest(parallel) == _digest(serial)

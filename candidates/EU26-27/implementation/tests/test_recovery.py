from __future__ import annotations

import numpy as np
import pytest

from eu2627.old import run_two_rate_old
from eu2627.recovery import (
    lower_group,
    recovery_campaign_digest,
    run_recovery_campaign,
    run_two_rate_recovery,
    select_winner_index,
    split_counts,
)


def test_split_counts_match_frozen_recovery_contract() -> None:
    assert split_counts(10, "balanced") == (5, 5)
    assert split_counts(10, "literal_one_based") == (4, 6)
    assert [lower_group(i, 10, "literal_one_based") for i in range(10)] == [
        True, True, True, True, False, False, False, False, False, False
    ]


def test_first_tie_is_literal_first_maximum_without_extra_choice() -> None:
    rng = np.random.Generator(np.random.PCG64DXSM(7))
    state_before = rng.bit_generator.state
    assert select_winner_index([0, 5, 5, 1], tie_policy="first", rng=rng) == 1
    assert rng.bit_generator.state == state_before


def test_uniform_tie_selects_only_maxima() -> None:
    rng = np.random.Generator(np.random.PCG64DXSM(11))
    observed = {
        select_winner_index([0, 5, 5, 1], tie_policy="uniform", rng=rng)
        for _ in range(100)
    }
    assert observed <= {1, 2}
    assert observed == {1, 2}


def test_invalid_recovery_policies_fail_closed() -> None:
    rng = np.random.Generator(np.random.PCG64DXSM(1))
    with pytest.raises(ValueError):
        select_winner_index([1], tie_policy="unknown", rng=rng)
    with pytest.raises(ValueError):
        lower_group(0, 10, "unknown")
    with pytest.raises(ValueError):
        run_recovery_campaign([1], tie_policy="uniform", split_policy="bad")


def test_r1_preserves_rejected_baseline_semantics() -> None:
    baseline = run_two_rate_old(270001, n=20, offspring=10, max_evaluations=100_000)
    recovery = run_two_rate_recovery(
        270001,
        tie_policy="uniform",
        split_policy="balanced",
        n=20,
        offspring=10,
        max_evaluations=100_000,
    )
    assert recovery.complete == baseline.complete
    assert recovery.evaluations == baseline.evaluations
    assert recovery.generations == baseline.generations
    assert recovery.final_rate == baseline.final_rate
    assert recovery.lower_winners == baseline.lower_winners
    assert recovery.higher_winners == baseline.higher_winners
    assert recovery.archive_digest == baseline.archive_digest
    assert recovery.first_hits == baseline.first_hits
    assert recovery.effort == baseline.effort


@pytest.mark.parametrize(
    ("tie_policy", "split_policy"),
    [
        ("uniform", "balanced"),
        ("first", "balanced"),
        ("uniform", "literal_one_based"),
        ("first", "literal_one_based"),
    ],
)
def test_same_seed_is_exactly_reproducible(tie_policy: str, split_policy: str) -> None:
    a = run_two_rate_recovery(
        271001,
        tie_policy=tie_policy,
        split_policy=split_policy,
        n=20,
        offspring=10,
        max_evaluations=100_000,
    )
    b = run_two_rate_recovery(
        271001,
        tie_policy=tie_policy,
        split_policy=split_policy,
        n=20,
        offspring=10,
        max_evaluations=100_000,
    )
    assert a.canonical() == b.canonical()


@pytest.mark.parametrize(
    ("tie_policy", "split_policy"),
    [("first", "balanced"), ("first", "literal_one_based")],
)
def test_worker_1_2_digest_equality(tie_policy: str, split_policy: str) -> None:
    seeds = range(271001, 271005)
    serial = run_recovery_campaign(
        seeds,
        tie_policy=tie_policy,
        split_policy=split_policy,
        workers=1,
        n=20,
        offspring=10,
        max_evaluations=100_000,
    )
    parallel = run_recovery_campaign(
        seeds,
        tie_policy=tie_policy,
        split_policy=split_policy,
        workers=2,
        n=20,
        offspring=10,
        max_evaluations=100_000,
    )
    assert recovery_campaign_digest(serial) == recovery_campaign_digest(parallel)

import csv
import zipfile
from pathlib import Path

import numpy as np
import pytest

from eu2627.artifact import parse_raw_endpoint
from eu2627.campaign import campaign_digest, run_campaign
from eu2627.core import (
    EffortLedger,
    conditional_mutation,
    hypervolume,
    hypervolume_contribution,
    oneminmax_objective,
)
from eu2627.old import run_two_rate_old, update_two_rate
from eu2627.stats import compare_distributions, kolmogorov_distance


def test_oneminmax_objective():
    assert oneminmax_objective(0b1011, 4) == (3, 1)
    with pytest.raises(ValueError):
        oneminmax_objective(16, 4)


def test_hypervolume_and_contribution_exact_integer_oracle():
    assert hypervolume([0, 4], 4) == 9
    assert hypervolume([0, 2, 4], 4) == 13
    assert hypervolume_contribution([0, 4], 2, 4) == 4
    assert hypervolume_contribution([0, 2, 4], 2, 4) == 0


def test_conditional_mutation_is_nonzero_and_closed():
    rng = np.random.Generator(np.random.PCG64DXSM(9))
    for probability in (0.001, 0.1, 0.5, 1.0):
        child, strength = conditional_mutation(0, 100, probability, rng)
        assert 1 <= strength <= 100
        assert child.bit_count() == strength


def test_effort_ledger_rejects_accounting_drift():
    EffortLedger(21, 20, 20, 30, 4, 2).validate(10)
    with pytest.raises(RuntimeError):
        EffortLedger(20, 20, 20, 30, 4, 2).validate(10)


def test_two_rate_fixed_tape_boundaries():
    assert update_two_rate(1.0, "lower", 0.0, 100) == 0.5
    assert update_two_rate(1.0, "lower", 0.749999, 100) == 0.5
    assert update_two_rate(1.0, "lower", 0.75, 100) == 2.0
    assert update_two_rate(1.0, "higher", 0.249999, 100) == 0.5
    assert update_two_rate(1.0, "higher", 0.25, 100) == 2.0
    assert update_two_rate(25.0, "higher", 0.9, 100) == 25.0
    with pytest.raises(ValueError):
        update_two_rate(1.0, "bad", 0.5, 100)


def test_small_front_completes_and_accounts_exactly():
    result = run_two_rate_old(17, n=12, offspring=4, max_evaluations=100_000)
    assert result.complete
    assert result.archive_size == 13
    assert all(value is not None for value in result.first_hits)
    assert result.evaluations == 1 + 4 * result.generations
    assert result.effort.objective_evaluations == result.evaluations


def test_seed_determinism():
    first = run_two_rate_old(101, n=20, offspring=10, max_evaluations=200_000)
    second = run_two_rate_old(101, n=20, offspring=10, max_evaluations=200_000)
    assert first.canonical() == second.canonical()


def _write_fixture(path: Path, incomplete: bool = False):
    header = ["pareto", "algorithm", "func", "dimension"]
    for run in range(100):
        header += [f"found{run}", f"First_hit{run}"]
    rows = [header]
    for point in range(101):
        row = [str(point), "TwoRate", "OneMax", "100"]
        for run in range(100):
            found = not (incomplete and run == 2 and point == 100)
            row += ["1" if found else "0", str(1000 + point + run)]
        rows.append(row)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        text = "\n".join(",".join(row) for row in rows) + "\n"
        archive.writestr("csv/om/TwoRateL10P1HVOneMaxD100.csv", text)


def test_parser_recovers_100_full_front_endpoints(tmp_path):
    archive = tmp_path / "fixture.zip"
    _write_fixture(archive)
    report = parse_raw_endpoint(archive)
    assert report.front_rows == 101
    assert report.complete_runs == 100
    assert report.endpoints[0] == 1100
    assert report.endpoints[-1] == 1199


def test_parser_marks_incomplete_run(tmp_path):
    archive = tmp_path / "fixture.zip"
    _write_fixture(archive, incomplete=True)
    report = parse_raw_endpoint(archive)
    assert report.complete_runs == 99
    assert report.endpoints[2] is None


def test_parser_fails_closed_on_bad_header(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("csv/om/TwoRateL10P1HVOneMaxD100.csv", "bad,header\n")
    with pytest.raises(ValueError):
        parse_raw_endpoint(archive)


def test_compatibility_positive_and_negative_controls():
    raw = list(range(1000, 1100))
    close = list(range(1002, 1102))
    far = list(range(2000, 2100))
    assert compare_distributions(raw, close, resamples=4000).overall_pass
    assert not compare_distributions(raw, far, resamples=4000).overall_pass


def test_kolmogorov_and_invalid_statistics():
    assert kolmogorov_distance([1, 2, 3], [1, 2, 3]) == 0.0
    with pytest.raises(ValueError):
        compare_distributions([], [1], resamples=4000)
    with pytest.raises(ValueError):
        compare_distributions([1], [1], resamples=999)


def test_workers_1_2_4_are_identical_on_smoke_ledger():
    seeds = range(901, 907)
    one = run_campaign(seeds, workers=1, n=20, max_evaluations=200_000)
    two = run_campaign(seeds, workers=2, n=20, max_evaluations=200_000)
    four = run_campaign(seeds, workers=4, n=20, max_evaluations=200_000)
    assert campaign_digest(one) == campaign_digest(two) == campaign_digest(four)


def test_campaign_rejects_bad_ledgers_and_workers():
    with pytest.raises(ValueError):
        run_campaign([], workers=1)
    with pytest.raises(ValueError):
        run_campaign([1, 1], workers=1)
    with pytest.raises(ValueError):
        run_campaign([1], workers=3)

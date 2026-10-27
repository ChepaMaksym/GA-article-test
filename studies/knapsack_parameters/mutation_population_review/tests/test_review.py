import copy
import tempfile
import unittest
from pathlib import Path

from .. import authority as a
from ..review import aggregate, family_values, target_query, validate_events, validate_rectangle


def record(task="UC-s020", profile=0, seed=97001):
    return {"task": task, "family": task.split("-")[1], "seed": seed, "profile": profile,
        "verification_status": "VERIFIED", "stage": "main", "start": "bank", "n": 100, "budget": 5000,
        "implementation_sha": a.SOURCE_SHA, "optimum": 100, "initial_best_profit": 80, "final_best_profit": 99,
        "final_gap_percent": 1, "record_events": [{"q": 0, "profit": 80}, {"q": 5000, "profit": 99}],
        "first_targets": {"95": 5000, "99": 5000}, "initial_population_sha256": "a" * 64,
        "initial_rng_sha256": "b" * 64, "first_generation_sha256": "c" * 64, "problem_sha256": "d" * 64,
        "full_generations": 172, "infeasible_fraction": .2, "duplicate_fraction": .1,
        "activity": {"p_m": {"query_weighted_mean": .01}, "target_mu": {"query_weighted_mean": 30}}}


class ReviewTests(unittest.TestCase):
    def test_exact_rectangle_and_mixed_provenance(self):
        rows = [record(profile=p) for p in (0, 1, 4, 5)]
        validate_rectangle(rows, ("UC-s020",), (97001,), (0, 1, 4, 5), a.SOURCE_SHA)
        for damaged in (rows[:-1], rows + [rows[0]], [dict(rows[0], implementation_sha="f" * 40), *rows[1:]],
                        [dict(rows[0], first_generation_sha256="e" * 64), *rows[1:]]):
            with self.assertRaises(ValueError):
                validate_rectangle(damaged, ("UC-s020",), (97001,), (0, 1, 4, 5), a.SOURCE_SHA)

    def test_last_query_start_and_nonattainment(self):
        events = [{"q": 0, "profit": 95}, {"q": 5000, "profit": 99}]
        validate_events(events)
        self.assertEqual(target_query(events, 100, 95), 0)
        self.assertEqual(target_query(events, 100, 99), 5000)
        self.assertIsNone(target_query(events, 100, 100))
        for bad in ([{"q": 1, "profit": 80}], [{"q": 0, "profit": 90}, {"q": 5001, "profit": 99}],
                    [{"q": 0, "profit": 90}, {"q": 2, "profit": 90}],
                    [{"q": 0, "profit": 90}, {"q": 0, "profit": 91}]):
            with self.assertRaises(ValueError):
                validate_events(bad)

    def test_corrupt_record_endpoints_and_targets(self):
        for change in ({"final_gap_percent": 2}, {"final_best_profit": 98}, {"first_targets": {"95": 4999, "99": None}}):
            row = dict(record(), **change)
            with self.assertRaises(ValueError):
                validate_rectangle([row], ("UC-s020",), (97001,), (0,), a.SOURCE_SHA)

    def test_family_weights_do_not_count_candidates_or_extra_tasks_as_independent(self):
        rows = [{"family": "a", "task": "a1", "v": 0}, {"family": "a", "task": "a2", "v": 10},
                {"family": "a", "task": "a2", "v": 10}, {"family": "b", "task": "b1", "v": 20}]
        self.assertEqual(family_values(rows, lambda r: r["v"]), {"a": 5, "b": 20})

    def test_failures_remain_in_denominator(self):
        rows = []
        for p in (0, 1, 4, 5):
            yes = record(profile=p)
            no = record(profile=p, seed=97002)
            no.update(final_best_profit=80, final_gap_percent=20, record_events=[{"q": 0, "profit": 80}],
                      first_targets={"95": None, "99": None})
            rows.extend((yes, no))
        cells = aggregate(rows)
        for cell in cells:
            self.assertEqual(cell["targets"]["99"]["curve"][-1]["fraction"], .5)
            self.assertEqual(cell["targets"]["99"]["not_attained"], 1)
            self.assertEqual(cell["targets"]["99"]["denominator"], 2)

    def test_standalone_figures_have_labels_and_prescribed_scales(self):
        from ..plots import render
        cells = []
        examples = []
        for p in (0, 1, 4, 5):
            cells.append({"profile": p, "mean_final_gap_percent": 2 + p / 5,
                "targets": {str(t): {"attained": 0, "curve": [{"q": 0, "fraction": 0}, {"q": 5000, "fraction": 0}]}
                            for t in (95, 99)}})
            examples.append({"profile": p, "optimum": 100,
                "record_events": [{"q": 0, "profit": 80}, {"q": 5000, "profit": 99}],
                "generations": [{"start_q": 1, "parameters_before": {"p_m": .01, "target_mu": 30}}]})
        with tempfile.TemporaryDirectory() as tmp:
            receipt = render({"status": "COMPLETE_VERIFIED_SECONDARY_REVIEW", "cells": cells}, examples, tmp)
            self.assertEqual(len(receipt["figures"]), 6)
            figures = {f["file"]: f for f in receipt["figures"]}
            self.assertEqual(figures["04_target95.png"]["ylim"], [0, 100])
            self.assertEqual(figures["05_target99.png"]["ylim"], [0, 5])
            for fig in figures.values():
                self.assertTrue(fig["xlabel"] and fig["ylabel"])
                self.assertTrue((Path(tmp) / fig["file"]).exists())


if __name__ == "__main__":
    a.ci_only()
    unittest.main()

"""Small synthetic history controls and a complete synthetic identity rectangle.

These are CI-only tests, not additional scientific search experiments.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .. import speed_analysis as s
from .test_analysis import synthetic_grid


def history_row(points=None, size=30, initial=0, best=None, best_request=None):
    if points is None:
        points = [{"request": 1, "profit": 0}]
    if best is None:
        best = points[-1]["profit"]
    if best_request is None:
        best_request = points[-1]["request"]
    return {"population_size": size, "budget": 5000, "logical_requests": 5000,
            "initial_best_profit": initial, "best_profit": best,
            "best_request": best_request, "record_history": points}


class HistoryTests(unittest.TestCase):
    def test_never_hit_is_none_not_budget(self):
        history = s.validate_history(history_row(), 100)
        self.assertIsNone(s.first_at_least(history, 9900, 100))
        curve = s.weighted_ecdf({("UC-s000", 81001): None})
        self.assertEqual(curve["not_reached"], 1)
        self.assertEqual(curve["family_weighted_reached_fraction"], 0)
        self.assertEqual(curve["points"][-1],
                         {"request": 5000, "fraction": 0.0,
                          "fraction_exact": {"numerator": 0, "denominator": 1}})

    def test_last_query_is_a_real_hit_including_partial_generation(self):
        row = history_row([{"request": 1, "profit": 0}, {"request": 5000, "profit": 99}])
        history = s.validate_history(row, 100)
        self.assertEqual(s.first_at_least(history, 9900, 100), 5000)
        self.assertIsNone(s.first_at_least(history, 10000, 100))
        curve = s.weighted_ecdf({("UC-s000", 81001): 5000, ("UC-s000", 81002): None})
        self.assertEqual(curve["reached"], 1)
        self.assertEqual(curve["not_reached"], 1)
        self.assertEqual(curve["points"][-1]["fraction"], 0.5)

    def test_initial_prefix_is_charged_and_first_hit_preserved(self):
        row = history_row([{"request": 1, "profit": 0}, {"request": 2, "profit": 95},
                           {"request": 5000, "profit": 100}], initial=95)
        history = s.validate_history(row, 100)
        self.assertEqual(s.first_at_least(history, 9500, 100), 2)
        self.assertEqual(s.first_at_least(history, 9900, 100), 5000)
        self.assertEqual(s.first_at_least(history, 0), 1)

    def test_integer_threshold_does_not_round_95_percent_down(self):
        history = [{"request": 1, "profit": 0}, {"request": 20, "profit": 95},
                   {"request": 300, "profit": 96}]
        self.assertEqual(s.first_at_least(history, 95 * 101, 100), 300)
        self.assertIsNone(s.first_at_least(history, 99 * 101, 100))

    def test_malformed_histories_and_self_consistent_tie_rejected(self):
        bad_points = ([], [{"request": 2, "profit": 0}],
                      [{"request": 1, "profit": 1}],
                      [{"request": 1, "profit": 0}, {"request": 2, "profit": 0}],
                      [{"request": 1, "profit": 0}, {"request": 1, "profit": 1}],
                      [{"request": 1, "profit": 0}, {"request": 5001, "profit": 99}],
                      [{"request": 1, "profit": 0}, {"request": 5000, "profit": 101}],
                      [{"request": 1, "profit": 0}, {"request": True, "profit": 99}],
                      [{"request": 1, "profit": 0}, {"request": 2, "profit": 1.0}])
        for points in bad_points:
            with self.subTest(points=points), self.assertRaises(ValueError):
                s.validate_history(history_row(points) if points else history_row(points, best=0, best_request=1), 100)
        for patch_fields in ({"best_profit": 1}, {"best_request": 2}, {"initial_best_profit": 1},
                             {"budget": 4999}, {"logical_requests": 4999}):
            with self.subTest(patch_fields=patch_fields), self.assertRaises(ValueError):
                s.validate_history(dict(history_row(), **patch_fields), 100)

    def test_initial_prefix_mismatch_rejected(self):
        row = history_row([{"request": 1, "profit": 0}, {"request": 29, "profit": 10},
                           {"request": 31, "profit": 20}], initial=0)
        with self.assertRaisesRegex(ValueError, "initial-prefix"):
            s.validate_history(row, 100)

    def test_equal_family_weight_not_pooled_run_fraction(self):
        times = {("UC-s000", 1): 3, ("WC-s000", 1): 3, ("SC-s000", 1): 3,
                 ("UC-s001", 1): None}
        curve = s.weighted_ecdf(times)
        self.assertEqual(curve["reached"], 3)
        self.assertEqual(curve["family_weighted_reached_fraction"], 0.5)
        value, families = s.hierarchical_mean({pair: int(time is not None) for pair, time in times.items()})
        self.assertEqual(value, Fraction(1, 2))
        self.assertEqual(families, {"s000": 1, "s001": 0})


class FullRectangleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.instances, cls.optima = synthetic_grid()
        for row in cls.rows:
            row["record_history"] = [{"request": 1, "profit": 0}]
        cls.report = s.analyze(cls.rows, cls.instances, cls.optima)

    def changed(self, index=0):
        rows = self.rows[:]
        rows[index] = copy.deepcopy(rows[index])
        return rows, rows[index]

    def test_all_targets_and_same_results_without_fabricated_attainment(self):
        report = self.report
        self.assertEqual(report["runs"], 37500)
        self.assertEqual(len(report["configurations"]), 125)
        self.assertEqual(len(report["run_targets"]), 37500)
        self.assertEqual([panel["varying_parameter"] for panel in report["conditional_panels"]], list(s.AXES))
        self.assertEqual(report["example"]["same_final_value_groups"][0]["profit"], 0)
        self.assertEqual(len(report["example"]["same_final_value_groups"][0]["configurations"]), 125)
        for config in report["configurations"]:
            self.assertEqual(config["paired_results"]["equal"]["count"], 300)
            self.assertEqual(config["paired_results"]["equal"]["fraction"], 1)
            self.assertEqual(config["targets"]["99"]["not_reached"], 300)
            self.assertEqual(config["baseline_final_target"]["reached"], 300)
        self.assertTrue(all(run["target_times"] == {"95": None, "99": None, "100": None}
                            for run in report["run_targets"]))
        self.assertTrue(all(run["first_at_least_baseline_final"] == 1 for run in report["run_targets"]))
        self.assertFalse(report["statistical_equivalence_tested"])
        self.assertFalse(report["superiority_tested"])
        self.assertFalse(report["holdout_statistics_performed"])
        json.dumps(report, allow_nan=False)

    def test_missing_duplicate_holdout_mixed_and_unverified_rejected(self):
        with self.assertRaises(ValueError):
            s.analyze(self.rows[:-1], self.instances, self.optima)
        rows = self.rows[:]
        rows[-1] = rows[0]
        with self.assertRaises(ValueError):
            s.analyze(rows, self.instances, self.optima)
        for field, value in (("phase", "pilot"), ("instance_id", "UC-s010"),
                             ("repeat_seed", 82001), ("verified", False),
                             ("implementation_commit_sha", "ef" * 20),
                             ("source_manifest_sha256", "ef" * 32)):
            rows, row = self.changed()
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                s.analyze(rows, self.instances, self.optima)

    def test_same_initial_record_but_different_initial_history_rejected(self):
        rows, row = self.changed()
        row.update(record_history=[{"request": 1, "profit": 0}, {"request": 5, "profit": 1}],
                   best_profit=1, best_request=5, initial_best_profit=1)
        with self.assertRaisesRegex(ValueError, "shared initial bank history"):
            s.analyze(rows, self.instances, self.optima)

    def test_nested_prefix_checks_population_boundary_not_last_record_request(self):
        rows = self.rows[:]
        for index, original in enumerate(rows):
            if original["instance_id"] == "UC-s000" and original["repeat_seed"] == 81001 and original["population_size"] == 20:
                row = copy.deepcopy(original)
                row.update(record_history=[{"request": 1, "profit": 0}, {"request": 8, "profit": 1}],
                           best_profit=1, best_request=8, initial_best_profit=1)
                rows[index] = row
        with self.assertRaisesRegex(ValueError, "nested initial histories"):
            s.analyze(rows, self.instances, self.optima)

    def test_paired_comparison_and_baseline_target_use_same_task_seed(self):
        rows = self.rows[:]
        baseline = s.configuration_id(*s.BASELINE)
        higher = s.configuration_id(Fraction(3, 100), Fraction(9, 10), 30)
        lower = s.configuration_id(Fraction(1, 200), Fraction(9, 10), 30)
        for index, original in enumerate(rows):
            if (original["instance_id"], original["repeat_seed"]) != ("UC-s000", 81001):
                continue
            profit = 10 if original["configuration_id"] == baseline else 11 if original["configuration_id"] == higher else 0
            if not profit:
                continue
            row = copy.deepcopy(original)
            row.update(best_profit=profit, best_request=100,
                       record_history=[{"request": 1, "profit": 0}, {"request": 100, "profit": profit}])
            rows[index] = row
        report = s.analyze(rows, self.instances, self.optima)
        configs = {row["configuration_id"]: row for row in report["configurations"]}
        self.assertEqual(configs[baseline]["paired_results"]["equal"]["count"], 300)
        self.assertEqual(configs[higher]["paired_results"]["higher"]["count"], 1)
        self.assertEqual(configs[lower]["paired_results"]["lower"]["count"], 1)
        self.assertEqual(configs[higher]["paired_results"]["higher"]["fraction_exact"],
                         {"numerator": 1, "denominator": 300})
        selected = {row["configuration_id"]: row for row in report["run_targets"]
                    if (row["instance_id"], row["repeat_seed"]) == ("UC-s000", 81001)}
        self.assertEqual(selected[higher]["first_at_least_baseline_final"], 100)
        self.assertIsNone(selected[lower]["first_at_least_baseline_final"])
        self.assertEqual([row["profit"] for row in report["example"]["same_final_value_groups"]], [0, 10, 11])

    def test_ci_only_guards_analysis_and_writing(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(ValueError, "CI-only"):
                s.analyze(self.rows, self.instances, self.optima)
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaisesRegex(ValueError, "CI-only"):
                    s.write_report(self.report, folder)

    def test_report_figures_and_answers_are_produced_in_ci(self):
        with tempfile.TemporaryDirectory() as folder:
            receipt = s.write_report(self.report, folder)
            self.assertEqual(len(receipt["figures"]), 5)
            for name in receipt["figures"]:
                self.assertGreater((Path(folder) / name).stat().st_size, 1000)
            saved = json.loads((Path(folder) / "speed_analysis.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["runs"], 37500)
            text = (Path(folder) / "PARAMETERS_RESULTS_UK.md").read_text(encoding="utf-8")
            self.assertIn("99%", text)
            self.assertIn("невідомі", text)
            self.assertIn("5000", text)


if __name__ == "__main__":
    unittest.main()

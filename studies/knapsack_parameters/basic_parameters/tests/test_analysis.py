"""Synthetic development-grid fixtures; no search, DP, bootstrap or holdout runs."""
from __future__ import annotations

import copy
from fractions import Fraction
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .. import analysis as a


def rational(value):
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def synthetic_grid():
    """A complete identity rectangle, not purported seed-replayed GA evidence."""
    instances = {task: {"n": 100, "weights": [1] * 100, "profits": [1] * 100, "capacity": 100}
                 for task in a.TASKS}
    optima = {task: 100 for task in a.TASKS}
    rows = []
    for task in a.TASKS:
        kind, family = task.split("-")
        for seed in a.SEEDS:
            for p_m in a.MUTATIONS:
                for p_c in a.CROSSOVERS:
                    for size in a.POPULATIONS:
                        verdict = {"status": "PASS_REPLAY", "rng_and_operator_replay_verified": True,
                            "exact_requests_verified": 5000, "best_mask": "0" * 100,
                            "best_weight": 0, "best_profit": 0, "best_request": 1,
                            "logical_requests": 5000, "physical_evaluations": 5000 - size}
                        rows.append({"protocol_id": a.PROTOCOL, "phase": "main", "instance_id": task,
                            "class_label": kind, "family": family, "index": int(family[1:]),
                            "repeat_seed": seed, "seed": seed,
                            "configuration_id": a.configuration_id(p_m, p_c, size),
                            "mutation_numerator": float(100 * p_m), "crossover_probability": float(p_c),
                            "population_size": size, "p_m": float(p_m), "p_c": float(p_c), "N": size, "n": 100,
                            "best_mask": "0" * 100, "best_profit": 0, "best_weight": 0, "best_request": 1,
                            "budget": 5000, "logical_requests": 5000, "physical_evaluations": 5000 - size,
                            "known_initial_requests": size,
                            "complete_generations": (5000 - size) // (size - 1),
                            "terminal_partial": bool((5000 - size) % (size - 1)),
                            "duplicate_count": 0, "invalid_request_count": 0,
                            "initial_best_profit": 0, "exact_optimum": 100, "relative_gap": 1.0,
                            "verified": True, "verification_status": "PASS_REPLAY", "verification": verdict,
                            "implementation_commit_sha": "ab" * 20, "source_manifest_sha256": "cd" * 32})
    return rows, instances, optima


def ranking_row(name, mean=0, worst=0, size=30, p_m=Fraction(1, 100), p_c=Fraction(9, 10)):
    return {"configuration_id": name, "mean_gap_exact": rational(mean), "worst_family_gap_exact": rational(worst),
            "population_size": size, "p_m_exact": rational(p_m), "p_c_exact": rational(p_c)}


def teaching_trace(report, config_id):
    config = next(row for row in report["configurations"] if row["configuration_id"] == config_id)
    size = config["population_size"]
    requests = [size] + list(range(2 * size - 1, 5001, size - 1))
    if requests[-1] != 5000:
        requests.append(5000)
    points = [{"request": request, "generation": index,
               "complete": index == 0 or request - requests[index - 1] == size - 1,
               "record_profit": 0, "mean_feasible_profit": 0.0,
               "unique_fraction": 1 / size, "feasible_fraction": 1.0}
              for index, request in enumerate(requests)]
    return {"instance_id": "UC-s000", "repeat_seed": 81001, "configuration_id": config_id,
            "p_m": config["p_m"], "p_c": config["p_c"], "N": size, "points": points}


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.instances, cls.optima = synthetic_grid()
        cls.report = a.aggregate(cls.rows, cls.instances, cls.optima)

    def changed_row(self, index=0):
        rows = self.rows[:]
        rows[index] = copy.deepcopy(rows[index])
        return rows, rows[index]

    def test_complete_rectangle_accounting_and_constant_grid_choice(self):
        report = self.report
        self.assertEqual(report["runs"], 37500)
        self.assertEqual(report["configuration_count"], 125)
        self.assertEqual(report["logical_requests"], 187500000)
        self.assertEqual(report["physical_search_evaluations"], 185925000)
        self.assertEqual(report["independent_best_witness_checks"], 37500)
        self.assertEqual(report["winner_id"], "m0-c0-n10")
        self.assertEqual(report["winner"]["mean_gap_exact"], rational(1))
        self.assertEqual(len(report["conditional_effects"]), 75)
        self.assertTrue(all(curve["spearman"]["status"] == "UNDEFINED" for curve in report["conditional_effects"]))
        self.assertEqual(report["bootstrap_resamples"], 0)
        self.assertFalse(report["holdout_statistics_performed"])
        self.assertFalse(report["superiority_tested"])
        json.dumps(report, allow_nan=False)

    def test_exact_rational_comparison_precedes_population_tie_break(self):
        almost_one = Fraction(10 ** 30, 10 ** 30 + 1)
        self.assertEqual(float(almost_one), float(Fraction(1)))
        rows = [ranking_row("larger-exact-mean", 1, 1, 10),
                ranking_row("smaller-exact-mean", almost_one, 1, 100)]
        self.assertEqual(a.rank_configurations(rows)[0]["configuration_id"], "smaller-exact-mean")

    def test_registered_worst_family_population_and_numeric_tuple_ties(self):
        rows = [ranking_row("worst", Fraction(1, 3), Fraction(1, 2), 10),
                ranking_row("best-worst", Fraction(1, 3), Fraction(2, 5), 100)]
        self.assertEqual(a.rank_configurations(rows)[0]["configuration_id"], "best-worst")
        rows = [ranking_row("larger-pop", 0, 0, 30, 0, 0), ranking_row("smaller-pop", 0, 0, 10, 1, 1)]
        self.assertEqual(a.rank_configurations(rows)[0]["configuration_id"], "smaller-pop")
        rows = [ranking_row("pc-high", 0, 0, 30, Fraction(1, 200), 1),
                ranking_row("pm-high", 0, 0, 30, Fraction(1, 100), 0),
                ranking_row("numeric-first", 0, 0, 30, Fraction(1, 200), Fraction(1, 4))]
        self.assertEqual(a.rank_configurations(rows)[0]["configuration_id"], "numeric-first")

    def test_seed_task_class_family_means_are_exact(self):
        rows = self.rows[:]
        baseline = a.configuration_id(*a.BASELINE)
        for index, original in enumerate(rows):
            if original["instance_id"] == "UC-s000" and original["configuration_id"] == baseline:
                changed = copy.deepcopy(original)
                changed.update(best_mask="1" + "0" * 99, best_profit=1, best_weight=1,
                               best_request=31, relative_gap=0.99)
                changed["verification"].update(best_mask=changed["best_mask"], best_profit=1,
                                                best_weight=1, best_request=31)
                rows[index] = changed
        report = a.aggregate(rows, self.instances, self.optima)
        self.assertEqual(report["winner_id"], baseline)
        self.assertEqual(report["winner"]["mean_gap_exact"], rational(Fraction(2999, 3000)))
        self.assertEqual(report["winner"]["worst_family_gap_exact"], rational(1))
        family = next(row for row in report["winner"]["family_gaps"] if row["family"] == "s000")
        self.assertEqual(family["mean_gap_exact"], rational(Fraction(299, 300)))

    def test_missing_duplicate_or_holdout_identity_rejected(self):
        with self.assertRaises(ValueError):
            a.aggregate(self.rows[:-1], self.instances, self.optima)
        rows = self.rows[:]
        rows[-1] = rows[0]
        with self.assertRaises(ValueError):
            a.aggregate(rows, self.instances, self.optima)
        for field, value in (("instance_id", "UC-s010"), ("repeat_seed", 82001),
                             ("seed", 81002), ("phase", "pilot")):
            with self.subTest(field=field):
                rows, row = self.changed_row()
                row[field] = value
                with self.assertRaises(ValueError):
                    a.aggregate(rows, self.instances, self.optima)

    def test_independent_witness_mask_weight_profit_and_feasibility(self):
        for field, value in (("best_mask", "0" * 99), ("best_mask", "x" * 100),
                             ("best_weight", 1), ("best_profit", 1)):
            with self.subTest(field=field, value=value):
                rows, row = self.changed_row()
                row[field] = value
                with self.assertRaises(ValueError):
                    a.aggregate(rows, self.instances, self.optima)
        rows, row = self.changed_row()
        instances = copy.deepcopy(self.instances)
        instances["UC-s000"]["weights"] = [2] * 100
        row.update(best_mask="1" * 100, best_weight=200, best_profit=100, best_request=11, relative_gap=0.0)
        row["verification"].update(best_mask=row["best_mask"], best_weight=200, best_profit=100, best_request=11)
        with self.assertRaises(ValueError):
            a.aggregate(rows, instances, self.optima)

    def test_unverified_mixed_sources_and_incorrect_accounting_rejected(self):
        mutations = (("verified", False), ("verification_status", "UNKNOWN"),
                     ("implementation_commit_sha", "ef" * 20), ("source_manifest_sha256", "ef" * 32),
                     ("logical_requests", 4999), ("physical_evaluations", 5000),
                     ("known_initial_requests", 30), ("complete_generations", 0),
                     ("terminal_partial", False), ("relative_gap", 0.0),
                     ("mutation_numerator", 0.5), ("protocol_id", "OTHER"))
        for field, value in mutations:
            with self.subTest(field=field):
                rows, row = self.changed_row()
                row[field] = value
                with self.assertRaises(ValueError):
                    a.aggregate(rows, self.instances, self.optima)

    def test_forged_replay_oracle_disagreement_rejected(self):
        rows, row = self.changed_row()
        row["verification"]["best_profit"] = 1
        with self.assertRaises(ValueError):
            a.aggregate(rows, self.instances, self.optima)
        rows, row = self.changed_row()
        row["verification"]["rng_and_operator_replay_verified"] = False
        with self.assertRaises(ValueError):
            a.aggregate(rows, self.instances, self.optima)

    def test_initial_bank_mismatch_and_population_prefix_quality_rejected(self):
        rows, row = self.changed_row()
        row["initial_best_profit"] = 1
        with self.assertRaises(ValueError):
            a.aggregate(rows, self.instances, self.optima)
        # A self-consistent best record cannot repair conflicting initial banks
        # between the other parameter combinations sharing task/seed/population.
        index = next(i for i, row in enumerate(self.rows) if row["configuration_id"] == self.report["baseline_id"])
        rows, row = self.changed_row(index)
        row.update(initial_best_profit=1, best_mask="1" + "0" * 99, best_profit=1,
                   best_weight=1, best_request=1, relative_gap=0.99)
        row["verification"].update(best_mask=row["best_mask"], best_profit=1, best_weight=1, best_request=1)
        with self.assertRaises(ValueError):
            a.aggregate(rows, self.instances, self.optima)

    def test_average_tie_ranks_and_constant_spearman(self):
        self.assertEqual(a.average_ranks([3, 1, 1, 9]), [Fraction(3), Fraction(3, 2), Fraction(3, 2), Fraction(4)])
        self.assertEqual(a.descriptive_spearman([1, 2, 3], [3, 2, 1])["rho"], -1)
        self.assertEqual(a.descriptive_spearman([1, 1, 2], [4, 4, 5])["rho"], 1)
        for x, y in (([1, 1], [1, 2]), ([1, 2], [5, 5])):
            result = a.descriptive_spearman(x, y)
            self.assertEqual(result["status"], "UNDEFINED")
            self.assertIsNone(result["rho"])
        with self.assertRaises(ValueError):
            a.descriptive_spearman([1], [1])

    def test_conditional_effects_hold_two_parameters_and_anchor_fixed(self):
        baseline_values = {"p_m": 0.01, "p_c": 0.9, "population_size": 30}
        for curve in self.report["conditional_effects"]:
            self.assertEqual(len(curve["fixed_parameters"]), 2)
            self.assertEqual(len(curve["points"]), 5)
            parameter = curve["varying_parameter"]
            anchor = next(point for point in curve["points"] if point["level"] == baseline_values[parameter])
            self.assertEqual(anchor["gap_difference_from_reference_exact"], rational(0))
            self.assertEqual(curve["spearman"]["n"], 5)

    def test_no_holdout_instance_reference_or_invalid_optimum_accepted(self):
        instances = dict(self.instances)
        instances["UC-s010"] = instances.pop("UC-s000")
        with self.assertRaises(ValueError):
            a.aggregate(self.rows, instances, self.optima)
        optima = dict(self.optima)
        optima["UC-s000"] = 0
        with self.assertRaises(ValueError):
            a.aggregate(self.rows, self.instances, optima)

    def test_report_figures_and_archived_example_without_search(self):
        report = copy.deepcopy(self.report)
        report["example_trajectories"] = [teaching_trace(report, report["baseline_id"]),
                                           teaching_trace(report, report["winner_id"])]
        with tempfile.TemporaryDirectory() as tmp:
            receipt = a.write_report(report, tmp)
            root = Path(tmp)
            self.assertEqual(len([name for name in receipt["figures"] if name.startswith("heatmap-")]), 5)
            self.assertEqual(len(receipt["figures"]), 8)
            self.assertTrue(all((root / name).is_file() for name in receipt["figures"]))
            saved = json.loads((root / "analysis.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["example_trace_status"], "ARCHIVED_TRACES_PROVIDED")
            self.assertFalse(saved["holdout_statistics_performed"])
            self.assertNotIn("example_trajectories", saved)

    def test_missing_example_is_not_synthesized(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = a.write_report(self.report, tmp)
            self.assertEqual(receipt["example_trace_status"], "NOT_PROVIDED")
            self.assertNotIn("example-UC-s000-81001.png", receipt["figures"])
            self.assertIn("не надано", (Path(tmp) / "RESULTS_UK.md").read_text(encoding="utf-8"))

    def test_corrupted_archived_example_checkpoint_rejected(self):
        report = copy.deepcopy(self.report)
        baseline = teaching_trace(report, report["baseline_id"])
        winner = teaching_trace(report, report["winner_id"])
        baseline["points"][-1]["unique_fraction"] = 0
        report["example_trajectories"] = [baseline, winner]
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            a.write_report(report, tmp)

    def test_ci_identity_guard(self):
        for field, value in (("GITHUB_ACTIONS", "false"), ("GITHUB_REPOSITORY", "other/repository"),
                             ("GITHUB_REF", "refs/heads/main")):
            with patch.dict(os.environ, {field: value}), self.assertRaises(ValueError):
                a.aggregate(self.rows, self.instances, self.optima)


if __name__ == "__main__":
    unittest.main()

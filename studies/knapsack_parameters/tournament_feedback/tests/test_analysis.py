"""CI-only hand fixtures for weighting, attainment and primary inference."""
from __future__ import annotations

import copy
import os
import unittest

from studies.knapsack_parameters.tournament_feedback import analysis


def compact_fixture(task, start, profile, gap_percent, *, source="1" * 40):
    """Hand-built aggregate input, not an empirical or raw-search result."""
    final = 10000 - 100 * gap_percent
    k = int(profile[1:]) if profile.startswith("k") else 2
    return {"schema": analysis.SCHEMA, "verification_status": "VERIFIED", "role": "recipient",
            "task": task, "family": task[3:], "class_label": task[:2], "start": start,
            "seed": 109999, "profile": profile, "stage": "pilot", "implementation_sha": source,
            "budget": 5000, "n": 100, "optimum": 10000, "capacity": 100,
            "problem_sha256": analysis.digest(task), "journal_sha256": analysis.digest((task, start, profile)),
            "initial_population_sha256": analysis.digest((task, start)),
            "initial_rng_sha256": analysis.digest((task, start, 109999)),
            "first_generation_sha256": analysis.digest((task, start, 2 if profile in ("k2", "adaptive", "replay") else k)),
            "initial_best_profit": 1000, "final_best_profit": final,
            "final_best_mask": "0" * 100, "final_best_weight": 50,
            "final_gap_percent": gap_percent, "final_capacity_fraction": .5,
            "record_events": [{"q": 0, "profit": 1000}, {"q": 5000, "profit": final}],
            "first_targets": {str(target): 5000 if 100 * final >= target * 10000 else None for target in (95, 99)},
            "activity": {"tournament_size": {"increases": 0, "decreases": 0, "opportunities": 0,
                         "unchanged_opportunities": 0, "boundary_opportunities": 0, "changed": False,
                         "query_weighted_mean": k, "query_occupancy": [{"value": k, "new_calls": 5000}]}},
            "operator_bins": [{"distance_bin": label, "total": 5000 if index == 0 else 0,
                              "crossed": 4000 if index == 0 else 0, "novel_crossed": 0,
                              "feasible_crossed": 4000 if index == 0 else 0, "better_both_crossed": 0}
                              for index, label in enumerate(analysis.DISTANCE_LABELS)],
            "infeasible_fraction": .2, "duplicate_fraction": .1,
            "full_generations": 172, "partial_children": 12,
            "kernel_timing_ns": {"total": 100, "controller": 10},
            "timings": {"search_wall_ns": 100, "serialization_ns": 30, "verification_ns": None}}


def pilot_rectangle():
    gaps = {"k2": 10, "k3": 8, "k4": 6, "k5": 5, "adaptive": 7, "replay": 9}
    rows = []
    for task in analysis.PILOT_TASKS:
        for start in ("cloned", "bank"):
            for profile in analysis.PROFILES:
                row = compact_fixture(task, start, profile, gaps[profile])
                if task == "UC-s000" and start == "bank":
                    row["example_trace"] = {"population": [], "generations": []}
                rows.append(row)
    return rows


class TournamentFeedbackAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("These instructional checks may execute only in GitHub Actions")

    def test_gap_uses_percent_and_rejects_invalid_oracle(self):
        self.assertEqual(analysis.gap(1000, 950), 5)
        self.assertEqual(analysis.gap(1000, 1000), 0)
        for optimum, profit in ((0, 0), (1000, 1001), (1000, -1), (1000, True), (1000.0, 900)):
            with self.assertRaises(ValueError):
                analysis.gap(optimum, profit)

    def test_weighting_means_repeats_then_tasks_then_families(self):
        # A has two tasks: task1's mean is2; task2's mean is10 => A=6.
        # B has one task with mean20 => final(6+20)/2=13.
        # Pooling the four raw observations gives8.5, an incorrect weight.
        rows = [{"family": "A", "task": "A1", "value": value} for value in (0, 4)]
        rows += [{"family": "A", "task": "A2", "value": 10}, {"family": "B", "task": "B1", "value": 20}]
        self.assertEqual(analysis.mean_by_family(rows, lambda row: row["value"]), {"A": 6, "B": 20})
        self.assertEqual(analysis.weighted_mean(rows, lambda row: row["value"]), 13)
        self.assertNotEqual(analysis.weighted_mean(rows, lambda row: row["value"]), 8.5)

    def test_attainment_includes_initial_hit_last_query_and_nonhit(self):
        rows = [{"family": "A", "task": "A1", "first_targets": {"95": value}} for value in (0, None)]
        rows += [{"family": "A", "task": "A2", "first_targets": {"95": 5000}},
                 {"family": "B", "task": "B1", "first_targets": {"95": None}}]
        value = analysis.target_summary(rows, 95)
        self.assertEqual(value["attained"], 2)
        self.assertEqual(value["not_attained"], 2)
        self.assertEqual(value["curve"], [{"q": 0, "fraction": .125}, {"q": 5000, "fraction": .375}])
        self.assertEqual(value["restricted_mean_queries"], 4375)

    def test_all_nonhits_are_not_an_empty_success_only_analysis(self):
        rows = [{"family": "A", "task": "A1", "first_targets": {"99": None}}]
        value = analysis.target_summary(rows, 99)
        self.assertEqual(value["curve"], [{"q": 0, "fraction": 0}, {"q": 5000, "fraction": 0}])
        self.assertEqual(value["restricted_mean_queries"], 5000)
        self.assertEqual((value["attained"], value["not_attained"]), (0, 1))

    def test_activity_weights_applied_values_not_next_request(self):
        generations = [
            {"start_q": 1, "q": 29, "complete": True, "parameters_before": {"tournament_size": 2},
             "parameters_after": {"tournament_size": 5}, "controller_event": "SUCCESS"},
            {"start_q": 30, "q": 41, "complete": False, "parameters_before": {"tournament_size": 5},
             "parameters_after": {"tournament_size": 5}, "controller_event": "PARTIAL_NO_UPDATE"}]
        activity, windows = analysis.tournament_activity(generations, 41, "adaptive")
        self.assertEqual(activity["query_occupancy"], [{"value": 2, "new_calls": 29}, {"value": 5, "new_calls": 12}])
        self.assertEqual(activity["query_weighted_mean"], 118 / 41)
        self.assertEqual(windows[0]["mean_applied_tournament"], 118 / 41)
        self.assertEqual(activity["increases"], 1)
        self.assertEqual(activity["opportunities"], 1)

    def test_family_contrast_direction_from_hand_values(self):
        rows = []
        for family in ("A", "B"):
            for profile, value in zip(analysis.PROFILES, (10, 8, 6, 5, 7, 9), strict=True):
                rows.append({"family": family, "task": family + "1", "profile": profile, "final_gap_percent": value})
        effects = analysis.family_effect_vectors(rows)
        self.assertEqual(effects, [{"family": family, "effects": {"k2": 3, "k3": 1, "k4": -1, "k5": -2, "replay": 2}}
                                  for family in ("A", "B")])

    def test_pilot_aggregation_keeps_all_controls_without_inference(self):
        result = analysis.aggregate(pilot_rectangle(), scope="pilot", expected_sha="1" * 40)
        self.assertEqual(result["runs"], 48)
        self.assertEqual(result["new_search_evaluations"], 240000)
        self.assertEqual(result["primary_analysis"]["status"], "NOT_PERFORMED_TECHNICAL_PILOT")
        self.assertEqual(result["primary_analysis"]["replicates"], 0)
        self.assertEqual(result["primary_analysis"]["intervals"], [])
        bank = {row["profile"]: row for row in result["profile_cells"] if row["start"] == "bank"}
        self.assertEqual(bank["adaptive"]["mean_final_gap_percent"], 7)
        self.assertEqual(bank["k5"]["targets"]["95"]["attained"], 4)
        self.assertEqual(bank["k2"]["targets"]["95"]["not_attained"], 4)
        self.assertEqual(len(result["prespecified_examples"]), 6)

    def test_rectangle_rejects_missing_duplicate_mixed_sha_and_donor(self):
        rows = pilot_rectangle()
        cases = [rows[:-1], rows + [copy.deepcopy(rows[0])]]
        for field, value in (("implementation_sha", "2" * 40), ("role", "donor"),
                             ("verification_status", "UNVERIFIED"), ("final_gap_percent", 99),
                             ("initial_population_sha256", "f" * 64), ("first_generation_sha256", "e" * 64)):
            damaged = copy.deepcopy(rows)
            damaged[0][field] = value
            cases.append(damaged)
        for index, damaged in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(ValueError):
                    analysis.validate_rows(damaged, "pilot", "1" * 40)

    def test_larger_static_first_generation_need_not_equal_k2(self):
        rows = pilot_rectangle()
        for row in rows:
            if row["profile"] in ("k3", "k4", "k5"):
                row["first_generation_sha256"] = analysis.digest((row["task"], row["start"], row["profile"], "different"))
        analysis.validate_rows(rows, "pilot", "1" * 40)

    def test_bca_has_five_99percent_intervals_and_deterministic_indices(self):
        values = [[index + .1 * column for column in range(5)] for index in range(1, 11)]
        first = analysis.family_bca(values, replicates=2000)
        second = analysis.family_bca(values, replicates=2000)
        self.assertEqual(first, second)
        self.assertEqual(first["confidence_each"], .99)
        self.assertEqual(first["seed"], 112001)
        self.assertEqual(first["family_count"], 10)
        self.assertEqual([item["control"] for item in first["intervals"]], list(analysis.PRIMARY_CONTROLS))
        self.assertTrue(first["advantage_over_all_five_supported"])
        self.assertTrue(all(item["lower"] > 0 and item["upper"] > item["lower"] for item in first["intervals"]))

    def test_degenerate_bca_is_descriptive_even_for_positive_point_effect(self):
        result = analysis.family_bca([[3, -2, 0, 1, 5]] * 10, replicates=100)
        self.assertFalse(result["advantage_over_all_five_supported"])
        for item, estimate in zip(result["intervals"], (3, -2, 0, 1, 5), strict=True):
            self.assertEqual(item["estimate_gap_points"], estimate)
            self.assertEqual(item["status"], "DESCRIPTIVE_ONLY")
            self.assertIsNone(item["lower"])
            self.assertIsNone(item["upper"])
            self.assertFalse(item["positive_effect_supported"])

    def test_bootstrap_rejects_wrong_contrast_count_and_nonfinite_values(self):
        for values in ([[1] * 6] * 10, [[1] * 5] * 4, [[float("nan")] * 5] * 10):
            with self.assertRaises(ValueError):
                analysis.family_bca(values, replicates=100)


if __name__ == "__main__":
    unittest.main()

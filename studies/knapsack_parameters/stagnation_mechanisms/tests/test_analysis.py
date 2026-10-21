"""Fixtures only; execution is restricted to the registered CI workflow."""
from copy import deepcopy
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from .. import analysis as a
from ..mathematics import detection_probability, mutation_probability


def operator_group(count):
    applied = int(.9 * count)
    return {
        "candidate_count": count, "crossover_applied_count": applied,
        "crossover_skipped_count": count - applied,
        "premutation_better_count": 6, "final_record_count": 5,
        "mutation_created_count": 3, "mutation_preserved_count": 2,
        "mutation_lost_count": 4, "mutation_neither_count": count - 9,
        "premutation_feasible_count": count - 10, "final_feasible_count": count - 11,
        "zero_mutation_count": count // 3, "duplicate_count": count // 2,
        "record_present_in_population_count": count - 5,
        "record_selected_candidate_count": count // 5,
        "record_selected_parent_slots": count // 3,
        "record_pending_count": 3, "record_absent_from_population_and_pending_count": 2,
        "crossover_actual_change_from_first_parent_count": applied - 10,
        "crossover_novel_to_both_parents_count": applied - 20,
        "feasibility_transitions": {"infeasible_to_infeasible": 1,
                                    "infeasible_to_feasible": 9,
                                    "feasible_to_infeasible": 10,
                                    "feasible_to_feasible": count - 20},
        "crossover_conditioned": {"candidate_count": applied,
            "feasible_parent_baseline_count": applied - 7, "undefined_parent_baseline_count": 7,
            "premutation_better_than_parent_count": 10, "final_better_than_parent_count": 7},
    }


def feature_row(instance="UC-s000", seed=93001, *, b1=0, b2=2, stagnant=True):
    checkpoints = []
    better = b1 + b2
    for q in a.CHECKPOINTS:
        age = q if q != 5000 or stagnant else 100
        checkpoints.append({
            "q": q, "stagnation_age": age, "stagnant": age >= 1000,
            "state": "N2_NOT_LOCAL" if better else "N2_STRICT_NONGLOBAL",
            "b1": b1, "b2": b2, "total_better": better, "slack": 3,
            "min_positive_gain": 1 if better else None,
            "max_positive_gain": 1 if better else None,
            "sum_positive_gain": better,
            "improvement_types": {"add_one": b1, "remove_one": 0,
                                  "swap_one": b2, "add_two": 0, "remove_two": 0},
            "model_probabilities": [{"p": p, "probability": mutation_probability(100, b1, b2, p)}
                                    for p in a.PM_GRID],
            "detection_probabilities": [{"sample_size": sample,
                                         "probability": detection_probability(5050, better, sample)}
                                        for sample in a.SAMPLE_BUDGETS],
        })
    return {"instance_id": instance, "repeat_seed": seed, "family": instance[3:],
            "status": "PASS", "verified": True, "source_identity": {"run_id": 39465647096, "head_sha": "a" * 40},
            "checkpoints": checkpoints,
            "operators": {"groups": {"all_new": operator_group(5000), "late_1000": operator_group(1000)},
                          "checkpoints": [{"q": q, "record_mask_present_in_population": True,
                                           "record_mask_copy_count": 2} for q in a.CHECKPOINTS]}}


def summarize(rows):
    return a.summarize_features(rows, expected_identities={(row["instance_id"], row["repeat_seed"]) for row in rows})


class RankTests(unittest.TestCase):
    def test_average_ranks_keep_ties_and_original_order(self):
        self.assertEqual(a.average_ranks([4, 1, 1, 2]), [4.0, 1.5, 1.5, 3.0])
        self.assertEqual(a.average_ranks([]), [])

    def test_spearman_perfect_positive_negative_and_ties(self):
        self.assertEqual(a.spearman([3, 1, 2], [6, 2, 4])["rho"], 1)
        self.assertEqual(a.spearman([3, 1, 2], [2, 6, 4])["rho"], -1)
        self.assertAlmostEqual(a.spearman([1, 1, 2, 3], [2, 2, 1, 4])["rho"], 1 / 3)

    def test_constant_and_empty_are_undefined_not_zero(self):
        for x, y in (([], []), ([1], [2]), ([1, 1], [1, 2]), ([1, 2], [3, 3])):
            result = a.spearman(x, y)
            self.assertEqual(result["status"], "UNDEFINED")
            self.assertIsNone(result["rho"])
            self.assertNotIn("p_value", result)

    def test_invalid_ranks_and_mismatched_series_rejected(self):
        for values in ([True, 1], [float("nan"), 1], [float("inf"), 1], ["1", 1]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                a.average_ranks(values)
        with self.assertRaises(ValueError):
            a.spearman([1, 2], [1])


class SecondaryAnalysisTests(unittest.TestCase):
    def test_input_not_changed_and_no_new_search(self):
        rows = [feature_row()]
        before = deepcopy(rows)
        result = summarize(rows)
        self.assertEqual(rows, before)
        self.assertEqual(result["new_search_evaluations"], 0)
        self.assertEqual(result["new_exact_solves"], 0)
        self.assertFalse(result["bootstrap"])
        self.assertFalse(result["hypothesis_tests"])

    def test_zero_better_retained_in_all_stagnant_and_gains_undefined(self):
        rows = [feature_row(b2=0), feature_row(seed=93002, b2=2)]
        result = summarize(rows)
        all_stagnant = result["availability"]["all_stagnant"]
        conditional = result["availability"]["stagnant_with_improvement"]
        self.assertEqual(all_stagnant["b2"]["value"], 1)
        self.assertEqual(conditional["b2"]["value"], 2)
        self.assertEqual(all_stagnant["b2"]["absolute_selected_runs"], 2)
        self.assertEqual(conditional["b2"]["absolute_selected_runs"], 1)
        self.assertAlmostEqual(all_stagnant["detection"][0]["value"], conditional["detection"][0]["value"] / 2)
        zero = summarize([feature_row(b2=0)])["availability"]["all_stagnant"]
        self.assertEqual(zero["b2"]["value"], 0)
        self.assertIsNone(zero["minimum_positive_gain"]["value"])
        self.assertEqual(zero["detection"][0]["value"], 0)

    def test_conditional_ratio_uses_all_tasks_not_only_selected_tasks(self):
        rows = [feature_row(b2=2), feature_row(seed=93002, b2=0, stagnant=False),
                feature_row("WC-s000", b2=4, stagnant=False), feature_row("UC-s001", b2=10)]
        result = summarize(rows)
        # Family 0: numerator=.5, denominator=.25. Family 1: numerator=10, denominator=1.
        # Ratio of equal-family numerators and denominators = 5.25/.625 = 8.4, not mean(2,10).
        item = result["availability"]["all_stagnant"]["b2"]
        self.assertAlmostEqual(item["weighted_numerator"], 5.25)
        self.assertAlmostEqual(item["weighted_denominator"], .625)
        self.assertAlmostEqual(item["value"], 8.4)
        self.assertAlmostEqual(result["availability"]["all_runs"]["b2"]["value"], 6.25)

    def test_no_stagnation_undefined_not_zero(self):
        result = summarize([feature_row(stagnant=False)])
        self.assertIsNone(result["primary_restoration"]["value"])
        self.assertEqual(result["availability"]["all_stagnant"]["b1"]["status"], "UNDEFINED")
        self.assertIsNone(result["availability"]["all_stagnant"]["detection"][0]["value"])

    def test_spearman_uses_family_means_not_repeated_candidates(self):
        rows = [feature_row(f"{label}-s{index:03d}", seed=93001 + repeat, b2=index + 1)
                for index in range(10) for label in ("UC", "WC", "SC") for repeat in range(2)]
        result = summarize(rows)
        self.assertEqual(len(result["spearman"]), 3)
        self.assertTrue(all(item["n"] == 10 for item in result["spearman"]))
        self.assertTrue(all(item["status"] == "UNDEFINED" for item in result["spearman"]))
        self.assertTrue(all(item["p_value"] is None for item in result["spearman"]))

    def test_full_900_known_source_counts_restored(self):
        rows = []
        for index, (instance, seed) in enumerate(sorted(a.expected_identities())):
            rows.append(feature_row(instance, seed, b2=1 if index < 202 else 0 if index < 210 else 2,
                                    stagnant=index < 210))
        result = a.summarize_features(rows)
        self.assertEqual(result["status"], "COMPLETE_EXPLORATORY")
        self.assertEqual(result["counts"], {"runs": 900, "stagnant": 210, "stagnant_with_improvement": 202})
        self.assertAlmostEqual(result["primary_restoration"]["value"], 202 / 210)
        rows[0] = feature_row(rows[0]["instance_id"], rows[0]["repeat_seed"], b2=0)
        with self.assertRaisesRegex(ValueError, "historical"):
            a.summarize_features(rows)

    def test_duplicate_missing_and_unexpected_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            a.summarize_features([feature_row(), feature_row()])
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            a.summarize_features([feature_row()])
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            a.summarize_features([feature_row()], expected_identities={("WC-s000", 93001)})

    def test_wrong_instance_seed_family_or_verification_rejected(self):
        for field, value in (("instance_id", "UC-s010"), ("repeat_seed", 92999), ("family", "s001"),
                             ("status", "INCOMPLETE"), ("verified", False), ("source_identity", {})):
            row = feature_row()
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize([row])

    def test_mixed_source_provenance_rejected_across_instances(self):
        rows = [feature_row(), feature_row("WC-s000")]
        rows[1]["source_identity"]["run_id"] += 1
        with self.assertRaisesRegex(ValueError, "Mixed"):
            summarize(rows)

    def test_bad_stagnation_neighbor_state_gains_or_types_rejected(self):
        changes = (("stagnant", False), ("stagnation_age", 5001), ("b1", 101),
                   ("b2", -1), ("total_better", 3), ("state", "GLOBAL_OPTIMUM"),
                   ("slack", -1), ("min_positive_gain", 0), ("sum_positive_gain", 0),
                   ("improvement_types", {"swap_one": 2}))
        for field, value in changes:
            row = feature_row()
            row["checkpoints"][-1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize([row])
        row = feature_row(b2=0)
        row["checkpoints"][-1]["min_positive_gain"] = 0
        with self.assertRaisesRegex(ValueError, "undefined"):
            summarize([row])

    def test_incomplete_checkpoint_or_probability_grid_rejected(self):
        for field in ("checkpoints", "model_probabilities", "detection_probabilities"):
            row = feature_row()
            if field == "checkpoints":
                row[field].pop()
            else:
                row["checkpoints"][-1][field].pop()
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize([row])

    def test_corrupt_model_or_detection_probability_rejected(self):
        for field in ("model_probabilities", "detection_probabilities"):
            row = feature_row()
            row["checkpoints"][-1][field][1]["probability"] += .01
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize([row])

    def test_operator_counts_margins_and_parent_denominators_rejected(self):
        for field, value in (("candidate_count", 4999), ("mutation_created_count", 4),
                             ("premutation_feasible_count", 4991), ("record_selected_parent_slots", 2001),
                             ("crossover_novel_to_both_parents_count", 5000)):
            row = feature_row()
            row["operators"]["groups"]["all_new"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize([row])
        row = feature_row()
        row["operators"]["groups"]["all_new"]["crossover_conditioned"]["undefined_parent_baseline_count"] += 1
        with self.assertRaisesRegex(ValueError, "denominator"):
            summarize([row])

    def test_operator_rates_and_exhaustive_events_keep_absolute_counts(self):
        result = summarize([feature_row(), feature_row(seed=93002)])
        group = result["operator_events"]["all_new"]
        self.assertEqual(group["candidate_count"], 10000)
        self.assertEqual(group["mutation_created_count"]["absolute_count"], 6)
        self.assertAlmostEqual(group["mutation_created_count"]["weighted_fraction"], 3 / 5000)
        self.assertEqual(sum(group[f"mutation_{kind}_count"]["absolute_count"]
                             for kind in ("created", "preserved", "lost", "neither")), 10000)
        parent = group["crossover_conditioned"]
        self.assertAlmostEqual(parent["premutation_better_than_parent_count"]["conditional_fraction_defined_crossover_parents"], 10 / 4493)

    def test_undefined_parent_denominator_is_not_zero_rate(self):
        row = feature_row()
        for group in row["operators"]["groups"].values():
            group["crossover_conditioned"].update(feasible_parent_baseline_count=0,
                undefined_parent_baseline_count=group["crossover_applied_count"],
                premutation_better_than_parent_count=0, final_better_than_parent_count=0)
        result = summarize([row])
        item = result["operator_events"]["all_new"]["crossover_conditioned"]["final_better_than_parent_count"]
        self.assertIsNone(item["conditional_fraction_defined_crossover_parents"])

    def test_operator_checkpoint_presence_consistency_and_fixed_example(self):
        row = feature_row()
        result = summarize([row, feature_row("WC-s000")])
        self.assertEqual(result["fixed_example"], row)
        self.assertEqual(result["record_presence"][0]["mask_present_fraction"], 1)
        row["operators"]["checkpoints"][0]["record_mask_copy_count"] = 0
        with self.assertRaisesRegex(ValueError, "presence"):
            summarize([row])

    def test_report_requires_ci_outside_checkout_and_complete_full_series(self):
        rows = [feature_row()]
        summary = summarize(rows)
        with TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
                with self.assertRaisesRegex(ValueError, "CI-only"):
                    a.write_report(directory, rows, summary)
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
                with self.assertRaisesRegex(ValueError, "outside"):
                    a.write_report(Path(__file__).parent / "forbidden", rows, summary)
                with self.assertRaisesRegex(ValueError, "Incomplete"):
                    a.write_report(directory, rows, summary)


if __name__ == "__main__":
    unittest.main()

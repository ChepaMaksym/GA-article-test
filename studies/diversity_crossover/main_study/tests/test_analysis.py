"""Synthetic mathematical/semantic fixtures; executed only by the CI suite.

No fixture reads main-series outputs or invokes a genetic algorithm. Entire
run pairs and task/family membership, rather than search calls, are observations.
"""

from copy import deepcopy
import unittest

from .. import analysis, reporting


def compact_row(task="UC-s000", start="cloned", method="baseline", seed=71001):
    """Abstract compact evidence with no claim to be a real KPLIB result."""
    diagnostic = seed == analysis.DIAGNOSTIC_SEED
    if task.startswith("Jump"):
        initial, optimum = 100, 100 + int(task[4:])
        mask = "1" * (100 - int(task[4:])) + "0" * int(task[4:])
    elif task in ("Flat", "OneMax"):
        initial, optimum, mask = 0, None if task == "Flat" else 100, "0" * 100
    else:
        initial, optimum, mask = 20 if diagnostic else 10, 20, "0" * 100
    score = {"key": [1, initial], "value": initial, "feasible": True}
    record = {"mask": mask, "score": score, "call": 0}
    search = {"status": "COMPLETE", "method": "baseline" if method == "mutation_control" else method,
              "budget": 5000, "new_calls": 5000, "physical_calls": 5000, "steps": 5000,
              "completed_steps": 5000, "incomplete_steps": 0, "accepted_steps": 0,
              "crossover_steps": 0, "candidate_feasible": 5000, "invalid_candidates": 0,
              "duplicate_candidates": 5000, "initial_record": deepcopy(record), "record": deepcopy(record),
              "first_improvement_call": None, "directed_active_steps": 0, "directed_changed_steps": 0,
              "metrics": {"unique_fraction": 1 / 30, "diversity": 0.0, "feasible_fraction": 1.0,
                          "mean_feasible_value": float(initial)}}
    product = {"crossover_candidates": 0, "pre_mutation_feasible": 0,
               "both_parents_feasible_candidates": 0, "pre_mutation_better_than_both": 0,
               "post_mutation_better_than_both": 0, "conditional_status": "NOT_APPLICABLE",
               "pre_mutation_better_fraction": None, "post_mutation_better_fraction": None,
               "U_pre": 0, "U_post": 0, "both_parents_feasible": 0}
    applicable = start == "cloned" and (task in analysis.CENTERS or task in ("Jump4", "Jump8"))
    return {"task": task, "start": start, "method": method, "seed": seed,
            "series": "diagnostic" if diagnostic else "main", "status": "COMPLETE",
            "verification_status": "VERIFIED", "implementation_sha": "a" * 40,
            "search": search, "productivity": product, "initial_value": initial,
            "exact_optimum": optimum, "relative_gap": None if optimum is None else (optimum - initial) / optimum,
            "verification_calls": 5030, "escape_applicable": applicable,
            "escape": False if applicable else None, "escape_call": None,
            "directed_activity": {"steps": 0, "active_steps": 0, "changed_position_steps": 0,
                                  "eligible_positions_total": 0, "eligible_positions_max": 0}}


def full_rectangle():
    return [compact_row(*key) for key in sorted(analysis.expected_identities())]


def observed_exit(row, call=5000):
    search = row["search"]
    target = row["exact_optimum"] if row["task"].startswith("Jump") else row["initial_value"] + 1
    search["record"] = {"mask": "1" * 100, "score": {"key": [1, target], "value": target, "feasible": True}, "call": call}
    search["first_improvement_call"] = call
    row["escape"], row["escape_call"] = True, call
    row["relative_gap"] = (row["exact_optimum"] - target) / row["exact_optimum"]
    return row


def productivity(row, *, cross=100, both=100, post=10, pre=0):
    item = row["productivity"]
    item.update(crossover_candidates=cross, pre_mutation_feasible=cross,
                both_parents_feasible_candidates=both, pre_mutation_better_than_both=pre,
                post_mutation_better_than_both=post, conditional_status="DEFINED" if both else "NOT_APPLICABLE",
                pre_mutation_better_fraction=pre / both if both else None,
                post_mutation_better_fraction=post / both if both else None,
                U_pre=pre, U_post=post, both_parents_feasible=both)
    cross_steps = cross // 4 if row["method"] == "repeated" else cross
    row["search"]["crossover_steps"] = cross_steps
    if row["method"] == "repeated":
        row["search"]["steps"] = row["search"]["completed_steps"] = 5000 - 3 * cross_steps
    if row["method"] == "directed":
        row["directed_activity"]["steps"] = cross_steps
    row["verification_calls"] = 5030 + cross
    return row


class RectangleAndSemanticsTests(unittest.TestCase):
    def test_registered_rectangle_has_exact_counts_and_diagnostic_seed(self):
        keys = analysis.expected_identities()
        self.assertEqual(len(keys), 6304)
        self.assertEqual(sum(key[0] in analysis.MODELS for key in keys), 960)
        self.assertEqual(sum(key[0] in analysis.KNAPSACK and key[1] == "bank" for key in keys), 3600)
        self.assertEqual(sum(key[0] in analysis.CENTERS and key[1] == "cloned" for key in keys), 1680)
        self.assertEqual(sum(key[3] == 71901 for key in keys), 64)
        self.assertNotIn(("UC-s001", "cloned", "baseline", 71001), keys)
        self.assertNotIn(("UC-s000", "cloned", "baseline", 71901), keys)

    def test_all_6304_complete_rows_required(self):
        result = analysis.validate_rows(full_rectangle())
        self.assertEqual(result["status"], "COMPLETE_MAIN")
        self.assertEqual(result["completed_search_calls"], 31520000)
        self.assertEqual(result["main_complete_runs"], 6240)
        self.assertEqual(result["diagnostic_complete_runs"], 64)

    def test_missing_results_have_no_inferential_zeros(self):
        result = analysis.analyze([compact_row()])
        self.assertEqual(result["status"], "INCOMPLETE_MAIN")
        self.assertEqual(len(result["missing_identities"]), 6303)
        self.assertIsNone(result["primary"])
        self.assertFalse(result["incomplete_rows_treated_as_zero"])

    def test_duplicate_unregistered_seed_and_mixed_sha_fail_closed(self):
        row = compact_row()
        with self.assertRaises(ValueError):
            analysis.validate_rows([row, deepcopy(row)])
        bad = deepcopy(row)
        bad["seed"] = 70001
        with self.assertRaises(ValueError):
            analysis.validate_rows([bad])
        other = compact_row(method="directed")
        other["implementation_sha"] = "b" * 40
        with self.assertRaises(ValueError):
            analysis.validate_rows([row, other])

    def test_verified_status_does_not_bypass_endpoint_validation(self):
        for path, value in (("physical_calls", 4999), ("candidate_feasible", 5001), ("first_improvement_call", 1)):
            row = compact_row()
            row["search"][path] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                analysis.validate_complete_row(row)
        row = compact_row()
        row["productivity"]["post_mutation_better_fraction"] = 0.0
        with self.assertRaises(ValueError):
            analysis.validate_complete_row(row)

    def test_success_on_final_call_and_nonexit_remain_distinct(self):
        noexit = compact_row(task="Jump4")
        success = observed_exit(deepcopy(noexit), 5000)
        analysis.validate_complete_row(success)
        a, b = analysis.escape_observation(noexit), analysis.escape_observation(success)
        self.assertEqual(a["restricted_calls"], b["restricted_calls"])
        self.assertTrue(a["censored"])
        self.assertFalse(b["censored"])
        self.assertIsNone(a["call"])
        self.assertEqual(b["call"], 5000)

    def test_global_controls_are_diagnostic_not_local_failures(self):
        row = compact_row(task="UC-s001", seed=71901)
        analysis.validate_complete_row(row)
        self.assertEqual(analysis.escape_observation(row)["status"], "NOT_APPLICABLE")
        row["search"]["record"]["score"]["value"] += 1
        with self.assertRaises(ValueError):
            analysis.validate_complete_row(row)

    def test_flat_has_no_quality_improvement_endpoint(self):
        row = compact_row(task="Flat", start="bank")
        analysis.validate_complete_row(row)
        summary = analysis.summarize_group([row])
        self.assertIsNone(summary["mean_record_gain"])
        self.assertEqual(summary["quality_improvement_status"], "NOT_APPLICABLE_FLAT")

    def test_mutation_branch_cannot_create_two_parent_event(self):
        row = productivity(compact_row(method="mutation_control"), cross=1, both=1, post=1)
        with self.assertRaises(ValueError):
            analysis.validate_complete_row(row)


class MathematicalAnalysisTests(unittest.TestCase):
    def test_exact_mcnemar_threshold_and_symmetry(self):
        self.assertEqual(analysis.mcnemar_exact(0, 0), 1.0)
        self.assertEqual(analysis.mcnemar_exact(6, 0), 0.03125)
        self.assertEqual(analysis.mcnemar_exact(7, 0), 0.015625)
        self.assertEqual(analysis.mcnemar_exact(7, 2), analysis.mcnemar_exact(2, 7))
        self.assertEqual(analysis.mcnemar_exact(5, 5), 1.0)

    def test_family_weights_do_not_follow_unequal_task_or_seed_counts(self):
        rows = [{"task": "UC-s000", "value": 1}, {"task": "WC-s000", "value": 1},
                {"task": "UC-s001", "value": 0}]
        self.assertAlmostEqual(analysis.equal_family_mean(rows, lambda row: row["value"]), 0.5)
        self.assertNotEqual(analysis.equal_family_mean(rows, lambda row: row["value"]), 2 / 3)
        rows = [{"task": "UC-s000", "value": 0}, {"task": "UC-s000", "value": 0},
                {"task": "WC-s000", "value": 1}]
        self.assertAlmostEqual(analysis.equal_family_mean(rows, lambda row: row["value"]), 0.5)

    def test_budget_and_conditional_productivity_have_different_denominators(self):
        row = productivity(compact_row(start="bank"))
        analysis.validate_complete_row(row)
        summary = analysis.summarize_group([row])
        self.assertEqual(summary["q_per_budget"], 10 / 5000)
        self.assertEqual(summary["conditional_productivity_pooled"]["value"], 10 / 100)
        zero = analysis.conditional_fraction(0, 0)
        self.assertEqual(zero["status"], "NOT_APPLICABLE")
        self.assertIsNone(zero["value"])

    def test_bca_constant_nonzero_and_zero_are_undefined_not_point_intervals(self):
        for values in ([0] * 30, [1] * 10):
            interval = analysis.bca_mean(values, seed=72001, resamples=100)
            self.assertEqual(interval["status"], "UNDEFINED_BCA")
            self.assertIsNone(interval["lower"])
            self.assertIsNone(interval["upper"])
            self.assertIsNotNone(interval["resample_index_sha256"])

    def test_bca_reproducible_with_finite_non_degenerate_whole_units(self):
        values = [-1, 0, 0, 0, 1, 1, 1, 0, -1, 0]
        a = analysis.bca_mean(values, seed=72002, resamples=1000)
        b = analysis.bca_mean(values, seed=72002, resamples=1000)
        self.assertEqual(a, b)
        self.assertEqual(a["status"], "DEFINED_BCA")
        self.assertLess(a["lower"], a["upper"])
        self.assertEqual(a["bootstrap_unit"], "whole_family")
        self.assertEqual(a["jackknife_unit"], "whole_family")

    def test_degenerate_complete_main_analysis_makes_no_superiority_claim(self):
        result = analysis.analyze(full_rectangle())
        self.assertEqual(result["status"], "COMPLETE_MAIN")
        self.assertEqual(result["primary"]["H1"]["exact_p"], 1.0)
        self.assertEqual(result["primary"]["H2"]["bca"]["status"], "UNDEFINED_BCA")
        self.assertEqual(result["nominal_primary_superiority_claims"], {"H1": False, "H2": False})
        self.assertFalse(result["practical_superiority_authorized"])
        self.assertEqual(len(result["primary"]["H2"]["pairs"]), 900)
        self.assertEqual(len(result["primary"]["H2"]["family_contrasts"]), 10)

    def test_exact_h1_is_not_replaced_when_supplementary_bca_is_undefined(self):
        rows = full_rectangle()
        for row in rows:
            if row["task"] == "Jump4" and row["start"] == "cloned" and row["method"] == "directed":
                observed_exit(row, call=1)
        result = analysis.analyze(rows)
        h1 = result["primary"]["H1"]
        self.assertEqual(h1["paired_table"], {"both_fail": 0, "directed_only": 30,
                                            "baseline_only": 0, "both_succeed": 0})
        self.assertEqual(h1["estimate"], 1.0)
        self.assertEqual(h1["exact_p"], 2 / 2 ** 30)
        self.assertEqual(h1["supplementary_bca"]["status"], "UNDEFINED_BCA")
        self.assertTrue(h1["nominal_superiority_supported"])
        self.assertFalse(result["primary"]["H2"]["nominal_superiority_supported"])


class ReportSemanticsTests(unittest.TestCase):
    def test_incomplete_report_has_no_primary_results_or_figure_links(self):
        result = analysis.analyze([])
        text = reporting.render_report(result)
        self.assertIn("не зараховано як нулі", text)
        self.assertNotIn("Δ_J", text)
        self.assertNotIn("figures/", text)

    def test_missing_traces_are_exposed_and_not_interpolated(self):
        found, missing = reporting.validate_traces(None, [])
        self.assertEqual(found, {})
        self.assertEqual(len(missing), 16)

    def test_verified_trace_endpoint_must_match_compact_endpoint(self):
        row = compact_row()
        points = [{"call": 0, "best_value": 10, "mean_feasible_value": 10.0, "diversity": 0.0},
                  {"call": 5000, "best_value": 10, "mean_feasible_value": 10.0, "diversity": 0.0}]
        trace = {key: row[key] for key in ("task", "start", "method", "seed")}
        trace["points"] = points
        found, missing = reporting.validate_traces([trace], [row])
        self.assertEqual(len(found), 1)
        self.assertEqual(len(missing), 15)
        points[-1]["diversity"] = 0.5
        with self.assertRaises(ValueError):
            reporting.validate_traces([trace], [row])


if __name__ == "__main__":
    unittest.main()

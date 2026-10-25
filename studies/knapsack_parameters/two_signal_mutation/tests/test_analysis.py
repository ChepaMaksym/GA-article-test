"""CI-only software fixtures, not observed experiments or superiority data."""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.two_signal_mutation import analysis as a
from studies.knapsack_parameters.two_signal_mutation import engine
from studies.knapsack_parameters.two_signal_mutation.plots import render_report


def synthetic_row(identity):
    """Constructed, stationary fixture with no claim of a real GA execution."""
    task, start, seed, method = identity
    population = [{"q": q, "complete": True, "unique_masks": 3, "unique_fraction": .1,
                   "mean_pairwise_hamming": 2.5, "feasible_fraction": .8,
                   "mean_feasible_profit": 50., "record_in_population": True}
                  for q in range(0, 4989, 29)]
    population.append({**population[-1], "q": 5000, "complete": False})
    generations = [{"q": q, "start_q": q - 28, "complete": True, "p_m": .01, "p_m_next": .01,
                    "mean_novelty": .5, "gate_allows_increase": True, "controller_event": "NO_CHANGE"}
                   for q in range(29, 4989, 29)]
    generations.append({**generations[-1], "q": 5000, "start_q": 4989, "complete": False,
                        "gate_allows_increase": None, "controller_event": "PARTIAL_NO_UPDATE"})
    operators = [{"distance": distance, "total": 0, "crossed": 0, "novel_crossed": 0,
                  "feasible_crossed": 0, "better_both_crossed": 0} for distance in range(101)]
    operators[2].update(total=5000, crossed=4500, novel_crossed=2250,
                        feasible_crossed=4000, better_both_crossed=500)
    return {"schema": a.SCHEMA, "verification_status": "VERIFIED", "task": task,
            "family": task.split("-")[1], "class_label": task.split("-")[0],
            "start": start, "seed": seed, "method": method, "implementation_sha": "a" * 40,
            "budget": 5000, "n": 100, "journal_sha256": "b" * 64,
            "problem_sha256": "c" * 64, "initial_population_sha256": "d" * 64,
            "initial_rng_sha256": "e" * 64, "optimum": 100, "capacity": 100,
            "initial_best_profit": 50, "final_best_profit": 99, "final_best_weight": 90,
            "final_capacity_fraction": .9, "final_gap_percent": 1.,
            "first_targets": {"95": 1000, "99": 5000},
            "record_events": [{"q": 0, "profit": 50}, {"q": 1000, "profit": 95}, {"q": 5000, "profit": 99}],
            "population_trace": population, "generation_trace": generations, "operator_bins": operators,
            "early": {"mean_novelty": .5, "mean_pairwise_hamming": 2.5, "unique_fraction": .1},
            "late_gain_gap_points": 4., "infeasible_fraction": .2, "duplicate_fraction": .1,
            "timings": {"search_wall_ns": 100, "serialization_ns": None, "verification_ns": 200,
                        "preparation_ns": 10},
            "kernel_timing_ns": {"validation": 1, "selection": 1, "variation": 1, "evaluation": 1,
                                 "signal": 1, "controller": 1, "log_assembly": 1, "total": 10},
            "accounting": {"new_search_evaluations": 5000, "initial_known_positions": 30,
                           "independent_score_checks": 10030, "initial_score_checks": 30,
                           "final_score_checks": 5000, "premutation_score_checks": 5000}}


def synthetic_rows(scope="pilot"):
    return [synthetic_row(identity) for identity in sorted(a.expected_identities(scope))]


def small_envelope(method="two_signal", budget=61):
    problem = {"n": 4, "weights": [1, 1, 1, 1], "profits": [1, 2, 3, 4], "capacity": 2}
    masks = ["0000", "1000", "0100", "0010", "0001", "1100"] * 5
    scores = [{"weight": sum(bit == "1" for bit in mask),
               "profit": sum(value for bit, value in zip(mask, problem["profits"], strict=True) if bit == "1"),
               "feasible": sum(bit == "1" for bit in mask) <= 2} for mask in masks]
    log = engine.run_search(problem, masks, scores, method, engine.make_rngs(37002, 0, 1), budget=budget)
    return {"task": "UC-s000", "family": "s000", "start": "bank", "seed": 37002,
            "method": method, "implementation_sha": "a" * 40, "optimum": 7, "log": log,
            "timings": {"search_wall_ns": 100, "serialization_ns": None}}


class TwoSignalAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Registered analysis fixtures execute only in CI")

    def test_expected_rectangles_are_disjoint_and_exact(self):
        pilot, main = a.expected_identities("pilot"), a.expected_identities("main")
        self.assertEqual(len(pilot), 24)
        self.assertEqual(len(main), 2700)
        self.assertFalse(pilot & main)
        self.assertEqual({identity[1] for identity in main}, {"bank"})
        self.assertEqual(len({identity[0].split("-")[1] for identity in main}), 10)

    def test_extract_calls_independent_verifier_and_keeps_prefix(self):
        for method in a.METHODS:
            with self.subTest(method=method):
                envelope = small_envelope(method)
                compact = a.extract_run(envelope)
                self.assertEqual(compact["verification_status"], "VERIFIED")
                self.assertEqual(compact["budget"], 61)
                self.assertEqual(compact["accounting"]["independent_score_checks"], 152)
                self.assertEqual(len(compact["generation_trace"]), 3)
                self.assertFalse(compact["generation_trace"][-1]["complete"])
                self.assertIsNone(compact["timings"]["serialization_ns"])
                feasible = [score["profit"] for score in envelope["log"]["initial_scores"] if score["feasible"]]
                feasible += [row["profit"] for row in envelope["log"]["candidates"] if row["feasible"]]
                self.assertEqual(compact["final_best_profit"], max(feasible))

    def test_extract_does_not_pass_external_optimum_into_search(self):
        envelope = small_envelope()
        with patch.object(engine, "run_search", side_effect=AssertionError("analysis initiated a search")):
            result = a.extract_run(envelope)
        self.assertEqual(result["optimum"], 7)
        self.assertNotIn("optimum", envelope["log"]["problem"])

    def test_extract_rejects_corrupt_raw_candidate(self):
        envelope = small_envelope()
        envelope["log"]["candidates"][-1]["profit"] += 1
        with self.assertRaises(ValueError):
            a.extract_run(envelope)

    def test_external_reference_cannot_be_below_a_known_feasible_record(self):
        envelope = small_envelope()
        envelope["optimum"] = 1
        with self.assertRaisesRegex(ValueError, "optimum"):
            a.extract_run(envelope)

    def test_unknown_and_negative_timings_are_not_zero(self):
        envelope = small_envelope()
        envelope["timings"]["verification_ns"] = -1
        with self.assertRaisesRegex(ValueError, "timings"):
            a.extract_run(envelope)

    def test_population_window_uses_state_at_each_inclusive_query(self):
        trace = [{"q": 0, "complete": True, "d": 0}, {"q": 3, "complete": True, "d": 10},
                 {"q": 5, "complete": False, "d": 1000}]
        # q1,2 use the beginning; q3,4,5 use the committed q3 state.
        self.assertEqual(a.carried_population_mean(trace, 5, "d"), 6)

    def test_rank_ties_and_undefined_constant_series(self):
        self.assertEqual(a.average_ranks([3, 1, 1, 7]), [3., 1.5, 1.5, 4.])
        result = a.descriptive_spearman([1, 1, 1], [3, 2, 1])
        self.assertEqual(result["status"], "UNDEFINED")
        self.assertIsNone(result["rho"])
        self.assertIsNone(result["p_value"])

    def test_spearman_is_descriptive_not_a_causal_or_independence_test(self):
        result = a.descriptive_spearman([1, 2, 2, 4], [4, 2, 2, 1])
        self.assertAlmostEqual(result["rho"], -1)
        self.assertFalse(result["causal_claim"])
        with self.assertRaises(ValueError):
            a.descriptive_spearman([1, float("nan")], [1, 2])

    def test_family_weighting_does_not_overweight_more_tasks_or_repeats(self):
        rows = [{"task": "UC-s010", "family": "s010", "v": 0},
                {"task": "UC-s010", "family": "s010", "v": 0},
                {"task": "SC-s010", "family": "s010", "v": 10},
                {"task": "UC-s011", "family": "s011", "v": 20}]
        self.assertEqual(a.mean_by_family(rows, lambda row: row["v"]), {"s010": 5, "s011": 20})
        self.assertEqual(a._mean(rows, lambda row: row["v"]), 12.5)

    def test_bca_shared_draws_deterministic_and_registered_direction(self):
        vectors = [[value / 10, -value / 20] for value in range(10)]
        first = a.family_bca(vectors, replicates=500)
        second = a.family_bca(vectors, replicates=500)
        self.assertEqual(first, second)
        self.assertEqual(first["seed"], 94031)
        self.assertEqual(first["confidence_each"], .975)
        self.assertAlmostEqual(first["nominal_joint_confidence"], .95)
        self.assertEqual(len(first["intervals"]), 2)
        self.assertEqual(first["intervals"][0]["contrast_id"], a.CONTRASTS[0])
        self.assertGreater(first["intervals"][0]["estimate_gap_points"], 0)
        self.assertLess(first["intervals"][1]["estimate_gap_points"], 0)
        self.assertIsNotNone(first["resample_index_sha256"])

    def test_degenerate_bca_has_no_fabricated_zero_width_interval(self):
        result = a.family_bca([[0, 1]] * 10, replicates=100)
        self.assertTrue(all(row["status"] == "DESCRIPTIVE_ONLY" for row in result["intervals"]))
        self.assertTrue(all(row["lower"] is None and row["upper"] is None for row in result["intervals"]))
        self.assertFalse(any(row["positive_effect_supported"] for row in result["intervals"]))

    def test_insufficient_family_count_is_only_descriptive(self):
        result = a.family_bca([[0, 1], [1, 2]], replicates=50)
        self.assertIsNone(result["resample_index_sha256"])
        self.assertEqual(result["intervals"][0]["reason"], "fewer_than_five_families")

    def test_pilot_has_no_bootstrap_or_correlations(self):
        with patch.object(a, "family_bca", side_effect=AssertionError("pilot attempted inference")):
            report = a.aggregate(synthetic_rows(), scope="pilot", expected_sha="a" * 40)
        self.assertEqual(report["runs"], 24)
        self.assertEqual(report["new_search_evaluations"], 120000)
        self.assertEqual(report["primary_analysis"]["status"], "NOT_PERFORMED_TECHNICAL_PILOT")
        self.assertEqual(report["correlations"], [])
        self.assertEqual(len(report["method_summaries"]), 6)
        self.assertEqual(report["prespecified_example"]["task"], "UC-s000")

    def test_main_has_two_contrasts_six_correlations_and_fixed_example(self):
        report = a.aggregate(synthetic_rows("main"), scope="main", expected_sha="a" * 40)
        self.assertEqual(report["runs"], 2700)
        self.assertEqual(report["new_search_evaluations"], 13500000)
        self.assertEqual(report["primary_analysis"]["replicates"], 50000)
        self.assertEqual(len(report["primary_analysis"]["family_effects"]), 10)
        self.assertEqual(len(report["primary_analysis"]["intervals"]), 2)
        self.assertEqual(len(report["correlations"]), 6)
        self.assertTrue(all(row["family_count"] == 10 for row in report["correlations"]))
        self.assertTrue(all(row["status"] == "UNDEFINED" for row in report["correlations"]))
        self.assertFalse(report["primary_analysis"]["advantage_over_both_controls_supported"])
        self.assertFalse(report["primary_analysis"]["practical_advantage_established"])
        self.assertEqual(report["prespecified_example"]["task"], "UC-s010")
        self.assertEqual(report["prespecified_example"]["seed"], 94001)

    def test_missing_and_duplicate_runs_do_not_form_a_complete_series(self):
        rows = synthetic_rows()
        for invalid in (rows[:-1], rows + [deepcopy(rows[0])]):
            with self.assertRaises(ValueError):
                a.aggregate(invalid, scope="pilot")

    def test_pilot_rows_cannot_be_promoted_to_main(self):
        with self.assertRaises(ValueError):
            a.aggregate(synthetic_rows(), scope="main")

    def test_mixed_source_sha_and_initial_states_rejected(self):
        for field, value in (("implementation_sha", "f" * 40),
                             ("initial_population_sha256", "f" * 64),
                             ("initial_rng_sha256", "f" * 64)):
            rows = synthetic_rows()
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                a.aggregate(rows, scope="pilot")

    def test_mixed_problem_reference_or_wrong_budget_rejected(self):
        for field, value in (("problem_sha256", "f" * 64), ("budget", 4999),
                             ("final_gap_percent", 5), ("family", "s999")):
            rows = synthetic_rows()
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                a.aggregate(rows, scope="pilot")

    def test_target_at_zero_last_query_and_nonattainment_are_distinct(self):
        rows = synthetic_rows()
        zero, last, never = rows[:3]
        zero["first_targets"] = {"95": 0, "99": 0}
        last["first_targets"] = {"95": 5000, "99": 5000}
        never["first_targets"] = {"95": None, "99": None}
        result = a._summarize(rows[:3])["targets"]["99"]
        self.assertEqual(result["attained"], 2)
        self.assertEqual(result["not_attained"], 1)
        self.assertEqual(result["curve"][0], {"q": 0, "fraction": 1 / 3})
        self.assertEqual(result["curve"][-1], {"q": 5000, "fraction": 2 / 3})
        self.assertAlmostEqual(result["restricted_mean_queries"], 10000 / 3)

    def test_operator_rates_condition_on_applied_crossover(self):
        report = a.aggregate(synthetic_rows(), scope="pilot")
        cell = next(row for row in report["operator_cells"] if row["start"] == "bank" and
                    row["method"] == "fixed" and row["distance_bin"] == "2")
        self.assertEqual(cell["novel_fraction"], .5)
        self.assertAlmostEqual(cell["feasible_fraction"], 4000 / 4500)
        self.assertAlmostEqual(cell["better_both_fraction"], 500 / 4500)
        empty = next(row for row in report["operator_cells"] if row["distance_bin"] == "0")
        self.assertEqual(empty["crossed"], 0)
        self.assertIsNone(empty["better_both_fraction"])
        self.assertFalse(cell["independent_sample_claim"])

    def test_operator_missing_counts_or_invalid_denominator_rejected(self):
        for mutate in (lambda row: row["operator_bins"][2].update(total=4999),
                       lambda row: row["operator_bins"][2].update(better_both_crossed=4501)):
            rows = synthetic_rows()
            mutate(rows[0])
            with self.assertRaises(ValueError):
                a.aggregate(rows, scope="pilot")

    def test_preparation_shared_once_and_unknown_times_retained(self):
        report = a.aggregate(synthetic_rows(), scope="pilot")
        self.assertEqual(report["costs"]["shared_preparation_conditions"], 8)
        self.assertEqual(report["costs"]["shared_preparation_total_ns"], 80)
        rows = [row for row in report["costs"]["profile_metrics"] if row["metric"] == "serialization_ns"]
        self.assertTrue(all(row["mean_ns"] is None and row["known_observations"] == 0 for row in rows))

    def test_scientific_analysis_refuses_local_execution(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            for action in (lambda: a.expected_identities("pilot"),
                           lambda: a.descriptive_spearman([1, 2], [2, 1]),
                           lambda: a.family_bca([[1, 2]] * 10)):
                with self.assertRaises(ValueError):
                    action()

    def test_five_title_free_figures_and_numerical_empty_categories(self):
        report = a.aggregate(synthetic_rows(), scope="pilot")
        import matplotlib.figure

        original = matplotlib.figure.Figure.savefig
        checked = []
        def save_checked(figure, *args, **kwargs):
            self.assertFalse(figure._suptitle and figure._suptitle.get_text())
            self.assertTrue(all(not axis.get_title() for axis in figure.axes))
            checked.append(True)
            return original(figure, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory, patch.object(matplotlib.figure.Figure, "savefig", save_checked):
            result = render_report(report, directory)
            self.assertEqual(len(result["files"]), 5)
            self.assertEqual(len(checked), 5)
            self.assertTrue(all((Path(directory) / name).stat().st_size > 0 for name in result["files"]))
            self.assertTrue(any(row["name"] == "empty_crossover_strata" for row in result["tables"]))
            self.assertTrue(result["technical_pilot_only"])

    def test_unverified_or_replaced_example_is_not_rendered(self):
        report = a.aggregate(synthetic_rows(), scope="pilot")
        for change in (lambda value: value.update(status="PARTIAL"),
                       lambda value: value["prespecified_example"].update(seed=1)):
            invalid = deepcopy(report)
            change(invalid)
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                render_report(invalid, directory)


if __name__ == "__main__":
    unittest.main()

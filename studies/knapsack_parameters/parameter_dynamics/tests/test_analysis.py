"""Analysis fixtures use synthetic summaries, never scientific outcomes."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from studies.knapsack_parameters.parameter_dynamics import analysis as a


class AnalysisTests(unittest.TestCase):
    def test_query_weighting_is_not_generation_weighting(self):
        generations = []
        for left, right, mu in ((1, 10, 10), (11, 100, 100)):
            theta = {"p_m": .01, "p_c": .9, "target_mu": mu, "tournament_size": 2, "elite_count": 1}
            generations.append({"start_q": left, "q": right, "parameters_before": theta,
                                "actual_parent_mu": mu, "complete": False})
        activity, windows = a.parameter_metrics(generations, 100)
        self.assertEqual(activity["target_mu"]["query_weighted_mean"], 91)
        self.assertEqual(windows[0]["parameters"]["target_mu"], 91)
        self.assertFalse(activity["target_mu"]["changed"])
        bad = deepcopy(generations)
        bad[-1]["start_q"] = 12
        with self.assertRaises(ValueError):
            a.parameter_metrics(bad, 100)

    def test_unequal_family_sizes_are_not_pooled(self):
        rows = [{"family": "a", "task": "a1", "v": 0, "first_targets": {"95": None}},
                {"family": "a", "task": "a2", "v": 0, "first_targets": {"95": None}},
                {"family": "b", "task": "b1", "v": 10, "first_targets": {"95": 5000}}]
        self.assertEqual(a.weighted_mean(rows, lambda r: r["v"]), 5)
        result = a.target_summary(rows, 95)
        self.assertEqual(result["curve"][-1]["fraction"], .5)
        self.assertEqual(result["attained"], 1)
        self.assertEqual(result["not_attained"], 2)
        self.assertEqual(result["restricted_mean_queries"], 5000)

    def test_all_six_degenerate_intervals_stay_undefined(self):
        result = a.family_bca([[0] * 6 for _ in range(10)], replicates=80, seed=5)
        self.assertEqual(result["confidence_each"], 1 - .05 / 6)
        self.assertEqual(len(result["intervals"]), 6)
        self.assertTrue(all(row["lower"] is None and row["upper"] is None for row in result["intervals"]))

    def test_bca_is_deterministic_and_resamples_whole_families(self):
        values = [[(i - 4) * (j + 1) for j in range(6)] for i in range(10)]
        first = a.family_bca(values, replicates=1200, seed=9)
        self.assertEqual(first, a.family_bca(values, replicates=1200, seed=9))
        self.assertEqual(first["unit"], "whole_family")
        self.assertEqual(first["family_count"], 10)

    def test_rectangles_and_no_partial_promotion(self):
        self.assertEqual(len(a.expected_identities("pilot")), 256)
        self.assertEqual(len(a.expected_identities("main")), 28800)
        with self.assertRaises(ValueError):
            a.validate_rows([], "pilot")
        with self.assertRaises(ValueError):
            a.expected_identities("unknown")

    def test_exact_gap_and_operator_denominators(self):
        self.assertEqual(a.gap(100, 99), 1)
        for optimum, profit in ((100, 101), (0, 0), (100, -1)):
            with self.assertRaises(ValueError):
                a.gap(optimum, profit)
        rows = [{"distance": 2, "total": 5, "crossed": 4, "novel_crossed": 1,
                 "feasible_crossed": 3, "better_both_crossed": 0}]
        self.assertEqual(a.collapse_operators(rows)[2]["total"], 5)
        rows[0]["novel_crossed"] = 5
        with self.assertRaises(ValueError):
            a.collapse_operators(rows)

    def test_real_replay_to_complete_synthetic_rectangle_and_figures(self):
        from studies.knapsack_parameters.parameter_dynamics import engine, plots
        problem = {"n": 100, "weights": [1] * 100, "profits": [1] * 100, "capacity": 100}
        masks = ["0" * 100] * 30
        scores = [{"weight": 0, "profit": 0, "feasible": True} for _ in masks]
        log = engine.run_search(problem, masks, scores, 0, engine.make_rngs(3, 0, 0), 5000)
        envelope = {"task": "UC-s000", "family": "s000", "start": "bank", "seed": 96999,
                    "profile": 0, "stage": "pilot", "implementation_sha": "a" * 40, "optimum": 100,
                    "log": log, "timings": {"search_wall_ns": 1, "serialization_ns": 1, "verification_ns": 1}}
        base = a.extract_run(envelope)
        self.assertEqual(base["accounting"]["independent_score_checks"], 10030)
        self.assertEqual(sum(row["new_calls"] for row in base["parameter_windows"]), 5000)
        # Synthetic compact records deliberately reuse a verified educational
        # trajectory; they are fixtures, not additional GA searches/results.
        rows = []
        for task, start, seed, profile in sorted(a.expected_identities("pilot")):
            row = deepcopy(base)
            row.update(task=task, family=task[3:], class_label=task[:2], start=start, seed=seed, profile=profile)
            if (task, start, profile) not in (("UC-s000", "bank", 0), ("UC-s000", "bank", 31)):
                row.pop("example_trace", None)
            rows.append(row)
        summary = a.aggregate(rows, scope="pilot", expected_sha="a" * 40)
        self.assertEqual(summary["runs"], 256)
        self.assertEqual(summary["primary_analysis"]["replicates"], 0)
        self.assertEqual(len(summary["interactions"]), 10)
        with tempfile.TemporaryDirectory() as temp:
            rendering = plots.render_report(summary, temp)
            self.assertFalse(rendering["inside_titles"])
            self.assertGreaterEqual(len(rendering["figures"]), 3)
            self.assertTrue(all((Path(temp) / row["file"]).is_file() for row in rendering["figures"]))
        for mutate in (lambda rs: rs.pop(), lambda rs: rs.append(deepcopy(rs[0])),
                       lambda rs: rs[0].update(implementation_sha="b" * 40),
                       lambda rs: rs[0].update(first_generation_sha256="b" * 64),
                       lambda rs: rs[0].update(final_best_mask="bad")):
            bad = deepcopy(rows)
            mutate(bad)
            with self.assertRaises(ValueError):
                a.aggregate(bad, scope="pilot", expected_sha="a" * 40)


if __name__ == "__main__":
    unittest.main()

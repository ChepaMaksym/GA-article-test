"""CI-only checks of prospective analysis using explicitly synthetic fixtures.

The complete rectangular tables below contain constructed compact records,
not scientific runs, and cannot support an empirical advantage claim.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.adaptation_analysis import analysis
from studies.knapsack_parameters.adaptation_analysis.comparison import run_profile
from studies.knapsack_parameters.adaptation_analysis.plots import render_report


def toy_envelope(method="classical", start="bank", budget=61):
    problem = {"n": 4, "weights": [1, 2, 3, 4], "profits": [2, 4, 6, 8], "capacity": 10}
    masks = (["0000", "1000", "0100", "0010", "0001", "1100"] * 5
             if start == "bank" else ["1000"] * 30)
    scores = []
    for mask in masks:
        weight = sum(problem["weights"][i] for i, bit in enumerate(mask) if bit == "1")
        profit = sum(problem["profits"][i] for i, bit in enumerate(mask) if bit == "1")
        scores.append({"weight": weight, "profit": profit, "feasible": weight <= 10})
    log = run_profile(problem, masks, scores, method, 18001, 0, 0 if start == "cloned" else 1, budget=budget)["log"]
    return {"task": "UC-s000", "family": "s000", "start": start, "seed": 18001,
            "method": method, "implementation_sha": "a" * 40, "log": log,
            "optimum": 20, "center_profit": 2 if start == "cloned" else None}


def synthetic_row(identity, cases):
    """A stationary mathematical fixture, explicitly not a recorded GA run."""
    task, start, seed, method = identity
    case = cases[task]
    optimum = case["payload"]["exact"]["confirmed_optimum"]
    center = case["payload"]["certificate"]["center"]["profit"] if start == "cloned" else None
    profit = center if center is not None else optimum // 2
    gap = 100 * (optimum - profit) / optimum
    arch = method in ("balanced_gap", "unbalanced_gap")
    windows = [{"first_query": i * 500 + 1, "last_query": (i + 1) * 500, "queries": 500,
                "mean_p_m": 0.01, "mean_p_c": 0.9, "feasible_fraction": 1.0,
                "mean_archive_size": 1.0 if arch else None,
                "memory_switch_fraction": 0.0 if arch else None,
                "parent_uses": 1000, "unique_parents": 1, "maximum_parent_share": 1.0}
               for i in range(10)]
    return {"schema": "ga-adaptation-compact-run-v1", "verification_status": "VERIFIED",
            "task": task, "family": case["family"], "start": start, "seed": seed, "method": method,
            "implementation_sha": "a" * 40, "budget": 5000, "journal_sha256": "b" * 64,
            "initial_population_sha256": "c" * 64, "initial_rng_sha256": "d" * 64,
            "problem_sha256": hashlib.sha256(analysis._registered_problem_bytes(task)).hexdigest(),
            "input_binding": "KPLIB_BYTES_AND_REGISTERED_INITIAL_STATE",
            "optimum": optimum, "center_profit": center, "initial_best_profit": profit,
            "final_best_profit": profit, "final_gap_percent": gap,
            "escaped": False if center is not None else None, "first_escape": None,
            "capped_escape_calls": 5000 if center is not None else None,
            "first_99": 0 if 100 * profit >= 99 * optimum else None,
            "observations": [{"query": q, "best_profit": profit, "gap_percent": gap,
                              "attained_99": 100 * profit >= 99 * optimum,
                              "escaped": False if center is not None else None} for q in (0, 1000, 2500, 5000)],
            "windows": windows,
            "early": {"mean_p_m": 0.01, "mean_p_c": 0.9, "feasible_fraction": 1.0,
                      "parent_uses": 5000, "unique_parents": 1, "maximum_parent_share": 1.0},
            "late": {"gain_over_optimum": 0.0, "feasible_fraction": 1.0,
                     "parent_uses": 5000, "unique_parents": 1, "maximum_parent_share": 1.0},
            "record_events": [{"query": 0, "profit": profit}],
            "population_trace": [{"query": 0, "mu": 30, "feasible_fraction": 1.0,
                                  "mean_feasible_profit": float(profit), "unique_genotypes": 1,
                                  "normalized_hamming": 0.0}],
            "diagnostics": {"infeasible_candidates": 0, "duplicate_candidates": 5000,
                            "strict_record_improvements": 0},
            "accounting": {"search_queries": 5000, "known_score_checks": 30,
                           "analysis_raw_score_checks": 5030, "diagnostic_new_fitness_evaluations": 0}}


class AdaptationAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Prospective analysis checks execute only in GitHub Actions")

    def test_extract_all_five_verified_log_shapes(self):
        for method in analysis.METHODS:
            with self.subTest(method=method):
                compact = analysis.extract_run(toy_envelope(method))
                self.assertEqual(compact["verification_status"], "VERIFIED")
                self.assertEqual(compact["budget"], 61)
                self.assertEqual(compact["accounting"]["analysis_raw_score_checks"], 91)
                self.assertIsNone(compact["escaped"])
                self.assertIsNone(compact["first_escape"])
                self.assertEqual(compact["windows"][0]["parent_uses"], 122)
                self.assertEqual(compact["population_trace"][-1]["query"], 58)

    def test_record_uses_every_evaluated_candidate_including_prefix(self):
        envelope = toy_envelope("balanced_gap")
        compact = analysis.extract_run(envelope)
        feasible = [entry["profit"] for entry in envelope["log"]["initial_scores"] if entry["feasible"]]
        feasible += [entry["profit"] for entry in envelope["log"]["candidates"] if entry["feasible"]]
        self.assertEqual(compact["final_best_profit"], max(feasible))
        self.assertEqual(compact["observations"][-1]["query"], 61)
        self.assertEqual(compact["record_events"][0]["query"], 0)

    def test_cloned_escape_and_nonexits_remain_separate(self):
        envelope = toy_envelope("classical", start="cloned")
        compact = analysis.extract_run(envelope)
        calls = [child["call"] for child in envelope["log"]["candidates"] if child["feasible"] and child["profit"] > 2]
        self.assertEqual(compact["first_escape"], min(calls) if calls else None)
        self.assertEqual(compact["capped_escape_calls"], min(calls) if calls else 61)
        self.assertEqual(compact["escaped"], bool(calls))

    def test_99_percent_is_exact_integer_threshold(self):
        envelope = toy_envelope("unbalanced_gap")
        compact = analysis.extract_run(envelope)
        for point in compact["observations"]:
            self.assertEqual(point["attained_99"], 100 * point["best_profit"] >= 99 * 20)

    def test_archive_memory_diagnostic_does_not_call_search_again(self):
        envelope = toy_envelope("balanced_gap")
        with patch("studies.knapsack_parameters.adaptation_analysis.comparison.run_profile",
                   side_effect=AssertionError("analysis initiated search")):
            compact = analysis.extract_run(envelope)
        self.assertTrue(all(0 <= window["memory_switch_fraction"] <= 1 for window in compact["windows"]))
        self.assertTrue(all(window["mean_archive_size"] >= 1 for window in compact["windows"]))

    def test_parameters_are_query_weighted_not_generation_weighted(self):
        envelope = toy_envelope("adaptive_crossover", budget=61)
        compact = analysis.extract_run(envelope)
        log = envelope["log"]
        expected = sum(event["p_c"] * (event["end_call"] - event["start_call"] + 1)
                       for event in log["generations"]) / 61
        self.assertAlmostEqual(compact["windows"][0]["mean_p_c"], expected)

    def test_parent_concentration_counts_duplicate_parent_positions(self):
        metric = analysis._parent_concentration([["00", "00"], ["00", "11"]])
        self.assertEqual(metric["parent_uses"], 4)
        self.assertEqual(metric["unique_parents"], 2)
        self.assertEqual(metric["maximum_parent_share"], 0.75)

    def test_bad_envelope_metadata_and_oracle_disagreement_rejected(self):
        envelope = toy_envelope()
        for key, value in (("family", "s999"), ("method", "lambda_own"),
                           ("implementation_sha", "main"), ("optimum", 1)):
            bad = deepcopy(envelope)
            bad[key] = value
            with self.assertRaises(ValueError):
                analysis.extract_run(bad)
        bad = deepcopy(envelope)
        bad["extra"] = "not declared"
        with self.assertRaises(ValueError):
            analysis.extract_run(bad)

    def test_corrupted_candidate_not_accepted_as_verified(self):
        envelope = toy_envelope()
        envelope["log"]["candidates"][0]["profit"] += 1
        with self.assertRaises(ValueError):
            analysis.extract_run(envelope)

    def test_average_ranks_and_undefined_constant_spearman(self):
        self.assertEqual(analysis.average_ranks([1, 1, 2, 3]), [1.5, 1.5, 3.0, 4.0])
        constant = analysis.descriptive_spearman([1, 1, 1], [1, 2, 3])
        self.assertEqual(constant["status"], "UNDEFINED")
        self.assertIsNone(constant["rho"])
        self.assertIsNone(constant["p_value"])
        positive = analysis.descriptive_spearman([1, 1, 2, 3], [4, 4, 5, 6])
        self.assertAlmostEqual(positive["rho"], 1)
        self.assertFalse(positive["causal_claim"])

    def test_task_then_family_weighting_not_pooled_repetition_weight(self):
        records = [{"task": "UC", "value": 0}] * 3 + [{"task": "WC", "value": 1}]
        self.assertEqual(analysis._mean_by_task(records, lambda row: row["value"]), 0.5)

    def test_registered_rectangles_have_exact_required_sizes(self):
        self.assertEqual(len(analysis.expected_identities("main")), 6600)
        self.assertEqual(len(analysis.expected_identities("pilot")), 40)
        self.assertTrue(all(identity[-1] not in analysis.DEFERRED for identity in analysis.expected_identities("main")))

    def test_not_run_does_not_become_zero_success(self):
        summary = analysis.summarize_series([], scope="main")
        self.assertEqual(summary["status"], "NOT_RUN")
        self.assertEqual(summary["family_cells"], [])
        self.assertIsNone(summary["statistics"])
        self.assertEqual(summary["deferred"]["lambda_own"], "BLOCKED_LAMBDA_REPLICATION")

    def test_incomplete_duplicate_and_mixed_sha_results_rejected(self):
        cases, _ = analysis._cases()
        identities = sorted(analysis.expected_identities("main"))
        first = synthetic_row(identities[0], cases)
        incomplete = analysis.summarize_series([first])
        self.assertEqual(incomplete["status"], "INCOMPLETE")
        self.assertIsNone(incomplete["statistics"])
        with self.assertRaises(ValueError):
            analysis.summarize_series([first, deepcopy(first)])
        second = synthetic_row(identities[1], cases)
        second["implementation_sha"] = "c" * 40
        with self.assertRaises(ValueError):
            analysis.summarize_series([first, second])

    def test_complete_synthetic_pilot_is_descriptive_without_bootstrap(self):
        cases, _ = analysis._cases()
        rows = [synthetic_row(identity, cases) for identity in sorted(analysis.expected_identities("pilot"))]
        with patch.object(analysis, "family_bca", side_effect=AssertionError("pilot bootstrap forbidden")):
            summary = analysis._summarize_rows(rows, scope="pilot", raw_verified=True)
        self.assertEqual(summary["status"], "COMPLETE_VERIFIED_PILOT")
        self.assertEqual(summary["received_runs"], 40)
        self.assertIsNone(summary["statistics"])
        self.assertEqual(summary["correlations"], [])

    def test_complete_main_uses_only_three_active_contrast_columns(self):
        cases, _ = analysis._cases()
        rows = [synthetic_row(identity, cases) for identity in sorted(analysis.expected_identities("main"))]
        with patch.object(analysis, "family_bca", return_value={"fixture": "not empirical statistics"}) as bootstrap:
            summary = analysis._summarize_rows(rows, raw_verified=True)
        self.assertEqual(summary["status"], "COMPLETE_VERIFIED_MAIN")
        self.assertEqual(len(bootstrap.call_args.args[0]), 10)
        self.assertTrue(all(len(vector) == 3 for vector in bootstrap.call_args.args[0]))
        self.assertEqual(len(summary["correlations"]), 7)
        self.assertTrue(all(item["status"] == "UNDEFINED" for item in summary["correlations"][:-1]))
        self.assertEqual(summary["correlations"][-1]["status"], "BLOCKED_LAMBDA_REPLICATION")

    def test_degenerate_and_small_family_bca_no_fake_intervals(self):
        for count in (4, 10):
            result = analysis.family_bca([[0.0, 0.0, 0.0]] * count, replicates=101)
            self.assertEqual(len(result["intervals"]), 4)
            self.assertTrue(all(item["status"] == "DESCRIPTIVE_ONLY" for item in result["intervals"][:3]))
            self.assertTrue(all(item["lower"] is None for item in result["intervals"]))
            self.assertEqual(result["intervals"][-1]["status"], "BLOCKED_LAMBDA_REPLICATION")

    def test_compact_corruption_not_pooled(self):
        cases, _ = analysis._cases()
        row = synthetic_row(sorted(analysis.expected_identities("main"))[0], cases)
        row["final_gap_percent"] += 1
        with self.assertRaises(ValueError):
            analysis.summarize_series([row])

    def test_declared_seed_cannot_be_relabelled(self):
        envelope = toy_envelope()
        envelope["seed"] += 1
        with self.assertRaises(ValueError):
            analysis.extract_run(envelope)

    def test_paired_initial_population_and_rng_checksums_must_match(self):
        cases, _ = analysis._cases()
        first = synthetic_row(("UC-s000", "bank", 85001, "classical"), cases)
        for key in ("initial_population_sha256", "initial_rng_sha256"):
            other = synthetic_row(("UC-s000", "bank", 85001, "adaptive_mutation"), cases)
            other[key] = "e" * 64
            with self.assertRaises(ValueError):
                analysis.summarize_series([first, other])

    def test_public_raw_envelope_entry_reverifies_before_summary(self):
        envelope = toy_envelope()
        envelope["log"]["candidates"][0]["profit"] += 1
        with self.assertRaises(ValueError):
            analysis.summarize_verified_envelopes([envelope])

    def test_raw_entry_accepts_stream_without_loading_all_source_logs(self):
        summary = analysis.summarize_verified_envelopes(iter(()), scope="pilot")
        self.assertEqual(summary["status"], "NOT_RUN")
        self.assertEqual(summary["raw_logs_replayed"], 0)
        with self.assertRaises(ValueError):
            analysis.summarize_verified_envelopes({"not": "a run stream"}, scope="pilot")

    def test_complete_compact_receipts_cannot_authorize_inference_or_rendering(self):
        cases, _ = analysis._cases()
        rows = [synthetic_row(identity, cases) for identity in sorted(analysis.expected_identities("pilot"))]
        with patch.object(analysis, "family_bca", side_effect=AssertionError("unverified inference")):
            summary = analysis.summarize_series(rows, scope="pilot")
        self.assertEqual(summary["status"], "COMPLETE_COMPACT_REQUIRES_RAW_VERIFICATION")
        self.assertIsNone(summary["statistics"])
        self.assertEqual(summary["correlations"], [])
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(render_report(summary, directory)["status"], "NOT_RENDERED")

    def test_scientific_binding_rejects_toy_problem_and_wrong_certified_mask(self):
        envelope = toy_envelope(start="cloned")
        with self.assertRaises(ValueError):
            analysis._bind_scientific_input(envelope)
        cases, _ = analysis._cases()
        case = cases["UC-s000"]
        envelope["seed"] = 86001
        envelope["optimum"] = case["payload"]["exact"]["confirmed_optimum"]
        envelope["center_profit"] = case["payload"]["certificate"]["center"]["profit"]
        envelope["log"]["problem"] = json.loads(analysis._registered_problem_bytes("UC-s000"))
        envelope["log"]["initial_masks"] = ["0" * 100] * 30
        with self.assertRaises(ValueError):
            analysis._bind_scientific_input(envelope)
        envelope["log"]["initial_masks"] = [case["payload"]["certificate"]["center"]["mask"]] * 30
        analysis._bind_scientific_input(envelope)

    def test_scientific_binding_reconstructs_exact_registered_bank(self):
        cases, _ = analysis._cases()
        case = cases["UC-s000"]
        envelope = {"task": "UC-s000", "start": "bank", "seed": 86001,
                    "optimum": case["payload"]["exact"]["confirmed_optimum"], "center_profit": None,
                    "log": {"problem": json.loads(analysis._registered_problem_bytes("UC-s000"))}}
        generator = analysis.np.random.Generator(analysis.np.random.PCG64(
            analysis.np.random.SeedSequence([86000, 86001, case["index"], 1, 0])))
        masks = ["0" * 100] + ["".join("1" if bit else "0" for bit in generator.random(100) < 0.5)
                              for _ in range(29)]
        envelope["log"]["initial_masks"] = masks
        analysis._bind_scientific_input(envelope)
        envelope["log"]["initial_masks"] = list(reversed(masks))
        with self.assertRaises(ValueError):
            analysis._bind_scientific_input(envelope)

    def test_scientific_rectangles_reject_software_fixture_provenance(self):
        cases, _ = analysis._cases()
        row = synthetic_row(sorted(analysis.expected_identities("main"))[0], cases)
        row["input_binding"] = "SOFTWARE_FIXTURE_NOT_KPLIB"
        with self.assertRaises(ValueError):
            analysis.summarize_series([row])

    def test_no_figures_created_from_not_run_or_incomplete_data(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "not-created"
            result = render_report(analysis.summarize_series([], scope="pilot"), output)
            self.assertEqual(result["status"], "NOT_RENDERED")
            self.assertFalse(output.exists())

    def test_synthetic_plot_software_smoke_has_tables_and_heatmaps(self):
        # Constructed stationary fixtures only.  These temporary PNGs are not
        # retained scientific figures and do not represent measured GA runs.
        cases, _ = analysis._cases()
        rows = [synthetic_row(identity, cases) for identity in sorted(analysis.expected_identities("pilot"))]
        summary = analysis._summarize_rows(rows, scope="pilot", raw_verified=True)
        # Guarantee a varying matrix as well as the constant activity tables.
        # The modification is confined to this explicitly synthetic render input.
        summary["family_cells"][0]["mean_final_gap_percent"] = 37.25
        with tempfile.TemporaryDirectory() as directory:
            result = render_report(summary, directory)
            self.assertEqual(result["status"], "RENDERED_VERIFIED_DATA")
            self.assertEqual(len(result["files"]), 3)
            for name in result["files"]:
                self.assertGreater((Path(directory) / name).stat().st_size, 0)
            with self.assertRaises(ValueError):
                render_report(summary, directory)

    def test_analysis_refuses_non_ci_execution(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                analysis.average_ranks([1, 2])


if __name__ == "__main__":
    unittest.main()

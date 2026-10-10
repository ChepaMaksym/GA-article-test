"""Small deterministic scientific fixtures; executed only by GitHub Actions."""

from copy import deepcopy
import hashlib
from types import SimpleNamespace
import unittest

import numpy as np

from studies.knapsack_parameters.ga_study.statistics import bca_family_intervals
from studies.knapsack_parameters.secondary_review.analysis import (
    CONTRAST_IDS, SOURCE_RUN, SOURCE_SHA, average_ranks, configuration_grid,
    descriptive_spearman, diagnostic_bca, equal_family_mean, family_values,
    independent_contrasts, summarize_group, validate_compact_row,
    validate_rectangle, validate_source_report,
)


def tiny_instance_case():
    instance = SimpleNamespace(instance_id="UC-s000", n=3, capacity=10,
                               weights=(6, 5, 5), profits=(10, 8, 8))
    case = {
        "instance_id": "UC-s000", "class_label": "UC", "family": "s000",
        "status": "ADMITTED_STRICT", "payload": {
            "exact": {"confirmed_optimum": 16},
            "certificate": {"center": {"profit": 10}, "strict": True},
        },
    }
    return instance, case


def compact_row(*, config_id="m1-c0p9-n30", seed=51001, profile="local", escape=False):
    config = configuration_grid()[config_id]
    size = config["population_size"]
    complete, remainder = divmod(5000 - size, size - 1)
    return {
        "instance_id": "UC-s000", "start_profile": profile, "repeat_seed": seed,
        **config, "best_mask": "011" if escape else "100",
        "best_profit": 16 if escape else 10, "best_weight": 10 if escape else 6,
        "best_request": 5000 if escape else 1,
        "escape_event": escape if profile == "local" else None,
        "first_escape_request": 5000 if escape else None,
        "censored": not escape if profile == "local" else None,
        "logical_requests": 5000, "physical_evaluations": 5000 - size,
        "invalid_request_count": 900, "duplicate_count": 1600,
        "complete_generations": complete, "terminal_partial": bool(remainder),
    }


class CompactWitnessTests(unittest.TestCase):
    def test_last_request_escape_and_nonevent_are_both_retained(self):
        instance, case = tiny_instance_case()
        for escaped in (False, True):
            row = compact_row(escape=escaped)
            key = validate_compact_row(row, instance, case)
            self.assertEqual(key, ("UC-s000", "local", 51001, "m1-c0p9-n30"))

    def test_original_bit_order_is_used(self):
        instance, case = tiny_instance_case()
        row = compact_row()
        row["best_mask"] = "001"
        with self.assertRaisesRegex(ValueError, "integer witness"):
            validate_compact_row(row, instance, case)

    def test_infeasible_witness_rejected(self):
        instance, case = tiny_instance_case()
        row = compact_row()
        row.update(best_mask="110", best_profit=18, best_weight=11)
        with self.assertRaisesRegex(ValueError, "integer witness"):
            validate_compact_row(row, instance, case)

    def test_bad_mask_and_missing_or_extra_fields_fail(self):
        instance, case = tiny_instance_case()
        for changes in ({"best_mask": "10"}, {"best_mask": "10A"}, {"unregistered": 1}):
            row = compact_row()
            row.update(changes)
            with self.assertRaises(ValueError):
                validate_compact_row(row, instance, case)
        row = compact_row()
        del row["best_weight"]
        with self.assertRaises(ValueError):
            validate_compact_row(row, instance, case)

    def test_bool_is_not_an_integer_counter(self):
        instance, case = tiny_instance_case()
        for field in ("best_profit", "best_weight", "best_request", "repeat_seed",
                      "population_size", "logical_requests", "physical_evaluations",
                      "invalid_request_count", "duplicate_count", "complete_generations"):
            row = compact_row()
            row[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_compact_row(row, instance, case)

    def test_accounting_and_partial_generation(self):
        instance, case = tiny_instance_case()
        for changes in ({"physical_evaluations": 5000}, {"logical_requests": 4999},
                        {"terminal_partial": False}, {"complete_generations": 172},
                        {"invalid_request_count": -1}, {"duplicate_count": 5001}):
            row = compact_row()
            row.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_compact_row(row, instance, case)

    def test_parameters_and_seeds_are_not_inferred_from_observations(self):
        instance, case = tiny_instance_case()
        for changes in ({"repeat_seed": 52001}, {"configuration_id": "m2-c0p9-n30"},
                        {"mutation_numerator": .5}, {"crossover_probability": .5},
                        {"start_profile": "replacement"}):
            row = compact_row()
            row.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_compact_row(row, instance, case)

    def test_nonevent_cannot_have_improved_record_or_exit_time(self):
        instance, case = tiny_instance_case()
        for changes in ({"first_escape_request": 5000}, {"censored": False},
                        {"best_mask": "011", "best_profit": 16, "best_weight": 10}):
            row = compact_row()
            row.update(changes)
            with self.assertRaises(ValueError):
                validate_compact_row(row, instance, case)

    def test_random_profile_has_no_local_endpoint(self):
        instance, case = tiny_instance_case()
        row = compact_row(profile="random")
        validate_compact_row(row, instance, case)
        row["escape_event"] = False
        with self.assertRaisesRegex(ValueError, "random result"):
            validate_compact_row(row, instance, case)

    def test_global_center_cannot_supply_local_rows(self):
        instance, case = tiny_instance_case()
        case["status"] = "NOT_ADMITTED_GLOBAL"
        with self.assertRaisesRegex(ValueError, "nonadmitted"):
            validate_compact_row(compact_row(), instance, case)

    def test_complete_rectangle_and_duplicate_or_missing_identity(self):
        instance, case = tiny_instance_case()
        cases = {instance.instance_id: case}
        instances = {instance.instance_id: instance}
        rows = [compact_row(config_id=config, seed=seed, profile=profile)
                for config in configuration_grid() for seed in range(51001, 51031)
                for profile in ("random", "local")]
        counts = validate_rectangle(rows, instances, cases)
        self.assertEqual(counts["runs"], 1620)
        self.assertEqual(counts["censored_nonevents"], 810)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_rectangle(rows[:-1], instances, cases)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_rectangle(rows + [deepcopy(rows[0])], instances, cases)

    def test_mixed_source_sha_and_source_run_fail(self):
        report = {
            "implementation_commit_sha": SOURCE_SHA,
            "protocol_id": "GA-KNAPSACK-PARAMETERS-MAIN-V1", "status": "COMPLETE_VERIFIED_MAIN",
            "runs": 35640, "random_runs": 24300, "local_runs": 11340,
            "logical_requests": 178200000, "source_job_count": 90,
            "provenance": {"implementation_commit_sha": SOURCE_SHA,
                           "sources": [{"run_id": SOURCE_RUN} for _ in range(90)]},
        }
        validate_source_report(report)
        changed = deepcopy(report)
        changed["implementation_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "SHA"):
            validate_source_report(changed)
        changed = deepcopy(report)
        changed["provenance"]["sources"][20]["run_id"] += 1
        with self.assertRaisesRegex(ValueError, "run provenance"):
            validate_source_report(changed)


class EstimandTests(unittest.TestCase):
    def test_seed_then_instance_then_family_weighting(self):
        # Two classes in s000, one in s001, unequal seed counts in this fixture.
        rows = [{"instance_id": "UC-s000", "value": 0.0},
                {"instance_id": "UC-s000", "value": 1.0},
                {"instance_id": "WC-s000", "value": 1.0},
                {"instance_id": "UC-s001", "value": 0.0}]
        cases = {"UC-s000": {"family": "s000"}, "WC-s000": {"family": "s000"},
                 "UC-s001": {"family": "s001"}}
        families = family_values(rows, cases, lambda row: row["value"])
        self.assertEqual(families, {"s000": .75, "s001": 0.0})
        self.assertEqual(equal_family_mean(rows, cases, lambda row: row["value"]), .375)

    def test_raw_frequency_is_not_the_family_estimand(self):
        _, case = tiny_instance_case()
        cases = {"UC-s000": case, "WC-s000": {**case, "instance_id": "WC-s000"},
                 "UC-s001": {**case, "instance_id": "UC-s001", "family": "s001"}}
        rows = []
        for name, escaped in (("UC-s000", True), ("WC-s000", True), ("UC-s001", False)):
            row = compact_row(escape=escaped)
            row["instance_id"] = name
            rows.append(row)
        result = summarize_group(rows, cases)
        self.assertEqual(result["escape_events"], 2)
        self.assertEqual(result["censored_nonevents"], 1)
        self.assertEqual(result["escape_rate_raw"], 2 / 3)
        self.assertEqual(result["escape_rate_equal_family"], .5)
        self.assertEqual(result["mean_restricted_escape_time_equal_family"], 5000)
        self.assertEqual(result["events_at_limit"], 2)

    def test_four_registered_contrasts_hand_fixture(self):
        rates = np.asarray([[[.1 + .1*m + .05*c + .02*p + .03*m*c
                              for p in range(3)] for c in range(3)] for m in range(3)])
        np.testing.assert_allclose(independent_contrasts(rates), [.13, .16, .04, .06], atol=1e-14, rtol=0)

    def test_invalid_rates_fail(self):
        for rates in (np.zeros(27), np.full((3, 3, 3), np.nan), np.full((3, 3, 3), 1.1)):
            with self.assertRaises(ValueError):
                independent_contrasts(rates)


class DiagnosticBootstrapTests(unittest.TestCase):
    def test_independent_bca_matches_unchanged_original_on_same_stream(self):
        values = np.asarray([[a, 2*a, -a, a*a] for a in [-.1, 0, .05, .1, .15, .2, .3, .4, .5, .6]])
        original = bca_family_intervals(values, replicates=2000, seed=51031)
        rebuilt = diagnostic_bca(values, replicates=2000, seed_entropy=[51031])
        self.assertEqual(original["resample_index_sha256"], rebuilt["resample_index_sha256"])
        for old, new in zip(original["intervals"], rebuilt["intervals"], strict=True):
            for field in ("estimate", "lower", "upper", "bias_fraction", "bias_correction",
                          "acceleration", "adjusted_quantiles"):
                self.assertEqual(old.get(field), new.get(field))
            self.assertFalse(new["positive_effect_supported"])
            self.assertFalse(new["negative_effect_supported"])
        self.assertFalse(rebuilt["superiority_tests"])

    def test_loo_exact_seed_sequence_and_omitted_index(self):
        values = np.arange(36).reshape(9, 4) / 100
        first = diagnostic_bca(values, replicates=100, seed_entropy=[53001, 0])
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([53001, 0])))
        indices = rng.integers(0, 9, size=(100, 9))
        expected = hashlib.sha256(indices.astype("<i8", copy=False).tobytes(order="C")).hexdigest()
        self.assertEqual(first["resample_index_sha256"], expected)
        self.assertEqual(first, diagnostic_bca(values, replicates=100, seed_entropy=[53001, 0]))
        second = diagnostic_bca(values, replicates=100, seed_entropy=[53001, 1])
        self.assertNotEqual(first["resample_index_sha256"], second["resample_index_sha256"])

    def test_flat_and_fewer_than_five_have_no_fallback(self):
        result = diagnostic_bca(np.zeros((10, 4)), replicates=100, seed_entropy=[53001, 0])
        self.assertTrue(all(row["lower"] is None and row["upper"] is None for row in result["intervals"]))
        self.assertEqual({row["reason"] for row in result["intervals"]}, {"degenerate_bootstrap_distribution"})
        result = diagnostic_bca(np.zeros((4, 4)), replicates=100, seed_entropy=[53001, 0])
        self.assertIsNone(result["resample_index_sha256"])
        self.assertEqual({row["reason"] for row in result["intervals"]}, {"fewer_than_five_families"})

    def test_bias_correction_half_weights_ties(self):
        values = np.asarray([[value] * 4 for value in (0, .25, .5, .75, 1)])
        result = diagnostic_bca(values, replicates=1000, seed_entropy=[53001, 9])
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([53001, 9])))
        samples = values[rng.integers(0, 5, size=(1000, 5)), 0].mean(axis=1)
        fraction = (np.count_nonzero(samples < .5) + .5*np.count_nonzero(samples == .5)) / 1000
        self.assertEqual(result["intervals"][0]["bias_fraction"], fraction)
        self.assertEqual([row["contrast_id"] for row in result["intervals"]], list(CONTRAST_IDS))


class CorrelationTests(unittest.TestCase):
    def test_average_ranks_in_original_order(self):
        np.testing.assert_array_equal(average_ranks([3, 1, 1, 2]), [4, 1.5, 1.5, 3])

    def test_tied_spearman_hand_result(self):
        result = descriptive_spearman([1, 1, 3], [10, 20, 30])
        self.assertAlmostEqual(result["rho"], np.sqrt(3) / 2)
        self.assertEqual(result["status"], "DESCRIPTIVE")
        self.assertIsNone(result["p_value"])
        self.assertFalse(result["causal_claim"])

    def test_constant_series_is_undefined_not_zero(self):
        for x, y in (([1, 1, 1], [2, 3, 4]), ([2, 3, 4], [1, 1, 1])):
            result = descriptive_spearman(x, y)
            self.assertEqual(result["status"], "UNDEFINED")
            self.assertIsNone(result["rho"])
            self.assertEqual(result["reason"], "constant_series")

    def test_opposite_order_and_identical_ties(self):
        self.assertEqual(descriptive_spearman([1, 2, 3], [3, 2, 1])["rho"], -1)
        self.assertEqual(descriptive_spearman([1, 1, 3], [1, 1, 3])["rho"], 1)

    def test_invalid_correlation_input_fail_closed(self):
        for x, y in (([1], [1]), ([1, 2], [1]), ([1, np.nan], [2, 3]), ([[1, 2]], [[2, 3]])):
            with self.assertRaises(ValueError):
                descriptive_spearman(x, y)


if __name__ == "__main__":
    unittest.main()

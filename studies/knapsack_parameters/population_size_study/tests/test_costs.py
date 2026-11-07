"""CI-only resource-forecast evidence and accounting fixtures."""
from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.population_size_study.costs import build_quotes


def evidence():
    cases, workers = [], []
    for n in (100, 200, 500):
        for kind in ("UC", "WC", "SC"):
            task = f"n{n}-{kind}"
            cases.append({"n": n, "class_label": kind, "task_id": task,
                "timing_ns": {"certification": 2_000_000_000, "bank_preparation": 1_000_000_000,
                              "bank_verification": 1_000_000_000, "bank_serialization": 1_000_000_000},
                "files": {name: {"bytes": 100} for name in ("problem", "certificate", "bank", "bank_metadata")},
                "physical_preparation_evaluations": 25000, "independent_verification_evaluations": 25000})
            records = [{"identity": {"task_id": task, "n": n, "class_label": kind,
                                     "mu": mu, "total_evaluations": 50000},
                        "verification_status": "VERIFIED", "file": {"bytes": 1000}, "peak_rss_bytes": 2000,
                        "timing_ns": {"core": {"total": 1_000_000_000}, "verification": 1_000_000_000,
                                      "observations": 1_000_000_000, "serialization": 1_000_000_000}}
                       for mu in (2, 25000)]
            workers.append({"schema": "population-size-pilot-worker-v1", "status": "VERIFIED_TECHNICAL_WORKER",
                            "task_id": task, "input_validation_ns": 2_000_000_000, "peak_rss_bytes": 2000,
                            "records": records})
    return {"schema": "population-size-pilot-preparation-v1", "status": "PREPARED_CERTIFIED_PILOT_INPUTS",
            "cases": cases}, workers


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Cost fixtures run only in GitHub Actions")
class ProspectiveCostTests(unittest.TestCase):
    def test_validation_counts_include_initialization_and_shared_bank_costs(self):
        quote = build_quotes(*evidence())["validation"]
        self.assertEqual(quote["physical_runs_upper"], 8100)
        self.assertEqual(quote["logical_total_evaluations_upper"], 405_000_000)
        self.assertEqual(quote["distinct_initial_banks_upper"], 2700)
        for row in quote["per_dimension"]:
            self.assertEqual(row["physical_bank_preparation_evaluations_upper"], 22_500_000)
            self.assertEqual(row["independent_bank_verification_evaluations_upper"], 22_500_000)
            self.assertEqual(row["exactly_certified_tasks"], 30)

    def test_tuning_scenarios_are_proposals_and_do_not_authorize_runs(self):
        quote = build_quotes(*evidence())
        self.assertFalse(quote["execution_authorized"])
        self.assertFalse(quote["population_selected"])
        self.assertEqual([item["physical_runs_upper"] for item in quote["tuning_options"]], [3600, 4500, 6300])
        for option in quote["tuning_options"]:
            self.assertEqual(option["status"], "PROPOSED_NOT_AUTHORIZED")
            self.assertEqual(option["design_proposal"]["common_finalist_banks_per_dimension"], 300)

    def test_quotes_are_invariant_to_worker_and_case_order(self):
        registry, workers = evidence()
        original = build_quotes(registry, workers)
        registry["cases"].reverse()
        workers.reverse()
        # Only the presentation order of raw measurements may differ.
        reordered = build_quotes(registry, workers)
        self.assertEqual(original["validation"], reordered["validation"])
        self.assertEqual(original["tuning_options"], reordered["tuning_options"])

    def test_missing_duplicate_unverified_and_mixed_evidence_is_rejected(self):
        for modification in ("missing", "duplicate", "unverified", "mixed", "missing_boundary"):
            registry, workers = evidence()
            if modification == "missing":
                workers.pop()
            elif modification == "duplicate":
                workers[-1] = deepcopy(workers[0])
            elif modification == "unverified":
                workers[0]["records"][0]["verification_status"] = "FAILED"
            elif modification == "mixed":
                workers[0]["records"][0]["identity"]["n"] = 500
            else:
                workers[0]["records"][1]["identity"]["mu"] = 2
            with self.subTest(modification=modification), self.assertRaises(ValueError):
                build_quotes(registry, workers)

    def test_bad_numeric_timings_are_not_silently_ignored(self):
        for value in (None, True, -1, 2.5):
            registry, workers = evidence()
            workers[0]["records"][0]["timing_ns"]["verification"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_quotes(registry, workers)

    def test_slowest_observed_boundary_drives_forecast_without_quality_values(self):
        registry, workers = evidence()
        baseline = build_quotes(registry, workers)
        workers[0]["records"][1]["timing_ns"]["core"]["total"] = 20_000_000_000
        workers[0]["records"][1]["file"]["bytes"] = 2000
        changed = build_quotes(registry, workers)
        self.assertGreater(changed["validation"]["runner_minutes_proposed_ceiling"],
                           baseline["validation"]["runner_minutes_proposed_ceiling"])
        self.assertGreater(changed["validation"]["compressed_bytes_proposed_ceiling"],
                           baseline["validation"]["compressed_bytes_proposed_ceiling"])
        self.assertEqual(changed["validation"]["per_dimension"][1:], baseline["validation"]["per_dimension"][1:])

    def test_shared_input_cost_is_attributed_once_per_technical_pair(self):
        registry, workers = evidence()
        quote = build_quotes(registry, workers)
        for base in quote["measurement_bases"]:
            self.assertEqual(base["max_attributed_run_ns"], 5_000_000_000)
            self.assertEqual(base["max_prepared_bank_ns"], 3_000_000_000)

    def test_cost_model_does_not_modify_evidence(self):
        registry, workers = evidence()
        before = deepcopy((registry, workers))
        build_quotes(registry, workers)
        self.assertEqual((registry, workers), before)

    def test_cost_calculation_is_ci_only(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(ValueError, "GitHub Actions"):
                build_quotes(*evidence())

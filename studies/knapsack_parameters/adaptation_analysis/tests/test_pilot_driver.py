"""CI-only transport/control fixtures; fake journals never run KPLIB search.

Search, authorization and raw-series analysis are deliberately mocked here.
The existing independent kernel tests exercise real small software examples.
These tests must not be described as scientific pilot observations.
"""
from copy import deepcopy
import gzip
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.adaptation_analysis import pilot_driver as d
from studies.knapsack_parameters.adaptation_analysis import authority as a


def provenance():
    return {"protocol_id": "GA-KNAPSACK-ADAPTATION-ANALYSIS-V1",
            "pilot_protocol_id": d.PILOT_PROTOCOL, "pilot_registration_sha": "d" * 40,
            "implementation_sha": "a" * 40,
            "source_manifest": {"files": [], "sha256": "b" * 64}, "run_id": 12345, "run_attempt": 1}


def problem():
    return {"n": 3, "weights": [6, 5, 5], "profits": [10, 8, 8], "capacity": 10}


def score(mask):
    instance = problem()
    weight = sum(instance["weights"][i] for i, bit in enumerate(mask) if bit == "1")
    profit = sum(instance["profits"][i] for i, bit in enumerate(mask) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= 10}


def banks():
    result = []
    for task_index, task in enumerate(d.TASKS):
        for start_index, start in enumerate(d.STARTS):
            masks = ["100"] * 30 if start == "cloned" else ["000"] + ["100"] * 29
            result.append({**provenance(), "task": task, "task_index": task_index,
                "start": start, "start_index": start_index, "search_seed": 86001,
                "preparation_seed": 86000, "problem": problem(),
                "source_identity": {"path": task + ".fixture", "bytes": 1, "sha256": "c" * 64},
                "initial_masks": masks, "initial_scores": [score(mask) for mask in masks],
                "physical_preparation_evaluations": len(set(masks)),
                "independent_preparation_checks": 30})
    return result


def fake_profile(instance, masks, scores, method, seed, task_index, start_index, budget):
    # This is intentionally a TRANSPORT fixture, not a valid independent GA
    # journal. The analysis/replay calls are separately mocked in these tests.
    summary = {"new_calls": 5000, "physical_evaluations": 5000,
               "known_score_validation_evaluations": 30, "best_profit": 10,
               "best_mask": "100", "best_call": 0}
    log = {"method": method, "problem": deepcopy(instance), "initial_masks": list(masks),
           "initial_scores": deepcopy(scores), "rng_initial": {}, "budget": budget,
           "candidates": [], "generations": [], "summary": summary}
    return {"log": log, "verification": {"verification_status": "VERIFIED",
            "summary": deepcopy(summary), "independent_score_checks": 5030}}


def source_task(task):
    kind = "GLOBAL_CENTER" if task == "SC-s000" else "ADMITTED_PLATEAU_LOCAL" if task == "SC-s005" else "ADMITTED_STRICT_LOCAL"
    return problem(), {"status": kind, "exact": {"confirmed_optimum": 16},
                       "certificate": {"center": {"profit": 10, "mask": "100"}}}, {
        "path": task + ".fixture", "bytes": 1, "sha256": "c" * 64}


class PilotDriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("The registered checks execute only in GitHub Actions")

    def test_bank_rectangle_and_stale_seeds_are_rejected(self):
        self.assertEqual(len(d._bank_map(banks())), 8)
        for changed in (banks()[:-1], banks()[:-1] + [banks()[0]]):
            with self.assertRaises(ValueError):
                d._bank_map(changed)
        changed = banks()
        changed[0]["search_seed"] = 7
        with self.assertRaises(ValueError):
            d._bank_map(changed)

    def test_preparation_eight_banks_no_search_and_real_file_hashes(self):
        def initial(instance, case, task_index, start, search_seed, preparation_seed):
            masks = ["100"] * 30 if start == "cloned" else ["000"] + ["100"] * 29
            return {"initial_masks": masks, "initial_scores": [score(mask) for mask in masks],
                    "initialization_before": {}, "initialization_after": {},
                    "logical_initial_positions": 30,
                    "physical_preparation_evaluations": len(set(masks)), "independent_preparation_checks": 30}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(d.p, "check_permit", return_value=provenance()), \
             patch.object(d.p, "validated_tests", return_value=provenance()), \
             patch("studies.knapsack_parameters.mutation_population.driver.source_task", side_effect=source_task), \
             patch("studies.knapsack_parameters.mutation_population.driver.initial_bank", side_effect=initial), \
             patch("studies.knapsack_parameters.adaptation_analysis.comparison.run_profile",
                   side_effect=AssertionError("preparation must not search")):
            registry = d.prepare(Path(directory) / "prepared", Path(directory) / "permit")
            self.assertEqual(registry["initial_conditions"], 8)
            self.assertEqual(registry["scientific_search_calls"], 0)
            self.assertEqual(registry["physical_preparation_evaluations"], 12)
            self.assertEqual(registry["independent_preparation_checks"], 240)
            a.verify_manifest(Path(directory) / "prepared")
            for row in registry["banks"]:
                self.assertEqual(a.identity(Path(directory) / "prepared" / row["path"]),
                                 {"bytes": row["bytes"], "sha256": row["sha256"]})

    def test_worker_writes_five_sequential_full_packets_and_progress_manifest(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(d.p, "check_permit", return_value=provenance()), \
             patch.object(d.p, "validated_tests", return_value=provenance()), \
             patch.object(d.p, "load_banks", return_value=banks()), \
             patch("studies.knapsack_parameters.adaptation_analysis.comparison.run_profile", side_effect=fake_profile) as run:
            output = Path(directory) / "worker"
            index = d.run_one_condition(output, "WC-s001", "cloned", Path(directory) / "permit")
            self.assertEqual(index["status"], "COMPLETE_CONDITION")
            self.assertEqual([row["method"] for row in index["results"]], list(d.METHODS))
            self.assertEqual(run.call_count, 5)
            self.assertEqual(index["bank_validation_independent_score_checks"], 240)
            a.verify_manifest(output)
            for row in index["results"]:
                with gzip.open(output / row["path"], "rt", encoding="utf-8") as stream:
                    packet = json.load(stream)
                self.assertEqual(packet["log"]["budget"], 5000)
                self.assertEqual(packet["method"], row["method"])
                self.assertEqual(packet["bank_sha256"], index["bank_sha256"])
                self.assertEqual(d._json_hash(packet["log"]), row["log_sha256"])

    def test_worker_failure_keeps_completed_profiles_and_no_budget_shortening(self):
        counter = 0
        def fail_third(*args, **kwargs):
            nonlocal counter
            counter += 1
            if counter == 3:
                raise RuntimeError("declared fixture failure")
            return fake_profile(*args, **kwargs)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(d.p, "check_permit", return_value=provenance()), \
             patch.object(d.p, "validated_tests", return_value=provenance()), \
             patch.object(d.p, "load_banks", return_value=banks()), \
             patch("studies.knapsack_parameters.adaptation_analysis.comparison.run_profile", side_effect=fail_third):
            output = Path(directory) / "worker"
            index = d.run_one_condition(output, "WC-s001", "bank")
            self.assertEqual(index["status"], "INCOMPLETE")
            self.assertEqual(len(index["results"]), 2)
            self.assertEqual(index["active_method"], "adaptive_crossover")
            self.assertEqual(index["failures"][0]["error_type"], "RuntimeError")
            self.assertTrue(all(row["summary"]["new_calls"] == 5000 for row in index["results"]))
            a.verify_manifest(output)

    def test_capped_stream_refuses_bytes_before_exceeding_limit(self):
        raw = io.BytesIO()
        writer = d._CappedWriter(raw, 4)
        self.assertEqual(writer.write(b"abcd"), 4)
        with self.assertRaises(ValueError):
            writer.write(b"e")
        self.assertEqual(raw.getvalue(), b"abcd")

    def test_missing_permit_blocks_before_banks_or_search(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(d.p, "check_permit", side_effect=ValueError("BLOCKED")), \
             patch.object(d.p, "load_banks", side_effect=AssertionError("banks must not load")), \
             patch("studies.knapsack_parameters.adaptation_analysis.comparison.run_profile",
                   side_effect=AssertionError("search must not start")):
            with self.assertRaisesRegex(ValueError, "BLOCKED"):
                d.run_one_condition(Path(directory), "UC-s000", "bank")

    def _aggregate_fixture(self, root, corrupt=None):
        artifacts = root / "workers"
        for task in d.TASKS:
            for start in d.STARTS:
                d.run_one_condition(artifacts / (task + "-" + start), task, start)
        if corrupt == "foreign_sha":
            condition = artifacts / "SC-s000-bank"
            index = a.read_json(condition / "condition_index.json")
            index["implementation_sha"] = "e" * 40
            a.write_json(condition / "condition_index.json", index)
            a.write_manifest(condition)
        elif corrupt == "checksum":
            condition = artifacts / "SC-s000-bank"
            index = a.read_json(condition / "condition_index.json")
            with (condition / index["results"][0]["path"]).open("ab") as stream:
                stream.write(b"corrupted")
        return artifacts

    def test_aggregate_requires_forty_raw_packets_pairings_and_no_compact_promotion(self):
        received = []
        def replay(envelopes, scope):
            self.assertEqual(scope, "pilot")
            received.extend((row["task"], row["start"], row["method"]) for row in envelopes)
            return {"schema": "ga-adaptation-series-summary-v1", "scope": "pilot",
                    "status": "COMPLETE_VERIFIED_PILOT", "method_summaries": [], "family_cells": []}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(d.p, "check_permit", return_value=provenance()), \
             patch.object(d.p, "validated_tests", return_value=provenance()), \
             patch.object(d.p, "load_banks", return_value=banks()), \
             patch("studies.knapsack_parameters.adaptation_analysis.comparison.run_profile", side_effect=fake_profile), \
             patch("studies.knapsack_parameters.mutation_population.driver.source_task", side_effect=source_task), \
             patch.object(d, "_first_generation", return_value={}), \
             patch.object(d, "_trajectory", return_value={}), \
             patch.object(d, "_render_trajectory", return_value=None), \
             patch("studies.knapsack_parameters.adaptation_analysis.analysis.summarize_verified_envelopes", side_effect=replay), \
             patch("studies.knapsack_parameters.adaptation_analysis.plots.render_report", return_value={"status": "RENDERED", "files": []}), \
             patch("studies.knapsack_parameters.mutation_population.search.verify_paired_first_generation", return_value={"status": "VERIFIED"}), \
             patch("studies.knapsack_parameters.adaptation_analysis.comparison.verify_crossover_first_generation", return_value={"status": "VERIFIED"}), \
             patch("studies.knapsack_parameters.bntga_selection.knapsack_comparison.verify_first_generation", return_value={"status": "VERIFIED"}):
            root = Path(directory)
            artifacts = self._aggregate_fixture(root)
            result = d.aggregate(root / "aggregate", artifacts)
            self.assertEqual(result["status"], "COMPLETE_TECHNICAL_PILOT")
            self.assertEqual(len(received), 40)
            self.assertEqual(len(set(received)), 40)
            self.assertEqual(len(result["paired_checks"]), 8)
            self.assertEqual(result["new_search_evaluations_verified"], 200000)
            self.assertEqual(result["cost_accounting"]["worker_bank_validation_independent_score_checks"], 1920)
            self.assertEqual(result["cost_accounting"]["aggregation_bank_validation_independent_score_checks"], 240)
            self.assertEqual(result["cost_accounting"]["aggregation_independent_operator_score_checks_completed"], 201200)
            self.assertEqual(result["cost_accounting"]["aggregation_independent_metric_score_checks_completed"], 201200)
            self.assertFalse(result["bootstrap_performed"])
            self.assertFalse(result["correlations_performed"])
            a.verify_manifest(root / "aggregate")

    def test_corrupt_or_foreign_artifact_cannot_become_complete(self):
        def replay(envelopes, scope):
            list(envelopes)
            # Even a false compact/full status cannot bypass source coverage.
            return {"schema": "ga-adaptation-series-summary-v1", "scope": "pilot",
                    "status": "COMPLETE_VERIFIED_PILOT", "method_summaries": [], "family_cells": []}
        for corruption in ("foreign_sha", "checksum"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as directory, \
                 patch.object(d.p, "check_permit", return_value=provenance()), \
                 patch.object(d.p, "validated_tests", return_value=provenance()), \
                 patch.object(d.p, "load_banks", return_value=banks()), \
                 patch("studies.knapsack_parameters.adaptation_analysis.comparison.run_profile", side_effect=fake_profile), \
                 patch("studies.knapsack_parameters.mutation_population.driver.source_task", side_effect=source_task), \
                 patch.object(d, "_first_generation", return_value={}), \
                 patch.object(d, "_trajectory", return_value={}), \
                 patch("studies.knapsack_parameters.adaptation_analysis.analysis.summarize_verified_envelopes", side_effect=replay), \
                 patch("studies.knapsack_parameters.adaptation_analysis.plots.render_report", side_effect=AssertionError("incomplete data must not plot")), \
                 patch("studies.knapsack_parameters.mutation_population.search.verify_paired_first_generation", return_value={"status": "VERIFIED"}), \
                 patch("studies.knapsack_parameters.adaptation_analysis.comparison.verify_crossover_first_generation", return_value={"status": "VERIFIED"}), \
                 patch("studies.knapsack_parameters.bntga_selection.knapsack_comparison.verify_first_generation", return_value={"status": "VERIFIED"}):
                root = Path(directory)
                artifacts = self._aggregate_fixture(root, corruption)
                result = d.aggregate(root / "aggregate", artifacts)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertTrue(result["errors"])
                self.assertEqual(result["rendering"]["status"], "NOT_RENDERED")
                a.verify_manifest(root / "aggregate")


if __name__ == "__main__":
    unittest.main()

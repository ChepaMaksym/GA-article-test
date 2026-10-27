"""Synthetic stored-worker fixtures only; no GA, scoring, replay or network."""
from copy import deepcopy
import gzip
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ...mutation_refinement import authority as a
from ...mutation_refinement_recovery.aggregate import aggregate_saved


SOURCE = {"protocol_id": "GA-KNAPSACK-MUTATION-REFINEMENT-V1",
          "registration_sha": "e" * 40, "implementation_sha": "a" * 40,
          "source_manifest": {"files": [], "sha256": "f" * 64},
          "run_id": 40516606272, "run_attempt": 1}
RECOVERY = {"protocol_id": "instructional-recovery", "run_id": 2,
            "implementation_sha": "b" * 40, "run_attempt": 1}


def registry(module):
    path = module / "inputs/pilot/bank_registry.json"
    a.write_json(path, {**SOURCE, "schema": "mutation-refinement-bank-registry-v1",
                       "stage": "pilot", "conditions": 8, "pilot_runs": 40,
                       "new_search_calls": 0, "new_exact_solves": 0,
                       "physical_preparation_evaluations": 124, "logical_initial_positions": 240,
                       "existing_center_validation_score_checks": 4})


def worker_fixture(root, task):
    """Inert files imitate producer receipts; they are not search journals."""
    directory = root / task
    records = []
    for start in a.STARTS:
        for method in a.METHODS:
            name = f"{task}-{start}-97999-{method}"
            path = directory / "logs" / (name + ".json.gz")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(gzip.compress(a.canonical({"instructional_inert_fixture": name}), mtime=0))
            record = {"task": task, "start": start, "seed": 97999, "method": method,
                      "log_path": "logs/" + path.name, "log_identity": a.identity(path),
                      "new_search_evaluations": 5000,
                      "engine_initial_score_validation_evaluations": 30,
                      "engine_premutation_observational_evaluations": 0,
                      "independent_replay_score_checks": 10030,
                      "independent_replay_initial_score_checks": 30,
                      "independent_replay_final_score_checks": 5000,
                      "independent_replay_premutation_score_checks": 5000,
                      "summary": {"new_calls": 5000, "physical_evaluations": 5000,
                                  "known_score_validation_evaluations": 30},
                      "timings": {"search_wall_ns": 1000000000, "serialization_ns": 100000000,
                                  "verification_ns": 1000000000}}
            records.append(record)
    row = {**SOURCE, "schema": "mutation-refinement-worker-v1", "stage": "pilot", "worker": task,
           "complete": True, "errors": [], "expected_runs": 10, "verified_runs": 10, "records": records,
           "compressed_journal_bytes": sum(r["log_identity"]["bytes"] for r in records),
           "worker_ns": 30000000000, "bank_validation_ns": 1000,
           "bank_validation_initial_score_checks": 60, "existing_center_validation_score_checks": 2}
    save_worker(directory, row)
    return directory


def save_worker(directory, row):
    for record in row["records"]:
        basename = Path(record["log_path"]).name.removesuffix(".json.gz")
        a.write_json(directory / "metadata" / (basename + ".json"),
                     {**SOURCE, "verification_status": "VERIFIED", "record": record})
    a.write_json(directory / "worker_summary.json", row)
    a.write_manifest(directory)


class SavedAggregationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.module = self.root / "frozen-module"
        registry(self.module)
        self.workers = self.root / "workers"
        self.directories = [worker_fixture(self.workers, task) for task in a.PILOT_TASKS]
        self.output = self.root / "output"
        self.module_patch = patch.object(a, "MODULE", self.module)
        self.module_patch.start()

    def tearDown(self):
        self.module_patch.stop()
        self.temporary.cleanup()

    def run_recovery(self):
        with patch.object(a, "api", side_effect=AssertionError("No network in saved aggregation")), \
             patch.object(a, "check_permit", side_effect=AssertionError("No search permit in saved aggregation")):
            return aggregate_saved(self.workers, self.output, SOURCE, RECOVERY)

    def assertBlocked(self):
        with self.assertRaises(ValueError):
            self.run_recovery()
        audit = a.read_json(self.output / "audit_status.json")
        self.assertFalse(audit["complete"])
        self.assertFalse(audit["new_search_performed_during_aggregation"])
        self.assertEqual(audit["run_id"], SOURCE["run_id"])
        self.assertFalse((self.output / "pilot_summary.json").exists())
        self.assertFalse((self.output / "cost_review.json").exists())
        a.verify_manifest(self.output)

    def test_full_forty_run_rectangle_preserves_source_and_separate_recovery(self):
        summary = self.run_recovery()
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["verified_runs"], 40)
        self.assertEqual(len(summary["records"]), 40)
        self.assertEqual(summary["run_id"], SOURCE["run_id"])
        self.assertEqual(summary["implementation_sha"], SOURCE["implementation_sha"])
        self.assertEqual(summary["recovery_provenance"], RECOVERY)
        self.assertFalse(summary["new_search_performed_during_aggregation"])
        costs = summary["costs"]
        self.assertEqual(costs["new_search_evaluations"], 200000)
        self.assertEqual(costs["initial_preparation_physical_evaluations"], 124)
        self.assertEqual(costs["initial_preparation_logical_positions"], 240)
        self.assertEqual(costs["engine_premutation_observational_evaluations"], 0)
        self.assertEqual(costs["independent_replay_score_checks"],
                         costs["independent_replay_initial_score_checks"] +
                         costs["independent_replay_final_score_checks"] +
                         costs["independent_replay_premutation_score_checks"])
        forecast = a.read_json(self.output / "cost_review.json")
        self.assertTrue(forecast["forecast_only"])
        self.assertFalse(forecast["calibration_authorized"])
        self.assertFalse(forecast["main_authorized"])
        self.assertEqual(forecast["source_provenance"], SOURCE)
        self.assertEqual(forecast["recovery_provenance"], RECOVERY)
        a.verify_manifest(self.output)

    def test_mixed_worker_source_sha_is_blocked(self):
        directory = self.directories[0]
        row = a.read_json(directory / "worker_summary.json")
        row["implementation_sha"] = "c" * 40
        save_worker(directory, row)
        self.assertBlocked()

    def test_duplicate_condition_is_blocked_even_with_valid_file_manifest(self):
        directory = self.directories[0]
        row = a.read_json(directory / "worker_summary.json")
        row["records"][1] = deepcopy(row["records"][0])
        save_worker(directory, row)
        self.assertBlocked()

    def test_tampered_full_journal_is_blocked(self):
        path = next((self.directories[0] / "logs").glob("*.gz"))
        path.write_bytes(path.read_bytes() + b"tampered")
        self.assertBlocked()

    def test_incomplete_worker_is_retained_without_cost_forecast(self):
        directory = self.directories[0]
        row = a.read_json(directory / "worker_summary.json")
        row["complete"] = False
        row["verified_runs"] = 9
        row["records"].pop()
        save_worker(directory, row)
        self.assertBlocked()

    def test_false_engine_premutation_count_is_blocked_with_self_consistent_metadata(self):
        directory = self.directories[0]
        row = a.read_json(directory / "worker_summary.json")
        row["records"][0]["engine_premutation_observational_evaluations"] = 5000
        save_worker(directory, row)
        self.assertBlocked()

    def test_false_replay_split_is_blocked_with_self_consistent_metadata(self):
        directory = self.directories[0]
        row = a.read_json(directory / "worker_summary.json")
        row["records"][0]["independent_replay_premutation_score_checks"] = 0
        save_worker(directory, row)
        self.assertBlocked()

    def test_mixed_replay_source_sha_is_blocked(self):
        directory = self.directories[0]
        path = next((directory / "metadata").glob("*.json"))
        row = a.read_json(path)
        row["implementation_sha"] = "d" * 40
        a.write_json(path, row)
        a.write_manifest(directory)
        self.assertBlocked()

    def test_changed_frozen_preparation_count_is_blocked(self):
        path = self.module / "inputs/pilot/bank_registry.json"
        row = a.read_json(path)
        row["physical_preparation_evaluations"] = 240
        a.write_json(path, row)
        self.assertBlocked()

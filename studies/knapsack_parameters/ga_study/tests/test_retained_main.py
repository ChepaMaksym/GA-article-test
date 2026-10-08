"""CI-only byte and completeness checks of the retained compact main report."""

import gzip
import json
from pathlib import Path
import unittest

from studies.knapsack_parameters.ga_study.contract import (
    MODULE_ROOT, PROTOCOL_ID, DATA_SHA, REGISTRY_SHA, file_identity,
    read_json, verify_file_manifest,
)


class RetainedMainEvidence(unittest.TestCase):
    def setUp(self):
        self.bundle = MODULE_ROOT / "evidence/run-37793424917"
        if not self.bundle.is_dir():
            self.skipTest("compact main evidence has not yet been retained")

    def test_exact_ci_bytes_and_report_identity(self):
        verify_file_manifest(self.bundle)
        transport = read_json(MODULE_ROOT / "main_result_transport.json")
        self.assertEqual(file_identity(self.bundle / "report-data.json")["sha256"], transport["report_data_sha256"])
        self.assertEqual(file_identity(self.bundle / "file_manifest.json")["sha256"], transport["file_manifest_sha256"])
        report = read_json(self.bundle / "report-data.json")
        self.assertEqual(report["status"], "COMPLETE_VERIFIED_MAIN")
        self.assertEqual(report["protocol_id"], PROTOCOL_ID)
        self.assertEqual(report["implementation_commit_sha"], "5fe14fad17368dd94faa86cc0d6138361d3722cf")
        self.assertEqual(report["data_manifest_sha256"], DATA_SHA)
        self.assertEqual(report["registry_sha256"], REGISTRY_SHA)
        self.assertEqual((report["runs"], report["random_runs"], report["local_runs"], report["logical_requests"]),
                         (35640, 24300, 11340, 178200000))
        self.assertEqual(len(report["preparation_cases"]), 30)
        self.assertEqual(len(report["configuration_summaries"]), 54)
        self.assertEqual(len(report["primary_statistics"]["intervals"]), 4)
        self.assertEqual(report["primary_statistics"]["confidence_level_each"], 0.9875)
        self.assertEqual(report["primary_statistics"]["replicates"], 50000)
        self.assertEqual(len(report["provenance"]["sources"]), 90)
        self.assertEqual(len({row["artifact_id"] for row in report["provenance"]["sources"]}), 90)
        self.assertEqual(len(report["example_figures"]), 5)

    def test_all_run_summaries_retained_without_replacement(self):
        identities = set()
        profiles = {"random": 0, "local": 0}
        # The compact CI export intentionally omits the full replay verdict.
        # Its byte identity is checked above; full verdicts stay in source jobs.
        compact_fields = {
            "instance_id", "start_profile", "repeat_seed", "configuration_id",
            "mutation_numerator", "crossover_probability", "population_size",
            "best_mask", "best_profit", "best_weight", "best_request",
            "escape_event", "first_escape_request", "censored", "logical_requests",
            "physical_evaluations", "invalid_request_count", "duplicate_count",
            "complete_generations", "terminal_partial",
        }
        with gzip.open(self.bundle / "run-summaries.jsonl.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                self.assertEqual(set(row), compact_fields)
                identity = (row["instance_id"], row["start_profile"], row["repeat_seed"], row["configuration_id"])
                self.assertNotIn(identity, identities)
                identities.add(identity)
                profiles[row["start_profile"]] += 1
                self.assertTrue(51001 <= row["repeat_seed"] <= 51030)
                self.assertEqual(row["logical_requests"], 5000)
                self.assertEqual(row["physical_evaluations"], 5000 - row["population_size"])
                self.assertEqual(len(row["best_mask"]), 100)
                self.assertLessEqual(set(row["best_mask"]), {"0", "1"})
        self.assertEqual(len(identities), 35640)
        self.assertEqual(profiles, {"random": 24300, "local": 11340})


if __name__ == "__main__":
    unittest.main()

"""Input/control checks only; no KPLIB search or DP occurs in these tests."""
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.final_study import inputs as i


class InputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Checks run only in GitHub Actions")

    def test_binding_is_original_bytes_and_no_new_preparation(self):
        binding = i.probe_binding()
        self.assertEqual(binding["new_preparation_evaluations"], 0)
        self.assertFalse(binding["holdout_search_authorized"])
        self.assertEqual(len(binding["files"]), 5)
        self.assertEqual(binding["conditions"], [["UC-s000", "cloned"], ["SC-s005", "bank"]])
        self.assertTrue(all(len(row["sha256"]) == 64 and row["bytes"] > 0 for row in binding["files"]))

    def test_existing_holdout_preparation_is_complete_without_search(self):
        result = i.holdout_inventory()
        self.assertEqual((result["tasks"], result["nonglobal_centers"], result["global_centers"]), (30, 12, 18))
        self.assertEqual(result["families_local"], 8)
        self.assertFalse(result["GA_outcomes_opened"])
        self.assertFalse(result["search_authorized"])

    def test_no_holdout_bank_preparation_release(self):
        with self.assertRaisesRegex(ValueError, "BLOCKED_MAIN_RESOURCE_APPROVAL"):
            i.prepare_holdout_banks()

    def test_unregistered_probe_condition_rejected_before_loading(self):
        for task, start in (("UC-s010", "bank"), ("UC-s000", "bank"), ("SC-s005", "cloned")):
            with self.assertRaisesRegex(ValueError, "Only the two registered"):
                i.load_probe_bank(task, start)

    def test_bank_loader_reconstructs_initial_masks_without_search(self):
        from studies.knapsack_parameters.final_study import authority as a
        frozen = i._read(i.OLD / "frozen_banks.json")
        def api(endpoint):
            if endpoint.startswith("/actions/runs/"):
                return {"conclusion": "success", "head_sha": i.HISTORICAL_PREP_SHA,
                        "head_branch": a.BRANCH, "event": "push",
                        "path": ".github/workflows/knapsack-adaptation-pilot.yml"}
            return {"workflow_run": {"id": i.HISTORICAL_PREP_RUN, "head_sha": i.HISTORICAL_PREP_SHA},
                    "digest": "sha256:" + frozen["zip_sha256"], "expired": False}
        with patch.object(a, "api", side_effect=api):
            for task, start in i.CONDITIONS:
                bank = i.load_probe_bank(task, start)
                self.assertEqual(bank["search_seed"], 86001)
                self.assertEqual(bank["initial_masks"], i._read(i.OLD /
                    f"inputs/pilot/banks/{task}-{start}-86001.json")["initial_masks"])

    def test_expired_source_is_not_silently_replaced(self):
        from studies.knapsack_parameters.final_study import authority as a
        with patch.object(a, "api", return_value={"expired": True}):
            with self.assertRaisesRegex(ValueError, "unavailable or mismatched"):
                i.load_probe_bank("UC-s000", "cloned")

    def test_corrupted_binding_is_rejected(self):
        original = i._read
        def changed(path):
            value = original(path)
            if Path(path).name == "registration.json":
                value = deepcopy(value)
                name = "studies/knapsack_parameters/adaptation_analysis/frozen_banks.json"
                value["protected_sha256"][name] = "0" * 64
            return value
        with patch.object(i, "_read", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "changed historical input"):
                i.probe_binding()

    def test_missing_new_input_receipt_does_not_release_probe(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(i, "MODULE", Path(directory)):
            with self.assertRaisesRegex(ValueError, "not been bound"):
                i.validate_probe_freeze({})

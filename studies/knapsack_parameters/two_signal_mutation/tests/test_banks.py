"""Preparation fixtures only; no KPLIB search or new exact solves."""
from copy import deepcopy
import os
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.two_signal_mutation import authority as a, banks


class BankTests(unittest.TestCase):
    def setUp(self):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("CI-only tests")
        self.source = {"problem": {"n": 100, "weights": [1] * 100, "profits": [2] * 100, "capacity": 50},
                       "center_mask": "1" * 50 + "0" * 50,
                       "source_identity": {"path": "fixture", "bytes": 1, "sha256": "a" * 64},
                       "registry_identity": {"bytes": 1, "sha256": "b" * 64}}

    def prepared(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(banks, "source_case", return_value=self.source):
            registry = banks.prepare("pilot", directory, {})
            return [a.read_json(a.safe_child(directory, row["path"])) for row in registry["banks"]]

    def test_registered_rectangles(self):
        self.assertEqual(len(banks.expected_conditions("pilot")), 8)
        self.assertEqual(len(banks.expected_conditions("main")), 900)

    def test_preparation_reconstructs_all_eight_banks(self):
        for bank in self.prepared():
            banks.validate_bank(bank, self.source)

    def test_wrong_random_mask_is_rejected_even_with_correct_score(self):
        bank = self.prepared()[1]
        bank["initial_masks"][1] = "0" * 100
        bank["initial_scores"][1] = {"weight": 0, "profit": 0, "feasible": True}
        with self.assertRaises(ValueError):
            banks.validate_bank(bank, self.source)

    def test_rng_states_are_not_decorative(self):
        for field in ("initialization_before", "initialization_after"):
            bank = self.prepared()[1]
            bank[field]["state"]["state"] += 1
            with self.assertRaises(ValueError):
                banks.validate_bank(bank, self.source)

    def test_physical_count_and_booleans_rejected(self):
        for field, value in (("physical_preparation_evaluations", 30), ("new_search_calls", False),
                             ("preparation_ns", -1), ("logical_initial_positions", True)):
            bank = self.prepared()[0]
            bank[field] = value
            with self.assertRaises(ValueError):
                banks.validate_bank(bank, self.source)

    def test_initial_score_corruption(self):
        bank = self.prepared()[1]
        bank["initial_scores"][0]["feasible"] = 1
        with self.assertRaises(ValueError):
            banks.validate_bank(bank, self.source)

    def test_sources_not_solvers(self):
        import inspect
        text = inspect.getsource(banks)
        self.assertNotIn("from studies.knapsack_parameters.feasibility.solvers", text)
        self.assertNotIn("from .engine", text)


if __name__ == "__main__":
    unittest.main()

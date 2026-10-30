import unittest
from unittest.mock import patch
from .audit import expected, safe_path
from . import verifier_snapshot
from studies.knapsack_parameters.tournament_feedback import verifier as protected_verifier


class AuditContract(unittest.TestCase):
    def test_expected_identities(self):
        self.assertEqual(len(expected("smoke")), 7)
        self.assertEqual(len(expected("full")), 6356)

    def test_unsafe_paths(self):
        for name in ("../escape", "/root", "logs/../escape", "C:/escape", "a\\b"):
            self.assertFalse(safe_path(name), name)
        self.assertTrue(safe_path("logs/example.json.gz"))

    def test_missing_and_corrupted_journal_fields(self):
        with self.assertRaises(ValueError):
            verifier_snapshot.verify_log({})
        with self.assertRaises(ValueError):
            verifier_snapshot._score({"n": 2, "weights": [1, 2], "profits": [1, 2], "capacity": 2}, "1x")
        with self.assertRaises(ValueError):
            verifier_snapshot._restore({})

    def test_protected_original_rejects_foreign_environment(self):
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                protected_verifier._ci_only()


if __name__ == "__main__":
    unittest.main()

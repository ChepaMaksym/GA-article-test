"""Small admission checks for the continuation wrapper; no GA is executed."""
import os
import unittest
from unittest.mock import patch
from . import common
from .runner import expected_missing


class CompletionAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        common.guard_completion()

    def test_exact_fourteen_missing_identities(self):
        protocol = common.read_json(common.HERE / "protocol.json")
        declared = {(r["task"], r["seed"], r["mu"]) for r in protocol["missing_cases"]}
        self.assertEqual(len(declared), 14)
        self.assertEqual(declared, expected_missing())
        self.assertTrue(all(mu == 10 and "-SC-" in task for task, seed, mu in declared))

    def test_other_branch_cannot_start_continuation(self):
        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/unregistered"}):
            with self.assertRaises(ValueError):
                common.guard_completion()

    def test_pending_authority_cannot_start_continuation(self):
        with patch.object(common, "read_json", return_value={"status": "PENDING", "stage": "completion"}):
            with self.assertRaises(ValueError):
                common.guard_completion()


if __name__ == "__main__":
    unittest.main()

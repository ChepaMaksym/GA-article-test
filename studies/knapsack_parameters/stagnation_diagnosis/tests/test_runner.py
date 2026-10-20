"""Orchestration/isolation checks; execute only in the registered CI suite."""

from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from .. import runner


class RunnerTests(unittest.TestCase):
    def test_search_problem_contains_no_reference_or_diagnostic(self):
        self.assertEqual({field.name for field in fields(runner.SearchProblem)},
                         {"n", "capacity", "weights", "profits"})
        problem = runner.SearchProblem(3, 10, (6, 5, 5), (9, 5, 5))
        self.assertFalse(hasattr(problem, "optimum"))
        self.assertFalse(hasattr(problem, "certificate"))

    def test_bank_identity_inventory_has_all_main_and_only_three_probes(self):
        instances = [SimpleNamespace(instance_id=f"{label}-s{index:03d}")
                     for label in ("UC", "WC", "SC") for index in range(10)]
        rows = runner.expected_banks(instances)
        self.assertEqual(len(rows), 903)
        self.assertEqual(len(set(rows)), 903)
        self.assertEqual({case for case, seed in rows if seed == 92999},
                         {"UC-s000", "SC-s005", "SC-s000"})
        self.assertEqual(sum(93001 <= seed <= 93030 for _, seed in rows), 900)

    def test_outputs_cannot_enter_checkout_or_overwrite(self):
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}):
            with self.assertRaises(ValueError):
                runner._new_output(runner.ROOT / "prohibited-generated-evidence")
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "new"
                self.assertEqual(runner._new_output(path), path.resolve())
                (path / "existing").write_text("evidence", encoding="utf-8")
                with self.assertRaises(ValueError):
                    runner._new_output(path)

    def test_scientific_output_entrypoint_rejects_non_ci(self):
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}):
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    runner._new_output(Path(directory) / "forbidden")


if __name__ == "__main__":
    unittest.main()

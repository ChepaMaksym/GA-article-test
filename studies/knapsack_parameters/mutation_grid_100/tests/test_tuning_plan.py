"""Synthetic schedule checks, run only by the registered CI checks stage."""
import os
import unittest

from ..prepare_tuning import build_schedule


class TuningScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Scientific tests require GitHub Actions")

    def tasks(self):
        return [{"task": f"n00100-{kind}-s{family:03d}", "task_index": 3 + (family - 50) * 3 + offset,
                 "family": f"s{family:03d}", "class_label": kind}
                for family in range(50, 60) for offset, kind in enumerate(("UC", "WC", "SC"))]

    def test_only_1350_missing_cases_are_scheduled_once(self):
        blocks = build_schedule(self.tasks())
        self.assertEqual(len(blocks), 225)
        self.assertTrue(all(len(block["cases"]) == 6 for block in blocks))
        cases = [case for block in blocks for case in block["cases"]]
        self.assertEqual(len(cases), 1350)
        self.assertEqual({case["mutation_basis_points"] for case in cases}, {25, 50, 75, 150, 200})
        self.assertEqual({case["mu"] for case in cases}, {10, 15, 20})
        self.assertEqual({case["pc_percentage"] for case in cases}, {100})
        ids = {(c["task"], c["seed"], c["mu"], c["pc_percentage"], c["mutation_basis_points"]) for c in cases}
        self.assertEqual(len(ids), 1350)

    def test_missing_or_duplicate_task_rejected(self):
        tasks = self.tasks()
        with self.assertRaises(ValueError):
            build_schedule(tasks[:-1])
        with self.assertRaises(ValueError):
            build_schedule(tasks[:-1] + [tasks[0]])


if __name__ == "__main__":
    unittest.main()

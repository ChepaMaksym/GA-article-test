"""CI-only checks for the prospective tuning schedule and selection."""
from fractions import Fraction
import unittest
import os

from .common import guard_checks, guard_stage
from .prepare_tuning import tuning_schedule
from .analyze_tuning import CONFIGS, choose_config, identity


class TuningChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_REF") == "refs/heads/research/initial-grid100-checks-20261110":
            guard_checks()
        else:
            guard_stage("tuning")

    def test_schedule_excludes_the_180_retained_cases_without_losing_other_cells(self):
        tasks = [{"task": f"n00100-{kind}-s{family:03d}",
                  "task_index": 3 + (family - 50) * 3 + index,
                  "family": f"s{family:03d}", "class_label": kind}
                 for family in range(50, 60) for index, kind in enumerate(("UC", "WC", "SC"))]
        shards = tuning_schedule(tasks)
        cases = [case for shard in shards for case in shard["cases"]]
        self.assertEqual(len(shards), 210)
        self.assertTrue(all(len(shard["cases"]) == 6 for shard in shards))
        self.assertEqual(len(cases), len({identity(c) for c in cases}), 1260)
        self.assertFalse(any((c["mu"], c["pc_percentage"]) in ((10, 90), (20, 90)) for c in cases))
        self.assertEqual({c["seed"] for c in cases}, {150001, 150002, 150003})

    def test_selection_uses_exact_means_then_registered_ties(self):
        scores = {pair: [Fraction(1)] * 10 for pair in CONFIGS}
        self.assertEqual(choose_config(scores), (10, 90))
        scores[(15, 80)] = [Fraction(999999, 1000000)] * 10
        self.assertEqual(choose_config(scores), (15, 80))
        scores[(25, 90)] = [Fraction(999999, 1000000)] * 10
        self.assertEqual(choose_config(scores), (25, 90))
        scores[(10, 90)] = [Fraction(9, 10)] + [Fraction(1)] * 9
        scores[(20, 90)] = [Fraction(99, 100)] * 10
        self.assertEqual(choose_config(scores), (20, 90))

    def test_incomplete_family_scores_cannot_select_a_winner(self):
        with self.assertRaises(ValueError):
            choose_config({(10, 90): [Fraction(1)] * 10})


if __name__ == "__main__":
    unittest.main()

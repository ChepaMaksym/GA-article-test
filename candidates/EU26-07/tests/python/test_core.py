from __future__ import annotations

import unittest

from eu2607.core import run_artifact_jump_optimized


class CleanRoomReplayTests(unittest.TestCase):
    def test_first_two_published_trajectories_are_exact(self):
        expected = {
            1: (6401, 84504, 3, 0.1377837980315536),
            2: (9221, 121590, 9, 0.4650203183564929),
        }
        for run, values in expected.items():
            with self.subTest(run=run):
                row = run_artifact_jump_optimized(run)
                self.assertEqual(
                    (
                        row.generations,
                        row.evaluations,
                        row.final_lambda,
                        row.last_mutation_probability,
                    ),
                    values,
                )
                self.assertTrue(row.solved)
                self.assertEqual(row.effective_seed, 816_114_841 + run)

    def test_reseeding_makes_a_run_repeatable(self):
        first = run_artifact_jump_optimized(1)
        second = run_artifact_jump_optimized(1)
        self.assertEqual(first, second)

    def test_fixture_parameters_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "frozen fixture"):
            run_artifact_jump_optimized(1, n=21)
        with self.assertRaises(ValueError):
            run_artifact_jump_optimized(0)


if __name__ == "__main__":
    unittest.main()

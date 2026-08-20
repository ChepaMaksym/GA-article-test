from __future__ import annotations

import unittest

from pyvrp import PenaltyManager, PenaltyParams


class PenaltyTransitionTests(unittest.TestCase):
    def setUp(self):
        self.params = PenaltyParams(
            init_capacity_penalty=20,
            init_time_warp_penalty=0,
            repair_booster=12,
            num_registrations_between_penalty_updates=100,
            penalty_increase=1.25,
            penalty_decrease=0.85,
            target_feasible=0.43,
        )

    def test_below_target_increases_with_plus_one(self):
        self.assertEqual(PenaltyManager._compute(100, 0.37, self.params), 126)

    def test_above_target_decreases_with_minus_one(self):
        self.assertEqual(PenaltyManager._compute(100, 0.49, self.params), 84)

    def test_interior_unchanged(self):
        self.assertEqual(PenaltyManager._compute(100, 0.43, self.params), 100)

    def test_discrete_lower_boundary_is_unchanged_under_float(self):
        diff = self.params.target_feasible - 0.38
        self.assertLess(abs(diff), 0.05)
        self.assertEqual(PenaltyManager._compute(100, 0.38, self.params), 100)

    def test_discrete_upper_boundary_is_unchanged_under_float(self):
        diff = self.params.target_feasible - 0.48
        self.assertLess(abs(diff), 0.05)
        self.assertEqual(PenaltyManager._compute(100, 0.48, self.params), 100)

    def test_clips_upper(self):
        self.assertEqual(PenaltyManager._compute(999, 0.0, self.params), 1000)

    def test_clips_lower(self):
        self.assertEqual(PenaltyManager._compute(1, 1.0, self.params), 1)

    def test_integer_truncation(self):
        self.assertEqual(PenaltyManager._compute(21, 0.0, self.params), 27)
        self.assertEqual(PenaltyManager._compute(21, 1.0, self.params), 16)

    def test_update_cadence_and_history_clear(self):
        manager = PenaltyManager(self.params)
        for _ in range(99):
            manager.register_capacity_feasible(False)
        self.assertEqual(manager.capacity_penalty(1).capacity_penalty, 20)
        manager.register_capacity_feasible(False)
        self.assertEqual(manager.capacity_penalty(1).capacity_penalty, 26)
        self.assertEqual(manager._capacity_feasibility, [])

    def test_histories_are_separate(self):
        manager = PenaltyManager(self.params)
        for _ in range(100):
            manager.register_capacity_feasible(False)
            manager.register_time_feasible(True)
        self.assertEqual(manager.capacity_penalty(1).capacity_penalty, 26)
        self.assertEqual(manager.tw_penalty(1).tw_penalty, 1)


if __name__ == "__main__":
    unittest.main()

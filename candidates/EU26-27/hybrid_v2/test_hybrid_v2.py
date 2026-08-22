from __future__ import annotations

import math
import unittest

import analyze_paired as analysis
import controller


class RollbackControllerTests(unittest.TestCase):
    def test_initial_state_is_paper_baseline(self):
        state = controller.initial_state()
        self.assertEqual(state.lambda_real, 10.0)
        self.assertEqual(state.lambda_base, 10.0)
        self.assertEqual(state.bad_count, 0)
        self.assertEqual(state.delta, 10)

    def test_success_cannot_go_below_paper_baseline(self):
        state = controller.next_rollback(controller.initial_state(), strict_success=True)
        self.assertEqual(state.lambda_real, 10.0)
        self.assertEqual(state.lambda_count, 10)
        self.assertEqual(state.lambda_base, 10.0)
        self.assertEqual(state.bad_count, 0)
        self.assertEqual(state.delta, 10)

    def test_failure_grows_from_base(self):
        state = controller.next_rollback(controller.initial_state(), strict_success=False)
        expected = 10.0 * 1.5 ** 0.25
        self.assertTrue(math.isclose(state.lambda_real, expected))
        self.assertEqual(state.bad_count, 1)
        self.assertEqual(state.delta, 10)

    def test_tenth_bad_iteration_rolls_back_and_extends_span(self):
        state = controller.initial_state()
        for _ in range(9):
            state = controller.next_rollback(state, strict_success=False)
        self.assertEqual(state.bad_count, 9)
        self.assertGreater(state.lambda_real, state.lambda_base)
        state = controller.next_rollback(state, strict_success=False)
        self.assertEqual(state.bad_count, 0)
        self.assertEqual(state.delta, 11)
        self.assertTrue(math.isclose(state.lambda_real, state.lambda_base))

    def test_success_resets_base_bad_count_and_delta(self):
        state = controller.RollbackState(30.0, 30, 20.0, 4, 13)
        state = controller.next_rollback(state, strict_success=True)
        self.assertEqual(state.lambda_real, 20.0)
        self.assertEqual(state.lambda_base, 20.0)
        self.assertEqual(state.bad_count, 0)
        self.assertEqual(state.delta, 10)

    def test_floor_ablation_never_below_ten(self):
        value, count = controller.next_floor_only(10.0, strict_success=True)
        self.assertEqual(value, 10.0)
        self.assertEqual(count, 10)


class HoldoutAnalysisTests(unittest.TestCase):
    def test_v2_seed_ledger_rejects_v1_overlap_logic(self):
        self.assertTrue(set(range(28001, 28031)).isdisjoint(set(range(27001, 27031))))

    def test_relative_reduction(self):
        self.assertEqual(analysis.paired_relative_reductions([100, 200], [80, 100]), [0.2, 0.5])

    def test_bootstrap_is_deterministic(self):
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        self.assertEqual(analysis.bootstrap_median_ci(values), analysis.bootstrap_median_ci(values))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import math
import unittest

import analyze_paired as analysis
import controller


class ControllerTests(unittest.TestCase):
    def test_success_shrinks(self):
        state = controller.next_lambda(10.0, strict_success=True)
        self.assertAlmostEqual(state.lambda_real, 10.0 / 1.5)
        self.assertEqual(state.lambda_count, 7)

    def test_failure_grows_by_fourth_root(self):
        state = controller.next_lambda(10.0, strict_success=False)
        self.assertAlmostEqual(state.lambda_real, 10.0 * 1.5 ** 0.25)
        self.assertEqual(state.lambda_count, controller.round_half_up(state.lambda_real))

    def test_reset_at_cap(self):
        state = controller.next_lambda(100.0, strict_success=False, reset=True)
        self.assertEqual(state.lambda_real, 1.0)
        self.assertEqual(state.lambda_count, 1)

    def test_no_reset_stays_at_cap(self):
        state = controller.next_lambda(100.0, strict_success=False, reset=False)
        self.assertEqual(state.lambda_real, 100.0)
        self.assertEqual(state.lambda_count, 100)

    def test_lower_bound(self):
        state = controller.next_lambda(1.0, strict_success=True)
        self.assertEqual(state.lambda_real, 1.0)
        self.assertEqual(state.lambda_count, 1)

    def test_invalid_factor(self):
        with self.assertRaises(ValueError):
            controller.next_lambda(10.0, strict_success=False, update_factor=1.0)


class AnalysisTests(unittest.TestCase):
    def test_relative_reduction(self):
        values = analysis.paired_relative_reductions([100, 200], [80, 100])
        self.assertEqual(values, [0.2, 0.5])

    def test_percentile_endpoints(self):
        values = [0.0, 1.0, 2.0, 3.0]
        self.assertEqual(analysis.percentile(values, 0.0), 0.0)
        self.assertEqual(analysis.percentile(values, 1.0), 3.0)
        self.assertTrue(math.isclose(analysis.percentile(values, 0.5), 1.5))

    def test_bootstrap_is_deterministic(self):
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        self.assertEqual(analysis.bootstrap_median_ci(values), analysis.bootstrap_median_ci(values))


if __name__ == "__main__":
    unittest.main()

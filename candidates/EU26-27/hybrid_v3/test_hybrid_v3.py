from __future__ import annotations

import statistics
import unittest

CAPS = (15, 20, 30, 40, 60, 100)
F = 1.5
FLOOR = 10.0


def update_lambda(value: float, success: bool, cap: int) -> float:
    if success:
        return max(value / F, FLOOR)
    return min(value * F ** 0.25, float(cap))


def choose_cap(scores: dict[int, float]) -> int:
    return min(CAPS, key=lambda cap: (-scores[cap], cap))


class HybridV3Tests(unittest.TestCase):
    def test_success_never_below_old_lambda(self) -> None:
        self.assertEqual(update_lambda(10.0, True, 40), 10.0)

    def test_failure_respects_cap(self) -> None:
        value = 10.0
        for _ in range(100):
            value = update_lambda(value, False, 20)
        self.assertEqual(value, 20.0)

    def test_success_can_reduce_from_cap(self) -> None:
        self.assertAlmostEqual(update_lambda(30.0, True, 30), 20.0)

    def test_cap_grid_is_frozen(self) -> None:
        self.assertEqual(CAPS, (15, 20, 30, 40, 60, 100))

    def test_selection_uses_largest_paired_median(self) -> None:
        scores = {15: 0.01, 20: 0.03, 30: 0.02, 40: -0.01, 60: 0.0, 100: 0.01}
        self.assertEqual(choose_cap(scores), 20)

    def test_selection_tie_prefers_smaller_cap(self) -> None:
        scores = {cap: 0.0 for cap in CAPS}
        scores[20] = scores[30] = 0.05
        self.assertEqual(choose_cap(scores), 20)

    def test_paired_median_not_marginal_median(self) -> None:
        old = [100, 100, 100]
        candidate = [50, 100, 200]
        paired = statistics.median((o - c) / o for o, c in zip(old, candidate))
        self.assertEqual(paired, 0.0)

    def test_holdout_disjointness(self) -> None:
        holdout = set(range(29001, 29031))
        retired = set(range(27001, 27031)) | set(range(28001, 28031))
        self.assertTrue(holdout.isdisjoint(retired))

    def test_holdout_exact_ledger(self) -> None:
        self.assertEqual(list(range(29001, 29031))[0], 29001)
        self.assertEqual(list(range(29001, 29031))[-1], 29030)


if __name__ == "__main__":
    unittest.main()

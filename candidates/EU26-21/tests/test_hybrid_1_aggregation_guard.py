#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_1.aggregate_old_hybrid_v2_corrected import corrected_capped  # noqa: E402


class AggregationGuardTests(unittest.TestCase):
    def test_first_initial_mask_is_valid_target_hit(self) -> None:
        self.assertEqual(corrected_capped(1, 2500), (1, True))

    def test_last_initial_mask_is_valid_target_hit(self) -> None:
        self.assertEqual(corrected_capped(50, 2500), (50, True))

    def test_missing_and_over_budget_hits_are_censored(self) -> None:
        self.assertEqual(corrected_capped(None, 2500), (2500, False))
        self.assertEqual(corrected_capped(2501, 2500), (2500, False))

    def test_nonpositive_nfe_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            corrected_capped(0, 2500)


if __name__ == "__main__":
    unittest.main()

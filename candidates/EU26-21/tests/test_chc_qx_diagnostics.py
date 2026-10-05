"""CI-only tests for complete, isolated approximate/full one-bit certificates."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chc_qx_alignment_study.diagnostics import certify_snapshot  # noqa: E402


def _snapshot():
    return {"mask": [0] * 40, "active_wba": 0.999,
            "reason": "first_whole_chunk_without_active_gain", "chunk": 1}


def _strict(mask):
    return 0.6 if not any(mask) else 0.5


def _not_local(mask):
    return 0.5 if not any(mask) else 0.6


class DiagnosticTests(unittest.TestCase):
    def test_all_four_preregistered_classifications(self):
        cases = [
            (_strict, _strict, "both_local"),
            (_strict, _not_local, "approximate_only_false_local"),
            (_not_local, _strict, "full_only_local"),
            (_not_local, _not_local, "neither_local"),
        ]
        for active, full, expected in cases:
            with self.subTest(classification=expected):
                result = certify_snapshot(snapshot=_snapshot(), active_objective=active, full_objective=full)
                self.assertEqual(result["classification"], expected)
                self.assertEqual(result["objective_calls"], 82)
                self.assertFalse(result["feed_back_to_search"])
                self.assertFalse(result["controlled_escape"])
                self.assertFalse(result["two_bit_audit"])
                json.dumps(result, allow_nan=False)

    def test_center_is_recomputed_independently_and_every_neighbor_is_queried_in_order(self):
        active = Mock(side_effect=_strict)
        full = Mock(side_effect=_not_local)
        result = certify_snapshot(snapshot=_snapshot(), active_objective=active, full_objective=full)
        self.assertEqual(active.call_count, 41)
        self.assertEqual(full.call_count, 41)
        self.assertEqual(result["approximate"]["center_wba"], 0.6)
        self.assertEqual(result["full"]["center_wba"], 0.5)
        self.assertNotEqual(result["snapshot"]["active_wba"], result["approximate"]["center_wba"])
        for scope in ("approximate", "full"):
            rows = result[scope]["evaluations"]
            self.assertEqual(rows[0]["mask"], [0] * 40)
            self.assertIsNone(rows[0]["bit"])
            self.assertEqual([row["bit"] for row in rows[1:]], list(range(40)))
            self.assertEqual([row["call"] for row in rows], list(range(1, 42)))
            for bit, row in enumerate(rows[1:]):
                expected = [0] * 40
                expected[bit] = 1
                self.assertEqual(row["mask"], expected)
            self.assertEqual(result[scope]["global_optimality"], "not_assessed")
            self.assertEqual(result[scope]["non_globality"], "not_assessed")

    def test_strict_maximum_plateau_and_nonlocal_ties_are_not_conflated(self):
        result = certify_snapshot(snapshot=_snapshot(), active_objective=_strict, full_objective=lambda _mask: 0.5)
        self.assertTrue(result["approximate"]["strict_local_maximum"])
        self.assertFalse(result["approximate"]["plateau_local_maximum"])
        self.assertFalse(result["full"]["strict_local_maximum"])
        self.assertTrue(result["full"]["plateau_local_maximum"])
        self.assertEqual(result["full"]["equal_neighbors"], 40)
        result = certify_snapshot(
            snapshot=_snapshot(), active_objective=lambda mask: 0.6 if mask[0] else 0.5,
            full_objective=_strict,
        )
        self.assertFalse(result["approximate"]["local_maximum"])
        self.assertFalse(result["approximate"]["plateau_local_maximum"])
        self.assertEqual(result["approximate"]["higher_neighbors"], 1)
        self.assertEqual(result["approximate"]["equal_neighbors"], 39)

    def test_comparison_has_no_unregistered_numeric_tolerance(self):
        result = certify_snapshot(
            snapshot=_snapshot(),
            active_objective=lambda mask: 0.5 + (1e-12 if mask[0] else 0.0),
            full_objective=_strict,
        )
        self.assertFalse(result["approximate"]["local_maximum"])
        self.assertEqual(result["approximate"]["numerical_tolerance"], 0.0)

    def test_invalid_center_or_nonscalar_metric_fails_without_fallback(self):
        active, full = Mock(return_value=0.5), Mock(return_value=0.5)
        with self.assertRaises(ValueError):
            certify_snapshot(snapshot={"mask": [0] * 39}, active_objective=active, full_objective=full)
        active.assert_not_called()
        full.assert_not_called()
        for value in ((0.5, -0.5), float("nan"), True, 1.1):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                certify_snapshot(snapshot=_snapshot(), active_objective=lambda _mask: value,
                                 full_objective=lambda _mask: 0.5)


if __name__ == "__main__":
    unittest.main()

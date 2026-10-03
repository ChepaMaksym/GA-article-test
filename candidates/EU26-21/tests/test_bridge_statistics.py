"""Independent vectorized BCa reference and exact confirmatory decision gates."""
from __future__ import annotations

from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

import numpy as np
from scipy.special import ndtr, ndtri

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_bridge import aggregate  # noqa: E402


class BCaReferenceTests(unittest.TestCase):
    def test_nonconstant_tied_sample_matches_vectorized_scipy_normal_reference(self) -> None:
        # The reference uses the same prespecified resampling indices, but
        # independent NumPy medians/quantiles and SciPy normal CDF/inverse.
        values = np.asarray([-0.09, -0.02, -0.02, -0.01, 0.0, 0.01] * 5)
        rng = random.Random(41031)
        indices = np.fromiter((rng.randrange(30) for _ in range(50_000 * 30)),
                              dtype=np.int64).reshape(50_000, 30)
        draws = np.median(values[indices], axis=1)
        estimate = np.median(values)
        probability = (np.count_nonzero(draws < estimate) + 0.5 * np.count_nonzero(draws == estimate)) / 50_000
        bias = ndtri(np.clip(probability, 0.5 / 50_000, 1 - 0.5 / 50_000))
        jackknife = np.asarray([np.median(np.delete(values, index)) for index in range(30)])
        centered = jackknife.mean() - jackknife
        denominator = 6 * np.sum(centered**2)**1.5
        acceleration = 0 if denominator == 0 else np.sum(centered**3) / denominator
        inner = bias + ndtri([0.025, 0.975])
        adjusted = ndtr(bias + inner / (1 - acceleration * inner))
        reference = np.quantile(draws, adjusted, method="linear")
        actual = aggregate.paired_median_bca(values.tolist())
        np.testing.assert_allclose(
            [actual["two_sided_95_lower"], actual["two_sided_95_upper"]], reference,
            rtol=0, atol=1e-12,
        )
        self.assertAlmostEqual(actual["bias_correction"], float(bias), places=12)
        self.assertAlmostEqual(actual["acceleration"], float(acceleration), places=12)
        self.assertEqual(actual["analysis_seed"], 41031)
        self.assertEqual(actual["resamples"], 50_000)

    def test_degenerate_and_nonfinite_inputs(self) -> None:
        interval = aggregate.paired_median_bca([0.0] * 30)
        self.assertEqual(interval["two_sided_95_lower"], 0.0)
        self.assertEqual(interval["two_sided_95_upper"], 0.0)
        self.assertEqual(interval["acceleration"], 0.0)
        for values in ([0.0] * 29, [0.0] * 29 + [float("nan")]):
            with self.assertRaises(aggregate.EvidenceError):
                aggregate.paired_median_bca(values)

    def test_quality_and_efficiency_boundaries_are_strict_and_ordered(self) -> None:
        rows = [{"arms": {
            arm: {"auc": 0.5, "post_initial_auc": 0.5,
                  "terminal": {"test_weighted_balanced_accuracy": 0.8, "selected_feature_count": 20}}
            for arm in aggregate.ARM_NAMES
        }} for _ in range(30)]
        cases = [
            (-0.001, 0.1, "FAIL_NONINFERIORITY", "BLOCKED_BY_QUALITY_NONINFERIORITY"),
            (-0.000999, 0.0, "PASS_NONINFERIORITY", "FAIL_AUC_SUPERIORITY"),
            (0.0, 0.000001, "PASS_NONINFERIORITY", "PASS_AUC_SUPERIORITY"),
        ]
        for quality, auc, quality_decision, auc_decision in cases:
            intervals = [{"two_sided_95_lower": endpoint} for endpoint in (quality, auc, 0.0)]
            with self.subTest(quality=quality, auc=auc), patch.object(aggregate, "_paired_median_bca", side_effect=intervals):
                result = aggregate.analyze_rows(rows)
            self.assertEqual(result["quality_noninferiority"]["decision"], quality_decision)
            self.assertEqual(result["auc_superiority"]["decision"], auc_decision)
            if quality_decision == "FAIL_NONINFERIORITY":
                self.assertEqual(result["feature_count_secondary"]["decision"], "BLOCKED_BY_QUALITY_NONINFERIORITY")


if __name__ == "__main__":
    unittest.main()

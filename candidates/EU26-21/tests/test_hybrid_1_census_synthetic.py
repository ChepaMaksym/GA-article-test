#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_1.census import (  # noqa: E402
    FROZEN_ACTIVE_SAMPLE_SIZES,
    FeatureSelectionObjective,
    PreparedCensus,
    final_test_accuracy,
)
from hybrid_1.core import run_reset_lambda_ga, source_density_population  # noqa: E402


class HybridOneCensusSyntheticTests(unittest.TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(8)
        x = rng.normal(size=(120, 20))
        y = (x[:, 0] + 0.7 * x[:, 1] > 0.0).astype(int)
        self.prepared = PreparedCensus(
            x_train=x[:70],
            y_train=y[:70],
            x_validation=x[70:95],
            y_validation=y[70:95],
            x_test=x[95:],
            y_test=y[95:],
            active_instances=np.arange(50),
            baseline_validation_accuracy=0.0,
            baseline_test_accuracy=0.0,
            metadata={},
        )

    def test_frozen_old_active_size_ledger_is_complete(self) -> None:
        self.assertEqual(set(FROZEN_ACTIVE_SAMPLE_SIZES), set(range(1, 11)))
        self.assertEqual(
            [FROZEN_ACTIVE_SAMPLE_SIZES[seed] for seed in range(1, 11)],
            [
                7482,
                7482,
                14964,
                7482,
                14964,
                14964,
                7482,
                14964,
                7482,
                14964,
            ],
        )

    def test_empty_mask_is_penalized_and_sparsity_breaks_ties(self) -> None:
        objective = FeatureSelectionObjective(
            self.prepared.x_train[self.prepared.active_instances],
            self.prepared.y_train[self.prepared.active_instances],
            self.prepared.x_validation,
            self.prepared.y_validation,
        )
        self.assertEqual(objective(tuple([0] * 20)), (0.0, -1.0))
        first = objective(tuple([1] + [0] * 19))
        both = objective(tuple([1, 1] + [0] * 18))
        if first[0] == both[0]:
            self.assertGreater(first[1], both[1])

    def test_hybrid_returns_valid_nonempty_subset(self) -> None:
        objective = FeatureSelectionObjective(
            self.prepared.x_train[self.prepared.active_instances],
            self.prepared.y_train[self.prepared.active_instances],
            self.prepared.x_validation,
            self.prepared.y_validation,
        )
        initial = source_density_population(
            10,
            20,
            np.random.default_rng(4),
        )
        result = run_reset_lambda_ga(
            objective,
            dimension=20,
            seed=14,
            max_evaluations=180,
            workers=2,
            initial_masks=initial,
        )
        self.assertLessEqual(result.evaluations, 180)
        self.assertGreater(sum(result.best_mask), 0)
        accuracy = final_test_accuracy(self.prepared, result.best_mask)
        self.assertTrue(0.0 <= accuracy <= 1.0)


if __name__ == "__main__":
    unittest.main()

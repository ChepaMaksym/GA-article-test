"""Training-only and timing-controlled sampler fixtures; executed in CI only."""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import warnings

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chc_qx_alignment_study import data  # noqa: E402


def raw_frame(rows=80):
    frame = np.empty((rows, 42), dtype=object)
    for column in range(42):
        if column in (0, 5, 16, 17, 18, 24, 30, 39):
            frame[:, column] = np.arange(rows) % 9 + 1
        elif column == 41:
            frame[:, column] = [0, 1] * (rows // 2)
        else:
            frame[:, column] = np.where(np.arange(rows) % 3, "a", "b")
    frame[:, 24] = np.arange(rows) + 1000
    return pd.DataFrame(frame)


class TrainingDataTests(unittest.TestCase):
    def fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "train.csv"
            path.write_bytes(b"fixture")
            with mock.patch.object(data, "_read_raw", return_value=raw_frame()) as loader:
                prepared = data.prepare_training(path, seed=44001)
            loader.assert_called_once_with(path, 199_523)
            return prepared

    def test_training_container_and_objective_cannot_own_holdout_arrays(self):
        prepared = self.fixture()
        self.assertFalse(any("test" in item.name for item in fields(prepared)))
        objective = data.objective_for(prepared, [0, 1, 2, 3])
        self.assertFalse(any("test" in item.name for item in fields(objective)))
        self.assertFalse(any(getattr(objective, item.name) is prepared for item in fields(objective)))
        self.assertFalse(prepared.metadata["test_arrays_loaded"])

    def test_split_encoding_weight_exclusion_and_readonly_arrays(self):
        prepared = self.fixture()
        self.assertEqual(prepared.x_train.shape, (64, 40))
        self.assertEqual(prepared.x_validation.shape, (16, 40))
        self.assertEqual(prepared.feature_names, data.TRANSFORMED_FEATURE_NAMES)
        self.assertNotIn("instance_weight", prepared.feature_names)
        self.assertNotIn(24, prepared.metadata["transformed_raw_indices"])
        self.assertEqual(len(set(prepared.metadata["transformed_raw_indices"])), 40)
        self.assertFalse(set(prepared.train_raw_indices) & set(prepared.validation_raw_indices))
        self.assertFalse(prepared.x_train.flags.writeable)
        self.assertTrue(np.all(prepared.weight_train >= 1000))

    def test_same_seed_reconstructs_identical_training_only_arrays_and_hashes(self):
        first, second = self.fixture(), self.fixture()
        self.assertEqual(first.metadata, second.metadata)
        np.testing.assert_array_equal(first.x_train, second.x_train)

    def test_empty_mask_scalar_score_zero_without_fit_or_timer(self):
        objective = data.objective_for(self.fixture())
        with mock.patch.object(data, "DecisionTreeClassifier") as classifier:
            timer = mock.Mock(side_effect=AssertionError("timer must not run"))
            self.assertEqual(objective.measured([0] * 40, clock=timer), (0.0, 0.0))
            classifier.assert_not_called()
            timer.assert_not_called()

    def test_scalar_wba_has_no_feature_penalty_and_timer_covers_fit_predict(self):
        objective = data.objective_for(self.fixture())
        model = mock.Mock()
        model.predict.return_value = objective.y_validation.copy()
        events = []
        model.fit.side_effect = lambda *args, **kwargs: events.append("fit")
        model.predict.side_effect = lambda *args, **kwargs: (events.append("predict") or objective.y_validation.copy())
        timer_values = iter((10.0, 12.0))
        def timer():
            events.append("clock")
            return next(timer_values)
        with mock.patch.object(data, "DecisionTreeClassifier", return_value=model) as classifier:
            score, duration = objective.measured([1] + [0] * 39, clock=timer)
        self.assertEqual(score, 1.0)
        self.assertEqual(duration, 2.0)
        self.assertEqual(events, ["clock", "fit", "predict", "clock"])
        classifier.assert_called_once_with(random_state=0)
        self.assertIn("sample_weight", model.fit.call_args.kwargs)

    def test_invalid_active_rows_and_masks_rejected(self):
        prepared = self.fixture()
        for rows in ([0, 0], [-1, 0], [0, 10000], [0.0, 1.0], [True, False]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                data.objective_for(prepared, rows)
        for mask in ([1] * 39, [True] + [0] * 39, [0.5] + [0] * 39):
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                data.objective_for(prepared)(mask)


class SamplerTests(unittest.TestCase):
    def prepared(self):
        return TrainingDataTests().fixture()

    def test_source_density_stream_is_reproducible_controls_nonempty(self):
        first = data.source_density_masks(10, seed=2044004, nonempty=True)
        self.assertEqual(first, data.source_density_masks(10, seed=2044004, nonempty=True))
        self.assertTrue(all(sum(mask) for mask in first))
        self.assertTrue(all(len(mask) == 40 for mask in first))
        self.assertEqual(len(data.source_density_masks(50, seed=3044004, nonempty=False)), 50)

    def test_initial_density_does_not_reject_empty_mask(self):
        with mock.patch.object(data.random, "Random") as python_random, \
             mock.patch.object(data.np.random, "RandomState") as numpy_random:
            python_random.return_value.uniform.return_value = 1.0
            numpy_random.return_value.choice.return_value = np.zeros(40, dtype=int)
            self.assertEqual(data.source_density_masks(2, seed=1, nonempty=False), ((0,) * 40,) * 2)
            self.assertEqual(numpy_random.return_value.choice.call_count, 2)

    def test_progressive_halving_stops_at_first_nonimprovement_and_keeps_previous_order(self):
        prepared = self.prepared()
        durations = {64: 1.0, 32: 0.5, 16: 0.25, 8: 0.4}
        scorer = mock.Mock(side_effect=lambda rows, mask: (sum(mask) / 40, durations[len(rows)]))
        result = data.select_active_rows(prepared, seed=44001, measured_score=scorer, minimum_rows=4)
        self.assertEqual(result["status"], "PASS_PREPARATION")
        self.assertEqual([row["size"] for row in result["trials"]], [32, 16, 8])
        self.assertEqual([row["strictly_improving"] for row in result["trials"]], [True, True, False])
        self.assertEqual(result["selected_row_count"], 16)
        self.assertEqual(scorer.call_count, 40)
        self.assertEqual(result["sampler_validation_calls"], 40)
        self.assertEqual(len(set(result["selected_rows"])), 16)
        self.assertEqual(prepared.train_raw_indices[result["selected_rows"]].tolist(), result["selected_raw_row_ids"])
        self.assertEqual(result["selected_rows_sha256"], data.array_sha256(np.asarray(result["selected_rows"], dtype=np.int64)))

    def test_negative_spearman_is_not_clamped_and_first_finite_candidate_is_selected(self):
        scorer = lambda rows, mask: (sum(mask) / 40 if len(rows) == 64 else 1 - sum(mask) / 40,
                                     1.0 if len(rows) == 64 else 0.1)
        result = data.select_active_rows(self.prepared(), seed=44001, measured_score=scorer, minimum_rows=4)
        self.assertEqual(result["status"], "PASS_PREPARATION")
        self.assertAlmostEqual(result["trials"][0]["rho"], -1.0)
        self.assertAlmostEqual(result["trials"][0]["criterion"], 2.1)
        self.assertEqual(result["selected_row_count"], 32)

    def test_undefined_spearman_retained_without_fallback(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = data.select_active_rows(self.prepared(), seed=44001,
                     measured_score=lambda rows, mask: (0.6, 1.0), minimum_rows=4)
        self.assertEqual(result["status"], "NOT_EVALUABLE_SAMPLER")
        self.assertIsNone(result["selected_rows"])
        self.assertIsNone(result["trials"][0]["rho"])
        self.assertFalse(result["trials"][0]["rho_defined"])
        self.assertEqual(result["sampler_validation_calls"], 20)

    def test_invalid_full_or_sample_timers_are_not_evaluable(self):
        for bad_time in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(value=bad_time):
                result = data.select_active_rows(self.prepared(), seed=44001,
                         measured_score=lambda rows, mask: (sum(mask) / 40, bad_time), minimum_rows=4)
                self.assertEqual(result["status"], "NOT_EVALUABLE_SAMPLER")
                self.assertIsNone(result["selected_rows"])
                self.assertEqual(result["sampler_validation_calls"], 10)

    def test_sampling_is_repeatable_with_frozen_timing_inputs(self):
        scorer = lambda rows, mask: (sum(mask) / 40, len(rows) / 64)
        first = data.select_active_rows(self.prepared(), seed=44001, measured_score=scorer, minimum_rows=4)
        second = data.select_active_rows(self.prepared(), seed=44001, measured_score=scorer, minimum_rows=4)
        self.assertEqual(first, second)

    def test_nonfinite_timing_ratio_is_not_an_infrastructure_json_error(self):
        scorer = lambda rows, mask: (sum(mask) / 40, 1e-300 if len(rows) == 64 else 1e300)
        result = data.select_active_rows(self.prepared(), seed=44001, measured_score=scorer, minimum_rows=4)
        self.assertEqual(result["status"], "NOT_EVALUABLE_SAMPLER")
        self.assertIsNone(result["trials"][0]["criterion"])
        self.assertIsNone(result["selected_rows"])


if __name__ == "__main__":
    unittest.main()

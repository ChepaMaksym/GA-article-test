"""CI-only synthetic checks for historical class metrics and saved-tree reports."""
from __future__ import annotations

import copy
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_audit import class_tree_report as report  # noqa: E402


def metric_block(matrix):
    tn, fp = matrix[0]
    fn, tp = matrix[1]
    return {
        "confusion_matrix": matrix, "negative_support": tn + fp, "positive_support": fn + tp,
        "accuracy": (tn + tp) / (tn + fp + fn + tp),
        "balanced_accuracy": (tn / (tn + fp) + tp / (fn + tp)) / 2,
        "precision_positive": tp / (tp + fp) if tp + fp else 0,
        "recall_positive": tp / (tp + fn),
        "f1_positive": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
    }


class ClassMetricTests(unittest.TestCase):
    def test_both_classes_are_derived_without_pooling(self):
        block = metric_block([[90000, 3000], [3000, 3762]])
        observed = report.class_metrics(block, weighted=False)
        self.assertEqual([row["class"] for row in observed], [0, 1])
        self.assertAlmostEqual(observed[0]["precision"], 90000 / 93000)
        self.assertAlmostEqual(observed[0]["recall"], 90000 / 93000)
        self.assertAlmostEqual(observed[1]["recall"], 3762 / 6762)
        self.assertEqual(observed[1]["support"], 6762)

    def test_weighted_matrix_uses_sums_not_record_counts(self):
        rows = report.class_metrics(metric_block([[1000.5, 80.5], [30.2, 20.3]]), weighted=True)
        self.assertAlmostEqual(rows[0]["precision"], 1000.5 / 1030.7)
        self.assertAlmostEqual(rows[1]["support"], 50.5)

    def test_zero_division_returns_zero_and_wba_is_mean_recall(self):
        block = metric_block([[93000, 0], [6762, 0]])
        rows = report.class_metrics(block, weighted=False)
        self.assertEqual(rows[1]["precision"], 0)
        self.assertEqual(rows[1]["f1"], 0)
        self.assertEqual(block["balanced_accuracy"], 0.5)

    def test_invalid_matrix_support_metric_and_total_are_rejected(self):
        original = metric_block([[90000, 3000], [3000, 3762]])
        for key, value, message in (
            ("confusion_matrix", [[90000, 3000], [3000]], "shape"),
            ("confusion_matrix", [[-1, 3000], [3000, 3762]], "nonnegative"),
            ("confusion_matrix", [[90000.5, 3000], [3000, 3761.5]], "record counts"),
            ("negative_support", 93001, "support mismatch"),
            ("balanced_accuracy", 0.5, "disagrees"),
            ("precision_positive", float("nan"), "outside"),
        ):
            block = copy.deepcopy(original)
            block[key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, message):
                report.class_metrics(block, weighted=False)
        with self.assertRaisesRegex(ValueError, "official-test total"):
            report.class_metrics(metric_block([[9, 3], [3, 4]]), weighted=False)

    def test_feature_mapping_is_transformed_not_raw_order(self):
        mapping = report.feature_mapping()
        self.assertEqual(len(mapping), 40)
        self.assertEqual([row["mask_bit_1_based"] for row in mapping], list(range(1, 41)))
        self.assertEqual([row["raw_index_0_based"] for row in mapping[:7]], [0, 5, 16, 17, 18, 30, 39])
        self.assertEqual(mapping[6]["feature_name"], "weeks_worked_in_year")
        self.assertEqual(mapping[7]["feature_name"], "class_of_worker")
        self.assertNotIn(24, [row["raw_index_0_based"] for row in mapping])
        self.assertEqual(mapping[39]["feature_name"], "year")


class HistoricalClassTreeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.rows = self.root / "rows"
        self.rows.mkdir()
        self.expected = self.root / "expected.json"
        self.expected.write_text("fixture ledger", encoding="utf-8")
        self.verified = self.root / "verified.json"
        self.mapping = report.feature_mapping()
        self.mask = [int(index in (0, 7)) for index in range(40)]
        self.names = [row["feature_name"] for row in self.mapping]
        self.provenance = {"inputs": [], "source": {"source_run_id": report.tables.RUN_ID}}
        self.environment = mock.patch.dict("os.environ", {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": report.REPOSITORY,
            "GITHUB_RUN_ID": "9", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40,
            "GITHUB_REF": "refs/heads/report", "THESIS_WORKFLOW_SHA": "a" * 40,
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        from sklearn.tree import DecisionTreeClassifier
        parameters = DecisionTreeClassifier(random_state=0).get_params(deep=False)
        for seed in report.tables.source.EXPECTED_SEEDS:
            models, arms = {}, {}
            for arm, suffix in zip(report.tables.ARMS, ("chc", "lambda")):
                path = self.rows / f"seed-{seed}-{suffix}-model.joblib"
                path.write_bytes(b"opaque fixture - never deserialize")
                models[arm] = {"schema": "eu26-21-common-bridge-model-evidence-v1", "seed": seed, "arm": arm,
                               "mask": self.mask, "file": path.name, "bytes": path.stat().st_size,
                               "sha256": report.tables.source._file_sha256(path),
                               "selected_feature_names": [self.names[index] for index in (0, 7)],
                               "classifier_parameters": parameters}
                blocks = self.blocks()
                arms[arm] = {"test_evaluations": 1, "terminal": {
                    "mask": self.mask, "selected_feature_count": 2, "test_metrics": blocks,
                    "test_weighted_balanced_accuracy": blocks["weighted"]["balanced_accuracy"]}}
            self.write(self.rows / f"seed-{seed}.json", {
                "seed": seed, "models": models, "arms": arms,
                "provenance": {"run_id": report.tables.RUN_ID, "run_attempt": 1,
                               "implementation_sha": report.tables.SOURCE_SHA,
                               "workflow_sha": report.tables.SOURCE_SHA,
                               "protocol_sha256": report.tables.PROTOCOL_SHA, "ref": report.tables.SOURCE_REF}})
        self.refresh_paths()
        self.pinned_ledger = mock.patch.object(report, "EXPECTED_LEDGER_SHA", report.tables.source._file_sha256(self.expected))
        self.pinned_row = mock.patch.object(report, "EXAMPLE_ROW_SHA", report.tables.source._file_sha256(self.rows / "seed-41001.json"))
        self.pinned_ledger.start()
        self.pinned_row.start()
        self.addCleanup(self.pinned_ledger.stop)
        self.addCleanup(self.pinned_row.stop)
        self.base_loader = mock.patch.object(report.tables, "load_pairs", return_value=([], {}, self.provenance))
        self.base_loader.start()
        self.addCleanup(self.base_loader.stop)

    def blocks(self):
        return {"weighted": metric_block([[1000.5, 80.5], [30.2, 20.3]]),
                "unweighted": metric_block([[90000, 3000], [3000, 3762]]),
                "selected_feature_count": 2, "selected_predictive_indices": [0, 7],
                "selected_raw_indices": [0, 1],
                "selected_feature_names": [self.names[index] for index in (0, 7)]}

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")

    def refresh_paths(self):
        self.provenance["inputs"] = [{"path": path.name} for path in sorted(self.rows.iterdir())]

    def load(self):
        return report.load_class_data(self.rows, self.expected, self.verified)

    def test_all_pairs_and_classes_retained_without_deserialization(self):
        with mock.patch("joblib.load", side_effect=AssertionError("must not deserialize metrics")):
            rows, examples, mapping, _ = self.load()
        self.assertEqual(len(rows), 240)
        self.assertEqual(len(report.summarize_metrics(rows)), 8)
        self.assertEqual(set(examples), set(report.tables.ARMS))
        self.assertEqual(mapping, self.mapping)
        self.assertTrue(all(row["models"] == 30 for row in report.summarize_metrics(rows)))
        with self.assertRaisesRegex(ValueError, "every ordered seed"):
            report.summarize_metrics(rows[1:])

    def test_pinned_ledger_or_example_row_mutation_rejected(self):
        self.expected.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "artifact ledger SHA"):
            self.load()
        self.expected.write_text("fixture ledger", encoding="utf-8")
        row = self.rows / "seed-41001.json"
        row.write_bytes(row.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "example row SHA"):
            self.load()

    def test_model_bytes_and_feature_mapping_rejected(self):
        model = self.rows / "seed-41002-chc-model.joblib"
        model.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "model identity/bytes"):
            self.load()
        model.write_bytes(b"opaque fixture - never deserialize")
        path = self.rows / "seed-41002.json"
        row = report.tables.source._load_json(path)
        row["models"]["chc_harmonized"]["selected_feature_names"] = ["instance_weight", "age"]
        self.write(path, row)
        with self.assertRaisesRegex(ValueError, "selected feature names"):
            self.load()

    def test_bundle_rejected_before_loading_outside_ci_or_if_bytes_change(self):
        _, examples, _, _ = self.load()
        example = examples["chc_harmonized"]
        with mock.patch("joblib.load", side_effect=AssertionError("must not load")):
            with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}):
                with self.assertRaisesRegex(ValueError, "restricted"):
                    report._load_authenticated_model(example, "chc_harmonized")
            example["model_path"].write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "changed before deserialization"):
                report._load_authenticated_model(example, "chc_harmonized")

    def test_complete_report_inspects_saved_models_without_refit_predict_or_data_reads(self):
        import joblib
        import numpy as np
        import pandas as pd
        from corrected_applied import data_protocol as data
        from sklearn.tree import DecisionTreeClassifier
        raw = pd.DataFrame({index: np.arange(16, dtype=float) if index in data.NUMERIC_PREDICTIVE_POSITIONS
                            else ["A", "B"] * 8 for index in range(40)})
        preprocessing = data._build_preprocessor()
        transformed = preprocessing.fit_transform(raw)
        classifier = DecisionTreeClassifier(random_state=0).fit(transformed[:, [0, 7]], np.array([0, 0, 1, 1] * 4))
        path = self.rows / "seed-41001.json"
        row = report.tables.source._load_json(path)
        for arm, suffix in zip(report.tables.ARMS, ("chc", "lambda")):
            bundle = {"schema": "eu26-21-common-bridge-model-evidence-v1", "seed": 41001, "arm": arm,
                      "provenance": row["provenance"], "mask": self.mask, "selected_indices": [0, 7],
                      "feature_names": self.names, "classifier": classifier, "preprocessor": preprocessing}
            buffer = BytesIO()
            joblib.dump(bundle, buffer, compress=3)
            model = self.rows / f"seed-41001-{suffix}-model.joblib"
            model.write_bytes(buffer.getvalue())
            row["models"][arm].update(bytes=model.stat().st_size, sha256=report.tables.source._file_sha256(model))
        self.write(path, row)
        with mock.patch.object(report, "EXAMPLE_ROW_SHA", report.tables.source._file_sha256(path)):
            inputs = self.load()
            output = self.root / "report"
            with mock.patch.object(DecisionTreeClassifier, "fit", side_effect=AssertionError("no refit")), \
                    mock.patch.object(DecisionTreeClassifier, "predict", side_effect=AssertionError("no predict")), \
                    mock.patch.object(DecisionTreeClassifier, "predict_proba", side_effect=AssertionError("no predict_proba")), \
                    mock.patch.object(data, "_read_raw", side_effect=AssertionError("no census records")):
                report.write_report(*inputs, output)
        manifest = report.tables.source._load_json(output / "class-tree-manifest.json")
        self.assertFalse(manifest["matrices_pooled"])
        self.assertFalse(manifest["scientific_decisions_recomputed"])
        self.assertEqual(manifest["model_bundles_deserialized"], 2)
        self.assertEqual(manifest["model_fit_calls"], 0)
        self.assertEqual(len(manifest["outputs"]), 9)
        for name, entry in manifest["outputs"].items():
            self.assertEqual(report.tables.source._file_sha256(output / name), entry["sha256"])
        trees = report.tables.source._load_json(output / "tree-details.json")
        for tree in trees.values():
            self.assertEqual(tree["node_count"], classifier.tree_.node_count)
            self.assertFalse(tree["is_process_rss_measurement"])
            self.assertTrue(all(node["depth"] <= 2 for node in tree["top_three_levels"]))
            self.assertTrue(all(node["raw_index_0_based"] != 24 for node in tree["top_three_levels"] if not node["leaf"]))
            numeric = [node for node in tree["top_three_levels"] if node.get("encoding") == "standardized_numeric"]
            for node in numeric:
                scaler = preprocessing.named_transformers_["numeric"].named_steps["scale"]
                index = node["mask_index_0_based"]
                self.assertAlmostEqual(node["threshold_original_numeric"],
                                       node["threshold_processed"] * scaler.scale_[index] + scaler.mean_[index])


if __name__ == "__main__":
    unittest.main()

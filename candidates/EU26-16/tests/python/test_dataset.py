from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from eu2616.dataset import (
    DatasetFormatError,
    EvidenceGapError,
    assert_table7_replay_ready,
    audit_yeast,
    parse_arff,
    parse_label_xml,
    parse_yeast_config,
)

from support import CONTRACT, upstream


class YeastStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = audit_yeast(upstream(), CONTRACT)

    def test_input_dimension_is_103(self) -> None:
        self.assertEqual(len(self.audit.input_names), 103)
        self.assertEqual(self.audit.input_names[0], "Att1")
        self.assertEqual(self.audit.input_names[-1], "Att103")

    def test_label_dimension_is_14(self) -> None:
        self.assertEqual(len(self.audit.label_names), 14)
        self.assertEqual(set(self.audit.label_names), {f"Class{index}" for index in range(1, 15)})

    def test_fold_one_rows_match_paper_dimension(self) -> None:
        self.assertEqual(self.audit.train_rows, 1933)
        self.assertEqual(self.audit.test_rows, 484)
        self.assertEqual(self.audit.total_rows, 2417)

    def test_config_seed_list_is_incomplete(self) -> None:
        self.assertEqual(self.audit.seeds, (10, 20, 100))
        self.assertNotEqual(len(self.audit.seeds), CONTRACT["paper_protocol"]["random_seed_count"])

    def test_fold_two_is_referenced_but_missing(self) -> None:
        self.assertEqual(
            self.audit.missing_paths,
            ("data/Yeast/Yeast-train2.arff", "data/Yeast/Yeast-test2.arff"),
        )

    def test_all_mandatory_gaps_are_detected(self) -> None:
        self.assertEqual(set(self.audit.gaps), set(CONTRACT["blockers"]))
        self.assertFalse(self.audit.paper_replay_ready)

    def test_table_7_readiness_fails_closed(self) -> None:
        with self.assertRaises(EvidenceGapError) as context:
            assert_table7_replay_ready(self.audit, CONTRACT)
        self.assertIn("Table 7 replay is contractually disabled", str(context.exception))
        self.assertIn("DATASET_LICENSE_UNRESOLVED", str(context.exception))

    def test_config_parser_finds_two_fold_references(self) -> None:
        seeds, paths = parse_yeast_config(upstream() / "cfg/Yeast.xml")
        self.assertEqual(seeds, (10, 20, 100))
        self.assertEqual(len([path for path in paths if "train" in path.lower()]), 2)
        self.assertEqual(len([path for path in paths if "test" in path.lower()]), 2)

    def test_label_parser_preserves_xml_order(self) -> None:
        labels = parse_label_xml(upstream() / "data/Yeast/Yeast.xml")
        self.assertEqual(labels[:3], ("Class13", "Class12", "Class14"))

    def test_arff_train_and_test_declarations_match(self) -> None:
        train = parse_arff(upstream() / "data/Yeast/Yeast-train1.arff")
        test = parse_arff(upstream() / "data/Yeast/Yeast-test1.arff")
        self.assertEqual(train.attributes, test.attributes)
        self.assertEqual(len(train.attributes), 117)


class DatasetNegativeTests(unittest.TestCase):
    def test_arff_rejects_wrong_row_width(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.arff"
            path.write_text(
                "@relation X\n@attribute A numeric\n@attribute B numeric\n@data\n1\n",
                encoding="utf-8",
            )
            with self.assertRaises(DatasetFormatError):
                parse_arff(path)

    def test_arff_rejects_sparse_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.arff"
            path.write_text(
                "@relation X\n@attribute A numeric\n@data\n{0 1}\n",
                encoding="utf-8",
            )
            with self.assertRaises(DatasetFormatError):
                parse_arff(path)

    def test_label_xml_rejects_duplicate_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "labels.xml"
            path.write_text('<labels><label name="A"/><label name="A"/></labels>', encoding="utf-8")
            with self.assertRaises(DatasetFormatError):
                parse_label_xml(path)

    def test_config_rejects_missing_seed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.xml"
            path.write_text(
                "<experiment><dataset><train-dataset>x</train-dataset></dataset></experiment>",
                encoding="utf-8",
            )
            with self.assertRaises(DatasetFormatError):
                parse_yeast_config(path)


if __name__ == "__main__":
    unittest.main()

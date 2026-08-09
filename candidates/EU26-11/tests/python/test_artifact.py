from __future__ import annotations

import json
import math
import os
import pickle
import struct
import unittest
from pathlib import Path

from eu2611.artifact import (
    ArtifactError,
    extract_numeric_table,
    l2_star_discrepancy,
    parse_point_set,
)


CANDIDATE = Path(__file__).resolve().parents[2]
CONTRACT = json.loads(
    (CANDIDATE / "config" / "verification_contract.json").read_text(encoding="utf-8")
)


def point_payload(
    *,
    header: str = "n=4,k=2,dim=2, discrepancy=0.100000, runtime=1.000000",
    rows: tuple[str, ...] = ("0.250000 0.750000 ", "0.750000 0.250000 "),
    newline: bytes = b"\n",
) -> bytes:
    return newline.join([header.encode("ascii"), *(row.encode("ascii") for row in rows)]) + newline


class PointSetParserTests(unittest.TestCase):
    def parse(self, payload: bytes):
        return parse_point_set(
            payload,
            expected_header="n=4,k=2,dim=2, discrepancy=0.100000, runtime=1.000000",
            expected_rows=2,
            expected_dimension=2,
        )

    def test_parses_canonical_shape_and_metadata(self) -> None:
        observed = self.parse(point_payload())
        self.assertEqual((observed.rows, observed.dimension), (2, 2))
        self.assertEqual(observed.source_pool_size, 4)
        self.assertEqual(observed.points[0], (0.25, 0.75))

    def test_rejects_changed_header(self) -> None:
        with self.assertRaises(ArtifactError):
            self.parse(point_payload(header="n=5,k=2,dim=2, discrepancy=0.100000, runtime=1.000000"))

    def test_rejects_wrong_row_count(self) -> None:
        with self.assertRaises(ArtifactError):
            self.parse(point_payload(rows=("0.250000 0.750000 ",)))

    def test_rejects_wrong_dimension(self) -> None:
        with self.assertRaises(ArtifactError):
            self.parse(point_payload(rows=("0.250000 ", "0.750000 ")))

    def test_rejects_noncanonical_coordinate_format(self) -> None:
        for token in (".250000", "0.25", "+0.250000", "00.250000", "nan"):
            with self.subTest(token=token), self.assertRaises(ArtifactError):
                self.parse(point_payload(rows=(f"{token} 0.750000 ", "0.750000 0.250000 ")))

    def test_rejects_missing_trailing_space(self) -> None:
        with self.assertRaises(ArtifactError):
            self.parse(point_payload(rows=("0.250000 0.750000", "0.750000 0.250000 ")))

    def test_rejects_non_lf_or_missing_final_newline(self) -> None:
        with self.assertRaises(ArtifactError):
            self.parse(point_payload(newline=b"\r\n"))
        with self.assertRaises(ArtifactError):
            self.parse(point_payload()[:-1])

    def test_rejects_header_shape_conflict(self) -> None:
        payload = point_payload(
            header="n=4,k=3,dim=2, discrepancy=0.100000, runtime=1.000000"
        )
        with self.assertRaises(ArtifactError):
            parse_point_set(
                payload,
                expected_header=payload.decode("ascii").splitlines()[0],
                expected_rows=2,
                expected_dimension=2,
            )


class FormulaTests(unittest.TestCase):
    def test_one_point_one_dimension_closed_form(self) -> None:
        observed = l2_star_discrepancy([(0.5,)])
        self.assertAlmostEqual(observed, math.sqrt(1.0 / 12.0), places=15)

    def test_formula_rejects_empty_ragged_and_invalid_points(self) -> None:
        cases = ([], [(0.5,), (0.2, 0.3)], [(math.nan,)], [(-0.1,)], [(1.1,)])
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ArtifactError):
                l2_star_discrepancy(case)

    @unittest.skipUnless(os.environ.get("EU2611_POINT_SET"), "EU2611_POINT_SET not set")
    def test_authenticated_point_set_reproduces_frozen_cell(self) -> None:
        point_contract = CONTRACT["point_set"]
        parsed = parse_point_set(
            Path(os.environ["EU2611_POINT_SET"]).read_bytes(),
            expected_header=point_contract["header"],
            expected_rows=point_contract["rows"],
            expected_dimension=point_contract["dimension"],
        )
        observed = l2_star_discrepancy(parsed.points)
        endpoint = CONTRACT["endpoint"]
        self.assertLessEqual(
            abs(observed - float(endpoint["l2_star_reference"])),
            endpoint["l2_absolute_tolerance"],
        )
        self.assertEqual(format(math.log10(observed), ".2f"), endpoint["paper_display"])


class NumericBlockTests(unittest.TestCase):
    @staticmethod
    def encoded(values: tuple[float, ...]) -> bytes:
        return pickle.dumps(bytearray(struct.pack(f"<{len(values)}d", *values)), protocol=5)

    def test_extracts_inert_binary64_matrix_by_frozen_labels(self) -> None:
        table = extract_numeric_table(
            self.encoded((1.0, 2.0, 3.0, 4.0)),
            dimensions=(10, 20),
            algorithms=("A", "B"),
            expected_block_bytes=32,
        )
        self.assertEqual(table[("A", 10)], 1.0)
        self.assertEqual(table[("B", 20)], 4.0)

    def test_rejects_multiple_or_missing_binary_blocks(self) -> None:
        multiple = pickle.dumps(
            [bytearray(struct.pack("<d", 1.0)), bytearray(struct.pack("<d", 2.0))],
            protocol=5,
        )
        for payload in (multiple, pickle.dumps([1.0], protocol=5)):
            with self.subTest(payload=payload), self.assertRaises(ArtifactError):
                extract_numeric_table(
                    payload,
                    dimensions=(20,),
                    algorithms=("A",),
                    expected_block_bytes=8,
                )

    def test_rejects_wrong_block_size(self) -> None:
        with self.assertRaises(ArtifactError):
            extract_numeric_table(
                self.encoded((1.0, 2.0)),
                dimensions=(20,),
                algorithms=("A",),
                expected_block_bytes=8,
            )

    def test_rejects_nonfinite_and_nonpositive_values(self) -> None:
        for value in (0.0, -1.0, math.inf, math.nan):
            with self.subTest(value=value), self.assertRaises(ArtifactError):
                extract_numeric_table(
                    self.encoded((value,)),
                    dimensions=(20,),
                    algorithms=("A",),
                    expected_block_bytes=8,
                )

    @unittest.skipUnless(os.environ.get("EU2611_PICKLE"), "EU2611_PICKLE not set")
    def test_authenticated_numeric_block_matches_frozen_cell(self) -> None:
        numeric = CONTRACT["numeric_block"]
        table = extract_numeric_table(
            Path(os.environ["EU2611_PICKLE"]).read_bytes(),
            dimensions=numeric["dimensions"],
            algorithms=numeric["algorithms"],
            expected_block_bytes=numeric["binary64_block_bytes"],
        )
        endpoint = CONTRACT["endpoint"]
        observed = table[(endpoint["algorithm"], endpoint["dimension"])]
        self.assertLessEqual(
            abs(observed - float(endpoint["l2_star_reference"])),
            endpoint["l2_absolute_tolerance"],
        )


if __name__ == "__main__":
    unittest.main()

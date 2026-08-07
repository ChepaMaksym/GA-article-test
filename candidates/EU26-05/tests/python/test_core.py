from __future__ import annotations

from fractions import Fraction
import itertools
import json
import math
from pathlib import Path
import sys
import unittest


CANDIDATE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from eu2605.canonical import canonical_bytes, sha256_value  # noqa: E402
from eu2605.core import (  # noqa: E402
    ValidationError,
    binary_decode_anchor,
    fixture_report,
    hamming_distance,
    maximum_extension_crossover,
    objective_interface_anchor,
    one_point_crossover,
    post_selection_transition,
    update_probabilities,
)


class ProbabilityTests(unittest.TestCase):
    def test_frozen_examples(self) -> None:
        self.assertEqual(update_probabilities([0, 0, 0, 0], [1, 2, 3, 4]), (Fraction(1, 4),) * 4)
        self.assertEqual(
            update_probabilities([3, 0, 0, 0], [3, 4, 5, 6]),
            (Fraction(7, 10), Fraction(1, 10), Fraction(1, 10), Fraction(1, 10)),
        )
        self.assertEqual(
            update_probabilities([1, 2, 1, 0], [2, 4, 4, 8]),
            (Fraction(17, 50), Fraction(17, 50), Fraction(11, 50), Fraction(1, 10)),
        )

    def test_grid_preserves_simplex_and_floor(self) -> None:
        totals = (1, 2, 3, 4)
        for successes in itertools.product(*(range(total + 1) for total in totals)):
            values = update_probabilities(successes, totals)
            self.assertEqual(sum(values, Fraction(0, 1)), 1)
            self.assertTrue(all(Fraction(1, 10) <= value <= Fraction(7, 10) for value in values))

    def test_zero_denominator_always_rejects(self) -> None:
        for index in range(4):
            totals = [1, 1, 1, 1]
            totals[index] = 0
            with self.assertRaisesRegex(ValidationError, "denominator"):
                update_probabilities([0, 0, 0, 0], totals)

    def test_malformed_counts_reject(self) -> None:
        invalid = [
            ([1, 0, 0], [1, 1, 1, 1]),
            ([2, 0, 0, 0], [1, 1, 1, 1]),
            ([-1, 0, 0, 0], [1, 1, 1, 1]),
            ([True, 0, 0, 0], [1, 1, 1, 1]),
            ([1.0, 0, 0, 0], [1, 1, 1, 1]),
        ]
        for successes, totals in invalid:
            with self.subTest(successes=successes, totals=totals):
                with self.assertRaises(ValidationError):
                    update_probabilities(successes, totals)


class CrossoverTests(unittest.TestCase):
    @staticmethod
    def bitstrings(length: int) -> list[str]:
        return [format(value, f"0{length}b") for value in range(1 << length)]

    def test_one_point_is_hamming_geometric_exhaustively(self) -> None:
        values = self.bitstrings(4)
        checked = 0
        for first, second, cut in itertools.product(values, values, range(1, 4)):
            children = one_point_crossover(first, second, cut)
            for child in children:
                self.assertEqual(len(child), 4)
                self.assertEqual(
                    hamming_distance(first, child) + hamming_distance(child, second),
                    hamming_distance(first, second),
                )
            checked += 1
        self.assertEqual(checked, 768)

    def test_extension_is_thesis_profile_complement_origin_exhaustively(self) -> None:
        values = self.bitstrings(4)
        for first, second in itertools.product(values, values):
            children = maximum_extension_crossover(first, second)
            self.assertEqual(children[0], "".join("1" if bit == "0" else "0" for bit in first))
            self.assertEqual(children[1], "".join("1" if bit == "0" else "0" for bit in second))

    def test_extension_has_non_geometric_witness(self) -> None:
        child, _ = maximum_extension_crossover("0000", "0000")
        self.assertEqual(child, "1111")
        self.assertNotEqual(
            hamming_distance("0000", child) + hamming_distance(child, "0000"),
            hamming_distance("0000", "0000"),
        )

    def test_transition_labels_and_frozen_tape(self) -> None:
        first = post_selection_transition("00001111", "11110000", 0, cut=4)
        self.assertEqual(first["children"], ["00000000", "11111111"])
        extension = post_selection_transition("001101", "011001", 3, cut=None)
        self.assertEqual(extension["children"], ["110010", "100110"])
        self.assertEqual(extension["operator"], "thesis_maximum_extension_complement_origin")

    def test_invalid_transitions_reject(self) -> None:
        callbacks = [
            lambda: one_point_crossover("0", "1", 1),
            lambda: one_point_crossover("00", "0", 1),
            lambda: one_point_crossover("00", "01", 0),
            lambda: one_point_crossover("00", "01", 2),
            lambda: maximum_extension_crossover("0x", "00"),
            lambda: post_selection_transition("00", "11", 4, cut=1),
            lambda: post_selection_transition("00", "11", 0, cut=None),
            lambda: post_selection_transition("00", "11", 3, cut=1),
        ]
        for callback in callbacks:
            with self.subTest(callback=callback):
                with self.assertRaises(ValidationError):
                    callback()


class DecodeAndObjectiveTests(unittest.TestCase):
    def test_explicit_decode_endpoints_and_orders(self) -> None:
        arguments = {"lower": -100.0, "upper": 100.0, "endpoint_convention": "closed_linear"}
        self.assertEqual(binary_decode_anchor("0000", bit_order="msb_first", **arguments), -100.0)
        self.assertEqual(binary_decode_anchor("1111", bit_order="msb_first", **arguments), 100.0)
        self.assertAlmostEqual(binary_decode_anchor("1000", bit_order="msb_first", **arguments), 100 / 15)
        self.assertAlmostEqual(binary_decode_anchor("1000", bit_order="lsb_first", **arguments), -1300 / 15)

    def test_decode_requires_every_missing_convention(self) -> None:
        callbacks = [
            lambda: binary_decode_anchor("", -1, 1, bit_order="msb_first", endpoint_convention="closed_linear"),
            lambda: binary_decode_anchor("01x", -1, 1, bit_order="msb_first", endpoint_convention="closed_linear"),
            lambda: binary_decode_anchor("01", -1, 1, bit_order="unknown", endpoint_convention="closed_linear"),
            lambda: binary_decode_anchor("01", -1, 1, bit_order="msb_first", endpoint_convention="half_open"),
            lambda: binary_decode_anchor("01", 1, -1, bit_order="msb_first", endpoint_convention="closed_linear"),
            lambda: binary_decode_anchor("01", math.nan, 1, bit_order="msb_first", endpoint_convention="closed_linear"),
        ]
        for callback in callbacks:
            with self.subTest(callback=callback):
                with self.assertRaises(ValidationError):
                    callback()

    def test_objective_anchor_is_toy_only(self) -> None:
        result = objective_interface_anchor(
            "0" * 600,
            lambda coordinates: sum(value * value for value in coordinates),
            bit_order="msb_first",
            endpoint_convention="closed_linear",
        )
        self.assertEqual(len(result["coordinates"]), 30)
        self.assertEqual(result["coordinates"], [-100.0] * 30)
        self.assertEqual(result["value"], 300000.0)
        self.assertEqual(result["objective_kind"], "toy_injected")

    def test_objective_anchor_rejects_cec_claim_and_bad_shape(self) -> None:
        with self.assertRaisesRegex(ValidationError, "authenticated CEC"):
            objective_interface_anchor(
                "0" * 600,
                sum,
                bit_order="msb_first",
                endpoint_convention="closed_linear",
                claimed_authenticated_cec=True,
            )
        with self.assertRaisesRegex(ValidationError, "600"):
            objective_interface_anchor(
                "0" * 599,
                sum,
                bit_order="msb_first",
                endpoint_convention="closed_linear",
            )


class FixtureAndCanonicalTests(unittest.TestCase):
    def test_shared_fixture_report_is_exact(self) -> None:
        fixture = json.loads(
            (CANDIDATE / "fixtures" / "formula_transition_cases.json").read_text(encoding="utf-8")
        )
        report = fixture_report(fixture)
        self.assertEqual(
            sha256_value(report),
            "6f560ccd36492e9fb1c4057d67ea2e54fffa032e72ddd02557bad077aacaf502",
        )
        self.assertEqual(report["source_byte_status"], "PASS_METADATA_ONLY")
        self.assertEqual(report["source_freeze_status"], "BLOCKED_SOURCE_BYTE_FREEZE")
        self.assertEqual(
            report["h0_source_status"],
            "PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE",
        )
        self.assertNotIn("PASS_FULL", canonical_bytes(report).decode("utf-8"))

    def test_canonical_payload_rejects_nonfinite(self) -> None:
        with self.assertRaisesRegex(ValueError, "NaN or Inf"):
            canonical_bytes({"bad": math.nan})


if __name__ == "__main__":
    unittest.main()

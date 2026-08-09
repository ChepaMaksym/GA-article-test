from __future__ import annotations

import json
import unittest
from copy import deepcopy

from eu2612.artifact import ArtifactError, parse_companion_dat, parse_endpoint
from eu2612.contract import load_contract
from test_support import synthetic_dat, synthetic_ioh_json


class JsonArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()
        self.payload = synthetic_ioh_json(self.contract)

    def test_frozen_endpoint_shape_passes(self) -> None:
        result = parse_endpoint(self.payload, self.contract)
        self.assertEqual(result.run_count, 50)
        self.assertEqual(result.best_y_decimal, "1.698652750709869e-14")
        self.assertEqual(result.run_evaluations[29], 46461)

    def test_duplicate_root_key_fails(self) -> None:
        payload = self.payload.replace(b'{\n  "version"', b'{\n  "version": "0.3.5",\n  "version"', 1)
        with self.assertRaises(ArtifactError):
            parse_endpoint(payload, self.contract)

    def test_wrong_algorithm_fails(self) -> None:
        payload = self.payload.replace(b'"name": "L-SHADE"', b'"name": "SHADE"')
        with self.assertRaises(ArtifactError):
            parse_endpoint(payload, self.contract)

    def test_wrong_dimension_fails(self) -> None:
        payload = self.payload.replace(b'"dimension": 20', b'"dimension": 10')
        with self.assertRaises(ArtifactError):
            parse_endpoint(payload, self.contract)

    def test_run_order_mutation_fails(self) -> None:
        value = json.loads(self.payload)
        value["scenarios"][0]["runs"][5]["instance"] = 0
        with self.assertRaises(ArtifactError):
            parse_endpoint(json.dumps(value).encode(), self.contract)

    def test_run_count_mutation_fails(self) -> None:
        value = json.loads(self.payload)
        value["scenarios"][0]["runs"].pop()
        with self.assertRaises(ArtifactError):
            parse_endpoint(json.dumps(value).encode(), self.contract)

    def test_selected_evaluation_mutation_fails(self) -> None:
        value = json.loads(self.payload)
        value["scenarios"][0]["runs"][0]["best"]["evals"] += 1
        with self.assertRaises(ArtifactError):
            parse_endpoint(json.dumps(value).encode(), self.contract)

    def test_endpoint_literal_duplicate_fails(self) -> None:
        payload = self.payload.replace(b"2e-14", b"1.698652750709869e-14", 1)
        with self.assertRaises(ArtifactError):
            parse_endpoint(payload, self.contract)

    def test_non_finite_json_fails(self) -> None:
        payload = self.payload.replace(b"2e-14", b"NaN", 1)
        with self.assertRaises(ArtifactError):
            parse_endpoint(payload, self.contract)

    def test_carriage_return_fails(self) -> None:
        with self.assertRaises(ArtifactError):
            parse_endpoint(self.payload.replace(b"\n", b"\r\n"), self.contract)

    def test_best_vector_dimension_fails(self) -> None:
        value = json.loads(self.payload)
        value["scenarios"][0]["runs"][0]["best"]["x"].pop()
        with self.assertRaises(ArtifactError):
            parse_endpoint(json.dumps(value).encode(), self.contract)


class DatArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()
        self.endpoint = parse_endpoint(synthetic_ioh_json(self.contract), self.contract)
        self.payload = synthetic_dat(self.endpoint.run_evaluations)

    def test_companion_dat_passes_and_remains_diagnostic(self) -> None:
        result = parse_companion_dat(
            self.payload, self.contract, expected_run_evaluations=self.endpoint.run_evaluations
        )
        self.assertEqual(result.run_count, 50)
        self.assertEqual(result.first_run_final_raw_y, "0.0000000000")

    def test_dat_run_count_fails(self) -> None:
        first = self.payload.find(b"evaluations raw_y")
        second = self.payload.find(b"evaluations raw_y", first + 1)
        with self.assertRaises(ArtifactError):
            parse_companion_dat(self.payload[:second], self.contract)

    def test_dat_noncanonical_decimal_fails(self) -> None:
        payload = self.payload.replace(b"1.0000000000", b"1.0", 1)
        with self.assertRaises(ArtifactError):
            parse_companion_dat(payload, self.contract)

    def test_dat_json_evaluation_mismatch_fails(self) -> None:
        expected = list(self.endpoint.run_evaluations)
        expected[0] -= 1
        with self.assertRaises(ArtifactError):
            parse_companion_dat(self.payload, self.contract, expected_run_evaluations=expected)

    def test_dat_non_increasing_evaluations_fail(self) -> None:
        payload = self.payload.replace(b"1 1.0000000000", b"50002 1.0000000000", 1)
        with self.assertRaises(ArtifactError):
            parse_companion_dat(payload, self.contract)


if __name__ == "__main__":
    unittest.main()

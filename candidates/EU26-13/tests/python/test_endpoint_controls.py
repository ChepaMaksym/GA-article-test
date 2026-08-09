from __future__ import annotations

import copy
import json
import unittest

from eu2613.contract import load_contract
from eu2613.controls import BIPOPState, hill_valley, run_controls, seed_schedule
from eu2613.endpoint import validate_endpoint
from eu2613.errors import VerificationError

from fixture_builders import endpoint_bytes, make_endpoint_document


class EndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract()
        cls.document = make_endpoint_document(cls.contract)

    def test_endpoint_fixture(self) -> None:
        report = validate_endpoint(endpoint_bytes(self.document), self.contract)
        self.assertEqual(report["best_y_decimal"], "7.379046076174201e-09")
        self.assertEqual(report["inferred_seed"], 0)

    def reject(self, mutator) -> None:
        document = copy.deepcopy(self.document)
        mutator(document)
        with self.assertRaises(VerificationError):
            validate_endpoint(endpoint_bytes(document), self.contract)

    def test_mutation_scenario_order(self) -> None:
        self.reject(lambda d: d["scenarios"].__setitem__(0, d["scenarios"][1]))

    def test_mutation_selected_run_count(self) -> None:
        self.reject(lambda d: d["scenarios"][3]["runs"].pop())

    def test_mutation_instance_order(self) -> None:
        self.reject(lambda d: d["scenarios"][3]["runs"][50].__setitem__("instance", 1))

    def test_mutation_target_decimal(self) -> None:
        self.reject(lambda d: d["scenarios"][3]["runs"][0]["best"].__setitem__("y", 7.38e-9))

    def test_mutation_target_evals(self) -> None:
        self.reject(lambda d: d["scenarios"][3]["runs"][0].__setitem__("evals", 2172))

    def test_mutation_target_best_evals(self) -> None:
        self.reject(lambda d: d["scenarios"][3]["runs"][0]["best"].__setitem__("evals", 2172))

    def test_mutation_target_vector_length(self) -> None:
        self.reject(lambda d: d["scenarios"][3]["runs"][0]["best"]["x"].pop())

    def test_mutation_other_scenario_vector_length(self) -> None:
        self.reject(lambda d: d["scenarios"][0]["runs"][0]["best"]["x"].pop())

    def test_mutation_algorithm(self) -> None:
        self.reject(lambda d: d["algorithm"].__setitem__("name", "other"))

    def test_mutation_root_key_order(self) -> None:
        document = copy.deepcopy(self.document)
        version = document.pop("version")
        document["version"] = version
        with self.assertRaises(VerificationError):
            validate_endpoint(endpoint_bytes(document), self.contract)

    def test_mutation_duplicate_json_key(self) -> None:
        raw = endpoint_bytes(self.document)
        raw = raw.replace(b'{"version":', b'{"version":"bad","version":', 1)
        with self.assertRaises(VerificationError):
            validate_endpoint(raw, self.contract)

    def test_mutation_nonfinite_json(self) -> None:
        raw = endpoint_bytes(self.document)
        raw = raw.replace(b'"y":7.379046076174201e-09', b'"y":NaN', 1)
        with self.assertRaises(VerificationError):
            validate_endpoint(raw, self.contract)

    def test_mutation_quoted_numeric_token(self) -> None:
        raw = endpoint_bytes(self.document)
        raw = raw.replace(
            b'"y":7.379046076174201e-09',
            b'"y":"7.379046076174201e-09"',
            1,
        )
        with self.assertRaises(VerificationError):
            validate_endpoint(raw, self.contract)


class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract()

    def test_controls(self) -> None:
        self.assertEqual(run_controls(self.contract)["status"], "PASS_INDEPENDENT_CONTROLS")

    def test_seed_schedule_instance_major(self) -> None:
        schedule = seed_schedule(2, 3, 42)
        self.assertEqual(schedule, [[1, 0, 0], [1, 1, 42], [1, 2, 84], [2, 0, 0], [2, 1, 42], [2, 2, 84]])

    def test_bipop_tie_selects_large(self) -> None:
        state = BIPOPState(12, 0.5, 200_000)
        result = state.restart(1_000, 0.5, 0.0, 2.0)
        self.assertTrue(result["selected_large"])
        self.assertEqual(result["lambda"], 24)

    def test_hill_valley_equality_is_same(self) -> None:
        self.assertEqual(hill_valley(1.0, 2.0, [2.0, 2.0, 2.0]), (True, 3))

    def test_hill_valley_strict_barrier_stops(self) -> None:
        self.assertEqual(hill_valley(1.0, 2.0, [1.0, 2.1, 1.0]), (False, 2))

    def reject_control(self, mutator) -> None:
        contract = copy.deepcopy(self.contract)
        mutator(contract)
        with self.assertRaises(VerificationError):
            run_controls(contract)

    def test_mutation_seed_multiplier(self) -> None:
        self.reject_control(lambda c: c["control_fixtures"]["seed_schedule"].__setitem__("seed_multiplier", 41))

    def test_mutation_first_bipop_lambda(self) -> None:
        self.reject_control(lambda c: c["control_fixtures"]["bipop"]["first_restart"].__setitem__("expected_lambda", 23))

    def test_mutation_second_bipop_sigma(self) -> None:
        self.reject_control(lambda c: c["control_fixtures"]["bipop"]["second_restart"].__setitem__("expected_sigma", 0.1))

    def test_mutation_repelling_radius(self) -> None:
        self.reject_control(lambda c: c["control_fixtures"]["repelling_radius"].__setitem__("expected_radius", 8.0))

    def test_mutation_csa(self) -> None:
        self.reject_control(lambda c: c["control_fixtures"]["csa"].__setitem__("expected_sigma", 2.0))

    def test_mutation_hill_fractions(self) -> None:
        self.reject_control(lambda c: c["control_fixtures"]["hill_valley"].__setitem__("expected_interpolation_fractions", [0.2, 0.5, 0.8]))


if __name__ == "__main__":
    unittest.main()

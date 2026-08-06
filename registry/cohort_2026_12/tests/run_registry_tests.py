#!/usr/bin/env python3
"""Mutation tests for the fail-closed cohort registry validator."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


COHORT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = COHORT / "validate_registry.py"
SPEC = importlib.util.spec_from_file_location("cohort_validator", VALIDATOR_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def load(name: str):
    with (COHORT / name).open(encoding="utf-8") as handle:
        return json.load(handle)


class RegistryValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load("registry.json")
        self.assessments = load("hard_gate_assessments.json")
        self.definitions = load("gate_definitions.json")

    def validate(
        self,
        registry=None,
        assessments=None,
        definitions=None,
        ranking="rank,candidate_id,final_score,title,doi\n",
    ):
        registry = copy.deepcopy(self.registry if registry is None else registry)
        assessments = copy.deepcopy(self.assessments if assessments is None else assessments)
        definitions = copy.deepcopy(self.definitions if definitions is None else definitions)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "registry.json"
            assessments_path = root / "assessments.json"
            definitions_path = root / "definitions.json"
            ranking_path = root / "ranking.csv"
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            assessments_path.write_text(json.dumps(assessments), encoding="utf-8")
            definitions_path.write_text(json.dumps(definitions), encoding="utf-8")
            ranking_path.write_text(ranking, encoding="utf-8")
            return validator.validate_paths(
                registry_path=registry_path,
                assessments_path=assessments_path,
                definitions_path=definitions_path,
                ranking_path=ranking_path,
                old_registry_path=validator.OLD_REGISTRY_PATH,
            )

    def test_frozen_registry_passes(self):
        summary = self.validate()
        self.assertEqual(summary["records"], 12)
        self.assertEqual(summary["hard_pass_ids"], [])

    def test_duplicate_doi_fails(self):
        registry = copy.deepcopy(self.registry)
        registry[1]["doi"] = registry[0]["doi"]
        with self.assertRaisesRegex(validator.ValidationError, "Duplicate DOI"):
            self.validate(registry=registry)

    def test_inverse_scope_fails(self):
        registry = copy.deepcopy(self.registry)
        registry[0]["direct_not_inverse"] = False
        with self.assertRaisesRegex(validator.ValidationError, "direct-only scope"):
            self.validate(registry=registry)

    def test_noneligible_score_fails(self):
        registry = copy.deepcopy(self.registry)
        registry[0]["final_score"] = 99
        with self.assertRaisesRegex(validator.ValidationError, "null final_score"):
            self.validate(registry=registry)

    def test_missing_adaptation_boundary_fails(self):
        assessments = copy.deepcopy(self.assessments)
        del assessments[0]["g5"]["boundary_behavior"]
        with self.assertRaisesRegex(validator.ValidationError, "boundary_behavior"):
            self.validate(assessments=assessments)

    def test_figure_only_target_cannot_pass(self):
        assessments = copy.deepcopy(self.assessments)
        target = next(item for item in assessments if item["candidate_id"] == "USA26-04")
        target["g8"]["numeric_targets"] = []
        with self.assertRaisesRegex(validator.ValidationError, "literal numeric target"):
            self.validate(assessments=assessments)

    def test_claimed_code_requires_source_native_replay(self):
        assessments = copy.deepcopy(self.assessments)
        target = next(item for item in assessments if item["candidate_id"] == "EU26-02")
        target["g10"]["source_native_replay_possible"] = False
        with self.assertRaisesRegex(validator.ValidationError, "source-native replay"):
            self.validate(assessments=assessments)

    def test_unresolved_gate_cannot_be_labeled_hard_pass(self):
        registry = copy.deepcopy(self.registry)
        registry[0]["eligibility_status"] = "hard_pass"
        registry[0]["final_score"] = 100
        with self.assertRaisesRegex(validator.ValidationError, "must be 'conditional_noneligible'"):
            self.validate(registry=registry)

    def test_gate_numbering_cannot_drift(self):
        for gate_id in (f"g{i}" for i in range(3, 11)):
            with self.subTest(gate_id=gate_id):
                definitions = copy.deepcopy(self.definitions)
                definitions["adaptive_hard_gates"][gate_id]["name"] = "shifted_or_weakened_gate"
                with self.assertRaisesRegex(validator.ValidationError, f"{gate_id} semantic name"):
                    self.validate(definitions=definitions)

    def test_required_gate_fields_cannot_be_weakened(self):
        for gate_id in (f"g{i}" for i in range(3, 11)):
            with self.subTest(gate_id=gate_id):
                definitions = copy.deepcopy(self.definitions)
                definitions["adaptive_hard_gates"][gate_id]["required_fields"].pop()
                with self.assertRaisesRegex(validator.ValidationError, f"{gate_id} required fields"):
                    self.validate(definitions=definitions)


if __name__ == "__main__":
    unittest.main(verbosity=2)

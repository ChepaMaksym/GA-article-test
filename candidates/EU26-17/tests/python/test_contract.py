from __future__ import annotations

import json
from pathlib import Path
import unittest


CANDIDATE_ROOT = Path(__file__).resolve().parents[2]


class ContractTests(unittest.TestCase):
    def test_hard_fail_and_null_endpoint_are_immutable(self) -> None:
        contract = json.loads(
            (CANDIDATE_ROOT / "config" / "verification_contract.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            contract["artifact_scope"],
            "FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY",
        )
        self.assertEqual(contract["eligibility_status"], "HARD_FAIL")
        self.assertIsNone(contract["eligibility_score"])
        self.assertIsNone(contract["published_numeric_endpoint"])
        self.assertIsNone(contract["acceptance_tolerance"])
        for forbidden in (
            "PASS_FULL",
            "PASS_CEC_EMPIRICAL_REPLAY",
            "PASS_LITERAL_PAPER_ENDPOINT",
            "AUTHOR_PINNED_EXPERIMENT_CORE",
            "HISTORICAL_EXECUTION_REVISION_PROVEN",
        ):
            self.assertIn(forbidden, contract["forbidden_claims"])

    def test_amendment_corrects_only_direct_dimension_and_input_gates(self) -> None:
        amendment = json.loads(
            (CANDIDATE_ROOT / "config" / "amendment-001.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(amendment["frozen_before_validation"])
        self.assertEqual(amendment["overrides"]["direct_only"], "pass")
        self.assertEqual(
            amendment["overrides"]["c2_meaningful_applied_parameters"], "pass"
        )
        self.assertEqual(amendment["overrides"]["c2_count"], 18)
        self.assertEqual(
            amendment["overrides"]["g7_lawful_reproducible_inputs"], "pass"
        )
        self.assertEqual(amendment["unchanged"]["eligibility_status"], "HARD_FAIL")
        self.assertEqual(
            amendment["unchanged"]["decisive_failure"],
            "G8_NO_LITERAL_UNAMBIGUOUS_NUMERIC_PAPER_CELL",
        )
        self.assertIsNone(amendment["unchanged"]["published_numeric_endpoint"])

    def test_preregistration_never_freezes_approximate_prose_as_target(self) -> None:
        texts = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((CANDIDATE_ROOT / "preregistration").glob("*.md"))
        )
        self.assertIn("Approximate", texts)
        self.assertNotIn("acceptance target: ~", texts)
        self.assertNotIn("numeric endpoint: ~", texts)

    def test_object_amendment_resolves_prefix_without_changing_scope(self) -> None:
        amendment = json.loads(
            (CANDIDATE_ROOT / "config" / "amendment-002.json").read_text(
                encoding="utf-8"
            )
        )
        source = amendment["algorithm_addition"]
        self.assertEqual(len(source["requested_revision"]), 39)
        self.assertEqual(len(source["resolved_commit"]), 40)
        self.assertTrue(source["resolved_commit"].startswith(source["requested_revision"]))
        self.assertTrue(source["require_unique_resolution"])
        self.assertTrue(source["require_report_both_names"])
        self.assertEqual(amendment["unchanged"]["eligibility_status"], "HARD_FAIL")
        self.assertIsNone(amendment["unchanged"]["published_numeric_endpoint"])


if __name__ == "__main__":
    unittest.main()

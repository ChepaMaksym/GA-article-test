from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import unittest


CANDIDATE = Path(__file__).resolve().parents[2]


class ProtocolTests(unittest.TestCase):
    def test_frozen_cell_and_forbidden_full_pass(self):
        protocol = json.loads(
            (CANDIDATE / "config" / "frozen_protocol.json").read_text(encoding="utf-8")
        )
        self.assertEqual(protocol["scope"], "ARCHIVE_AND_FORMULA_VALIDATION_ONLY")
        self.assertFalse(protocol["pass_full_allowed"])
        self.assertEqual(protocol["eligibility_status"], "conditional_noneligible")
        self.assertEqual(protocol["overall_status"], "BLOCKED_SOURCE_NATIVE_REPLAY")
        self.assertEqual(protocol["paper"]["algorithm"], "TwoRate")
        self.assertEqual(protocol["paper"]["indicator"], "HV")
        self.assertEqual(protocol["paper"]["dimension"], 100)
        self.assertEqual(protocol["paper"]["lambda"], 10)
        self.assertEqual(protocol["paper"]["runs"], 100)

    def test_exact_archive_member_is_bound_in_both_manifest_and_config(self):
        protocol = json.loads(
            (CANDIDATE / "config" / "frozen_protocol.json").read_text(encoding="utf-8")
        )
        with (CANDIDATE / "source_manifest" / "sources.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            rows = {row["source_id"]: row for row in csv.DictReader(handle)}
        archive = protocol["archive"]
        self.assertEqual(rows["ZENODO_CSV_ZIP"]["bytes"], str(archive["bytes"]))
        self.assertEqual(rows["ZENODO_CSV_ZIP"]["sha256"], archive["sha256"])
        self.assertEqual(rows["FOCUS_CSV_MEMBER"]["revision_or_path"], archive["member"])
        self.assertEqual(rows["FOCUS_CSV_MEMBER"]["sha256"], archive["member_sha256"])

    def test_contract_retains_explicit_four_six_conflict_and_claim_limit(self):
        contract = (
            CANDIDATE / "preregistration" / "archive_and_formula_validation_contract.md"
        ).read_text(encoding="utf-8")
        audit = (CANDIDATE / "source_manifest" / "audit_notes.md").read_text(
            encoding="utf-8"
        )
        amendment = (
            CANDIDATE / "preregistration" / "amendment-001-indexing-clarification.md"
        ).read_text(encoding="utf-8")
        combined = contract + audit + amendment
        self.assertIn("5/5", combined)
        self.assertIn("4/6", combined)
        self.assertIn("PASS_FULL", combined)
        self.assertIn("BLOCKED_SOURCE_NATIVE_REPLAY", combined)

    def test_fixture_is_candidate_specific_and_stable(self):
        fixture_path = CANDIDATE / "fixtures" / "tworate_fixed_tape.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        bindings = json.loads(
            (CANDIDATE / "config" / "hardware_expected_digests.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(fixture["candidate_id"], "EU26-01")
        self.assertEqual(fixture["tie_policy"], "first_maximum")
        self.assertEqual(len(fixture["generation_cases"][0]["children"]), 10)
        self.assertEqual(
            len(fixture["generation_cases"][0]["population_bits"][0]), 100
        )
        self.assertEqual(
            hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
            bindings["fixture_file_sha256"],
        )

    def test_post_freeze_binding_preserves_exact_unrounded_statistics(self):
        bindings = json.loads(
            (CANDIDATE / "config" / "hardware_expected_digests.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(bindings["binding_kind"], "post_freeze_exact_object_output_binding")
        self.assertEqual(bindings["complete_runs"], 100)
        self.assertEqual(bindings["completion_sum"], 6162378)
        self.assertEqual(bindings["mean_exact"], "61623.78")
        self.assertEqual(bindings["population_variance_exact"], "327085104.6716")
        self.assertFalse(bindings["pass_full_allowed"])


if __name__ == "__main__":
    unittest.main()

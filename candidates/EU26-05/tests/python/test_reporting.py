from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest


CANDIDATE = Path(__file__).resolve().parents[2]
REPOSITORY = CANDIDATE.parents[1]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))
sys.path.insert(0, str(CANDIDATE / "tests"))

from eu2605.canonical import (  # noqa: E402
    StrictJSONError,
    sha256_value,
    strict_json_load,
    strict_json_loads,
)
from eu2605.core import ValidationError, fixture_report  # noqa: E402
from eu2605.reporting import (  # noqa: E402
    git_head,
    matlab_implementation_paths,
    python_implementation_paths,
    source_digest,
    source_hash_rows,
)
import compare_fixture_reports as cross_language  # noqa: E402


class StrictJSONTests(unittest.TestCase):
    def test_duplicate_key_rejects(self) -> None:
        with self.assertRaisesRegex(StrictJSONError, "duplicate"):
            strict_json_loads('{"case":1,"case":2}')

    def test_nonfinite_constants_reject(self) -> None:
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(StrictJSONError, "non-finite"):
                    strict_json_loads(f'{{"case":{value}}}')

    def test_fixture_extra_field_rejects(self) -> None:
        fixture = strict_json_load(CANDIDATE / "fixtures" / "formula_transition_cases.json")
        fixture["unexpected"] = False
        with self.assertRaisesRegex(ValidationError, "schema"):
            fixture_report(fixture)

    def test_fixture_case_identity_mutation_rejects(self) -> None:
        fixture = strict_json_load(CANDIDATE / "fixtures" / "formula_transition_cases.json")
        fixture["transition_cases"][0]["id"] = "copied-case"
        with self.assertRaisesRegex(ValidationError, "identities"):
            fixture_report(fixture)


class IndependentReportMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture = strict_json_load(CANDIDATE / "fixtures" / "formula_transition_cases.json")
        payload = fixture_report(fixture)
        digest = sha256_value(payload)
        head = git_head(REPOSITORY)

        python_rows = source_hash_rows(python_implementation_paths(CANDIDATE), REPOSITORY)
        cls.python_report = {
            "schema_version": "1.0.0",
            "report_kind": "EU26-05-INDEPENDENT-FIXTURE-v1",
            "implementation": "python",
            "git_head": head,
            "runtime": {"engine": "python", "version": "unit", "platform": "unit"},
            "implementation_source_hashes": python_rows,
            "implementation_source_digest": source_digest(python_rows),
            "h0_source_status": "PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE",
            "source_byte_status": "PASS_METADATA_ONLY",
            "source_freeze_status": "BLOCKED_SOURCE_BYTE_FREEZE",
            "semantic_payload": copy.deepcopy(payload),
            "semantic_payload_sha256": digest,
        }

        matlab_rows = source_hash_rows(matlab_implementation_paths(CANDIDATE), REPOSITORY)
        cls.matlab_report = {
            "schema_version": "1.0.0",
            "report_kind": "EU26-05-INDEPENDENT-FIXTURE-v1",
            "implementation": "matlab_octave",
            "git_head": head,
            "runtime": {"engine": "octave", "version": "unit", "platform": "unit"},
            "implementation_source_hashes": matlab_rows,
            "implementation_source_digest": source_digest(matlab_rows),
            "h0_source_status": "PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE",
            "source_byte_status": "PASS_METADATA_ONLY",
            "source_freeze_status": "BLOCKED_SOURCE_BYTE_FREEZE",
            "semantic_payload": copy.deepcopy(payload),
            "semantic_payload_sha256": digest,
        }

    def test_independently_bound_envelopes_pass(self) -> None:
        summary = cross_language.compare_reports(self.python_report, self.matlab_report)
        self.assertEqual(summary["status"], "PASS_H3_CROSS_LANGUAGE_FIXED_TAPE")
        self.assertNotEqual(summary["python_source_digest"], summary["matlab_octave_source_digest"])
        self.assertIs(summary["published_27_of_30_evaluated"], False)

    def test_minimal_matlab_report_rejects(self) -> None:
        with self.assertRaisesRegex(ValueError, "schema"):
            cross_language.compare_reports(
                self.python_report,
                {"implementation": "matlab_octave"},
            )

    def test_copied_python_report_cannot_pose_as_matlab(self) -> None:
        copied = copy.deepcopy(self.python_report)
        copied["implementation"] = "matlab_octave"
        copied["runtime"]["engine"] = "octave"
        with self.assertRaisesRegex(ValueError, "source hashes"):
            cross_language.compare_reports(self.python_report, copied)

    def test_forged_matlab_payload_rejects(self) -> None:
        forged = copy.deepcopy(self.matlab_report)
        forged["semantic_payload"]["transition_cases"][0]["children"][0] = "1" * 8
        with self.assertRaisesRegex(ValueError, "semantic fixture payload"):
            cross_language.compare_reports(self.python_report, forged)

    def test_matlab_source_hash_mutation_rejects(self) -> None:
        forged = copy.deepcopy(self.matlab_report)
        forged["implementation_source_hashes"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source hashes"):
            cross_language.compare_reports(self.python_report, forged)


if __name__ == "__main__":
    unittest.main()

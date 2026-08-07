from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
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
    exclusive_write_bytes,
    git_head,
    matlab_implementation_paths,
    prepare_exclusive_outputs,
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

    def test_overflowing_finite_syntax_rejects(self) -> None:
        with self.assertRaisesRegex(StrictJSONError, "overflows"):
            strict_json_loads('{"case":1e9999}')

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
            "execution_authentication": "SELF_ASSERTED_RUNTIME_CONTEXT_ONLY",
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
            "execution_authentication": "SELF_ASSERTED_RUNTIME_CONTEXT_ONLY",
            "h0_source_status": "PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE",
            "source_byte_status": "PASS_METADATA_ONLY",
            "source_freeze_status": "BLOCKED_SOURCE_BYTE_FREEZE",
            "semantic_payload": copy.deepcopy(payload),
            "semantic_payload_sha256": digest,
        }

    def test_independently_bound_envelopes_pass(self) -> None:
        summary = cross_language.compare_reports(self.python_report, self.matlab_report)
        self.assertEqual(summary["status"], "PASS_H3_PAYLOAD_FORMULA_EQUIVALENCE_ONLY")
        self.assertEqual(
            summary["native_runtime_execution_status"],
            "NOT_EVALUATED_EXTERNAL_EXECUTION_AUTH_REQUIRED",
        )
        self.assertIs(summary["offline_comparison_authorizes_native_execution"], False)
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

    def test_python_forged_octave_envelope_never_authenticates_execution(self) -> None:
        forged = copy.deepcopy(self.matlab_report)
        forged["runtime"] = {
            "engine": "octave",
            "version": "FORGED_WITHOUT_OCTAVE",
            "platform": "FORGED",
        }
        summary = cross_language.compare_reports(self.python_report, forged)
        self.assertEqual(summary["status"], "PASS_H3_PAYLOAD_FORMULA_EQUIVALENCE_ONLY")
        self.assertEqual(
            summary["native_runtime_execution_status"],
            "NOT_EVALUATED_EXTERNAL_EXECUTION_AUTH_REQUIRED",
        )


class OutputSafetyTests(unittest.TestCase):
    def test_destinations_must_be_distinct_external_and_new(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            with self.assertRaisesRegex(ValueError, "distinct"):
                prepare_exclusive_outputs([target, target], REPOSITORY)
            with self.assertRaisesRegex(ValueError, "outside"):
                prepare_exclusive_outputs(
                    [CANDIDATE / "results" / "unsafe.json"], REPOSITORY
                )
            target.write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already exists"):
                prepare_exclusive_outputs([target], REPOSITORY)

    def test_symlink_parent_and_exclusive_create_reject(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            try:
                linked.symlink_to(real, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                prepare_exclusive_outputs([linked / "report.json"], REPOSITORY)

            (target,) = prepare_exclusive_outputs([real / "report.json"], REPOSITORY)
            exclusive_write_bytes(target, b"first\n")
            with self.assertRaises(FileExistsError):
                exclusive_write_bytes(target, b"second\n")
            self.assertEqual(target.read_bytes(), b"first\n")


if __name__ == "__main__":
    unittest.main()

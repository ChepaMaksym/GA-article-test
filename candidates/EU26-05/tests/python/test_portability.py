from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch


CANDIDATE = Path(__file__).resolve().parents[2]
HARDWARE = CANDIDATE / "tests" / "hardware"
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))
sys.path.insert(0, str(HARDWARE))

from eu2605.canonical import canonical_bytes, sha256_value  # noqa: E402
from eu2605.portability import (  # noqa: E402
    PARALLEL_CASE_COUNT,
    expected_parallel_cases,
    parallel_case,
    property_summary,
)
import compare_portability_reports as comparator  # noqa: E402
import build_github_content_match as content_match_builder  # noqa: E402
import run_portability_suite as runner  # noqa: E402


class PortabilityPayloadTests(unittest.TestCase):
    def test_execution_context_rejects_profile_relabelling(self) -> None:
        with patch.dict(
            os.environ,
            {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1"},
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "may not be relabelled"):
                runner._execution_context("work-4")
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}, clear=False):
            with self.assertRaisesRegex(ValueError, "only in a GitHub Actions"):
                runner._execution_context("github-4")

    def test_property_counts_and_claim_boundaries(self) -> None:
        summary = property_summary()
        self.assertEqual(summary["probability_grid_cases"], 120)
        self.assertEqual(summary["probability_zero_denominator_policy"], "REJECT")
        self.assertEqual(summary["one_point_four_bit_transitions"], 768)
        self.assertEqual(summary["extension_four_bit_children"], 512)
        self.assertEqual(summary["extension_profile"], "THESIS_MAXIMUM_BINARY_COMPLEMENT_ORIGIN")
        self.assertIs(summary["extension_author_code_claimed"], False)
        self.assertIs(summary["cec2017_claimed"], False)
        self.assertEqual(summary["objective_anchor_value"], 300000.0)

    def test_parallel_cases_are_complete_and_deterministic(self) -> None:
        first = expected_parallel_cases()
        second = expected_parallel_cases()
        self.assertEqual(len(first), PARALLEL_CASE_COUNT)
        self.assertEqual(first, second)
        self.assertEqual(sha256_value(first), sha256_value(second))
        self.assertEqual(len({row["case_id"] for row in first}), PARALLEL_CASE_COUNT)

    def test_parallel_case_boundaries_reject(self) -> None:
        for value in (-1, PARALLEL_CASE_COUNT, True, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parallel_case(value)  # type: ignore[arg-type]

    def test_barrier_observes_distinct_worker_processes_and_exact_shards(self) -> None:
        rows, evidence = runner._parallel_rows(4)
        self.assertEqual([row["case_id"] for row in rows], [
            f"formula-transition-{index:03d}" for index in range(PARALLEL_CASE_COUNT)
        ])
        self.assertEqual(len({record["pid"] for record in evidence}), 4)
        for slot, record in enumerate(evidence):
            self.assertEqual(record["worker_slot"], slot)
            self.assertEqual(
                record["scientific_case_indices"],
                list(range(slot, PARALLEL_CASE_COUNT, 4)),
            )


class StrictComparatorTests(unittest.TestCase):
    @staticmethod
    def worker_evidence(workers: int, cpus: list[int]) -> list[list[dict[str, object]]]:
        return [
            [
                {
                    "worker_slot": slot,
                    "pid": 10_000 + repeat * workers + slot,
                    "affinity_visible_cpus": cpus,
                    "scientific_case_indices": list(range(slot, PARALLEL_CASE_COUNT, workers)),
                }
                for slot in range(workers)
            ]
            for repeat in range(5)
        ]

    @classmethod
    def setUpClass(cls) -> None:
        args = SimpleNamespace(
            label="work-4",
            workers=4,
            logical_cpus=4,
            timing_repeats=5,
            require_clean=False,
            require_exact_visible_cpus=False,
        )
        # This is a synthetic Work-profile fixture even when the unit suite is
        # itself executing inside GitHub Actions. Keep the production relabel
        # guard enabled and mask only the test process's ambient CI marker.
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}, clear=False):
            base, _ = runner.build_report(args)
        base["git_clean_at_start"] = True
        base["hardware"]["exact_visible_cpus_enforced"] = True
        base["hardware"]["affinity_visible_cpus"] = [0, 1, 2, 3]
        base["worker_execution_repeats"] = cls.worker_evidence(4, [0, 1, 2, 3])
        cls.work4 = base

        cls.work8 = copy.deepcopy(base)
        cls.work8["profile_label"] = "work-8"
        cls.work8["requested_workers"] = 8
        cls.work8["requested_logical_cpus"] = 8
        cls.work8["hardware"]["affinity_visible_cpus"] = list(range(8))
        cls.work8["worker_execution_repeats"] = cls.worker_evidence(8, list(range(8)))

        cls.github4 = copy.deepcopy(base)
        cls.github4["profile_label"] = "github-4"
        cls.github4["hardware_role_authentication"] = "UNAUTHENTICATED_CONTEXT_CLAIM"
        cls.github4["hardware"]["execution_context"] = {
            "github_actions": True,
            "github_run_id": "123456",
            "github_run_attempt": "1",
        }
        cls.github4["worker_execution_repeats"] = cls.worker_evidence(4, [0, 1, 2, 3])
        cls._temporary = tempfile.TemporaryDirectory()
        report_path = Path(cls._temporary.name) / "github-4.json"
        report_path.write_bytes(canonical_bytes(cls.github4) + b"\n")
        cls.github_report_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()
        workflow_run = {
            "id": 123456,
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "success",
            "repository": {"full_name": "ChepaMaksym/GA-article-test"},
            "path": ".github/workflows/eu26-05-validation.yml@research/EU26-05-adaptive-crossover-verification",
            "head_sha": cls.github4["git_head"],
            "url": "https://api.github.com/repos/ChepaMaksym/GA-article-test/actions/runs/123456",
        }
        artifact = {
            "id": 987654,
            "name": "eu26-05-github-4-formula-portability",
            "expired": False,
            "workflow_run": {"id": 123456, "head_sha": cls.github4["git_head"]},
            "url": "https://api.github.com/repos/ChepaMaksym/GA-article-test/actions/artifacts/987654",
        }
        cls.content_match = content_match_builder.build_content_match(
            workflow_run, artifact, report_path
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_missing_github_is_not_a_pass(self) -> None:
        summary, complete = comparator.compare_reports([self.work4, self.work8])
        self.assertIs(complete, False)
        self.assertEqual(summary["status"], "NOT_RUN_MISSING_PROFILES")
        self.assertEqual(summary["missing_profiles"], ["github-4"])
        self.assertEqual(
            summary["h0_source_status"],
            "PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE",
        )

    def test_three_self_asserted_profiles_stay_unauthenticated(self) -> None:
        summary, complete = comparator.compare_reports(
            [self.work4, self.work8, self.github4]
        )
        self.assertIs(complete, False)
        self.assertEqual(summary["status"], "NOT_RUN_GITHUB_CONTENT_MATCH_RECORD")
        self.assertEqual(
            summary["github_role_authentication"],
            "NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED",
        )

    def test_offline_content_match_never_authorizes_h5(self) -> None:
        summary, complete = comparator.compare_reports(
            [self.work4, self.work8, self.github4],
            github_content_match=self.content_match,
            report_sha256_by_label={"github-4": self.github_report_sha256},
        )
        self.assertIs(complete, False)
        self.assertEqual(
            summary["status"], "NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED"
        )
        self.assertEqual(summary["strongest_result"], "NOT_EVALUATED")
        self.assertIs(summary["offline_authorizes_h5"], False)
        self.assertEqual(
            summary["offline_content_match"],
            "PASS_CALLER_SUPPLIED_METADATA_AND_LOCAL_REPORT_COHERENCE_ONLY",
        )
        self.assertIs(summary["published_27_of_30_evaluated"], False)
        self.assertIs(summary["pass_full_claimed"], False)

    def test_internally_incoherent_content_match_rejects(self) -> None:
        forged = copy.deepcopy(self.content_match)
        forged["artifact_id"] += 1
        with self.assertRaisesRegex(ValueError, "artifact API URL"):
            comparator.compare_reports(
                [self.work4, self.work8, self.github4],
                github_content_match=forged,
                report_sha256_by_label={"github-4": self.github_report_sha256},
            )

    def test_cpu_masks_and_worker_evidence_require_exact_types(self) -> None:
        bad_mask = copy.deepcopy(self.work4)
        bad_mask["hardware"]["affinity_visible_cpus"] = ["forged"] * 4
        with self.assertRaisesRegex(ValueError, "CPU mask"):
            comparator.compare_reports([bad_mask])

        duplicate_mask = copy.deepcopy(self.work4)
        duplicate_mask["hardware"]["affinity_visible_cpus"] = [0, 0, 1, 2]
        with self.assertRaisesRegex(ValueError, "CPU mask"):
            comparator.compare_reports([duplicate_mask])

        bad_pid = copy.deepcopy(self.work4)
        bad_pid["worker_execution_repeats"][0][0]["pid"] = True
        with self.assertRaisesRegex(ValueError, "PID"):
            comparator.compare_reports([bad_pid])

    def test_bool_integer_confusion_rejects(self) -> None:
        bad = copy.deepcopy(self.work4)
        bad["requested_workers"] = True
        with self.assertRaisesRegex(ValueError, "exact integer"):
            comparator.compare_reports([bad])

    def test_tampered_scientific_payload_rejects(self) -> None:
        bad = copy.deepcopy(self.work4)
        bad["scientific_payload"]["parallel_cases"][0]["children"][0] = "0" * 12
        with self.assertRaisesRegex(ValueError, "scientific payload"):
            comparator.compare_reports([bad])

    def test_minimal_profile_report_rejects(self) -> None:
        with self.assertRaisesRegex(ValueError, "schema"):
            comparator.compare_reports([{"profile_label": "work-4"}])


if __name__ == "__main__":
    unittest.main()

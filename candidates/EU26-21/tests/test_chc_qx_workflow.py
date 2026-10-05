"""Static orchestration and fabricated metadata checks, executed only in CI."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT / "candidates/EU26-21"
sys.path.insert(0, str(CANDIDATE))
from chc_qx_alignment_study.artifacts import select_sources, validate_transport  # noqa: E402
from chc_qx_alignment_study.contract import CASE_SEEDS, PROTOCOL_SHA256  # noqa: E402

SPEC = importlib.util.spec_from_file_location("qx_transport", ROOT / ".github/scripts/download_study_artifacts.py")
transport = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transport)
SHA, RUN = "a" * 40, 77


def metadata(seed=44001, identity=10001, attempt=1, kind="case"):
    return {"id": identity, "name": f"eu26-21-qx-{kind}-{seed}-{RUN}-{attempt}",
            "expired": False, "size_in_bytes": 100, "digest": "sha256:" + "b" * 64,
            "workflow_run": {"id": RUN, "head_sha": SHA}}


class MetadataSelectionTests(unittest.TestCase):
    def setUp(self):
        self.raw = {"artifacts": [metadata(seed, i + 10001) for i, seed in enumerate(CASE_SEEDS)]}

    def test_all_thirty_sources_selected_without_opening_results(self):
        selected = select_sources(self.raw, run_id=RUN, expected_sha=SHA, kind="case")
        self.assertEqual(len(selected["artifacts"]), 30)
        self.assertIn("without_opening_results", selected["selection_policy"])

    def test_retry_selected_by_attempt_not_input_order(self):
        self.raw["artifacts"].insert(0, metadata(identity=10101, attempt=2))
        selected = select_sources(self.raw, run_id=RUN, expected_sha=SHA, kind="case")
        self.assertEqual(selected["artifacts"][0]["id"], 10101)
        self.assertEqual(len(selected["attempts"]), 31)

    def test_missing_seed_rejected(self):
        self.raw["artifacts"].pop()
        with self.assertRaises(ValueError):
            select_sources(self.raw, run_id=RUN, expected_sha=SHA, kind="case")

    def test_duplicate_attempt_rejected(self):
        self.raw["artifacts"].append(metadata(identity=10101))
        with self.assertRaises(ValueError):
            select_sources(self.raw, run_id=RUN, expected_sha=SHA, kind="case")

    def test_wrong_sha_expiry_digest_and_namespace_rejected(self):
        for key, value in (("expired", True), ("digest", ""), ("name", "unexpected")):
            raw = copy.deepcopy(self.raw)
            raw["artifacts"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                select_sources(raw, run_id=RUN, expected_sha=SHA, kind="case")
        with self.assertRaises(ValueError):
            select_sources(self.raw, run_id=RUN, expected_sha="c" * 40, kind="case")

    def test_transport_proof_must_cover_the_exact_selected_sources(self):
        selected = select_sources(self.raw, run_id=RUN, expected_sha=SHA, kind="case")
        ledger = {"complete": True, "source_run_id": RUN, "implementation_sha": SHA,
                  "artifacts": [{**row, "zip_verified_before_extraction": True,
                                 "verified_zip_sha256": "b" * 64, "verified_zip_bytes": 100}
                                for row in selected["artifacts"]]}
        validate_transport(selected, ledger)
        ledger["artifacts"][0]["zip_verified_before_extraction"] = False
        with self.assertRaises(ValueError):
            validate_transport(selected, ledger)

    def test_exact_id_downloader_accepts_only_registered_qx_seed_namespace(self):
        for kind in ("case", "preparation"):
            row = metadata(kind=kind)
            transport.validate_metadata(row, artifact_id=row["id"], run_id=RUN,
                                        expected_sha=SHA, kind="qx-" + kind)
            row["name"] = row["name"].replace("44001", "44031")
            with self.assertRaises(ValueError):
                transport.validate_metadata(row, artifact_id=row["id"], run_id=RUN,
                                            expected_sha=SHA, kind="qx-" + kind)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = (ROOT / ".github/workflows/eu26-21-chc-qx-alignment-study.yml").read_text(encoding="utf-8")

    def test_actions_are_fully_pinned_and_checkouts_retain_registration(self):
        for action in re.findall(r"uses:\s*([^\s]+)", self.workflow):
            self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$")
        self.assertIn("fetch-depth: 0", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn('git merge-base --is-ancestor "$REGISTRATION_SHA" "$EXPECTED_SHA"', self.workflow)
        self.assertEqual(hashlib.sha256((CANDIDATE / "chc_qx_alignment_study/protocol.json").read_bytes()).hexdigest(), PROTOCOL_SHA256)

    def test_ordinary_push_cannot_launch_science(self):
        dispatch = self.workflow.split("  dispatch:\n", 1)[1].split("  authorize:\n", 1)[0]
        self.assertIn("[launch-chc-qx-alignment]", dispatch)
        self.assertIn("needs: preflight", dispatch)
        self.assertIn("inputs[expected_sha]=$EXPECTED_SHA", dispatch)
        authorize = self.workflow.split("  authorize:\n", 1)[1].split("  source_smoke:\n", 1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch'", authorize)
        for check in ('test "$GITHUB_SHA" = "$EXPECTED_SHA"', 'test "$STUDY_WORKFLOW_SHA" = "$EXPECTED_SHA"'):
            self.assertIn(check, self.workflow)

    def test_two_complete_matrices_are_independent_and_bounded(self):
        self.assertEqual(self.workflow.count("fail-fast: false"), 2)
        self.assertEqual(self.workflow.count("max-parallel: 10"), 2)
        literal = "seed: [" + ",".join(map(str, CASE_SEEDS)) + "]"
        self.assertEqual(self.workflow.count(literal), 2)

    def test_registry_precedes_search_and_repreparation_after_freeze_is_rejected(self):
        self.assertIn("needs: [fixture, registry]", self.workflow)
        self.assertIn("Reject temporal re-preparation after a registry already exists", self.workflow)
        self.assertIn("Rerun failed main jobs only", self.workflow)
        self.assertIn("--preparation", self.workflow)
        self.assertIn("--registry", self.workflow)

    def test_source_and_corrected_environment_are_separate(self):
        smoke = self.workflow.split("  source_smoke:\n", 1)[1].split("  fixture:\n", 1)[0]
        self.assertIn("python-version: '3.9'", smoke)
        self.assertIn("hybrid_1/requirements.txt", smoke)
        self.assertIn("--phase real-smoke", smoke)
        self.assertNotIn("run_source_campaign", smoke)

    def test_aggregation_waits_for_all_cases_and_authenticates_zip_sources(self):
        report = self.workflow.split("  aggregate:\n", 1)[1]
        self.assertIn("needs: [cases, registry]", report)
        self.assertIn("needs.cases.result == 'success'", report)
        self.assertIn("--download-ledger", report)
        self.assertIn("--kind qx-case", report)
        self.assertNotIn("issues:", self.workflow)


if __name__ == "__main__":
    unittest.main()

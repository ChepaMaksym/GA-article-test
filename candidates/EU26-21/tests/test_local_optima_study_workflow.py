"""Static follow-up wiring contracts, executed exclusively by GitHub Actions."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/eu26-21-local-optima-study.yml"


class StudyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_full_sha_action_pins(self):
        actions = re.findall(r"uses:\s*([^\s]+)", self.workflow)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$")

    def test_science_requires_dispatch_and_successful_preflight(self):
        self.assertIn("github.event_name == 'workflow_dispatch'", self.workflow)
        self.assertIn("[launch-local-optima]", self.workflow)
        self.assertIn("needs: preflight", self.workflow)
        self.assertIn("inputs[expected_sha]=$EXPECTED_SHA", self.workflow)
        self.assertIn('test "$STUDY_WORKFLOW_SHA" = "$EXPECTED_SHA"', self.workflow)
        self.assertIn("REGISTRATION_SHA: ee3073f565ee07978a6b58ab63e6061b396ba54c", self.workflow)

    def test_frozen_protocol_and_matrix(self):
        self.assertIn("8167f46a1adce8d759404d9577101befa183756ca92230e4ac3718c9f46d2ca7", self.workflow)
        seeds = re.search(r"seed:\s*\[([^]]+)\]", self.workflow)
        self.assertIsNotNone(seeds)
        self.assertEqual([int(s) for s in seeds.group(1).split(",")], list(range(42001,42031)))
        self.assertEqual(self.workflow.count("fail-fast: false"), 2)
        self.assertEqual(self.workflow.count("max-parallel: 10"), 2)
        self.assertNotIn("cancel-in-progress: true", self.workflow)

    def test_registry_precedes_escape_and_complete_aggregation(self):
        self.assertIn("needs: [freeze, fixture]", self.workflow)
        self.assertIn("fromJSON(needs.freeze.outputs.matrix)", self.workflow)
        self.assertIn("needs.freeze.outputs.eligible_count != '0'", self.workflow)
        self.assertIn("needs: [freeze, escape]", self.workflow)
        self.assertIn("needs.escape.result == 'success' || needs.escape.result == 'skipped'", self.workflow)
        self.assertIn("--registry-sha256", self.workflow)
        self.assertIn("--case-ledger", self.workflow)
        self.assertIn("--escape-ledger", self.workflow)

    def test_all_runners_are_in_ci_and_artifacts_bound(self):
        for module in ("run_case", "run_escape", "aggregate"):
            self.assertIn("python -m local_optima_study." + module, self.workflow)
        self.assertIn("--expected-protocol-sha256", self.workflow)
        self.assertIn("actions/runs/${GITHUB_RUN_ID}/artifacts", self.workflow)
        self.assertIn("artifact-ids: ${{ needs.freeze.outputs.artifact_id }}", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)

    def test_retries_preserve_raw_attempts_and_freeze_exact_source_ids(self):
        self.assertEqual(self.workflow.count("python -m local_optima_study.artifact_selection"), 2)
        self.assertIn("case-attempt-ledger.json", self.workflow)
        self.assertIn("escape-attempt-ledger.json", self.workflow)
        self.assertIn("artifact-ids: ${{ steps.source.outputs.artifact_id }}", self.workflow)
        self.assertIn("artifact-ids: ${{ steps.sources.outputs.case_artifact_ids }}", self.workflow)
        self.assertNotIn("pattern: eu26-21-local-case-", self.workflow)

    def test_id_downloads_keep_single_sources_flat_and_retry_sources_accessible(self):
        blocks = re.split(r"\n      - ", self.workflow)
        downloads = [block for block in blocks if "uses: actions/download-artifact@" in block]
        self.assertEqual(len(downloads), 8)
        for block in downloads:
            self.assertIn("github-token: ${{ github.token }}", block)
            self.assertIn("run-id: ${{ github.run_id }}", block)
            if "artifact-ids: ${{ needs." in block or "artifact-ids: ${{ steps.source.outputs.artifact_id }}" in block:
                self.assertIn("merge-multiple: true", block)


if __name__ == "__main__":
    unittest.main()

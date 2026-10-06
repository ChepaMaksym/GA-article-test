"""Static workflow and fictitious transport contracts, executed in CI only."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/eu26-21-lambda-initial-study.yml"
PROTOCOL = ROOT / "candidates/EU26-21/lambda_initial_study/protocol.json"
PROTOCOL_SHA = "8f96fbf91ae5e92b90409c3ba0492da2d13551bca0d49e273d299dd4ac1453b4"
REGISTRATION_SHA = "fdf093fd4b53ecf48a148d86b28c8ecee007e7aa"
SPEC = importlib.util.spec_from_file_location(
    "lambda_initial_transport", ROOT / ".github/scripts/download_study_artifacts.py",
)
transport = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transport)
SYNTHETIC_SHA = "a" * 40
SYNTHETIC_RUN = 77


def synthetic_archive():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(zipfile.ZipInfo("synthetic.txt", date_time=(2020, 1, 1, 0, 0, 0)),
                         b"FICTITIOUS_LAMBDA_TEST_ONLY\n")
    return buffer.getvalue()


def synthetic_metadata(artifact_id=10001, *, kind="case", seed=43001, raw=None):
    raw = synthetic_archive() if raw is None else raw
    prefix = f"{seed}-" if kind == "case" else ""
    return {
        "id": artifact_id,
        "name": (f"eu26-21-lambda-case-{prefix}{SYNTHETIC_RUN}-1" if kind == "case" else
                 f"eu26-21-lambda-initial-{kind}-{prefix}{SYNTHETIC_RUN}-1"),
        "expired": False, "size_in_bytes": len(raw),
        "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "workflow_run": {"id": SYNTHETIC_RUN, "head_sha": SYNTHETIC_SHA},
    }


class SyntheticAPI:
    def __init__(self, rows, archives=None):
        self.rows = rows
        self.archives = archives or {identity: synthetic_archive() for identity in rows}
        self.downloads = []
        self.metadata_requests = []

    def metadata(self, identity):
        self.metadata_requests.append(identity)
        return self.rows[identity]

    def download(self, identity, path):
        self.downloads.append(identity)
        path.write_bytes(self.archives[identity])


class LambdaInitialWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_actions_are_pinned_to_full_commit_sha(self):
        actions = re.findall(r"uses:\s*([^\s]+)", self.workflow)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$")

    def test_registered_protocol_bytes_and_registration_ancestor_are_bound(self):
        self.assertEqual(hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(), PROTOCOL_SHA)
        self.assertIn("PROTOCOL_SHA256: " + PROTOCOL_SHA, self.workflow)
        self.assertIn("REGISTRATION_SHA: " + REGISTRATION_SHA, self.workflow)
        self.assertIn('git merge-base --is-ancestor "$REGISTRATION_SHA" "$EXPECTED_SHA"', self.workflow)
        self.assertIn('${REGISTRATION_SHA}:candidates/EU26-21/lambda_initial_study/protocol.json', self.workflow)
        self.assertIn('test "$registered_digest" = "$PROTOCOL_SHA256"', self.workflow)

    def test_exact_implementation_and_workflow_sha_cannot_diverge(self):
        self.assertIn('test "$GITHUB_SHA" = "$EXPECTED_SHA"', self.workflow)
        self.assertIn('test "$STUDY_WORKFLOW_SHA" = "$EXPECTED_SHA"', self.workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"', self.workflow)
        self.assertIn("fetch-depth: 0", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)

    def test_normal_pushes_cannot_launch_science(self):
        dispatch = self.workflow.split("  dispatch:\n", 1)[1].split("  authorize:\n", 1)[0]
        self.assertIn("github.event_name == 'push'", dispatch)
        self.assertIn("[launch-lambda-initial]", dispatch)
        self.assertIn("needs: preflight", dispatch)
        self.assertIn("actions: write", dispatch)
        self.assertIn("inputs[expected_sha]=$EXPECTED_SHA", dispatch)
        self.assertNotIn("[launch-local-optima]", self.workflow)
        authorize = self.workflow.split("  authorize:\n", 1)[1].split("  fixture:\n", 1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch'", authorize)
        self.assertIn("needs: preflight", authorize)

    def test_complete_paired_seed_matrix_preserves_registered_parallelism(self):
        seeds = re.search(r"seed:\s*\[([^]]+)\]", self.workflow)
        self.assertIsNotNone(seeds)
        self.assertEqual([int(value) for value in seeds.group(1).split(",")], list(range(43001, 43031)))
        self.assertEqual(self.workflow.count("fail-fast: false"), 1)
        self.assertEqual(self.workflow.count("max-parallel: 10"), 1)
        self.assertIn("timeout-minutes: 180", self.workflow)
        self.assertNotIn("cancel-in-progress: true", self.workflow)
        self.assertNotIn("matrix.arm", self.workflow)

    def test_source_transport_is_exact_id_authenticated_not_name_pattern_download(self):
        blocks = re.split(r"\n      - ", self.workflow)
        downloads = [block for block in blocks if "python .github/scripts/download_study_artifacts.py" in block]
        self.assertEqual(len(downloads), 3)
        for block in downloads:
            self.assertIn("GH_TOKEN: ${{ github.token }}", block)
            self.assertIn('--repository "$GITHUB_REPOSITORY" --run-id "$GITHUB_RUN_ID"', block)
            self.assertIn('--expected-sha "$EXPECTED_SHA"', block)
        self.assertNotIn("uses: actions/download-artifact@", self.workflow)
        self.assertIn("--kind lambda-smoke", downloads[0])
        self.assertIn("--merge-multiple", downloads[0])
        self.assertIn("--kind lambda-fixture", downloads[1])
        self.assertIn("--merge-multiple", downloads[1])
        self.assertIn("--kind lambda-case", downloads[2])
        self.assertNotIn("--merge-multiple", downloads[2])
        self.assertIn("--transport-ledger", downloads[2])

    def test_synthetic_smoke_and_all_tests_precede_science(self):
        preflight = self.workflow.split("  preflight:\n", 1)[1].split("  dispatch:\n", 1)[0]
        self.assertIn("unittest discover -s candidates/EU26-21/tests -p 'test_*.py'", preflight)
        self.assertIn("--select E9,F63,F7,F82", preflight)
        self.assertIn("CI_ONLY_SYNTHETIC_LAMBDA_ARTIFACT", preflight)
        self.assertIn("synthetic lambda transport payload mismatch", preflight)
        self.assertIn("zip_verified_before_extraction", preflight)
        self.assertNotIn("python -m lambda_initial_study.run_case", preflight)
        self.assertNotIn("python -m lambda_initial_study.aggregate", preflight)

    def test_fixture_data_and_chc_source_are_hash_pinned(self):
        for digest in (
            "54fd206becffcfaf099544c3938c681d64a65709800c94c00a4fba0a00df10c9",
            "3676a81db7d3528f3f8b9f3c699d0f0aa28db45e6e994fa0b8ed38327539ee86",
            "98402b1ab879573d0a7f38a699a40258080e25e33d3401e7bf9c96d3fa0fab8c",
            "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6",
        ):
            self.assertIn(digest, self.workflow)
        self.assertIn("sha256sum --check upstream.sha256", self.workflow)
        self.assertIn("candidates/EU26-21/corrected_applied/requirements.txt", self.workflow)

    def test_paired_runner_and_complete_report_cli_wiring(self):
        cases = self.workflow.split("  cases:\n", 1)[1].split("  report:\n", 1)[0]
        self.assertIn("python -m lambda_initial_study.run_case", cases)
        for flag in ("--expected-sha", "--upstream", "--train", "--test", "--seed", "--output"):
            self.assertIn(flag, cases)
        report = self.workflow.split("  report:\n", 1)[1]
        self.assertIn("needs: cases", report)
        self.assertNotIn("if: ${{ always()", report)
        self.assertIn("python -m lambda_initial_study.aggregate", report)
        for flag in ("--expected-sha", "--root", "--sources", "--download-ledger", "--output"):
            self.assertIn(flag, report)
        self.assertIn("len(rows) != 30", report)

    def test_retry_sources_use_full_paginated_metadata_and_retain_both_ledgers(self):
        commands = re.sub(r"\\\r?\n\s*", " ", self.workflow)
        command = re.search(r"gh api[^\r\n]*--slurp[^\r\n]*", commands)
        self.assertIsNotNone(command)
        gh_command, separator, jq_command = command.group().partition("|")
        self.assertEqual(separator, "|")
        self.assertIn("--paginate", gh_command)
        self.assertNotRegex(gh_command, r"(?:^|\s)(?:--jq|-q)(?:\s|=|$)")
        self.assertTrue(jq_command.lstrip().startswith("jq "))
        self.assertIn('[.[].artifacts[]', jq_command)
        self.assertIn("case-attempt-ledger.json", self.workflow)
        self.assertIn("sources.json", self.workflow)
        self.assertIn("download-ledger.json", self.workflow)
        self.assertIn("python -m lambda_initial_study.select_artifacts", self.workflow)

    def test_uploaded_case_namespace_matches_runner_selector_and_transport(self):
        prefix = "eu26-21-lambda-case-"
        self.assertIn('name: ' + prefix + '${{ matrix.seed }}-', self.workflow)
        self.assertIn('startswith("' + prefix + '")', self.workflow)
        self.assertNotIn("eu26-21-lambda-initial-case-", self.workflow)
        runner = (ROOT / "candidates/EU26-21/lambda_initial_study/run_case.py").read_text(encoding="utf-8")
        selector = (ROOT / "candidates/EU26-21/lambda_initial_study/select_artifacts.py").read_text(encoding="utf-8")
        self.assertIn(prefix, runner)
        self.assertIn(prefix, selector)
        transport.validate_metadata(synthetic_metadata(), artifact_id=10001, run_id=SYNTHETIC_RUN,
                                    expected_sha=SYNTHETIC_SHA, kind="lambda-case")

    def test_new_paths_trigger_both_preflight_and_quality_coverage(self):
        self.assertIn("- 'candidates/EU26-21/lambda_initial_study/**'", self.workflow)
        self.assertIn("- 'candidates/EU26-21/tests/test_lambda_initial*.py'", self.workflow)
        self.assertIn("- '.github/scripts/download_study_artifacts.py'", self.workflow)
        quality = (ROOT / ".github/workflows/eu26-21-code-quality.yml").read_text(encoding="utf-8")
        self.assertIn("- 'candidates/EU26-21/lambda_initial_study/**'", quality)
        self.assertGreaterEqual(quality.count("candidates/EU26-21/lambda_initial_study"), 8)
        self.assertIn("eu26-21-lambda-initial-report-${{ github.run_id }}-${{ github.run_attempt }}", self.workflow)
        self.assertIn("retention-days: 90", self.workflow)

    def test_all_workflows_discovering_new_contracts_have_registration_history(self):
        # Authentic ancestor/blob checks must not be weakened for older jobs.
        # Every full-discovery workflow needs its first checkout history.
        full_discovery = []
        for path in sorted((ROOT / ".github/workflows").glob("eu26-21-*.yml")):
            content = path.read_text(encoding="utf-8")
            if "-p 'test_*.py'" not in content:
                continue
            full_discovery.append(path.name)
            checkout = content.split("uses: actions/checkout@", 1)[1].split("- uses: actions/setup-python@", 1)[0]
            with self.subTest(workflow=path.name):
                self.assertIn("fetch-depth: 0", checkout)
        self.assertEqual(set(full_discovery), {
            "eu26-21-code-quality.yml", "eu26-21-local-optima-study.yml",
            "eu26-21-lambda-initial-study.yml",
            "eu26-21-chc-qx-alignment-study.yml",
        })


class LambdaInitialTransportTests(unittest.TestCase):
    def test_three_new_kinds_accept_only_their_own_namespaces(self):
        for kind in ("smoke", "fixture", "case"):
            with self.subTest(kind=kind):
                row = synthetic_metadata(kind=kind)
                transport.validate_metadata(row, artifact_id=10001, run_id=SYNTHETIC_RUN,
                                            expected_sha=SYNTHETIC_SHA, kind="lambda-" + kind)
                with self.assertRaises(transport.ArtifactError):
                    transport.validate_metadata(row, artifact_id=10001, run_id=SYNTHETIC_RUN,
                                                expected_sha=SYNTHETIC_SHA, kind=kind)

    def test_lambda_case_seed_must_belong_to_exact_ledger(self):
        for seed in (43001, 43030):
            transport.validate_metadata(synthetic_metadata(seed=seed), artifact_id=10001,
                                        run_id=SYNTHETIC_RUN, expected_sha=SYNTHETIC_SHA, kind="lambda-case")
        for seed in (42001, 43000, 43031, 44001):
            with self.subTest(seed=seed), self.assertRaises(transport.ArtifactError):
                transport.validate_metadata(synthetic_metadata(seed=seed), artifact_id=10001,
                                            run_id=SYNTHETIC_RUN, expected_sha=SYNTHETIC_SHA, kind="lambda-case")

    def download(self, api, destination, ledger):
        with redirect_stdout(StringIO()):
            transport.download_artifacts(
                ids=list(api.rows), repository="owner/repo", run_id=SYNTHETIC_RUN,
                expected_sha=SYNTHETIC_SHA, kind="lambda-case", destination=destination,
                api=api, transport_ledger=ledger,
            )

    def test_complete_transport_ledger_records_verified_zip_identity(self):
        api = SyntheticAPI({10001: synthetic_metadata(), 10002: synthetic_metadata(10002, seed=43002)})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger_path = root / "download-ledger.json"
            self.download(api, root / "cases", ledger_path)
            ledger = json.loads(ledger_path.read_text())
            self.assertEqual(ledger["schema"], "eu26-21-exact-id-transport-ledger-v1")
            self.assertEqual(ledger["source_run_id"], SYNTHETIC_RUN)
            self.assertEqual(ledger["implementation_sha"], SYNTHETIC_SHA)
            self.assertEqual(ledger["kind"], "lambda-case")
            self.assertIs(ledger["complete"], True)
            self.assertEqual([row["id"] for row in ledger["artifacts"]], [10001, 10002])
            for row in ledger["artifacts"]:
                self.assertEqual(row["verified_zip_sha256"], row["digest"].removeprefix("sha256:"))
                self.assertEqual(row["verified_zip_bytes"], row["size_in_bytes"])
                self.assertIs(row["zip_verified_before_extraction"], True)
            self.assertEqual(len(list((root / "cases").iterdir())), 2)

    def test_digest_failure_cannot_write_a_complete_transport_ledger(self):
        row = {**synthetic_metadata(), "digest": "sha256:" + "b" * 64}
        api = SyntheticAPI({10001: row})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(transport.ArtifactError, "SHA256"):
                self.download(api, root / "cases", root / "download-ledger.json")
            self.assertFalse((root / "download-ledger.json").exists())
            self.assertFalse((root / "cases").exists())

    def test_existing_ledger_cannot_be_overwritten_even_before_metadata_access(self):
        api = SyntheticAPI({10001: synthetic_metadata()})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root / "retained.json"
            ledger.write_bytes(b"PREEXISTING_TEST_DATA")
            with self.assertRaisesRegex(transport.ArtifactError, "overwrite"):
                self.download(api, root / "cases", ledger)
            self.assertEqual(ledger.read_bytes(), b"PREEXISTING_TEST_DATA")
            self.assertEqual(api.metadata_requests, [])

    def test_ledger_cannot_be_injected_into_extracted_manifest_inventory(self):
        api = SyntheticAPI({10001: synthetic_metadata()})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "cases"
            with self.assertRaisesRegex(transport.ArtifactError, "outside"):
                self.download(api, root, root / "download-ledger.json")
            self.assertEqual(api.metadata_requests, [])


if __name__ == "__main__":
    unittest.main()

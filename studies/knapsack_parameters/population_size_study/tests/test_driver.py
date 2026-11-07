"""CI-only binding checks for retained prerequisites and empty test suites."""
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from studies.knapsack_parameters.population_size_study import driver
from studies.knapsack_parameters.population_size_study.io_utils import identity, write_manifest


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Driver fixtures run only in GitHub Actions")
class DriverBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.module = self.root / "module"
        self.module.mkdir()
        self.source = self.root / "source"
        self.source.mkdir()
        self.fingerprint = "f" * 64
        self.provenance = {"protocol_id": driver.a.PROTOCOL, "implementation_sha": "a" * 40,
                           "source_manifest": {"sha256": self.fingerprint}, "run_id": 100,
                           "run_attempt": 1}
        self.report = {"status": "VERIFIED_SOFTWARE_TESTS", "provenance": self.provenance}
        self.archive = self.root / "fixture.zip"
        self.artifact = {"id": 200, "name": "population-size-tests-100-1", "workflow_run": {"id": 100},
                         "expired": False}
        self.run = {"id": 100, "run_attempt": 1, "status": "completed", "conclusion": "success",
                    "head_branch": driver.a.BRANCH, "path": driver.a.WORKFLOW, "head_sha": "a" * 40}
        self.freeze_fixture()

    def freeze_fixture(self):
        (self.source / "software_tests.json").write_text(json.dumps(self.report), encoding="utf-8")
        write_manifest(self.source)
        with zipfile.ZipFile(self.archive, "w") as archive:
            for path in self.source.iterdir():
                archive.write(path, path.name)
        self.artifact["size_in_bytes"] = self.archive.stat().st_size
        self.descriptor = {"status": "VERIFIED", "phase": "tests", "run_id": 100, "run_attempt": 1,
                           "artifact_id": 200, "artifact_name": self.artifact["name"],
                           "source_manifest_sha256": self.fingerprint,
                           "archive_sha256": identity(self.archive)["sha256"],
                           "file_manifest_sha256": identity(self.source / "file_manifest.json")["sha256"],
                           "report_sha256": identity(self.source / "software_tests.json")["sha256"]}
        self.save_descriptor()

    def save_descriptor(self):
        (self.module / "frozen_tests.json").write_text(json.dumps(self.descriptor), encoding="utf-8")

    def restore(self):
        def download(url, target, **kwargs):
            self.assertFalse(kwargs["follow_redirects"])
            self.assertTrue(url.endswith("/actions/artifacts/200/zip"))
            with Path(target).open("xb") as stream:
                stream.write(self.archive.read_bytes())
            return identity(target)
        with ExitStack() as stack:
            stack.enter_context(patch.object(driver.a, "MODULE", self.module))
            stack.enter_context(patch.object(driver.a, "source_manifest", return_value={"sha256": self.fingerprint}))
            stack.enter_context(patch.object(driver.a, "api", side_effect=[deepcopy(self.artifact), deepcopy(self.run)]))
            stack.enter_context(patch.object(driver, "_download", side_effect=download))
            stack.enter_context(patch.dict(os.environ, {"GITHUB_TOKEN": "fixture-placeholder"}))
            return driver.frozen_artifact("frozen_tests.json", self.root / "restored", "tests", "software_tests.json")

    def test_successful_frozen_report_is_restored(self):
        result = self.restore()
        self.assertEqual(json.loads((result / "software_tests.json").read_bytes()), self.report)

    def test_mixed_scientific_source_is_rejected(self):
        self.descriptor["source_manifest_sha256"] = "0" * 64
        self.save_descriptor()
        with self.assertRaisesRegex(ValueError, "different scientific"):
            self.restore()

    def test_failed_prerequisite_run_is_rejected(self):
        self.run["conclusion"] = "failure"
        with self.assertRaisesRegex(ValueError, "not successful"):
            self.restore()

    def test_wrong_report_origin_is_rejected_despite_valid_file_hash(self):
        self.report["provenance"]["implementation_sha"] = "b" * 40
        self.freeze_fixture()
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.restore()

    def test_incomplete_report_is_rejected_despite_valid_file_hash(self):
        self.report["status"] = "FAILED"
        self.freeze_fixture()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.restore()

    def test_archive_checksum_is_required(self):
        self.descriptor["archive_sha256"] = "0" * 64
        self.save_descriptor()
        with self.assertRaisesRegex(ValueError, "archive identity"):
            self.restore()

    def test_empty_discovery_cannot_count_as_verified(self):
        with patch.object(driver.a, "check_permit", return_value=self.provenance), \
             patch.object(driver.unittest.defaultTestLoader, "discover", return_value=unittest.TestSuite()):
            with self.assertRaisesRegex(ValueError, "Software checks failed"):
                driver.software_tests(self.root / "empty_output", {})
        report = json.loads((self.root / "empty_output/software_tests.json").read_bytes())
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["tests_run"], 0)

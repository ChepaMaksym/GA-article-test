"""Synthetic preservation-chain and fail-closed recovery tests (CI-only)."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_bridge.fetch_source_artifacts import ArtifactError
from evidence_audit import restore_source_rows as recovery
from evidence_audit.historical import SOURCES


class FakeAPI:
    def __init__(self, archive, digest):
        self.archive = archive
        self.digest = digest
        self.run = {
            "id": recovery.PRESERVATION["run_id"], "run_attempt": 1,
            "head_sha": recovery.PRESERVATION["head_sha"],
            "event": "workflow_dispatch", "status": "completed",
            "conclusion": "success", "path": recovery.WORKFLOW_PATH,
        }
        self.artifact = {
            **{key: recovery.PRESERVATION[key] for key in ("id", "name")},
            "digest": digest, "expired": False, "size_in_bytes": len(archive),
            "workflow_run": {"id": recovery.PRESERVATION["run_id"],
                             "head_sha": recovery.PRESERVATION["head_sha"]},
        }

    def json(self, url):
        if "/attempts/" in url:
            return self.run
        return self.artifact

    def download(self, url, destination):
        destination.write_bytes(self.archive)
        return hashlib.sha256(self.archive).hexdigest()


class RestoreSourceRowsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "preserved"
        self.source = SOURCES["source_compatible"]
        directory = self.root / self.source["name"] / "nested"
        directory.mkdir(parents=True)
        self.source_dir = directory.parent
        for seed in range(1, 31):
            (directory / f"seed-{seed}.json").write_bytes(
                (json.dumps({"seed": seed}, indent=2) + "\r\n").encode("utf-8")
            )
        (self.source_dir / "retained-note.txt").write_bytes(b"Original auxiliary bytes\n")
        self.manifest = {
            "schema": "eu26-21-historical-evidence-audit-v1",
            "repository": recovery.REPOSITORY,
            "audit_sha": recovery.PRESERVATION["head_sha"],
            "audit_run_id": recovery.PRESERVATION["run_id"], "audit_run_attempt": 1,
            **{field: False for field in recovery.FALSE_FLAGS},
            "profiles": {
                "source_compatible": {
                    "source": copy.deepcopy(self.source), "seed_count": 30,
                    "verification": {
                        **{key: self.source[key] for key in ("id", "name", "digest")},
                        "api_run_id": self.source["run_id"],
                        "api_head_sha": self.source["head_sha"],
                        "downloaded_zip_sha256": self.source["digest"].split(":", 1)[1],
                        "extraction_directory": self.source["name"],
                    },
                },
                "corrected_official_uci": {},
            },
        }
        self.refresh_ledger()

    def save_manifest(self):
        (self.root / recovery.MANIFEST_NAME).write_text(
            json.dumps(self.manifest), encoding="utf-8",
        )

    def refresh_ledger(self):
        entries = []
        for path in sorted(self.source_dir.rglob("*")):
            if path.is_file():
                content = path.read_bytes()
                entries.append({"path": path.relative_to(self.root).as_posix(),
                                "bytes": len(content),
                                "sha256": hashlib.sha256(content).hexdigest()})
        self.manifest["profiles"]["source_compatible"]["verification"]["extracted_files"] = entries
        self.save_manifest()

    def archive(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for path in sorted(self.root.rglob("*")):
                if path.is_file():
                    archive.writestr(path.relative_to(self.root).as_posix(), path.read_bytes())
        content = output.getvalue()
        return content, "sha256:" + hashlib.sha256(content).hexdigest()

    def test_pins_original_and_preservation_identities(self):
        self.assertEqual(recovery.PRESERVATION["id"], 10058819094)
        self.assertEqual(recovery.PRESERVATION["run_id"], 34233480959)
        self.assertEqual(recovery.PRESERVATION["digest"],
                         "sha256:fb1f994a68472efe45ad5471d083dc57de94bfe07bda3a3fa186b6b55740f17b")
        self.assertEqual(self.source["id"], 9260332711)
        self.assertEqual(recovery.SOURCE_MATRIX_RUN_ID, 31934321927)

    def test_validates_all_source_files_and_preserves_exact_row_bytes(self):
        self.assertEqual(len(recovery.validate_preserved_source(self.root)), 31)
        archive, digest = self.archive()
        api = FakeAPI(archive, digest)
        base = Path(self.temporary.name)
        with patch.dict(recovery.PRESERVATION, {"digest": digest}):
            result = recovery.restore_source_rows(
                api, output_dir=base / "download", rows_dir=base / "rows",
            )
        self.assertEqual(result["verification_status"], "PASS")
        self.assertEqual(result["seed_count"], 30)
        self.assertFalse(result["original_zip_reverified"])
        self.assertFalse(result["optimizer_rerun"])
        for entry in result["copied_seed_files"]:
            self.assertEqual((base / "rows" / entry["path"]).read_bytes(),
                             (self.root / entry["source_path"]).read_bytes())

    def test_manifest_provenance_and_false_flags_are_strict(self):
        original = copy.deepcopy(self.manifest)
        changes = [("schema", "other"), ("repository", "other/repo"),
                   ("audit_sha", "0" * 40), ("audit_run_id", 1),
                   ("audit_run_attempt", True), ("audit_run_attempt", 2)]
        changes.extend((flag, value) for flag in recovery.FALSE_FLAGS for value in (True, 0))
        for field, value in changes:
            with self.subTest(field=field, value=value):
                self.manifest = copy.deepcopy(original)
                self.manifest[field] = value
                self.save_manifest()
                with self.assertRaises(ArtifactError):
                    recovery.validate_preserved_source(self.root)

    def test_wrong_source_and_original_verification_are_rejected(self):
        original = copy.deepcopy(self.manifest)
        for group, field, value in (
            ("source", "id", 10058819094), ("source", "head_sha", "0" * 40),
            ("verification", "api_run_id", 31934321927),
            ("verification", "api_head_sha", "0" * 40),
            ("verification", "downloaded_zip_sha256", "0" * 64),
            ("verification", "extraction_directory", "elsewhere"),
        ):
            with self.subTest(group=group, field=field):
                self.manifest = copy.deepcopy(original)
                self.manifest["profiles"]["source_compatible"][group][field] = value
                self.save_manifest()
                with self.assertRaises(ArtifactError):
                    recovery.validate_preserved_source(self.root)

    def test_file_content_length_missing_and_extra_are_rejected(self):
        target = self.source_dir / "retained-note.txt"
        original = target.read_bytes()
        for content in (b"x" * len(original), b"short"):
            target.write_bytes(content)
            with self.assertRaises(ArtifactError):
                recovery.validate_preserved_source(self.root)
        target.unlink()
        with self.assertRaises(ArtifactError):
            recovery.validate_preserved_source(self.root)
        target.write_bytes(original)
        (self.source_dir / "unlisted.txt").write_bytes(b"extra")
        with self.assertRaisesRegex(ArtifactError, "inventory"):
            recovery.validate_preserved_source(self.root)

    def test_duplicate_unsafe_and_noncanonical_ledger_paths_are_rejected(self):
        verification = self.manifest["profiles"]["source_compatible"]["verification"]
        original = copy.deepcopy(verification["extracted_files"])
        verification["extracted_files"].append(copy.deepcopy(original[0]))
        self.save_manifest()
        with self.assertRaisesRegex(ArtifactError, "duplicate"):
            recovery.validate_preserved_source(self.root)
        for name in ("../outside", "/absolute", "other/seed-1.json", "back\\slash",
                     self.source["name"] + "//nested/seed-1.json"):
            with self.subTest(path=name):
                verification["extracted_files"] = copy.deepcopy(original)
                verification["extracted_files"][0]["path"] = name
                self.save_manifest()
                with self.assertRaises(ArtifactError):
                    recovery.validate_preserved_source(self.root)

    def test_missing_duplicate_and_noninteger_seeds_fail_after_valid_file_hashes(self):
        target = self.source_dir / "nested" / "seed-1.json"
        for seed in (2, True, "1"):
            with self.subTest(seed=seed):
                target.write_text(json.dumps({"seed": seed}), encoding="utf-8")
                self.refresh_ledger()
                with self.assertRaises(ValueError):
                    recovery.validate_preserved_source(self.root)
        target.unlink()
        self.refresh_ledger()
        with self.assertRaisesRegex(ValueError, "exactly 30"):
            recovery.validate_preserved_source(self.root)

    def test_duplicate_json_keys_fail_even_if_file_hash_matches(self):
        target = self.source_dir / "nested" / "seed-1.json"
        target.write_bytes(b'{"seed": 1, "seed": 1}')
        self.refresh_ledger()
        with self.assertRaisesRegex(ArtifactError, "duplicate"):
            recovery.validate_preserved_source(self.root)

    def test_symlink_cannot_replace_a_preserved_file(self):
        target = self.source_dir / "retained-note.txt"
        outside = Path(self.temporary.name) / "same-bytes.txt"
        outside.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaises(ArtifactError):
            recovery.validate_preserved_source(self.root)

    def test_outer_run_and_archive_metadata_fail_closed(self):
        archive, digest = self.archive()
        cases = [("run", "run_attempt", 2), ("run", "head_sha", "0" * 40),
                 ("run", "conclusion", "failure"), ("run", "path", "other.yml"),
                 ("artifact", "id", 1), ("artifact", "expired", True),
                 ("artifact", "digest", "sha256:" + "0" * 64)]
        for index, (group, field, value) in enumerate(cases):
            with self.subTest(group=group, field=field):
                api = FakeAPI(archive, digest)
                getattr(api, group)[field] = value
                base = Path(self.temporary.name) / str(index)
                with patch.dict(recovery.PRESERVATION, {"digest": digest}):
                    with self.assertRaises(ArtifactError):
                        recovery.restore_source_rows(api, output_dir=base / "download",
                                                     rows_dir=base / "rows")
                self.assertFalse((base / "rows").exists())

    def test_outer_downloaded_bytes_must_match_pinned_digest(self):
        archive, digest = self.archive()
        api = FakeAPI(archive + b"tampered", digest)
        base = Path(self.temporary.name)
        with patch.dict(recovery.PRESERVATION, {"digest": digest}):
            with self.assertRaisesRegex(ArtifactError, "downloaded ZIP SHA mismatch"):
                recovery.restore_source_rows(api, output_dir=base / "download",
                                             rows_dir=base / "rows")
        self.assertFalse((base / "rows").exists())

    def test_existing_destination_is_not_overwritten(self):
        base = Path(self.temporary.name)
        rows = base / "rows"
        rows.mkdir()
        (rows / "retained.txt").write_bytes(b"retained")
        with self.assertRaisesRegex(ArtifactError, "already exists"):
            recovery.restore_source_rows(None, output_dir=base / "download", rows_dir=rows)
        self.assertEqual((rows / "retained.txt").read_bytes(), b"retained")

    def test_cli_refuses_local_execution_before_writing(self):
        base = Path(self.temporary.name)
        args = ["restore", "--output-dir", str(base / "download"),
                "--rows-dir", str(base / "rows"), "--status-json", str(base / "status.json")]
        with patch.object(sys, "argv", args), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SystemExit, "CI-only"):
                recovery.main()
        self.assertFalse((base / "status.json").exists())

    def test_cli_preserves_failure_status_and_exits_nonzero(self):
        base = Path(self.temporary.name)
        status = base / "status.json"
        args = ["restore", "--output-dir", str(base / "download"),
                "--rows-dir", str(base / "rows"), "--status-json", str(status)]
        environment = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": recovery.REPOSITORY}
        with patch.object(sys, "argv", args), patch.dict(os.environ, environment, clear=True):
            with patch.object(recovery, "GitHubReader", side_effect=ArtifactError("synthetic failure")):
                with patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit) as failure:
                    recovery.main()
        self.assertEqual(failure.exception.code, 1)
        result = json.loads(status.read_text(encoding="utf-8"))
        self.assertEqual(result["verification_status"], "FAIL")
        self.assertEqual(result["preservation"]["id"], 10058819094)
        self.assertFalse(result["optimizer_rerun"])
        self.assertIn("synthetic failure", result["error"])


if __name__ == "__main__":
    unittest.main()

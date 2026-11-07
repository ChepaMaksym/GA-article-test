"""CI-only evidence transport and nested inventory checks."""
import io
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from studies.knapsack_parameters.population_size_study import authority
from studies.knapsack_parameters.population_size_study.io_utils import (
    extract_artifact, safe_child, verify_manifest, write_manifest)


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Evidence fixtures run only in GitHub Actions")
class EvidenceTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def archive(self, members):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for name, value in members:
                archive.writestr(name, value)
        return output.getvalue()

    def test_nested_manifests_are_retained_and_compatible(self):
        child = self.root / "mathematics"
        child.mkdir()
        (child / "value.txt").write_text("fixture", encoding="utf-8")
        write_manifest(child)
        write_manifest(self.root)
        manifest = verify_manifest(self.root)
        self.assertIn("mathematics/file_manifest.json", {row["path"] for row in manifest["files"]})
        self.assertEqual(manifest, authority.verify_manifest(self.root))
        (child / "value.txt").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "checksum"):
            verify_manifest(self.root)

    def test_unsafe_paths_are_rejected(self):
        for name in ("../escape", "/absolute", "C:/file", "a\\b", ""):
            with self.assertRaises(ValueError):
                safe_child(self.root, name)

    def test_zip_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            extract_artifact(self.archive([("../escape", b"invalid")]), self.root / "out")
        self.assertFalse((self.root / "escape").exists())

    def test_zip_rejects_symlinks(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            item = zipfile.ZipInfo("link")
            item.create_system = 3
            item.external_attr = 0o120777 << 16
            archive.writestr(item, "../target")
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            extract_artifact(output.getvalue(), self.root / "out")

    def test_zip_rejects_oversized_contents(self):
        raw = self.archive([("file", b"0123456789")])
        with self.assertRaisesRegex(ValueError, "Expanded"):
            extract_artifact(raw, self.root / "out", expanded_limit=9)
        with self.assertRaisesRegex(ValueError, "Compressed"):
            extract_artifact(raw, self.root / "other", compressed_limit=len(raw)-1)

    def test_zip_file_stream_matches_byte_transport(self):
        raw = self.archive([("nested/file", b"retained bytes")])
        path = self.root / "artifact.zip"
        path.write_bytes(raw)
        extract_artifact(path, self.root / "file_transport")
        extract_artifact(raw, self.root / "byte_transport")
        self.assertEqual((self.root / "file_transport/nested/file").read_bytes(),
                         (self.root / "byte_transport/nested/file").read_bytes())

    def test_unlisted_files_are_rejected(self):
        (self.root / "file").write_bytes(b"content")
        write_manifest(self.root)
        (self.root / "extra").write_bytes(b"unlisted")
        with self.assertRaisesRegex(ValueError, "inventory"):
            verify_manifest(self.root)

    def test_existing_destinations_are_never_overwritten(self):
        output = self.root / "out"
        output.mkdir()
        (output / "file").write_bytes(b"original")
        with self.assertRaisesRegex(ValueError, "empty"):
            extract_artifact(self.archive([("file", b"replacement")]), output)
        self.assertEqual((output / "file").read_bytes(), b"original")

"""Small control-plane checks; CI only, no KPLIB search or new statistics."""
import copy
import importlib
from pathlib import Path
import tempfile
import unittest

from . import contract as c


class ContractTests(unittest.TestCase):
    def test_reporting_entry_point_imports(self):
        report = importlib.import_module("studies.adaptive_parameters.mutation_only.reporting")
        self.assertTrue(callable(report.build_report))

    def test_root_and_registration(self):
        self.assertTrue((c.ROOT / "AGENTS.md").is_file())
        self.assertEqual(c.read_json(c.MODULE / "registration.json")["protocol_id"], c.PROTOCOL)

    def test_phase_markers(self):
        for p in ("tests", "prepare", "pilot"):
            self.assertEqual(c.phase("Run [adaptive-mutation:" + p + "]"), p)
        for message in ("", "[adaptive-mutation:main]", "[adaptive-mutation:tests] [diversity-main:main]",
                        "[adaptive-mutation:tests] [adaptive-mutation:prepare]"):
            with self.assertRaises(ValueError):
                c.phase(message)

    def test_complete_manifest_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c.write_json(root / "a.json", {"fixture": 1})
            c.write_manifest(root)
            c.verify_manifest(root)
            c.write_json(root / "a.json", {"fixture": 2})
            with self.assertRaises(ValueError):
                c.verify_manifest(root)

    def test_extra_or_duplicate_manifest_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c.write_json(root / "a.json", {"fixture": 1})
            c.write_manifest(root)
            manifest = c.read_json(root / "file_manifest.json")
            manifest["files"].append(copy.deepcopy(manifest["files"][0]))
            c.write_json(root / "file_manifest.json", manifest)
            with self.assertRaises(ValueError):
                c.verify_manifest(root)
            c.write_manifest(root)
            c.write_json(root / "unexpected.json", {})
            with self.assertRaises(ValueError):
                c.verify_manifest(root)

    def test_unsafe_manifest_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c.write_json(root / "a.json", {})
            c.write_manifest(root)
            manifest = c.read_json(root / "file_manifest.json")
            manifest["files"][0]["path"] = "../a.json"
            c.write_json(root / "file_manifest.json", manifest)
            with self.assertRaises(ValueError):
                c.verify_manifest(root)

    def test_source_identity_uses_content(self):
        manifest = c.source_manifest()
        paths = [row["path"] for row in manifest["files"]]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn(c.WORKFLOW, paths)
        self.assertIn(c.REL + "engine.py", paths)
        self.assertIn(c.REL + "verifier.py", paths)
        self.assertEqual(len(manifest["sha256"]), 64)

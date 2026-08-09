from __future__ import annotations

import copy
import json
import tempfile
import unittest
import zlib
from pathlib import Path

from eu2613.artifact import _inflate_target, validate_octave_attestation, validate_python_attestation, verify_metadata
from eu2613.contract import load_contract
from eu2613.errors import VerificationError
from eu2613.integrity import implementation_manifest
from eu2613.report import write_json_once


def metadata_fixture(contract):
    return {
        "id": contract["zenodo"]["record_id"],
        "doi": contract["zenodo"]["doi"],
        "created": contract["zenodo"]["created"],
        "updated": contract["zenodo"]["updated"],
        "metadata": {
            "publication_date": contract["zenodo"]["publication_date"],
            "license": {"id": contract["zenodo"]["license"]},
            "title": "Repelling restart potential -- reproducibility and additional figures",
        },
        "files": [
            {
                "key": name,
                "size": cfg["bytes"],
                "checksum": "md5:" + cfg["md5"],
                "links": {"self": cfg["url"]},
            }
            for name, cfg in contract["zenodo_files"].items()
        ],
    }


class ArtifactHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract()

    def encoded_metadata(self, value) -> bytes:
        return json.dumps(value).encode("utf-8")

    def test_metadata(self) -> None:
        report = verify_metadata(self.encoded_metadata(metadata_fixture(self.contract)), self.contract)
        self.assertEqual(report["status"], "PASS_ZENODO_METADATA")
        self.assertEqual(report["files"]["repelling.zip"]["md5_status"], "ZENODO_DECLARED_NOT_RECOMPUTED")

    def test_mutation_metadata_md5(self) -> None:
        value = metadata_fixture(self.contract)
        value["files"][1]["checksum"] = "md5:" + "0" * 32
        with self.assertRaises(VerificationError):
            verify_metadata(self.encoded_metadata(value), self.contract)

    def test_mutation_metadata_size(self) -> None:
        value = metadata_fixture(self.contract)
        value["files"][1]["size"] -= 1
        with self.assertRaises(VerificationError):
            verify_metadata(self.encoded_metadata(value), self.contract)

    def test_mutation_metadata_license(self) -> None:
        value = metadata_fixture(self.contract)
        value["metadata"]["license"]["id"] = "none"
        with self.assertRaises(VerificationError):
            verify_metadata(self.encoded_metadata(value), self.contract)

    def test_mutation_metadata_duplicate_file(self) -> None:
        value = metadata_fixture(self.contract)
        value["files"].append(copy.deepcopy(value["files"][0]))
        with self.assertRaises(VerificationError):
            verify_metadata(self.encoded_metadata(value), self.contract)

    def test_inflate_raw_deflate(self) -> None:
        raw = b"endpoint" * 20
        compressor = zlib.compressobj(wbits=-15)
        payload = compressor.compress(raw) + compressor.flush()
        self.assertEqual(_inflate_target(payload, len(raw), "TEST"), raw)

    def test_mutation_inflate_trailing_bytes(self) -> None:
        raw = b"endpoint" * 20
        compressor = zlib.compressobj(wbits=-15)
        payload = compressor.compress(raw) + compressor.flush() + b"x"
        with self.assertRaises(VerificationError):
            _inflate_target(payload, len(raw), "TEST")

    def test_mutation_inflate_wrong_size(self) -> None:
        raw = b"endpoint" * 20
        compressor = zlib.compressobj(wbits=-15)
        payload = compressor.compress(raw) + compressor.flush()
        with self.assertRaises(VerificationError):
            _inflate_target(payload, len(raw) - 1, "TEST")

    def test_mutation_report_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            write_json_once(path, {"status": "first"})
            with self.assertRaises(VerificationError):
                write_json_once(path, {"status": "second"})
            self.assertEqual(json.loads(path.read_text())["status"], "first")

    def test_python_attestation(self) -> None:
        manifest = implementation_manifest()
        value = {"candidate_id": "EU26-13", "status": "PASS_FAIL_CLOSED_MUTATION_SUITE", "failures": 0, "errors": 0, "tests_run": 50, "mutation_tests": 30, "implementation_files": manifest["files"], "implementation_manifest_sha256": manifest["sha256"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tests.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertEqual(validate_python_attestation(path, self.contract)["tests_run"], 50)

    def test_mutation_python_attestation_count(self) -> None:
        manifest = implementation_manifest()
        value = {"candidate_id": "EU26-13", "status": "PASS_FAIL_CLOSED_MUTATION_SUITE", "failures": 0, "errors": 0, "tests_run": 50, "mutation_tests": 19, "implementation_files": manifest["files"], "implementation_manifest_sha256": manifest["sha256"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tests.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(VerificationError):
                validate_python_attestation(path, self.contract)

    def test_mutation_python_attestation_manifest(self) -> None:
        manifest = implementation_manifest()
        value = {"candidate_id": "EU26-13", "status": "PASS_FAIL_CLOSED_MUTATION_SUITE", "failures": 0, "errors": 0, "tests_run": 50, "mutation_tests": 30, "implementation_files": manifest["files"], "implementation_manifest_sha256": "0" * 64}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tests.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(VerificationError):
                validate_python_attestation(path, self.contract)


if __name__ == "__main__":
    unittest.main()

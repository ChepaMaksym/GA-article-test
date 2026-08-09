from __future__ import annotations

import hashlib
import io
import json
import stat
import unittest
import zipfile
from copy import deepcopy

from eu2612.code import (
    CodeIdentityError,
    validate_code_archive,
    validate_download,
    validate_runner,
    validate_zenodo_record,
)
from eu2612.contract import load_contract
from test_support import synthetic_record, tiny_code_contract


class ZenodoMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()
        self.payload = synthetic_record(self.contract)

    def test_frozen_metadata_passes(self) -> None:
        result = validate_zenodo_record(self.payload, self.contract)
        self.assertEqual(result["record_id"], 7624677)
        self.assertEqual(result["raw_archive_md5_status"], "ZENODO_DECLARED_NOT_RECOMPUTED")

    def test_record_id_mutation_fails(self) -> None:
        value = json.loads(self.payload)
        value["id"] += 1
        with self.assertRaises(CodeIdentityError):
            validate_zenodo_record(json.dumps(value).encode(), self.contract)

    def test_license_mutation_fails(self) -> None:
        value = json.loads(self.payload)
        value["metadata"]["license"]["id"] = "proprietary"
        with self.assertRaises(CodeIdentityError):
            validate_zenodo_record(json.dumps(value).encode(), self.contract)

    def test_file_checksum_mutation_fails(self) -> None:
        value = json.loads(self.payload)
        value["files"][0]["checksum"] = "md5:" + "0" * 32
        with self.assertRaises(CodeIdentityError):
            validate_zenodo_record(json.dumps(value).encode(), self.contract)

    def test_duplicate_file_key_fails(self) -> None:
        value = json.loads(self.payload)
        value["files"].append(deepcopy(value["files"][0]))
        with self.assertRaises(CodeIdentityError):
            validate_zenodo_record(json.dumps(value).encode(), self.contract)


class SourceArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload, self.contract = tiny_code_contract(
            {"LICENCE": b"MIT License\npermission\n", "modde/core.py": b"x = 1\r\n"}
        )

    def test_small_download_identity_passes(self) -> None:
        self.assertEqual(validate_download("ModDE.zip", self.payload, self.contract)["bytes"], len(self.payload))

    def test_small_download_hash_mutation_fails(self) -> None:
        contract = deepcopy(self.contract)
        contract["zenodo_files"]["ModDE.zip"]["sha256"] = "0" * 64
        with self.assertRaises(CodeIdentityError):
            validate_download("ModDE.zip", self.payload, contract)

    def test_static_archive_and_normalized_blob_pass(self) -> None:
        result = validate_code_archive(self.payload, self.contract)
        self.assertEqual(result["required_members"], 2)
        self.assertEqual(result["embedded_license"], "MIT")
        self.assertFalse(result["artifact_exact_tree_match"])
        self.assertEqual(result["matched_git_blobs"], 2)
        self.assertEqual(result["tracked_git_blobs"], 3)

    def test_unfrozen_extra_member_fails(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.payload), "r") as source:
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for info in source.infolist():
                    archive.writestr(info.filename, source.read(info))
                archive.writestr("unfrozen.txt", b"unexpected")
        payload = buffer.getvalue()
        contract = deepcopy(self.contract)
        contract["zenodo_files"]["ModDE.zip"] = {
            "bytes": len(payload),
            "md5": hashlib.md5(payload).hexdigest(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        with self.assertRaises(CodeIdentityError):
            validate_code_archive(payload, contract)

    def test_member_hash_mutation_fails(self) -> None:
        contract = deepcopy(self.contract)
        contract["required_code_members"][1]["normalized_git_blob"] = "0" * 40
        with self.assertRaises(CodeIdentityError):
            validate_code_archive(self.payload, contract)

    def test_path_traversal_member_fails(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("LICENCE", b"MIT License\n")
            archive.writestr("../bad", b"x")
        payload = buffer.getvalue()
        contract = deepcopy(self.contract)
        contract["zenodo_files"]["ModDE.zip"] = {
            "bytes": len(payload),
            "md5": hashlib.md5(payload).hexdigest(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        with self.assertRaises(CodeIdentityError):
            validate_code_archive(payload, contract)

    def test_symlink_member_fails(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("LICENCE", b"MIT License\n")
            info = zipfile.ZipInfo("modde/link")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b"target")
        payload = buffer.getvalue()
        contract = deepcopy(self.contract)
        contract["zenodo_files"]["ModDE.zip"] = {
            "bytes": len(payload),
            "md5": hashlib.md5(payload).hexdigest(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        with self.assertRaises(CodeIdentityError):
            validate_code_archive(payload, contract)


class RunnerTests(unittest.TestCase):
    MARKERS = "\n".join(
        (
            "np.random.seed(seed)",
            "for iid in range(10):",
            "for seed in range(5):",
            "budget=50000",
            "'L-SHADE'",
            "'mutation_base':'target'",
            "'mutation_reference':'pbest'",
            "'lpsr':True",
            "'lambda_' : 18*dim",
            "'adaptation_method_F' :'shade'",
            "'adaptation_method_CR' : 'shade'",
        )
    ).encode()

    def contract(self, payload: bytes) -> dict:
        return {
            "zenodo_files": {
                "Common_DE_runner.py": {
                    "bytes": len(payload),
                    "md5": hashlib.md5(payload).hexdigest(),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            }
        }

    def test_runner_markers_pass(self) -> None:
        result = validate_runner(self.MARKERS, self.contract(self.MARKERS))
        self.assertEqual(result["markers"], 11)

    def test_missing_seed_marker_fails(self) -> None:
        payload = self.MARKERS.replace(b"np.random.seed(seed)\n", b"")
        with self.assertRaises(CodeIdentityError):
            validate_runner(payload, self.contract(payload))


if __name__ == "__main__":
    unittest.main()

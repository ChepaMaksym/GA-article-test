from __future__ import annotations

import copy
import hashlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

import zstandard

from eu2614.contract import load_contract
from eu2614.errors import VerificationError
from eu2614.result_archive import extract_frozen_member, verify_checksum_manifest
from eu2614.tar_safety import validate_tar_member

from test_safe_pickle import safe_array_pickle


def _file_identity(payload: bytes) -> dict[str, object]:
    return {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "md5": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
    }


def _archive(entries: list[tuple[str, bytes, bytes]]) -> tuple[bytes, dict[str, tuple[int, int]]]:
    buffer = io.BytesIO()
    offsets: dict[str, tuple[int, int]] = {}
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, payload, kind in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(payload) if kind == tarfile.REGTYPE else 0
            archive.addfile(info, io.BytesIO(payload) if kind == tarfile.REGTYPE else None)
    raw = buffer.getvalue()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive:
            offsets[member.name] = (member.offset_data, member.size)
    return zstandard.ZstdCompressor(level=1).compress(raw), offsets


def _synthetic_contract(compressed: bytes, target: str, payload: bytes, offset: int) -> dict:
    contract = copy.deepcopy(load_contract())
    contract["files"]["msc_cec2020.tar.zst"] = _file_identity(compressed)
    contract["member"] = {
        "path": target,
        "tar_data_offset": offset,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    return contract


class ArchiveTests(unittest.TestCase):
    def test_streaming_archive_returns_exact_member(self) -> None:
        target = "experiments/cec2020/d15/MSC-CMA/maxevals_3000000/f1.pkl"
        payload = safe_array_pickle()
        compressed, offsets = _archive(
            [("experiments", b"", tarfile.DIRTYPE), (target, payload, tarfile.REGTYPE)]
        )
        contract = _synthetic_contract(compressed, target, payload, offsets[target][0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.tar.zst"
            path.write_bytes(compressed)
            observed, report = extract_frozen_member(path, contract)
        self.assertEqual(observed, payload)
        self.assertEqual(report["gate"], "PASS_FULL_ARCHIVE_IDENTITY")

    def test_duplicate_member_is_rejected_even_with_matching_archive_hash(self) -> None:
        target = "experiments/cec2020/d15/MSC-CMA/maxevals_3000000/f1.pkl"
        payload = safe_array_pickle()
        compressed, offsets = _archive(
            [(target, payload, tarfile.REGTYPE), (target, payload, tarfile.REGTYPE)]
        )
        contract = _synthetic_contract(compressed, target, payload, offsets[target][0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.tar.zst"
            path.write_bytes(compressed)
            with self.assertRaises(VerificationError):
                extract_frozen_member(path, contract)

    def test_unsafe_tar_path_is_rejected(self) -> None:
        member = tarfile.TarInfo("../escape")
        member.type = tarfile.REGTYPE
        with self.assertRaises(VerificationError):
            validate_tar_member(member, set())

    def test_tar_link_is_rejected(self) -> None:
        member = tarfile.TarInfo("safe-name")
        member.type = tarfile.SYMTYPE
        member.linkname = "elsewhere"
        with self.assertRaises(VerificationError):
            validate_tar_member(member, set())

    def test_checksum_manifest_requires_unique_exact_binding(self) -> None:
        contract = copy.deepcopy(load_contract())
        result_hash = contract["files"]["msc_cec2020.tar.zst"]["sha256"]
        text = f"{result_hash}  msc_cec2020.tar.zst\n".encode("ascii")
        contract["files"]["SHA256SUMS"] = _file_identity(text)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SHA256SUMS"
            path.write_bytes(text)
            report = verify_checksum_manifest(path, contract)
            self.assertEqual(report["gate"], "PASS_CHECKSUM_MANIFEST")
            duplicate = text + f"{result_hash}  copy.tar.zst\n".encode("ascii")
            path.write_bytes(duplicate)
            contract["files"]["SHA256SUMS"] = _file_identity(duplicate)
            with self.assertRaises(VerificationError):
                verify_checksum_manifest(path, contract)


if __name__ == "__main__":
    unittest.main()

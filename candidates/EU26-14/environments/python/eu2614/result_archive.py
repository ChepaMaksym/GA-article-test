"""Full-hash-first streaming zstd/tar endpoint extraction."""

from __future__ import annotations

import hashlib
import re
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any

import zstandard

from .errors import VerificationError
from .hashing import open_verified
from .tar_safety import validate_tar_member


_CHECKSUM_LINE = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)\n")
MAX_TAR_TRAILING_ZERO_BYTES = 1024 * 1024


def verify_checksum_manifest(
    path: Path, contract: dict[str, Any]
) -> dict[str, Any]:
    try:
        with open_verified(
            path, contract["files"]["SHA256SUMS"], label="SHA256SUMS"
        ) as verified:
            identity = verified.identity
            payload = verified.stream.read(contract["files"]["SHA256SUMS"]["bytes"] + 1)
            if len(payload) != contract["files"]["SHA256SUMS"]["bytes"]:
                raise VerificationError("SHA256SUMS read length differs")
            text = payload.decode("ascii", errors="strict")
    except (OSError, UnicodeError) as error:
        raise VerificationError(f"cannot read SHA256SUMS: {error}") from error
    position = 0
    entries: dict[str, str] = {}
    for match in _CHECKSUM_LINE.finditer(text):
        if match.start() != position:
            raise VerificationError("SHA256SUMS syntax differs")
        digest, name = match.groups()
        if name in entries:
            raise VerificationError("SHA256SUMS contains a duplicate filename")
        entries[name] = digest
        position = match.end()
    if position != len(text):
        raise VerificationError("SHA256SUMS has trailing or malformed data")
    expected = contract["files"]["msc_cec2020.tar.zst"]["sha256"]
    if entries.get("msc_cec2020.tar.zst") != expected:
        raise VerificationError("CEC2020 checksum-manifest binding differs")
    if list(entries.values()).count(expected) != 1:
        raise VerificationError("CEC2020 SHA-256 is not unique in SHA256SUMS")
    return {"gate": "PASS_CHECKSUM_MANIFEST", "identity": identity, "entries": entries}


def extract_frozen_member(
    path: Path, contract: dict[str, Any]
) -> tuple[bytes, dict[str, Any]]:
    """Hash the complete archive, then stream and authenticate one member."""
    expected = contract["member"]
    seen: set[str] = set()
    types: Counter[str] = Counter()
    payload: bytes | None = None
    selected_offset: int | None = None
    selected_header_offset: int | None = None
    trailing_zeros = 0
    try:
        with open_verified(
            path,
            contract["files"]["msc_cec2020.tar.zst"],
            label="CEC2020 result archive",
        ) as verified:
            identity = verified.identity
            compressed = verified.stream
            with zstandard.ZstdDecompressor().stream_reader(
                compressed, read_across_frames=True, closefd=False
            ) as reader:
                with tarfile.open(fileobj=reader, mode="r|", errorlevel=2) as archive:
                    for member in archive:
                        validate_tar_member(member, seen)
                        types["file" if member.isfile() else "directory"] += 1
                        if member.name != expected["path"]:
                            continue
                        if not member.isfile():
                            raise VerificationError("frozen endpoint member is not regular")
                        if payload is not None:
                            raise VerificationError("frozen endpoint member occurs more than once")
                        if member.offset_data != expected["tar_data_offset"]:
                            raise VerificationError("frozen endpoint tar data offset differs")
                        if member.size != expected["bytes"]:
                            raise VerificationError("frozen endpoint member size differs")
                        stream = archive.extractfile(member)
                        if stream is None:
                            raise VerificationError("cannot read frozen endpoint member")
                        payload = stream.read(expected["bytes"] + 1)
                        if len(payload) != expected["bytes"]:
                            raise VerificationError("frozen endpoint member is truncated")
                        if hashlib.sha256(payload).hexdigest() != expected["sha256"]:
                            raise VerificationError("frozen endpoint member SHA-256 differs")
                        selected_offset = member.offset_data
                        selected_header_offset = member.offset
                while chunk := reader.read(64 * 1024):
                    trailing_zeros += len(chunk)
                    if trailing_zeros > MAX_TAR_TRAILING_ZERO_BYTES or any(chunk):
                        raise VerificationError("tar has non-zero or excessive trailing data")
            if compressed.tell() != identity["bytes"]:
                raise VerificationError("zstd decoder did not consume the complete archive")
    except VerificationError:
        raise
    except (OSError, tarfile.TarError, zstandard.ZstdError) as error:
        raise VerificationError(f"invalid CEC2020 zstd/tar archive: {error}") from error
    if payload is None:
        raise VerificationError("frozen endpoint member is missing")
    return payload, {
        "gate": "PASS_FULL_ARCHIVE_IDENTITY",
        "identity": identity,
        "tar_entries": len(seen),
        "tar_types": dict(sorted(types.items())),
        "member": {
            "path": expected["path"],
            "header_offset": selected_header_offset,
            "data_offset": selected_offset,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        "trailing_zero_bytes": trailing_zeros,
    }

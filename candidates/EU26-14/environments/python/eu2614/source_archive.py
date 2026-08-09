"""Complete source-archive identity and Git-byte mapping."""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any

from .contract import CANDIDATE_ROOT
from .errors import VerificationError
from .hashing import git_blob_sha1, open_verified
from .tar_safety import validate_tar_member


SOURCE_MEMBERS_PATH = CANDIDATE_ROOT / "config" / "source_members.json"
MAX_REQUIRED_MEMBER_BYTES = 100_000


def load_source_manifest(path: Path = SOURCE_MEMBERS_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot load source member manifest: {error}") from error
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "candidate_id",
        "archive_root",
        "upstream_commit",
        "members",
    }:
        raise VerificationError("source member manifest schema differs")
    if value["schema_version"] != "1.0.0" or value["candidate_id"] != "EU26-14":
        raise VerificationError("source member manifest identity differs")
    if value["archive_root"] != "src-a888416":
        raise VerificationError("source archive root differs")
    if value["upstream_commit"] != "a88841620b2eddd13a1fab85331fcfc8caa1e85f":
        raise VerificationError("source commit differs")
    if not isinstance(value["members"], dict) or not value["members"]:
        raise VerificationError("source member set is empty")
    return value


def verify_source_archive(
    path: Path, contract: dict[str, Any], source_manifest: dict[str, Any]
) -> dict[str, Any]:
    root = source_manifest["archive_root"]
    expected = source_manifest["members"]
    expected_paths = {f"{root}/{relative}": details for relative, details in expected.items()}
    observed_required: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    regular = 0
    directories = 0
    try:
        with open_verified(
            path, contract["files"]["source.tar.gz"], label="source archive"
        ) as verified:
            identity = verified.identity
            with tarfile.open(fileobj=verified.stream, mode="r:gz", errorlevel=2) as archive:
                for member in archive:
                    validate_tar_member(member, seen)
                    if member.isdir():
                        directories += 1
                        continue
                    regular += 1
                    if member.name not in expected_paths:
                        continue
                    details = expected_paths[member.name]
                    if member.size != details["bytes"] or member.size > MAX_REQUIRED_MEMBER_BYTES:
                        raise VerificationError(f"source member size differs: {member.name}")
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise VerificationError(f"cannot read source member: {member.name}")
                    payload = stream.read(MAX_REQUIRED_MEMBER_BYTES + 1)
                    if len(payload) != member.size:
                        raise VerificationError(f"source member is truncated: {member.name}")
                    sha256 = hashlib.sha256(payload).hexdigest()
                    blob = git_blob_sha1(payload)
                    if sha256 != details["sha256"] or blob != details["git_blob_sha1"]:
                        raise VerificationError(f"source/Git byte mapping differs: {member.name}")
                    observed_required[member.name] = {
                        "bytes": len(payload),
                        "sha256": sha256,
                        "git_blob_sha1": blob,
                    }
    except VerificationError:
        raise
    except (OSError, tarfile.TarError) as error:
        raise VerificationError(f"invalid source tar archive: {error}") from error
    if set(observed_required) != set(expected_paths):
        missing = sorted(set(expected_paths) - set(observed_required))
        raise VerificationError(f"required source members are missing: {missing}")
    if root not in seen:
        raise VerificationError("source archive root directory is missing")
    return {
        "gate": "PASS_SOURCE_IDENTITY",
        "identity": identity,
        "archive_root": root,
        "upstream_commit": source_manifest["upstream_commit"],
        "tar_entries": len(seen),
        "regular_files": regular,
        "directories": directories,
        "required_members": dict(sorted(observed_required.items())),
    }

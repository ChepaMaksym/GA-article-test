"""Load and validate the preregistered EU26-12 contract."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


CANDIDATE_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = CANDIDATE_ROOT / "config" / "verification_contract.json"
CONTRACT_SHA256 = "31d7d0e219afde23522753cae4e3089f7483fc5a4f1fbbd6cfa5b9bb01346997"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
SHA1_PATTERN = re.compile(r"[0-9a-f]{40}")
ARTIFACT_ONLY_ENTRIES = (
    "modde/",
    "modde/.ipynb_checkpoints/",
    "modde/.ipynb_checkpoints/modularde-checkpoint.py",
    "modde/.ipynb_checkpoints/parameters-checkpoint.py",
    "modde/.ipynb_checkpoints/population-checkpoint.py",
    "modde/.ipynb_checkpoints/sampling-checkpoint.py",
    "modde/.ipynb_checkpoints/utils-checkpoint.py",
    "modde/.ipynb_checkpoints/__init__-checkpoint.py",
    "modde/__pycache__/",
    "modde/__pycache__/modularde.cpython-38.pyc",
    "modde/__pycache__/parameters.cpython-38.pyc",
    "modde/__pycache__/population.cpython-38.pyc",
    "modde/__pycache__/sampling.cpython-38.pyc",
    "modde/__pycache__/utils.cpython-38.pyc",
    "modde/__pycache__/__init__.cpython-38.pyc",
    "tests/",
    "tests/.ipynb_checkpoints/",
    "tests/.ipynb_checkpoints/create_expected-checkpoint.py",
    "tests/.ipynb_checkpoints/test_modularde-checkpoint.py",
    "tests/.ipynb_checkpoints/__init__-checkpoint.py",
    "tests/__pycache__/",
    "tests/__pycache__/test_modularde.cpython-38.pyc",
    "tests/__pycache__/__init__.cpython-38.pyc",
)


class ContractError(ValueError):
    """Raised when the frozen contract or claim boundary is malformed."""


def _reject_constant(token: str) -> None:
    raise ContractError(f"non-finite JSON constant is forbidden: {token}")


def _unique_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ContractError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _integer(value: Any, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError(f"{name} must be an integer >= {minimum}")
    return value


def _hash(value: Any, pattern: re.Pattern[str], *, name: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ContractError(f"{name} is not a canonical lowercase digest")
    return value


def _safe_member(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ContractError(f"{name} is not a safe POSIX member path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ContractError(f"{name} is not a safe relative POSIX path")
    return value


def _read(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        payload = path.read_bytes()
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read contract {path}: {error}") from error
    if not isinstance(value, dict):
        raise ContractError("contract root must be an object")
    return payload, value


def validate_contract(value: dict[str, Any]) -> dict[str, Any]:
    """Validate scientific identity, endpoint, and non-vendoring invariants."""

    if value.get("schema_version") != "1.0.0":
        raise ContractError("schema_version changed")
    if value.get("candidate_id") != "EU26-12":
        raise ContractError("candidate_id is not EU26-12")
    if value.get("status") != "TARGETED_ARTIFACT_REPLAY_ONLY":
        raise ContractError("status must remain TARGETED_ARTIFACT_REPLAY_ONLY")
    if value.get("paper_mapping") != "PAPER_EXPERIMENT_ARTIFACT_MAPPING":
        raise ContractError("paper mapping boundary changed")
    required_forbidden = {
        "PASS_FULL",
        "PASS_LITERAL_PAPER_ENDPOINT",
        "HISTORICAL_DEPENDENCY_ENVIRONMENT_PROVEN",
        "FULL_ARCHIVE_MD5_RECOMPUTED",
        "EXACT_ARTIFACT_GIT_TREE_MATCH",
    }
    forbidden = value.get("forbidden_claims")
    if not isinstance(forbidden, list) or not required_forbidden.issubset(set(forbidden)):
        raise ContractError("mandatory forbidden claims are incomplete")

    endpoint = value.get("endpoint")
    zip64 = value.get("zip64")
    files = value.get("zenodo_files")
    members = value.get("raw_members")
    execution = value.get("verification_execution")
    upstream = value.get("upstream")
    if not all(
        isinstance(item, dict)
        for item in (endpoint, zip64, files, members, execution, upstream)
    ):
        raise ContractError("endpoint/archive sections must be objects")
    if endpoint.get("dimension") != 20 or endpoint.get("run_index") != 0:
        raise ContractError("frozen endpoint dimension or run index changed")
    if endpoint.get("instance") != 0 or endpoint.get("seed") != 0:
        raise ContractError("frozen instance/seed changed")
    if endpoint.get("logged_evaluations") != 50002:
        raise ContractError("frozen logged evaluation endpoint changed")
    if endpoint.get("best_y_decimal") != "1.698652750709869e-14":
        raise ContractError("frozen exact objective changed")

    if "artifact_maps_to_commit" in upstream:
        raise ContractError("superseded exact-tree mapping field was restored")
    if upstream.get("artifact_exact_tree_match") is not False:
        raise ContractError("artifact must not be promoted to an exact Git tree match")
    if upstream.get("mapping_status") != "PARTIAL_14_OF_15_GIT_BLOB_CORROBORATION":
        raise ContractError("partial Git-blob mapping status changed")
    if upstream.get("matched_git_blobs") != 14 or upstream.get("tracked_git_blobs") != 15:
        raise ContractError("Git-blob corroboration counts changed")
    if upstream.get("missing_tracked_paths") != [".github/workflows/python_test.yml"]:
        raise ContractError("missing tracked Git path changed")
    if upstream.get("missing_tracked_blob") != "ec3048da336bfb60f708cceb5d27d8ed10c2bbb3":
        raise ContractError("missing tracked Git blob changed")
    artifact_only = upstream.get("artifact_only_entries")
    if artifact_only != list(ARTIFACT_ONLY_ENTRIES):
        raise ContractError("artifact-only ZIP inventory changed")
    if upstream.get("artifact_only_file_entries") != 17:
        raise ContractError("artifact-only file count changed")
    if upstream.get("artifact_only_directory_entries") != 6:
        raise ContractError("artifact-only directory count changed")

    raw_file = files.get("raw_data.zip")
    if not isinstance(raw_file, dict):
        raise ContractError("raw_data.zip contract is missing")
    archive_bytes = _integer(raw_file.get("bytes"), name="raw archive bytes", minimum=1)
    if archive_bytes != 4785454278:
        raise ContractError("raw archive byte count changed")
    if raw_file.get("md5_status") != "ZENODO_DECLARED_NOT_RECOMPUTED":
        raise ContractError("full-archive MD5 claim boundary changed")
    if execution.get("full_raw_archive_download_forbidden") is not True:
        raise ContractError("full raw archive download is no longer forbidden")
    maximum_request = _integer(
        execution.get("maximum_raw_archive_bytes_per_request"),
        name="maximum range request",
        minimum=1,
    )
    if maximum_request >= archive_bytes or maximum_request > 8_000_000:
        raise ContractError("range request cap is not fail-closed")

    cd_offset = _integer(zip64.get("central_directory_offset"), name="CD offset")
    cd_bytes = _integer(zip64.get("central_directory_bytes"), name="CD bytes", minimum=1)
    eocd_offset = _integer(zip64.get("zip64_eocd_offset"), name="ZIP64 EOCD offset")
    if cd_offset + cd_bytes != eocd_offset:
        raise ContractError("central directory does not end at ZIP64 EOCD")
    if eocd_offset + 98 != archive_bytes:
        raise ContractError("ZIP64 trailer length changed")
    _hash(zip64.get("tail_sha256"), SHA256_PATTERN, name="tail SHA-256")
    _hash(zip64.get("central_directory_sha256"), SHA256_PATTERN, name="CD SHA-256")

    seen_raw: set[str] = set()
    for label in ("json", "dat"):
        member = members.get(label)
        if not isinstance(member, dict):
            raise ContractError(f"raw member {label} is missing")
        path = _safe_member(member.get("path"), name=f"raw member {label}")
        if path in seen_raw:
            raise ContractError("raw member paths are duplicated")
        seen_raw.add(path)
        _integer(member.get("local_header_offset"), name=f"{label} local offset")
        _integer(member.get("compressed_bytes"), name=f"{label} compressed bytes", minimum=1)
        _integer(member.get("uncompressed_bytes"), name=f"{label} bytes", minimum=1)
        _hash(member.get("sha256"), SHA256_PATTERN, name=f"{label} SHA-256")
        crc = member.get("crc32")
        if not isinstance(crc, str) or re.fullmatch(r"[0-9a-f]{8}", crc) is None:
            raise ContractError(f"{label} CRC32 is invalid")

    required = value.get("required_code_members")
    if not isinstance(required, list) or len(required) != 14:
        raise ContractError("exactly 14 code members are required")
    seen_code: set[str] = set()
    for index, member in enumerate(required):
        if not isinstance(member, dict):
            raise ContractError(f"code member {index} is not an object")
        path = _safe_member(member.get("path"), name=f"code member {index}")
        if path in seen_code:
            raise ContractError(f"duplicate code member: {path}")
        seen_code.add(path)
        _integer(member.get("bytes"), name=f"{path} bytes")
        _integer(member.get("normalized_lf_bytes"), name=f"{path} normalized bytes")
        _hash(member.get("sha256"), SHA256_PATTERN, name=f"{path} SHA-256")
        _hash(member.get("normalized_git_blob"), SHA1_PATTERN, name=f"{path} Git blob")
    return value


def load_contract(path: Path | None = None) -> dict[str, Any]:
    """Load the contract; the canonical path additionally has a frozen byte hash."""

    selected = CONTRACT_PATH if path is None else path
    payload, value = _read(selected)
    if path is None and hashlib.sha256(payload).hexdigest() != CONTRACT_SHA256:
        raise ContractError("frozen contract byte hash changed")
    return validate_contract(value)

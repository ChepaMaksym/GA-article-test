"""Authenticate Zenodo metadata, static source archive, and experiment runner."""

from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping


class CodeIdentityError(ValueError):
    """Raised when paper-cited code/data identity differs from the freeze."""


def _reject_constant(token: str) -> None:
    raise CodeIdentityError(f"non-finite JSON value is forbidden: {token}")


def _unique_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CodeIdentityError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _digest(payload: bytes, algorithm: str) -> str:
    return hashlib.new(algorithm, payload).hexdigest()


def validate_zenodo_record(payload: bytes, contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate stable metadata and every required Zenodo file identity."""

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CodeIdentityError(f"Zenodo record is not strict JSON: {error}") from error
    if not isinstance(value, dict):
        raise CodeIdentityError("Zenodo record root must be an object")
    frozen = contract["zenodo"]
    metadata = value.get("metadata")
    files = value.get("files")
    if not isinstance(metadata, dict) or not isinstance(files, list):
        raise CodeIdentityError("Zenodo metadata/files sections are missing")
    observed_record = {
        "record_id": value.get("id"),
        "doi": value.get("doi"),
        "created": value.get("created"),
        "updated": value.get("updated"),
        "publication_date": metadata.get("publication_date"),
        "license": (metadata.get("license") or {}).get("id")
        if isinstance(metadata.get("license"), dict)
        else None,
    }
    expected_record = {key: frozen[key] for key in observed_record}
    if observed_record != expected_record:
        raise CodeIdentityError(f"Zenodo record identity differs: {observed_record!r}")
    indexed: dict[str, dict[str, Any]] = {}
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise CodeIdentityError("Zenodo file entry is malformed")
        key = item["key"]
        if key in indexed:
            raise CodeIdentityError(f"duplicate Zenodo file entry: {key}")
        indexed[key] = item
    for key, expected in contract["zenodo_files"].items():
        item = indexed.get(key)
        if item is None:
            raise CodeIdentityError(f"Zenodo record lacks {key}")
        if item.get("size") != expected["bytes"]:
            raise CodeIdentityError(f"Zenodo byte count differs for {key}")
        if item.get("checksum") != f"md5:{expected['md5']}":
            raise CodeIdentityError(f"Zenodo MD5 differs for {key}")
    return {
        **observed_record,
        "title": metadata.get("title"),
        "raw_archive_md5_status": contract["zenodo_files"]["raw_data.zip"]["md5_status"],
    }


def validate_download(name: str, payload: bytes, contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one small downloaded Zenodo file by size, MD5, and SHA-256."""

    expected = contract["zenodo_files"].get(name)
    if not isinstance(expected, dict) or "sha256" not in expected:
        raise CodeIdentityError(f"{name} is not a frozen small download")
    observed = {
        "bytes": len(payload),
        "md5": _digest(payload, "md5"),
        "sha256": _digest(payload, "sha256"),
    }
    frozen = {key: expected[key] for key in observed}
    if observed != frozen:
        raise CodeIdentityError(f"download identity differs for {name}: {observed!r}")
    return observed


def _safe_zip_path(name: str) -> None:
    if not name or "\\" in name or "\x00" in name:
        raise CodeIdentityError(f"unsafe source ZIP path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise CodeIdentityError(f"unsafe source ZIP path: {name!r}")


def _git_blob(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def validate_code_archive(payload: bytes, contract: Mapping[str, Any]) -> dict[str, Any]:
    """Inspect the static source ZIP without extracting or trusting its paths."""

    identity = validate_download("ModDE.zip", payload, contract)
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload), "r")
        bad = archive.testzip()
    except (zipfile.BadZipFile, OSError) as error:
        raise CodeIdentityError(f"static source ZIP is invalid: {error}") from error
    if bad is not None:
        raise CodeIdentityError(f"static source ZIP member CRC failed: {bad}")
    infos = archive.infolist()
    names: set[str] = set()
    total_uncompressed = 0
    for info in infos:
        _safe_zip_path(info.filename.rstrip("/") if info.is_dir() else info.filename)
        if info.filename in names:
            raise CodeIdentityError(f"duplicate source ZIP member: {info.filename}")
        names.add(info.filename)
        if info.flag_bits & 0x1:
            raise CodeIdentityError(f"encrypted source ZIP member: {info.filename}")
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise CodeIdentityError(f"unsupported source ZIP method: {info.filename}")
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise CodeIdentityError(f"source ZIP symlink is forbidden: {info.filename}")
        total_uncompressed += info.file_size
    if total_uncompressed > 2_000_000:
        raise CodeIdentityError("static source ZIP expands past the safety cap")

    upstream = contract["upstream"]
    required_paths = {member["path"] for member in contract["required_code_members"]}
    artifact_only = set(upstream["artifact_only_entries"])
    expected_names = required_paths | artifact_only
    if names != expected_names:
        missing = sorted(expected_names - names)
        unexpected = sorted(names - expected_names)
        raise CodeIdentityError(
            f"static source ZIP inventory differs: missing={missing!r}, "
            f"unexpected={unexpected!r}"
        )

    required_results: list[dict[str, Any]] = []
    for expected in contract["required_code_members"]:
        path = expected["path"]
        if path not in names:
            raise CodeIdentityError(f"static source ZIP lacks {path}")
        info = archive.getinfo(path)
        member = archive.read(info)
        normalized = member.replace(b"\r\n", b"\n")
        observed = {
            "path": path,
            "bytes": len(member),
            "sha256": _digest(member, "sha256"),
            "normalized_lf_bytes": len(normalized),
            "normalized_git_blob": _git_blob(normalized),
        }
        frozen = {key: expected[key] for key in observed}
        if observed != frozen:
            raise CodeIdentityError(f"static source member differs: {observed!r}")
        required_results.append(observed)
    license_payload = archive.read("LICENCE").replace(b"\r\n", b"\n")
    if not license_payload.startswith(b"MIT License\n"):
        raise CodeIdentityError("embedded code license is not the frozen MIT text")
    return {
        **identity,
        "zip_members": len(infos),
        "uncompressed_bytes": total_uncompressed,
        "required_members": len(required_results),
        "mapping_status": upstream["mapping_status"],
        "artifact_exact_tree_match": False,
        "matched_git_blobs": upstream["matched_git_blobs"],
        "tracked_git_blobs": upstream["tracked_git_blobs"],
        "missing_tracked_paths": upstream["missing_tracked_paths"],
        "artifact_only_entries": len(upstream["artifact_only_entries"]),
        "artifact_only_file_entries": upstream["artifact_only_file_entries"],
        "artifact_only_directory_entries": upstream["artifact_only_directory_entries"],
        "upstream_commit_reference": upstream["commit"],
        "upstream_tree_reference": upstream["tree"],
        "embedded_license": "MIT",
    }


def validate_runner(payload: bytes, contract: Mapping[str, Any]) -> dict[str, Any]:
    """Authenticate the runner and assert frozen seed/configuration markers."""

    identity = validate_download("Common_DE_runner.py", payload, contract)
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise CodeIdentityError("runner is not strict UTF-8") from error
    markers = (
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
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise CodeIdentityError(f"runner lacks frozen semantics markers: {missing!r}")
    return {**identity, "seed_schedule": "iid-major then seed 0..4", "markers": len(markers)}

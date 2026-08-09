"""End-to-end authenticated targeted-artifact verification."""

from __future__ import annotations

import hashlib
import json
import math
import zlib
from pathlib import Path
from typing import Any

from .code_archive import verify_code_archive
from .contract import exact, require
from .controls import run_controls
from .endpoint import validate_endpoint
from .errors import VerificationError
from .integrity import implementation_manifest
from .ranges import HTTPRangeSource, fetch_https_bytes
from .zipformat import ZipEntry, verify_local_header, verify_nested_zip, verify_outer_zip64


def _unique_json(data: bytes, stage: str) -> dict[str, Any]:
    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise VerificationError(stage, f"duplicate JSON key {key!r}")
            value[key] = item
        return value

    try:
        parsed = json.loads(data.decode("utf-8"), object_pairs_hook=hook)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(stage, f"invalid JSON: {exc}") from exc
    require(isinstance(parsed, dict), stage, "JSON root must be an object")
    return parsed


def verify_metadata(data: bytes, contract: dict[str, Any]) -> dict[str, Any]:
    stage = "A1_METADATA"
    record = _unique_json(data, stage)
    frozen = contract["zenodo"]
    exact(record.get("id"), frozen["record_id"], stage, "record id")
    exact(record.get("doi"), frozen["doi"], stage, "record DOI")
    exact(record.get("created"), frozen["created"], stage, "created timestamp")
    exact(record.get("updated"), frozen["updated"], stage, "updated timestamp")
    metadata = record.get("metadata")
    require(isinstance(metadata, dict), stage, "metadata missing")
    exact(metadata.get("publication_date"), frozen["publication_date"], stage, "publication date")
    exact(metadata.get("license", {}).get("id"), frozen["license"], stage, "license")
    exact(metadata.get("title"), "Repelling restart potential -- reproducibility and additional figures", stage, "title")

    files = record.get("files")
    require(isinstance(files, list), stage, "files must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for item in files:
        require(isinstance(item, dict), stage, "file record must be an object")
        key = item.get("key")
        require(isinstance(key, str) and key not in indexed, stage, f"duplicate or invalid file key {key!r}")
        indexed[key] = item
    exact(set(indexed), set(contract["zenodo_files"]), stage, "Zenodo file set")
    file_report: dict[str, Any] = {}
    for key, expected in contract["zenodo_files"].items():
        item = indexed[key]
        exact(item.get("size"), expected["bytes"], stage, f"{key} size")
        exact(item.get("checksum"), f"md5:{expected['md5']}", stage, f"{key} declared MD5")
        exact(item.get("links", {}).get("self"), expected["url"], stage, f"{key} content URL")
        file_report[key] = {
            "bytes": item["size"],
            "declared_md5": expected["md5"],
            "md5_status": expected.get("md5_status", "RECOMPUTED_LATER"),
        }
    return {
        "status": "PASS_ZENODO_METADATA",
        "record_id": record["id"],
        "doi": record["doi"],
        "license": metadata["license"]["id"],
        "files": file_report,
    }


def _verify_entry(entry: ZipEntry, expected: dict[str, Any], stage: str, *, relative: bool = False) -> None:
    exact(entry.name, expected["path"], stage, "member path")
    offset_field = "local_header_offset_relative" if relative else "local_header_offset"
    exact(entry.local_header_offset, expected[offset_field], stage, "local-header offset")
    exact(entry.flags, expected["flags"], stage, "flags")
    exact(entry.method, expected["compression_method"], stage, "compression method")
    exact(entry.compressed_bytes, expected["compressed_bytes"], stage, "compressed bytes")
    exact(entry.uncompressed_bytes, expected["uncompressed_bytes"], stage, "uncompressed bytes")
    exact(f"{entry.crc32:08x}", expected["crc32"], stage, "CRC32")


def _inflate_target(payload: bytes, expected_bytes: int, stage: str) -> bytes:
    decompressor = zlib.decompressobj(wbits=-15)
    try:
        raw = decompressor.decompress(payload, expected_bytes + 1)
        require(len(raw) <= expected_bytes, stage, "deflate output exceeds frozen size")
        raw += decompressor.flush()
    except zlib.error as exc:
        raise VerificationError(stage, f"raw-deflate failure: {exc}") from exc
    exact(len(raw), expected_bytes, stage, "inflated bytes")
    require(decompressor.eof, stage, "deflate stream did not reach EOF")
    require(not decompressor.unused_data, stage, "trailing bytes after deflate stream")
    require(not decompressor.unconsumed_tail, stage, "unconsumed deflate input")
    return raw


def _load_attestation(path: Path | str, stage: str) -> dict[str, Any]:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise VerificationError(stage, f"cannot read attestation: {exc}") from exc
    return _unique_json(data, stage)


def validate_python_attestation(path: Path | str, contract: dict[str, Any]) -> dict[str, Any]:
    stage = "A9_FAIL_CLOSED"
    report = _load_attestation(path, stage)
    exact(report.get("candidate_id"), contract["candidate_id"], stage, "candidate id")
    exact(report.get("status"), "PASS_FAIL_CLOSED_MUTATION_SUITE", stage, "attestation status")
    exact(report.get("failures"), 0, stage, "test failures")
    exact(report.get("errors"), 0, stage, "test errors")
    require(type(report.get("tests_run")) is int and report["tests_run"] >= 30, stage, "fewer than 30 mutation/unit tests")
    require(type(report.get("mutation_tests")) is int and report["mutation_tests"] >= 20, stage, "fewer than 20 negative mutation tests")
    manifest = implementation_manifest()
    exact(report.get("implementation_files"), manifest["files"], stage, "implementation file count")
    exact(
        report.get("implementation_manifest_sha256"),
        manifest["sha256"],
        stage,
        "implementation manifest SHA-256",
    )
    return report


def _close(actual: Any, expected: float, stage: str, field: str) -> None:
    require(type(actual) in (int, float) and not isinstance(actual, bool), stage, f"{field} is not numeric")
    require(math.isfinite(float(actual)), stage, f"{field} is non-finite")
    require(math.isclose(float(actual), expected, rel_tol=2e-14, abs_tol=2e-14), stage, f"{field} mismatch")


def validate_octave_attestation(path: Path | str, contract: dict[str, Any]) -> dict[str, Any]:
    stage = "A8_CROSS_LANGUAGE"
    report = _load_attestation(path, stage)
    exact(report.get("candidate_id"), contract["candidate_id"], stage, "candidate id")
    exact(report.get("status"), "PASS_CROSS_LANGUAGE_CONTROLS", stage, "Octave status")
    exact(report.get("paper_mapping"), contract["paper_mapping"], stage, "paper mapping")
    exact(report.get("source_native_status"), contract["source_native_status"], stage, "source-native status")
    candidate_root = Path(__file__).resolve().parents[3]
    frozen_files = {
        "contract_sha256": candidate_root / "config" / "verification_contract.json",
        "fixture_sha256": candidate_root / "fixtures" / "frozen_endpoint.json",
        "octave_script_sha256": candidate_root / "tests" / "octave" / "run_octave_tests.m",
    }
    for field, frozen_path in frozen_files.items():
        exact(report.get(field), hashlib.sha256(frozen_path.read_bytes()).hexdigest(), stage, field)
    checks = report.get("checks")
    require(isinstance(checks, dict) and len(checks) >= 8, stage, "Octave checks missing")
    require(all(value is True for value in checks.values()), stage, "an Octave check did not pass")
    values = report.get("values")
    require(isinstance(values, dict), stage, "Octave values missing")
    fixtures = contract["control_fixtures"]
    exact(values.get("seed_rows"), fixtures["seed_schedule"]["expected_rows"], stage, "seed rows")
    exact(values.get("seed_last"), fixtures["seed_schedule"]["expected_last"], stage, "last seed row")
    exact(values.get("first_lambda"), fixtures["bipop"]["first_restart"]["expected_lambda"], stage, "first lambda")
    exact(values.get("second_lambda"), fixtures["bipop"]["second_restart"]["expected_lambda"], stage, "second lambda")
    _close(values.get("second_sigma"), fixtures["bipop"]["second_restart"]["expected_sigma"], stage, "second sigma")
    _close(values.get("repelling_radius"), fixtures["repelling_radius"]["expected_radius"], stage, "repelling radius")
    _close(values.get("csa_sigma"), fixtures["csa"]["expected_sigma"], stage, "CSA sigma")
    return report


def verify_artifact(
    contract: dict[str, Any],
    *,
    metadata_bytes: bytes | None = None,
    code_archive_bytes: bytes | None = None,
    range_source: Any | None = None,
    python_attestation: Path | str,
    octave_attestation: Path | str,
) -> dict[str, Any]:
    """Run A1--A10 while preserving the mandatory A11 source-native block."""

    if metadata_bytes is None:
        metadata_bytes = fetch_https_bytes(contract["zenodo"]["record_url"], maximum_bytes=1_000_000)
    metadata = verify_metadata(metadata_bytes, contract)

    code_cfg = contract["zenodo_files"]["repelling_code.zip"]
    if code_archive_bytes is None:
        code_archive_bytes = fetch_https_bytes(
            code_cfg["url"], maximum_bytes=code_cfg["bytes"], expected_bytes=code_cfg["bytes"]
        )
    code = verify_code_archive(code_archive_bytes, contract)

    raw_cfg = contract["zenodo_files"]["repelling.zip"]
    if range_source is None:
        range_source = HTTPRangeSource(
            raw_cfg["url"],
            raw_cfg["bytes"],
            contract["verification_execution"]["maximum_range_bytes_per_request"],
        )
    exact(range_source.total_bytes, raw_cfg["bytes"], "A3_OUTER_ZIP64", "source total bytes")
    outer = verify_outer_zip64(range_source, contract["outer_zip64"])
    outer_entry = outer.unique(contract["outer_member"]["path"], "A4_NESTED_ZIP")
    _verify_entry(outer_entry, contract["outer_member"], "A4_NESTED_ZIP")
    outer_cfg = contract["outer_member"]
    nested_cfg = contract["nested_zip"]
    exact(outer_entry.compressed_bytes, nested_cfg["bytes"], "A4_NESTED_ZIP", "stored nested size")
    data_offset = verify_local_header(
        range_source,
        absolute_offset=outer_cfg["local_header_offset"],
        expected_bytes=outer_cfg["local_header_bytes"],
        expected_sha256=outer_cfg["local_header_sha256"],
        central=outer_entry,
        stage="A4_NESTED_ZIP",
    )
    exact(data_offset, outer_cfg["data_offset"], "A4_NESTED_ZIP", "outer payload offset")
    require(data_offset + outer_entry.compressed_bytes <= contract["outer_zip64"]["central_directory_offset"], "A4_NESTED_ZIP", "stored nested member overlaps outer directory")

    nested = verify_nested_zip(range_source, data_offset, nested_cfg)
    target_cfg = contract["target_member"]
    target_entry = nested.unique(target_cfg["path"], "A5_TARGET_MEMBER")
    _verify_entry(target_entry, target_cfg, "A5_TARGET_MEMBER", relative=True)
    absolute_local = data_offset + target_entry.local_header_offset
    exact(absolute_local, target_cfg["local_header_offset_absolute"], "A5_TARGET_MEMBER", "absolute local offset")
    target_data_offset = verify_local_header(
        range_source,
        absolute_offset=absolute_local,
        expected_bytes=target_cfg["local_header_bytes"],
        expected_sha256=target_cfg["local_header_sha256"],
        central=target_entry,
        stage="A5_TARGET_MEMBER",
    )
    exact(target_data_offset, target_cfg["data_offset_absolute"], "A5_TARGET_MEMBER", "target data offset")
    exact(target_data_offset + target_entry.compressed_bytes - 1, target_cfg["data_end_inclusive_absolute"], "A5_TARGET_MEMBER", "target data end")
    compressed = range_source.read(target_data_offset, target_entry.compressed_bytes)
    exact(hashlib.sha256(compressed).hexdigest(), target_cfg["compressed_sha256"], "A5_TARGET_MEMBER", "compressed SHA-256")
    raw = _inflate_target(compressed, target_entry.uncompressed_bytes, "A5_TARGET_MEMBER")
    exact(hashlib.sha256(raw).hexdigest(), target_cfg["raw_sha256"], "A5_TARGET_MEMBER", "raw SHA-256")
    exact(f"{zlib.crc32(raw) & 0xFFFFFFFF:08x}", target_cfg["crc32"], "A5_TARGET_MEMBER", "raw CRC32")
    endpoint = validate_endpoint(raw, contract)
    controls = run_controls(contract)
    octave = validate_octave_attestation(octave_attestation, contract)
    python_tests = validate_python_attestation(python_attestation, contract)

    events = [
        {"start": event.start, "end": event.end, "bytes": event.bytes, "sha256": event.sha256}
        for event in range_source.events
    ]
    exact(len(events), 7, "A10_BOUNDARY", "range request count")
    require(all(event["bytes"] <= contract["verification_execution"]["maximum_range_bytes_per_request"] for event in events), "A10_BOUNDARY", "range cap exceeded")
    total_ranged = sum(event["bytes"] for event in events)
    require(total_ranged < 1_000_000, "A10_BOUNDARY", "range verifier fetched one megabyte or more")

    gates = {
        "A1_metadata": "PASS_ZENODO_METADATA",
        "A2_code": "PASS_CODE_ARCHIVE_IDENTITY",
        "A3_outer_zip64": "PASS_OUTER_ZIP64_IDENTITY",
        "A4_nested_zip": "PASS_NESTED_ZIP_IDENTITY",
        "A5_target_member": "PASS_RANGE_AUTHENTICATED_MEMBER",
        "A6_endpoint": "PASS_ARTIFACT_ENDPOINT",
        "A7_controls": "PASS_INDEPENDENT_CONTROLS",
        "A8_cross_language": "PASS_CROSS_LANGUAGE_CONTROLS",
        "A9_fail_closed": "PASS_FAIL_CLOSED_MUTATION_SUITE",
        "A10_boundary": "PASS_TARGETED_ONLY_BOUNDARY",
        "A11_source_native": contract["source_native_status"],
    }
    return {
        "schema_version": "1.0.0",
        "candidate_id": contract["candidate_id"],
        "overall_status": "TARGETED_ARTIFACT_REPLAY_VERIFIED_WITH_SOURCE_NATIVE_BLOCKED",
        "candidate_status": contract["status"],
        "paper_mapping": contract["paper_mapping"],
        "source_native_status": contract["source_native_status"],
        "pass_full": False,
        "source_native_executed": False,
        "full_outer_archive_downloaded": False,
        "full_nested_archive_downloaded": False,
        "large_archive_md5_status": raw_cfg["md5_status"],
        "public_git_revision": None,
        "gates": gates,
        "metadata": metadata,
        "code_archive": code,
        "archive": {
            "outer_entries": len(outer.entries),
            "outer_tail_sha256": outer.tail_sha256,
            "outer_directory_sha256": outer.directory_sha256,
            "outer_member_crc_status": outer_cfg["crc_status"],
            "nested_entries": len(nested.entries),
            "nested_tail_sha256": nested.tail_sha256,
            "nested_directory_sha256": nested.directory_sha256,
            "target_compressed_sha256": hashlib.sha256(compressed).hexdigest(),
            "target_raw_sha256": hashlib.sha256(raw).hexdigest(),
            "target_crc32": f"{zlib.crc32(raw) & 0xFFFFFFFF:08x}",
            "range_requests": events,
            "total_range_bytes": total_ranged,
        },
        "endpoint": endpoint,
        "python_controls": controls,
        "octave_controls": octave,
        "python_test_attestation": python_tests,
        "forbidden_claims_retained": contract["forbidden_claims"],
    }

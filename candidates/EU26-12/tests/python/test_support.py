"""Deterministic synthetic artifacts for EU26-12 unit tests."""

from __future__ import annotations

import hashlib
import io
import json
import struct
import zlib
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


def candidate_root() -> Path:
    return Path(__file__).resolve().parents[2]


def synthetic_ioh_json(contract: Mapping[str, Any]) -> bytes:
    endpoint = contract["endpoint"]
    runs = []
    for index in range(50):
        evaluations = 50002
        if index == 29:
            evaluations = 46461
        elif index == 45:
            evaluations = 46271
        runs.append(
            {
                "instance": index // 5,
                "evals": evaluations,
                "best": {
                    "evals": 45886 if index == 0 else min(45000, evaluations),
                    "y": 1.698652750709869e-14 if index == 0 else 2e-14,
                    "x": [0.0] * 20,
                },
            }
        )
    value = {
        "version": "0.3.5",
        "suite": "unknown_suite",
        "function_id": 1,
        "function_name": "Sphere",
        "maximization": False,
        "algorithm": {"name": "L-SHADE", "info": "algorithm_info"},
        "attributes": ["evaluations", "raw_y"],
        "scenarios": [
            {
                "dimension": endpoint["dimension"],
                "path": "data_f1_Sphere/IOHprofiler_f1_DIM20.dat",
                "runs": runs,
            }
        ],
    }
    return json.dumps(value, indent=2, separators=(",", ": ")).encode("utf-8")


def synthetic_dat(run_evaluations: tuple[int, ...]) -> bytes:
    lines: list[str] = []
    for evaluations in run_evaluations:
        lines.extend(
            [
                "evaluations raw_y",
                "1 1.0000000000",
                f"{evaluations} 0.0000000000",
            ]
        )
    return ("\n".join(lines) + "\n").encode("ascii")


def _deflate(payload: bytes) -> bytes:
    compressor = zlib.compressobj(level=6, wbits=-15)
    return compressor.compress(payload) + compressor.flush()


def make_zip64(files: Mapping[str, bytes]) -> tuple[bytes, dict[str, Any]]:
    """Build a small, valid ZIP64 archive with offset sentinels in the CD."""

    local_parts: list[bytes] = []
    central_parts: list[bytes] = []
    entries: dict[str, dict[str, Any]] = {}
    offset = 0
    for path, payload in files.items():
        name = path.encode("utf-8")
        compressed = _deflate(payload)
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        local = struct.pack(
            "<4s5H3I2H",
            b"PK\x03\x04",
            45,
            0x800,
            8,
            0,
            0,
            crc,
            len(compressed),
            len(payload),
            len(name),
            0,
        ) + name + compressed
        local_parts.append(local)
        zip64_extra = struct.pack("<HHQ", 0x0001, 8, offset)
        central = struct.pack(
            "<4s6H3I5H2I",
            b"PK\x01\x02",
            45,
            45,
            0x800,
            8,
            0,
            0,
            crc,
            len(compressed),
            len(payload),
            len(name),
            len(zip64_extra),
            0,
            0,
            0,
            0,
            0xFFFFFFFF,
        ) + name + zip64_extra
        central_parts.append(central)
        entries[path] = {
            "path": path,
            "local_header_offset": offset,
            "flags": 0x800,
            "compression_method": 8,
            "compressed_bytes": len(compressed),
            "uncompressed_bytes": len(payload),
            "crc32": f"{crc:08x}",
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        offset += len(local)
    local_blob = b"".join(local_parts)
    central_blob = b"".join(central_parts)
    cd_offset = len(local_blob)
    zip64_eocd_offset = cd_offset + len(central_blob)
    count = len(files)
    zip64_eocd = struct.pack(
        "<4sQ2H2I4Q",
        b"PK\x06\x06",
        44,
        45,
        45,
        0,
        0,
        count,
        count,
        len(central_blob),
        cd_offset,
    )
    locator_offset = zip64_eocd_offset + len(zip64_eocd)
    locator = struct.pack("<4sIQI", b"PK\x06\x07", 0, zip64_eocd_offset, 1)
    classic_offset = locator_offset + len(locator)
    classic = struct.pack(
        "<4s4H2IH",
        b"PK\x05\x06",
        0,
        0,
        count,
        count,
        len(central_blob),
        0xFFFFFFFF,
        0,
    )
    archive = local_blob + central_blob + zip64_eocd + locator + classic
    tail_bytes = len(archive)
    contract = {
        "zenodo_files": {"raw_data.zip": {"bytes": len(archive)}},
        "zip64": {
            "tail_bytes": tail_bytes,
            "tail_sha256": hashlib.sha256(archive).hexdigest(),
            "zip64_eocd_offset": zip64_eocd_offset,
            "zip64_locator_offset": locator_offset,
            "classic_eocd_offset": classic_offset,
            "entry_count": count,
            "central_directory_offset": cd_offset,
            "central_directory_bytes": len(central_blob),
            "central_directory_sha256": hashlib.sha256(central_blob).hexdigest(),
        },
        "raw_members": entries,
    }
    return archive, contract


def synthetic_record(contract: Mapping[str, Any]) -> bytes:
    files = []
    for key, item in contract["zenodo_files"].items():
        files.append({"key": key, "size": item["bytes"], "checksum": f"md5:{item['md5']}"})
    value = {
        "id": contract["zenodo"]["record_id"],
        "doi": contract["zenodo"]["doi"],
        "created": contract["zenodo"]["created"],
        "updated": contract["zenodo"]["updated"],
        "metadata": {
            "title": "Modular Differential Evolution: Supplementary Material",
            "publication_date": contract["zenodo"]["publication_date"],
            "license": {"id": contract["zenodo"]["license"]},
        },
        "files": files,
    }
    return json.dumps(value).encode("utf-8")


def tiny_code_contract(payloads: Mapping[str, bytes]) -> tuple[bytes, dict[str, Any]]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, payload in payloads.items():
            archive.writestr(path, payload)
    archive_payload = buffer.getvalue()
    required = []
    for path, payload in payloads.items():
        normalized = payload.replace(b"\r\n", b"\n")
        blob = hashlib.sha1(f"blob {len(normalized)}\0".encode() + normalized).hexdigest()
        required.append(
            {
                "path": path,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "normalized_lf_bytes": len(normalized),
                "normalized_git_blob": blob,
            }
        )
    contract = {
        "zenodo_files": {
            "ModDE.zip": {
                "bytes": len(archive_payload),
                "md5": hashlib.md5(archive_payload).hexdigest(),
                "sha256": hashlib.sha256(archive_payload).hexdigest(),
            }
        },
        "required_code_members": required,
        "upstream": {
            "commit": "a" * 40,
            "tree": "b" * 40,
            "artifact_exact_tree_match": False,
            "matched_git_blobs": len(required),
            "tracked_git_blobs": len(required) + 1,
            "missing_tracked_paths": ["ci.yml"],
            "artifact_only_entries": [],
            "artifact_only_file_entries": 0,
            "artifact_only_directory_entries": 0,
            "mapping_status": f"PARTIAL_{len(required)}_OF_{len(required) + 1}_TEST_FIXTURE",
        },
    }
    return archive_payload, contract


def mutated(value: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy(value)

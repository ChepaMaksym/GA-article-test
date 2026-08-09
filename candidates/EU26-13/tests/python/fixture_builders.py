"""Deterministic offline fixtures for bounded ZIP and endpoint tests."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import struct
import zipfile
import zlib
from dataclasses import dataclass
from typing import Any


CENTRAL = struct.Struct("<4s6H3I5H2I")
LOCAL = struct.Struct("<4s5H3I2H")
EOCD = struct.Struct("<4s4H2IH")
ZIP64_EOCD = struct.Struct("<4sQ2H2I4Q")
ZIP64_LOCATOR = struct.Struct("<4sIQI")


@dataclass(frozen=True)
class ArchiveFixture:
    outer: bytes
    contract: dict[str, Any]
    raw: bytes


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _standard_directory(archive: bytes) -> tuple[int, int, int, int]:
    at = archive.rfind(b"PK\x05\x06")
    record = EOCD.unpack_from(archive, at)
    return at, record[4], record[5], record[6]


def build_archive_fixture(
    *,
    outer_name: str = "nested.zip",
    target_name: str = "fixture/endpoint.json",
) -> ArchiveFixture:
    raw = b'{"fixture":"EU26-13","value":2173}\n'
    nested_io = io.BytesIO()
    with zipfile.ZipFile(nested_io, "w") as archive:
        info = zipfile.ZipInfo(target_name, date_time=(2024, 5, 2, 12, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 0
        archive.writestr(info, raw)
    nested = nested_io.getvalue()
    inner_eocd, inner_count, inner_cd_size, inner_cd_offset = _standard_directory(nested)
    inner_tail_start = max(0, len(nested) - 65_536)
    inner_tail = nested[inner_tail_start:]
    inner_cd = nested[inner_cd_offset : inner_cd_offset + inner_cd_size]

    target_header_offset = 0
    local = LOCAL.unpack_from(nested, target_header_offset)
    target_header_bytes = LOCAL.size + local[9] + local[10]
    target_data_offset = target_header_offset + target_header_bytes
    compressed_bytes = local[7]
    target_compressed = nested[target_data_offset : target_data_offset + compressed_bytes]

    outer_name_bytes = outer_name.encode("ascii")
    crc = zlib.crc32(nested) & 0xFFFFFFFF
    outer_local = LOCAL.pack(
        b"PK\x03\x04", 45, 0, 0, 0, 0, crc, len(nested), len(nested), len(outer_name_bytes), 0
    ) + outer_name_bytes
    outer_data_offset = len(outer_local)
    central_offset = outer_data_offset + len(nested)
    central = CENTRAL.pack(
        b"PK\x01\x02",
        45,
        45,
        0,
        0,
        0,
        0,
        crc,
        len(nested),
        len(nested),
        len(outer_name_bytes),
        0,
        0,
        0,
        0,
        0,
        0,
    ) + outer_name_bytes
    zip64_offset = central_offset + len(central)
    zip64 = ZIP64_EOCD.pack(
        b"PK\x06\x06", 44, 45, 45, 0, 0, 1, 1, len(central), central_offset
    )
    locator_offset = zip64_offset + len(zip64)
    locator = ZIP64_LOCATOR.pack(b"PK\x06\x07", 0, zip64_offset, 1)
    eocd_offset = locator_offset + len(locator)
    eocd = EOCD.pack(b"PK\x05\x06", 0, 0, 1, 1, len(central), 0xFFFFFFFF, 0)
    outer = outer_local + nested + central + zip64 + locator + eocd
    outer_tail_start = max(0, len(outer) - 65_536)
    outer_tail = outer[outer_tail_start:]

    target_local_absolute = outer_data_offset + target_header_offset
    target_data_absolute = outer_data_offset + target_data_offset
    contract = {
        "outer_zip64": {
            "tail_start": outer_tail_start,
            "tail_bytes": len(outer_tail),
            "tail_sha256": _sha(outer_tail),
            "zip64_eocd_offset": zip64_offset,
            "zip64_locator_offset": locator_offset,
            "classic_eocd_offset": eocd_offset,
            "entry_count": 1,
            "central_directory_offset": central_offset,
            "central_directory_bytes": len(central),
            "central_directory_sha256": _sha(central),
        },
        "outer_member": {
            "path": outer_name,
            "local_header_offset": 0,
            "local_header_bytes": len(outer_local),
            "local_header_sha256": _sha(outer_local),
            "data_offset": outer_data_offset,
            "flags": 0,
            "compression_method": 0,
            "compressed_bytes": len(nested),
            "uncompressed_bytes": len(nested),
            "crc32": f"{crc:08x}",
        },
        "nested_zip": {
            "bytes": len(nested),
            "tail_start_relative": inner_tail_start,
            "tail_bytes": len(inner_tail),
            "tail_sha256": _sha(inner_tail),
            "classic_eocd_offset_relative": inner_eocd,
            "entry_count": inner_count,
            "central_directory_offset_relative": inner_cd_offset,
            "central_directory_bytes": inner_cd_size,
            "central_directory_sha256": _sha(inner_cd),
        },
        "target_member": {
            "path": target_name,
            "local_header_offset_relative": target_header_offset,
            "local_header_offset_absolute": target_local_absolute,
            "local_header_bytes": target_header_bytes,
            "local_header_sha256": _sha(nested[:target_header_bytes]),
            "data_offset_absolute": target_data_absolute,
            "data_end_inclusive_absolute": target_data_absolute + compressed_bytes - 1,
            "flags": 0,
            "compression_method": 8,
            "compressed_bytes": compressed_bytes,
            "uncompressed_bytes": len(raw),
            "crc32": f"{zlib.crc32(raw) & 0xFFFFFFFF:08x}",
            "compressed_sha256": _sha(target_compressed),
            "raw_sha256": _sha(raw),
        },
    }
    return ArchiveFixture(outer=outer, contract=contract, raw=raw)


def make_endpoint_document(contract: dict[str, Any]) -> dict[str, Any]:
    endpoint = contract["endpoint"]
    scenarios: list[dict[str, Any]] = []
    for dimension in endpoint["scenario_dimensions"]:
        runs = []
        for index in range(endpoint["runs"]):
            instance = index // endpoint["runs_per_instance"] + 1
            runs.append(
                {
                    "instance": instance,
                    "evals": 100,
                    "best": {"evals": 100, "y": 1.0, "x": [0.0] * dimension},
                }
            )
        scenarios.append(
            {
                "dimension": dimension,
                "path": f"data_f1_Sphere/IOHprofiler_f1_DIM{dimension}.dat",
                "runs": runs,
            }
        )
    target = scenarios[endpoint["scenario_index"]]["runs"][endpoint["run_index"]]
    target["evals"] = endpoint["evals"]
    target["best"]["evals"] = endpoint["best_evals"]
    target["best"]["y"] = float(endpoint["best_y_decimal"])
    return {
        "version": endpoint["json_version"],
        "suite": endpoint["suite"],
        "function_id": endpoint["function_id"],
        "function_name": endpoint["function_name"],
        "maximization": endpoint["maximization"],
        "algorithm": {"name": endpoint["algorithm_name"], "info": "algorithm_info"},
        "attributes": ["evaluations", "raw_y"],
        "scenarios": scenarios,
    }


def endpoint_bytes(document: dict[str, Any]) -> bytes:
    return json.dumps(document, separators=(",", ":"), allow_nan=False).encode("utf-8")


def mutate(document: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(document)

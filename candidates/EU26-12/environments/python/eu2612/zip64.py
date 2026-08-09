"""Minimal fail-closed ZIP64 directory parser and bounded member extractor."""

from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping, Protocol


EOCD_SIGNATURE = b"PK\x05\x06"
ZIP64_LOCATOR_SIGNATURE = b"PK\x06\x07"
ZIP64_EOCD_SIGNATURE = b"PK\x06\x06"
CENTRAL_SIGNATURE = b"PK\x01\x02"
LOCAL_SIGNATURE = b"PK\x03\x04"
ZIP64_EXTRA_ID = 0x0001


class Zip64Error(ValueError):
    """Raised when archive structure or member authentication fails."""


class RangeReader(Protocol):
    size: int

    def read(self, start: int, length: int) -> bytes: ...


@dataclass(frozen=True)
class Zip64Layout:
    archive_size: int
    entry_count: int
    central_directory_offset: int
    central_directory_bytes: int
    tail_sha256: str
    central_directory_sha256: str
    zip64_eocd_offset: int
    zip64_locator_offset: int
    classic_eocd_offset: int


@dataclass(frozen=True)
class CentralEntry:
    path: str
    flags: int
    compression_method: int
    crc32: int
    compressed_bytes: int
    uncompressed_bytes: int
    local_header_offset: int


@dataclass(frozen=True)
class ExtractedMember:
    entry: CentralEntry
    payload: bytes
    sha256: str


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_path(raw: bytes, *, utf8: bool) -> str:
    try:
        path = raw.decode("utf-8" if utf8 else "cp437", errors="strict")
    except UnicodeDecodeError as error:
        raise Zip64Error("central member path has invalid encoding") from error
    if not path or "\x00" in path or "\\" in path:
        raise Zip64Error("central member path is empty or unsafe")
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise Zip64Error(f"unsafe central member path: {path!r}")
    return path


def _extra_fields(payload: bytes) -> dict[int, bytes]:
    fields: dict[int, bytes] = {}
    position = 0
    while position < len(payload):
        if position + 4 > len(payload):
            raise Zip64Error("truncated ZIP extra-field header")
        field_id, size = struct.unpack_from("<HH", payload, position)
        position += 4
        end = position + size
        if end > len(payload):
            raise Zip64Error("truncated ZIP extra-field payload")
        if field_id in fields:
            raise Zip64Error(f"duplicate ZIP extra field: {field_id:#x}")
        fields[field_id] = payload[position:end]
        position = end
    return fields


def _zip64_values(
    extra: bytes,
    *,
    uncompressed: int,
    compressed: int,
    offset: int,
    disk: int,
) -> tuple[int, int, int, int]:
    needs = (
        uncompressed == 0xFFFFFFFF,
        compressed == 0xFFFFFFFF,
        offset == 0xFFFFFFFF,
        disk == 0xFFFF,
    )
    if not any(needs):
        return uncompressed, compressed, offset, disk
    field = _extra_fields(extra).get(ZIP64_EXTRA_ID)
    if field is None:
        raise Zip64Error("ZIP64 sentinel has no ZIP64 extra field")
    position = 0
    values = [uncompressed, compressed, offset, disk]
    widths = (8, 8, 8, 4)
    for index, (needed, width) in enumerate(zip(needs, widths)):
        if not needed:
            continue
        if position + width > len(field):
            raise Zip64Error("ZIP64 extra field is truncated")
        values[index] = int.from_bytes(field[position : position + width], "little")
        position += width
    if position != len(field):
        raise Zip64Error("ZIP64 extra field contains unexpected trailing bytes")
    return tuple(values)  # type: ignore[return-value]


def parse_central_directory(payload: bytes, *, expected_entries: int) -> dict[str, CentralEntry]:
    """Parse an exact central directory and reject duplicates or unsafe entries."""

    if not isinstance(payload, bytes):
        raise Zip64Error("central directory must be bytes")
    entries: dict[str, CentralEntry] = {}
    position = 0
    for index in range(expected_entries):
        if position + 46 > len(payload):
            raise Zip64Error(f"central directory truncated before entry {index}")
        values = struct.unpack_from("<4s6H3I5H2I", payload, position)
        (
            signature,
            _version_made,
            _version_needed,
            flags,
            method,
            _mtime,
            _mdate,
            crc32,
            compressed,
            uncompressed,
            name_bytes,
            extra_bytes,
            comment_bytes,
            disk,
            _internal,
            _external,
            offset,
        ) = values
        if signature != CENTRAL_SIGNATURE:
            raise Zip64Error(f"central entry {index} has the wrong signature")
        end = position + 46 + name_bytes + extra_bytes + comment_bytes
        if end > len(payload):
            raise Zip64Error(f"central entry {index} extends past the directory")
        name_raw = payload[position + 46 : position + 46 + name_bytes]
        extra_start = position + 46 + name_bytes
        extra = payload[extra_start : extra_start + extra_bytes]
        path = _safe_path(name_raw, utf8=bool(flags & 0x800))
        if path in entries:
            raise Zip64Error(f"duplicate central member path: {path}")
        if flags & 0x1:
            raise Zip64Error(f"encrypted member is forbidden: {path}")
        if method not in (0, 8):
            raise Zip64Error(f"unsupported compression method {method} for {path}")
        uncompressed, compressed, offset, disk = _zip64_values(
            extra,
            uncompressed=uncompressed,
            compressed=compressed,
            offset=offset,
            disk=disk,
        )
        if disk != 0:
            raise Zip64Error("multi-disk ZIP members are forbidden")
        entries[path] = CentralEntry(
            path=path,
            flags=flags,
            compression_method=method,
            crc32=crc32,
            compressed_bytes=compressed,
            uncompressed_bytes=uncompressed,
            local_header_offset=offset,
        )
        position = end
    if position != len(payload):
        raise Zip64Error("central directory has trailing or unparsed bytes")
    return entries


def inspect_archive(
    reader: RangeReader,
    contract: Mapping[str, Any],
) -> tuple[Zip64Layout, dict[str, CentralEntry]]:
    """Authenticate ZIP64 trailer and the complete central directory."""

    archive = contract["zenodo_files"]["raw_data.zip"]
    frozen = contract["zip64"]
    archive_size = archive["bytes"]
    if reader.size != archive_size:
        raise Zip64Error(f"archive size differs: {reader.size} != {archive_size}")
    tail_bytes = frozen["tail_bytes"]
    tail_start = archive_size - tail_bytes
    tail = reader.read(tail_start, tail_bytes)
    tail_hash = _sha256(tail)
    if tail_hash != frozen["tail_sha256"]:
        raise Zip64Error("archive tail SHA-256 differs")

    eocd_relative = tail.rfind(EOCD_SIGNATURE)
    if eocd_relative < 0:
        raise Zip64Error("classic EOCD not found in frozen tail")
    eocd_offset = tail_start + eocd_relative
    if eocd_offset != frozen["classic_eocd_offset"]:
        raise Zip64Error("classic EOCD offset differs")
    if eocd_relative + 22 > len(tail):
        raise Zip64Error("classic EOCD is truncated")
    (
        signature,
        disk,
        cd_disk,
        entries_disk,
        entries_total,
        cd_bytes32,
        cd_offset32,
        comment_bytes,
    ) = struct.unpack_from("<4s4H2IH", tail, eocd_relative)
    if signature != EOCD_SIGNATURE or disk != 0 or cd_disk != 0:
        raise Zip64Error("classic EOCD disk fields are invalid")
    if entries_disk != frozen["entry_count"] or entries_total != frozen["entry_count"]:
        raise Zip64Error("classic EOCD entry count differs")
    if cd_bytes32 != frozen["central_directory_bytes"] or cd_offset32 != 0xFFFFFFFF:
        raise Zip64Error("classic EOCD central-directory fields differ")
    if comment_bytes != 0 or eocd_relative + 22 != len(tail):
        raise Zip64Error("classic EOCD comment/trailer policy differs")

    locator_relative = eocd_relative - 20
    locator_offset = tail_start + locator_relative
    if locator_relative < 0 or locator_offset != frozen["zip64_locator_offset"]:
        raise Zip64Error("ZIP64 locator offset differs")
    locator = struct.unpack_from("<4sIQI", tail, locator_relative)
    if locator != (ZIP64_LOCATOR_SIGNATURE, 0, frozen["zip64_eocd_offset"], 1):
        raise Zip64Error("ZIP64 locator fields differ")

    zip64_relative = frozen["zip64_eocd_offset"] - tail_start
    if zip64_relative < 0 or zip64_relative + 56 > len(tail):
        raise Zip64Error("ZIP64 EOCD is outside the authenticated tail")
    values = struct.unpack_from("<4sQ2H2I4Q", tail, zip64_relative)
    (
        zip_signature,
        record_size,
        _version_made,
        _version_needed,
        zip_disk,
        zip_cd_disk,
        zip_entries_disk,
        zip_entries_total,
        cd_bytes,
        cd_offset,
    ) = values
    expected_zip = (
        ZIP64_EOCD_SIGNATURE,
        44,
        0,
        0,
        frozen["entry_count"],
        frozen["entry_count"],
        frozen["central_directory_bytes"],
        frozen["central_directory_offset"],
    )
    observed_zip = (
        zip_signature,
        record_size,
        zip_disk,
        zip_cd_disk,
        zip_entries_disk,
        zip_entries_total,
        cd_bytes,
        cd_offset,
    )
    if observed_zip != expected_zip:
        raise Zip64Error(f"ZIP64 EOCD fields differ: {observed_zip!r}")
    if frozen["zip64_eocd_offset"] + 56 != frozen["zip64_locator_offset"]:
        raise Zip64Error("ZIP64 EOCD does not end at its locator")

    directory = reader.read(cd_offset, cd_bytes)
    directory_hash = _sha256(directory)
    if directory_hash != frozen["central_directory_sha256"]:
        raise Zip64Error("central-directory SHA-256 differs")
    entries = parse_central_directory(directory, expected_entries=zip_entries_total)
    layout = Zip64Layout(
        archive_size=archive_size,
        entry_count=zip_entries_total,
        central_directory_offset=cd_offset,
        central_directory_bytes=cd_bytes,
        tail_sha256=tail_hash,
        central_directory_sha256=directory_hash,
        zip64_eocd_offset=frozen["zip64_eocd_offset"],
        zip64_locator_offset=locator_offset,
        classic_eocd_offset=eocd_offset,
    )
    return layout, entries


def _assert_entry(entry: CentralEntry, expected: Mapping[str, Any]) -> None:
    observed = {
        "path": entry.path,
        "local_header_offset": entry.local_header_offset,
        "flags": entry.flags,
        "compression_method": entry.compression_method,
        "compressed_bytes": entry.compressed_bytes,
        "uncompressed_bytes": entry.uncompressed_bytes,
        "crc32": f"{entry.crc32:08x}",
    }
    frozen = {key: expected[key] for key in observed}
    if observed != frozen:
        raise Zip64Error(f"central member metadata differs: {observed!r}")


def extract_member(
    reader: RangeReader,
    entries: Mapping[str, CentralEntry],
    expected: Mapping[str, Any],
) -> ExtractedMember:
    """Fetch, inflate, and authenticate one frozen member by exact ranges."""

    path = expected["path"]
    entry = entries.get(path)
    if entry is None:
        raise Zip64Error(f"target member is absent: {path}")
    _assert_entry(entry, expected)
    fixed = reader.read(entry.local_header_offset, 30)
    values = struct.unpack("<4s5H3I2H", fixed)
    (
        signature,
        _version,
        flags,
        method,
        _mtime,
        _mdate,
        crc32,
        compressed,
        uncompressed,
        name_bytes,
        extra_bytes,
    ) = values
    if signature != LOCAL_SIGNATURE:
        raise Zip64Error("local header signature differs")
    if flags & 0x8:
        raise Zip64Error("data-descriptor members are forbidden for the target")
    if (flags, method, crc32, compressed, uncompressed) != (
        entry.flags,
        entry.compression_method,
        entry.crc32,
        entry.compressed_bytes,
        entry.uncompressed_bytes,
    ):
        raise Zip64Error("local and central member metadata differ")
    remainder = reader.read(
        entry.local_header_offset + 30,
        name_bytes + extra_bytes + entry.compressed_bytes,
    )
    name_raw = remainder[:name_bytes]
    local_path = _safe_path(name_raw, utf8=bool(flags & 0x800))
    if local_path != entry.path:
        raise Zip64Error("local and central member paths differ")
    extra = remainder[name_bytes : name_bytes + extra_bytes]
    if extra:
        _extra_fields(extra)
    compressed_payload = remainder[name_bytes + extra_bytes :]
    if method == 8:
        inflater = zlib.decompressobj(-15)
        try:
            payload = inflater.decompress(compressed_payload) + inflater.flush()
        except zlib.error as error:
            raise Zip64Error("target deflate stream is invalid") from error
        if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
            raise Zip64Error("target deflate stream has trailing or incomplete data")
    elif method == 0:
        payload = compressed_payload
    else:  # already rejected by central parser
        raise Zip64Error("target compression method is unsupported")
    if len(payload) != entry.uncompressed_bytes:
        raise Zip64Error("target uncompressed size differs")
    if zlib.crc32(payload) & 0xFFFFFFFF != entry.crc32:
        raise Zip64Error("target CRC32 differs")
    digest = _sha256(payload)
    if digest != expected["sha256"]:
        raise Zip64Error("target SHA-256 differs")
    return ExtractedMember(entry=entry, payload=payload, sha256=digest)

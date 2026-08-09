"""Minimal fail-closed ZIP/ZIP64 parser for authenticated bounded ranges."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import Any, Iterable

from .contract import exact, require
from .errors import VerificationError


CENTRAL_STRUCT = struct.Struct("<4s6H3I5H2I")
LOCAL_STRUCT = struct.Struct("<4s5H3I2H")
EOCD_STRUCT = struct.Struct("<4s4H2IH")
ZIP64_EOCD_STRUCT = struct.Struct("<4sQ2H2I4Q")
ZIP64_LOCATOR_STRUCT = struct.Struct("<4sIQI")


@dataclass(frozen=True)
class ZipEntry:
    name: str
    version_needed: int
    flags: int
    method: int
    crc32: int
    compressed_bytes: int
    uncompressed_bytes: int
    local_header_offset: int


@dataclass(frozen=True)
class DirectoryResult:
    entries: tuple[ZipEntry, ...]
    tail_sha256: str
    directory_sha256: str

    def unique(self, name: str, stage: str) -> ZipEntry:
        matches = [entry for entry in self.entries if entry.name == name]
        if len(matches) != 1:
            raise VerificationError(stage, f"expected one entry named {name!r}, got {len(matches)}")
        return matches[0]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_name(raw: bytes, stage: str) -> str:
    try:
        name = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise VerificationError(stage, "non-ASCII archive name is outside the frozen profile") from exc
    require(bool(name), stage, "empty member name")
    require("\x00" not in name and "\\" not in name, stage, f"unsafe member name {name!r}")
    require(not name.startswith("/"), stage, f"absolute member name {name!r}")
    require("//" not in name, stage, f"empty path component in {name!r}")
    components = name.rstrip("/").split("/")
    require(all(part not in ("", ".", "..") for part in components), stage, f"unsafe path {name!r}")
    require(not (components and ":" in components[0]), stage, f"drive-like path {name!r}")
    return name


def _extra_fields(extra: bytes, stage: str) -> list[tuple[int, bytes]]:
    fields: list[tuple[int, bytes]] = []
    offset = 0
    while offset < len(extra):
        require(len(extra) - offset >= 4, stage, "truncated extra-field header")
        tag, size = struct.unpack_from("<HH", extra, offset)
        offset += 4
        require(size <= len(extra) - offset, stage, "truncated extra-field payload")
        fields.append((tag, extra[offset : offset + size]))
        offset += size
    require(offset == len(extra), stage, "extra-field framing mismatch")
    return fields


def _apply_zip64(
    uncompressed: int,
    compressed: int,
    local_offset: int,
    disk: int,
    fields: Iterable[tuple[int, bytes]],
    stage: str,
) -> tuple[int, int, int, int]:
    sentinels = (
        uncompressed == 0xFFFFFFFF,
        compressed == 0xFFFFFFFF,
        local_offset == 0xFFFFFFFF,
        disk == 0xFFFF,
    )
    zip64 = [payload for tag, payload in fields if tag == 0x0001]
    require(len(zip64) <= 1, stage, "duplicate ZIP64 extra field")
    if not any(sentinels):
        return uncompressed, compressed, local_offset, disk
    require(len(zip64) == 1, stage, "ZIP64 sentinel without ZIP64 extra field")
    payload = zip64[0]
    cursor = 0
    values = [uncompressed, compressed, local_offset, disk]
    widths = [8, 8, 8, 4]
    formats = ["<Q", "<Q", "<Q", "<I"]
    for index, needed in enumerate(sentinels):
        if needed:
            width = widths[index]
            require(cursor + width <= len(payload), stage, "truncated ZIP64 extra field")
            values[index] = struct.unpack_from(formats[index], payload, cursor)[0]
            cursor += width
    require(cursor == len(payload), stage, "unexpected bytes in ZIP64 extra field")
    return values[0], values[1], values[2], values[3]


def parse_central_directory(data: bytes, expected_count: int, stage: str) -> tuple[ZipEntry, ...]:
    require(type(expected_count) is int and expected_count >= 0, stage, "invalid expected entry count")
    entries: list[ZipEntry] = []
    names: set[str] = set()
    offset = 0
    while offset < len(data):
        require(len(data) - offset >= CENTRAL_STRUCT.size, stage, "truncated central header")
        header = CENTRAL_STRUCT.unpack_from(data, offset)
        require(header[0] == b"PK\x01\x02", stage, f"bad central signature at byte {offset}")
        (
            _,
            _version_made,
            version_needed,
            flags,
            method,
            _mtime,
            _mdate,
            crc32,
            compressed,
            uncompressed,
            name_len,
            extra_len,
            comment_len,
            disk,
            _internal,
            _external,
            local_offset,
        ) = header
        record_len = CENTRAL_STRUCT.size + name_len + extra_len + comment_len
        require(record_len <= len(data) - offset, stage, "truncated central record")
        cursor = offset + CENTRAL_STRUCT.size
        name = _validate_name(data[cursor : cursor + name_len], stage)
        cursor += name_len
        fields = _extra_fields(data[cursor : cursor + extra_len], stage)
        uncompressed, compressed, local_offset, disk = _apply_zip64(
            uncompressed, compressed, local_offset, disk, fields, stage
        )
        require(comment_len == 0, stage, f"unexpected member comment for {name!r}")
        require(flags == 0, stage, f"unsupported flags {flags:#x} for {name!r}")
        require(method in (0, 8), stage, f"unsupported method {method} for {name!r}")
        require(disk == 0, stage, f"multi-disk member {name!r}")
        require(name not in names, stage, f"duplicate member {name!r}")
        names.add(name)
        entries.append(
            ZipEntry(
                name=name,
                version_needed=version_needed,
                flags=flags,
                method=method,
                crc32=crc32,
                compressed_bytes=compressed,
                uncompressed_bytes=uncompressed,
                local_header_offset=local_offset,
            )
        )
        offset += record_len
    require(offset == len(data), stage, "central directory has trailing bytes")
    exact(len(entries), expected_count, stage, "central entry count")
    return tuple(entries)


def _valid_eocd_candidates(tail: bytes, absolute_start: int, archive_end: int) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while True:
        cursor = tail.find(b"PK\x05\x06", cursor)
        if cursor < 0:
            break
        if len(tail) - cursor >= EOCD_STRUCT.size:
            comment_len = struct.unpack_from("<H", tail, cursor + 20)[0]
            if absolute_start + cursor + EOCD_STRUCT.size + comment_len == archive_end:
                offsets.append(cursor)
        cursor += 1
    return offsets


def verify_outer_zip64(source: Any, cfg: dict[str, Any]) -> DirectoryResult:
    stage = "A3_OUTER_ZIP64"
    tail = source.read(cfg["tail_start"], cfg["tail_bytes"])
    tail_hash = _sha256(tail)
    exact(tail_hash, cfg["tail_sha256"], stage, "tail SHA-256")
    candidates = _valid_eocd_candidates(tail, cfg["tail_start"], source.total_bytes)
    exact(candidates, [cfg["classic_eocd_offset"] - cfg["tail_start"]], stage, "valid EOCD offsets")
    eocd_at = candidates[0]
    eocd = EOCD_STRUCT.unpack_from(tail, eocd_at)
    _, disk, cd_disk, disk_count, total_count, cd_size32, cd_offset32, comment = eocd
    exact(disk, 0, stage, "EOCD disk")
    exact(cd_disk, 0, stage, "EOCD directory disk")
    exact(disk_count, cfg["entry_count"], stage, "EOCD disk count")
    exact(total_count, cfg["entry_count"], stage, "EOCD total count")
    exact(cd_size32, cfg["central_directory_bytes"], stage, "EOCD directory size")
    exact(cd_offset32, 0xFFFFFFFF, stage, "EOCD ZIP64 offset sentinel")
    exact(comment, 0, stage, "EOCD comment length")

    locator_abs = cfg["zip64_locator_offset"]
    locator_at = locator_abs - cfg["tail_start"]
    exact(locator_abs + ZIP64_LOCATOR_STRUCT.size, cfg["classic_eocd_offset"], stage, "locator adjacency")
    require(0 <= locator_at <= len(tail) - ZIP64_LOCATOR_STRUCT.size, stage, "locator outside tail")
    locator = ZIP64_LOCATOR_STRUCT.unpack_from(tail, locator_at)
    exact(locator[0], b"PK\x06\x07", stage, "ZIP64 locator signature")
    exact(locator[1], 0, stage, "ZIP64 EOCD disk")
    exact(locator[2], cfg["zip64_eocd_offset"], stage, "ZIP64 EOCD pointer")
    exact(locator[3], 1, stage, "ZIP64 disk count")

    zip64_abs = cfg["zip64_eocd_offset"]
    zip64_at = zip64_abs - cfg["tail_start"]
    require(0 <= zip64_at <= len(tail) - ZIP64_EOCD_STRUCT.size, stage, "ZIP64 EOCD outside tail")
    record = ZIP64_EOCD_STRUCT.unpack_from(tail, zip64_at)
    exact(record[0], b"PK\x06\x06", stage, "ZIP64 EOCD signature")
    exact(record[1], 44, stage, "ZIP64 EOCD payload length")
    exact(record[4], 0, stage, "ZIP64 current disk")
    exact(record[5], 0, stage, "ZIP64 directory disk")
    exact(record[6], cfg["entry_count"], stage, "ZIP64 disk count")
    exact(record[7], cfg["entry_count"], stage, "ZIP64 total count")
    exact(record[8], cfg["central_directory_bytes"], stage, "ZIP64 directory size")
    exact(record[9], cfg["central_directory_offset"], stage, "ZIP64 directory offset")
    exact(zip64_abs + ZIP64_EOCD_STRUCT.size, locator_abs, stage, "ZIP64 record adjacency")

    directory = source.read(cfg["central_directory_offset"], cfg["central_directory_bytes"])
    directory_hash = _sha256(directory)
    exact(directory_hash, cfg["central_directory_sha256"], stage, "central-directory SHA-256")
    entries = parse_central_directory(directory, cfg["entry_count"], stage)
    return DirectoryResult(entries, tail_hash, directory_hash)


def verify_nested_zip(source: Any, base: int, cfg: dict[str, Any]) -> DirectoryResult:
    stage = "A4_NESTED_ZIP"
    require(base >= 0 and base + cfg["bytes"] <= source.total_bytes, stage, "nested ZIP lies outside source")
    tail_abs = base + cfg["tail_start_relative"]
    tail = source.read(tail_abs, cfg["tail_bytes"])
    tail_hash = _sha256(tail)
    exact(tail_hash, cfg["tail_sha256"], stage, "tail SHA-256")
    archive_end = base + cfg["bytes"]
    candidates = _valid_eocd_candidates(tail, tail_abs, archive_end)
    expected_relative = cfg["classic_eocd_offset_relative"] - cfg["tail_start_relative"]
    exact(candidates, [expected_relative], stage, "valid EOCD offsets")
    record = EOCD_STRUCT.unpack_from(tail, candidates[0])
    _, disk, cd_disk, disk_count, total_count, cd_size, cd_offset, comment = record
    exact(disk, 0, stage, "EOCD disk")
    exact(cd_disk, 0, stage, "EOCD directory disk")
    exact(disk_count, cfg["entry_count"], stage, "EOCD disk count")
    exact(total_count, cfg["entry_count"], stage, "EOCD total count")
    exact(cd_size, cfg["central_directory_bytes"], stage, "EOCD directory size")
    exact(cd_offset, cfg["central_directory_offset_relative"], stage, "EOCD directory offset")
    exact(comment, 0, stage, "EOCD comment length")
    require(b"PK\x06\x06" not in tail and b"PK\x06\x07" not in tail, stage, "unexpected nested ZIP64 record")

    directory = source.read(base + cfg["central_directory_offset_relative"], cfg["central_directory_bytes"])
    directory_hash = _sha256(directory)
    exact(directory_hash, cfg["central_directory_sha256"], stage, "central-directory SHA-256")
    entries = parse_central_directory(directory, cfg["entry_count"], stage)
    for entry in entries:
        require(entry.local_header_offset < cfg["central_directory_offset_relative"], stage, "local header overlaps directory")
        require(
            entry.local_header_offset + LOCAL_STRUCT.size + entry.compressed_bytes <= cfg["central_directory_offset_relative"],
            stage,
            f"member {entry.name!r} extends into central directory",
        )
    return DirectoryResult(entries, tail_hash, directory_hash)


def verify_local_header(
    source: Any,
    *,
    absolute_offset: int,
    expected_bytes: int,
    expected_sha256: str,
    central: ZipEntry,
    stage: str,
) -> int:
    data = source.read(absolute_offset, expected_bytes)
    exact(_sha256(data), expected_sha256, stage, "local-header SHA-256")
    require(len(data) >= LOCAL_STRUCT.size, stage, "truncated local header")
    record = LOCAL_STRUCT.unpack_from(data)
    (
        signature,
        version_needed,
        flags,
        method,
        _mtime,
        _mdate,
        crc32,
        compressed,
        uncompressed,
        name_len,
        extra_len,
    ) = record
    exact(signature, b"PK\x03\x04", stage, "local signature")
    exact(version_needed, central.version_needed, stage, "version needed")
    exact(flags, central.flags, stage, "local flags")
    exact(method, central.method, stage, "local method")
    exact(crc32, central.crc32, stage, "local CRC32")
    exact(compressed, central.compressed_bytes, stage, "local compressed size")
    exact(uncompressed, central.uncompressed_bytes, stage, "local uncompressed size")
    exact(LOCAL_STRUCT.size + name_len + extra_len, len(data), stage, "local-header length")
    name = _validate_name(data[LOCAL_STRUCT.size : LOCAL_STRUCT.size + name_len], stage)
    exact(name, central.name, stage, "local member name")
    _extra_fields(data[LOCAL_STRUCT.size + name_len :], stage)
    return absolute_offset + len(data)

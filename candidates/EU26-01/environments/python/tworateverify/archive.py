"""Authenticated exact-member validator for the pinned EU26-01 ZIP."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from typing import Any
import zipfile

from .canonical import canonical_sha256, strict_json_load


class ArchiveValidationError(ValueError):
    """Raised when archive custody, schema or a frozen target fails closed."""


PARETO_RE = re.compile(r"([0-9]+) ([0-9]+) ")


@dataclass(frozen=True)
class ArchiveSpec:
    archive_bytes: int
    archive_md5: str
    archive_sha256: str
    member: str
    member_bytes: int
    member_compressed_bytes: int
    member_crc32: int
    member_sha256: str
    dimension: int = 100
    runs: int = 100
    algorithm: str = "TwoRateL10P1HV"
    func: str = "OneMax"
    published_mean: int = 61624
    published_variance: str = "3.271e+08"

    @classmethod
    def from_protocol(cls, path: Path) -> "ArchiveSpec":
        try:
            document = strict_json_load(path)
            archive = document["archive"]
            paper = document["paper"]
            return cls(
                archive_bytes=archive["bytes"],
                archive_md5=archive["md5"],
                archive_sha256=archive["sha256"],
                member=archive["member"],
                member_bytes=archive["member_uncompressed_bytes"],
                member_compressed_bytes=archive["member_compressed_bytes"],
                member_crc32=int(archive["member_crc32"], 16),
                member_sha256=archive["member_sha256"],
                dimension=paper["dimension"],
                runs=paper["runs"],
                published_mean=paper["published_mean_fes"],
                published_variance=paper["published_population_variance"],
            )
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise ArchiveValidationError("frozen protocol JSON is invalid") from error

    def validate(self) -> None:
        integer_fields = {
            "archive_bytes": self.archive_bytes,
            "member_bytes": self.member_bytes,
            "member_compressed_bytes": self.member_compressed_bytes,
            "member_crc32": self.member_crc32,
            "dimension": self.dimension,
            "runs": self.runs,
            "published_mean": self.published_mean,
        }
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in integer_fields.values()):
            raise ArchiveValidationError("archive specification integer is invalid")
        for label, digest, length in (
            ("archive_md5", self.archive_md5, 32),
            ("archive_sha256", self.archive_sha256, 64),
            ("member_sha256", self.member_sha256, 64),
        ):
            if len(digest) != length or any(character not in "0123456789abcdef" for character in digest):
                raise ArchiveValidationError(f"{label} is not a lowercase hexadecimal digest")
        if not self.member or PurePosixPath(self.member).as_posix() != self.member:
            raise ArchiveValidationError("member path is not canonical POSIX")


def _hash_handle(handle: Any) -> tuple[int, str, str]:
    handle.seek(0)
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    size = 0
    for block in iter(lambda: handle.read(1024 * 1024), b""):
        size += len(block)
        md5.update(block)
        sha256.update(block)
    return size, md5.hexdigest(), sha256.hexdigest()


def _descriptor_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns)


def _validate_zip_inventory(archive: zipfile.ZipFile, spec: ArchiveSpec) -> zipfile.ZipInfo:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ArchiveValidationError("ZIP contains duplicate member names")
    selected: zipfile.ZipInfo | None = None
    for info in infos:
        name = info.filename
        if "\\" in name or not name or name.startswith("/"):
            raise ArchiveValidationError("ZIP contains a non-canonical path")
        path = PurePosixPath(name)
        if any(part in ("", ".", "..") for part in path.parts):
            raise ArchiveValidationError("ZIP contains an unsafe path component")
        if info.flag_bits & 0x1:
            raise ArchiveValidationError("encrypted ZIP members are forbidden")
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise ArchiveValidationError("unsupported ZIP compression method")
        mode = info.external_attr >> 16
        kind = stat.S_IFMT(mode)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ArchiveValidationError("ZIP contains a non-regular member")
        if name == spec.member:
            selected = info
    if selected is None:
        raise ArchiveValidationError("exact frozen member is absent")
    if selected.is_dir() or stat.S_IFMT(selected.external_attr >> 16) == stat.S_IFDIR:
        raise ArchiveValidationError("exact frozen member is not a regular file")
    if selected.file_size != spec.member_bytes:
        raise ArchiveValidationError("exact member uncompressed size mismatch")
    if selected.compress_size != spec.member_compressed_bytes:
        raise ArchiveValidationError("exact member compressed size mismatch")
    if selected.CRC != spec.member_crc32:
        raise ArchiveValidationError("exact member CRC32 mismatch")
    return selected


def load_authenticated_member(path: Path, spec: ArchiveSpec) -> tuple[bytes, dict[str, Any]]:
    """Bind parsing to one retained descriptor and a private snapshot."""

    spec.validate()
    path = Path(os.path.abspath(path))
    try:
        supplied = os.lstat(path)
    except OSError as error:
        raise ArchiveValidationError("archive path cannot be inspected") from error
    if stat.S_ISLNK(supplied.st_mode):
        raise ArchiveValidationError("archive path must not be a symbolic link")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as source, tempfile.TemporaryFile("w+b") as snapshot:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ArchiveValidationError("archive descriptor is not a regular file")
            path_before = os.stat(path, follow_symlinks=False)
            if (path_before.st_dev, path_before.st_ino) != (before.st_dev, before.st_ino):
                raise ArchiveValidationError("archive path is not bound to the retained descriptor")

            md5 = hashlib.md5(usedforsecurity=False)
            sha256 = hashlib.sha256()
            copied = 0
            source.seek(0)
            for block in iter(lambda: source.read(1024 * 1024), b""):
                copied += len(block)
                md5.update(block)
                sha256.update(block)
                snapshot.write(block)
            archive_md5 = md5.hexdigest()
            archive_sha256 = sha256.hexdigest()
            if copied != spec.archive_bytes:
                raise ArchiveValidationError("archive byte length mismatch")
            if archive_md5 != spec.archive_md5 or archive_sha256 != spec.archive_sha256:
                raise ArchiveValidationError("archive digest mismatch")

            snapshot.flush()
            snapshot.seek(0)
            try:
                with zipfile.ZipFile(snapshot, "r") as archive:
                    info = _validate_zip_inventory(archive, spec)
                    with archive.open(info, "r") as member_handle:
                        payload = member_handle.read(spec.member_bytes + 1)
                    if len(payload) != spec.member_bytes:
                        raise ArchiveValidationError("decompressed member length mismatch")
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError) as error:
                raise ArchiveValidationError("ZIP/member decoding failed") from error

            member_sha256 = hashlib.sha256(payload).hexdigest()
            if member_sha256 != spec.member_sha256:
                raise ArchiveValidationError("exact member SHA-256 mismatch")

            snapshot_size_end, snapshot_md5_end, snapshot_sha256_end = _hash_handle(snapshot)
            source_size_end, source_md5_end, source_sha256_end = _hash_handle(source)
            after = os.fstat(descriptor)
            try:
                path_after = os.stat(path, follow_symlinks=False)
            except OSError as error:
                raise ArchiveValidationError("archive path disappeared during validation") from error
            if _descriptor_identity(before) != _descriptor_identity(after):
                raise ArchiveValidationError("archive descriptor identity changed during validation")
            if (path_after.st_dev, path_after.st_ino) != (after.st_dev, after.st_ino):
                raise ArchiveValidationError("archive path was replaced during validation")
            if (
                snapshot_size_end != copied
                or source_size_end != copied
                or snapshot_md5_end != archive_md5
                or source_md5_end != archive_md5
                or snapshot_sha256_end != archive_sha256
                or source_sha256_end != archive_sha256
            ):
                raise ArchiveValidationError("post-use archive authentication mismatch")
            return payload, {
                "custody_method": "retained_descriptor_private_snapshot_reauthenticated",
                "archive_bytes": copied,
                "archive_md5": archive_md5,
                "archive_sha256": archive_sha256,
                "archive_sha256_end": source_sha256_end,
                "snapshot_sha256_start": archive_sha256,
                "snapshot_sha256_end": snapshot_sha256_end,
                "descriptor_device": before.st_dev,
                "descriptor_inode": before.st_ino,
                "member": spec.member,
                "member_bytes": len(payload),
                "member_compressed_bytes": info.compress_size,
                "member_crc32": f"{info.CRC:08x}",
                "member_sha256": member_sha256,
            }
    finally:
        os.close(descriptor)


def _expected_header(runs: int) -> list[str]:
    header = ["pareto", "algorithm", "func", "dimension"]
    for run in range(runs):
        header.extend((f"found{run}", f"First_hit{run}"))
    return header


def parse_focus_csv(payload: bytes, spec: ArchiveSpec) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ArchiveValidationError("focus member is not strict UTF-8") from error
    if "\x00" in text or text.startswith("\ufeff"):
        raise ArchiveValidationError("focus member contains forbidden text markers")
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as error:
        raise ArchiveValidationError("focus CSV is malformed") from error
    if not rows or rows[0] != _expected_header(spec.runs):
        raise ArchiveValidationError("focus CSV header differs from the frozen schema")
    data = rows[1:]
    if len(data) != spec.dimension + 1:
        raise ArchiveValidationError("focus CSV must contain exactly n+1 data rows")
    if any(len(row) != len(rows[0]) for row in data):
        raise ArchiveValidationError("focus CSV row width mismatch")

    seen: set[tuple[int, int]] = set()
    per_run: list[list[int]] = [[] for _ in range(spec.runs)]
    for row_number, row in enumerate(data, start=2):
        match = PARETO_RE.fullmatch(row[0])
        if match is None:
            raise ArchiveValidationError(f"row {row_number} has non-canonical Pareto text")
        point = (int(match.group(1)), int(match.group(2)))
        if point[0] + point[1] != spec.dimension or point in seen:
            raise ArchiveValidationError("Pareto rows are duplicated or outside OneMinMax")
        seen.add(point)
        if row[1] != spec.algorithm or row[2] != spec.func or row[3] != str(spec.dimension):
            raise ArchiveValidationError("focus CSV metadata differs from the frozen cell")
        for run in range(spec.runs):
            found = row[4 + 2 * run]
            hit = row[5 + 2 * run]
            if found != "True":
                raise ArchiveValidationError(f"run {run} is incomplete")
            if not hit.isascii() or not hit.isdecimal():
                raise ArchiveValidationError(f"run {run} has a non-integral first hit")
            per_run[run].append(int(hit))
    expected = {(value, spec.dimension - value) for value in range(spec.dimension + 1)}
    if seen != expected:
        raise ArchiveValidationError("focus CSV does not contain the complete OneMinMax front")
    completions = [max(values) for values in per_run]
    return {
        "rows": len(data),
        "columns": len(rows[0]),
        "complete_runs": len(completions),
        "completion_fes": completions,
    }


def _fraction_decimal(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = max(80, len(str(abs(value.numerator))) + len(str(value.denominator)) + 10)
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
    rendered = format(decimal, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _scientific_four_significant(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = 80
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
        if decimal == 0:
            rounded = Decimal(0)
        else:
            quantum = Decimal(1).scaleb(decimal.adjusted() - 3)
            rounded = decimal.quantize(quantum, rounding=ROUND_HALF_UP)
        scientific = format(rounded, ".3E")
    mantissa, exponent = scientific.split("E")
    return f"{mantissa.lower()}e{int(exponent):+03d}"


def completion_statistics(completions: Any, spec: ArchiveSpec) -> dict[str, Any]:
    if (
        not isinstance(completions, list)
        or len(completions) != spec.runs
        or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in completions)
    ):
        raise ArchiveValidationError("completion vector is invalid")
    count = len(completions)
    total = sum(completions)
    mean = Fraction(total, count)
    variance = sum((Fraction(value) - mean) ** 2 for value in completions) / count
    rounded_mean = (2 * total + count) // (2 * count)
    rendered_variance = _scientific_four_significant(variance)
    return {
        "count": count,
        "minimum": min(completions),
        "maximum": max(completions),
        "sum": total,
        "mean_exact": _fraction_decimal(mean),
        "mean_fraction": f"{mean.numerator}/{mean.denominator}",
        "mean_published_rounding": rounded_mean,
        "population_variance_exact": _fraction_decimal(variance),
        "population_variance_fraction": f"{variance.numerator}/{variance.denominator}",
        "population_variance_published_rounding": rendered_variance,
        "matches_published_mean": rounded_mean == spec.published_mean,
        "matches_published_population_variance": rendered_variance == spec.published_variance,
    }


def validate_archive(path: Path, spec: ArchiveSpec) -> dict[str, Any]:
    payload, custody = load_authenticated_member(path, spec)
    table = parse_focus_csv(payload, spec)
    statistics = completion_statistics(table["completion_fes"], spec)
    gates = {
        "A1_custody": "PASS",
        "A2_member_identity": "PASS",
        "A3_schema": "PASS",
        "A4_completion": "PASS" if table["complete_runs"] == spec.runs else "FAIL",
        "A5_table1": "PASS"
        if statistics["matches_published_mean"]
        and statistics["matches_published_population_variance"]
        else "FAIL",
    }
    archive_status = "PASS_ARCHIVE_EXACT" if all(value == "PASS" for value in gates.values()) else "FAIL_ARCHIVE"
    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-01",
        "scope": "ARCHIVE_AND_FORMULA_VALIDATION_ONLY",
        "archive_status": archive_status,
        "paper_level_status": "BLOCKED_SOURCE_NATIVE_REPLAY",
        "eligibility_status": "conditional_noneligible",
        "pass_full_allowed": False,
        "claim_limit": "exact_archived_table_recalculation_not_source_native_reproduction",
        "algorithm2_conflict": "literal_one_based_pseudocode_4_low_6_high_vs_prose_and_source_5_low_5_high",
        "custody": custody,
        "table": table,
        "statistics": statistics,
        "gates": gates,
        "completion_vector_sha256": canonical_sha256(
            table["completion_fes"], domain="EU26-01-COMPLETION-FES-V1"
        ),
    }
    report["report_sha256"] = canonical_sha256(
        report, domain="EU26-01-ARCHIVE-REPORT-V1"
    )
    return report

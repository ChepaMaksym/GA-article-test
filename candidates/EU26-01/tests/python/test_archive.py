from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

from tworateverify import archive as archive_module
from tworateverify.archive import (
    ArchiveSpec,
    ArchiveValidationError,
    completion_statistics,
    load_authenticated_member,
    parse_focus_csv,
    validate_archive,
)


def focus_payload(*, complete: bool = True, extra_column: bool = False) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    header = ["pareto", "algorithm", "func", "dimension"]
    for run in range(3):
        header.extend((f"found{run}", f"First_hit{run}"))
    if extra_column:
        header.append("unexpected")
    writer.writerow(header)
    hits = ((1, 2, 7), (2, 4, 1), (3, 5, 2))
    for k in range(3):
        row: list[object] = [f"{k} {2-k} ", "TwoRateL10P1HV", "OneMax", 2]
        for run in range(3):
            row.extend(("True" if complete or run != 1 else "False", hits[k][run]))
        if extra_column:
            row.append("x")
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


def make_archive(directory: Path, payload: bytes, *,
                 member: str = "focus.csv", extra_members: list[tuple[str, bytes]] | None = None,
                 duplicate: bool = False) -> tuple[Path, ArchiveSpec]:
    path = directory / "fixture.zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(member, payload)
            for name, value in extra_members or []:
                archive.writestr(name, value)
            if duplicate:
                archive.writestr(member, payload)
    raw = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo(member)
    completions = [3, 5, 7]
    return path, ArchiveSpec(
        archive_bytes=len(raw),
        archive_md5=hashlib.md5(raw, usedforsecurity=False).hexdigest(),
        archive_sha256=hashlib.sha256(raw).hexdigest(),
        member=member,
        member_bytes=len(payload),
        member_compressed_bytes=info.compress_size,
        member_crc32=info.CRC,
        member_sha256=hashlib.sha256(payload).hexdigest(),
        dimension=2,
        runs=3,
        published_mean=5,
        published_variance="2.667e+00",
    )


class ArchiveParserTests(unittest.TestCase):
    def test_synthetic_archive_passes_all_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            path, spec = make_archive(Path(directory), focus_payload())
            report = validate_archive(path, spec)
        self.assertEqual(report["archive_status"], "PASS_ARCHIVE_EXACT")
        self.assertEqual(report["table"]["completion_fes"], [3, 5, 7])
        self.assertEqual(report["statistics"]["mean_exact"], "5")
        self.assertEqual(report["statistics"]["population_variance_exact"], "2.6666666666666666666666666666666666666666666666666666666666666666666666666666667")
        self.assertEqual(report["statistics"]["population_variance_published_rounding"], "2.667e+00")
        self.assertFalse(report["pass_full_allowed"])
        self.assertEqual(report["paper_level_status"], "BLOCKED_SOURCE_NATIVE_REPLAY")

    def test_exact_schema_and_completion_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path, spec = make_archive(Path(directory), focus_payload())
            valid_payload, _ = load_authenticated_member(path, spec)
            for payload in (
                focus_payload(complete=False),
                focus_payload(extra_column=True),
                valid_payload.replace(b"0 2 ", b"0 1 ", 1),
                valid_payload.replace(b",True,1", b",True,-1", 1),
            ):
                with self.subTest(payload=payload[:80]):
                    with self.assertRaises(ArchiveValidationError):
                        parse_focus_csv(payload, spec)

    def test_wrong_archive_and_member_digests_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path, spec = make_archive(Path(directory), focus_payload())
            wrong_archive = ArchiveSpec(**{**spec.__dict__, "archive_sha256": "0" * 64})
            wrong_member = ArchiveSpec(**{**spec.__dict__, "member_sha256": "0" * 64})
            with self.assertRaisesRegex(ArchiveValidationError, "archive digest"):
                load_authenticated_member(path, wrong_archive)
            with self.assertRaisesRegex(ArchiveValidationError, "member SHA"):
                load_authenticated_member(path, wrong_member)

    def test_duplicate_and_unsafe_members_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate_path, duplicate_spec = make_archive(root, focus_payload(), duplicate=True)
            with self.assertRaisesRegex(ArchiveValidationError, "duplicate"):
                load_authenticated_member(duplicate_path, duplicate_spec)
        with tempfile.TemporaryDirectory() as directory:
            unsafe_path, unsafe_spec = make_archive(
                Path(directory), focus_payload(), extra_members=[("../escape", b"x")]
            )
            with self.assertRaisesRegex(ArchiveValidationError, "unsafe"):
                load_authenticated_member(unsafe_path, unsafe_spec)

    def test_symlink_input_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, spec = make_archive(root, focus_payload())
            link = root / "link.zip"
            link.symlink_to(path)
            with self.assertRaisesRegex(ArchiveValidationError, "symbolic link"):
                load_authenticated_member(link, spec)

    def test_atomic_path_replacement_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, spec = make_archive(root, focus_payload())
            replacement = root / "replacement.zip"
            replacement.write_bytes(path.read_bytes())
            original = archive_module._validate_zip_inventory

            def replace_after_inventory(archive, frozen_spec):
                info = original(archive, frozen_spec)
                os.replace(replacement, path)
                return info

            with mock.patch.object(
                archive_module, "_validate_zip_inventory", side_effect=replace_after_inventory
            ):
                with self.assertRaisesRegex(ArchiveValidationError, "path was replaced"):
                    load_authenticated_member(path, spec)

    def test_statistic_rounding_is_half_away_and_population_ddof_zero(self):
        spec = ArchiveSpec(
            archive_bytes=0,
            archive_md5="0" * 32,
            archive_sha256="0" * 64,
            member="x",
            member_bytes=0,
            member_compressed_bytes=0,
            member_crc32=0,
            member_sha256="0" * 64,
            dimension=1,
            runs=2,
            published_mean=2,
            published_variance="2.500e-01",
        )
        statistics = completion_statistics([1, 2], spec)
        self.assertEqual(statistics["mean_exact"], "1.5")
        self.assertEqual(statistics["mean_published_rounding"], 2)
        self.assertEqual(statistics["population_variance_exact"], "0.25")
        self.assertEqual(statistics["population_variance_published_rounding"], "2.500e-01")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import hashlib
import struct
import unittest
import zlib

from eu2613.errors import VerificationError
from eu2613.ranges import MemoryRangeSource
from eu2613.zipformat import parse_central_directory, verify_local_header, verify_nested_zip, verify_outer_zip64

from fixture_builders import build_archive_fixture


class ZipFormatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = build_archive_fixture()

    def parse_outer(self, contract=None, data=None):
        cfg = contract or self.fixture.contract
        source = MemoryRangeSource(data or self.fixture.outer)
        return source, verify_outer_zip64(source, cfg["outer_zip64"])

    def test_full_fixture_path(self) -> None:
        cfg = self.fixture.contract
        source, outer = self.parse_outer()
        member = outer.unique(cfg["outer_member"]["path"], "TEST")
        base = verify_local_header(
            source,
            absolute_offset=cfg["outer_member"]["local_header_offset"],
            expected_bytes=cfg["outer_member"]["local_header_bytes"],
            expected_sha256=cfg["outer_member"]["local_header_sha256"],
            central=member,
            stage="TEST",
        )
        self.assertEqual(base, cfg["outer_member"]["data_offset"])
        nested = verify_nested_zip(source, base, cfg["nested_zip"])
        target = nested.unique(cfg["target_member"]["path"], "TEST")
        data_offset = verify_local_header(
            source,
            absolute_offset=cfg["target_member"]["local_header_offset_absolute"],
            expected_bytes=cfg["target_member"]["local_header_bytes"],
            expected_sha256=cfg["target_member"]["local_header_sha256"],
            central=target,
            stage="TEST",
        )
        payload = source.read(data_offset, target.compressed_bytes)
        self.assertEqual(zlib.decompress(payload, -15), self.fixture.raw)

    def reject_outer(self, mutator) -> None:
        cfg = copy.deepcopy(self.fixture.contract)
        mutator(cfg)
        with self.assertRaises(VerificationError):
            self.parse_outer(cfg)

    def test_mutation_outer_tail_hash(self) -> None:
        self.reject_outer(lambda c: c["outer_zip64"].__setitem__("tail_sha256", "0" * 64))

    def test_mutation_outer_eocd_offset(self) -> None:
        self.reject_outer(lambda c: c["outer_zip64"].__setitem__("classic_eocd_offset", c["outer_zip64"]["classic_eocd_offset"] - 1))

    def test_mutation_zip64_offset(self) -> None:
        self.reject_outer(lambda c: c["outer_zip64"].__setitem__("zip64_eocd_offset", c["outer_zip64"]["zip64_eocd_offset"] - 1))

    def test_mutation_locator_offset(self) -> None:
        self.reject_outer(lambda c: c["outer_zip64"].__setitem__("zip64_locator_offset", c["outer_zip64"]["zip64_locator_offset"] - 1))

    def test_mutation_outer_directory_hash(self) -> None:
        self.reject_outer(lambda c: c["outer_zip64"].__setitem__("central_directory_sha256", "f" * 64))

    def test_mutation_outer_entry_count(self) -> None:
        self.reject_outer(lambda c: c["outer_zip64"].__setitem__("entry_count", 2))

    def test_mutation_outer_local_hash(self) -> None:
        source, outer = self.parse_outer()
        cfg = self.fixture.contract
        entry = outer.unique(cfg["outer_member"]["path"], "TEST")
        with self.assertRaises(VerificationError):
            verify_local_header(
                source,
                absolute_offset=0,
                expected_bytes=cfg["outer_member"]["local_header_bytes"],
                expected_sha256="0" * 64,
                central=entry,
                stage="TEST",
            )

    def central(self) -> bytes:
        cfg = self.fixture.contract["outer_zip64"]
        return self.fixture.outer[cfg["central_directory_offset"] : cfg["central_directory_offset"] + cfg["central_directory_bytes"]]

    def test_mutation_duplicate_name(self) -> None:
        central = self.central()
        with self.assertRaises(VerificationError):
            parse_central_directory(central + central, 2, "TEST")

    def test_mutation_unsafe_name(self) -> None:
        fixture = build_archive_fixture(outer_name="../evil.zip")
        with self.assertRaises(VerificationError):
            verify_outer_zip64(MemoryRangeSource(fixture.outer), fixture.contract["outer_zip64"])

    def test_mutation_encryption_flag(self) -> None:
        central = bytearray(self.central())
        struct.pack_into("<H", central, 8, 1)
        with self.assertRaises(VerificationError):
            parse_central_directory(bytes(central), 1, "TEST")

    def test_mutation_unsupported_method(self) -> None:
        central = bytearray(self.central())
        struct.pack_into("<H", central, 10, 99)
        with self.assertRaises(VerificationError):
            parse_central_directory(bytes(central), 1, "TEST")

    def test_mutation_member_comment(self) -> None:
        central = bytearray(self.central())
        struct.pack_into("<H", central, 32, 1)
        central.append(0)
        with self.assertRaises(VerificationError):
            parse_central_directory(bytes(central), 1, "TEST")

    def test_mutation_truncated_central(self) -> None:
        with self.assertRaises(VerificationError):
            parse_central_directory(self.central()[:-1], 1, "TEST")

    def test_mutation_bad_central_signature(self) -> None:
        central = bytearray(self.central())
        central[0] = 0
        with self.assertRaises(VerificationError):
            parse_central_directory(bytes(central), 1, "TEST")

    def test_mutation_zip64_sentinel_without_extra(self) -> None:
        central = bytearray(self.central())
        struct.pack_into("<I", central, 42, 0xFFFFFFFF)
        with self.assertRaises(VerificationError):
            parse_central_directory(bytes(central), 1, "TEST")

    def test_mutation_nested_tail_hash(self) -> None:
        cfg = copy.deepcopy(self.fixture.contract)
        cfg["nested_zip"]["tail_sha256"] = "0" * 64
        with self.assertRaises(VerificationError):
            verify_nested_zip(MemoryRangeSource(self.fixture.outer), cfg["outer_member"]["data_offset"], cfg["nested_zip"])

    def test_mutation_nested_directory_hash(self) -> None:
        cfg = copy.deepcopy(self.fixture.contract)
        cfg["nested_zip"]["central_directory_sha256"] = "0" * 64
        with self.assertRaises(VerificationError):
            verify_nested_zip(MemoryRangeSource(self.fixture.outer), cfg["outer_member"]["data_offset"], cfg["nested_zip"])

    def test_mutation_nested_eocd_offset(self) -> None:
        cfg = copy.deepcopy(self.fixture.contract)
        cfg["nested_zip"]["classic_eocd_offset_relative"] -= 1
        with self.assertRaises(VerificationError):
            verify_nested_zip(MemoryRangeSource(self.fixture.outer), cfg["outer_member"]["data_offset"], cfg["nested_zip"])

    def test_mutation_target_local_hash(self) -> None:
        cfg = self.fixture.contract
        source = MemoryRangeSource(self.fixture.outer)
        nested = verify_nested_zip(source, cfg["outer_member"]["data_offset"], cfg["nested_zip"])
        target = nested.unique(cfg["target_member"]["path"], "TEST")
        with self.assertRaises(VerificationError):
            verify_local_header(
                source,
                absolute_offset=cfg["target_member"]["local_header_offset_absolute"],
                expected_bytes=cfg["target_member"]["local_header_bytes"],
                expected_sha256="0" * 64,
                central=target,
                stage="TEST",
            )


if __name__ == "__main__":
    unittest.main()

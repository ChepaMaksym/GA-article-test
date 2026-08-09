from __future__ import annotations

import hashlib
import struct
import unittest
from copy import deepcopy

from eu2612.http_range import MemoryRangeReader
from eu2612.zip64 import Zip64Error, extract_member, inspect_archive, parse_central_directory
from test_support import make_zip64


class Zip64LayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = {"a.json": b'{"x":1}', "b.dat": b"evaluations raw_y\n1 0.0000000000\n"}
        self.archive, self.contract = make_zip64(self.files)

    def reader(self, payload: bytes | None = None) -> MemoryRangeReader:
        value = self.archive if payload is None else payload
        return MemoryRangeReader(value, maximum_request=len(value))

    def test_valid_zip64_layout_and_directory(self) -> None:
        layout, entries = inspect_archive(self.reader(), self.contract)
        self.assertEqual(layout.entry_count, 2)
        self.assertEqual(set(entries), set(self.files))

    def test_reader_size_mismatch_fails(self) -> None:
        with self.assertRaises(Zip64Error):
            inspect_archive(self.reader(self.archive + b"x"), self.contract)

    def test_tail_hash_mutation_fails(self) -> None:
        value = bytearray(self.archive)
        value[-1] ^= 1
        with self.assertRaises(Zip64Error):
            inspect_archive(self.reader(bytes(value)), self.contract)

    def test_central_hash_mutation_fails(self) -> None:
        contract = deepcopy(self.contract)
        contract["zip64"]["central_directory_sha256"] = "0" * 64
        with self.assertRaises(Zip64Error):
            inspect_archive(self.reader(), contract)

    def test_entry_count_mutation_fails(self) -> None:
        contract = deepcopy(self.contract)
        contract["zip64"]["entry_count"] = 3
        with self.assertRaises(Zip64Error):
            inspect_archive(self.reader(), contract)

    def test_eocd_offset_mutation_fails(self) -> None:
        contract = deepcopy(self.contract)
        contract["zip64"]["classic_eocd_offset"] -= 1
        with self.assertRaises(Zip64Error):
            inspect_archive(self.reader(), contract)

    def test_duplicate_directory_path_fails(self) -> None:
        archive, contract = make_zip64({"a.json": b"1", "b.json": b"2"})
        cd_offset = contract["zip64"]["central_directory_offset"]
        cd_bytes = contract["zip64"]["central_directory_bytes"]
        directory = bytearray(archive[cd_offset : cd_offset + cd_bytes])
        second = directory.find(b"b.json")
        self.assertGreater(second, 0)
        directory[second : second + 6] = b"a.json"
        with self.assertRaises(Zip64Error):
            parse_central_directory(bytes(directory), expected_entries=2)

    def test_unsafe_member_path_fails(self) -> None:
        archive, contract = make_zip64({"../bad": b"x"})
        with self.assertRaises(Zip64Error):
            inspect_archive(MemoryRangeReader(archive, maximum_request=len(archive)), contract)

    def test_directory_trailing_byte_fails(self) -> None:
        cd_offset = self.contract["zip64"]["central_directory_offset"]
        cd_bytes = self.contract["zip64"]["central_directory_bytes"]
        directory = self.archive[cd_offset : cd_offset + cd_bytes]
        with self.assertRaises(Zip64Error):
            parse_central_directory(directory + b"x", expected_entries=2)


class Zip64ExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = b'{"answer":42}'
        self.archive, self.contract = make_zip64({"target.json": self.payload})
        self.reader = MemoryRangeReader(self.archive, maximum_request=len(self.archive))
        self.layout, self.entries = inspect_archive(self.reader, self.contract)

    def test_exact_member_extracts(self) -> None:
        result = extract_member(self.reader, self.entries, self.contract["raw_members"]["target.json"])
        self.assertEqual(result.payload, self.payload)
        self.assertEqual(result.sha256, hashlib.sha256(self.payload).hexdigest())

    def test_missing_member_fails(self) -> None:
        expected = deepcopy(self.contract["raw_members"]["target.json"])
        expected["path"] = "missing.json"
        with self.assertRaises(Zip64Error):
            extract_member(self.reader, self.entries, expected)

    def test_frozen_crc_mutation_fails(self) -> None:
        expected = deepcopy(self.contract["raw_members"]["target.json"])
        expected["crc32"] = "00000000"
        with self.assertRaises(Zip64Error):
            extract_member(self.reader, self.entries, expected)

    def test_frozen_sha_mutation_fails(self) -> None:
        expected = deepcopy(self.contract["raw_members"]["target.json"])
        expected["sha256"] = "0" * 64
        with self.assertRaises(Zip64Error):
            extract_member(self.reader, self.entries, expected)

    def test_local_signature_mutation_fails(self) -> None:
        value = bytearray(self.archive)
        value[0:4] = b"NOPE"
        reader = MemoryRangeReader(bytes(value), maximum_request=len(value))
        with self.assertRaises(Zip64Error):
            extract_member(reader, self.entries, self.contract["raw_members"]["target.json"])

    def test_compressed_payload_mutation_fails(self) -> None:
        entry = self.entries["target.json"]
        name_length = len("target.json".encode())
        payload_start = entry.local_header_offset + 30 + name_length
        value = bytearray(self.archive)
        value[payload_start] ^= 1
        reader = MemoryRangeReader(bytes(value), maximum_request=len(value))
        with self.assertRaises(Zip64Error):
            extract_member(reader, self.entries, self.contract["raw_members"]["target.json"])


if __name__ == "__main__":
    unittest.main()

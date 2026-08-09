from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from eu2614.errors import VerificationError
from eu2614.hashing import open_verified


def _identity(payload: bytes) -> dict[str, object]:
    return {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "md5": hashlib.md5(payload, usedforsecurity=False).hexdigest(),
    }


class DescriptorSecurityTests(unittest.TestCase):
    def test_unchanged_retained_descriptor_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.bin"
            payload = b"immutable-input"
            path.write_bytes(payload)
            with open_verified(path, _identity(payload), label="test input") as verified:
                self.assertEqual(verified.stream.read(), payload)

    def test_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.bin"
            link = root / "link.bin"
            payload = b"target"
            target.write_bytes(payload)
            link.symlink_to(target)
            with self.assertRaises(VerificationError):
                with open_verified(link, _identity(payload), label="symlink"):
                    pass

    def test_path_replacement_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "input.bin"
            replacement = root / "replacement.bin"
            payload = b"original"
            path.write_bytes(payload)
            replacement.write_bytes(b"malicious")
            with self.assertRaises(VerificationError):
                with open_verified(path, _identity(payload), label="replace target") as verified:
                    self.assertEqual(verified.stream.read(), payload)
                    os.replace(replacement, path)

    def test_in_place_mutation_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.bin"
            payload = b"original"
            path.write_bytes(payload)
            with self.assertRaises(VerificationError):
                with open_verified(path, _identity(payload), label="mutable target") as verified:
                    self.assertEqual(verified.stream.read(), payload)
                    path.write_bytes(b"modified")


if __name__ == "__main__":
    unittest.main()

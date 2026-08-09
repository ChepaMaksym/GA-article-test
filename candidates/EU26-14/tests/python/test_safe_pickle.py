from __future__ import annotations

import struct
import unittest
from pathlib import Path

from eu2614.errors import VerificationError
from eu2614.safe_pickle import ArrayValue, parse_numpy_pickle


def _short(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if len(encoded) > 255:
        raise ValueError("test string is too long")
    return b"\x8c" + bytes([len(encoded)]) + encoded


def _binint(value: int) -> bytes:
    return b"J" + struct.pack("<i", value)


def safe_array_pickle(value: int = 7) -> bytes:
    data = struct.pack("<q", value)
    return b"".join(
        [
            b"\x80\x05",
            _short("numpy._core.numeric"),
            _short("_frombuffer"),
            b"\x93",
            b"(",
            b"\x96" + struct.pack("<Q", len(data)) + data,
            _short("numpy"),
            _short("dtype"),
            b"\x93",
            _short("i8"),
            b"\x89\x88\x87R",
            b"(K\x03" + _short("<") + b"NNN" + _binint(-1) + _binint(-1) + b"K\x00tb",
            b"K\x01\x85",
            _short("C"),
            b"tR.",
        ]
    )


class SafePickleTests(unittest.TestCase):
    def test_static_dtype_and_frombuffer_forms_are_decoded(self) -> None:
        parsed = parse_numpy_pickle(safe_array_pickle(23))
        self.assertIsInstance(parsed.value, ArrayValue)
        self.assertEqual(parsed.value.dtype, "i8")
        self.assertEqual(parsed.value.shape, (1,))
        self.assertEqual(parsed.value.values, (23,))
        self.assertEqual(
            parsed.symbolic_globals,
            ("numpy._core.numeric._frombuffer", "numpy.dtype"),
        )

    def test_unexpected_global_is_rejected_without_execution(self) -> None:
        payload = safe_array_pickle().replace(
            _short("numpy._core.numeric") + _short("_frombuffer"),
            _short("posix") + _short("system"),
            1,
        )
        with self.assertRaises(VerificationError):
            parse_numpy_pickle(payload)

    def test_wrong_reduce_arguments_are_rejected(self) -> None:
        payload = safe_array_pickle().replace(_short("i8"), _short("u8"), 1)
        with self.assertRaises(VerificationError):
            parse_numpy_pickle(payload)

    def test_wrong_dtype_build_is_rejected(self) -> None:
        payload = safe_array_pickle().replace(_short("<") + b"NNN", _short(">") + b"NNN", 1)
        with self.assertRaises(VerificationError):
            parse_numpy_pickle(payload)

    def test_dtype_build_rejects_float_version(self) -> None:
        payload = safe_array_pickle().replace(
            b"(K\x03" + _short("<"),
            b"(G" + struct.pack(">d", 3.0) + _short("<"),
            1,
        )
        with self.assertRaises(VerificationError):
            parse_numpy_pickle(payload)

    def test_dtype_build_rejects_boolean_flag(self) -> None:
        payload = safe_array_pickle().replace(b"K\x00tb", b"\x89tb", 1)
        with self.assertRaises(VerificationError):
            parse_numpy_pickle(payload)

    def test_object_construction_opcode_is_rejected(self) -> None:
        payload = safe_array_pickle()[:-1] + b"\x81."
        with self.assertRaises(VerificationError):
            parse_numpy_pickle(payload)

    def test_trailing_bytes_are_rejected(self) -> None:
        with self.assertRaises(VerificationError):
            parse_numpy_pickle(safe_array_pickle() + b"trailing")

    def test_general_unpickling_calls_are_absent(self) -> None:
        source = (
            Path(__file__).resolve().parents[2]
            / "environments"
            / "python"
            / "eu2614"
            / "safe_pickle.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("pickle.loads", "pickle.load(", "Unpickler(", "find_class"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
import os
from pathlib import Path
from unittest import mock

from eu2613.errors import VerificationError
from eu2613.safe_paths import safe_read_bytes, safe_write_text_once


class SafePathTests(unittest.TestCase):
    def test_read_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.bin"
            path.write_bytes(b"evidence")
            self.assertEqual(safe_read_bytes(path, stage="TEST", maximum_bytes=8), b"evidence")

    def test_write_nested_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "new" / "report.json"
            safe_write_text_once(path, "{}\n", stage="TEST")
            self.assertEqual(path.read_text(encoding="utf-8"), "{}\n")

    def test_mutation_input_final_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.bin"
            target.write_bytes(b"evidence")
            link = root / "input.bin"
            link.symlink_to(target)
            with self.assertRaises(VerificationError):
                safe_read_bytes(link, stage="TEST", maximum_bytes=100)

    def test_mutation_input_ancestor_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real"
            real.mkdir()
            (real / "input.bin").write_bytes(b"evidence")
            link = root / "linked"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(VerificationError):
                safe_read_bytes(link / "input.bin", stage="TEST", maximum_bytes=100)

    def test_mutation_input_size_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.bin"
            path.write_bytes(b"too-large")
            with self.assertRaises(VerificationError):
                safe_read_bytes(path, stage="TEST", maximum_bytes=8)

    def test_mutation_input_fifo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.fifo"
            os.mkfifo(path)
            with self.assertRaises(VerificationError):
                safe_read_bytes(path, stage="TEST", maximum_bytes=100)

    def test_mutation_input_fifo_replacement_during_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.bin"
            path.write_bytes(b"evidence")
            real_open = os.open
            replaced = False

            def replace_leaf_with_fifo(target, flags, mode=0o777, *, dir_fd=None):
                nonlocal replaced
                if (
                    not replaced
                    and target == path.name
                    and dir_fd is not None
                    and flags & os.O_NONBLOCK
                ):
                    replaced = True
                    path.unlink()
                    os.mkfifo(path)
                return real_open(target, flags, mode, dir_fd=dir_fd)

            with mock.patch("eu2613.safe_paths.os.open", side_effect=replace_leaf_with_fifo):
                with self.assertRaises(VerificationError):
                    safe_read_bytes(path, stage="TEST", maximum_bytes=100)
            self.assertTrue(path.is_fifo())

    def test_mutation_input_device(self) -> None:
        with self.assertRaises(VerificationError):
            safe_read_bytes("/dev/null", stage="TEST", maximum_bytes=100)

    def test_mutation_output_final_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.json"
            target.write_text("original\n", encoding="utf-8")
            link = root / "report.json"
            link.symlink_to(target)
            with self.assertRaises(VerificationError):
                safe_write_text_once(link, "mutated\n", stage="TEST")
            self.assertEqual(target.read_text(encoding="utf-8"), "original\n")

    def test_mutation_output_ancestor_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real"
            real.mkdir()
            link = root / "linked"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(VerificationError):
                safe_write_text_once(link / "report.json", "{}\n", stage="TEST")
            self.assertFalse((real / "report.json").exists())

    def test_mutation_parent_component(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "child" / ".." / "report.json"
            with self.assertRaises(VerificationError):
                safe_write_text_once(path, "{}\n", stage="TEST")

    def test_mutation_output_parent_replacement_during_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            retained = root / "retained"
            moved = root / "moved"
            retained.mkdir()
            output = retained / "report.json"
            real_fsync = __import__("os").fsync
            replaced = False

            def replace_parent(file_descriptor):
                nonlocal replaced
                if not replaced:
                    replaced = True
                    retained.rename(moved)
                    retained.mkdir()
                return real_fsync(file_descriptor)

            with mock.patch("eu2613.safe_paths.os.fsync", side_effect=replace_parent):
                with self.assertRaises(VerificationError):
                    safe_write_text_once(output, "{}\n", stage="TEST")
            self.assertFalse(output.exists())
            self.assertFalse((moved / "report.json").exists())

    def test_mutation_output_leaf_replacement_during_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            real_fsync = __import__("os").fsync
            replaced = False

            def replace_leaf(file_descriptor):
                nonlocal replaced
                if not replaced:
                    replaced = True
                    output.unlink()
                    output.write_text("replacement\n", encoding="utf-8")
                return real_fsync(file_descriptor)

            with mock.patch("eu2613.safe_paths.os.fsync", side_effect=replace_leaf):
                with self.assertRaises(VerificationError):
                    safe_write_text_once(output, "{}\n", stage="TEST")
            self.assertEqual(output.read_text(encoding="utf-8"), "replacement\n")

    def test_mutation_output_leaf_fifo_replacement_during_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            real_fsync = os.fsync
            replaced = False

            def replace_leaf_with_fifo(file_descriptor):
                nonlocal replaced
                if not replaced:
                    replaced = True
                    output.unlink()
                    os.mkfifo(output)
                return real_fsync(file_descriptor)

            with mock.patch("eu2613.safe_paths.os.fsync", side_effect=replace_leaf_with_fifo):
                with self.assertRaises(VerificationError):
                    safe_write_text_once(output, "{}\n", stage="TEST")
            self.assertTrue(output.is_fifo())


if __name__ == "__main__":
    unittest.main()

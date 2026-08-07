from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import os
import sys
import tarfile
import tempfile
from types import MappingProxyType
import unittest
from pathlib import Path
from unittest import mock

import aheadverify.archive as archive_module
import aheadverify.witness as witness_module


CANDIDATE = Path(__file__).resolve().parents[2]
PYTHON_ENV = CANDIDATE / "environments" / "python"


class _ReadCallback:
    """Delegate a binary file while injecting one callback at source EOF."""

    def __init__(self, handle, callback):
        self._handle = handle
        self._callback = callback
        self._called = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._handle.__exit__(exc_type, exc_value, traceback)

    def __getattr__(self, name):
        return getattr(self._handle, name)

    def read(self, size=-1):
        value = self._handle.read(size)
        if not value and not self._called:
            self._called = True
            self._callback()
        return value


class _FirstReadCallback(_ReadCallback):
    """Delegate a binary file while injecting one callback after its first read."""

    def read(self, size=-1):
        value = self._handle.read(size)
        if value and not self._called:
            self._called = True
            self._callback()
        return value


class _WriteCallback:
    """Delegate a binary file while injecting one callback on its first write."""

    def __init__(self, handle, callback):
        self._handle = handle
        self._callback = callback
        self._called = False

    def __getattr__(self, name):
        return getattr(self._handle, name)

    def write(self, value):
        result = self._handle.write(value)
        if value and not self._called:
            self._called = True
            self._callback()
        return result


def _add_member(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(payload)
    member.mtime = 0
    archive.addfile(member, io.BytesIO(payload))


def _marker_archive(path: Path, marker: bytes) -> None:
    with tarfile.open(path, "w:gz") as archive:
        _add_member(archive, "marker.txt", marker)


def _read_marker(tar_snapshot) -> bytes:
    tar_snapshot.seek(0)
    with tarfile.open(fileobj=tar_snapshot, mode="r:") as archive:
        handle = archive.extractfile("marker.txt")
        if handle is None:
            raise AssertionError("marker member is unreadable")
        return handle.read()


def _load_cli(module_name: str, filename: str):
    path = PYTHON_ENV / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strict_dimacs_bytes() -> bytes:
    edges: list[tuple[int, int]] = []
    for left in range(1, 236):
        for right in range(left + 1, 236):
            edges.append((left, right))
            if len(edges) == 13_968:
                lines = ["p edge 235 13968"]
                lines.extend(f"e {first} {second}" for first, second in edges)
                return ("\n".join(lines) + "\n").encode("utf-8")
    raise AssertionError("cannot construct the frozen DIMACS dimensions")


class AuthenticatedArchiveAccessTests(unittest.TestCase):
    def _patched_source_open(self, source_path: Path, callback):
        original_open = Path.open
        opened = {"count": 0}

        def dispatch(path, *args, **kwargs):
            handle = original_open(path, *args, **kwargs)
            mode = args[0] if args else kwargs.get("mode", "r")
            if Path(path).resolve() == source_path.resolve() and mode == "rb":
                opened["count"] += 1
                if opened["count"] > 1:
                    handle.close()
                    raise AssertionError("authenticated source path was reopened")
                return _ReadCallback(handle, callback)
            return handle

        return mock.patch.object(Path, "open", new=dispatch), opened

    def test_atomic_replacement_at_snapshot_boundary_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.tgz"
            replacement = root / "replacement.tgz"
            _marker_archive(source, b"AUTHENTICATED")
            _marker_archive(replacement, b"REPLACEMENT")
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            expected_bytes = source.stat().st_size
            replacement_digest = hashlib.sha256(replacement.read_bytes()).hexdigest()
            injected = {"called": False}

            def replace_source() -> None:
                injected["called"] = True
                os.replace(replacement, source)

            patcher, opened = self._patched_source_open(source, replace_source)
            with tempfile.TemporaryFile(mode="w+b") as tar_snapshot, patcher:
                with self.assertRaises(archive_module.ArchiveValidationError):
                    archive_module.materialize_authenticated_archive(
                        source, tar_snapshot, expected, expected_bytes
                    )

            self.assertTrue(injected["called"])
            self.assertEqual(opened["count"], 1)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), replacement_digest)

    def test_atomic_swap_back_never_selects_replacement_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.tgz"
            replacement = root / "replacement.tgz"
            restore_link = root / "restore-link.tgz"
            _marker_archive(source, b"AUTHENTICATED")
            _marker_archive(replacement, b"REPLACEMENT")
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            expected_bytes = source.stat().st_size
            state = {"swapped": False, "restored": False}

            def replace_source() -> None:
                os.link(source, restore_link)
                os.replace(replacement, source)
                state["swapped"] = True

            def restore_source() -> None:
                os.replace(restore_link, source)
                state["restored"] = True

            patcher, opened = self._patched_source_open(source, replace_source)
            with tempfile.TemporaryFile(mode="w+b") as raw_tar:
                tar_snapshot = _WriteCallback(raw_tar, restore_source)
                try:
                    with patcher:
                        archive_module.materialize_authenticated_archive(
                            source, tar_snapshot, expected, expected_bytes
                        )
                except archive_module.ArchiveValidationError:
                    # Rejecting a detected swap is also fail-closed.  A success,
                    # however, must be based exclusively on the authenticated bytes.
                    pass
                else:
                    self.assertTrue(state["restored"])
                    self.assertEqual(_read_marker(raw_tar), b"AUTHENTICATED")

                raw_tar.seek(0, os.SEEK_END)
                if raw_tar.tell():
                    self.assertEqual(_read_marker(raw_tar), b"AUTHENTICATED")

            self.assertTrue(state["swapped"])
            self.assertTrue(state["restored"])
            self.assertEqual(opened["count"], 1)

    def test_same_inode_mutation_during_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.tgz"
            _marker_archive(source, b"AUTHENTICATED")
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            expected_bytes = source.stat().st_size

            def mutate_source() -> None:
                descriptor = os.open(source, os.O_RDWR)
                try:
                    original = os.pread(descriptor, 1, 0)
                    replacement = b"\x00" if original != b"\x00" else b"\x01"
                    os.pwrite(descriptor, replacement, 0)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)

            patcher, opened = self._patched_source_open(source, mutate_source)
            with tempfile.TemporaryFile(mode="w+b") as tar_snapshot, patcher:
                with self.assertRaisesRegex(
                    archive_module.ArchiveValidationError,
                    "changed during authentication",
                ):
                    archive_module.materialize_authenticated_archive(
                        source, tar_snapshot, expected, expected_bytes
                    )
            self.assertEqual(opened["count"], 1)

    def test_post_parse_tar_mutation_is_rejected(self):
        verifier = archive_module.verify_authenticated_tar_snapshot
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.tgz"
            _marker_archive(source, b"AUTHENTICATED")
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            with tempfile.TemporaryFile(mode="w+b") as tar_snapshot:
                identity = archive_module.materialize_authenticated_archive(
                    source, tar_snapshot, expected, source.stat().st_size
                )
                self.assertEqual(_read_marker(tar_snapshot), b"AUTHENTICATED")
                tar_snapshot.seek(0)
                original = tar_snapshot.read(1)
                tar_snapshot.seek(0)
                tar_snapshot.write(b"\x00" if original != b"\x00" else b"\x01")
                tar_snapshot.flush()
                with self.assertRaises(archive_module.ArchiveValidationError):
                    verifier(tar_snapshot, identity)

    def test_dimacs_parser_uses_one_opened_byte_sequence(self):
        raw_graph = _strict_dimacs_bytes()
        expected = hashlib.sha256(raw_graph).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            graph_path = Path(directory) / "graph.col"
            graph_path.write_bytes(raw_graph)
            original_open = Path.open
            opened = {"count": 0}

            def dispatch(path, *args, **kwargs):
                handle = original_open(path, *args, **kwargs)
                mode = args[0] if args else kwargs.get("mode", "r")
                if Path(path).resolve() == graph_path.resolve() and mode == "rb":
                    opened["count"] += 1
                    if opened["count"] > 1:
                        handle.close()
                        raise AssertionError("DIMACS input path was reopened")
                return handle

            with mock.patch.object(witness_module, "GRAPH_SHA256", expected), mock.patch.object(
                witness_module, "GRAPH_BYTES", len(raw_graph)
            ), mock.patch.object(Path, "open", new=dispatch), mock.patch.object(
                Path,
                "read_text",
                side_effect=AssertionError("DIMACS path was read again as text"),
            ):
                result = witness_module.parse_dimacs_graph(graph_path)

        self.assertEqual(opened["count"], 1)
        self.assertEqual(result["vertices"], 235)
        self.assertEqual(result["declared_edges"], 13_968)
        self.assertEqual(result["sha256"], expected)

    def test_hardware_worker_receives_identity_not_a_path(self):
        runner = _load_cli(
            "eu2602_hardware_payload_contract",
            "../../tests/hardware/run_portability_suite.py",
        )
        previous = runner._ARCHIVE_MEMBER_PAYLOADS
        payloads = (("root/deleter/r250.5_0_66.csv", b"immutable"),)
        runner._ARCHIVE_MEMBER_PAYLOADS = MappingProxyType({"r250.5": payloads})
        try:
            with mock.patch.object(
                archive_module,
                "validate_instance_payloads",
                return_value={"instance": "r250.5", "status": "synthetic"},
            ) as validator:
                result = runner._archive_case(
                    ("r250.5", "artifact_actual_10800")
                )
        finally:
            runner._ARCHIVE_MEMBER_PAYLOADS = previous

        validator.assert_called_once_with(
            payloads, "r250.5", "artifact_actual_10800"
        )
        self.assertEqual(result["instance"], "r250.5")

    def test_dimacs_atomic_replacement_is_detected_on_the_retained_handle(self):
        raw_graph = _strict_dimacs_bytes()
        expected = hashlib.sha256(raw_graph).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_path = root / "graph.col"
            replacement = root / "replacement.col"
            graph_path.write_bytes(raw_graph)
            replacement.write_text("p edge 2 1\ne 1 2\n", encoding="utf-8")
            original_open = Path.open
            opened = {"count": 0}
            injected = {"called": False}

            def replace_graph() -> None:
                injected["called"] = True
                os.replace(replacement, graph_path)

            def dispatch(path, *args, **kwargs):
                handle = original_open(path, *args, **kwargs)
                mode = args[0] if args else kwargs.get("mode", "r")
                if Path(path).resolve() == graph_path.resolve() and mode == "rb":
                    opened["count"] += 1
                    if opened["count"] > 1:
                        handle.close()
                        raise AssertionError("DIMACS input path was reopened")
                    return _FirstReadCallback(handle, replace_graph)
                return handle

            with mock.patch.object(witness_module, "GRAPH_SHA256", expected), mock.patch.object(
                witness_module, "GRAPH_BYTES", len(raw_graph)
            ), mock.patch.object(Path, "open", new=dispatch):
                with self.assertRaisesRegex(
                    witness_module.WitnessValidationError, "changed during authentication"
                ):
                    witness_module.parse_dimacs_graph(graph_path)

        self.assertTrue(injected["called"])
        self.assertEqual(opened["count"], 1)


class ValidationCliAtomicOutputTests(unittest.TestCase):
    def test_archive_cli_leaves_existing_output_unchanged_on_failure(self):
        cli = _load_cli("eu2602_archive_cli_failure", "run_archive_validation.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "invalid.tgz"
            output = root / "report.json"
            archive.write_bytes(b"not a gzip archive")
            sentinel = b"EXISTING ARCHIVE REPORT\n"
            output.write_bytes(sentinel)
            argv = [
                str(PYTHON_ENV / "run_archive_validation.py"),
                "--archive",
                str(archive),
                "--output",
                str(output),
            ]
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                status = cli.main()
            self.assertEqual(status, 2)
            self.assertEqual(output.read_bytes(), sentinel)

    def test_witness_cli_leaves_existing_output_unchanged_on_failure(self):
        cli = _load_cli("eu2602_witness_cli_failure", "run_selected_witness.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "invalid.tgz"
            graph = root / "invalid.col"
            output = root / "report.json"
            archive.write_bytes(b"not a gzip archive")
            graph.write_text("p edge 2 1\ne 1 2\n", encoding="utf-8")
            sentinel = b"EXISTING WITNESS REPORT\n"
            output.write_bytes(sentinel)
            argv = [
                str(PYTHON_ENV / "run_selected_witness.py"),
                "--archive",
                str(archive),
                "--graph",
                str(graph),
                "--output",
                str(output),
            ]
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                status = cli.main()
            self.assertEqual(status, 2)
            self.assertEqual(output.read_bytes(), sentinel)
if __name__ == "__main__":
    unittest.main()

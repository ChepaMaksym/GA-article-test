"""Source/runtime binding helpers for independent micro-oracle reports."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
from typing import Iterable


def git_head(repository: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def python_implementation_paths(candidate: Path) -> list[Path]:
    paths = {
        path
        for path in (candidate / "environments" / "python").rglob("*.py")
        if "__pycache__" not in path.parts
    }
    paths.add(candidate / "tests" / "compare_fixture_reports.py")
    return sorted(paths)


def matlab_implementation_paths(candidate: Path) -> list[Path]:
    paths = set((candidate / "environments" / "matlab").glob("*.m"))
    paths.update((candidate / "tests" / "matlab").glob("*.m"))
    return sorted(paths)


def source_hash_rows(paths: Iterable[Path], repository: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(paths):
        if not path.is_file():
            raise ValueError(f"implementation source is missing: {path}")
        rows.append(
            {
                "path": path.resolve().relative_to(repository.resolve()).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return rows


def source_tsv_bytes(rows: list[dict[str, str]]) -> bytes:
    return "".join(
        f"{row['sha256']}\t{row['path']}\n" for row in sorted(rows, key=lambda item: item["path"])
    ).encode("utf-8")


def source_digest(rows: list[dict[str, str]]) -> str:
    return hashlib.sha256(source_tsv_bytes(rows)).hexdigest()


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _assert_no_symlink_ancestor(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    cursor = Path(absolute.anchor)
    for part in absolute.parent.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"output parent traverses a symbolic link: {cursor}")


def prepare_exclusive_outputs(
    paths: Iterable[Path], repository: Path, *, labels: Iterable[str] | None = None
) -> list[Path]:
    """Validate formal evidence destinations before any result is computed.

    Formal reports are deliberately external to the checkout. Existing files,
    symbolic-link traversal, and aliases between destinations all fail closed.
    """

    raw_paths = list(paths)
    output_labels = list(labels) if labels is not None else ["output"] * len(raw_paths)
    if len(output_labels) != len(raw_paths):
        raise ValueError("output labels and paths differ in length")
    repository_resolved = repository.resolve(strict=True)
    prepared: list[Path] = []
    for raw_path, label in zip(raw_paths, output_labels):
        if not isinstance(raw_path, Path):
            raise TypeError(f"{label} must be a pathlib.Path")
        absolute = Path(os.path.abspath(raw_path))
        if absolute.name in {"", ".", ".."}:
            raise ValueError(f"{label} has no file name")
        _assert_no_symlink_ancestor(absolute)
        absolute.parent.mkdir(parents=True, exist_ok=True)
        _assert_no_symlink_ancestor(absolute)
        parent = absolute.parent.resolve(strict=True)
        resolved = parent / absolute.name
        if _is_within(resolved, repository_resolved):
            raise ValueError(f"{label} must be outside the repository")
        if resolved.exists() or resolved.is_symlink():
            raise ValueError(f"{label} already exists; evidence writes are exclusive")
        prepared.append(resolved)
    if len(set(prepared)) != len(prepared):
        raise ValueError("formal evidence destinations must be distinct")
    return prepared


def exclusive_write_bytes(path: Path, payload: bytes) -> None:
    """Create one evidence file without following/replacing the final path."""

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    parent_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        parent_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        parent_flags |= os.O_NOFOLLOW
    parent_descriptor = os.open(path.parent, parent_flags)
    try:
        descriptor = os.open(path.name, flags, 0o644, dir_fd=parent_descriptor)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(descriptor)
    finally:
        os.close(parent_descriptor)


def exclusive_write_text(path: Path, payload: str) -> None:
    exclusive_write_bytes(path, payload.encode("utf-8"))

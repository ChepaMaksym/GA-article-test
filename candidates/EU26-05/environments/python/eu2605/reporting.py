"""Source/runtime binding helpers for independent micro-oracle reports."""

from __future__ import annotations

import hashlib
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

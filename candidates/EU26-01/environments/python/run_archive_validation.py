#!/usr/bin/env python3
"""Validate the exact pinned EU26-01 Zenodo member and Table 1 statistics."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
REPOSITORY = CANDIDATE.parents[1]
sys.path.insert(0, str(SCRIPT.parent))

from tworateverify.archive import ArchiveSpec, ArchiveValidationError, validate_archive


def _outside_repository(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPOSITORY.resolve())
    except ValueError:
        return resolved
    raise argparse.ArgumentTypeError("formal outputs must be written outside the repository")


def _write_new(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=_outside_repository)
    arguments = parser.parse_args()
    spec = ArchiveSpec.from_protocol(CANDIDATE / "config" / "frozen_protocol.json")
    try:
        report = validate_archive(arguments.archive, spec)
        _write_new(arguments.output, report)
    except (ArchiveValidationError, OSError) as error:
        print(f"EU26-01 archive validation failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps({
        "archive_status": report["archive_status"],
        "paper_level_status": report["paper_level_status"],
        "mean_exact": report["statistics"]["mean_exact"],
        "population_variance_exact": report["statistics"]["population_variance_exact"],
        "report_sha256": report["report_sha256"],
    }, sort_keys=True))
    return 0 if report["archive_status"] == "PASS_ARCHIVE_EXACT" else 1


if __name__ == "__main__":
    raise SystemExit(main())

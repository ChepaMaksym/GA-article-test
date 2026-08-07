#!/usr/bin/env python3
"""Validate the pinned r250.5 archive transition and legal coloring."""

from __future__ import annotations

import argparse
import json
import os
import tarfile
import tempfile
from pathlib import Path

from aheadverify.witness import WitnessValidationError, validate_selected_witness


def _write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, allow_nan=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.resolve() in {args.archive.resolve(), args.graph.resolve()}:
        parser.error("--output must not overwrite --archive or --graph")
    try:
        report = validate_selected_witness(args.archive, args.graph)
    except (WitnessValidationError, OSError, tarfile.TarError, UnicodeError) as error:
        print(f"SELECTED WITNESS ERROR: {error}")
        return 2
    _write_atomic(args.output.resolve(), report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "paper_level_status": report["paper_level_status"],
                "legal_coloring": report["legal_coloring"]["legal"],
                "report": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

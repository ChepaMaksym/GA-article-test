#!/usr/bin/env python3
"""Run the frozen P1 replay and P2 diagnostic against an upstream archive."""

from __future__ import annotations

import argparse
import json
import os
import tarfile
import tempfile
from pathlib import Path

from aheadverify.archive import ArchiveValidationError, validate_archive
from aheadverify.canonical import canonical_sha256


def _atomic_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
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
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.archive.resolve() == args.output.resolve():
        parser.error("--output must not overwrite --archive")

    try:
        p1 = validate_archive(args.archive, "artifact_actual_10800")
        p2 = validate_archive(args.archive, "paper_claimed_3600_diagnostic")
    except (ArchiveValidationError, OSError, tarfile.TarError, UnicodeError) as error:
        print(f"ARCHIVE VALIDATION ERROR: {error}")
        return 2

    report = {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-02",
        "artifact_actual_10800": p1,
        "paper_claimed_3600_diagnostic": p2,
        "archive_gate": p1["status"],
        "paper_level_status": "BLOCKED_MULTIPLE_SOURCE_CONFLICTS",
        "allowed_claim": (
            "exact table-artifact provenance only; not a paper-faithful solver run"
        ),
    }
    report["report_digest"] = canonical_sha256(
        report, domain="EU26-02-ARCHIVE-REPORT-V1"
    )
    _atomic_write(args.output.resolve(), report)
    print(
        json.dumps(
            {
                "archive_gate": report["archive_gate"],
                "paper_level_status": report["paper_level_status"],
                "p1_digest": p1["canonical_result_digest"],
                "p2_retained_runs": p2["total_retained_runs"],
                "report": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0 if p1["status"] == "PASS_ARCHIVE_EXACT" else 1


if __name__ == "__main__":
    raise SystemExit(main())

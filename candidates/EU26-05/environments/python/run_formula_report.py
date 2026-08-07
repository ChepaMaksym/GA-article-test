#!/usr/bin/env python3
"""Emit the canonical outcome-blind EU26-05 shared-fixture report."""

from __future__ import annotations

import argparse
import platform
from pathlib import Path
import sys


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
sys.path.insert(0, str(SCRIPT.parent))

from eu2605.canonical import canonical_bytes, sha256_value, strict_json_load  # noqa: E402
from eu2605.core import (  # noqa: E402
    H0_SOURCE_STATUS,
    SOURCE_BYTE_STATUS,
    SOURCE_FREEZE_STATUS,
    fixture_report,
)
from eu2605.reporting import (  # noqa: E402
    git_head,
    python_implementation_paths,
    source_digest,
    source_hash_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=CANDIDATE / "fixtures" / "formula_transition_cases.json",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    fixture = strict_json_load(args.fixture)
    semantic_payload = fixture_report(fixture)
    digest = sha256_value(semantic_payload)
    rows = source_hash_rows(python_implementation_paths(CANDIDATE), CANDIDATE.parents[1])
    report = {
        "schema_version": "1.0.0",
        "report_kind": "EU26-05-INDEPENDENT-FIXTURE-v1",
        "implementation": "python",
        "git_head": git_head(CANDIDATE.parents[1]),
        "runtime": {
            "engine": "python",
            "version": platform.python_version(),
            "platform": platform.platform(),
        },
        "implementation_source_hashes": rows,
        "implementation_source_digest": source_digest(rows),
        "h0_source_status": H0_SOURCE_STATUS,
        "source_byte_status": SOURCE_BYTE_STATUS,
        "source_freeze_status": SOURCE_FREEZE_STATUS,
        "semantic_payload": semantic_payload,
        "semantic_payload_sha256": digest,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(report) + b"\n")


if __name__ == "__main__":
    main()

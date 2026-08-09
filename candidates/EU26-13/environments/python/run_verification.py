#!/usr/bin/env python3
"""Run the frozen EU26-13 targeted-artifact verifier."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eu2613.artifact import verify_artifact
from eu2613.contract import DEFAULT_CONTRACT, load_contract
from eu2613.errors import VerificationError
from eu2613.report import write_json_once


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--metadata", type=Path, help="already-downloaded exact Zenodo record JSON")
    parser.add_argument("--code-archive", type=Path, help="already-downloaded exact repelling_code.zip")
    parser.add_argument("--python-attestation", type=Path, required=True)
    parser.add_argument("--octave-attestation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_optional(path: Path | None) -> bytes | None:
    if path is None:
        return None
    return path.read_bytes()


def main() -> int:
    args = parse_args()
    try:
        if args.output.exists() or args.output.is_symlink():
            raise VerificationError("REPORT", f"refusing to overwrite {args.output}")
        contract = load_contract(args.contract)
        report = verify_artifact(
            contract,
            metadata_bytes=read_optional(args.metadata),
            code_archive_bytes=read_optional(args.code_archive),
            python_attestation=args.python_attestation,
            octave_attestation=args.octave_attestation,
        )
        write_json_once(args.output, report)
    except (OSError, VerificationError) as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": report["overall_status"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

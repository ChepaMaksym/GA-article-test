#!/usr/bin/env python3
"""Verify local, complete EU26-14 Zenodo inputs and write one report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PYTHON_ENV = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_ENV))

from eu2614.canonical import bind_report, write_new_json  # noqa: E402
from eu2614.pipeline import verify_artifacts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-json", required=True, type=Path)
    parser.add_argument("--checksum-manifest", required=True, type=Path)
    parser.add_argument("--source-archive", required=True, type=Path)
    parser.add_argument("--result-archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output must be a new path")
    report = verify_artifacts(
        record_json=args.record_json,
        checksum_manifest=args.checksum_manifest,
        source_archive=args.source_archive,
        result_archive=args.result_archive,
    )
    bound = bind_report(report, domain=b"EU26-14-ARTIFACT-REPORT-V1")
    write_new_json(args.output, bound)
    print(
        f"{bound['overall_gate']}: seed=0 "
        f"nfev_total={bound['frozen_endpoint']['nfev_total']} "
        f"status={bound['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fetch only bounded ranges and verify the frozen EU26-12 artifact."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PYTHON_ENV = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_ENV))

from eu2612.canonical import bind_report, write_new_json  # noqa: E402
from eu2612.contract import load_contract  # noqa: E402
from eu2612.http_range import HttpRangeReader, fetch_small_https  # noqa: E402
from eu2612.pipeline import verify_artifact_inputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output must be a new path")
    if not 1.0 <= args.timeout <= 300.0:
        parser.error("--timeout must be between 1 and 300 seconds")

    contract = load_contract()
    files = contract["zenodo_files"]
    record = fetch_small_https(
        contract["zenodo"]["record_url"], maximum_bytes=2_000_000, timeout=args.timeout
    )
    code = fetch_small_https(
        files["ModDE.zip"]["url"], maximum_bytes=100_000, timeout=args.timeout
    )
    runner = fetch_small_https(
        files["Common_DE_runner.py"]["url"], maximum_bytes=20_000, timeout=args.timeout
    )
    raw_reader = HttpRangeReader(
        files["raw_data.zip"]["url"],
        size=files["raw_data.zip"]["bytes"],
        maximum_request=contract["verification_execution"]["maximum_raw_archive_bytes_per_request"],
        timeout=args.timeout,
    )
    report = verify_artifact_inputs(
        contract=contract,
        zenodo_record=record,
        code_archive=code,
        runner=runner,
        raw_reader=raw_reader,
    )
    report["range_transport"] = {
        "request_count": raw_reader.request_count,
        "bytes_received": raw_reader.bytes_received,
        "maximum_request": raw_reader.maximum_request,
        "full_archive_downloaded": False,
    }
    bound = bind_report(report, domain=b"EU26-12-ARTIFACT-REPORT-V1")
    write_new_json(args.output, bound)
    endpoint = bound["endpoint"]
    print(
        f"{bound['artifact_gate']}: seed={endpoint['seed']} "
        f"evals={endpoint['logged_evaluations']} y={endpoint['best_y_decimal']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

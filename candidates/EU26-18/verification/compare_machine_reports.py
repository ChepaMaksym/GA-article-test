#!/usr/bin/env python3
"""Fail closed unless all CI machines produce one scientific digest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = sorted(args.root.rglob("machine-report.json"))
    if len(paths) != args.expected_count:
        raise SystemExit(
            f"expected {args.expected_count} reports, found {len(paths)}: {paths}"
        )
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    profiles = {report["profile"]["profile_id"] for report in reports}
    digests = {report["quantized_digest"] for report in reports}
    case_counts = {report["case_count"] for report in reports}
    seeds = {report["master_seed"] for report in reports}
    if profiles != {"eu26-18-clean-room-kernel-v1"}:
        raise SystemExit(f"profile mismatch: {profiles}")
    if len(digests) != 1:
        raise SystemExit(f"cross-machine quantized digest mismatch: {digests}")
    if case_counts != {96} or seeds != {20260810}:
        raise SystemExit(
            f"probe contract mismatch: case_counts={case_counts}, seeds={seeds}"
        )
    if not all(report["exact_worker_invariance"] for report in reports):
        raise SystemExit("at least one machine failed exact worker invariance")
    systems = sorted(
        {
            (
                report["platform"]["system"],
                report["platform"]["machine"],
                report["platform"]["python_version"],
            )
            for report in reports
        }
    )
    if len({system for system, _, _ in systems}) < 3:
        raise SystemExit(f"expected three operating-system families, got {systems}")
    print(f"EU26-18 cross-machine digest PASS: {digests.pop()}")
    for system in systems:
        print(" - ", "/".join(system))


if __name__ == "__main__":
    main()

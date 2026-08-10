#!/usr/bin/env python3
"""Generate one machine/worker verification report for EU26-18."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reference_sa_plm import build_machine_report


HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "verification_contract.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", nargs="+", type=int, default=[1, 2, 4])
    parser.add_argument("--cases", type=int, default=96)
    parser.add_argument("--master-seed", type=int, default=20260810)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    report = build_machine_report(args.workers, args.cases, args.master_seed)
    expected = contract["determinism_probe"]["expected_quantized_digest"]
    if report["quantized_digest"] != expected:
        raise SystemExit(
            "quantized formula digest drifted: "
            f"expected {expected}, got {report['quantized_digest']}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(
        f"EU26-18 worker invariance PASS: workers={args.workers}, "
        f"cases={args.cases}, digest={report['quantized_digest']}"
    )


if __name__ == "__main__":
    main()

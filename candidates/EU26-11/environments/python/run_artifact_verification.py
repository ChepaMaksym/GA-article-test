#!/usr/bin/env python3
"""Verify the frozen EU26-11 Figure 1 endpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from eu2611.report import compose_report, load_json, write_new_json


CANDIDATE = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--point-set", type=Path, required=True)
    parser.add_argument("--numeric-block", type=Path, required=True)
    parser.add_argument("--source-checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = load_json(CANDIDATE / "config" / "verification_contract.json")
    report = compose_report(
        contract=contract,
        point_path=args.point_set.absolute(),
        numeric_path=args.numeric_block.absolute(),
        source_checkout=args.source_checkout.absolute(),
    )
    write_new_json(args.output.resolve(), report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

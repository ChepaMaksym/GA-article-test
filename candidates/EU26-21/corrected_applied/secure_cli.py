#!/usr/bin/env python3
"""Canonical CLI for strict secure corrected-profile aggregation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Mapping

from . import aggregate as base
from .secure_aggregate import (
    EXPECTED_ENVIRONMENT_PROFILE,
    RUNS,
    evaluate_secure,
)
from .secure_plots import plot_results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows_dir", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--plots-dir", type=Path, required=True)
    parser.add_argument(
        "--environment-profile",
        default=EXPECTED_ENVIRONMENT_PROFILE,
    )
    args = parser.parse_args()

    candidates = sorted(args.rows_dir.resolve().rglob("seed-*.json"))
    if len(candidates) != RUNS:
        raise SystemExit(
            "expected {0} secure rows, found {1}".format(
                RUNS, len(candidates)
            )
        )
    by_seed: Dict[int, Mapping[str, Any]] = {}
    for path in candidates:
        row = json.loads(path.read_text(encoding="utf-8"))
        seed = int(row.get("seed", -1))
        if seed in by_seed:
            raise SystemExit("duplicate secure row for seed {0}".format(seed))
        by_seed[seed] = row
    if sorted(by_seed) != list(range(1, RUNS + 1)):
        raise SystemExit("secure seed ledger is incomplete")
    rows = [by_seed[seed] for seed in range(1, RUNS + 1)]
    report = evaluate_secure(
        rows,
        environment_profile=args.environment_profile,
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    base._write_csv(rows, args.output_csv)
    plot_results(rows, report, args.plots_dir)

    print(
        json.dumps(
            {
                "claim_status": report["claim_status"],
                "secure_audit_status": report["secure_audit_status"],
                "h1_corrected": report["h1_corrected"],
                "h2_corrected": report["h2_corrected"],
                "h8_reset_ablation": report["h8_reset_ablation"],
                "secure_environment": report["secure_environment"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

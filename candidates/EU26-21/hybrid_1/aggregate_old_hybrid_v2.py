#!/usr/bin/env python3
"""Aggregate exactly thirty frozen v2 paired seed rows, fail closed.

Scientific hypothesis failure is preserved in the generated report.  The
process exits nonzero only for missing/corrupt rows, provenance/configuration
mismatch, invalid NFE accounting, or another protocol failure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hybrid_1.audit_validation import evaluate_strict, validate_row_strict
    from hybrid_1.paired_comparison import DEFAULT_TARGETS
    from hybrid_1.run_old_hybrid_comparison_v2 import RUNS
else:
    from .audit_validation import evaluate_strict, validate_row_strict
    from .paired_comparison import DEFAULT_TARGETS
    from .run_old_hybrid_comparison_v2 import RUNS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows_dir", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--enforce-protocol", action="store_true")
    args = parser.parse_args()

    candidates = sorted(args.rows_dir.resolve().rglob("seed-*.json"))
    if len(candidates) != RUNS:
        raise SystemExit(
            f"expected exactly {RUNS} seed artifacts, found {len(candidates)}"
        )

    by_seed: Dict[int, Dict[str, Any]] = {}
    for path in candidates:
        row = json.loads(path.read_text(encoding="utf-8"))
        seed = int(row.get("seed", -1))
        if seed in by_seed:
            raise SystemExit(f"duplicate row for seed {seed}")
        validate_row_strict(row, seed, DEFAULT_TARGETS)
        by_seed[seed] = row

    expected = list(range(1, RUNS + 1))
    if sorted(by_seed) != expected:
        raise SystemExit(
            f"seed ledger mismatch: got {sorted(by_seed)}, expected {expected}"
        )

    rows: List[Dict[str, Any]] = [by_seed[seed] for seed in expected]
    report = evaluate_strict(rows, tuple(DEFAULT_TARGETS))
    report["aggregation"] = {
        "implementation": "canonical_strict_v3",
        "seed_rows_regenerated": False,
        "first_hit_guard": "every positive objective-call index is valid",
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    primary = report["h3"]["target_reports"]["0.946000"]
    print(json.dumps({
        "claim_status": report["claim_status"],
        "audit_status": report["audit_status"],
        "protocol_gates": report["protocol_gates"],
        "audit_gates": report["audit_gates"],
        "h1_decision": report["h1"]["decision"],
        "h1_paired_difference": report["h1"]["paired_hybrid_minus_old"],
        "h2": report["h2"],
        "h3_primary_decision": report["h3"]["primary_decision"],
        "h3_primary": primary,
        "aggregation": report["aggregation"],
    }, sort_keys=True))

    if args.enforce_protocol:
        if report["claim_status"] != "PASS_PROTOCOL_RESULTS_AVAILABLE":
            raise SystemExit(1)
        if report["audit_status"] != "PASS_STRICT_REVALIDATION":
            raise SystemExit(1)


if __name__ == "__main__":
    main()

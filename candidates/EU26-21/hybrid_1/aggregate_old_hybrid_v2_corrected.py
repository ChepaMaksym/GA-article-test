#!/usr/bin/env python3
"""Aggregate the frozen 30 v2 rows with the corrected first-hit guard.

The seed artifacts are not regenerated. The only correction is that a first-hit
NFE in ``1..50`` is valid: it means one of the common initial population masks
reached the validation target. The original guard incorrectly required every
first hit to occur after all 50 initial masks had been evaluated.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hybrid_1.paired_comparison import DEFAULT_TARGETS
    import hybrid_1.run_old_hybrid_comparison_v2 as analysis
else:
    from .paired_comparison import DEFAULT_TARGETS
    from . import run_old_hybrid_comparison_v2 as analysis

RUNS = 30


def corrected_capped(value: Optional[int], budget: int) -> Tuple[int, bool]:
    """Censor at budget while accepting any positive first-hit NFE."""

    if value is None or int(value) > budget:
        return int(budget), False
    result = int(value)
    if result < 1:
        raise ValueError("first-hit NFE must be positive")
    return result, True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows_dir", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--enforce-protocol", action="store_true")
    args = parser.parse_args()

    # Patch only the erroneous analysis guard. Algorithms and row data remain
    # byte-for-byte unchanged.
    analysis._capped = corrected_capped

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
        analysis._validate_row(row, seed)
        by_seed[seed] = row
    expected = list(range(1, RUNS + 1))
    if sorted(by_seed) != expected:
        raise SystemExit(
            f"seed ledger mismatch: got {sorted(by_seed)}, expected {expected}"
        )

    rows: List[Dict[str, Any]] = [by_seed[seed] for seed in expected]
    report = analysis.evaluate(rows, tuple(DEFAULT_TARGETS))
    report["aggregation_correction"] = {
        "type": "analysis_guard_only",
        "original_seed_run_id": 31934321927,
        "seed_rows_regenerated": False,
        "correction": "allow positive first-hit NFE within initial population",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    primary = report["h3"]["target_reports"]["0.946000"]
    print(json.dumps({
        "claim_status": report["claim_status"],
        "protocol_gates": report["protocol_gates"],
        "h1_decision": report["h1"]["decision"],
        "h1_paired_difference": report["h1"]["paired_hybrid_minus_old"],
        "h2": report["h2"],
        "h3_primary_decision": report["h3"]["primary_decision"],
        "h3_primary": primary,
        "aggregation_correction": report["aggregation_correction"],
    }, sort_keys=True))
    if (
        args.enforce_protocol
        and report["claim_status"] != "PASS_PROTOCOL_RESULTS_AVAILABLE"
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run one frozen v2 OLD-versus-Hybrid paired Census seed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hybrid_1.paired_comparison import DEFAULT_ACTIVE_SAMPLE_SIZE, DEFAULT_TARGETS
    from hybrid_1.paired_comparison_v2 import run_paired_seed_v2
    from hybrid_1.run_old_hybrid_comparison_v2 import (
        H1_BUDGET,
        H3_BUDGET,
        INITIAL_POPULATION,
        RUNS,
        _validate_row,
    )
else:
    from .paired_comparison import DEFAULT_ACTIVE_SAMPLE_SIZE, DEFAULT_TARGETS
    from .paired_comparison_v2 import run_paired_seed_v2
    from .run_old_hybrid_comparison_v2 import (
        H1_BUDGET,
        H3_BUDGET,
        INITIAL_POPULATION,
        RUNS,
        _validate_row,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    if not 1 <= args.seed <= RUNS:
        raise SystemExit(f"seed must lie in 1..{RUNS}")
    row = run_paired_seed_v2(
        args.upstream.resolve(),
        seed=args.seed,
        active_sample_size=DEFAULT_ACTIVE_SAMPLE_SIZE,
        initial_population=INITIAL_POPULATION,
        h1_budget=H1_BUDGET,
        h3_budget=H3_BUDGET,
        h1_workers=4,
        targets=DEFAULT_TARGETS,
    )
    _validate_row(row, args.seed)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(row, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "seed": args.seed,
        "active_indices_sha256": row["active_indices_sha256"],
        "initial_masks_sha256": row["initial_masks_sha256"],
        "old_test_accuracy": row["old"]["test_accuracy"],
        "hybrid_test_accuracy": row["hybrid_h1"]["test_accuracy"],
        "old_optimizer_nfe": row["old"]["optimizer_nfe"],
        "hybrid_h3_nfe": row["hybrid_h3"]["evaluations"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

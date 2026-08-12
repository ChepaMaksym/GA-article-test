#!/usr/bin/env python3
"""Run the preregistered Jump control experiment for Hybrid 1."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hybrid_1.benchmarks import run_jump_campaign, summarize_jump
else:
    from .benchmarks import run_jump_campaign, summarize_jump


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--budget", type=int, default=10000)
    parser.add_argument("--seed-start", type=int, default=101)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--campaign-workers", type=int, default=1)
    parser.add_argument("--evaluation-workers", type=int, default=1)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    seeds = range(args.seed_start, args.seed_start + args.runs)
    rows = run_jump_campaign(
        n=args.n,
        k=args.k,
        seeds=seeds,
        budget=args.budget,
        campaign_workers=args.campaign_workers,
        evaluation_workers=args.evaluation_workers,
    )
    summary = summarize_jump(rows)
    gates = {
        "J0_ALL_ROWS": len(rows) == args.runs,
        "J1_RESET_TRIGGERED": int(summary["total_reset_events"]) > 0,
        "J2_ABSOLUTE_GAIN": float(summary["success_rate_difference"]) >= 0.20,
        "J3_RELATIVE_GAIN": float(summary["success_ratio"]) >= 1.50,
    }
    report = {
        "schema": "eu26-21-hybrid-1-jump-v1",
        "parameters": {
            "n": args.n,
            "k": args.k,
            "budget": args.budget,
            "seed_start": args.seed_start,
            "runs": args.runs,
            "campaign_workers": args.campaign_workers,
            "evaluation_workers": args.evaluation_workers,
        },
        "summary": summary,
        "gates": gates,
        "claim_status": (
            "PASS_JUMP_MEANINGFUL_IMPROVEMENT"
            if all(gates.values())
            else "FAIL_JUMP_IMPROVEMENT_GATE"
        ),
        "rows": rows,
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "claim_status": report["claim_status"],
        "summary": summary,
        "gates": gates,
    }, sort_keys=True))
    if args.enforce and not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

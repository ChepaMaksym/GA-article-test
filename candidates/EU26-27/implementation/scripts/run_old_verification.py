from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, median, pstdev

from eu2627 import (
    campaign_digest,
    compare_distributions,
    parse_raw_endpoint,
    run_campaign,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--workers", required=True, type=int, choices=(1, 2, 4))
    parser.add_argument("--output", required=True)
    parser.add_argument("--first-seed", type=int, default=270001)
    parser.add_argument("--last-seed", type=int, default=270100)
    parser.add_argument("--budget", type=int, default=2_000_000)
    args = parser.parse_args()

    raw = parse_raw_endpoint(args.archive)
    seeds = range(args.first_seed, args.last_seed + 1)
    runs = run_campaign(seeds, workers=args.workers, max_evaluations=args.budget)
    complete = [run.evaluations for run in runs if run.complete]
    compatibility = compare_distributions(raw.finite_endpoints(), complete)
    payload = {
        "schema": "eu26-27-old-verification-v1",
        "status": (
            "PASS_OLD_DISTRIBUTIONAL_COMPATIBILITY"
            if compatibility.overall_pass
            else "FAIL_OLD_DISTRIBUTIONAL_COMPATIBILITY"
        ),
        "workers": args.workers,
        "raw": {
            "member_sha256": raw.member_sha256,
            "endpoint_digest": raw.endpoint_digest,
            "complete_runs": raw.complete_runs,
            "median": median(raw.finite_endpoints()),
            "mean": mean(raw.finite_endpoints()),
            "pstdev": pstdev(raw.finite_endpoints()),
            "minimum": min(raw.finite_endpoints()),
            "maximum": max(raw.finite_endpoints()),
        },
        "independent": {
            "seed_first": args.first_seed,
            "seed_last": args.last_seed,
            "complete_runs": len(complete),
            "campaign_digest": campaign_digest(runs),
            "median": median(complete) if complete else None,
            "mean": mean(complete) if complete else None,
            "pstdev": pstdev(complete) if len(complete) > 1 else None,
            "minimum": min(complete) if complete else None,
            "maximum": max(complete) if complete else None,
            "rows": [run.canonical() for run in runs],
        },
        "compatibility": compatibility.canonical(),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = {key: value for key, value in payload.items() if key != "independent"}
    print(json.dumps(summary, sort_keys=True))
    return 0 if compatibility.overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())

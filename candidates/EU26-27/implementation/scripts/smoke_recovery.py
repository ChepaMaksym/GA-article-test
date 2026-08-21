from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

from eu2627.recovery import recovery_campaign_digest, run_recovery_campaign


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, choices=[1, 2, 4], required=True)
    parser.add_argument("--tie-policy", choices=["uniform", "first"], required=True)
    parser.add_argument(
        "--split-policy",
        choices=["balanced", "literal_one_based"],
        required=True,
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = run_recovery_campaign(
        range(271001, 271007),
        tie_policy=args.tie_policy,
        split_policy=args.split_policy,
        workers=args.workers,
        n=30,
        offspring=10,
        max_evaluations=300_000,
    )
    payload = {
        "schema": "eu26-27-recovery-smoke-v1",
        "research_tag": "RESEARCH_2",
        "workers": args.workers,
        "tie_policy": args.tie_policy,
        "split_policy": args.split_policy,
        "digest": recovery_campaign_digest(rows),
        "complete": sum(row.complete for row in rows),
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

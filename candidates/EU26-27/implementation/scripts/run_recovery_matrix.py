from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, median, pstdev

import numpy as np

from eu2627.artifact import parse_raw_endpoint
from eu2627.recovery import recovery_campaign_digest, run_recovery_campaign
from eu2627.stats import compare_distributions

VARIANTS = {
    "R1_uniform_balanced": ("uniform", "balanced"),
    "R2_first_balanced": ("first", "balanced"),
    "R3_uniform_literal": ("uniform", "literal_one_based"),
    "R4_first_literal": ("first", "literal_one_based"),
}


def describe(values: list[float]) -> dict:
    array = np.asarray(values, dtype=np.float64)
    q1, q3 = np.quantile(array, [0.25, 0.75])
    return {
        "count": len(values),
        "mean": float(mean(values)),
        "median": float(median(values)),
        "pstdev": float(pstdev(values)),
        "minimum": float(np.min(array)),
        "q1": float(q1),
        "q3": float(q3),
        "maximum": float(np.max(array)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--workers", type=int, choices=[1, 2, 4], required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    raw = parse_raw_endpoint(args.archive)
    raw_values = list(raw.finite_endpoints())
    if len(raw_values) != 100:
        raise SystemExit("selected raw profile is incomplete")

    report = {
        "schema": "eu26-27-recovery-v1",
        "research_tag": "RESEARCH_2",
        "workers": args.workers,
        "raw": {
            "member_sha256": raw.member_sha256,
            "endpoint_digest": raw.endpoint_digest,
            "summary": describe([float(value) for value in raw_values]),
            "endpoints": raw_values,
        },
        "variants": {},
    }

    passing = []
    for name, (tie_policy, split_policy) in VARIANTS.items():
        rows = run_recovery_campaign(
            range(270001, 270101),
            tie_policy=tie_policy,
            split_policy=split_policy,
            workers=args.workers,
            n=100,
            offspring=10,
            max_evaluations=2_000_000,
        )
        if len(rows) != 100:
            raise SystemExit(f"{name}: campaign row count drift")
        endpoints = [row.evaluations for row in rows]
        complete = sum(row.complete for row in rows)
        compatibility = compare_distributions(raw_values, endpoints)
        variant = {
            "tie_policy": tie_policy,
            "split_policy": split_policy,
            "complete_runs": complete,
            "campaign_digest": recovery_campaign_digest(rows),
            "endpoint_summary": describe([float(value) for value in endpoints]),
            "compatibility": compatibility.canonical(),
            "endpoints": endpoints,
            "final_rates": [row.final_rate for row in rows],
            "lower_winners": [row.lower_winners for row in rows],
            "higher_winners": [row.higher_winners for row in rows],
            "flipped_bits": [row.effort.flipped_bits for row in rows],
            "generated_offspring": [row.effort.generated_offspring for row in rows],
            "diagnostic_match": compatibility.overall_pass,
        }
        report["variants"][name] = variant
        if name != "R1_uniform_balanced" and compatibility.overall_pass:
            passing.append(name)

    baseline = report["variants"]["R1_uniform_balanced"]["compatibility"]
    if baseline["overall_pass"]:
        raise SystemExit("baseline unexpectedly changed from retained failed interpretation")

    report["diagnostic_matches"] = passing
    report["scientific_decision"] = (
        "RECOVERY_DIAGNOSTIC_MATCH_ONLY" if passing else "RECOVERY_NO_DIAGNOSTIC_MATCH"
    )
    report["old_full_reproduction"] = False
    report["author_source_gate"] = "UNRESOLVED"
    report["hybrid"] = "BLOCKED_NOT_AUTHORIZED"

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "scientific_decision": report["scientific_decision"],
        "diagnostic_matches": passing,
        "workers": args.workers,
        "variant_medians": {
            name: value["endpoint_summary"]["median"]
            for name, value in report["variants"].items()
        },
        "variant_kolmogorov": {
            name: value["compatibility"]["kolmogorov_distance"]
            for name, value in report["variants"].items()
        },
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

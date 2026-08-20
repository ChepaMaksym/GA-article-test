from __future__ import annotations

import argparse
import json
from pathlib import Path

FIELDS = [
    "candidate_id",
    "profile",
    "algorithm",
    "source_commit",
    "source_version",
    "instance_git_blob",
    "config_sha256",
    "penalty_manager_git_blob",
    "seed",
    "max_iterations",
    "completed_iterations",
    "final_cost",
    "feasible",
    "num_clients",
    "num_routes",
    "first_hit",
    "solution_sha256",
    "scientific_digest",
]


def load_batch(path: Path) -> dict[int, dict]:
    rows = [json.loads(file.read_text()) for file in sorted(path.glob("seed_*.json"))]
    return {int(row["seed"]): {field: row.get(field) for field in FIELDS} for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("batches", nargs="+", type=Path)
    args = parser.parse_args()
    if len(args.batches) < 2:
        raise SystemExit("need at least two batch directories")

    loaded = [load_batch(path) for path in args.batches]
    expected_seeds = sorted(loaded[0])
    mismatches: list[dict] = []
    for idx, batch in enumerate(loaded[1:], start=1):
        if sorted(batch) != expected_seeds:
            mismatches.append(
                {
                    "batch": str(args.batches[idx]),
                    "type": "seed_ledger",
                    "expected": expected_seeds,
                    "actual": sorted(batch),
                }
            )
            continue
        for seed in expected_seeds:
            fields = [field for field in FIELDS if batch[seed][field] != loaded[0][seed][field]]
            if fields:
                mismatches.append(
                    {
                        "batch": str(args.batches[idx]),
                        "seed": seed,
                        "type": "scientific_row",
                        "fields": fields,
                    }
                )

    report = {
        "pass": not mismatches,
        "batches": [str(path) for path in args.batches],
        "seeds": expected_seeds,
        "mismatches": mismatches,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())

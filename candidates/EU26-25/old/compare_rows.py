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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    rows = [json.loads(path.read_text()) for path in args.files]
    if len(rows) < 2:
        raise SystemExit("need at least two rows")
    base = {field: rows[0].get(field) for field in FIELDS}
    mismatches = []
    for idx, row in enumerate(rows[1:], start=1):
        other = {field: row.get(field) for field in FIELDS}
        if other != base:
            mismatches.append(
                {"row": idx, "fields": [field for field in FIELDS if other[field] != base[field]]}
            )
    report = {"pass": not mismatches, "rows": len(rows), "mismatches": mismatches}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())

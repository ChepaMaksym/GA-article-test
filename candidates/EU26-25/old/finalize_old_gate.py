from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {"missing": str(path)}
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-summary", type=Path, required=True)
    parser.add_argument("--formula-report", type=Path, required=True)
    parser.add_argument("--repeat-report", type=Path, required=True)
    parser.add_argument("--worker-report", type=Path, required=True)
    parser.add_argument("--portability-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    old = read_json(args.old_summary)
    formula = read_json(args.formula_report)
    repeat = read_json(args.repeat_report)
    workers = read_json(args.worker_report)
    portability_rows = [
        json.loads(path.read_text())
        for path in sorted(args.portability_dir.rglob("portability_*.json"))
    ]

    portability_gate = (
        len(portability_rows) == 6
        and all(row.get("complete") is True for row in portability_rows)
        and all(row.get("source_version") == "0.5.0" for row in portability_rows)
        and all(row.get("feasible") is True for row in portability_rows)
        and all(row.get("num_clients") == 100 for row in portability_rows)
        and all(
            row.get("instance_git_blob") == "ad4539d0b70cd60178601d7b3515d08945fdb3ad"
            for row in portability_rows
        )
        and len({row.get("platform") for row in portability_rows}) >= 3
    )

    gates = {
        "old_numeric": old.get("decision")
        == "PASS_SOURCE_NATIVE_ITERATION_NORMALISED_ENDPOINT",
        "formula": formula.get("pass") is True,
        "repeatability": repeat.get("pass") is True,
        "worker_load_equivalence": workers.get("pass") is True,
        "portability_smoke": portability_gate,
    }
    passed = all(gates.values())
    report = {
        "candidate_id": "EU26-25",
        "decision": (
            "PASS_OLD_FULL_ENGINEERING_GATE"
            if passed
            else "REJECTED_OLD_REPRODUCTION"
        ),
        "old_numeric_decision": old.get("decision"),
        "hybrid_status": "UNBLOCKED_FOR_EXPLORATION" if passed else "BLOCKED_NOT_CREATED",
        "gates": gates,
        "failed_gates": [name for name, value in gates.items() if not value],
        "old_summary": old,
        "formula_report": formula,
        "repeatability_report": repeat,
        "worker_report": workers,
        "portability_rows": portability_rows,
        "claim_limits": [
            "iteration-normalised endpoint, not historical CPU equivalence",
            "portability smoke does not prove equal wall-clock speed",
            "no HYBRID result exists at this gate",
            "PR #19 evidence is not used",
        ],
        "pr19_evidence_used": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

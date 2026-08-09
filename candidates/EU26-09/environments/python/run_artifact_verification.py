#!/usr/bin/env python3
"""Authenticate and verify the frozen EU26-09 raw artifact."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


PYTHON_ENV = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_ENV))

from eu2609.archive import parse_artifact  # noqa: E402
from eu2609.canonical import bind_report, write_new_json  # noqa: E402
from eu2609.contract import load_contract  # noqa: E402
from eu2609.controls import control_state, transition_lambda  # noqa: E402
from eu2609.source import assert_same_identity, authenticate_checkout  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output must be a new path")

    contract = load_contract()
    before = authenticate_checkout(args.checkout, contract)
    raw_path = args.checkout.resolve() / contract["raw_member"]["path"]
    payload = raw_path.read_bytes()
    artifact = parse_artifact(payload, contract)
    half_integer = control_state(2.5, dimension=100)
    fixtures = {
        "success_from_1": transition_lambda(
            1.0, success=True, update_factor=1.5, lambda_max=100.0
        ),
        "failure_from_1": transition_lambda(
            1.0, success=False, update_factor=1.5, lambda_max=100.0
        ),
        "failure_at_cap_reset": transition_lambda(
            100.0, success=False, update_factor=1.5, lambda_max=100.0
        ),
        "source_half_integer_count": half_integer.source_offspring_count,
        "paper_half_integer_count": half_integer.paper_offspring_count,
    }
    if fixtures["source_half_integer_count"] == fixtures["paper_half_integer_count"]:
        raise RuntimeError("paper/source half-integer conflict fixture disappeared")
    after = authenticate_checkout(args.checkout, contract)
    assert_same_identity(before, after)

    report = bind_report(
        {
            "schema_version": "1.0.0",
            "candidate_id": "EU26-09",
            "status": "TARGETED_ARTIFACT_REPLAY",
            "paper_mapping": "PAPER_FIGURE_CONTEXT_ONLY",
            "artifact_gate": "PASS_ARTIFACT_ENDPOINT",
            "source_identity_gate": "PASS_AUTHENTICATED_ARTIFACT",
            "control_gate": "PASS_CONTROL_TRANSITIONS",
            "forbidden_claims": contract["forbidden_claims"],
            "mandatory_conflicts": [
                "paper_ceil_vs_source_round_ties_even",
                "paper_has_no_literal_numeric_mapping",
                "paper_does_not_pin_commit",
                "upstream_has_no_dependency_lock",
                "source_excludes_initial_parent_evaluation",
            ],
            "source": before,
            "artifact": {
                "path": contract["raw_member"]["path"],
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "run_count": len(artifact.runs),
                "totals": dict(artifact.totals),
                "means": dict(artifact.means),
                "all_solved": all(record.solved for record in artifact.runs),
            },
            "control_fixtures": fixtures,
        },
        domain=b"EU26-09-ARTIFACT-REPORT-V1",
    )
    write_new_json(args.output, report)
    print(f"{report['artifact_gate']}: {len(artifact.runs)} authenticated rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

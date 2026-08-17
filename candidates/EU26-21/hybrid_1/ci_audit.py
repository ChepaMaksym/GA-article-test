#!/usr/bin/env python3
"""Static fail-closed audit for the EU26-21 GitHub Actions topology."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Dict, List


PINNED_ACTION = re.compile(r"^\s*-?\s*uses:\s*[^@\s]+@[0-9a-f]{40}\s*(?:#.*)?$")
ANY_ACTION = re.compile(r"^\s*-?\s*uses:\s*([^@\s]+)@([^\s#]+)")
TOP_LEVEL_EVENT = re.compile(r"^  (push|pull_request):\s*$", re.MULTILINE)

CANONICAL_MATRIX = ".github/workflows/eu26-21-old-hybrid-30-matrix.yml"
AUDIT_WORKFLOW = ".github/workflows/eu26-21-verification-audit.yml"
MUTATION_WORKFLOW = ".github/workflows/eu26-21-test-mutation-audit.yml"
OLD_WORKFLOW = ".github/workflows/eu26-21-old-validation.yml"
HYBRID_WORKFLOW = ".github/workflows/eu26-21-hybrid-1.yml"
RETIRED_WORKFLOWS = (
    ".github/workflows/eu26-21-old-hybrid-30-seed.yml",
    ".github/workflows/eu26-21-old-hybrid-30-seed-v2.yml",
    ".github/workflows/eu26-21-old-hybrid-aggregate-only.yml",
)

REQUIRED_MATRIX_PATHS = (
    "candidates/EU26-21/hybrid_1/core.py",
    "candidates/EU26-21/hybrid_1/benchmarks.py",
    "candidates/EU26-21/hybrid_1/census.py",
    "candidates/EU26-21/hybrid_1/paired_comparison.py",
    "candidates/EU26-21/hybrid_1/paired_comparison_v2.py",
    "candidates/EU26-21/hybrid_1/run_old_hybrid_comparison_v2.py",
    "candidates/EU26-21/hybrid_1/run_old_hybrid_seed_v2.py",
    "candidates/EU26-21/hybrid_1/aggregate_old_hybrid_v2.py",
    "candidates/EU26-21/hybrid_1/audit_validation.py",
    "candidates/EU26-21/hybrid_1/requirements.txt",
    "candidates/EU26-21/tests/test_hybrid_1_aggregation_guard.py",
    "candidates/EU26-21/tests/test_hybrid_1_audit_validation.py",
    "candidates/EU26-21/tests/test_hybrid_1_paired_comparison.py",
    "candidates/EU26-21/tests/test_hybrid_1_paired_comparison_v2.py",
)


def _read(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(relative)
    return path.read_text(encoding="utf-8")


def _action_refs(text: str) -> List[Dict[str, str]]:
    output: List[Dict[str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = ANY_ACTION.match(line)
        if match:
            output.append({
                "line": str(number),
                "action": match.group(1),
                "ref": match.group(2),
                "pinned": str(bool(PINNED_ACTION.match(line))).lower(),
            })
    return output


def _push_only(text: str) -> bool:
    return "  push:" in text and "  pull_request:" not in text


def audit(root: Path) -> Dict[str, object]:
    critical: Dict[str, bool] = {}
    warnings: List[str] = []

    matrix = _read(root, CANONICAL_MATRIX)
    audit_workflow = _read(root, AUDIT_WORKFLOW)
    mutation_workflow = _read(root, MUTATION_WORKFLOW)
    old_workflow = _read(root, OLD_WORKFLOW)
    hybrid_workflow = _read(root, HYBRID_WORKFLOW)

    critical["C0_MATRIX_IS_PUSH_ONLY"] = _push_only(matrix)
    critical["C1_MATRIX_COVERS_ALL_SCIENTIFIC_PATHS"] = all(
        path in matrix for path in REQUIRED_MATRIX_PATHS
    )
    critical["C2_MATRIX_USES_CANONICAL_STRICT_AGGREGATOR"] = (
        "aggregate_old_hybrid_v2.py" in matrix
        and "aggregate_old_hybrid_v2_corrected.py" not in matrix
    )
    critical["C3_MATRIX_RETAINS_PARTIAL_FAILURE_EVIDENCE"] = all(
        token in matrix
        for token in (
            "fail-fast: false",
            "if: always()",
            "aggregation-status.json",
            "seed-*.log",
        )
    )
    critical["C4_MATRIX_ACTIONS_PINNED"] = all(
        item["pinned"] == "true" for item in _action_refs(matrix)
    )
    critical["C5_AUDIT_ACTIONS_PINNED"] = all(
        item["pinned"] == "true" for item in _action_refs(audit_workflow)
    )
    critical["C6_AUDIT_RUNS_ALL_HYBRID_TESTS"] = (
        "python -m unittest discover" in audit_workflow
        and "test_hybrid_1_*.py" in audit_workflow
    )
    critical["C7_AUDIT_REVALIDATES_IMMUTABLE_ROWS"] = all(
        token in audit_workflow
        for token in (
            "31934321927",
            "aggregate_old_hybrid_v2.py",
            "test_hybrid_1_audit_validation.py",
        )
    )

    for relative in RETIRED_WORKFLOWS:
        text = _read(root, relative)
        critical[f"C8_MANUAL_ONLY_{Path(relative).stem}"] = (
            "workflow_dispatch:" in text and TOP_LEVEL_EVENT.search(text) is None
        )

    critical["C9_OLD_TRIGGER_IS_PUSH_ONLY_AND_OLD_SCOPED"] = (
        _push_only(old_workflow)
        and "candidates/EU26-21/**" not in old_workflow
        and "candidates/EU26-21/old/**" in old_workflow
    )
    critical["C10_HYBRID_TRIGGER_IS_PUSH_ONLY_AND_EXCLUDES_RESULT_DOCS"] = (
        _push_only(hybrid_workflow)
        and "candidates/EU26-21/hybrid_1/**" not in hybrid_workflow
        and "candidates/EU26-21/hybrid_1/core.py" in hybrid_workflow
    )

    aggregator = _read(
        root,
        "candidates/EU26-21/hybrid_1/aggregate_old_hybrid_v2.py",
    )
    critical["C11_SCIENTIFIC_FAILURE_IS_NOT_CI_PROTOCOL_FAILURE"] = (
        'report["claim_status"]' in aggregator
        and 'report["audit_status"]' in aggregator
        and 'report["h1"]["decision"] !=' not in aggregator
        and 'report["h3"]["primary_decision"] !=' not in aggregator
    )
    critical["C12_MUTATION_AUDIT_IS_PUSH_ONLY_AND_PINNED"] = (
        _push_only(mutation_workflow)
        and all(
            item["pinned"] == "true" for item in _action_refs(mutation_workflow)
        )
    )
    critical["C13_AUDIT_KILLS_DELIBERATE_MUTANTS"] = all(
        token in mutation_workflow
        for token in (
            "mutation_sensitivity_audit.py",
            "--enforce",
            "mutation-audit.json",
            "Kill six deliberate critical-code mutants",
        )
    )
    critical["C14_VERIFICATION_AUDIT_IS_PUSH_ONLY"] = _push_only(audit_workflow)

    for relative, text in (
        (OLD_WORKFLOW, old_workflow),
        (HYBRID_WORKFLOW, hybrid_workflow),
        (CANONICAL_MATRIX, matrix),
        (AUDIT_WORKFLOW, audit_workflow),
        (MUTATION_WORKFLOW, mutation_workflow),
    ):
        mutable = [
            item for item in _action_refs(text) if item["pinned"] != "true"
        ]
        if mutable:
            warnings.append(
                f"{relative} still uses mutable action tags: "
                + ", ".join(f"{item['action']}@{item['ref']}" for item in mutable)
            )

    return {
        "schema": "eu26-21-ci-audit-v3",
        "critical_gates": critical,
        "warnings": warnings,
        "pass": all(critical.values()),
        "audited_workflows": [
            CANONICAL_MATRIX,
            AUDIT_WORKFLOW,
            MUTATION_WORKFLOW,
            OLD_WORKFLOW,
            HYBRID_WORKFLOW,
            *RETIRED_WORKFLOWS,
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    report = audit(args.root.resolve())
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if args.enforce and not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

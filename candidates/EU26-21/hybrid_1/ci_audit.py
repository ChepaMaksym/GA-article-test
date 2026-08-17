#!/usr/bin/env python3
"""Static fail-closed audit for the canonical EU26-21 CI topology."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Dict, List


PINNED_ACTION = re.compile(
    r"^\s*-?\s*uses:\s*[^@\s]+@[0-9a-f]{40}\s*(?:#.*)?$"
)
ANY_ACTION = re.compile(r"^\s*-?\s*uses:\s*([^@\s]+)@([^\s#]+)")

CANONICAL_MATRIX = ".github/workflows/eu26-21-old-hybrid-30-matrix.yml"
AUDIT_WORKFLOW = ".github/workflows/eu26-21-verification-audit.yml"
MUTATION_WORKFLOW = ".github/workflows/eu26-21-test-mutation-audit.yml"
OLD_WORKFLOW = ".github/workflows/eu26-21-old-validation.yml"
HYBRID_WORKFLOW = ".github/workflows/eu26-21-hybrid-1.yml"
CORRECTED_SECURE_WORKFLOW = (
    ".github/workflows/eu26-21-corrected-applied-secure-matrix.yml"
)
QUALITY_WORKFLOW = ".github/workflows/eu26-21-code-quality.yml"
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
            output.append(
                {
                    "line": str(number),
                    "action": match.group(1),
                    "ref": match.group(2),
                    "pinned": str(bool(PINNED_ACTION.match(line))).lower(),
                }
            )
    return output


def _push_only(text: str) -> bool:
    return "  push:" in text and "  pull_request:" not in text


def _all_actions_pinned(text: str) -> bool:
    references = _action_refs(text)
    return bool(references) and all(
        item["pinned"] == "true" for item in references
    )


def audit(root: Path) -> Dict[str, object]:
    critical: Dict[str, bool] = {}
    warnings: List[str] = []

    workflows = {
        CANONICAL_MATRIX: _read(root, CANONICAL_MATRIX),
        AUDIT_WORKFLOW: _read(root, AUDIT_WORKFLOW),
        MUTATION_WORKFLOW: _read(root, MUTATION_WORKFLOW),
        OLD_WORKFLOW: _read(root, OLD_WORKFLOW),
        HYBRID_WORKFLOW: _read(root, HYBRID_WORKFLOW),
        CORRECTED_SECURE_WORKFLOW: _read(root, CORRECTED_SECURE_WORKFLOW),
        QUALITY_WORKFLOW: _read(root, QUALITY_WORKFLOW),
    }
    matrix = workflows[CANONICAL_MATRIX]
    audit_workflow = workflows[AUDIT_WORKFLOW]
    mutation_workflow = workflows[MUTATION_WORKFLOW]
    old_workflow = workflows[OLD_WORKFLOW]
    hybrid_workflow = workflows[HYBRID_WORKFLOW]
    corrected = workflows[CORRECTED_SECURE_WORKFLOW]
    quality = workflows[QUALITY_WORKFLOW]

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
    critical["C4_MATRIX_ACTIONS_PINNED"] = _all_actions_pinned(matrix)
    critical["C5_AUDIT_ACTIONS_PINNED"] = _all_actions_pinned(
        audit_workflow
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
    critical["C8_RETIRED_PLACEHOLDER_WORKFLOWS_REMOVED"] = all(
        not (root / relative).exists() for relative in RETIRED_WORKFLOWS
    )
    critical["C9_OLD_TRIGGER_IS_PUSH_ONLY_AND_OLD_SCOPED"] = (
        _push_only(old_workflow)
        and "candidates/EU26-21/**" not in old_workflow
        and "candidates/EU26-21/old/**" in old_workflow
    )
    critical[
        "C10_HYBRID_TRIGGER_IS_PUSH_ONLY_AND_EXCLUDES_RESULT_DOCS"
    ] = (
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
        and _all_actions_pinned(mutation_workflow)
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
    critical["C14_VERIFICATION_AUDIT_IS_PUSH_ONLY"] = _push_only(
        audit_workflow
    )
    critical["C15_CORRECTED_SECURE_IS_PUSH_ONLY_AND_PINNED"] = (
        _push_only(corrected) and _all_actions_pinned(corrected)
    )
    critical["C16_CORRECTED_SECURE_USES_OFFICIAL_TRAIN_AND_TEST"] = all(
        token in corrected
        for token in (
            "census-income.data",
            "census-income.test",
            "UCI_ARCHIVE_URL",
            "train.sha256",
            "test.sha256",
            "corrected_applied.experiment",
        )
    )
    critical["C17_CORRECTED_SECURE_PRESERVES_SCIENTIFIC_FAILURES"] = all(
        token in corrected
        for token in (
            "fail-fast: false",
            "if: always()",
            "corrected-report.json",
            "status.json",
        )
    )
    critical["C18_CORRECTED_SECURE_AUDITS_DEPENDENCIES"] = all(
        token in corrected
        for token in (
            "corrected_applied/requirements.txt",
            "pip-audit",
            "python -m pip check",
        )
    )
    critical["C19_QUALITY_WORKFLOW_IS_PUSH_ONLY_AND_PINNED"] = (
        _push_only(quality) and _all_actions_pinned(quality)
    )
    critical["C20_QUALITY_WORKFLOW_RUNS_COMPLETE_AUDIT"] = all(
        token in quality
        for token in (
            "coverage run",
            "ruff check",
            "bandit -r",
            "vulture",
            "pip-audit",
            "if: always()",
            "Enforce blocking quality gates after preserving all reports",
        )
    )

    for relative, text in workflows.items():
        mutable = [
            item for item in _action_refs(text) if item["pinned"] != "true"
        ]
        if mutable:
            warnings.append(
                f"{relative} still uses mutable action tags: "
                + ", ".join(
                    f"{item['action']}@{item['ref']}" for item in mutable
                )
            )

    return {
        "schema": "eu26-21-ci-audit-v4",
        "critical_gates": critical,
        "warnings": warnings,
        "pass": all(critical.values()),
        "audited_workflows": list(workflows),
        "retired_workflows_expected_absent": list(RETIRED_WORKFLOWS),
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

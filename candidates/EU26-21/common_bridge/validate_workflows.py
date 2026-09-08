#!/usr/bin/env python3
"""Fail-closed static contract for common-bridge GitHub Actions workflows.

The validator deliberately reads workflow text instead of loading YAML. YAML
1.1 loaders commonly coerce the GitHub Actions on key to a boolean, and a
static text contract also makes action pins and forbidden execution commands
unambiguous. It never downloads data or executes a search.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable


CHECKOUT = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
SETUP_PYTHON = (
    "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065"
)
UPLOAD_ARTIFACT = (
    "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
)
DOWNLOAD_ARTIFACT = (
    "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093"
)
ALLOWED_ACTIONS = {
    CHECKOUT,
    SETUP_PYTHON,
    UPLOAD_ARTIFACT,
    DOWNLOAD_ARTIFACT,
}
PROTECTED_REF = "refs/tags/eu26-21-common-bridge-evidence-v1"
EXPECTED_SEEDS = list(range(41001, 41031))
WORKFLOW_PATHS = {
    "ci": Path(".github/workflows/eu26-21-common-bridge-ci.yml"),
    "campaign": Path(
        ".github/workflows/eu26-21-common-bridge-30-paired.yml"
    ),
    "reaggregate": Path(
        ".github/workflows/eu26-21-common-bridge-reaggregate.yml"
    ),
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _trigger_block(text: str) -> str:
    lines = text.splitlines()
    try:
        start = lines.index("on:")
    except ValueError as error:
        raise ValueError("workflow has no top-level on block") from error
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line and not line[0].isspace() and not line.startswith("#"):
            end = index
            break
    return "\n".join(lines[start:end])


def _uses(text: str) -> list[str]:
    return re.findall(r"(?m)^\s*-\s+uses:\s*(\S+)\s*$", text)


def _action_blocks(text: str, action: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        if line.strip() != f"- uses: {action}":
            continue
        indentation = len(line) - len(line.lstrip())
        end = len(lines)
        for cursor in range(index + 1, len(lines)):
            candidate = lines[cursor]
            candidate_indent = len(candidate) - len(candidate.lstrip())
            if candidate.strip() and not candidate.lstrip().startswith("#") and candidate_indent < indentation:
                end = cursor
                break
            if (
                candidate_indent == indentation
                and candidate.lstrip().startswith("- ")
            ):
                end = cursor
                break
        blocks.append("\n".join(lines[index:end]))
    return blocks


def _require_tokens(text: str, tokens: Iterable[str], label: str) -> None:
    for token in tokens:
        _require(token in text, f"{label} lost required contract token: {token}")


def _forbid_tokens(text: str, tokens: Iterable[str], label: str) -> None:
    for token in tokens:
        _require(token not in text, f"{label} contains forbidden token: {token}")


def _validate_permissions(text: str, label: str) -> None:
    _require(
        re.search(
            r"(?m)^permissions:\n  contents: read\n  actions: read(?:\n|$)",
            text,
        )
        is not None,
        f"{label} permissions must be contents/actions read only",
    )
    _require(
        re.search(r"(?m)^\s+[A-Za-z-]+:\s*write\s*$", text) is None,
        f"{label} grants a write permission",
    )


def _validate_actions(
    text: str,
    label: str,
    required_actions: set[str],
) -> None:
    references = _uses(text)
    _require(bool(references), f"{label} contains no pinned actions")
    unexpected = sorted(set(references) - ALLOWED_ACTIONS)
    _require(not unexpected, f"{label} has unapproved action refs: {unexpected}")
    missing = sorted(required_actions - set(references))
    _require(not missing, f"{label} is missing required action refs: {missing}")
    for reference in references:
        _require(
            re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", reference) is not None,
            f"{label} action is not pinned to a full SHA: {reference}",
        )
    for block in _action_blocks(text, CHECKOUT):
        _require(
            "persist-credentials: false" in block,
            f"{label} checkout persists credentials",
        )
    for block in _action_blocks(text, UPLOAD_ARTIFACT):
        _require(
            "if-no-files-found: error" in block,
            f"{label} upload does not fail on missing evidence",
        )
        _require(
            "github.run_id" in block and "github.run_attempt" in block,
            f"{label} artifact name is not unique by run and attempt",
        )


def _require_dispatch_only(text: str, label: str) -> str:
    trigger = _trigger_block(text)
    _require(
        "workflow_dispatch:" in trigger,
        f"{label} is missing workflow_dispatch",
    )
    _forbid_tokens(
        trigger,
        ("pull_request:", "schedule:", "repository_dispatch:"),
        label,
    )
    # GitHub does not initially register a dispatch-only file introduced in a
    # draft branch (API 404). A self-file push event registers it, but all real
    # work must remain guarded behind an explicit manual job.
    if "push:" in trigger:
        _require("branches: [research/EU26-21-chcqx-census-old-first]" in trigger,
                 f"{label} registration escaped the PR19 branch")
        job = "authorize" if label == "protected campaign" else "reaggregate"
        path = WORKFLOW_PATHS["campaign" if job == "authorize" else "reaggregate"]
        _require(f"paths: ['{path.as_posix()}']" in trigger,
                 f"{label} registration path is not self-file-only")
        guard = f"  {job}:\n    if: " + "${{ github.event_name == 'workflow_dispatch' }}"
        _require(guard in text, f"{label} permits execution outside manual dispatch")
    return trigger


def _require_required_input(trigger: str, name: str, label: str) -> None:
    pattern = (
        rf"(?ms)^\s{{6}}{re.escape(name)}:\s*$"
        rf".*?^\s{{8}}required:\s*true\s*$"
    )
    _require(
        re.search(pattern, trigger) is not None,
        f"{label} input {name} is not required",
    )


def _validate_ci(text: str) -> None:
    label = "lightweight CI"
    trigger = _trigger_block(text)
    _require("workflow_dispatch:" in trigger, f"{label} lost manual trigger")
    _require("push:" in trigger, f"{label} lost branch push trigger")
    _require(
        "branches: [research/EU26-21-chcqx-census-old-first]" in trigger,
        f"{label} branch changed",
    )
    _require_tokens(
        trigger,
        (
            "'candidates/EU26-21/common_bridge/**'",
            "'candidates/EU26-21/tests/test_common_bridge.py'",
            "'.github/workflows/eu26-21-common-bridge-ci.yml'",
            "'.github/workflows/eu26-21-common-bridge-30-paired.yml'",
            "'.github/workflows/eu26-21-common-bridge-reaggregate.yml'",
            "'candidates/EU26-21/corrected_applied/data_protocol.py'",
            "'candidates/EU26-21/corrected_applied/requirements.txt'",
            "'candidates/EU26-21/hybrid_1/core.py'",
        ),
        label,
    )
    _validate_permissions(text, label)
    _validate_actions(
        text,
        label,
        {CHECKOUT, SETUP_PYTHON, UPLOAD_ARTIFACT},
    )
    _require_tokens(
        text,
        (
            "validate_protocol.py",
            "validate_workflows.py",
            "candidates/EU26-21/tests/test_common_bridge.py",
            "python -m unittest",
            "if-no-files-found: error",
        ),
        label,
    )
    _forbid_tokens(
        text,
        (
            "run_seed.py",
            "common_bridge.aggregate",
            "fetch_source_artifacts",
            "census-income.data",
            "census-income.test",
            "git clone",
            "curl --",
        ),
        label,
    )


def _parse_matrix_seeds(text: str) -> list[int]:
    match = re.search(r"(?m)^\s+seed:\s*\[([0-9,\s]+)\]\s*$", text)
    if match is None:
        raise ValueError("campaign seed matrix is missing or not explicit")
    return [int(value.strip()) for value in match.group(1).split(",")]


def _validate_campaign(text: str) -> None:
    label = "protected campaign"
    trigger = _require_dispatch_only(text, label)
    _require_required_input(trigger, "expected_sha", label)
    _validate_permissions(text, label)
    _validate_actions(
        text,
        label,
        {CHECKOUT, SETUP_PYTHON, UPLOAD_ARTIFACT, DOWNLOAD_ARTIFACT},
    )
    _require(
        _parse_matrix_seeds(text) == EXPECTED_SEEDS,
        "campaign seed matrix is not exactly 41001..41030",
    )
    _require("fail-fast: false" in text, "campaign fail-fast must be false")
    _require(
        "cancel-in-progress: false" in text,
        "campaign cancellation policy changed",
    )
    _require_tokens(
        text,
        (
            f"PROTECTED_REF: {PROTECTED_REF}",
            're.fullmatch(r"[0-9a-f]{40}", expected)',
            "actual != expected",
            "ref != protected",
            "ref: " + "$" + "{{ inputs.expected_sha }}",
            "persist-credentials: false",
            "54fd206becffcfaf099544c3938c681d64a65709800c94c00a4fba0a00df10c9",
            "3676a81db7d3528f3f8b9f3c699d0f0aa28db45e6e994fa0b8ed38327539ee86",
            "98402b1ab879573d0a7f38a699a40258080e25e33d3401e7bf9c96d3fa0fab8c",
            "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6",
            "730cd436db59d23da7dab5e24c49bc7b28d65379136fad7fd2d2370e0a436205",
            "upstream.tar.gz",
            "merge-multiple: false",
            "needs: [authorize, fixture, seed]",
            "needs: authorize",
            "needs: [authorize, fixture]",
            "common_bridge/run_seed.py",
            "--official-train",
            "--official-test",
            "--expected-sha",
            "--expected-protocol-sha256",
            "--expected-config-sha256",
            "--expected-requirements-sha256",
            "--artifact-name",
            "seed-$seed-chc-trace.json",
            "seed-$seed-lambda-trace.json",
            "seed-$seed-status.json",
            "seed-$seed-manifest.json",
            "common-bridge-source-artifact-ledger.json",
            "select_seed_artifacts",
            "artifact-ids:",
            "BRIDGE_WORKFLOW_SHA:",
            "fetch_all_artifacts",
            "range(1, 7)",
            ".github/workflows/eu26-21-common-bridge-30-paired.yml",
            "--source-artifact-ledger",
            "python -m common_bridge.aggregate",
            "aggregate-manifest.json",
        ),
        label,
    )
    _require(
        text.count("curl --fail") == 1,
        "campaign must download the official archive exactly once",
    )
    _require(
        text.count("git clone --no-tags") == 1,
        "campaign must fetch pinned upstream exactly once",
    )
    _require(
        text.count(
            "python candidates/EU26-21/common_bridge/run_seed.py"
        )
        == 1,
        "campaign must have one matrix runner invocation",
    )
    seed_uploads = [
        block
        for block in _action_blocks(text, UPLOAD_ARTIFACT)
        if "matrix.seed" in block
    ]
    _require(
        len(seed_uploads) == 1,
        "campaign must define one per-seed upload step",
    )
    _require(
        "github.run_id" in seed_uploads[0]
        and "github.run_attempt" in seed_uploads[0]
        and "matrix.seed" in seed_uploads[0],
        "per-seed artifact name lost run/attempt/seed identity",
    )
    campaign_checkouts = _action_blocks(text, CHECKOUT)
    _require(
        len(campaign_checkouts) == 2,
        "campaign checkout topology changed",
    )
    for block in campaign_checkouts:
        _require(
            "ref: " + "$" + "{{ inputs.expected_sha }}" in block,
            "campaign checkout is not bound to expected_sha",
        )
    _forbid_tokens(
        text,
        (
            "issues: write",
            "pull-requests: write",
            "gh api",
            "PASS_JOINT_BRIDGE_CLAIM ==",
            "FAIL_NONINFERIORITY ==",
            "if-no-files-found: warn",
        ),
        label,
    )


def _validate_reaggregate(text: str) -> None:
    label = "immutable reaggregation"
    trigger = _require_dispatch_only(text, label)
    for name in ("source_run_id", "expected_sha", "artifact_ledger_json"):
        _require_required_input(trigger, name, label)
    _validate_permissions(text, label)
    _validate_actions(
        text,
        label,
        {CHECKOUT, SETUP_PYTHON, UPLOAD_ARTIFACT},
    )
    _require(
        DOWNLOAD_ARTIFACT not in _uses(text),
        "reaggregation must use the verified fetch helper, not a broad action download",
    )
    _require(
        "cancel-in-progress: false" in text,
        "reaggregation cancellation policy changed",
    )
    _require_tokens(
        text,
        (
            f"PROTECTED_REF: {PROTECTED_REF}",
            're.fullmatch(r"[0-9a-f]{40}", expected_sha)',
            "list(range(41001, 41031))",
            'r"sha256:[0-9a-f]{64}"',
            "artifact IDs are not unique",
            "eu26-21-common-bridge-source-artifact-ledger-v1",
            "source_workflow_path",
            "730cd436db59d23da7dab5e24c49bc7b28d65379136fad7fd2d2370e0a436205",
            "python -m common_bridge.fetch_source_artifacts",
            "--artifact-ledger",
            "--metadata-output",
            "verified-source-artifacts.json",
            "python -m common_bridge.aggregate",
            "--source-artifact-ledger",
            "--expected-protocol-sha256",
            "--expected-config-sha256",
            "--expected-requirements-sha256",
            "--expected-run-id",
            "--expected-run-attempt",
            "--expected-ref",
            "--expected-workflow-sha",
            "aggregate-manifest.json",
            "if-no-files-found: error",
        ),
        label,
    )
    _require(
        text.index("python -m common_bridge.fetch_source_artifacts")
        < text.index("python -m common_bridge.aggregate"),
        "reaggregation runs aggregate before verified artifact fetch",
    )
    checkouts = _action_blocks(text, CHECKOUT)
    _require(len(checkouts) == 1, "reaggregation checkout topology changed")
    _require(
        "ref: " + "$" + "{{ inputs.expected_sha }}" in checkouts[0],
        "reaggregation checkout is not bound to expected_sha",
    )
    _forbid_tokens(
        text,
        (
            "run_seed.py",
            "git clone",
            "curl --",
            "census-income.data",
            "census-income.test",
            "--official-train",
            "--official-test",
            "UPSTREAM_COMMIT",
            "UCI_ARCHIVE_URL",
            "actions/download-artifact@",
            "issues: write",
            "pull-requests: write",
            "gh api",
            "if-no-files-found: warn",
        ),
        label,
    )


def validate(root: Path) -> dict[str, object]:
    resolved_root = root.resolve()
    texts: dict[str, str] = {}
    digests: dict[str, str] = {}
    for name, relative in WORKFLOW_PATHS.items():
        path = resolved_root / relative
        _require(path.is_file(), f"missing workflow: {relative.as_posix()}")
        texts[name] = path.read_text(encoding="utf-8")
        digests[name] = _sha256(path)

    _validate_ci(texts["ci"])
    _validate_campaign(texts["campaign"])
    _validate_reaggregate(texts["reaggregate"])
    return {
        "schema": "eu26-21-common-bridge-workflow-validation-v1",
        "workflow_sha256": digests,
        "seed_count": len(EXPECTED_SEEDS),
        "protected_ref": PROTECTED_REF,
        "optimizer_executed": False,
        "dataset_accessed": False,
        "pass": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = validate(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build a GitHub4 artifact attestation from authenticated GitHub API JSON."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
from typing import Any


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from eu2605.canonical import canonical_bytes, strict_json_load  # noqa: E402
from eu2605.core import (  # noqa: E402
    H0_SOURCE_STATUS,
    SOURCE_BYTE_STATUS,
    SOURCE_FREEZE_STATUS,
)


REPOSITORY_NAME = "ChepaMaksym/GA-article-test"
WORKFLOW_PATH = ".github/workflows/eu26-05-validation.yml"
ARTIFACT_NAME = "eu26-05-github-4-formula-portability"
REPORT_MEMBER = "github-4.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-run-json", required=True, type=Path)
    parser.add_argument("--artifact-json", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _select_artifact(payload: dict[str, Any], run_id: int) -> dict[str, Any]:
    if "artifacts" not in payload:
        return payload
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("GitHub artifact-list response has no artifact array")
    matches = [
        item
        for item in artifacts
        if isinstance(item, dict)
        and item.get("name") == ARTIFACT_NAME
        and item.get("workflow_run", {}).get("id") == run_id
        and item.get("expired") is False
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one unexpired GitHub4 artifact, found {len(matches)}")
    return matches[0]


def build_attestation(
    workflow_run: dict[str, Any], artifact_payload: dict[str, Any], report_path: Path
) -> dict[str, Any]:
    if not isinstance(workflow_run, dict) or not isinstance(artifact_payload, dict):
        raise ValueError("GitHub API responses must be JSON objects")
    run_id = workflow_run.get("id")
    attempt = workflow_run.get("run_attempt")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise ValueError("workflow API response has no positive run ID")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt <= 0:
        raise ValueError("workflow API response has no positive run attempt")
    if workflow_run.get("conclusion") != "success" or workflow_run.get("status") != "completed":
        raise ValueError("workflow run is not completed successfully")
    if workflow_run.get("repository", {}).get("full_name") != REPOSITORY_NAME:
        raise ValueError("workflow run repository differs from the frozen repository")
    api_workflow_path = workflow_run.get("path")
    if not isinstance(api_workflow_path, str) or not (
        api_workflow_path == WORKFLOW_PATH
        or api_workflow_path.startswith(f"{WORKFLOW_PATH}@")
    ):
        raise ValueError("workflow run path differs from the frozen workflow")
    head_sha = workflow_run.get("head_sha")
    if not isinstance(head_sha, str) or len(head_sha) != 40 or any(character not in "0123456789abcdef" for character in head_sha):
        raise ValueError("workflow run head SHA is malformed")

    artifact = _select_artifact(artifact_payload, run_id)
    artifact_id = artifact.get("id")
    if not isinstance(artifact_id, int) or isinstance(artifact_id, bool) or artifact_id <= 0:
        raise ValueError("artifact API response has no positive artifact ID")
    if artifact.get("name") != ARTIFACT_NAME or artifact.get("expired") is not False:
        raise ValueError("artifact identity/expiry differs from the frozen contract")
    artifact_run = artifact.get("workflow_run", {})
    if artifact_run.get("id") != run_id or artifact_run.get("head_sha") != head_sha:
        raise ValueError("artifact does not bind to the selected workflow run/head")

    report = strict_json_load(report_path)
    if not isinstance(report, dict) or report.get("profile_label") != "github-4":
        raise ValueError("artifact member is not a GitHub4 profile report")
    if report.get("git_head") != head_sha:
        raise ValueError("GitHub4 report head differs from the workflow API head")
    context = report.get("hardware", {}).get("execution_context", {})
    if str(run_id) != context.get("github_run_id") or str(attempt) != context.get("github_run_attempt"):
        raise ValueError("GitHub4 report run context differs from the workflow API")

    expected_run_url = f"https://api.github.com/repos/{REPOSITORY_NAME}/actions/runs/{run_id}"
    expected_artifact_url = f"https://api.github.com/repos/{REPOSITORY_NAME}/actions/artifacts/{artifact_id}"
    if workflow_run.get("url") != expected_run_url or artifact.get("url") != expected_artifact_url:
        raise ValueError("GitHub API object URLs are not exact")
    return {
        "schema_version": "1.0.0",
        "attestation_type": "GITHUB_ACTIONS_ARTIFACT_API_v1",
        "retrieval_method": "authenticated_github_api",
        "repository": REPOSITORY_NAME,
        "workflow_path": WORKFLOW_PATH,
        "head_sha": head_sha,
        "run_id": str(run_id),
        "run_attempt": str(attempt),
        "workflow_conclusion": "success",
        "artifact_id": artifact_id,
        "artifact_name": ARTIFACT_NAME,
        "artifact_expired": False,
        "report_member": REPORT_MEMBER,
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "workflow_run_api_url": expected_run_url,
        "artifact_api_url": expected_artifact_url,
        "h0_source_status": H0_SOURCE_STATUS,
        "source_byte_status": SOURCE_BYTE_STATUS,
        "source_freeze_status": SOURCE_FREEZE_STATUS,
    }


def main() -> None:
    args = parse_args()
    workflow_run = strict_json_load(args.workflow_run_json)
    artifact = strict_json_load(args.artifact_json)
    attestation = build_attestation(workflow_run, artifact, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(attestation) + b"\n")
    print(f"EU26-05 GITHUB API ATTESTATION PASS: {attestation['artifact_id']}")


if __name__ == "__main__":
    main()

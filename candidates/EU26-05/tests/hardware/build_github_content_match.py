#!/usr/bin/env python3
"""Build a non-authorizing match record from caller-supplied GitHub-shaped JSON.

This offline helper cannot authenticate an API response or prove that a local
report was extracted from an artifact.  It checks internal identity/content
coherence only.  H5 therefore remains externally not evaluated.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
from typing import Any


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
REPOSITORY = CANDIDATE.parents[1]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from eu2605.canonical import canonical_bytes, strict_json_load  # noqa: E402
from eu2605.core import (  # noqa: E402
    H0_SOURCE_STATUS,
    SOURCE_BYTE_STATUS,
    SOURCE_FREEZE_STATUS,
)
from eu2605.reporting import (  # noqa: E402
    exclusive_write_bytes,
    prepare_exclusive_outputs,
)


REPOSITORY_NAME = "ChepaMaksym/GA-article-test"
WORKFLOW_PATH = ".github/workflows/eu26-05-validation.yml"
ARTIFACT_NAME = "eu26-05-github-4-formula-portability"
REPORT_MEMBER = "github-4.json"
RECORD_TYPE = "CALLER_SUPPLIED_GITHUB_METADATA_CONTENT_MATCH_v1"
EXTERNAL_AUTH_STATUS = "NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-run-json", required=True, type=Path)
    parser.add_argument("--artifact-json", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _positive_integer(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _select_artifact(payload: dict[str, Any], run_id: int) -> dict[str, Any]:
    if "artifacts" not in payload:
        return payload
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("artifact metadata has no artifact array")
    matches = [
        item
        for item in artifacts
        if isinstance(item, dict)
        and item.get("name") == ARTIFACT_NAME
        and isinstance(item.get("workflow_run"), dict)
        and item["workflow_run"].get("id") == run_id
        and item.get("expired") is False
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one matching unexpired artifact object, found {len(matches)}")
    return matches[0]


def build_content_match(
    workflow_run: dict[str, Any], artifact_payload: dict[str, Any], report_path: Path
) -> dict[str, Any]:
    """Check coherence without claiming API authentication or artifact membership."""

    if not isinstance(workflow_run, dict) or not isinstance(artifact_payload, dict):
        raise ValueError("caller-supplied metadata values must be JSON objects")
    run_id = _positive_integer(workflow_run.get("id"), "workflow run ID")
    attempt = _positive_integer(workflow_run.get("run_attempt"), "workflow run attempt")
    if workflow_run.get("conclusion") != "success" or workflow_run.get("status") != "completed":
        raise ValueError("caller-supplied workflow metadata is not completed/success")
    repository = workflow_run.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != REPOSITORY_NAME:
        raise ValueError("workflow metadata repository differs from the frozen repository")
    workflow_path = workflow_run.get("path")
    if not isinstance(workflow_path, str) or not (
        workflow_path == WORKFLOW_PATH or workflow_path.startswith(f"{WORKFLOW_PATH}@")
    ):
        raise ValueError("workflow metadata path differs from the frozen workflow")
    head_sha = workflow_run.get("head_sha")
    if not isinstance(head_sha, str) or len(head_sha) != 40 or any(
        character not in "0123456789abcdef" for character in head_sha
    ):
        raise ValueError("workflow metadata head SHA is malformed")

    artifact = _select_artifact(artifact_payload, run_id)
    artifact_id = _positive_integer(artifact.get("id"), "artifact ID")
    if artifact.get("name") != ARTIFACT_NAME or artifact.get("expired") is not False:
        raise ValueError("artifact metadata identity/expiry differs from the frozen contract")
    artifact_run = artifact.get("workflow_run")
    if not isinstance(artifact_run, dict) or (
        artifact_run.get("id") != run_id or artifact_run.get("head_sha") != head_sha
    ):
        raise ValueError("artifact metadata does not bind to the selected run/head")

    report = strict_json_load(report_path)
    if not isinstance(report, dict) or report.get("profile_label") != "github-4":
        raise ValueError("local content is not a GitHub4 profile report")
    if report.get("git_head") != head_sha:
        raise ValueError("local report head differs from caller-supplied workflow metadata")
    hardware = report.get("hardware")
    context = hardware.get("execution_context") if isinstance(hardware, dict) else None
    if not isinstance(context, dict) or (
        str(run_id) != context.get("github_run_id")
        or str(attempt) != context.get("github_run_attempt")
    ):
        raise ValueError("local report run context differs from caller-supplied metadata")

    expected_run_url = f"https://api.github.com/repos/{REPOSITORY_NAME}/actions/runs/{run_id}"
    expected_artifact_url = (
        f"https://api.github.com/repos/{REPOSITORY_NAME}/actions/artifacts/{artifact_id}"
    )
    if workflow_run.get("url") != expected_run_url or artifact.get("url") != expected_artifact_url:
        raise ValueError("caller-supplied API object URLs are not exact")
    return {
        "schema_version": "1.0.0",
        "record_type": RECORD_TYPE,
        "metadata_source": "CALLER_SUPPLIED_UNVERIFIED_JSON",
        "external_authentication_status": EXTERNAL_AUTH_STATUS,
        "offline_authorizes_h5": False,
        "artifact_membership_verified": False,
        "repository": REPOSITORY_NAME,
        "workflow_path": WORKFLOW_PATH,
        "head_sha": head_sha,
        "run_id": str(run_id),
        "run_attempt": str(attempt),
        "claimed_workflow_conclusion": "success",
        "artifact_id": artifact_id,
        "artifact_name": ARTIFACT_NAME,
        "claimed_artifact_expired": False,
        "report_member": REPORT_MEMBER,
        "local_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "claimed_workflow_run_api_url": expected_run_url,
        "claimed_artifact_api_url": expected_artifact_url,
        "h0_source_status": H0_SOURCE_STATUS,
        "source_byte_status": SOURCE_BYTE_STATUS,
        "source_freeze_status": SOURCE_FREEZE_STATUS,
    }


def main() -> None:
    args = parse_args()
    (output_path,) = prepare_exclusive_outputs(
        [args.output], REPOSITORY, labels=["GitHub content-match output"]
    )
    workflow_run = strict_json_load(args.workflow_run_json)
    artifact = strict_json_load(args.artifact_json)
    record = build_content_match(workflow_run, artifact, args.report)
    exclusive_write_bytes(output_path, canonical_bytes(record) + b"\n")
    print(
        "EU26-05 CALLER-SUPPLIED CONTENT MATCH ONLY; "
        "EXTERNAL GITHUB AUTHENTICATION NOT EVALUATED"
    )


if __name__ == "__main__":
    main()

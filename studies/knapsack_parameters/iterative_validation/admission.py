"""Admit only the separately authorized retained-data analysis in GitHub CI.

This module never imports an analysis or search implementation. It verifies the
prepared source seal before dependencies, tests, or numerical work can start.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPOSITORY = "ChepaMaksym/GA-article-test"
REF = "refs/heads/research/iterative-validation-20261117"
WORKFLOW = ".github/workflows/iterative-validation.yml"
SOURCE = "studies/knapsack_parameters/iterative_validation/data/validated_records.json.gz"
SOURCE_SHA256 = "70adbcca7b27e645f8a01b7f8662358d62c347bf02a4edb825996ebf62a1af32"
LOCK = "studies/knapsack_parameters/ga_study/dependencies/requirements.lock"
RUNNER_MINUTES = 20
WORKFLOW_TIMEOUT_MINUTES = 15
ARTIFACT_BYTES = 524288000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path, document):
    path = Path(path)
    require(not path.exists(), "Preserve the existing execution receipt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ci_identity():
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Execution is permitted only in GitHub Actions")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "Unregistered repository")
    require(os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch", "Only manual dispatch is admitted")
    require(os.environ.get("GITHUB_REF") == REF, "Unregistered execution branch")
    require(os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "A rerun requires a separate resource grant")
    commit = os.environ.get("GITHUB_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "Missing execution commit")
    require(re.fullmatch(r"[0-9]+", run_id) is not None, "Missing workflow run identity")
    return {"workflow_commit": commit, "workflow_run_id": run_id, "workflow_run_attempt": 1}


def validate_authorization(document, requested_id):
    require(isinstance(document, dict), "Malformed resource authorization")
    expected = {
        "schema": "iterative-validation-resource-authorization-v1",
        "status": "AUTHORIZED",
        "phase": "first_analysis",
        "repository": REPOSITORY,
        "ref": REF,
        "runner_minutes": RUNNER_MINUTES,
        "artifact_bytes": ARTIFACT_BYTES,
        "source_sha256": SOURCE_SHA256,
        "fresh_approval": True,
        "new_search_evaluations": 0,
        "additional_dispatches_authorized": False,
    }
    for field, value in expected.items():
        require(type(document.get(field)) is type(value) and document[field] == value,
                "A fresh first-analysis resource grant is required: " + field)
    grant = document.get("authorization_id")
    require(isinstance(grant, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", grant) is not None,
            "Missing distinct authorization identity")
    require(isinstance(requested_id, str) and requested_id == grant,
            "Dispatch authorization identity differs from the granted payload")
    for name in ("protocol_sha256", "source_manifest_sha256"):
        require(isinstance(document.get(name), str) and re.fullmatch(r"[0-9a-f]{64}", document[name]) is not None,
                "Missing frozen payload checksum: " + name)
    return document


def verify_source(authorization):
    manifest_path = HERE / "source_manifest.json"
    require(sha256(manifest_path) == authorization["source_manifest_sha256"], "Source manifest checksum differs")
    require(sha256(HERE / "PROTOCOL_UK.md") == authorization["protocol_sha256"], "Protocol checksum differs")
    manifest = read_json(manifest_path)
    rows = manifest.get("files") if isinstance(manifest, dict) else None
    require(isinstance(rows, list) and bool(rows), "Source manifest is empty or malformed")
    seen = set()
    for row in rows:
        require(isinstance(row, dict) and isinstance(row.get("path"), str), "Malformed manifest entry")
        relative = PurePosixPath(row["path"])
        require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in row["path"]
                and relative.as_posix() == row["path"] and row["path"] not in seen,
                "Unsafe or duplicated manifest path")
        path = ROOT.joinpath(*relative.parts)
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT),
                "Missing or unsafe manifest source")
        require(type(row.get("bytes")) is int and path.stat().st_size == row["bytes"]
                and sha256(path) == row.get("sha256"), "Source payload differs: " + row["path"])
        seen.add(row["path"])
    required = {path.relative_to(ROOT).as_posix() for path in HERE.glob("*.py")}
    required.update({WORKFLOW, SOURCE, LOCK,
                     (HERE / "PROTOCOL_UK.md").relative_to(ROOT).as_posix(),
                     (HERE / "data/all-configurations.csv").relative_to(ROOT).as_posix(),
                     (HERE / "data/selection.json").relative_to(ROOT).as_posix()})
    require(required.issubset(seen), "The source manifest omits a required execution input")
    require(sha256(ROOT / SOURCE) == SOURCE_SHA256, "Retained source checksum differs")
    return authorization["source_manifest_sha256"]


def admit(output, requested_id):
    context = ci_identity()
    authorization = validate_authorization(read_json(HERE / "resource_authorization.json"), requested_id)
    manifest_sha256 = verify_source(authorization)
    receipt = {
        "schema": "iterative-validation-admission-v1",
        "status": "ADMITTED_FIRST_ANALYSIS",
        "phase": "first_analysis",
        "authorization_id": authorization["authorization_id"],
        "repository": REPOSITORY,
        "ref": REF,
        "source_sha256": SOURCE_SHA256,
        "protocol_sha256": authorization["protocol_sha256"],
        "source_manifest_sha256": manifest_sha256,
        "runner_minutes": RUNNER_MINUTES,
        "workflow_timeout_minutes": WORKFLOW_TIMEOUT_MINUTES,
        "artifact_bytes": ARTIFACT_BYTES,
        "new_search_evaluations": 0,
        "additional_dispatches_authorized": False,
        **context,
    }
    write_json(output, receipt)
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as stream:
            stream.write("source_sha256=" + SOURCE_SHA256 + "\n")
    return receipt


def validate_artifacts(directory):
    ci_identity()
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), "Artifact directory is absent or unsafe")
    resolved = directory.resolve()
    require(resolved.is_relative_to(ROOT) and resolved != ROOT, "Artifact directory must be inside the workspace")
    total = 0
    for path in directory.rglob("*"):
        require(not path.is_symlink() and path.resolve().is_relative_to(resolved), "Unsafe artifact path")
        if path.is_file():
            total += path.stat().st_size
            require(total <= ARTIFACT_BYTES, "Artifact budget exceeded; upload is blocked")
    return {"artifact_bytes": total, "artifact_limit_bytes": ARTIFACT_BYTES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorization-id")
    parser.add_argument("--validate-artifacts", type=Path)
    args = parser.parse_args()
    try:
        if args.validate_artifacts is not None:
            require(args.output is None and args.authorization_id is None, "Choose one admission operation")
            result = validate_artifacts(args.validate_artifacts)
            print(json.dumps(result, sort_keys=True), flush=True)
        else:
            require(args.output is not None and args.authorization_id is not None,
                    "Admission requires an output receipt and authorization identity")
            admit(args.output, args.authorization_id)
            print("ADMITTED_FIRST_ANALYSIS: retained-data analysis only; zero new search evaluations.", flush=True)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print("ADMISSION_FAILED: " + str(error), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

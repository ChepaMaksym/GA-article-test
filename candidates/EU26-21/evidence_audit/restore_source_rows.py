"""Restore historical source-compatible rows from one pinned preservation ZIP.

The original expired ZIP is not downloaded or re-hashed. Its prior verification
record and extracted files are authenticated through the pinned preservation
archive, then every preserved source file is checked against that record.
No optimizer or statistical routine runs in this module. The CLI is CI-only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from common_bridge.fetch_source_artifacts import (
    GitHubReader, HEX64, _file_sha256, _hex, _integer, _load_json, _mapping,
    _require, _safe_member_path, _verify_artifact, _write_json,
)
from evidence_audit.historical import REPOSITORY, SOURCES, seed_rows


PRESERVATION = {
    "id": 10058819094,
    "name": "eu26-21-historical-evidence-34233480959-1",
    "digest": "sha256:fb1f994a68472efe45ad5471d083dc57de94bfe07bda3a3fa186b6b55740f17b",
    "run_id": 34233480959,
    "head_sha": "79c9b154206cdc3d318b90b598c7f0f48ca02b53",
    "run_attempt": 1,
}
SOURCE_MATRIX_RUN_ID = 31934321927
WORKFLOW_PATH = ".github/workflows/eu26-21-historical-evidence-audit.yml"
STATUS_SCHEMA = "eu26-21-source-row-recovery-v1"
MANIFEST_NAME = "historical-audit-manifest.json"
FALSE_FLAGS = (
    "seed_rows_regenerated", "optimizer_rerun", "profiles_pooled",
    "prospective_bridge_included",
)


def validate_preserved_source(root: Path) -> list[dict[str, Any]]:
    """Validate a previously authenticated extraction; return source-file ledger.

    This function alone does not authenticate archive origin. Production callers
    must first verify the fixed outer archive with ``_verify_artifact``.
    """
    manifest_path = root / MANIFEST_NAME
    _require(not manifest_path.is_symlink(), "manifest must not be a symlink")
    manifest = _mapping(_load_json(manifest_path), "preservation manifest")
    _require(manifest.get("schema") == "eu26-21-historical-evidence-audit-v1",
             "preservation schema mismatch")
    _require(manifest.get("repository") == REPOSITORY, "preservation repository mismatch")
    _require(manifest.get("audit_sha") == PRESERVATION["head_sha"], "audit SHA mismatch")
    for field, expected in (("audit_run_id", PRESERVATION["run_id"]),
                            ("audit_run_attempt", PRESERVATION["run_attempt"])):
        _require(_integer(manifest.get(field), field) == expected, f"{field} mismatch")
    for field in FALSE_FLAGS:
        _require(manifest.get(field) is False, f"{field} must be false")
    profiles = _mapping(manifest.get("profiles"), "profiles")
    _require(set(profiles) == set(SOURCES), "preserved profile set mismatch")
    profile = _mapping(profiles["source_compatible"], "source-compatible profile")
    source = SOURCES["source_compatible"]
    identity = _mapping(profile.get("source"), "original source")
    for field in ("id", "run_id"):
        _integer(identity.get(field), f"original source {field}")
    _require(dict(identity) == source, "original source identity mismatch")
    _require(_integer(profile.get("seed_count"), "seed count") == 30,
             "preserved seed count mismatch")
    verification = _mapping(profile.get("verification"), "original verification")
    expected_fields = {
        **{key: source[key] for key in ("id", "name", "digest")},
        "api_run_id": source["run_id"], "api_head_sha": source["head_sha"],
        "downloaded_zip_sha256": source["digest"].split(":", 1)[1],
        "extraction_directory": source["name"],
    }
    for field in ("id", "api_run_id"):
        _integer(verification.get(field), f"original verification {field}")
    for field, expected in expected_fields.items():
        _require(verification.get(field) == expected, f"original verification {field} mismatch")
    entries = verification.get("extracted_files")
    _require(isinstance(entries, list) and bool(entries), "missing preserved file ledger")
    directory = root / source["name"]
    _require(directory.is_dir() and not directory.is_symlink(), "missing source directory")
    ledger: dict[str, dict[str, Any]] = {}
    for value in entries:
        entry = _mapping(value, "preserved file entry")
        _require(set(entry) == {"path", "bytes", "sha256"}, "file entry schema mismatch")
        name = entry["path"]
        _require(isinstance(name, str), "file path must be a string")
        path = _safe_member_path(name)
        _require(path.as_posix() == name, "file path must be canonical")
        _require(len(path.parts) > 1 and path.parts[0] == source["name"],
                 "file path is outside original source profile")
        _require(name not in ledger, "duplicate preserved file path")
        size = _integer(entry["bytes"], "file bytes", minimum=0)
        digest = _hex(entry["sha256"], "file SHA-256", HEX64)
        target = root.joinpath(*path.parts)
        _require(target.is_file() and not target.is_symlink(), f"missing source file: {name}")
        _require(target.stat().st_size == size, f"source file size mismatch: {name}")
        _require(_file_sha256(target) == digest, f"source file SHA mismatch: {name}")
        ledger[name] = {"path": name, "bytes": size, "sha256": digest}
    actual: set[str] = set()
    for path in directory.rglob("*"):
        _require(not path.is_symlink(), "source directory contains a symlink")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
        else:
            _require(path.is_dir(), "source directory contains a non-regular entry")
    _require(actual == set(ledger), "source file inventory mismatch")
    seed_rows(directory)
    return [ledger[name] for name in sorted(ledger)]


def restore_source_rows(api: GitHubReader, *, output_dir: Path,
                        rows_dir: Path) -> dict[str, Any]:
    """Authenticate the fixed archive, validate its source profile, copy rows."""
    _require(not output_dir.exists(), "recovery extraction directory already exists")
    _require(not rows_dir.exists(), "recovered row directory already exists")
    output_dir.mkdir(parents=True)
    run = api.json(
        f"https://api.github.com/repos/{REPOSITORY}/actions/runs/"
        f"{PRESERVATION['run_id']}/attempts/{PRESERVATION['run_attempt']}"
    )
    _require(_integer(run.get("id"), "preservation run ID") == PRESERVATION["run_id"],
             "preservation run mismatch")
    _require(_integer(run.get("run_attempt"), "preservation attempt") == 1,
             "preservation attempt mismatch")
    for field, expected in (("head_sha", PRESERVATION["head_sha"]),
                            ("event", "workflow_dispatch"), ("status", "completed"),
                            ("conclusion", "success"), ("path", WORKFLOW_PATH)):
        _require(run.get(field) == expected, f"preservation run {field} mismatch")
    verification = _verify_artifact(
        api, repository=REPOSITORY, source_run_id=PRESERVATION["run_id"],
        source_head_sha=PRESERVATION["head_sha"],
        expected={key: PRESERVATION[key] for key in ("id", "name", "digest")},
        output_dir=output_dir,
    )
    root = output_dir / PRESERVATION["name"]
    ledger = validate_preserved_source(root)
    source_dir = root / SOURCES["source_compatible"]["name"]
    rows_dir.mkdir(parents=True)
    copied = []
    for path in sorted(source_dir.rglob("seed-*.json")):
        row = _load_json(path)
        destination = rows_dir / f"seed-{row['seed']}.json"
        with destination.open("xb") as handle:
            handle.write(path.read_bytes())
        digest = _file_sha256(destination)
        _require(digest == _file_sha256(path), "copied seed bytes changed")
        copied.append({"seed": row["seed"], "source_path": path.relative_to(root).as_posix(),
                       "path": destination.name, "sha256": digest,
                       "bytes": destination.stat().st_size})
    seed_rows(rows_dir)
    return {
        "schema": STATUS_SCHEMA, "verification_status": "PASS",
        "repository": REPOSITORY, "source_matrix_run_id": SOURCE_MATRIX_RUN_ID,
        "original_source": SOURCES["source_compatible"],
        "original_zip_reverified": False,
        "original_verification_basis": "pinned_preservation_zip_and_preserved_file_ledger",
        "preservation": PRESERVATION, "preservation_verification": verification,
        "preservation_manifest_sha256": _file_sha256(root / MANIFEST_NAME),
        "source_files_verified": ledger, "seed_count": 30,
        "copied_seed_files": sorted(copied, key=lambda item: item["seed"]),
        **{field: False for field in FALSE_FLAGS},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rows-dir", type=Path, required=True)
    parser.add_argument("--status-json", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("source-row recovery is CI-only")
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise SystemExit("source-row recovery repository mismatch")
    try:
        api = GitHubReader(os.environ.get("GH_TOKEN", ""))
        result = restore_source_rows(
            api, output_dir=args.output_dir.resolve(), rows_dir=args.rows_dir.resolve(),
        )
        result["recovery_commit_sha"] = os.environ["GITHUB_SHA"]
        result["recovery_run_id"] = int(os.environ["GITHUB_RUN_ID"])
        _write_json(args.status_json, result)
        print("PASS: 30 preserved source-compatible rows authenticated and copied")
    except Exception as exc:
        failure = {
            "schema": STATUS_SCHEMA, "verification_status": "FAIL",
            "repository": REPOSITORY, "preservation": PRESERVATION,
            "original_source": SOURCES["source_compatible"],
            "source_matrix_run_id": SOURCE_MATRIX_RUN_ID,
            "original_zip_reverified": False, "optimizer_rerun": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        _write_json(args.status_json, failure)
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

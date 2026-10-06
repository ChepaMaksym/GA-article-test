"""Deterministic metadata-only source selection after infrastructure retries.

Choose the highest uploaded workflow attempt for each registered case/pair.
An upload can contain a failure status: download and manifest validation must
then fail closed. This selector never opens scientific outcome artifacts and
never falls back to an older attempt because the newest outcome is unwanted.
The untouched raw API ledger is retained separately by the workflow.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Any, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from local_optima_study.contract import (
    CASE_SEEDS, PROTOCOL_SHA256, REGISTRY_SCHEMA,
    canonical_sha256, file_sha256, hex_digest, read_json, require, write_json,
)


def _expected_keys(
    kind: str,
    *,
    registry: Mapping[str, Any] | None,
    expected_sha: str,
    source_run_id: int,
) -> list[tuple[int, ...]]:
    require(kind in ("case", "escape"), "artifact kind must be case or escape")
    if kind == "case":
        require(registry is None, "case source selection does not accept an escape registry")
        return [(seed,) for seed in CASE_SEEDS]
    require(registry is not None, "escape source selection requires the frozen registry")
    require(registry["schema"] == REGISTRY_SCHEMA, "registry schema mismatch")
    require(registry["implementation_sha"] == expected_sha, "registry implementation SHA mismatch")
    require(registry["source_run_id"] == source_run_id, "registry source run mismatch")
    require(registry["protocol_sha256"] == PROTOCOL_SHA256, "registry protocol hash mismatch")
    require(registry["all_case_records_frozen"] == 30 and registry["escape_outcomes_inspected"] is False,
            "escape registry was not frozen before outcomes")
    cases = registry["cases"]
    require(isinstance(cases, list) and len(cases) == 30, "registry case count is not 30")
    seeds: set[int] = set()
    eligible = []
    for case in cases:
        seed = case["seed"]
        require(type(seed) is int and seed in CASE_SEEDS and seed not in seeds,
                "registry contains a wrong or duplicate case seed")
        require(type(case["eligible"]) is bool, "registry eligibility must be boolean")
        seeds.add(seed)
        if case["eligible"]:
            eligible.append(seed)
    require(seeds == set(CASE_SEEDS), "registry seed completeness is not 30/30")
    return [(seed, repeat) for seed in sorted(eligible) for repeat in range(1, 6)]


def select_artifacts(
    raw_ledger: Mapping[str, Any],
    *,
    kind: str,
    expected_sha: str,
    source_run_id: int,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate every retained upload identity, then choose by attempt only."""
    hex_digest(expected_sha, "implementation SHA", 40)
    require(type(source_run_id) is int and source_run_id > 0, "invalid source run ID")
    keys = _expected_keys(kind, registry=registry, expected_sha=expected_sha, source_run_id=source_run_id)
    expected = set(keys)
    require(isinstance(raw_ledger, dict) and isinstance(raw_ledger.get("artifacts"), list),
            "invalid raw source artifact ledger")
    integer = r"([1-9][0-9]*)"
    pattern = re.compile(
        rf"eu26-21-local-case-{integer}-{integer}-{integer}"
        if kind == "case" else
        rf"eu26-21-local-escape-{integer}-{integer}-{integer}-{integer}"
    )
    by_key: dict[tuple[int, ...], dict[int, dict[str, Any]]] = {}
    identities: set[int] = set()
    names: set[str] = set()
    for artifact in raw_ledger["artifacts"]:
        require(isinstance(artifact, dict), "artifact API row must be an object")
        name = artifact.get("name")
        require(isinstance(name, str), "artifact name must be a string")
        match = pattern.fullmatch(name)
        require(match is not None, "artifact name is outside the registered namespace")
        numbers = tuple(int(part) for part in match.groups())
        key = numbers[:1] if kind == "case" else numbers[:2]
        run_id, attempt = numbers[-2:]
        require(key in expected, "artifact key is not an expected registered case or pair")
        require(run_id == source_run_id, "artifact name belongs to another workflow run")
        identity = artifact.get("id")
        require(type(identity) is int and identity > 0, "invalid source artifact ID")
        require(identity not in identities and name not in names, "duplicate source artifact ID or name")
        require(artifact.get("expired") is False, "source artifact expired or expiry status missing")
        size = artifact.get("size_in_bytes")
        require(type(size) is int and size > 0, "source artifact size missing or invalid")
        digest = artifact.get("digest")
        require(isinstance(digest, str) and digest.startswith("sha256:"), "source artifact digest missing")
        hex_digest(digest[len("sha256:"):], "artifact SHA-256")
        workflow = artifact.get("workflow_run")
        require(isinstance(workflow, dict), "artifact workflow identity missing")
        require(type(workflow.get("id")) is int and workflow["id"] == source_run_id
                and workflow.get("head_sha") == expected_sha, "artifact workflow run or head SHA mismatch")
        attempts = by_key.setdefault(key, {})
        require(attempt not in attempts, "duplicate artifact upload for the same key and attempt")
        attempts[attempt] = artifact
        identities.add(identity)
        names.add(name)
    require(set(by_key) == expected, "missing expected source artifact case or pair")
    selected = [by_key[key][max(by_key[key])] for key in keys]
    selected_ids = {artifact["id"] for artifact in selected}
    discarded = [artifact for artifact in raw_ledger["artifacts"] if artifact["id"] not in selected_ids]
    return {
        "artifacts": selected,
        "selection": {
            "schema": "eu26-21-local-optima-artifact-selection-v1", "kind": kind,
            "policy": "highest_uploaded_attempt_per_registered_key_no_outcome_inspection",
            "implementation_sha": expected_sha, "source_run_id": source_run_id,
            "raw_ledger_sha256": canonical_sha256(raw_ledger),
            "expected_key_count": len(keys), "selected_count": len(selected),
            "raw_upload_count": len(raw_ledger["artifacts"]),
            "selected_artifact_ids": [artifact["id"] for artifact in selected],
            "superseded_artifacts": [
                {field: artifact[field] for field in ("id", "name", "digest")}
                for artifact in sorted(discarded, key=lambda row: row["name"])
            ],
            "scientific_artifacts_opened": False,
            "latest_artifact_still_requires_manifest_validation": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-ledger", type=Path, required=True)
    parser.add_argument("--kind", choices=("case", "escape"), required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    parser.add_argument("--output-ledger", type=Path, required=True)
    parser.add_argument("--output-ids", type=Path, required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--registry-sha256")
    args = parser.parse_args()
    registry = None
    if args.kind == "escape":
        require(args.registry is not None and args.registry_sha256 is not None,
                "escape selection needs the registry and its frozen digest")
        hex_digest(args.registry_sha256, "registry SHA-256")
        require(file_sha256(args.registry) == args.registry_sha256, "registry byte digest mismatch")
        registry = read_json(args.registry)
    else:
        require(args.registry is None and args.registry_sha256 is None,
                "case selection must not receive an escape registry")
    require(args.raw_ledger.resolve() not in (args.output_ledger.resolve(), args.output_ids.resolve()),
            "raw full artifact ledger must not be overwritten")
    require(args.output_ledger.resolve() != args.output_ids.resolve(), "output paths must differ")
    result = select_artifacts(read_json(args.raw_ledger), kind=args.kind,
                              expected_sha=args.expected_sha, source_run_id=args.source_run_id,
                              registry=registry)
    result["selection"]["raw_ledger_file_sha256"] = file_sha256(args.raw_ledger)
    write_json(args.output_ledger, result)
    args.output_ids.write_text(
        ",".join(str(artifact["id"]) for artifact in result["artifacts"]) + "\n", encoding="utf-8",
    )
    print(f"PASS_PINNED_{args.kind.upper()}_ARTIFACT_SELECTION count={len(result['artifacts'])}")


if __name__ == "__main__":
    main()

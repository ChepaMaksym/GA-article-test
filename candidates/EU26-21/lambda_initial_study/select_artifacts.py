"""Metadata-only selection; never choose a retry by scientific outcome."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

from lambda_initial_study.contract import (
    CASE_SEEDS, PROTOCOL_SHA256, canonical_sha256, file_sha256,
    read_json, require, write_json,
)


def select_artifacts(raw: dict, *, run_id: int, expected_sha: str) -> dict:
    require(re.fullmatch(r"[0-9a-f]{40}", expected_sha) is not None, "invalid implementation SHA")
    require(type(run_id) is int and run_id > 0, "invalid run ID")
    require(isinstance(raw, dict) and isinstance(raw.get("artifacts"), list), "invalid API metadata")
    grouped, ids, names = {}, set(), set()
    for artifact in raw["artifacts"]:
        match = re.fullmatch(r"eu26-21-lambda-case-([1-9][0-9]*)-([1-9][0-9]*)-([1-9][0-9]*)",
                             artifact.get("name", ""))
        require(match is not None, "unregistered artifact namespace")
        seed, named_run, attempt = map(int, match.groups())
        require(seed in CASE_SEEDS and named_run == run_id, "wrong artifact seed or run")
        identity = artifact.get("id")
        require(type(identity) is int and identity > 0 and identity not in ids
                and artifact["name"] not in names, "duplicate or invalid artifact identity")
        require(artifact.get("expired") is False, "expired artifact")
        require(type(artifact.get("size_in_bytes")) is int and artifact["size_in_bytes"] > 0,
                "invalid artifact size")
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", artifact.get("digest", "")) is not None,
                "missing artifact SHA256")
        source = artifact.get("workflow_run", {})
        require(source.get("id") == run_id and source.get("head_sha") == expected_sha,
                "wrong artifact implementation SHA or run")
        uploads = grouped.setdefault(seed, {})
        require(attempt not in uploads, "duplicate upload within one attempt")
        uploads[attempt] = artifact
        ids.add(identity)
        names.add(artifact["name"])
    require(set(grouped) == set(CASE_SEEDS), "source completeness is not 30/30")
    selected = [grouped[seed][max(grouped[seed])] for seed in CASE_SEEDS]
    return {"schema": "eu26-21-lambda-initial-source-ledger-v1",
            "source_run_id": run_id, "implementation_sha": expected_sha,
            "protocol_sha256": PROTOCOL_SHA256, "artifacts": selected,
            "attempts": raw["artifacts"], "raw_metadata_sha256": canonical_sha256(raw),
            "selection_policy": "highest_uploaded_attempt_per_seed_no_outcome_inspection",
            "scientific_artifacts_opened": False,
            "latest_artifact_still_requires_manifest_validation": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-metadata", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(args.api_metadata.resolve() != args.output.resolve(), "cannot overwrite raw API metadata")
    selected = select_artifacts(read_json(args.api_metadata), run_id=args.run_id, expected_sha=args.expected_sha)
    selected["raw_metadata_file_sha256"] = file_sha256(args.api_metadata)
    write_json(args.output, selected)
    print("PASS_METADATA_ONLY_30_CASE_SELECTION")


if __name__ == "__main__":
    main()

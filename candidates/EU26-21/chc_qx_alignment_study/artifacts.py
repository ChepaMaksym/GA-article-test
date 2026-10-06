"""Metadata-only source selection and immutable preparation registration."""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import re

from chc_qx_alignment_study.contract import (
    CASE_SEEDS, PROTOCOL_ID, PROTOCOL_SHA256, canonical_sha256,
    file_sha256, read_json, require, verify_manifest, write_json,
)


def select_sources(raw: dict, *, run_id: int, expected_sha: str, kind: str) -> dict:
    require(kind in ("preparation", "case"), "unsupported source kind")
    require(type(run_id) is int and run_id > 0
            and re.fullmatch(r"[0-9a-f]{40}", expected_sha) is not None, "invalid run identity")
    require(isinstance(raw, dict) and isinstance(raw.get("artifacts"), list), "invalid API ledger")
    grouped, ids, names = {}, set(), set()
    for artifact in raw["artifacts"]:
        match = re.fullmatch(rf"eu26-21-qx-{kind}-([1-9][0-9]*)-([1-9][0-9]*)-([1-9][0-9]*)",
                             artifact.get("name", ""))
        require(match is not None, "unexpected artifact namespace")
        seed, named_run, attempt = map(int, match.groups())
        require(seed in CASE_SEEDS and named_run == run_id, "unexpected seed or run")
        identity = artifact.get("id")
        require(type(identity) is int and identity > 0 and identity not in ids
                and artifact["name"] not in names, "duplicate artifact identity")
        require(artifact.get("expired") is False
                and type(artifact.get("size_in_bytes")) is int and artifact["size_in_bytes"] > 0,
                "expired or empty artifact")
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", artifact.get("digest", "")) is not None,
                "artifact digest missing")
        source = artifact.get("workflow_run", {})
        require(source.get("id") == run_id and source.get("head_sha") == expected_sha,
                "artifact SHA mismatch")
        uploads = grouped.setdefault(seed, {})
        require(attempt not in uploads, "duplicate upload within an attempt")
        uploads[attempt] = artifact
        ids.add(identity)
        names.add(artifact["name"])
    require(set(grouped) == set(CASE_SEEDS), "source completeness is not 30/30")
    return {"schema": "eu26-21-qx-source-ledger-v1", "kind": kind,
            "source_run_id": run_id, "implementation_sha": expected_sha,
            "protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
            "artifacts": [grouped[seed][max(grouped[seed])] for seed in CASE_SEEDS],
            "attempts": raw["artifacts"], "raw_metadata_sha256": canonical_sha256(raw),
            "selection_policy": "highest_uploaded_attempt_per_seed_without_opening_results"}


def validate_transport(sources: dict, transport: dict) -> None:
    require(transport.get("complete") is True
            and transport.get("source_run_id") == sources["source_run_id"]
            and transport.get("implementation_sha") == sources["implementation_sha"],
            "transport identity mismatch")
    verified = {row["id"]: row for row in transport["artifacts"]}
    require(len(verified) == len(transport["artifacts"]) == 30
            and set(verified) == {row["id"] for row in sources["artifacts"]},
            "transport completeness mismatch")
    for row in sources["artifacts"]:
        proof = verified[row["id"]]
        require(proof["zip_verified_before_extraction"] is True
                and proof["name"] == row["name"] and proof["digest"] == row["digest"]
                and proof["verified_zip_sha256"] == row["digest"].removeprefix("sha256:")
                and proof["verified_zip_bytes"] == row["size_in_bytes"],
                "source ZIP was not authenticated")


def validate_upload_identity(manifest: dict, source: dict, *, kind: str,
                             seed: int, expected_sha: str, run_id: int) -> None:
    """Bind embedded provenance to the selected upload, including its attempt."""
    provenance = manifest["provenance"]
    require(type(provenance["run_attempt"]) is int and provenance["run_attempt"] > 0,
            "embedded upload attempt invalid")
    name = f"eu26-21-qx-{kind}-{seed}-{run_id}-{provenance['run_attempt']}"
    require(source["name"] == manifest["artifact_name"] == name
            and manifest["seed"] == seed and provenance["run_id"] == run_id
            and provenance["implementation_sha"] == expected_sha
            and source["workflow_run"]["id"] == run_id
            and source["workflow_run"]["head_sha"] == expected_sha,
            "selected upload and embedded source identity differ")


def build_registry(root: Path, sources: dict, transport: dict) -> dict:
    require(sources["kind"] == "preparation", "registry requires preparation sources")
    validate_transport(sources, transport)
    cases = []
    for seed, source in zip(CASE_SEEDS, sources["artifacts"]):
        path = root / source["name"] / "preparation.json"
        require(path.is_file() and not path.is_symlink(), "missing preparation")
        manifest = verify_manifest(path.parent / "manifest.json", expected_sha=sources["implementation_sha"])
        validate_upload_identity(manifest, source, kind="preparation", seed=seed,
                                 expected_sha=sources["implementation_sha"], run_id=sources["source_run_id"])
        require(manifest["artifact_name"] == source["name"] and manifest["seed"] == seed
                and manifest["row_file"] == "preparation.json", "preparation manifest identity mismatch")
        row = read_json(path)
        require(row["seed"] == seed and row["schema"] == "eu26-21-qx-preparation-v1"
                and row["provenance"] == manifest["provenance"]
                and row["provenance"]["protocol_id"] == PROTOCOL_ID
                and row["provenance"]["implementation_sha"] == sources["implementation_sha"]
                and row["provenance"]["protocol_sha256"] == PROTOCOL_SHA256,
                "preparation identity mismatch")
        require(row["status"] in ("PASS_PREPARATION", "NOT_EVALUABLE_SAMPLER"),
                "incomplete preparation cannot be frozen")
        cases.append({"seed": seed, "status": row["status"],
                      "preparation": {"sha256": file_sha256(path), "bytes": path.stat().st_size},
                      "source_run_id": sources["source_run_id"], "source_artifact_id": source["id"],
                      "source_artifact_name": source["name"], "source_artifact_digest": source["digest"]})
    return {"schema": "eu26-21-qx-frozen-preparation-registry-v1",
            "protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
            "implementation_sha": sources["implementation_sha"],
            "source_run_id": sources["source_run_id"], "cases": cases,
            "sources_sha256": canonical_sha256(sources),
            "transport_sha256": canonical_sha256(transport),
            "all_30_accounted": True, "frozen_before_main_search": True,
            "retry_policy": "reuse_exact_registered_preparation_never_rerun_successful_preparation"}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    select = sub.add_parser("select")
    select.add_argument("--api-metadata", type=Path, required=True)
    select.add_argument("--run-id", type=int, required=True)
    select.add_argument("--expected-sha", required=True)
    select.add_argument("--kind", choices=("preparation", "case"), required=True)
    select.add_argument("--output", type=Path, required=True)
    registry = sub.add_parser("registry")
    registry.add_argument("--root", type=Path, required=True)
    registry.add_argument("--sources", type=Path, required=True)
    registry.add_argument("--transport-ledger", type=Path, required=True)
    registry.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(os.environ.get("GITHUB_ACTIONS") == "true", "registration is CI-only")
    if args.command == "select":
        result = select_sources(read_json(args.api_metadata), run_id=args.run_id,
                                expected_sha=args.expected_sha, kind=args.kind)
        require(args.api_metadata.resolve() != args.output.resolve(), "raw ledger overwrite")
        result["raw_metadata_file_sha256"] = file_sha256(args.api_metadata)
    else:
        sources = read_json(args.sources)
        result = build_registry(args.root, sources, read_json(args.transport_ledger))
        # Timed selection cannot be reconstructed from a seed after artifact
        # expiry. Retain every original preparation byte, not just its hash.
        packed_path = args.output.parent / "frozen-preparations.json.gz"
        require(not packed_path.exists(), "frozen preparation archive already exists")
        records = []
        for seed, source in zip(CASE_SEEDS, sources["artifacts"]):
            path = args.root / source["name"] / "preparation.json"
            raw = path.read_bytes()
            records.append({"seed": seed, "original_sha256": file_sha256(path),
                            "bytes": len(raw), "original_utf8": raw.decode("utf-8")})
        packed_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"schema": "eu26-21-qx-original-preparations-v1", "records": records},
                             sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
        with packed_path.open("xb") as stream:
            stream.write(gzip.compress(payload, compresslevel=9, mtime=0))
        result["frozen_preparations"] = {"file": packed_path.name, "sha256": file_sha256(packed_path),
                                         "bytes": packed_path.stat().st_size}
    require(not args.output.exists(), "registry or source ledger must be immutable")
    write_json(args.output, result)
    print("PASS_30_SOURCE_IDENTITIES")


if __name__ == "__main__":
    main()

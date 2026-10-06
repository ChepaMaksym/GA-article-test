"""Metadata-only source selection and authenticated low-start registration.

Selection never opens an experimental result and never ranks uploads by their
score. The latest uploaded attempt for each registered seed is retained; its
contents must subsequently pass the same proof checks as any other upload.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from corrected_applied.data_protocol import TRANSFORMED_FEATURE_NAMES, TRANSFORMED_PREDICTIVE_RAW_INDICES
from lambda_response_study.contract import (
    CASE_SEEDS, PROTOCOL_ID, PROTOCOL_SHA256,
    canonical_sha256, file_sha256, read_json, require, validate_preparation, validate_protocol, verify_manifest, write_json,
)


SOURCE_SCHEMA = "eu26-21-lr-source-ledger-v1"
PREPARATION_SCHEMA = "eu26-21-lr-preparation-v1"
REGISTRY_SCHEMA = "eu26-21-lr-registry-v1"


def validate_preparation_metadata(metadata: dict, *, seed: int) -> None:
    protocol = validate_protocol()
    require(metadata["schema"] == "eu26-21-qx-training-only-data-v1"
            and metadata["seed"] == seed and metadata["feature_names"] == list(TRANSFORMED_FEATURE_NAMES)
            and metadata["transformed_raw_indices"] == list(TRANSFORMED_PREDICTIVE_RAW_INDICES)
            and 24 not in metadata["transformed_raw_indices"], "feature-bit order or weight exclusion invalid")
    require(metadata["train_file_sha256"] == protocol["data"]["train_sha256"]
            and metadata["train_file_rows"] == 199523
            and metadata["train_partition_rows"] == 159618
            and metadata["validation_partition_rows"] == 39905
            and metadata["split_seed"] == 2026081700 + seed, "training file or corrected split mismatch")
    require(metadata["test_arrays_loaded"] is False
            and metadata["instance_weight_as_predictor"] is False
            and metadata["instance_weight_as_sample_weight"] is True
            and metadata["preprocessing_fit_scope"] == "internal_training_only", "test or weight leakage")
    arrays = metadata["array_hashes"]
    require(set(arrays) == {"x_train", "y_train", "weight_train", "x_validation", "y_validation", "weight_validation",
                            "train_raw_indices", "validation_raw_indices"}
            and all(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                    for digest in arrays.values()), "training arrays or split hashes absent")
    for name, count in (("train_positive_count", 159618), ("validation_positive_count", 39905)):
        require(type(metadata[name]) is int and 0 < metadata[name] < count, "both training/validation classes required")


def select_sources(raw: dict, *, run_id: int, expected_sha: str, kind: str) -> dict:
    require(kind in ("preparation", "case"), "unsupported source kind")
    require(type(run_id) is int and run_id > 0
            and isinstance(expected_sha, str)
            and re.fullmatch(r"[0-9a-f]{40}", expected_sha) is not None,
            "invalid run identity")
    require(isinstance(raw, dict) and isinstance(raw.get("artifacts"), list), "invalid API ledger")
    grouped, ids, names = {}, set(), set()
    for artifact in raw["artifacts"]:
        require(isinstance(artifact, dict), "artifact metadata is not an object")
        name = artifact.get("name")
        require(isinstance(name, str), "invalid artifact name")
        match = re.fullmatch(
            rf"eu26-21-lr-{kind}-([1-9][0-9]*)-([1-9][0-9]*)-([1-9][0-9]*)", name)
        require(match is not None, "unexpected artifact namespace")
        seed, named_run, attempt = map(int, match.groups())
        require(seed in CASE_SEEDS and named_run == run_id, "unexpected seed or run")
        identity = artifact.get("id")
        require(type(identity) is int and identity > 0 and identity not in ids
                and name not in names, "duplicate artifact identity")
        require(artifact.get("expired") is False
                and type(artifact.get("size_in_bytes")) is int
                and 0 < artifact["size_in_bytes"] <= 2 * 1024**3,
                "expired, invalid or empty artifact")
        digest = artifact.get("digest")
        require(isinstance(digest, str)
                and re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is not None,
                "artifact digest missing")
        source = artifact.get("workflow_run")
        require(isinstance(source, dict) and type(source.get("id")) is int
                and source["id"] == run_id and source.get("head_sha") == expected_sha,
                "artifact SHA mismatch")
        uploads = grouped.setdefault(seed, {})
        require(attempt not in uploads, "duplicate upload within an attempt")
        uploads[attempt] = {**artifact, "seed": seed, "source_run_id": run_id,
                            "implementation_sha": expected_sha, "run_attempt": attempt}
        ids.add(identity)
        names.add(name)
    require(set(grouped) == set(CASE_SEEDS), "source completeness is not 30/30")
    selected = [grouped[seed][max(grouped[seed])] for seed in CASE_SEEDS]
    return {"schema": SOURCE_SCHEMA, "kind": kind, "source_run_id": run_id,
            "implementation_sha": expected_sha, "protocol_id": PROTOCOL_ID,
            "protocol_sha256": PROTOCOL_SHA256, "artifacts": selected,
            "attempts": raw["artifacts"], "raw_metadata": raw,
            "raw_metadata_sha256": canonical_sha256(raw),
            "selection_policy": "highest_uploaded_attempt_per_seed_without_opening_results",
            "scientific_results_opened_for_selection": False}


def validate_sources(sources: dict, *, kind: str, expected_sha: str | None = None) -> None:
    require(isinstance(sources, dict) and sources.get("schema") == SOURCE_SCHEMA
            and sources.get("kind") == kind and sources.get("protocol_id") == PROTOCOL_ID
            and sources.get("protocol_sha256") == PROTOCOL_SHA256,
            "source ledger schema or protocol mismatch")
    require(sources.get("scientific_results_opened_for_selection") is False
            and sources.get("selection_policy") ==
            "highest_uploaded_attempt_per_seed_without_opening_results", "source selection policy mismatch")
    require(sources["raw_metadata"]["artifacts"] == sources["attempts"], "retained metadata differs from attempts")
    rebuilt = select_sources(sources["raw_metadata"], run_id=sources["source_run_id"],
                             expected_sha=sources["implementation_sha"], kind=kind)
    require(sources["artifacts"] == rebuilt["artifacts"]
            and sources["raw_metadata_sha256"] == rebuilt["raw_metadata_sha256"],
            "source selection differs from retained metadata")
    if expected_sha is not None:
        require(sources["implementation_sha"] == expected_sha, "source ledger implementation SHA mismatch")


def validate_transport(sources: dict, transport: dict) -> None:
    validate_sources(sources, kind=sources["kind"])
    require(isinstance(transport, dict) and transport.get("complete") is True
            and transport.get("source_run_id") == sources["source_run_id"]
            and transport.get("implementation_sha") == sources["implementation_sha"]
            and transport.get("kind") == "lr-" + sources["kind"], "transport identity mismatch")
    require(isinstance(transport.get("artifacts"), list), "transport artifacts missing")
    verified = {row["id"]: row for row in transport["artifacts"]}
    require(len(verified) == len(transport["artifacts"]) == len(CASE_SEEDS)
            and set(verified) == {row["id"] for row in sources["artifacts"]},
            "transport completeness mismatch")
    for row in sources["artifacts"]:
        proof = verified[row["id"]]
        require(proof["zip_verified_before_extraction"] is True
                and proof["name"] == row["name"] and proof["digest"] == row["digest"]
                and proof["verified_zip_sha256"] == row["digest"].removeprefix("sha256:")
                and proof["verified_zip_bytes"] == row["size_in_bytes"]
                and proof["size_in_bytes"] == row["size_in_bytes"],
                "source ZIP was not authenticated")


def validate_upload_identity(manifest: dict, source: dict, *, kind: str,
                             seed: int, expected_sha: str, run_id: int) -> None:
    provenance = manifest["provenance"]
    require(type(provenance["run_attempt"]) is int and provenance["run_attempt"] > 0,
            "embedded upload attempt invalid")
    name = f"eu26-21-lr-{kind}-{seed}-{run_id}-{provenance['run_attempt']}"
    require(source["name"] == manifest["artifact_name"] == name
            and source["seed"] == manifest["seed"] == seed
            and source["run_attempt"] == provenance["run_attempt"]
            and source["source_run_id"] == provenance["run_id"] == run_id
            and source["implementation_sha"] == provenance["implementation_sha"] == expected_sha
            and source["workflow_run"]["id"] == run_id
            and source["workflow_run"]["head_sha"] == expected_sha,
            "selected upload and embedded source identity differ")


def build_registry(root: Path, sources: dict, transport: dict) -> dict:
    validate_sources(sources, kind="preparation")
    validate_transport(sources, transport)
    cases = []
    for seed, source in zip(CASE_SEEDS, sources["artifacts"]):
        path = root / source["name"] / "preparation.json"
        require(path.is_file() and not path.is_symlink(), "missing preparation")
        manifest = verify_manifest(path.parent / "manifest.json", expected_sha=sources["implementation_sha"])
        validate_upload_identity(manifest, source, kind="preparation", seed=seed,
                                 expected_sha=sources["implementation_sha"], run_id=sources["source_run_id"])
        require(manifest["row_file"] == "preparation.json", "preparation manifest identity mismatch")
        raw = path.read_bytes()
        row = read_json(path)
        require(row["seed"] == seed and row["schema"] == PREPARATION_SCHEMA
                and row["provenance"] == manifest["provenance"]
                and row["provenance"]["protocol_id"] == PROTOCOL_ID
                and row["provenance"]["implementation_sha"] == sources["implementation_sha"]
                and row["provenance"]["protocol_sha256"] == PROTOCOL_SHA256,
                "preparation identity mismatch")
        require(row["status"] == "PASS_PREPARATION", "incomplete preparation cannot be frozen")
        validate_preparation(row, seed=seed, expected_sha=sources["implementation_sha"])
        validate_preparation_metadata(row["training_data"], seed=seed)
        cases.append({"seed": seed, "status": row["status"],
                      "preparation": {"sha256": file_sha256(path), "bytes": len(raw)},
                      "source_run_id": sources["source_run_id"], "source_artifact_id": source["id"],
                      "source_artifact_name": source["name"], "source_artifact_digest": source["digest"],
                      "payload": row, "original_preparation_utf8": raw.decode("utf-8")})
    return {"schema": REGISTRY_SCHEMA, "protocol_id": PROTOCOL_ID,
            "protocol_sha256": PROTOCOL_SHA256, "implementation_sha": sources["implementation_sha"],
            "source_run_id": sources["source_run_id"], "cases": cases,
            "sources_sha256": canonical_sha256(sources), "transport_sha256": canonical_sha256(transport),
            "all_30_accounted": True, "frozen_before_main_search": True,
            "retry_policy": "reuse_exact_registered_preparation_never_rerun_successful_preparation"}


def validate_registry(registry: dict, *, expected_sha: str) -> dict[int, dict]:
    require(registry.get("schema") == REGISTRY_SCHEMA
            and registry.get("protocol_id") == PROTOCOL_ID
            and registry.get("protocol_sha256") == PROTOCOL_SHA256
            and registry.get("implementation_sha") == expected_sha
            and registry.get("all_30_accounted") is True
            and registry.get("frozen_before_main_search") is True,
            "registry identity or freeze mismatch")
    entries = registry["cases"]
    require(len(entries) == 30 and [entry["seed"] for entry in entries] == list(CASE_SEEDS),
            "registry completeness is not 30/30")
    ids, names, records = set(), set(), {}
    for entry in entries:
        seed, identity = entry["seed"], entry["preparation"]
        raw = entry["original_preparation_utf8"].encode("utf-8")
        require(type(identity["bytes"]) is int and identity["bytes"] > 0
                and len(raw) == identity["bytes"]
                and hashlib.sha256(raw).hexdigest() == identity["sha256"],
                "registered original preparation byte identity mismatch")
        row = json.loads(raw)
        require(row == entry["payload"] and row["schema"] == PREPARATION_SCHEMA
                and row["seed"] == seed and row["status"] == entry["status"] == "PASS_PREPARATION",
                "registered preparation record mismatch")
        validate_preparation(row, seed=seed, expected_sha=expected_sha)
        validate_preparation_metadata(row["training_data"], seed=seed)
        artifact_id = entry["source_artifact_id"]
        require(type(artifact_id) is int and artifact_id > 0 and artifact_id not in ids,
                "registry artifact ID duplicated or invalid")
        name = entry["source_artifact_name"]
        require(isinstance(name, str) and name not in names, "registry artifact name duplicated")
        provenance = row["provenance"]
        named = f"eu26-21-lr-preparation-{seed}-{registry['source_run_id']}-{provenance['run_attempt']}"
        require(name == named and entry["source_run_id"] == registry["source_run_id"]
                == provenance["run_id"] and provenance["implementation_sha"] == expected_sha
                and provenance["workflow_sha"] == expected_sha
                and provenance["protocol_id"] == PROTOCOL_ID
                and provenance["protocol_sha256"] == PROTOCOL_SHA256,
                "registered preparation source identity mismatch")
        require(isinstance(entry["source_artifact_digest"], str)
                and re.fullmatch(r"sha256:[0-9a-f]{64}", entry["source_artifact_digest"]) is not None,
                "registered source ZIP digest missing")
        ids.add(artifact_id)
        names.add(name)
        records[seed] = row
    return records


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
    require(not args.output.exists() and not args.output.is_symlink(), "registry or source ledger must be immutable")
    if args.command == "select":
        result = select_sources(read_json(args.api_metadata), run_id=args.run_id,
                                expected_sha=args.expected_sha, kind=args.kind)
        require(args.api_metadata.resolve() != args.output.resolve(), "raw ledger overwrite")
        result["raw_metadata_file_sha256"] = file_sha256(args.api_metadata)
    else:
        result = build_registry(args.root, read_json(args.sources), read_json(args.transport_ledger))
        validate_registry(result, expected_sha=result["implementation_sha"])
    write_json(args.output, result)
    print("PASS_30_SOURCE_IDENTITIES")


if __name__ == "__main__":
    main()

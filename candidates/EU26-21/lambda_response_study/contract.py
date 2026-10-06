"""Identity gates and exact-byte evidence for a prospective mechanism check."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from chc_qx_alignment_study.contract import (
    canonical_sha256, ensure_empty_output, file_sha256, git, git_blob,
    read_json, require, runtime_environment, validate_mask, write_json,
)

THIS_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = THIS_DIRECTORY.parents[2]
PROTOCOL_ID = "EU26-21-LAMBDA-RESPONSE-LOW-START-V1"
PROTOCOL_SHA256 = "49ebc9efd860c680e2026f94c9be2fd919abef9acfdbd5498c1a6669911f8cf1"
REGISTRATION_SHA = "ab4a430c00856174957a5ab829ae2b688efbeeb8"
KERNEL_SHA = "d5efb490531a0aa6f650a4e0152d274b1775cacb"
CASE_SEEDS = tuple(range(45001, 45031))
PROBLEMS = ("onemax", "census")
ARMS = ("adaptive", "fixed10")
REUSED_FILES = (
    "hybrid_1/core.py", "local_optima/generation.py",
    "corrected_applied/data_protocol.py", "corrected_applied/requirements.txt",
    "common_bridge/model_evidence.py", "common_bridge/run_seed.py",
    "local_optima_study/contract.py", "chc_qx_alignment_study/data.py",
    "chc_qx_alignment_study/contract.py", "chc_qx_alignment_study/run_case.py",
)

def validate_protocol(path: Path = THIS_DIRECTORY / "protocol.json") -> dict:
    require(not path.is_symlink() and file_sha256(path) == PROTOCOL_SHA256, "protocol byte identity changed")
    value = read_json(path)
    require(value["schema"] == "eu26-21-lambda-response-protocol-v1"
            and value["protocol_id"] == PROTOCOL_ID, "wrong registered protocol")
    require(value["rng"]["case_seeds"] == list(CASE_SEEDS)
            and value["search"]["arms"] == list(ARMS)
            and value["search"]["generations"] == 20 and value["search"]["reset"] is False,
            "registered seed, arm or generation contract changed")
    return value

def authenticate(expected_sha: str) -> tuple[dict, dict]:
    protocol = validate_protocol()
    require(os.environ.get("GITHUB_ACTIONS") == "true", "scientific execution is CI-only")
    require(isinstance(expected_sha, str) and re.fullmatch(r"[0-9a-f]{40}", expected_sha) is not None,
            "exact SHA required")
    require(os.environ.get("GITHUB_SHA") == os.environ.get("STUDY_WORKFLOW_SHA") == git("rev-parse", "HEAD") == expected_sha,
            "workflow and scientific source SHA must coincide")
    result = subprocess.run(["git", "-C", str(REPOSITORY_ROOT), "merge-base", "--is-ancestor",
                             REGISTRATION_SHA, expected_sha], check=False, capture_output=True)
    require(result.returncode == 0, "registration must precede implementation")
    require(hashlib.sha256(git_blob(REGISTRATION_SHA,
            "candidates/EU26-21/lambda_response_study/protocol.json")).hexdigest() == PROTOCOL_SHA256,
            "preregistered blob mismatch")
    require(git("status", "--porcelain=v1", "--untracked-files=all") == "", "scientific checkout is dirty")
    reused = {}
    for relative in REUSED_FILES:
        name = "candidates/EU26-21/" + relative
        digest = hashlib.sha256(git_blob(KERNEL_SHA, name)).hexdigest()
        require(file_sha256(REPOSITORY_ROOT / name) == digest, "frozen reused file changed: " + name)
        reused[name] = digest
    run_id, attempt = int(os.environ.get("GITHUB_RUN_ID", "0")), int(os.environ.get("GITHUB_RUN_ATTEMPT", "0"))
    require(run_id > 0 and attempt > 0, "Actions run identity missing")
    inventory = {p.relative_to(REPOSITORY_ROOT).as_posix(): file_sha256(p)
                 for p in sorted(list(THIS_DIRECTORY.glob("*.py")) + [THIS_DIRECTORY / "protocol.json",
                 REPOSITORY_ROOT / ".github/workflows/eu26-21-lambda-response-study.yml",
                 REPOSITORY_ROOT / ".github/scripts/download_study_artifacts.py"])}
    provenance = {"protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
                  "registration_sha": REGISTRATION_SHA, "implementation_sha": expected_sha,
                  "workflow_sha": expected_sha, "run_id": run_id, "run_attempt": attempt,
                  "reused_files": reused, "implementation_files": inventory,
                  "implementation_files_sha256": canonical_sha256(inventory), "environment": runtime_environment(),
                  "data_sha256": {key: protocol["data"][key + "_sha256"] for key in ("archive", "train", "test")}}
    return protocol, provenance

def write_manifest(directory: Path, *, seed: int, kind: str, provenance: dict) -> dict:
    require(kind in ("preparation", "case") and seed in CASE_SEEDS, "manifest kind/seed invalid")
    files = {}
    for path in sorted(directory.iterdir()):
        require(path.is_file() and not path.is_symlink() and path.name != "manifest.json", "unsafe artifact member")
        files[path.name] = {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
    row = kind + ".json"
    require(row in files, "artifact result absent")
    value = {"schema": "eu26-21-lr-artifact-v1", "kind": kind, "seed": seed, "provenance": provenance,
             "artifact_name": f"eu26-21-lr-{kind}-{seed}-{provenance['run_id']}-{provenance['run_attempt']}",
             "row_file": row, "files": files}
    write_json(directory / "manifest.json", value)
    return value

def verify_manifest(path: Path, *, expected_sha: str) -> dict:
    require(path.is_file() and not path.is_symlink(), "manifest absent or linked")
    value = read_json(path)
    require(value["schema"] == "eu26-21-lr-artifact-v1" and value["seed"] in CASE_SEEDS
            and value["kind"] in ("case", "preparation"), "manifest schema/seed invalid")
    prov = value["provenance"]
    require(prov["protocol_id"] == PROTOCOL_ID and prov["protocol_sha256"] == PROTOCOL_SHA256
            and prov["implementation_sha"] == prov["workflow_sha"] == expected_sha
            and prov["registration_sha"] == REGISTRATION_SHA, "manifest provenance mismatch")
    require(type(prov["run_id"]) is int and prov["run_id"] > 0
            and type(prov["run_attempt"]) is int and prov["run_attempt"] > 0, "manifest run identity invalid")
    require(value["artifact_name"] == f"eu26-21-lr-{value['kind']}-{value['seed']}-{prov['run_id']}-{prov['run_attempt']}",
            "manifest uploaded name mismatch")
    require(value["row_file"] == value["kind"] + ".json"
            and value["row_file"] in value["files"], "manifest result file mismatch")
    require({p.name for p in path.parent.iterdir()} == set(value["files"]) | {"manifest.json"},
            "unlisted or missing artifact files")
    for name, identity in value["files"].items():
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) is not None, "unsafe member name")
        member = path.parent / name
        require(member.is_file() and not member.is_symlink()
                and member.stat().st_size == identity["bytes"] and file_sha256(member) == identity["sha256"],
                "artifact member checksum mismatch: " + name)
    return value

def validate_preparation(value: dict, *, seed: int, expected_sha: str) -> None:
    require(value["schema"] == "eu26-21-lr-preparation-v1" and value["seed"] == seed
            and value["status"] == "PASS_PREPARATION", "preparation identity or status invalid")
    prov = value["provenance"]
    require(prov["protocol_id"] == PROTOCOL_ID and prov["protocol_sha256"] == PROTOCOL_SHA256
            and prov["implementation_sha"] == prov["workflow_sha"] == expected_sha, "preparation SHA mismatch")
    rows = value["evaluations"]
    require(len(rows) == 40 and value["counts"] == {"physical_calls": 40, "actual_tree_fits": 40},
            "preparation must contain forty actual fits")
    for bit, row in enumerate(rows):
        require(row["bit_index"] == bit and row["mask"] == [int(i == bit) for i in range(40)]
                and type(row["score"]) in (int, float) and 0 <= row["score"] <= 1,
                "single-bit preparation record invalid")
    bit = min(range(40), key=lambda i: (rows[i]["score"], i))
    require(value["initial"] == {"mask": rows[bit]["mask"], "score": rows[bit]["score"],
            "bit_index": bit, "feature_name": value["training_data"]["feature_names"][bit]},
            "weak initial mask differs from preregistered minimum/tie rule")
    metadata = value["training_data"]
    require(metadata["test_arrays_loaded"] is False and metadata["instance_weight_as_predictor"] is False
            and metadata["instance_weight_as_sample_weight"] is True
            and metadata["preprocessing_fit_scope"] == "internal_training_only",
            "invalid training-only profile")

def load_preparation(path: Path, registry_path: Path, *, seed: int, expected_sha: str) -> tuple[dict, dict]:
    registry = read_json(registry_path)
    require(registry["schema"] == "eu26-21-lr-registry-v1" and registry["protocol_id"] == PROTOCOL_ID
            and registry["protocol_sha256"] == PROTOCOL_SHA256 and registry["implementation_sha"] == expected_sha
            and registry["all_30_accounted"] is True and registry["frozen_before_main_search"] is True,
            "registry identity or freeze mismatch")
    require([row["seed"] for row in registry["cases"]] == list(CASE_SEEDS), "registry is not ordered 30/30")
    require(len({row["source_artifact_id"] for row in registry["cases"]}) == 30, "duplicate registry source ID")
    entry = registry["cases"][seed - CASE_SEEDS[0]]
    require(path.is_file() and not path.is_symlink() and entry["preparation"] ==
            {"sha256": file_sha256(path), "bytes": path.stat().st_size}, "frozen preparation bytes changed")
    value = read_json(path)
    validate_preparation(value, seed=seed, expected_sha=expected_sha)
    require(value == entry["payload"] and value["provenance"]["run_id"] == entry["source_run_id"]
            and entry["source_run_id"] == registry["source_run_id"], "registry embedded preparation mismatch")
    require(entry["source_artifact_name"] ==
            f"eu26-21-lr-preparation-{seed}-{entry['source_run_id']}-{value['provenance']['run_attempt']}",
            "preparation source attempt mismatch")
    return value, {"registry_sha256": file_sha256(registry_path),
                   **{k: entry[k] for k in ("preparation", "source_run_id", "source_artifact_id",
                                           "source_artifact_name", "source_artifact_digest")}}

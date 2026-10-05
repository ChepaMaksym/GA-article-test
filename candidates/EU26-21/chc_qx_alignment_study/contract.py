"""Fail-closed identity and flat evidence I/O for the registered QX study.

Scientific entrypoints run only in an exact clean Actions checkout.  Downloaded
models are never deserialized here; their immutable byte identities are enough.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence

THIS_DIRECTORY = Path(__file__).resolve().parent
CANDIDATE_DIRECTORY = THIS_DIRECTORY.parent
REPOSITORY_ROOT = THIS_DIRECTORY.parents[2]
if str(CANDIDATE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(CANDIDATE_DIRECTORY))

from common_bridge.run_seed import _requirements_environment  # noqa: E402
from local_optima_study.contract import (  # noqa: E402,F401
    add_class_metrics, canonical_bytes, canonical_sha256, file_sha256,
    hex_digest, read_json, require, write_json,
)

PROTOCOL_ID = "EU26-21-CHCQX-SOURCE-WBA-DIAG-V1"
PROTOCOL_SHA256 = "c51cbad33d2012b504312e70ff180f7f35cc58ffbd079882acf596b17710de40"
CONTENT_FREEZE_SHA = "b5c46e603838c5fbc7e35b121f757421c222046f"
REUSED_KERNEL_SHA = "05b2514d0a17bb8165f7d0388a96e9771e339284"
CASE_SEEDS = tuple(range(44001, 44031))
SEARCH_ARMS = ALL_ARMS = ("chc_qx", "lambda_adaptive_qx", "lambda_fixed1_qx")
CASE_SCHEMA = "eu26-21-qx-case-v1"
PREPARATION_SCHEMA = "eu26-21-qx-preparation-v1"
REGISTRY_SCHEMA = "eu26-21-qx-frozen-preparation-registry-v1"
MANIFEST_SCHEMA = "eu26-21-qx-case-artifact-manifest-v1"
REUSED_FILES = (
    "corrected_applied/data_protocol.py", "corrected_applied/requirements.txt",
    "common_bridge/model_evidence.py", "common_bridge/run_seed.py",
    "hybrid_1/core.py", "local_optima/generation.py",
    "local_optima_study/contract.py",
)


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPOSITORY_ROOT), *arguments],
        text=True, stderr=subprocess.STDOUT,
    ).strip()


def git_blob(revision: str, relative: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(REPOSITORY_ROOT), "show", f"{revision}:{relative}"],
        stderr=subprocess.STDOUT,
    )


def validate_protocol(path: Path, expected_digest: str = PROTOCOL_SHA256) -> dict[str, Any]:
    require(expected_digest == PROTOCOL_SHA256, "unregistered protocol digest")
    require(not path.is_symlink() and file_sha256(path) == PROTOCOL_SHA256,
            "protocol byte digest mismatch")
    protocol = read_json(path)
    require(protocol["schema"] == "eu26-21-chc-qx-protocol-v1"
            and protocol["protocol_id"] == PROTOCOL_ID, "protocol identity mismatch")
    require(protocol["rng"]["case_seeds"] == list(CASE_SEEDS), "registered seed ledger mismatch")
    require(protocol["comparison"]["search_arms"] == list(SEARCH_ARMS), "registered arms mismatch")
    require(protocol["comparison"]["search_fitness"] == "scalar_validation_weighted_balanced_accuracy"
            and protocol["comparison"]["smaller_features_in_search_success"] is False,
            "unregistered search objective")
    require(protocol["search"]["reset"] is False, "reset must remain disabled")
    require(protocol["analysis"]["descriptive_only"] is True, "inference was not registered")
    return protocol


def verify_registration() -> dict[str, Any]:
    result = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "merge-base", "--is-ancestor",
         CONTENT_FREEZE_SHA, "HEAD"], check=False, capture_output=True,
    )
    require(result.returncode == 0, "protocol registration is not an ancestor")
    relative = "candidates/EU26-21/chc_qx_alignment_study/protocol.json"
    require(hashlib.sha256(git_blob(CONTENT_FREEZE_SHA, relative)).hexdigest() == PROTOCOL_SHA256,
            "registration protocol blob mismatch")
    identities = {}
    for item in REUSED_FILES:
        path = CANDIDATE_DIRECTORY / item
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        digest = hashlib.sha256(git_blob(REUSED_KERNEL_SHA, relative)).hexdigest()
        require(file_sha256(path) == digest, f"frozen reused source changed: {relative}")
        identities[relative] = digest
    return {"content_freeze_commit_sha": CONTENT_FREEZE_SHA,
            "registration_protocol_blob_sha256": PROTOCOL_SHA256,
            "reused_kernel_revision": REUSED_KERNEL_SHA,
            "reused_files": identities, "reused_files_sha256": canonical_sha256(identities)}


def implementation_inventory() -> dict[str, str]:
    paths = list(THIS_DIRECTORY.glob("*.py")) + [THIS_DIRECTORY / "protocol.json"]
    paths += [CANDIDATE_DIRECTORY / item for item in REUSED_FILES]
    paths += list((REPOSITORY_ROOT / ".github" / "workflows").glob("eu26-21-chc-qx*.yml"))
    paths += [REPOSITORY_ROOT / ".github" / "scripts" / "download_study_artifacts.py"]
    return {path.relative_to(REPOSITORY_ROOT).as_posix(): file_sha256(path)
            for path in sorted(paths)}


def runtime_environment() -> dict[str, Any]:
    requirements = CANDIDATE_DIRECTORY / "corrected_applied" / "requirements.txt"
    environment = _requirements_environment(requirements)
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            name, version = line.split("==")
            require(environment["packages"][name] == version,
                    f"installed dependency differs from pin: {name}")
    require(environment["python_implementation"] == "CPython"
            and environment["python_version"].startswith("3.11."),
            "scientific Python implementation/version mismatch")
    return environment


def verify_upstream(upstream: Path, protocol: Mapping[str, Any]) -> dict[str, Any]:
    """Authenticate every registered author blob, without importing it."""
    def upstream_git(*arguments: str) -> str:
        return subprocess.check_output(["git", "-C", str(upstream), *arguments],
                                       text=True, stderr=subprocess.STDOUT).strip()
    source = protocol["source"]
    require(upstream_git("rev-parse", "HEAD") == source["upstream_commit"],
            "upstream commit mismatch")
    require(upstream_git("status", "--porcelain=v1", "--untracked-files=all") == "",
            "upstream checkout is not clean")
    blobs = {}
    for relative, expected_blob in source["blobs"].items():
        member = upstream / relative
        require(member.is_file() and not member.is_symlink(), f"missing upstream member: {relative}")
        blob = upstream_git("hash-object", str(member.resolve()))
        require(blob == expected_blob, f"upstream blob mismatch: {relative}")
        blobs[relative] = blob
    return {"upstream_commit": source["upstream_commit"], "upstream_blobs": blobs,
            "upstream_blobs_sha256": canonical_sha256(blobs)}


def authenticate(*, protocol_path: Path, expected_sha: str,
                 expected_protocol_sha256: str = PROTOCOL_SHA256,
                 upstream: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    hex_digest(expected_sha, "implementation SHA", 40)
    require(os.environ.get("GITHUB_ACTIONS") == "true", "scientific execution is CI-only")
    protocol = validate_protocol(protocol_path, expected_protocol_sha256)
    require(git("rev-parse", "HEAD") == expected_sha, "implementation SHA mismatch")
    require(git("status", "--porcelain=v1", "--untracked-files=all") == "",
            "implementation checkout is not clean")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    require(run_id.isdigit() and int(run_id) > 0, "invalid workflow run ID")
    require(attempt.isdigit() and int(attempt) > 0, "invalid run attempt")
    require(os.environ.get("STUDY_WORKFLOW_SHA") == expected_sha, "workflow SHA mismatch")
    require(os.environ.get("GITHUB_REF", "").startswith("refs/"), "invalid workflow ref")
    environment, files = runtime_environment(), implementation_inventory()
    provenance = {"protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
                  **verify_registration(), "implementation_sha": expected_sha,
                  "workflow_sha": expected_sha, "run_id": int(run_id),
                  "run_attempt": int(attempt), "ref": os.environ["GITHUB_REF"],
                  "environment": environment, "environment_sha256": canonical_sha256(environment),
                  "implementation_files": files, "implementation_files_sha256": canonical_sha256(files),
                  "data_sha256": {key: protocol["data"][f"{key}_sha256"]
                                  for key in ("archive", "train", "test")}}
    if upstream is not None:
        provenance.update(verify_upstream(upstream, protocol))
    return protocol, provenance


def validate_mask(mask: Sequence[int]) -> tuple[int, ...]:
    require(isinstance(mask, (tuple, list)) and len(mask) == 40, "mask must have forty entries")
    require(all(type(bit) is int and bit in (0, 1) for bit in mask), "mask entries must be integer bits")
    return tuple(mask)


def scalar_score(value: Any) -> float:
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
            "scalar WBA must be finite and lie in the unit interval")
    return float(value)


def ensure_empty_output(directory: Path) -> None:
    """Never add a failure marker to an existing evidence package."""
    require(not directory.is_symlink(), "output directory cannot be a symbolic link")
    if directory.exists():
        require(directory.is_dir() and not any(directory.iterdir()), "output directory is not empty")
    else:
        directory.mkdir(parents=True, exist_ok=False)


def scientific_contract() -> dict[str, Any]:
    return {"protocol_id": PROTOCOL_ID, "arms": list(SEARCH_ARMS), "shared_initial_queries": 50,
            "objective": "scalar_validation_weighted_balanced_accuracy", "reset": False,
            "equal_objective_budget": False, "outer_no_change": 2, "max_chunks": 20,
            "chunk_generations": 10, "diagnostic_queries_per_arm": 82,
            "hypothesis_tests": False, "test_access_during_search": False}


def write_manifest(directory: Path, *, seed: int, artifact_name: str,
                   provenance: Mapping[str, Any], row_file: str = "case.json") -> Path:
    require(type(seed) is int and seed in CASE_SEEDS, "manifest seed outside frozen ledger")
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", artifact_name)), "unsafe artifact basename")
    files = {}
    for member in sorted(directory.iterdir()):
        require(member.is_file() and not member.is_symlink(), "artifact must be flat without symlinks")
        if member.name != "manifest.json":
            files[member.name] = {"sha256": file_sha256(member), "bytes": member.stat().st_size}
    require(row_file in files, "row absent from manifest")
    path = directory / "manifest.json"
    write_json(path, {"schema": MANIFEST_SCHEMA, "seed": seed, "artifact_name": artifact_name,
                      "provenance": dict(provenance), "contract": scientific_contract(),
                      "row_file": row_file, "files": files, "manifest_self_hash_excluded": True})
    return path


def verify_manifest(path: Path, *, expected_sha: str) -> dict[str, Any]:
    require(not path.is_symlink(), "manifest cannot be a symbolic link")
    manifest = read_json(path)
    require(manifest.get("schema") == MANIFEST_SCHEMA
            and manifest["contract"] == scientific_contract(), "artifact contract mismatch")
    require(type(manifest["seed"]) is int and manifest["seed"] in CASE_SEEDS, "invalid artifact seed")
    provenance = manifest["provenance"]
    require(provenance["implementation_sha"] == expected_sha
            and provenance["workflow_sha"] == expected_sha, "artifact implementation/workflow SHA mismatch")
    require(provenance["protocol_id"] == PROTOCOL_ID
            and provenance["protocol_sha256"] == PROTOCOL_SHA256, "artifact protocol mismatch")
    registration = verify_registration()
    require(all(provenance[key] == value for key, value in registration.items()), "registration identity mismatch")
    require(provenance["implementation_files"] == implementation_inventory()
            and provenance["implementation_files_sha256"] == canonical_sha256(provenance["implementation_files"]),
            "implementation inventory mismatch")
    require(provenance["environment"] == runtime_environment()
            and provenance["environment_sha256"] == canonical_sha256(provenance["environment"]),
            "artifact environment mismatch")
    require(type(provenance["run_id"]) is int and provenance["run_id"] > 0
            and type(provenance["run_attempt"]) is int and provenance["run_attempt"] > 0,
            "artifact source run/attempt invalid")
    protocol = validate_protocol(THIS_DIRECTORY / "protocol.json")
    require(provenance["data_sha256"] == {key: protocol["data"][f"{key}_sha256"]
                                          for key in ("archive", "train", "test")}, "artifact data mismatch")
    actual = set()
    for member in path.parent.iterdir():
        require(member.is_file() and not member.is_symlink(), "unlisted directory/symbolic link")
        actual.add(member.name)
    require(actual == set(manifest["files"]) | {path.name}, "unlisted or missing artifact file")
    require(manifest["row_file"] in manifest["files"], "row absent from manifest")
    for name, identity in manifest["files"].items():
        require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name)) and Path(name).name == name,
                "manifest path escaped artifact")
        hex_digest(identity["sha256"], f"file hash {name}")
        require(type(identity["bytes"]) is int and identity["bytes"] >= 0, "invalid member size")
        member = path.parent / name
        require(member.stat().st_size == identity["bytes"] and file_sha256(member) == identity["sha256"],
                f"artifact file identity mismatch: {name}")
    return manifest


def load_registered_preparation(preparation_path: Path, registry_path: Path, *,
                                seed: int, expected_sha: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Accept only the exact seed-specific preparation frozen before search."""
    require(type(seed) is int and seed in CASE_SEEDS, "seed outside registered ledger")
    require(not preparation_path.is_symlink() and not registry_path.is_symlink(), "linked input is forbidden")
    registry = read_json(registry_path)
    require(registry.get("schema") == REGISTRY_SCHEMA, "preparation registry schema mismatch")
    require(registry["implementation_sha"] == expected_sha
            and registry["protocol_sha256"] == PROTOCOL_SHA256, "preparation registry identity mismatch")
    cases = registry["cases"]
    require(len(cases) == 30 and [item["seed"] for item in cases] == list(CASE_SEEDS),
            "preparation registry must contain all thirty seeds exactly once in order")
    entry = cases[seed - CASE_SEEDS[0]]
    identity = entry["preparation"]
    require(preparation_path.stat().st_size == identity["bytes"]
            and file_sha256(preparation_path) == identity["sha256"], "preparation byte identity mismatch")
    require(type(entry["source_run_id"]) is int and entry["source_run_id"] > 0
            and type(entry["source_artifact_id"]) is int and entry["source_artifact_id"] > 0,
            "preparation source IDs missing")
    preparation = read_json(preparation_path)
    require(preparation.get("schema") == PREPARATION_SCHEMA and preparation["seed"] == seed,
            "preparation seed/schema mismatch")
    require(preparation["status"] in ("PASS_PREPARATION", "NOT_EVALUABLE_SAMPLER")
            and entry["status"] == preparation["status"], "preparation status mismatch")
    provenance = preparation["provenance"]
    require(provenance["implementation_sha"] == expected_sha
            and provenance["protocol_sha256"] == PROTOCOL_SHA256
            and provenance["run_id"] == entry["source_run_id"], "preparation source provenance mismatch")
    return preparation, {"registry_sha256": file_sha256(registry_path),
                         "preparation": dict(identity), "source_run_id": entry["source_run_id"],
                         "source_artifact_id": entry["source_artifact_id"]}

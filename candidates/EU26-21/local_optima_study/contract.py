"""Authenticated I/O for the prospective local-optima study.

Downloaded model bundles are hashed only, never deserialized. Scientific
entrypoints authenticate a clean, exact CI checkout before evaluating data.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping

import numpy as np

THIS_DIRECTORY = Path(__file__).resolve().parent
CANDIDATE_DIRECTORY = THIS_DIRECTORY.parent
REPOSITORY_ROOT = THIS_DIRECTORY.parents[2]
if str(CANDIDATE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(CANDIDATE_DIRECTORY))

from common_bridge.run_seed import (  # noqa: E402
    _pairing_payload,
    _requirements_environment,
    _validation_objective,
    _verify_upstream_evolution,
)
from corrected_applied.data_protocol import (  # noqa: E402
    TRANSFORMED_FEATURE_NAMES,
    prepare_corrected_census,
)

PROTOCOL_ID = "EU26-21-LOCAL-WBA-ESCAPE-400-V1"
PROTOCOL_SHA256 = "8167f46a1adce8d759404d9577101befa183756ca92230e4ac3718c9f46d2ca7"
CONTENT_FREEZE_SHA = "ee3073f565ee07978a6b58ab63e6061b396ba54c"
CASE_SEEDS = tuple(range(42001, 42031))
SEARCH_ARMS = ("chc_harmonized", "lambda_adaptive", "lambda_fixed1")
ESCAPE_ARMS = ("lambda_adaptive", "lambda_fixed1")
ALL_ARMS = SEARCH_ARMS + ("full40",)
CASE_SCHEMA = "eu26-21-local-optima-case-v1"
ESCAPE_SCHEMA = "eu26-21-local-optima-escape-pair-v1"
REGISTRY_SCHEMA = "eu26-21-local-optima-frozen-registry-v1"
MANIFEST_SCHEMA = "eu26-21-local-optima-artifact-manifest-v1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def hex_digest(value: str, label: str, length: int = 64) -> str:
    require(isinstance(value, str) and bool(re.fullmatch(f"[0-9a-f]{{{length}}}", value)),
            f"{label} must be {length} lowercase hexadecimal characters")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> dict[str, Any]:
    content = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False,
                          ensure_ascii=True) + "\n").encode("utf-8")
    path.write_bytes(content)
    return {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}


def read_json(path: Path) -> Any:
    def reject_constant(token: str) -> None:
        raise ValueError(f"nonfinite JSON constant {token}")
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in output, f"duplicate JSON key: {key}")
            output[key] = value
        return output
    return json.loads(path.read_text(encoding="utf-8"),
                      parse_constant=reject_constant, object_pairs_hook=unique_object)


def validate_protocol(path: Path, expected_digest: str = PROTOCOL_SHA256) -> dict[str, Any]:
    require(expected_digest == PROTOCOL_SHA256, "unregistered protocol digest")
    require(file_sha256(path) == PROTOCOL_SHA256, "protocol byte digest mismatch")
    protocol = read_json(path)
    require(protocol["protocol_id"] == PROTOCOL_ID, "protocol ID mismatch")
    require(protocol["schema"] == "eu26-21-local-optima-protocol-v1", "protocol schema mismatch")
    require(protocol["rng"]["case_seeds"] == list(CASE_SEEDS), "seed ledger mismatch")
    require(protocol["rng"]["escape_repeats"] == [1, 2, 3, 4, 5], "repeat ledger mismatch")
    require(protocol["search"]["reset"] is False, "reset must remain disabled")
    return protocol


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPOSITORY_ROOT), *arguments],
                                   text=True, stderr=subprocess.STDOUT).strip()


def implementation_inventory() -> dict[str, str]:
    files = {
        str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"): file_sha256(path)
        for path in sorted(THIS_DIRECTORY.glob("*.py"))
    }
    for relative in ("common_bridge/search.py", "common_bridge/model_evidence.py",
                     "common_bridge/run_seed.py", "common_bridge/validate_protocol.py",
                     "corrected_applied/data_protocol.py", "corrected_applied/requirements.txt",
                     "hybrid_1/core.py", "local_optima/generation.py"):
        path = CANDIDATE_DIRECTORY / relative
        files[str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/")] = file_sha256(path)
    return files


def runtime_environment() -> dict[str, Any]:
    requirements = CANDIDATE_DIRECTORY / "corrected_applied" / "requirements.txt"
    environment = _requirements_environment(requirements)
    for raw_line in requirements.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            name, version = line.split("==")
            require(environment["packages"][name] == version, f"installed dependency differs from pin: {name}")
    require(environment["python_implementation"] == "CPython"
            and environment["python_version"].startswith("3.11."), "scientific Python implementation/version mismatch")
    return environment


def authenticate(*, protocol_path: Path, expected_sha: str,
                 expected_protocol_sha256: str, upstream: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fail closed outside the workflow or outside the exact dispatch SHA."""
    hex_digest(expected_sha, "implementation SHA", 40)
    protocol = validate_protocol(protocol_path, expected_protocol_sha256)
    require(git("rev-parse", "HEAD") == expected_sha, "implementation SHA mismatch")
    require(git("status", "--porcelain=v1", "--untracked-files=all") == "",
            "implementation checkout is not clean")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    workflow_sha = os.environ.get("STUDY_WORKFLOW_SHA", "")
    require(os.environ.get("GITHUB_ACTIONS") == "true", "scientific execution is CI-only")
    require(run_id.isdigit() and int(run_id) > 0, "invalid workflow run ID")
    require(attempt.isdigit() and int(attempt) > 0, "invalid run attempt")
    require(workflow_sha == expected_sha, "workflow SHA mismatch")
    require(os.environ.get("GITHUB_REF", "").startswith("refs/"), "invalid workflow ref")
    environment = runtime_environment()
    files = implementation_inventory()
    provenance = {
        "protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
        "content_freeze_commit_sha": CONTENT_FREEZE_SHA,
        "implementation_sha": expected_sha, "workflow_sha": workflow_sha,
        "run_id": int(run_id), "run_attempt": int(attempt),
        "ref": os.environ["GITHUB_REF"], "environment": environment,
        "environment_sha256": canonical_sha256(environment),
        "implementation_files": files, "implementation_files_sha256": canonical_sha256(files),
        "data_sha256": {key: protocol["data"][f"{key}_sha256"] for key in ("archive", "train", "test")},
    }
    if upstream is not None:
        provenance.update(_verify_upstream_evolution(upstream, {
            "upstream_commit": protocol["search"]["chc_source_commit"],
            "upstream_evolution_path": "code/Evolution.py",
            "upstream_evolution_blob_sha1": protocol["search"]["chc_source_blob"],
        }))
    return protocol, provenance


def prepare_data(protocol: Mapping[str, Any], train: Path, holdout: Path, seed: int) -> Any:
    require(type(seed) is int and seed in CASE_SEEDS, "seed outside frozen ledger")
    for path, label in ((train, "train"), (holdout, "test")):
        require(file_sha256(path) == protocol["data"][f"{label}_sha256"], f"{label} data hash mismatch")
    prepared = prepare_corrected_census(train, holdout, seed=seed,
                                       active_sample_size=protocol["data"]["active_training_rows"])
    require(tuple(prepared.feature_names) == TRANSFORMED_FEATURE_NAMES, "transformed feature order mismatch")
    require("instance_weight" not in prepared.feature_names, "weight leaked into predictors")
    return prepared


def objective_for(prepared: Any) -> Any:
    # This object has no x_test/y_test/weight_test attributes.
    return _validation_objective(prepared)


def pairing_for(prepared: Any, masks: Any, records: Any, seed: int) -> dict[str, Any]:
    return _pairing_payload(prepared, masks, records, seed=seed,
                            search_seed=seed + 1000003, initial_mask_seed=seed + 1000102)


def mask_fitness(mask: Any, fitness: Any) -> tuple[tuple[int, ...], tuple[float, float]]:
    require(isinstance(mask, (list, tuple)) and len(mask) == 40, "mask must have 40 entries")
    require(all(type(bit) is int and bit in (0, 1) for bit in mask), "mask entries must be integer bits")
    require(isinstance(fitness, (list, tuple)) and len(fitness) == 2, "fitness must have two entries")
    require(all(type(value) in (int, float) and math.isfinite(value) for value in fitness), "nonfinite fitness")
    require(0 <= fitness[0] <= 1, "WBA outside unit interval")
    expected = -sum(mask) / 40 if sum(mask) else -1.0
    require(fitness[1] == expected, "sparsity/empty-mask contract mismatch")
    return tuple(mask), (float(fitness[0]), float(fitness[1]))


def per_class_metrics(matrix: Any) -> dict[str, Any]:
    """Derive both classes from saved counts or weight sums; never refit."""
    array = np.asarray(matrix, dtype=float)
    require(array.shape == (2, 2) and np.isfinite(array).all() and (array >= 0).all(),
            "invalid confusion matrix")
    tn, fp, fn, tp = map(float, array.ravel())
    def divide(numerator: float, denominator: float) -> float:
        return numerator / denominator if denominator else 0.0
    output: dict[str, Any] = {}
    for label, true_positive, false_positive, false_negative, support in (
        ("0", tn, fn, fp, tn + fp), ("1", tp, fp, fn, fn + tp),
    ):
        precision = divide(true_positive, true_positive + false_positive)
        recall = divide(true_positive, true_positive + false_negative)
        output[label] = {"precision": precision, "recall": recall,
                         "f1": divide(2 * precision * recall, precision + recall), "support": support}
    return output


def add_class_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(metrics)
    for scale in ("weighted", "unweighted"):
        block = metrics[scale]
        output[scale] = {**dict(block), "classes": per_class_metrics(block["confusion_matrix"])}
    return output


def write_manifest(directory: Path, *, seed: int, artifact_name: str,
                   provenance: Mapping[str, Any], row_file: str,
                   repeat: int | None = None) -> Path:
    require(artifact_name and "/" not in artifact_name and "\\" not in artifact_name,
            "artifact name must be a basename")
    manifest_name = "manifest.json"
    files = {path.name: {"sha256": file_sha256(path), "bytes": path.stat().st_size}
             for path in sorted(directory.iterdir()) if path.is_file() and path.name != manifest_name}
    path = directory / manifest_name
    write_json(path, {"schema": MANIFEST_SCHEMA, "seed": seed, "repeat": repeat,
                      "artifact_name": artifact_name, "provenance": dict(provenance),
                      "contract": {"protocol_id": PROTOCOL_ID,
                                   "arms": list(ALL_ARMS if repeat is None else ESCAPE_ARMS),
                                   "search_objective_calls_per_arm": 400,
                                   "objective": "validation_weighted_balanced_accuracy_then_negative_selected_fraction",
                                   "tie_break": "lexicographic_terminal_earliest_query",
                                   "reset": False, "duplicates_consume_calls": True},
                      "row_file": row_file, "files": files, "manifest_self_hash_excluded": True})
    return path


def verify_manifest(path: Path, *, expected_sha: str) -> dict[str, Any]:
    manifest = read_json(path)
    require(manifest.get("schema") == MANIFEST_SCHEMA, "artifact manifest schema mismatch")
    require(manifest["contract"] == {
        "protocol_id": PROTOCOL_ID,
        "arms": list(ALL_ARMS if manifest["repeat"] is None else ESCAPE_ARMS),
        "search_objective_calls_per_arm": 400,
        "objective": "validation_weighted_balanced_accuracy_then_negative_selected_fraction",
        "tie_break": "lexicographic_terminal_earliest_query", "reset": False,
        "duplicates_consume_calls": True}, "artifact scientific contract mismatch")
    provenance = manifest["provenance"]
    require(provenance["implementation_sha"] == expected_sha, "artifact implementation SHA mismatch")
    require(provenance["workflow_sha"] == expected_sha, "artifact workflow SHA mismatch")
    require(provenance["protocol_sha256"] == PROTOCOL_SHA256, "artifact protocol hash mismatch")
    require(provenance["content_freeze_commit_sha"] == CONTENT_FREEZE_SHA, "content freeze SHA mismatch")
    require(provenance["protocol_id"] == PROTOCOL_ID, "artifact protocol ID mismatch")
    require(provenance["implementation_files_sha256"] == canonical_sha256(provenance["implementation_files"]),
            "implementation file inventory digest mismatch")
    require(provenance["implementation_files"] == implementation_inventory(), "source file inventory differs from exact checkout")
    require(provenance["environment_sha256"] == canonical_sha256(provenance["environment"]), "environment digest mismatch")
    require(provenance["environment"] == runtime_environment(), "artifact environment differs from pinned current runtime")
    require(type(provenance["run_id"]) is int and provenance["run_id"] > 0
            and type(provenance["run_attempt"]) is int and provenance["run_attempt"] > 0,
            "artifact CI run/attempt identity invalid")
    protocol = validate_protocol(THIS_DIRECTORY / "protocol.json")
    require(provenance["data_sha256"] == {key: protocol["data"][f"{key}_sha256"]
                                          for key in ("archive", "train", "test")}, "artifact data hashes mismatch")
    require(manifest["row_file"] in manifest["files"], "row absent from manifest")
    require(not path.is_symlink(), "artifact manifest may not be a symlink")
    actual_files = set()
    for member in path.parent.iterdir():
        require(member.is_file() and not member.is_symlink(), "artifact contains a directory or symbolic link")
        actual_files.add(member.name)
    require(actual_files == set(manifest["files"]) | {path.name}, "artifact contains an unlisted or missing file")
    for name, identity in manifest["files"].items():
        require(isinstance(name, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name))
                and Path(name).name == name and name not in ("", ".", ".."), "manifest path escaped artifact")
        hex_digest(identity["sha256"], f"file hash {name}")
        require(type(identity["bytes"]) is int and identity["bytes"] >= 0, "file byte count invalid")
        member = path.parent / name
        require(member.is_file(), f"missing artifact member {name}")
        require(member.stat().st_size == identity["bytes"], f"artifact byte count mismatch {name}")
        require(file_sha256(member) == identity["sha256"], f"artifact hash mismatch {name}")
    return manifest

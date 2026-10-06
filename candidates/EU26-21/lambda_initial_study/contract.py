"""Authenticated contract and ordered initialization replay for the new series.

Only the common fifty validation queries are shared. Subsequent queries are
always physically evaluated, including duplicate masks. Replay never owns a
random generator or exposes held-out records to a search kernel.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence

THIS_DIRECTORY = Path(__file__).resolve().parent
CANDIDATE_DIRECTORY = THIS_DIRECTORY.parent
REPOSITORY_ROOT = THIS_DIRECTORY.parents[2]
if str(CANDIDATE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(CANDIDATE_DIRECTORY))

from common_bridge.run_seed import (  # noqa: E402
    _pairing_payload, _requirements_environment, _validation_objective,
    _verify_upstream_evolution,
)
from corrected_applied.data_protocol import (  # noqa: E402
    TRANSFORMED_FEATURE_NAMES, prepare_corrected_census,
)
from local_optima_study.contract import (  # noqa: E402,F401
    add_class_metrics, canonical_bytes, canonical_sha256, file_sha256,
    hex_digest, mask_fitness, per_class_metrics, read_json, require, write_json,
)
from local_optima_study.search import validate_mask  # noqa: E402

PROTOCOL_ID = "EU26-21-LAMBDA-INITIAL-WBA-400-V1"
PROTOCOL_SHA256 = "8f96fbf91ae5e92b90409c3ba0492da2d13551bca0d49e273d299dd4ac1453b4"
CONTENT_FREEZE_SHA = "fdf093fd4b53ecf48a148d86b28c8ecee007e7aa"
REUSED_KERNEL_SHA = "c5c9f1e870f4e80014d9f8d90bd76eb5a9d025a0"
CASE_SEEDS = tuple(range(43001, 43031))
LAMBDA_INITIAL_VALUES = (1, 5, 10, 20, 40)
LAMBDA_ARMS = tuple(f"lambda_initial_{value}" for value in LAMBDA_INITIAL_VALUES)
SEARCH_ARMS = ALL_ARMS = ("chc_harmonized",) + LAMBDA_ARMS
CASE_SCHEMA = "eu26-21-lambda-initial-case-v1"
TRACE_SCHEMA = "eu26-21-lambda-initial-trace-v1"
MANIFEST_SCHEMA = "eu26-21-lambda-initial-artifact-manifest-v1"
STATUS_SCHEMA = "eu26-21-lambda-initial-status-v1"
REUSED_FILES = (
    "common_bridge/search.py", "common_bridge/model_evidence.py",
    "common_bridge/run_seed.py", "common_bridge/validate_protocol.py",
    "corrected_applied/data_protocol.py", "corrected_applied/requirements.txt",
    "hybrid_1/core.py", "local_optima/generation.py",
    "local_optima_study/search.py", "local_optima_study/contract.py",
    "local_optima_study/aggregate.py",
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
    require(protocol["schema"] == "eu26-21-lambda-initial-protocol-v1"
            and protocol["protocol_id"] == PROTOCOL_ID, "protocol identity mismatch")
    require(protocol["rng"]["case_seeds"] == list(CASE_SEEDS), "seed ledger mismatch")
    require(protocol["comparison"]["search_arms"] == list(SEARCH_ARMS)
            and protocol["comparison"]["lambda_initial_values"] == list(LAMBDA_INITIAL_VALUES),
            "registered arms mismatch")
    require(protocol["search"]["reset"] is False
            and protocol["objective"]["post_initialization_cache"] is False,
            "reset or post-initialization cache enabled")
    return protocol


def verify_registration() -> dict[str, Any]:
    result = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "merge-base", "--is-ancestor",
         CONTENT_FREEZE_SHA, "HEAD"], check=False, capture_output=True,
    )
    require(result.returncode == 0, "protocol registration is not an ancestor")
    relative = "candidates/EU26-21/lambda_initial_study/protocol.json"
    require(hashlib.sha256(git_blob(CONTENT_FREEZE_SHA, relative)).hexdigest()
            == PROTOCOL_SHA256, "registration protocol blob mismatch")
    identities = {}
    for item in REUSED_FILES:
        path = CANDIDATE_DIRECTORY / item
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        registered_digest = hashlib.sha256(git_blob(REUSED_KERNEL_SHA, relative)).hexdigest()
        require(file_sha256(path) == registered_digest,
                f"frozen reused source changed: {relative}")
        identities[relative] = registered_digest
    return {"content_freeze_commit_sha": CONTENT_FREEZE_SHA,
            "registration_protocol_blob_sha256": PROTOCOL_SHA256,
            "reused_kernel_revision": REUSED_KERNEL_SHA,
            "reused_files": identities,
            "reused_files_sha256": canonical_sha256(identities)}


def implementation_inventory() -> dict[str, str]:
    paths = list(THIS_DIRECTORY.glob("*.py")) + [THIS_DIRECTORY / "protocol.json"]
    paths += [CANDIDATE_DIRECTORY / item for item in REUSED_FILES]
    paths += list((REPOSITORY_ROOT / ".github" / "workflows").glob("eu26-21-lambda*.yml"))
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


def authenticate(*, protocol_path: Path, expected_sha: str,
                 expected_protocol_sha256: str = PROTOCOL_SHA256,
                 upstream: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Authenticate the exact clean scientific workflow before evaluation."""
    hex_digest(expected_sha, "implementation SHA", 40)
    require(os.environ.get("GITHUB_ACTIONS") == "true", "scientific execution is CI-only")
    protocol = validate_protocol(protocol_path, expected_protocol_sha256)
    require(git("rev-parse", "HEAD") == expected_sha, "implementation SHA mismatch")
    require(git("status", "--porcelain=v1", "--untracked-files=all") == "",
            "implementation checkout is not clean")
    run_id, attempt = os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_RUN_ATTEMPT", "")
    require(run_id.isdigit() and int(run_id) > 0, "invalid workflow run ID")
    require(attempt.isdigit() and int(attempt) > 0, "invalid run attempt")
    require(os.environ.get("STUDY_WORKFLOW_SHA") == expected_sha, "workflow SHA mismatch")
    require(os.environ.get("GITHUB_REF", "").startswith("refs/"), "invalid workflow ref")
    registration = verify_registration()
    environment, files = runtime_environment(), implementation_inventory()
    provenance = {
        "protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
        **registration, "implementation_sha": expected_sha, "workflow_sha": expected_sha,
        "run_id": int(run_id), "run_attempt": int(attempt), "ref": os.environ["GITHUB_REF"],
        "environment": environment, "environment_sha256": canonical_sha256(environment),
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
    prepared = prepare_corrected_census(
        train, holdout, seed=seed, active_sample_size=protocol["data"]["active_training_rows"],
    )
    require(tuple(prepared.feature_names) == TRANSFORMED_FEATURE_NAMES,
            "transformed feature order mismatch")
    require("instance_weight" not in prepared.feature_names, "weight leaked into predictors")
    return prepared


def objective_for(prepared: Any) -> Any:
    return _validation_objective(prepared)


def pairing_for(prepared: Any, masks: Any, records: Any, seed: int) -> dict[str, Any]:
    return _pairing_payload(prepared, masks, records, seed=seed,
                            search_seed=seed + 1000003, initial_mask_seed=seed + 1000102)


class SharedInitialization:
    """Evaluate exactly fifty ordered masks once, with no deduplication."""

    def __init__(self, objective: Callable[[Any], Any], masks: Sequence[Sequence[int]]) -> None:
        require(callable(objective), "objective must be callable")
        require(len(masks) == 50, "exactly fifty initial masks are required")
        self.masks = tuple(validate_mask(mask, 40) for mask in masks)
        self.scores = tuple(mask_fitness(list(mask), objective(mask))[1] for mask in self.masks)
        self.records = tuple({"mask": list(mask), "fitness": list(score)}
                             for mask, score in zip(self.masks, self.scores))
        self.physical_validation_calls = 50
        self.actual_tree_fits = sum(bool(sum(mask)) for mask in self.masks)
        self.unique_mask_count = len(set(self.masks))

    def replay(self, objective: Callable[[Any], Any]) -> "PositionCheckedReplay":
        return PositionCheckedReplay(objective, self.masks, self.scores)


class PositionCheckedReplay:
    """First fifty ordered logical calls replay; next 350 invoke the evaluator."""

    def __init__(self, objective: Callable[[Any], Any], masks: Any, scores: Any) -> None:
        require(callable(objective), "objective must be callable")
        self._objective, self._masks, self._scores = objective, masks, scores
        self.calls = 0
        self.physical_validation_calls = 0
        self.actual_tree_fits = 0
        self._seen: set[tuple[int, ...]] = set()
        self.duplicate_queries = 0
        self.post_initial_duplicate_queries = 0

    def __call__(self, mask: Sequence[int]) -> tuple[float, float]:
        require(self.calls < 400, "logical call limit exhausted")
        value = validate_mask(mask, 40)
        is_duplicate = value in self._seen
        if self.calls < 50:
            require(value == self._masks[self.calls], "initial replay mask/order mismatch")
            score = self._scores[self.calls]
        else:
            score = mask_fitness(list(value), self._objective(value))[1]
            self.physical_validation_calls += 1
            self.actual_tree_fits += int(bool(sum(value)))
            self.post_initial_duplicate_queries += int(is_duplicate)
        self.duplicate_queries += int(is_duplicate)
        self._seen.add(value)
        self.calls += 1
        return score

    def complete(self) -> dict[str, Any]:
        require(self.calls == 400 and self.physical_validation_calls == 350,
                "initial replay or post-initialization physical call count mismatch")
        return {"logical_calls": self.calls, "initial_replayed_calls": 50,
                "post_initial_physical_calls": self.physical_validation_calls,
                "post_initial_actual_tree_fits": self.actual_tree_fits,
                "unique_masks": len(self._seen), "duplicate_queries": self.duplicate_queries,
                "post_initial_duplicate_queries": self.post_initial_duplicate_queries,
                "post_initialization_cache": False}


def scientific_contract() -> dict[str, Any]:
    return {"protocol_id": PROTOCOL_ID, "arms": list(ALL_ARMS),
            "lambda_initial_values": list(LAMBDA_INITIAL_VALUES),
            "search_objective_calls_per_arm": 400, "shared_initial_queries": 50,
            "post_initial_physical_calls_per_arm": 350,
            "objective": "validation_weighted_balanced_accuracy_then_negative_selected_fraction",
            "tie_break": "lexicographic_terminal_earliest_query", "reset": False,
            "duplicates_consume_calls": True, "post_initialization_cache": False}


def write_manifest(directory: Path, *, seed: int, artifact_name: str,
                   provenance: Mapping[str, Any], row_file: str = "case.json") -> Path:
    require(type(seed) is int and seed in CASE_SEEDS, "manifest seed outside frozen ledger")
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", artifact_name)),
            "artifact name must be a safe basename")
    files = {}
    for member in sorted(directory.iterdir()):
        require(member.is_file() and not member.is_symlink(),
                "artifact must be flat and contain no symlinks")
        if member.name != "manifest.json":
            files[member.name] = {"sha256": file_sha256(member), "bytes": member.stat().st_size}
    require(row_file in files, "row absent from manifest")
    path = directory / "manifest.json"
    write_json(path, {"schema": MANIFEST_SCHEMA, "seed": seed, "artifact_name": artifact_name,
                      "provenance": dict(provenance), "contract": scientific_contract(),
                      "row_file": row_file, "files": files, "manifest_self_hash_excluded": True})
    return path


def verify_manifest(path: Path, *, expected_sha: str) -> dict[str, Any]:
    require(not path.is_symlink(), "artifact manifest may not be a symlink")
    manifest = read_json(path)
    require(manifest.get("schema") == MANIFEST_SCHEMA
            and manifest["contract"] == scientific_contract(), "artifact scientific contract mismatch")
    require(type(manifest["seed"]) is int and manifest["seed"] in CASE_SEEDS,
            "artifact seed outside frozen ledger")
    provenance = manifest["provenance"]
    require(provenance["implementation_sha"] == expected_sha
            and provenance["workflow_sha"] == expected_sha, "artifact implementation/workflow SHA mismatch")
    require(provenance["protocol_id"] == PROTOCOL_ID
            and provenance["protocol_sha256"] == PROTOCOL_SHA256, "artifact protocol identity mismatch")
    registration = verify_registration()
    require(all(provenance[key] == value for key, value in registration.items()),
            "artifact registration/reused-source identity mismatch")
    require(provenance["implementation_files"] == implementation_inventory()
            and provenance["implementation_files_sha256"] == canonical_sha256(provenance["implementation_files"]),
            "artifact implementation file inventory mismatch")
    require(provenance["environment"] == runtime_environment()
            and provenance["environment_sha256"] == canonical_sha256(provenance["environment"]),
            "artifact environment mismatch")
    require(type(provenance["run_id"]) is int and provenance["run_id"] > 0
            and type(provenance["run_attempt"]) is int and provenance["run_attempt"] > 0,
            "artifact run/attempt identity invalid")
    protocol = validate_protocol(THIS_DIRECTORY / "protocol.json")
    require(provenance["data_sha256"] == {key: protocol["data"][f"{key}_sha256"]
                                          for key in ("archive", "train", "test")},
            "artifact data hashes mismatch")
    require(manifest["row_file"] in manifest["files"], "row absent from manifest")
    actual = set()
    for member in path.parent.iterdir():
        require(member.is_file() and not member.is_symlink(),
                "artifact contains a directory or symbolic link")
        actual.add(member.name)
    require(actual == set(manifest["files"]) | {path.name}, "unlisted or missing artifact file")
    for name, identity in manifest["files"].items():
        require(isinstance(name, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name))
                and Path(name).name == name, "manifest path escaped artifact")
        hex_digest(identity["sha256"], f"file hash {name}")
        require(type(identity["bytes"]) is int and identity["bytes"] >= 0,
                "invalid artifact byte count")
        member = path.parent / name
        require(member.stat().st_size == identity["bytes"] and file_sha256(member) == identity["sha256"],
                f"artifact hash/size mismatch: {name}")
    return manifest

"""Authenticate the separately frozen source bundle before preparation."""

import json
from pathlib import Path, PurePosixPath
import platform
import subprocess

from .data_audit import (PROTOCOL_ID, REPO_ROOT, SOURCE_SHA, authenticate,
                         canonical_bytes, check_license, compare_families,
                         parse_instance, require, sha256_bytes, source_specs)

STUDY_ROOT = REPO_ROOT / "studies/knapsack_parameters"
DEFAULT_INPUTS = STUDY_ROOT / "inputs"
INPUT_FREEZE_SHA = "58487fa3a541f194aeec5045f64a7d1641ae96be"
DATA_MANIFEST_SHA256 = "528fee8da7d7cb776fb851e6a05949133830e9533c4091cbb4e8698ac19fb0df"
AUDIT_IMPLEMENTATION_SHA = "442eda9f77deb60c72e230b40e0922a764a3be21"
AUDIT_RUN_ID = 37576847587
AUDIT_ARTIFACT_ID = 11463057072
AUDIT_ZIP_SHA256 = "a71895e564ac6c9d92e05f05cbe5d84984706c2dede991d9362cf0fe7381f9b9"
PYTHON_VERSION = "3.12.14"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_file_manifest(directory):
    directory = Path(directory).resolve()
    manifest = read_json(directory / "file_manifest.json")
    require(manifest["schema_version"] == "knapsack-feasibility-files-v1" and manifest["excludes_self"] is True, "invalid member manifest schema")
    seen = set()
    for row in manifest["files"]:
        path = PurePosixPath(row["path"])
        require(not path.is_absolute() and ".." not in path.parts and "\\" not in row["path"] and ":" not in row["path"], "unsafe member path")
        require(row["path"] not in seen and row["path"] != "file_manifest.json", "duplicate or self-referential member")
        seen.add(row["path"])
        target = directory / path
        require(target.resolve().is_relative_to(directory) and not target.is_symlink(), "unsafe member target")
        raw = target.read_bytes()
        require(type(row["bytes"]) is int and len(raw) == row["bytes"] and sha256_bytes(raw) == row["sha256"], "member bytes/hash mismatch")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    require(actual == seen | {"file_manifest.json"}, "unexpected or absent evidence members")
    return manifest


def verify_input_bundle(inputs=DEFAULT_INPUTS):
    inputs = Path(inputs)
    member_manifest = verify_file_manifest(inputs)
    manifest_raw = (inputs / "data_manifest.json").read_bytes()
    require(sha256_bytes(manifest_raw) == DATA_MANIFEST_SHA256, "frozen data manifest changed")
    manifest = json.loads(manifest_raw)
    require(manifest["schema_version"] == "knapsack-feasibility-data-manifest-v1" and manifest["status"] == "PASS_AUDIT", "source audit is incomplete")
    require(manifest["protocol_id"] == PROTOCOL_ID and manifest["source_commit_sha"] == SOURCE_SHA, "wrong source protocol/revision")
    require(manifest["instance_count"] == manifest["expected_instance_count"] == 30, "source registry must have 30 cases")
    specs = source_specs()
    expected_paths = {f"source/{row['path']}" for row in specs}
    require({row["path"] for row in member_manifest["files"] if row["path"].startswith("source/")} == expected_paths, "not the exact 31 source files")
    require([row["source_path"] for row in manifest["source_files"]] == [row["path"] for row in specs], "source order/identity changed")
    require(len(manifest["instances"]) == 30 and len(manifest["source_files"]) == 31, "duplicate or missing source identities")
    require(check_license((inputs / "source/README.md").read_bytes()) == manifest["license"], "license audit differs from original README")
    parsed = []
    for spec, recorded, source in zip(specs[1:], manifest["instances"], manifest["source_files"][1:], strict=True):
        raw = (inputs / "source" / spec["path"]).read_bytes()
        require(source["status"] == "PASS_SOURCE" and source["bytes"] == len(raw) and source["sha256"] == sha256_bytes(raw), "source identity mismatch")
        instance = parse_instance(raw, spec["path"], class_label=spec["class_label"], family=spec["family"], index=spec["index"])
        require((recorded["n"], recorded["capacity"], tuple(recorded["profits"]), tuple(recorded["weights"]), recorded["source_path"], recorded["class_label"], recorded["family"], recorded["index"]) == (instance.n, instance.capacity, instance.profits, instance.weights, instance.source_path, instance.class_label, instance.family, instance.index), "parsed source and frozen arrays differ")
        require(recorded["instance_id"] == instance.instance_id and recorded["original_positions"] == list(range(100)) and recorded["documentation_positions"] == list(range(1, 101)), "bit-to-item mapping mismatch")
        require(recorded["profits_sha256"] == sha256_bytes(canonical_bytes(instance.profits)) and recorded["weights_sha256"] == sha256_bytes(canonical_bytes(instance.weights)), "array identity mismatch")
        parsed.append(instance)
    require(compare_families(parsed) == manifest["family_comparisons"], "stored family comparisons differ from complete arrays")
    return parsed, manifest


def load_frozen_inputs(expected_sha=None, *, authenticate_ci=True, inputs=DEFAULT_INPUTS):
    require(authenticate_ci, "scientific callers must authenticate the CI checkout; fixture checks use verify_input_bundle")
    provenance = authenticate(expected_sha)
    subprocess.run(["git", "merge-base", "--is-ancestor", INPUT_FREEZE_SHA, expected_sha], cwd=REPO_ROOT, check=True)
    anchored = ["inputs/file_manifest.json", "inputs/data_manifest.json", "python_runtime.lock.json", "audit_transport.json"]
    for relative in anchored:
        original = subprocess.check_output(["git", "show", f"{INPUT_FREEZE_SHA}:studies/knapsack_parameters/{relative}"], cwd=REPO_ROOT)
        require(original == (STUDY_ROOT / relative).read_bytes(), "frozen input/provenance bytes changed")
    require(Path(inputs).resolve() == DEFAULT_INPUTS.resolve(), "scientific input location differs from the frozen checkout")
    instances, manifest = verify_input_bundle(inputs)
    lock, transport = read_json(STUDY_ROOT / "python_runtime.lock.json"), read_json(STUDY_ROOT / "audit_transport.json")
    require(lock["scientific_python_patch_frozen"] is True and lock["input_identity_frozen_before_scientific_implementation"] is True, "runtime is not frozen")
    require(lock["python_version"] == platform.python_version() == PYTHON_VERSION and lock["implementation"] == platform.python_implementation() == "CPython", "runtime patch/implementation mismatch")
    require(lock["data_manifest_sha256"] == transport["data_manifest_sha256"] == DATA_MANIFEST_SHA256, "transport/input hash mismatch")
    require(lock["audit_implementation_sha"] == transport["implementation_sha"] == manifest["provenance"]["implementation_sha"] == AUDIT_IMPLEMENTATION_SHA, "audit source code identity mismatch")
    require(lock["audit_run_id"] == transport["run_id"] == manifest["provenance"]["run_id"] == AUDIT_RUN_ID and transport["run_attempt"] == 1, "audit run identity mismatch")
    artifact = transport["artifact_api_metadata"]
    require(artifact["id"] == AUDIT_ARTIFACT_ID and artifact["workflow_run"]["head_sha"] == AUDIT_IMPLEMENTATION_SHA, "audit artifact identity mismatch")
    require(artifact["digest"] == f"sha256:{AUDIT_ZIP_SHA256}" and transport["downloaded_zip_sha256"] == AUDIT_ZIP_SHA256, "audit ZIP transport identity mismatch")
    provenance.update(data_freeze_commit_sha=INPUT_FREEZE_SHA, data_manifest_sha256=DATA_MANIFEST_SHA256,
                      input_file_manifest_sha256=sha256_bytes((DEFAULT_INPUTS / "file_manifest.json").read_bytes()),
                      runtime_lock_sha256=sha256_bytes((STUDY_ROOT / "python_runtime.lock.json").read_bytes()),
                      audit_transport_sha256=sha256_bytes((STUDY_ROOT / "audit_transport.json").read_bytes()),
                      python_version=PYTHON_VERSION, source_audit_run_id=AUDIT_RUN_ID,
                      source_audit_artifact_id=AUDIT_ARTIFACT_ID)
    return instances, provenance

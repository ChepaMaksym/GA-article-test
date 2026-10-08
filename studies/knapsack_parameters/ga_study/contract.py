"""Fail-closed scientific identities and byte-preserving evidence helpers."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess

REPO_ROOT = Path(__file__).resolve().parents[3]
STUDY_ROOT = REPO_ROOT / "studies/knapsack_parameters"
MODULE_ROOT = STUDY_ROOT / "ga_study"
PROTOCOL_ID = "GA-KNAPSACK-PARAMETERS-MAIN-V1"
REGISTRATION_SHA = "30a6a44e169458c70af0c215b754ab2b01f87953"
PROTOCOL_SHA = "40913447df079b7165a622f3d1e69a7d30fb0ffadc8de312b3bb82ba3bd10e90"
BASE_PROTOCOL_SHA = "f9b5816852b1a3b8b12ba4469d43da2a73b9d27d14879ed0dbad59333cba986d"
DATA_SHA = "528fee8da7d7cb776fb851e6a05949133830e9533c4091cbb4e8698ac19fb0df"
REGISTRY_SHA = "7e9b8fc893889426e2d3b57610e3a91c09263fcdff488cf15a2b84efe1bdc70f"
BRANCH = "research/masters-ga-knapsack-parameters"
REPOSITORY = "ChepaMaksym/GA-article-test"
CLASS_CODES = {"UC": 0, "WC": 1, "SC": 2}
FILE_SCHEMA = "ga-knapsack-files-v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def file_identity(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def write_jsonl_gz(path, rows):
    with Path(path).open("wb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", mtime=0, filename="") as stream:
            for row in rows:
                stream.write(canonical_bytes(row) + b"\n")


def safe_member(root, relative):
    root = Path(root).resolve()
    relative = str(relative)
    pure = PurePosixPath(relative)
    require(relative and not pure.is_absolute() and ".." not in pure.parts and
            "\\" not in relative and ":" not in relative, "unsafe evidence member")
    path = root.joinpath(*pure.parts)
    require(path.resolve().is_relative_to(root) and not path.is_symlink(), "evidence escapes directory")
    return path


def write_file_manifest(directory, *, exclude=("file_manifest.json",)):
    directory = Path(directory)
    files = [{"path": path.relative_to(directory).as_posix(), **file_identity(path)}
             for path in sorted(directory.rglob("*")) if path.is_file() and
             path.relative_to(directory).as_posix() not in exclude]
    value = {"schema_version": FILE_SCHEMA, "excludes_self": True, "files": files}
    write_json(directory / "file_manifest.json", value)
    return value


def verify_file_manifest(directory):
    directory = Path(directory)
    manifest = read_json(directory / "file_manifest.json")
    require(manifest.get("schema_version") == FILE_SCHEMA and manifest.get("excludes_self") is True,
            "wrong file manifest schema")
    seen = set()
    for entry in manifest["files"]:
        relative = entry["path"]
        require(relative not in seen and relative != "file_manifest.json", "duplicate/self member")
        seen.add(relative)
        actual = file_identity(safe_member(directory, relative))
        require(actual == {"bytes": entry["bytes"], "sha256": entry["sha256"]}, "member hash/length mismatch")
    actual_paths = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    require(actual_paths == seen | {"file_manifest.json"}, "unexpected or missing member")
    return manifest


def output_directory(path):
    path = Path(path).resolve()
    require(not path.is_relative_to(REPO_ROOT), "generated evidence must be outside checkout")
    require(not path.exists() or not any(path.iterdir()), "existing evidence must not be overwritten")
    path.mkdir(parents=True, exist_ok=True)
    return path


def implementation_fingerprint():
    """Metadata freeze commits do not alter the implementation fingerprint."""
    paths = sorted(path for path in MODULE_ROOT.rglob("*.py") if "tests" not in path.parts)
    paths += [MODULE_ROOT / "dependencies/requirements.lock"]
    rows = [{"path": path.relative_to(REPO_ROOT).as_posix(), **file_identity(path)} for path in paths]
    return sha256_bytes(canonical_bytes(rows))


def authenticate(expected_sha, *, scientific=True):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "scientific execution is permitted only in GitHub Actions")
    require(re.fullmatch(r"[0-9a-f]{40}", str(expected_sha)) is not None, "exact implementation SHA required")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    require(head == expected_sha == os.environ.get("GITHUB_SHA"), "checkout/expected/GitHub SHA mismatch")
    require(os.environ.get("GITHUB_REF") == f"refs/heads/{BRANCH}", "wrong execution branch")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "wrong repository")
    require(os.environ.get("STUDY_WORKFLOW_SHA", expected_sha) == expected_sha, "workflow must use checkout SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, expected_sha], cwd=REPO_ROOT, check=True)
    protocol_path = STUDY_ROOT / "main_protocol.json"
    raw = protocol_path.read_bytes()
    require(sha256_bytes(raw) == PROTOCOL_SHA, "registered main protocol changed")
    registered = subprocess.check_output(["git", "show", f"{REGISTRATION_SHA}:studies/knapsack_parameters/main_protocol.json"], cwd=REPO_ROOT)
    require(raw == registered, "registration is not byte-identical")
    require(sha256_bytes((STUDY_ROOT / "protocol.json").read_bytes()) == BASE_PROTOCOL_SHA, "historical base protocol changed")
    require(platform.python_version() == "3.12.14" and platform.python_implementation() == "CPython", "CPython patch mismatch")
    identity = {"protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA,
                "registration_commit_sha": REGISTRATION_SHA, "implementation_commit_sha": expected_sha,
                "data_manifest_sha256": DATA_SHA, "registry_sha256": REGISTRY_SHA,
                "run_id": int(os.environ["GITHUB_RUN_ID"]), "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
                "python_version": platform.python_version(), "repository": REPOSITORY}
    if scientific:
        import numpy
        import matplotlib
        require(numpy.__version__ == "2.2.6" and matplotlib.__version__ == "3.10.3", "numerical dependency versions mismatch")
        lock = read_json(MODULE_ROOT / "dependencies/environment.lock.json")
        requirements = file_identity(MODULE_ROOT / "dependencies/requirements.lock")
        require(lock["requirements_lock_sha256"] == requirements["sha256"], "dependency lock hash mismatch")
        require(lock["python_version"] == "3.12.14" and lock["root_versions"] == {"numpy": "2.2.6", "matplotlib": "3.10.3"}, "wrong locked environment")
        identity.update(runtime_lock_sha256=file_identity(MODULE_ROOT / "dependencies/environment.lock.json")["sha256"],
                        requirements_lock_sha256=requirements["sha256"], numpy_version=numpy.__version__, matplotlib_version=matplotlib.__version__,
                        implementation_fingerprint=implementation_fingerprint())
    return identity


def load_context(expected_sha):
    from ..feasibility.frozen_inputs import verify_input_bundle
    identity = authenticate(expected_sha)
    instances, manifest = verify_input_bundle()
    registry_path = STUDY_ROOT / "evidence/run-37637475385/registry.json"
    require(file_identity(registry_path)["sha256"] == REGISTRY_SHA, "preparation registry changed")
    registry = read_json(registry_path)
    require(registry["all_30_accounted"] and registry["case_count"] == 30 and registry["admitted_center_count"] == 14
            and registry["nonempty_admitted_family_count"] == 10, "preparation registry incomplete")
    cases = {row["instance_id"]: row for row in registry["cases"]}
    require(len(cases) == 30 and list(cases) == [instance.instance_id for instance in instances], "case ordering changed")
    return instances, cases, manifest, identity


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--lock-only", action="store_true")
    args = parser.parse_args(argv)
    authenticate(args.expected_sha, scientific=not args.lock_only)
    print("Authenticated exact registered checkout and runtime")


if __name__ == "__main__":
    main()

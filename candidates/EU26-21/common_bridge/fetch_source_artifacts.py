#!/usr/bin/env python3
"""Fetch and authenticate an explicit immutable GitHub artifact ledger.

The expected ledger names every artifact ID and GitHub-reported digest.  This
tool verifies that all 30 artifacts belong to one source run and head, hashes
the downloaded ZIP bytes, safely extracts them, and records a file-level
ledger for strict reaggregation.  Authentication is read only from GH_TOKEN or
GITHUB_TOKEN and is never printed or serialized.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


EXPECTED_SCHEMA = "eu26-21-common-bridge-source-artifact-ledger-v1"
OUTPUT_SCHEMA = "eu26-21-common-bridge-source-artifact-verification-v1"
EXPECTED_SEEDS = tuple(range(41001, 41031))
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
DIGEST = re.compile(r"sha256:([0-9a-f]{64})\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
ARTIFACT_NAME = re.compile(r"[A-Za-z0-9_.-]+\Z")
MAX_ARTIFACT_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
SOURCE_WORKFLOW_PATH = ".github/workflows/eu26-21-common-bridge-30-paired.yml"


class ArtifactError(ValueError):
    """Raised when source-run or artifact identity cannot be authenticated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactError(message)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    _require(isinstance(value, list), f"{label} must be an array")
    return value


def _integer(value: Any, label: str, *, minimum: int = 1) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool),
        f"{label} must be an integer",
    )
    normalized = int(value)
    _require(normalized >= minimum, f"{label} must be >= {minimum}")
    return normalized


def _string(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(value), f"{label} must be a string")
    return value


def _hex(value: Any, label: str, pattern: re.Pattern[str]) -> str:
    normalized = _string(value, label).lower()
    _require(pattern.fullmatch(normalized) is not None, f"{label} is malformed")
    return normalized


def _duplicate_guard(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _bad_constant(value: str) -> None:
    raise ArtifactError(f"non-finite JSON constant is forbidden: {value}")


def _walk_finite(value: Any, label: str) -> None:
    if isinstance(value, float):
        _require(math.isfinite(value), f"{label} contains a non-finite number")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _walk_finite(item, f"{label}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_finite(item, f"{label}[{index}]")


def _load_json(path: Path) -> Any:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_duplicate_guard,
            parse_constant=_bad_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ArtifactError) as exc:
        raise ArtifactError(f"cannot parse strict JSON {path}: {exc}") from exc
    _walk_finite(value, path.name)
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _normalize_ref(value: str) -> str:
    for prefix in ("refs/heads/", "refs/tags/"):
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value


def _validate_expected_ledger(
    value: Any,
    *,
    repository: str,
    source_run_id: int,
) -> dict[str, Any]:
    ledger = _mapping(value, "artifact ledger")
    _require(ledger.get("schema") == EXPECTED_SCHEMA, "artifact-ledger schema mismatch")
    _require(ledger.get("repository") == repository, "artifact-ledger repository mismatch")
    _require(ledger.get("source_run_id") == source_run_id, "artifact-ledger run mismatch")
    run_attempt = _integer(ledger.get("source_run_attempt"), "source run attempt")
    head_sha = _hex(ledger.get("source_head_sha"), "source head SHA", HEX40)
    source_ref = _string(ledger.get("source_ref"), "source ref")
    workflow_sha = _hex(ledger.get("source_workflow_sha"), "source workflow SHA", HEX40)
    workflow_path = _string(ledger.get("source_workflow_path"), "source workflow path")
    _require(workflow_path == SOURCE_WORKFLOW_PATH, "source workflow path mismatch")
    artifacts = _array(ledger.get("artifacts"), "artifact ledger artifacts")
    _require(len(artifacts) == 30, "artifact ledger must name exactly 30 artifacts")
    normalized_artifacts: list[dict[str, Any]] = []
    seeds: set[int] = set()
    ids: set[int] = set()
    names: set[str] = set()
    for raw in artifacts:
        entry = _mapping(raw, "artifact ledger entry")
        _require(
            set(entry) in ({"seed", "id", "name", "digest"},
                           {"seed", "id", "name", "digest", "run_attempt"}),
            "artifact ledger entries must contain seed/id/name/digest and optional run_attempt",
        )
        seed = _integer(entry["seed"], "artifact seed")
        artifact_id = _integer(entry["id"], f"seed {seed} artifact ID")
        name = _string(entry["name"], f"seed {seed} artifact name")
        _require(ARTIFACT_NAME.fullmatch(name) is not None, f"unsafe artifact name: {name}")
        digest = _string(entry["digest"], f"seed {seed} artifact digest").lower()
        _require(DIGEST.fullmatch(digest) is not None, f"seed {seed}: malformed digest")
        _require(seed in EXPECTED_SEEDS, f"unexpected artifact seed {seed}")
        _require(seed not in seeds, f"duplicate artifact seed {seed}")
        _require(artifact_id not in ids, f"duplicate artifact ID {artifact_id}")
        _require(name not in names, f"duplicate artifact name {name}")
        entry_attempt = _integer(entry.get("run_attempt", run_attempt), "artifact run attempt")
        _require(entry_attempt <= run_attempt, "artifact attempt is from the future")
        expected_name = f"eu26-21-common-bridge-seed-{seed}-{source_run_id}-{entry_attempt}"
        _require(name == expected_name, f"artifact name mismatch for seed {seed}")
        seeds.add(seed)
        ids.add(artifact_id)
        names.add(name)
        normalized_artifacts.append(
            {"seed": seed, "id": artifact_id, "name": name, "digest": digest,
             "run_attempt": entry_attempt}
        )
    _require(seeds == set(EXPECTED_SEEDS), "artifact seed ledger is incomplete")
    normalized_artifacts.sort(key=lambda item: item["seed"])
    return {
        "schema": EXPECTED_SCHEMA,
        "repository": repository,
        "source_run_id": source_run_id,
        "source_run_attempt": run_attempt,
        "source_head_sha": head_sha,
        "source_ref": source_ref,
        "source_workflow_sha": workflow_sha,
        "source_workflow_path": workflow_path,
        "artifacts": normalized_artifacts,
    }


def validate_expected_artifact_ledger(
    value: Any,
    *,
    repository: str,
    source_run_id: int,
) -> dict[str, Any]:
    """Public pure validator for the explicit 30-artifact source ledger."""

    _require(REPOSITORY.fullmatch(repository) is not None, "invalid owner/repository")
    _require(source_run_id > 0, "source run ID must be positive")
    _walk_finite(value, "artifact ledger")
    return _validate_expected_ledger(
        value,
        repository=repository,
        source_run_id=source_run_id,
    )


class _DropAuthorizationOnCrossOriginRedirect(urllib.request.HTTPRedirectHandler):
    """Do not forward the GitHub token to signed blob-storage URLs."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None
        old_origin = urllib.parse.urlsplit(req.full_url)[:2]
        new_origin = urllib.parse.urlsplit(newurl)[:2]
        if old_origin != new_origin:
            redirected.remove_header("Authorization")
        return redirected


class GitHubReader:
    def __init__(self, token: str) -> None:
        _require(bool(token), "GH_TOKEN or GITHUB_TOKEN is required")
        self._token = token
        self._opener = urllib.request.build_opener(
            _DropAuthorizationOnCrossOriginRedirect()
        )

    def _request(self, url: str) -> urllib.request.Request:
        parsed = urllib.parse.urlsplit(url)
        _require(parsed.scheme == "https", "GitHub API URL must use HTTPS")
        _require(parsed.netloc == "api.github.com", "unexpected GitHub API host")
        return urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "eu26-21-common-bridge-reaggregation/1.0",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def json(self, url: str) -> Mapping[str, Any]:
        try:
            with self._opener.open(self._request(url), timeout=60) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise ArtifactError(f"GitHub API returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ArtifactError(f"GitHub API request failed: {exc.reason}") from exc
        try:
            value = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_duplicate_guard,
                parse_constant=_bad_constant,
            )
        except (UnicodeError, json.JSONDecodeError, ArtifactError) as exc:
            raise ArtifactError("GitHub API returned malformed JSON") from exc
        _walk_finite(value, "GitHub API response")
        return _mapping(value, "GitHub API response")

    def download(self, url: str, destination: Path) -> str:
        digest = hashlib.sha256()
        try:
            with self._opener.open(self._request(url), timeout=180) as response:
                with destination.open("wb") as handle:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        digest.update(block)
                        handle.write(block)
        except urllib.error.HTTPError as exc:
            raise ArtifactError(f"artifact download returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ArtifactError(f"artifact download failed: {exc.reason}") from exc
        return digest.hexdigest()


def _safe_member_path(name: str) -> PurePosixPath:
    _require("\\" not in name, f"ZIP member uses a backslash: {name!r}")
    path = PurePosixPath(name)
    _require(not path.is_absolute(), f"ZIP member is absolute: {name!r}")
    _require(bool(path.parts), "ZIP member path is empty")
    _require(".." not in path.parts, f"ZIP member escapes root: {name!r}")
    _require("" not in path.parts, f"ZIP member has an empty component: {name!r}")
    return path


def _extract_authenticated_zip(
    zip_path: Path,
    *,
    destination: Path,
    output_root: Path,
) -> list[dict[str, Any]]:
    _require(not destination.exists(), f"artifact extraction target already exists: {destination}")
    destination.mkdir(parents=True)
    extracted: list[dict[str, Any]] = []
    names: set[str] = set()
    total_size = 0
    try:
        archive = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ArtifactError("downloaded artifact is not a valid ZIP") from exc
    with archive:
        infos = archive.infolist()
        _require(bool(infos), "downloaded artifact ZIP is empty")
        for info in infos:
            member = _safe_member_path(info.filename)
            normalized_name = member.as_posix()
            _require(normalized_name not in names, f"duplicate ZIP member: {normalized_name}")
            names.add(normalized_name)
            mode = (info.external_attr >> 16) & 0o170000
            _require(mode != stat.S_IFLNK, f"ZIP symlink is forbidden: {normalized_name}")
            _require((info.flag_bits & 0x1) == 0, f"encrypted ZIP member is forbidden: {normalized_name}")
            total_size += info.file_size
            _require(
                total_size <= MAX_ARTIFACT_UNCOMPRESSED_BYTES,
                "artifact exceeds the uncompressed-size safety limit",
            )
            target = destination.joinpath(*member.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            written = 0
            with archive.open(info, "r") as source, target.open("xb") as sink:
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    digest.update(block)
                    sink.write(block)
                    written += len(block)
            _require(written == info.file_size, f"short extraction for {normalized_name}")
            extracted.append(
                {
                    "path": target.relative_to(output_root).as_posix(),
                    "sha256": digest.hexdigest(),
                    "bytes": written,
                }
            )
    extracted.sort(key=lambda item: item["path"])
    return extracted


def _verify_run(
    api: GitHubReader,
    *,
    repository: str,
    expected: Mapping[str, Any],
) -> Mapping[str, Any]:
    run_id = expected["source_run_id"]
    run = api.json(
        f"https://api.github.com/repos/{repository}/actions/runs/{run_id}"
        f"/attempts/{expected['source_run_attempt']}"
    )
    _require(run.get("id") == run_id, "GitHub run ID mismatch")
    _require(run.get("run_attempt") == expected["source_run_attempt"], "run-attempt mismatch")
    _require(run.get("head_sha") == expected["source_head_sha"], "source head SHA mismatch")
    _require(
        _normalize_ref(_string(run.get("head_branch"), "API head branch"))
        == _normalize_ref(expected["source_ref"]),
        "source ref mismatch",
    )
    _require(run.get("event") == "workflow_dispatch", "source run was not workflow_dispatch")
    _require(run.get("status") == "completed", "source run is not complete")
    _require(
        run.get("conclusion") in {"success", "failure"},
        "source run conclusion is not eligible for evidence recovery",
    )
    _require(run.get("path") == SOURCE_WORKFLOW_PATH, "source workflow path mismatch")
    return run


def _verify_artifact(
    api: GitHubReader,
    *,
    repository: str,
    source_run_id: int,
    source_head_sha: str,
    expected: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    artifact_id = expected["id"]
    metadata = api.json(
        f"https://api.github.com/repos/{repository}/actions/artifacts/{artifact_id}"
    )
    _require(metadata.get("id") == artifact_id, "artifact ID mismatch")
    _require(metadata.get("name") == expected["name"], f"artifact {artifact_id}: name mismatch")
    _require(metadata.get("digest") == expected["digest"], f"artifact {artifact_id}: digest mismatch")
    _require(metadata.get("expired") is False, f"artifact {artifact_id} is expired")
    _integer(metadata.get("size_in_bytes"), f"artifact {artifact_id} size")
    workflow_run = _mapping(metadata.get("workflow_run"), f"artifact {artifact_id} workflow run")
    _require(workflow_run.get("id") == source_run_id, f"artifact {artifact_id}: source run mismatch")
    _require(
        workflow_run.get("head_sha") == source_head_sha,
        f"artifact {artifact_id}: source head mismatch",
    )

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"artifact-{artifact_id}-", suffix=".zip", dir=output_dir, delete=False
        ) as handle:
            temporary = Path(handle.name)
        zip_sha = api.download(
            f"https://api.github.com/repos/{repository}/actions/artifacts/{artifact_id}/zip",
            temporary,
        )
        expected_zip_sha = DIGEST.fullmatch(expected["digest"])
        assert expected_zip_sha is not None
        _require(
            zip_sha == expected_zip_sha.group(1),
            f"artifact {artifact_id}: downloaded ZIP SHA mismatch",
        )
        extraction_dir = output_dir / expected["name"]
        files = _extract_authenticated_zip(
            temporary, destination=extraction_dir, output_root=output_dir
        )
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

    return {
        **dict(expected),
        "downloaded_zip_sha256": zip_sha,
        "api_run_id": workflow_run["id"],
        "api_head_sha": workflow_run["head_sha"],
        "api_size_in_bytes": metadata["size_in_bytes"],
        "api_created_at": metadata.get("created_at"),
        "api_expires_at": metadata.get("expires_at"),
        "extraction_directory": expected["name"],
        "extracted_files": files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    parser.add_argument("--artifact-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    args = parser.parse_args()

    ledger_path = args.artifact_ledger.resolve()
    metadata_output = args.metadata_output.resolve()
    partial: list[dict[str, Any]] = []
    expected_ledger_sha256: str | None = None
    try:
        _require(REPOSITORY.fullmatch(args.repository) is not None, "invalid owner/repository")
        _require(args.source_run_id > 0, "source run ID must be positive")
        expected_ledger_sha256 = _file_sha256(ledger_path)
        expected = validate_expected_artifact_ledger(
            _load_json(ledger_path),
            repository=args.repository,
            source_run_id=args.source_run_id,
        )
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        api = GitHubReader(token)
        run = _verify_run(api, repository=args.repository, expected=expected)
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        for artifact in expected["artifacts"]:
            partial.append(
                _verify_artifact(
                    api,
                    repository=args.repository,
                    source_run_id=args.source_run_id,
                    source_head_sha=expected["source_head_sha"],
                    expected=artifact,
                    output_dir=output_dir,
                )
            )
        result = {
            "schema": OUTPUT_SCHEMA,
            "verification_status": "PASS",
            "repository": expected["repository"],
            "source_run_id": expected["source_run_id"],
            "source_run_attempt": expected["source_run_attempt"],
            "source_head_sha": expected["source_head_sha"],
            "source_ref": expected["source_ref"],
            "source_workflow_sha": expected["source_workflow_sha"],
            "source_workflow_path": expected["source_workflow_path"],
            "source_event": run.get("event"),
            "source_status": run.get("status"),
            "source_conclusion": run.get("conclusion"),
            "expected_ledger_sha256": expected_ledger_sha256,
            "optimizer_rerun": False,
            "artifacts": partial,
        }
        _write_json(metadata_output, result)
        print(
            json.dumps(
                {
                    "schema": OUTPUT_SCHEMA,
                    "verification_status": "PASS",
                    "source_run_id": args.source_run_id,
                    "artifact_count": len(partial),
                    "optimizer_rerun": False,
                },
                sort_keys=True,
            )
        )
    except Exception as exc:
        failure = {
            "schema": OUTPUT_SCHEMA,
            "verification_status": "FAIL",
            "repository": args.repository,
            "source_run_id": args.source_run_id,
            "expected_ledger_sha256": expected_ledger_sha256,
            "optimizer_rerun": False,
            "verified_artifacts_before_failure": partial,
            "error": f"{type(exc).__name__}: {exc}",
        }
        try:
            _write_json(metadata_output, failure)
        except Exception as write_exc:
            print(f"failed to write verification diagnostics: {write_exc}", file=sys.stderr)
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

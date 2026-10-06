"""CI-only, exact-ID artifact transport; never list or inspect scientific results.

The authenticated GitHub REST redirect is handled manually so GH_TOKEN is not
forwarded to signed storage URLs. Archive contents are extracted only after
their metadata-bound SHA256 has been verified.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile


MAX_ARCHIVE_BYTES = 2 * 1024**3
MAX_EXTRACTED_BYTES = 4 * 1024**3
MAX_MEMBERS = 20000
MAX_ATTEMPTS = 5
TRANSIENT_HTTP = set(range(500, 600))
RATE_LIMIT_WAIT_CAP = 65 * 60
RATE_LIMIT_SLEEP_CHUNK = 60
RATE_LIMIT_MARGIN = 5


class ArtifactError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactError(message)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def secure_url(value: str) -> str:
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None
            and not parsed.fragment, "invalid artifact storage redirect")
    return value


class GitHubArtifactAPI:
    def __init__(self, repository: str, token: str):
        require(bool(token), "GH_TOKEN is missing")
        self.repository = repository
        self.token = token
        self.opener = build_opener(NoRedirect())
        self.rate_limit_waited = 0.0

    def request(self, artifact_id: int, suffix: str = "") -> Request:
        return Request(f"https://api.github.com/repos/{self.repository}/actions/artifacts/{artifact_id}{suffix}",
                       headers={"Authorization": f"Bearer {self.token}",
                                "Accept": "application/vnd.github+json",
                                "X-GitHub-Api-Version": "2022-11-28"})

    def rate_limit_delay(self, code: int, headers) -> float | None:
        if code not in (403, 429):
            return None
        delays = []
        retry_after = headers.get("Retry-After") if headers is not None else None
        remaining = headers.get("x-ratelimit-remaining") if headers is not None else None
        if retry_after is not None:
            require(isinstance(retry_after, str) and re.fullmatch(r"[0-9]{1,12}", retry_after) is not None,
                    "invalid rate-limit Retry-After header")
            delays.append(float(int(retry_after)) + RATE_LIMIT_MARGIN)
        if remaining == "0":
            reset = headers.get("x-ratelimit-reset")
            require(isinstance(reset, str) and re.fullmatch(r"[0-9]{1,12}", reset) is not None,
                    "invalid primary rate-limit reset header")
            now = time.time()
            require(math.isfinite(now), "invalid rate-limit clock")
            delays.append(float(int(reset)) - now + RATE_LIMIT_MARGIN)
        if not delays:
            return None
        delay = max(delays)
        require(math.isfinite(delay) and 0 < delay <= RATE_LIMIT_WAIT_CAP,
                "rate-limit wait is invalid or exceeds the 65-minute cap")
        return delay

    def wait_rate_limit(self, seconds: float) -> None:
        require(math.isfinite(seconds) and seconds > 0
                and self.rate_limit_waited + seconds <= RATE_LIMIT_WAIT_CAP,
                "cumulative rate-limit wait exceeds the 65-minute cap")
        print(f"GitHub artifact rate limit: waiting {math.ceil(seconds)} seconds in bounded chunks")
        self.rate_limit_waited += seconds
        remaining = seconds
        while remaining > 0:
            chunk = min(remaining, RATE_LIMIT_SLEEP_CHUNK)
            time.sleep(chunk)
            remaining -= chunk

    def retry(self, operation):
        for attempt in range(MAX_ATTEMPTS):
            rate_limit_delay = None
            try:
                return operation()
            except HTTPError as error:
                code = error.code
                try:
                    origin = urlsplit(error.url)
                    authenticated_api_error = (not getattr(error, "study_signed_storage", False)
                        and origin.scheme == "https" and origin.hostname == "api.github.com"
                        and origin.username is None and origin.password is None
                        and origin.path.startswith(f"/repos/{self.repository}/actions/artifacts/"))
                    if authenticated_api_error:
                        rate_limit_delay = self.rate_limit_delay(code, error.headers)
                finally:
                    error.close()
                if rate_limit_delay is None and code not in TRANSIENT_HTTP:
                    raise ArtifactError(f"artifact HTTP request failed: status {code}") from None
            except (URLError, TimeoutError, ConnectionError, http.client.IncompleteRead):
                # Do not expose signed query strings, token headers or URL errors.
                pass
            if attempt + 1 == MAX_ATTEMPTS:
                raise ArtifactError("artifact transport exhausted five transient attempts") from None
            if rate_limit_delay is not None:
                self.wait_rate_limit(rate_limit_delay)
            else:
                time.sleep(2**attempt)
        raise AssertionError("unreachable retry state")

    def metadata(self, artifact_id: int) -> dict:
        def operation():
            with self.opener.open(self.request(artifact_id), timeout=60) as response:
                raw = response.read(1024 * 1024 + 1)
            require(len(raw) <= 1024 * 1024, "artifact metadata exceeds limit")
            try:
                value = json.loads(raw)
            except (ValueError, UnicodeError):
                raise ArtifactError("invalid artifact metadata JSON") from None
            require(isinstance(value, dict), "artifact metadata must be an object")
            return value
        return self.retry(operation)

    def download(self, artifact_id: int, destination: Path) -> None:
        def operation():
            try:
                response = self.opener.open(self.request(artifact_id, "/zip"), timeout=60)
            except HTTPError as error:
                if error.code != 302:
                    raise
                location = error.headers.get("Location", "")
                error.close()
                # A new Request has no Authorization header. Never automatically
                # redirect an authenticated request to the external storage host.
                request = Request(secure_url(location))
                try:
                    response = self.opener.open(request, timeout=60)
                except HTTPError as error:
                    error.study_signed_storage = True
                    raise
            with response, destination.open("wb") as stream:
                size = 0
                while block := response.read(1024 * 1024):
                    size += len(block)
                    require(size <= MAX_ARCHIVE_BYTES, "artifact archive exceeds limit")
                    stream.write(block)
        self.retry(operation)


def artifact_ids(value: str) -> list[int]:
    parts = value.split(",")
    require(bool(parts) and all(re.fullmatch(r"[1-9][0-9]*", part) for part in parts),
            "artifact IDs must be a nonempty canonical comma-separated list")
    ids = [int(part) for part in parts]
    require(len(ids) == len(set(ids)), "duplicate requested artifact ID")
    return ids


def validate_metadata(value: dict, *, artifact_id: int, run_id: int,
                      expected_sha: str, kind: str) -> dict:
    require(isinstance(value, dict) and type(value.get("id")) is int
            and value["id"] == artifact_id, "requested artifact ID mismatch")
    run = value.get("workflow_run")
    require(isinstance(run, dict) and type(run.get("id")) is int
            and run["id"] == run_id and run.get("head_sha") == expected_sha,
            "artifact run or source SHA mismatch")
    require(value.get("expired") is False, "artifact is expired or missing expiry status")
    require(type(value.get("size_in_bytes")) is int and 0 < value["size_in_bytes"] <= MAX_ARCHIVE_BYTES,
            "artifact metadata size is invalid")
    digest = value.get("digest")
    require(isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is not None,
            "artifact SHA256 digest is missing or invalid")
    suffixes = {"smoke": "", "fixture": "", "registry": "", "case": r"(420(?:0[1-9]|[12][0-9]|30))-",
                "escape": r"(420(?:0[1-9]|[12][0-9]|30))-([1-5])-",
                "lambda-smoke": "", "lambda-fixture": "",
                "lambda-case": r"(430(?:0[1-9]|[12][0-9]|30))-",
                "qx-smoke": "", "qx-fixture": "", "qx-registry": "",
                "qx-source-fixture": "", "qx-source-smoke": "",
                "qx-preparation": r"(440(?:0[1-9]|[12][0-9]|30))-",
                "qx-case": r"(440(?:0[1-9]|[12][0-9]|30))-",
                "lr-smoke": "", "lr-fixture": "", "lr-registry": "",
                "lr-preparation": r"(450(?:0[1-9]|[12][0-9]|30))-",
                "lr-case": r"(450(?:0[1-9]|[12][0-9]|30))-"}
    require(kind in suffixes, "invalid artifact kind")
    namespace = ("eu26-21-" + kind if kind.startswith(("qx-", "lr-")) else
                 "eu26-21-lambda-case" if kind == "lambda-case" else
                 "eu26-21-lambda-initial-" + kind.removeprefix("lambda-")
                 if kind.startswith("lambda-") else "eu26-21-local-" + kind)
    name = value.get("name")
    require(isinstance(name, str)
            and re.fullmatch(rf"{namespace}-{suffixes[kind]}{run_id}-[1-9][0-9]*", name) is not None,
            "artifact name does not match the requested kind and run")
    return value


def verify_archive(path: Path, metadata: dict) -> None:
    require(path.stat().st_size == metadata["size_in_bytes"], "downloaded artifact ZIP size mismatch")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    require(digest.hexdigest() == metadata["digest"].removeprefix("sha256:"),
            "downloaded artifact ZIP SHA256 mismatch")


def extract_archive(path: Path, destination: Path) -> None:
    require(not destination.is_symlink(), "artifact destination cannot be a symlink")
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            require(0 < len(members) <= MAX_MEMBERS, "artifact ZIP member count is invalid")
            seen, file_paths, total = set(), set(), 0
            targets = []
            for member in members:
                name = member.filename
                parts = PurePosixPath(name).parts
                require(name and "\\" not in name and ":" not in name and "\x00" not in name
                        and not name.startswith("/") and parts
                        and all(part not in (".", "..") for part in parts)
                        and not any(part == "" for part in name.rstrip("/").split("/")),
                        "unsafe artifact ZIP member path")
                relative = PurePosixPath(*parts)
                normalized = str(relative).casefold()
                require(normalized not in seen, "duplicate artifact ZIP member path")
                seen.add(normalized)
                mode = stat.S_IFMT(member.external_attr >> 16)
                require(mode in (0, stat.S_IFREG, stat.S_IFDIR)
                        and not (mode == stat.S_IFDIR and not member.is_dir())
                        and not member.flag_bits & 1, "unsupported artifact ZIP member type")
                require(0 <= member.file_size <= MAX_ARCHIVE_BYTES, "artifact ZIP member exceeds limit")
                total += member.file_size
                require(total <= MAX_EXTRACTED_BYTES, "artifact ZIP expanded size exceeds limit")
                target = root.joinpath(*relative.parts)
                require(target.resolve().is_relative_to(root), "artifact ZIP member escapes destination")
                require(not target.is_symlink() and not any(parent.is_symlink()
                        for parent in target.parents if parent != root and parent.is_relative_to(root)),
                        "artifact ZIP path intersects a symlink")
                require(not target.exists() or (member.is_dir() and target.is_dir()),
                        "artifact extraction would overwrite an existing path")
                if not member.is_dir():
                    file_paths.add(normalized)
                targets.append((member, target, relative))
            for _, _, relative in targets:
                require(not any(str(parent).casefold() in file_paths for parent in relative.parents
                                if str(parent) != "."), "artifact ZIP file/directory collision")
            for member, target, _ in targets:
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
    except zipfile.BadZipFile:
        raise ArtifactError("artifact ZIP is corrupt") from None


def download_artifacts(*, ids: list[int], repository: str, run_id: int,
                       expected_sha: str, kind: str, destination: Path,
                       merge_multiple: bool = False, api=None,
                       transport_ledger: Path | None = None) -> None:
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is not None,
            "invalid repository identifier")
    require(type(run_id) is int and run_id > 0
            and re.fullmatch(r"[0-9a-f]{40}", expected_sha) is not None, "invalid source run or SHA")
    require(ids and all(type(value) is int and value > 0 for value in ids)
            and len(ids) == len(set(ids)), "requested artifact IDs are invalid or duplicated")
    require(not merge_multiple or len(ids) == 1, "flat extraction requires exactly one artifact ID")
    if transport_ledger is not None:
        require(not transport_ledger.exists() and not transport_ledger.is_symlink(),
                "transport ledger would overwrite an existing path")
        require(not transport_ledger.resolve().is_relative_to(destination.resolve()),
                "transport ledger must remain outside extracted artifact contents")
    api = api or GitHubArtifactAPI(repository, os.environ.get("GH_TOKEN", ""))
    metadata = [validate_metadata(api.metadata(value), artifact_id=value, run_id=run_id,
                                 expected_sha=expected_sha, kind=kind) for value in ids]
    require(len({value["name"] for value in metadata}) == len(metadata), "duplicate artifact names")
    verified = []
    with tempfile.TemporaryDirectory(prefix="study-artifact-download-") as temporary:
        for value in metadata:
            path = Path(temporary) / f"{value['id']}.zip"
            api.download(value["id"], path)
            verify_archive(path, value)
            target = destination if merge_multiple else destination / value["name"]
            extract_archive(path, target)
            verified.append({
                "id": value["id"], "name": value["name"], "digest": value["digest"],
                "size_in_bytes": value["size_in_bytes"],
                "verified_zip_sha256": value["digest"].removeprefix("sha256:"),
                "verified_zip_bytes": value["size_in_bytes"],
                "zip_verified_before_extraction": True,
            })
            print(f"Authenticated artifact ID {value['id']} ({value['name']})")
    if transport_ledger is not None:
        transport_ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger = {"schema": "eu26-21-exact-id-transport-ledger-v1",
                  "repository": repository, "source_run_id": run_id,
                  "implementation_sha": expected_sha, "kind": kind,
                  "complete": True, "artifacts": verified}
        with transport_ledger.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(ledger, sort_keys=True, indent=2, allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-ids", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--kind", choices=("smoke", "fixture", "registry", "case", "escape",
                                          "lambda-smoke", "lambda-fixture", "lambda-case",
                                          "qx-smoke", "qx-fixture", "qx-registry",
                                          "qx-source-fixture", "qx-source-smoke",
                                          "qx-preparation", "qx-case", "lr-smoke", "lr-fixture",
                                          "lr-registry", "lr-preparation", "lr-case"), required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--merge-multiple", action="store_true")
    parser.add_argument("--transport-ledger", type=Path)
    args = parser.parse_args()
    require(os.environ.get("GITHUB_ACTIONS") == "true", "artifact download is CI-only")
    require(args.repository == os.environ.get("GITHUB_REPOSITORY")
            and str(args.run_id) == os.environ.get("GITHUB_RUN_ID")
            and args.expected_sha == os.environ.get("EXPECTED_SHA")
            == os.environ.get("GITHUB_SHA") == os.environ.get("STUDY_WORKFLOW_SHA"),
            "artifact request differs from the exact workflow run and SHA")
    download_artifacts(ids=artifact_ids(args.artifact_ids), repository=args.repository,
                       run_id=args.run_id, expected_sha=args.expected_sha, kind=args.kind,
                       destination=args.destination, merge_multiple=args.merge_multiple,
                       transport_ledger=args.transport_ledger)


if __name__ == "__main__":
    main()

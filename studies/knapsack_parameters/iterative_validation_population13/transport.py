"""Retrieve only pinned retained members for the separately admitted CI stage.

Full source ZIPs are temporary transport bytes. No search, exact solver, bank
generation, statistical analysis, or fallback source is available in this module.
"""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import ZipFile

from .common import HERE, ROOT, REPOSITORY, guard_technical, validate_plan
from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha

API_ROOT = "https://api.github.com/repos/" + REPOSITORY + "/actions/artifacts/"
EXPECTED_IDS = {13764860849, 13764640242, 13797092537, 13762967913}
EXPECTED_ARCHIVE_BYTES = 491214252
PREPARED_ID = 13762967913
LOCAL_ID = "committed-retained-inputs"
CHUNK = 1024 * 1024
MAX_MEMBERS = 5000
MAX_DECLARED_MEMBER_BYTES = 128 * 1024**2
MAX_DECLARED_ARCHIVE_BYTES = 1024**3
REDIRECT_CODES = (301, 302, 303, 307, 308)


class NoRedirect(HTTPRedirectHandler):
    """Return redirects to the caller so credentials never follow a Location."""

    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def safe_relative(relative):
    """Accept one canonical POSIX file path, without aliases or traversal."""
    require(type(relative) is str and relative and "\\" not in relative and ":" not in relative
            and all(32 <= ord(character) != 127 for character in relative),
            "Unsafe retained member path")
    path = PurePosixPath(relative)
    require(not path.is_absolute() and ".." not in path.parts and "." not in path.parts
            and path.as_posix() == relative and not relative.endswith("/"),
            "Unsafe retained member path")
    return path


def validate_members(archive):
    """Inspect every ZIP name, without expanding unselected members."""
    members, casefolded, declared = {}, set(), 0
    entries = archive.infolist()
    require(0 < len(entries) <= MAX_MEMBERS, "Retained ZIP member count exceeds its bound")
    for entry in entries:
        name = entry.filename
        canonical = name[:-1] if entry.is_dir() else name
        safe_relative(canonical)
        require(name not in members and canonical.casefold() not in casefolded
                and not stat.S_ISLNK(entry.external_attr >> 16)
                and not entry.flag_bits & 1,
                "Duplicate, encrypted, or linked retained ZIP member")
        require(0 <= entry.file_size <= MAX_DECLARED_MEMBER_BYTES,
                "Retained ZIP member exceeds its declared byte bound")
        declared += entry.file_size
        require(declared <= MAX_DECLARED_ARCHIVE_BYTES, "Retained ZIP declared expansion exceeds its bound")
        members[name] = entry
        casefolded.add(canonical.casefold())
    return members


def _validate_descriptor(entry):
    safe_relative(entry.get("path"))
    require(re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", "")) is not None,
            "Retained member SHA256 is absent")
    size, maximum = entry.get("bytes"), entry.get("max_bytes")
    require(type(size) is int and size > 0
            or size is None and type(maximum) is int and 0 < maximum <= 32 * 1024**2,
            "Retained member exact size or strict byte bound is absent")
    return size if size is not None else maximum


def validate_registry(registry, plan):
    """Check the four exact source identities before any network operation."""
    require(registry.get("schema") == "iterative-validation-population13-reference-sources-v1",
            "Unregistered reference registry")
    entries = registry.get("remote_artifacts")
    require(type(entries) is list and len(entries) == 4
            and {entry.get("id") for entry in entries} == EXPECTED_IDS,
            "Exactly the four pinned retained artifacts are required")
    require(plan.get("remote_artifacts") == entries
            and plan.get("local_input_archive") == registry.get("local_input_archive"),
            "Input plan and reference transport differ")
    total = 0
    for entry in entries:
        require(type(entry.get("id")) is int and type(entry.get("bytes")) is int
                and 0 < entry["bytes"] <= 256 * 1024**2
                and re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", "")) is not None
                and type(entry.get("run_id")) is int and entry["run_id"] > 0
                and re.fullmatch(r"[0-9a-f]{40}", entry.get("commit", "")) is not None,
                "Pinned retained archive identity differs")
        url = API_ROOT + str(entry["id"])
        require(entry.get("metadata_url") == url and entry.get("archive_download_url") == url + "/zip",
                "Only the registered GitHub artifact endpoint is permitted")
        total += entry["bytes"]
    require(total == EXPECTED_ARCHIVE_BYTES == plan.get("remote_archive_bytes"),
            "Pinned archive transport byte total differs")
    return entries


def _check_metadata(metadata, entry):
    require(metadata.get("id") == entry["id"] and metadata.get("name") == entry["name"]
            and metadata.get("size_in_bytes") == entry["bytes"]
            and metadata.get("digest") == "sha256:" + entry["sha256"]
            and metadata.get("expired") is False
            and metadata.get("workflow_run", {}).get("id") == entry["run_id"]
            and metadata["workflow_run"].get("head_sha") == entry["commit"],
            "Retained GitHub metadata or immutable workflow origin differs")


def _https_location(location):
    parsed = urlparse(location)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username
            and not parsed.password and not parsed.fragment,
            "Unsafe retained artifact redirect")
    return location


def _redirect(opener, request):
    """Read a Location only from the directly addressed server response."""
    try:
        response = opener.open(request, timeout=45)
    except HTTPError as error:
        try:
            require(error.code in REDIRECT_CODES, "Retained artifact archive request failed")
            return _https_location(error.headers.get("Location", ""))
        finally:
            error.close()
    else:
        with response:
            require(response.getcode() in REDIRECT_CODES, "Expected a retained artifact redirect")
            return _https_location(response.headers.get("Location", ""))


def _unsigned_response(opener, location):
    """Follow a bounded HTTPS redirect chain with no Authorization header."""
    for _ in range(4):
        request = Request(_https_location(location), headers={"User-Agent": "population13-retained-transport"})
        try:
            response = opener.open(request, timeout=90)
        except HTTPError as error:
            try:
                require(error.code in REDIRECT_CODES, "Unsigned retained artifact request failed")
                location = _https_location(error.headers.get("Location", ""))
            finally:
                error.close()
        else:
            require(response.getcode() == 200, "Unsigned retained archive response differs")
            return response
    raise ValueError("Unsigned retained artifact redirect limit reached")


def download_archive(entry, token, target, *, api_opener=None, unsigned_opener=None):
    """Authenticate exact ZIP bytes; the token is used only at api.github.com."""
    require(type(token) is str and token, "Read-only GitHub artifact token is absent")
    api = api_opener or build_opener(NoRedirect())
    unsigned = unsigned_opener or build_opener(NoRedirect())
    url = API_ROOT + str(entry["id"])
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "User-Agent": "population13-retained-transport"}
    try:
        with api.open(Request(url, headers=headers), timeout=45) as response:
            require(response.getcode() == 200 and response.geturl() == url,
                    "Retained artifact metadata redirected")
            content = response.read(128 * 1024 + 1)
            require(len(content) <= 128 * 1024, "Retained artifact metadata exceeds its byte bound")
            _check_metadata(json.loads(content), entry)
        location = _redirect(api, Request(url + "/zip", headers=headers))
        digest, count = sha256(), 0
        with _unsigned_response(unsigned, location) as response, Path(target).open("xb") as outgoing:
            while True:
                chunk = response.read(min(CHUNK, entry["bytes"] - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                require(count <= entry["bytes"], "Retained archive exceeds its pinned length")
                digest.update(chunk)
                outgoing.write(chunk)
        require(count == entry["bytes"] and digest.hexdigest() == entry["sha256"],
                "Retained archive exact length or SHA256 differs")
    except (HTTPError, URLError) as error:
        # Do not expose a signed archive URL or request headers in CI logs.
        raise RuntimeError("Pinned retained artifact HTTP retrieval failed") from None
    return {"id": entry["id"], "name": entry["name"], "bytes": count,
            "sha256": digest.hexdigest(), "run_id": entry["run_id"], "commit": entry["commit"]}


def retain_members(archive_path, selections, output, budget, *, failure_context=None):
    """Stream only selected members, checking their pinned full-file hashes."""
    receipts = []
    with ZipFile(archive_path) as archive:
        members = validate_members(archive)
        for selection in selections:
            if failure_context is not None:
                failure_context["requested_member"] = None
            entry = selection["descriptor"]
            bound = _validate_descriptor(entry)
            name = selection["source_member"]
            safe_relative(name)
            if failure_context is not None:
                failure_context["requested_member"] = name
            require(name in members and not members[name].is_dir(), "Required original retained member is absent")
            member = members[name]
            require(0 < member.file_size <= bound
                    and (entry["bytes"] is None or member.file_size == entry["bytes"]),
                    "Retained member exact length or strict byte bound differs")
            require(budget["used"] + member.file_size <= budget["limit"] - 128 * 1024,
                    "Selected retained evidence exceeds its transport output cap")
            relative = safe_relative(entry["path"])
            destination = Path(output).joinpath(*relative.parts)
            require(destination.resolve().is_relative_to(Path(output).resolve())
                    and not destination.exists(), "Retained output aliases or overwrites an existing file")
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest, count = sha256(), 0
            with archive.open(member) as incoming, destination.open("xb") as outgoing:
                while True:
                    chunk = incoming.read(min(CHUNK, bound - count + 1))
                    if not chunk:
                        break
                    count += len(chunk)
                    require(count <= bound, "Retained member expanded beyond its declared bound")
                    outgoing.write(chunk)
                    digest.update(chunk)
            require(count == member.file_size and digest.hexdigest() == entry["sha256"],
                    "Retained member exact SHA256 differs")
            budget["used"] += count
            receipts.append({"path": entry["path"], "bytes": count, "sha256": digest.hexdigest(),
                             "source_member": name, "artifact_id": selection["artifact_id"],
                             "task": selection["task"], "role": selection["role"]})
    return receipts


def _selections(registry, plan):
    by_id = validate_plan(plan)
    inputs = {row["task"]: row for row in registry["inputs"]}
    references = {row["task"]: row for row in registry["compatibility_references"]}
    result = {artifact: [] for artifact in EXPECTED_IDS | {LOCAL_ID}}
    for row in by_id.values():
        source = inputs[row["task"]]
        names = ("problem", "certificate") if row["mode"] == "pilot" else ("problem", "certificate", "source")
        artifact = LOCAL_ID if row["mode"] == "pilot" else PREPARED_ID
        for name in names:
            require(row[name] == source[name], "Selected source descriptor differs from the pinned registry")
            result[artifact].append({"descriptor": row[name], "source_member": row[name]["archive_member"],
                                     "artifact_id": artifact, "task": row["task"], "role": name})
        if row["mode"] == "compatibility":
            reference = references[row["task"]]
            for name in ("bank", "reference_journal"):
                descriptor = row[name]
                require(all(descriptor.get(key) == value for key, value in reference[name].items()),
                        "Original bank or full-journal descriptor differs")
                artifact = descriptor["artifact_id"]
                require(artifact in EXPECTED_IDS, "Selected retained artifact is unregistered")
                result[artifact].append({"descriptor": descriptor, "source_member": descriptor["archive_member"],
                                         "artifact_id": artifact, "task": row["task"], "role": name})
    return result


def _retain_pilot_sources(registry, plan, output, budget):
    receipts = []
    pilots = {row["task"]: row for row in registry["inputs"] if row["mode"] == "pilot"}
    for row in plan["cases"]:
        if row["mode"] != "pilot":
            continue
        entry = row["source"]
        require(entry == pilots[row["task"]]["source"], "Retained pilot raw source descriptor differs")
        safe_relative(entry["source_record_path"])
        expected_record = "studies/knapsack_parameters/population_validation_100/data/technical/" + row["task"] + ".source.json"
        require(entry["source_record_path"] == expected_record and entry.get("source_record_field") == "raw_base64",
                "Only the existing embedded pilot raw source is permitted")
        record = read_json(ROOT / expected_record)
        require(record.get("task_id") == row["task"]
                and record.get("source_commit") == registry["source_repository"]["commit"]
                and record.get("source_path") == entry["source_path"], "Embedded pilot source identity differs")
        raw = base64.b64decode(record["raw_base64"], validate=True)
        require(len(raw) == entry["bytes"] and sha256(raw).hexdigest() == entry["sha256"],
                "Embedded pilot raw source bytes differ")
        require(budget["used"] + len(raw) <= budget["limit"] - 128 * 1024,
                "Embedded pilot raw sources exceed the output cap")
        target = Path(output).joinpath(*safe_relative(entry["path"]).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as outgoing:
            outgoing.write(raw)
        budget["used"] += len(raw)
        receipts.append({"path": entry["path"], "bytes": len(raw), "sha256": entry["sha256"],
                         "source_record_path": expected_record, "artifact_id": LOCAL_ID,
                         "task": row["task"], "role": "source"})
    return receipts


def retrieve(out, authorization_id=None):
    """Admission precedes token access, network I/O, extraction, or preparation."""
    protocol, authorization = guard_technical(authorization_id)
    registry_path, plan_path = HERE / "reference_sources.json", HERE / "retained_input_plan.json"
    registry, plan = read_json(registry_path), read_json(plan_path)
    entries = validate_registry(registry, plan)
    selections = _selections(registry, plan)
    output = Path(out)
    require(not output.exists(), "Preserve previous or interrupted retained transport")
    token = os.environ.get("GITHUB_TOKEN", "")
    require(bool(token), "Read-only GitHub artifact token is absent")
    local = registry["local_input_archive"]
    require(local["path"] == "studies/knapsack_parameters/initial_grid_100/data/retained_inputs.zip"
            and (ROOT / local["path"]).stat().st_size == local["bytes"]
            and sha(ROOT / local["path"]) == local["sha256"], "Committed retained input archive differs")
    output.mkdir(parents=True, exist_ok=False)
    budget = {"used": 0, "limit": protocol["limits"]["preparation_artifact_bytes"]}
    receipts, archives = [], []
    failure_context = {"artifact_id": LOCAL_ID, "requested_member": None}
    try:
        receipts.extend(retain_members(ROOT / local["path"], selections[LOCAL_ID], output, budget,
                                       failure_context=failure_context))
        failure_context["requested_member"] = None
        receipts.extend(_retain_pilot_sources(registry, plan, output, budget))
        archives.append({"id": LOCAL_ID, "path": local["path"], "bytes": local["bytes"], "sha256": local["sha256"]})
        # Original source ZIPs stay outside the retained root and are never uploaded.
        with tempfile.TemporaryDirectory(prefix="population13-transport-") as temporary:
            for entry in sorted(entries, key=lambda item: item["id"]):
                failure_context.update(artifact_id=entry["id"], requested_member=None)
                archive = Path(temporary) / (str(entry["id"]) + ".zip")
                origin = download_archive(entry, token, archive)
                archives.append(origin)
                receipts.extend(retain_members(archive, selections[entry["id"]], output, budget,
                                               failure_context=failure_context))
                failure_context["requested_member"] = None
                archive.unlink()
        require(len(receipts) == 24 and len({entry["path"] for entry in receipts}) == 24,
                "The retained transport must contain exactly twenty-four selected files")
        manifest = {"schema": "population13-retained-transport-v1", "status": "AUTHENTICATED_SELECTED_MEMBERS",
                    "archives": archives, "files": receipts, "selected_file_bytes": budget["used"],
                    "remote_archive_bytes": sum(entry["bytes"] for entry in entries),
                    "reference_sources_sha256": sha(registry_path), "retained_input_plan_sha256": sha(plan_path),
                    "source_manifest_sha256": authorization["source_manifest_sha256"],
                    "authorization_id": authorization["authorization_id"],
                    "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
                    "ga_runs": 0, "banks_generated": 0, "exact_solver_calls": 0,
                    "raw_source_archives_uploaded": False}
        content = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        require(budget["used"] + len(content) <= budget["limit"], "Retained transport manifest exceeds its output cap")
        with (output / "transport_manifest.json").open("xb") as stream:
            stream.write(content)
        return manifest
    except Exception as error:
        failure = {"status": "RETAINED_TRANSPORT_INCOMPLETE", "error_type": type(error).__name__,
                   **failure_context,
                   "authenticated_selected_files": len(receipts), "selected_file_bytes": budget["used"],
                   "authorization_id": authorization["authorization_id"], "ga_runs": 0}
        with (output / "transport_failure.json").open("x", encoding="utf-8") as stream:
            json.dump(failure, stream, sort_keys=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--authorization-id", required=True)
    args = parser.parse_args()
    result = retrieve(args.out, args.authorization_id)
    print(json.dumps({"status": result["status"], "selected_files": len(result["files"]),
                      "selected_file_bytes": result["selected_file_bytes"], "ga_runs": 0}), flush=True)


if __name__ == "__main__":
    main()


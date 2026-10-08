"""Exact-ID artifact transport, safe extraction and immutable source ledgers."""

from __future__ import annotations

import argparse
import io
import os
from pathlib import Path, PurePosixPath
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from .contract import (BRANCH, MODULE_ROOT, PROTOCOL_ID, REPOSITORY, file_identity,
                       load_context, output_directory, read_json, require, sha256_bytes,
                       verify_file_manifest, write_json)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, newurl):
        return None


def api_get(url):
    require(urllib.parse.urlsplit(url).hostname == "api.github.com", "unexpected authenticated host")
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=60) as response:
        import json
        return json.load(response)


def download_zip(metadata):
    require(metadata.get("expired") is False, "frozen artifact expired; no replacement selected")
    digest = metadata.get("digest", "")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is not None, "artifact has no exact ZIP digest")
    request = urllib.request.Request(f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{metadata['id']}/zip",
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=90) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        require(error.code in (301, 302, 303, 307, 308), "artifact download did not return an authorized redirect")
        location = error.headers["Location"]
        require(urllib.parse.urlsplit(location).scheme == "https", "artifact redirect must use HTTPS")
        # Deliberately no authorization header on the object-store request.
        with urllib.request.urlopen(urllib.request.Request(location), timeout=180) as response:
            raw = response.read()
    require(sha256_bytes(raw) == digest[7:] and len(raw) == metadata["size_in_bytes"], "artifact ZIP hash/length mismatch")
    return raw


def extract_bundle(raw, destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    seen = set()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(sum(info.file_size for info in archive.infolist()) <= 8 * 1024 ** 3, "artifact exceeds 8 GiB extraction guard")
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            require(info.filename and not member.is_absolute() and ".." not in member.parts and
                    "\\" not in info.filename and ":" not in info.filename, "unsafe ZIP path")
            require(info.filename not in seen and ((info.external_attr >> 16) & 0o170000) != 0o120000,
                    "duplicate ZIP member or symbolic link")
            seen.add(info.filename)
            target = destination.joinpath(*member.parts)
            require(target.resolve().is_relative_to(destination), "ZIP path escapes destination")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as output:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        output.write(block)
    verify_file_manifest(destination)
    return destination


def verify_artifact_identity(metadata, *, artifact_id, source_run_id, source_sha, zip_sha256=None):
    require(metadata["id"] == artifact_id and metadata["workflow_run"]["id"] == source_run_id and
            metadata["workflow_run"]["head_sha"] == source_sha and metadata["workflow_run"]["head_branch"] == BRANCH,
            "artifact run/SHA/branch identity mismatch")
    require(metadata.get("expired") is False, "frozen artifact expired")
    if zip_sha256:
        require(metadata["digest"] == f"sha256:{zip_sha256}", "artifact digest differs from frozen source")


def retrieve_frozen(expected_sha, output):
    _, _, _, identity = load_context(expected_sha)
    output = output_directory(output)
    ledger = []
    for kind, filename in (("banks", "frozen_banks.json"), ("pilot", "frozen_pilot.json")):
        descriptor = read_json(MODULE_ROOT / filename)
        require(descriptor["protocol_id"] == PROTOCOL_ID and
                descriptor["implementation_fingerprint"] == identity["implementation_fingerprint"] and
                descriptor["runtime_lock_sha256"] == identity["runtime_lock_sha256"], "frozen source used different implementation/runtime")
        metadata = api_get(f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{descriptor['artifact_id']}")
        verify_artifact_identity(metadata, artifact_id=descriptor["artifact_id"],
                source_run_id=descriptor["run_id"], source_sha=descriptor["implementation_commit_sha"], zip_sha256=descriptor["zip_sha256"])
        require(metadata["name"] == descriptor["artifact_name"] and metadata["size_in_bytes"] == descriptor["zip_bytes"], "frozen artifact name/length mismatch")
        raw = download_zip(metadata)
        directory = extract_bundle(raw, output / kind)
        if kind == "banks":
            require(file_identity(directory / "banks_manifest.json")["sha256"] == descriptor["banks_manifest_sha256"], "bank manifest is not frozen source")
        else:
            technical = read_json(directory / "technical_result.json")
            require(file_identity(directory / "technical_result.json")["sha256"] == descriptor["technical_result_sha256"], "technical pilot report mismatch")
            for field in ("technical_status", "run_count", "projected_job_seconds", "projected_job_bytes",
                          "implementation_fingerprint", "runtime_lock_sha256", "banks_manifest_sha256"):
                require(technical[field] == descriptor[field], f"frozen pilot field mismatch: {field}")
            require(technical["technical_status"] == "PASS_TECHNICAL", "pilot did not authorize full matrix")
        ledger.append({"kind": kind, "artifact_id": metadata["id"], "run_id": descriptor["run_id"],
                       "run_attempt": descriptor["run_attempt"], "zip_sha256": sha256_bytes(raw), "zip_bytes": len(raw)})
    write_json(output / "frozen-source-transport.json", {"schema_version": "ga-knapsack-frozen-transport-v1", "provenance": identity, "downloads": ledger})
    return ledger


def expected_jobs(instances, stage):
    if stage == "pilot":
        return [{"instance_id": instance_id, "seed_first": 52001, "seed_last": 52001,
                 "job_key": f"{instance_id}-52001-52001", "name_stem": f"knapsack-ga-pilot-{instance_id}"}
                for instance_id in ("UC-s000", "WC-s001", "SC-s005")]
    require(stage in ("run", "main"), "unknown transport stage")
    return [{"instance_id": instance.instance_id, "seed_first": 51001 + batch * 10,
             "seed_last": 51010 + batch * 10,
             "job_key": f"{instance.instance_id}-{51001 + batch * 10}-{51010 + batch * 10}",
             "name_stem": f"knapsack-ga-run-{instance.instance_id}-b{batch}"}
            for instance in instances for batch in range(3)]


def collect_jobs(expected_sha, output, *, stage):
    instances, _, _, identity = load_context(expected_sha)
    output = output_directory(output)
    run_id, attempt = identity["run_id"], identity["run_attempt"]
    all_metadata = []
    page = 1
    while True:
        response = api_get(f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{run_id}/artifacts?per_page=100&page={page}")
        all_metadata.extend(response["artifacts"])
        if len(response["artifacts"]) < 100:
            break
        page += 1
    write_json(output / "artifact-api-metadata.json", {"run_id": run_id, "run_attempt": attempt, "artifacts": all_metadata})
    selected = []
    sources = {"schema_version": "ga-knapsack-sources-v1", **identity,
               "phase": "pilot" if stage == "pilot" else "main", "sources": selected}
    write_json(output / "sources.json", sources)
    for job in expected_jobs(instances, stage):
        name = f"{job['name_stem']}-{run_id}-{attempt}"
        matches = [row for row in all_metadata if row["name"] == name]
        require(len(matches) == 1, f"missing or duplicate exact-attempt artifact: {name}")
        metadata = matches[0]
        verify_artifact_identity(metadata, artifact_id=metadata["id"], source_run_id=run_id, source_sha=expected_sha)
        raw = download_zip(metadata)
        directory = extract_bundle(raw, output / "jobs" / job["job_key"])
        manifest = read_json(directory / "manifest.json")
        require(manifest["job_key"] == job["job_key"] and manifest["instance_id"] == job["instance_id"] and
                manifest["seed_first"] == job["seed_first"] and manifest["seed_last"] == job["seed_last"], "matrix artifact identity mismatch")
        require(manifest["implementation_commit_sha"] == expected_sha and manifest["run_id"] == run_id and
                manifest["run_attempt"] == attempt, "matrix evidence has mixed checkout/run/attempt")
        selected.append({key: job[key] for key in ("job_key", "instance_id", "seed_first", "seed_last")}
                        | {"run_id": run_id, "run_attempt": attempt, "artifact_id": metadata["id"],
                           "artifact_name": name, "zip_sha256": sha256_bytes(raw), "zip_bytes": len(raw),
                           "job_manifest_sha256": file_identity(directory / "manifest.json")["sha256"]})
        write_json(output / "sources.json", sources)
    require(len({row["artifact_id"] for row in selected}) == len(selected), "duplicate artifact source IDs")
    return sources


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("collect", "frozen"))
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--stage", choices=("pilot", "run", "main"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.operation == "frozen":
        retrieve_frozen(args.expected_sha, args.output)
    else:
        require(args.stage is not None, "collection requires an explicit stage")
        collect_jobs(args.expected_sha, args.output, stage=args.stage)
    print("Authenticated exact source IDs, ZIP hashes and every internal member")


if __name__ == "__main__":
    main()

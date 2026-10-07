"""Authenticate exact current-run case artifacts before registry aggregation."""

import argparse
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from .data_audit import PROTOCOL_ID, REPO_ROOT, require, sha256_bytes, write_json
from .frozen_inputs import load_frozen_inputs, verify_file_manifest


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, newurl):
        return None


def api_get(url):
    require(urllib.parse.urlsplit(url).hostname == "api.github.com", "unexpected authenticated API host")
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                                                 "Accept": "application/vnd.github+json",
                                                 "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def download_zip(metadata, repository):
    """Never forward the GitHub token to the signed object-store redirect."""
    api_url = f"https://api.github.com/repos/{repository}/actions/artifacts/{metadata['id']}/zip"
    request = urllib.request.Request(api_url, headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        require(error.code in (301, 302, 303, 307, 308), "artifact download did not provide a valid redirect")
        location = error.headers["Location"]
        require(urllib.parse.urlsplit(location).scheme == "https", "artifact redirect must use HTTPS")
        with urllib.request.urlopen(urllib.request.Request(location), timeout=60) as response:
            raw = response.read()
    digest = metadata.get("digest", "")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is not None, "artifact metadata has no exact ZIP digest")
    require(sha256_bytes(raw) == digest[7:] and len(raw) == metadata["size_in_bytes"], "downloaded ZIP digest or length differs from the selected artifact")
    return raw


def extract_case(raw, destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    seen = set()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in info.filename and ":" not in info.filename, "unsafe artifact member")
            require(info.filename not in seen and ((info.external_attr >> 16) & 0o170000) != 0o120000, "duplicate artifact member or symlink")
            seen.add(info.filename)
            target = destination / path
            require(target.resolve().is_relative_to(destination), "artifact path escapes its case directory")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
    verify_file_manifest(destination)


def collect_cases(expected_sha, output):
    instances, provenance = load_frozen_inputs(expected_sha)
    output = Path(output).resolve()
    require(not output.is_relative_to(REPO_ROOT), "transport outputs must be outside the checkout")
    require(not output.exists() or not any(output.iterdir()), "existing transport evidence is not overwritten")
    output.mkdir(parents=True, exist_ok=True)
    repository = os.environ["GITHUB_REPOSITORY"]
    require(repository == "ChepaMaksym/GA-article-test", "unexpected study repository")
    run_id, attempt = provenance["run_id"], provenance["run_attempt"]
    metadata = []
    page = 1
    while True:
        data = api_get(f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100&page={page}")
        metadata.extend(data["artifacts"])
        if len(data["artifacts"]) < 100:
            break
        page += 1
    write_json(output / "artifact-api-metadata.json", {"artifacts": metadata, "source_run_id": run_id, "run_attempt": attempt})
    selected = []
    for instance in instances:
        name = f"knapsack-feasibility-case-{instance.instance_id}-{run_id}-{attempt}"
        matching = [row for row in metadata if row["name"] == name]
        require(len(matching) == 1, "missing or duplicate exact-attempt case artifact")
        row = matching[0]
        require(row["expired"] is False and row["workflow_run"]["id"] == run_id and row["workflow_run"]["head_sha"] == expected_sha, "case artifact belongs to a different run or implementation")
        require(row["workflow_run"]["head_branch"] == "research/masters-ga-knapsack-parameters", "case artifact belongs to a different branch")
        selected.append({"id": row["id"], "name": name, "digest": row["digest"], "instance_id": instance.instance_id,
                         "source_run_id": run_id, "run_attempt": attempt, "implementation_sha": expected_sha})
    require(len({row["id"] for row in selected}) == 30, "selected source IDs are not unique and complete")
    write_json(output / "sources.json", {"schema_version": "knapsack-feasibility-case-sources-v1", "protocol_id": PROTOCOL_ID,
                                         "implementation_sha": expected_sha, "source_run_id": run_id, "run_attempt": attempt, "artifacts": selected})
    ledger = {"schema_version": "knapsack-feasibility-case-transport-v1", "protocol_id": PROTOCOL_ID,
              "implementation_sha": expected_sha, "source_run_id": run_id, "run_attempt": attempt, "downloads": []}
    write_json(output / "transport-ledger.json", ledger)
    for source in selected:
        row = next(item for item in metadata if item["id"] == source["id"])
        raw = download_zip(row, repository)
        identity = {"artifact_id": source["id"], "name": source["name"], "sha256": sha256_bytes(raw), "bytes": len(raw),
                    "source_run_id": run_id, "run_attempt": attempt, "instance_id": source["instance_id"], "implementation_sha": expected_sha}
        ledger["downloads"].append(identity)
        write_json(output / "transport-ledger.json", ledger)
        extract_case(raw, output / "cases" / source["instance_id"])
    return ledger


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    collect_cases(args.expected_sha, args.output)
    print("Authenticated all 30 exact-ID case artifacts before aggregation")


if __name__ == "__main__":
    main()

"""Authenticate retained artifacts and retain only nine required raw references.

This I/O command never invokes GA search, exact solvers or statistical analysis.
The six larger ZIPs are authenticated in memory, then only selected members are
retained; their complete ZIP digests and immutable workflow origins are recorded.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import stat
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from zipfile import ZipFile

from .common import HERE, guard_stage
from studies.knapsack_parameters.population_validation_100.common import read_json, require, require_ci, sha, write_json

REPOSITORY = "ChepaMaksym/GA-article-test"
REGISTRY = HERE / "data/retained_registry.json"
OUTPUT_LIMIT = 256 * 1024**2


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def validate_registry(registry):
    """Reject drift of artifact identities before network access."""
    require(registry.get("schema") == "mutation-grid-100-retained-registry-v1"
            and registry.get("source_manifest_sha256") == "2ed212337b22706decd7123ab1111cbc4c62fbe357e29478c1c868acf3c2f44f",
            "Retained source seal differs")
    entries = registry.get("archives")
    require(type(entries) is list and len(entries) == 9 and len({r["id"] for r in entries}) == 9,
            "Nine distinct pinned retained archives are required")
    roles = [row.get("role") for row in entries]
    require(roles.count("results") == roles.count("technical_inputs") == roles.count("tuning_inputs") == 1
            and roles.count("compatibility") == 6, "Retained archive roles differ")
    expected = {(f"n00100-{kind}-s050", mu, 150001)
                for kind in ("UC", "WC", "SC") for mu in (10, 15, 20)}
    selected = [(r["task"], r["mu"], r["seed"]) for row in entries for r in row.get("selected", [])]
    require(len(selected) == len(set(selected)) == 9 and set(selected) == expected,
            "Nine compatibility reference identities differ")
    for row in entries:
        require(type(row["id"]) is int and row["id"] > 0 and type(row["bytes"]) is int
                and 0 < row["bytes"] <= 64 * 1024**2
                and len(row["sha256"]) == 64 and set(row["sha256"]) <= set("0123456789abcdef"),
                "Invalid pinned archive descriptor")
    return entries


def download(entry, token):
    """Check GitHub metadata and authenticate ZIP bytes before opening members."""
    require_ci()
    require(bool(token), "Repository artifact token is absent")
    url = f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{entry['id']}"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "User-Agent": "knapsack-mutation-grid100-retained"}
    with urlopen(Request(url, headers=headers), timeout=45) as response:
        metadata = json.load(response)
    require(metadata.get("name") == entry["name"] and metadata.get("size_in_bytes") == entry["bytes"]
            and metadata.get("digest") == "sha256:" + entry["sha256"] and metadata.get("expired") is False
            and metadata.get("workflow_run", {}).get("id") == entry["original_run_id"]
            and metadata["workflow_run"].get("head_sha") == entry["original_commit"],
            "Retained artifact metadata or workflow origin differs")
    try:
        with build_opener(NoRedirect).open(Request(url + "/zip", headers=headers), timeout=45) as response:
            raw = response.read(entry["bytes"] + 1)
    except HTTPError as error:
        require(error.code in (301, 302, 303, 307, 308), "Artifact archive request failed")
        target = error.headers.get("Location", "")
        require(urlparse(target).scheme == "https", "Unsafe archive redirect")
        # The repository token is deliberately not sent to the signed host.
        with urlopen(Request(target), timeout=90) as response:
            raw = response.read(entry["bytes"] + 1)
    require(len(raw) == entry["bytes"] and sha256(raw).hexdigest() == entry["sha256"],
            "Retained ZIP size or digest differs")
    return raw


def validate_members(archive):
    """Inspect every archive name, including members not selected for extraction."""
    seen = set()
    for member in archive.infolist():
        name = member.filename
        require(name and name not in seen and "\\" not in name and ":" not in name
                and not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
                and not stat.S_ISLNK(member.external_attr >> 16), "Unsafe or duplicate ZIP member")
        require(member.file_size >= 0 and member.file_size <= 128 * 1024**2,
                "Unreasonable retained member size")
        seen.add(name)
    return seen


def retain_selected(raw, entry, out):
    """Copy only the authenticated journal and its source receipt for each case."""
    receipts = []
    with ZipFile(BytesIO(raw)) as archive:
        names = validate_members(archive)
        for case in entry["selected"]:
            prefix = f"{case['task']}/seed-{case['seed']}/mu{case['mu']}-pc100"
            for filename in ("journal.json.gz", "record.json", "verification.json"):
                source = prefix + "/" + filename
                require(source in names, "A required retained reference member is absent")
                content = archive.read(source)
                target = out / "references" / case["task"] / f"mu{case['mu']}" / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(content)
                receipts.append({"task": case["task"], "mu": case["mu"], "seed": case["seed"],
                                 "path": target.relative_to(out).as_posix(), "bytes": len(content),
                                 "sha256": sha256(content).hexdigest(), "source_member": source,
                                 "artifact_id": entry["id"], "artifact_sha256": entry["sha256"],
                                 "original_run_id": entry["original_run_id"],
                                 "original_commit": entry["original_commit"]})
    return receipts


def retrieve(out, *, token=None):
    require_ci()
    entries = validate_registry(read_json(REGISTRY))
    destination = Path(out)
    require(not destination.exists(), "Preserve prior or partial retained evidence")
    destination.mkdir(parents=True)
    receipts = []
    for entry in entries:
        raw = download(entry, token or os.environ.get("GH_TOKEN", ""))
        if entry["role"] == "compatibility":
            receipts.extend(retain_selected(raw, entry, destination))
        else:
            with ZipFile(BytesIO(raw)) as archive:
                validate_members(archive)
            path = destination / (entry["role"] + ".zip")
            with path.open("xb") as stream:
                stream.write(raw)
            receipts.append({"role": entry["role"], "path": path.name, "bytes": len(raw),
                             "sha256": entry["sha256"], "artifact_id": entry["id"],
                             "original_run_id": entry["original_run_id"], "original_commit": entry["original_commit"]})
        del raw
        require(sum(p.stat().st_size for p in destination.rglob("*") if p.is_file()) <= OUTPUT_LIMIT,
                "Retained selected evidence exceeds its output cap")
    write_json(destination / "origin.json", {"schema": "mutation-grid-100-retained-origin-v1",
               "status": "AUTHENTICATED_SELECTED_EVIDENCE", "registry_sha256": sha(REGISTRY),
               "archives": entries, "files": receipts})
    print("Authenticated retained inputs, 1440 compact records and nine raw references; no search executed.", flush=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    guard_stage("technical")
    retrieve(args.out)


if __name__ == "__main__":
    main()

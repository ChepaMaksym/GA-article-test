"""Retrieve 21 pinned, small artifacts from the retained 900-run study."""
import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from .common import HERE, guard_checks, guard_stage, read_json, require, sha
from studies.knapsack_parameters.population_size_study.io_utils import safe_child


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def download(entry, token, origin):
    url = "https://api.github.com/repos/ChepaMaksym/GA-article-test/actions/artifacts/" + str(entry["id"])
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "User-Agent": "knapsack-retained-tuning"}
    with urlopen(Request(url, headers=headers), timeout=45) as response:
        metadata = json.load(response)
    require(metadata["name"] == entry["name"] and metadata["size_in_bytes"] == entry["bytes"]
            and metadata["digest"] == "sha256:" + entry["sha256"] and not metadata["expired"]
            and metadata["workflow_run"]["id"] == origin["original_run_id"]
            and metadata["workflow_run"]["head_sha"] == origin["original_commit"],
            "Retained artifact origin differs")
    try:
        with build_opener(NoRedirect).open(Request(url + "/zip", headers=headers), timeout=45) as response:
            raw = response.read(entry["bytes"] + 1)
    except HTTPError as error:
        require(error.code in (301, 302, 303, 307, 308), "Artifact archive request failed")
        target = error.headers.get("Location", "")
        require(urlparse(target).scheme == "https", "Unsafe archive redirect")
        with urlopen(Request(target), timeout=60) as response:
            raw = response.read(entry["bytes"] + 1)
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    guard_checks() if args.audit_only else guard_stage("tuning")
    token = os.environ.get("GH_TOKEN", "")
    require(bool(token), "Repository artifact token is absent")
    registry_path = HERE / "data/retained_tuning_registry.json"
    origin = read_json(registry_path)
    require(origin.get("schema") == "initial-grid-100-retained-tuning-v1"
            and origin.get("original_run_id") == 42813784277 and len(origin.get("archives", [])) == 21,
            "Retained archive registry differs")
    require(not args.out.exists(), "Preserve prior downloaded evidence")
    args.out.mkdir(parents=True)
    for entry in origin["archives"]:
        raw = download(entry, token, origin)
        target = safe_child(args.out, entry["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        require(target.stat().st_size == entry["bytes"] and sha(target) == entry["sha256"],
                "Retained artifact bytes differ")
    (args.out / "origin.json").write_bytes(registry_path.read_bytes())
    print("Authenticated 21 retained artifacts; no GA search executed.", flush=True)


if __name__ == "__main__":
    main()

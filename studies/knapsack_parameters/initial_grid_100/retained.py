"""Authenticate a retained technical artifact without starting any search."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from .common import HERE, guard_stage, read_json, require, write_json
from studies.knapsack_parameters.population_size_study.io_utils import extract_artifact


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def download(artifact, token):
    base = "https://api.github.com/repos/ChepaMaksym/GA-article-test/actions/artifacts/" + str(artifact["id"])
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "User-Agent": "knapsack-retained-evidence"}
    with urlopen(Request(base, headers=headers), timeout=45) as response:
        metadata = json.load(response)
    require(metadata["name"] == artifact["name"] and metadata["size_in_bytes"] == artifact["bytes"]
            and metadata["digest"] == "sha256:" + artifact["sha256"] and not metadata["expired"]
            and metadata["workflow_run"]["id"] == 42780269269
            and metadata["workflow_run"]["head_sha"] == "c9c631243b287e7aefb58e59a01276ca4def77c7",
            "Retained artifact provenance differs")
    try:
        with build_opener(NoRedirect).open(Request(base + "/zip", headers=headers), timeout=45) as response:
            raw = response.read(artifact["bytes"] + 1)
    except HTTPError as error:
        require(error.code in (301, 302, 303, 307, 308), "Retained archive request was rejected")
        target = error.headers.get("Location", "")
        require(urlparse(target).scheme == "https", "Unsafe archive redirect")
        # Never forward the repository token to the signed archive host.
        with urlopen(Request(target), timeout=60) as response:
            raw = response.read(artifact["bytes"] + 1)
    require(len(raw) == artifact["bytes"] and sha256(raw).hexdigest() == artifact["sha256"],
            "Retained artifact bytes differ")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mu", type=int, choices=(10, 20), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    guard_stage("technical")
    registry = read_json(HERE / "data/compatibility_artifacts.json")
    require(registry["run_id"] == 42780269269, "Compatibility origin differs")
    selected = [row for row in registry["artifacts"] if row["mu"] == args.mu]
    require(len(selected) == 1 and not args.out.exists(), "Retain previous compatibility inputs")
    token = os.environ.get("GH_TOKEN", "")
    require(bool(token), "Repository artifact token is absent")
    raw = download(selected[0], token)
    extract_artifact(raw, args.out, compressed_limit=32 * 1024**2, expanded_limit=64 * 1024**2)
    write_json(args.out / "download_receipt.json", {"status": "RETAINED_ARCHIVE_AUTHENTICATED",
               "artifact": selected[0], "run_id": registry["run_id"], "commit": registry["commit"]})
    print("Retained compatibility inputs authenticated; no search executed.", flush=True)


if __name__ == "__main__":
    main()

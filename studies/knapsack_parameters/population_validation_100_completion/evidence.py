"""Download and authenticate only the original small evidence archives in CI."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from .common import guard_completion
from studies.knapsack_parameters.population_validation_100.common import require, write_json
from studies.knapsack_parameters.population_size_study.io_utils import extract_artifact


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def fetch_json(url, token):
    request = Request(url, headers={"Authorization": "Bearer " + token,
                      "Accept": "application/vnd.github+json", "User-Agent": "knapsack-evidence-audit"})
    with urlopen(request, timeout=45) as response:
        return json.load(response)


def archive_bytes(artifact_id, token, expected_bytes):
    url = f"https://api.github.com/repos/ChepaMaksym/GA-article-test/actions/artifacts/{artifact_id}/zip"
    request = Request(url, headers={"Authorization": "Bearer " + token,
                      "Accept": "application/vnd.github+json", "User-Agent": "knapsack-evidence-audit"})
    try:
        with build_opener(NoRedirect).open(request, timeout=45) as response:
            raw = response.read(expected_bytes + 1)
    except HTTPError as error:
        require(error.code in (301, 302, 303, 307, 308), "Artifact API rejected the archive request")
        target = error.headers.get("Location", "")
        require(urlparse(target).scheme == "https", "Unsafe artifact redirect")
        # The signed file URL receives no GitHub authorization header.
        with urlopen(Request(target), timeout=60) as response:
            raw = response.read(expected_bytes + 1)
    require(len(raw) == expected_bytes, "Archive byte count differs from pinned metadata")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = guard_completion()
    require(not args.out.exists(), "Preserve previously downloaded evidence")
    token = os.environ.get("GH_TOKEN", "")
    require(bool(token), "The repository-scoped artifact token is absent")
    rows = [row for row in protocol["original_artifacts"]
            if row["name"].startswith("population100-main-compact-")
            or row["name"] == "population100-main-prepared-42813784277"]
    require(len(rows) == 31 and sum(row["bytes"] for row in rows) < 8 * 1024**2,
            "Original small-evidence inventory differs")
    args.out.mkdir(parents=True)
    receipts = []
    for row in rows:
        metadata = fetch_json(f"https://api.github.com/repos/ChepaMaksym/GA-article-test/actions/artifacts/{row['id']}", token)
        origin = metadata["workflow_run"]
        require(metadata["name"] == row["name"] and metadata["size_in_bytes"] == row["bytes"]
                and metadata["digest"] == "sha256:" + row["sha256"] and not metadata["expired"]
                and origin["id"] == protocol["original_run_id"]
                and origin["head_sha"] == protocol["original_commit"], "Original artifact provenance differs")
        raw = archive_bytes(row["id"], token, row["bytes"])
        require(sha256(raw).hexdigest() == row["sha256"], "Original artifact SHA-256 differs")
        archive = args.out / "archives" / (row["name"] + ".zip")
        archive.parent.mkdir(exist_ok=True)
        archive.write_bytes(raw)
        destination = (args.out / "prepared" if "-prepared-" in row["name"]
                       else args.out / "compacts" / row["name"])
        extract_artifact(raw, destination, compressed_limit=1024**2, expanded_limit=32 * 1024**2)
        receipts.append({**row, "original_run_id": origin["id"], "original_commit": origin["head_sha"],
                         "archive_sha256_checked": True})
    write_json(args.out / "evidence_receipt.json", {"schema": "population100-completion-download-v1",
               "status": "AUTHENTICATED_31_ORIGINAL_ARCHIVES", "artifacts": receipts})
    print("Authenticated 31 small original archives; no GA executed.", flush=True)


if __name__ == "__main__":
    main()

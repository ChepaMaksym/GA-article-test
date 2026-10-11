"""CI test receipts and digest-checked artifact transport, never a search CLI."""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import stat
import unittest
import urllib.request
import zipfile

from .contract import (REPO_ROOT, REPOSITORY, PROTOCOL_ID, api, authenticate,
                       ci_only, file_identity, require, source_manifest,
                       write_file_manifest, write_json)


def tests(output):
    ci_only()
    identity = authenticate()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.discover(
        str(Path(__file__).parent / "tests"), top_level_dir=str(REPO_ROOT))
    with (output / "unittest.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    receipt = {"protocol_id": PROTOCOL_ID, "tests_passed": result.wasSuccessful(),
               "tests_run": result.testsRun, "failure_count": len(result.failures),
               "error_count": len(result.errors), "skipped_count": len(result.skipped),
               "source_manifest": source_manifest(), "provenance": identity}
    write_json(output / "tests_receipt.json", receipt)
    write_file_manifest(output)
    print("Tests:", result.testsRun, "passed:", result.wasSuccessful())
    if not result.wasSuccessful():
        print((output / "unittest.txt").read_text(encoding="utf-8"))
        raise SystemExit(1)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def download_zip(artifact, output):
    """Credential stays on GitHub API; signed storage download has no bearer."""
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact['id']}/zip",
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                 "User-Agent": "diversity-proof-transport"})
    try:
        response = opener.open(request, timeout=20)
    except urllib.error.HTTPError as exc:
        require(exc.code == 302, "Artifact redirect failed")
        location = exc.headers.get("Location", "")
        exc.close()
    else:
        response.close()
        raise ValueError("Expected signed artifact redirect")
    require(location.startswith("https://"), "Non-HTTPS artifact storage")
    with urllib.request.urlopen(location, timeout=40) as response, Path(output).open("xb") as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)
    identity = file_identity(output)
    require(identity["bytes"] == artifact["size_in_bytes"] and
            artifact["digest"] == "sha256:" + identity["sha256"], "ZIP digest or length mismatch")
    return identity


def extract_zip(archive, target):
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    seen = set()
    with zipfile.ZipFile(archive) as zipped:
        for entry in zipped.infolist():
            member = PurePosixPath(entry.filename)
            require(not member.is_absolute() and ".." not in member.parts and ":" not in entry.filename and
                    "\\" not in entry.filename and entry.filename not in seen, "Unsafe/duplicate ZIP member")
            require(not stat.S_ISLNK(entry.external_attr >> 16), "ZIP symlink forbidden")
            require((target / member).resolve().is_relative_to(target), "ZIP escapes output")
            seen.add(entry.filename)
        zipped.extractall(target)


def download_sources(output):
    from .reporting import source_receipts
    ci_only()
    authenticate()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    receipts = source_receipts()
    for row in receipts["artifacts"]:
        if row["status"] != "AVAILABLE":
            continue
        artifact = api(f"/actions/artifacts/{row['artifact_id']}")
        archive = output / (row["task"] + ".zip")
        identity = download_zip(artifact, archive)
        extract_zip(archive, output / row["task"])
        row["transport_verified"] = True
        row["downloaded_zip_sha256"] = identity["sha256"]
        row["downloaded_zip_bytes"] = identity["bytes"]
    write_json(output / "transport_receipts.json", receipts)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("tests", "download"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    (tests if args.phase == "tests" else download_sources)(args.output)


if __name__ == "__main__":
    main()

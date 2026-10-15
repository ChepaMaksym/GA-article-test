"""Outer identities are separate from the independent semantic journal replay."""
from __future__ import annotations

import io
from pathlib import PurePosixPath
import re
import urllib.error
import urllib.request
import zipfile

from . import contract as c


def validate_metadata(transport, run, artifact, phase):
    c.require(phase in ("tests", "prepare"), "Wrong source phase")
    c.require(transport.get("protocol_id") == c.PROTOCOL, "Wrong source protocol")
    for key in ("run_id", "run_attempt", "artifact_id"):
        c.require(type(transport.get(key)) is int and transport[key] > 0, "Invalid source ID")
    c.require(re.fullmatch("[0-9a-f]{40}", transport.get("implementation_sha", "")) and
              re.fullmatch("[0-9a-f]{64}", transport.get("artifact_zip_sha256", "")), "Invalid source hash")
    c.require(run["id"] == transport["run_id"] and run["run_attempt"] == transport["run_attempt"] and
              run["conclusion"] == "success" and run["status"] == "completed" and
              run["head_sha"] == transport["implementation_sha"] and run["head_branch"] == c.BRANCH and
              run["path"] == c.WORKFLOW and c.phase(run["head_commit"]["message"]) == phase,
              "Source is not the exact successful phase")
    prefix = "tests" if phase == "tests" else "inputs"
    c.require(artifact["id"] == transport["artifact_id"] and not artifact["expired"] and
              artifact["workflow_run"]["id"] == run["id"] and
              artifact["workflow_run"]["head_sha"] == run["head_sha"] and
              artifact["name"] == f"adaptive-mutation-{prefix}-{run['id']}-{run['run_attempt']}" and
              artifact.get("digest") == "sha256:" + transport["artifact_zip_sha256"], "Wrong source artifact")


def validate_archive(raw, expected_sha):
    limit = 16*1024*1024
    c.require(len(raw) <= limit and c.hashlib.sha256(raw).hexdigest() == expected_sha, "Source ZIP checksum mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        names = [v.filename for v in entries]
        c.require(len(names) == len(set(names)) and sum(v.file_size for v in entries) <= limit,
                  "Oversized or repeated archive members")
        for entry in entries:
            name = entry.filename
            path = PurePosixPath(name)
            c.require(not path.is_absolute() and ".." not in path.parts and ":" not in name and
                      "\\" not in name and not entry.is_dir() and
                      ((entry.external_attr >> 16) & 0o170000) != 0o120000, "Unsafe artifact member")
        members = {name: archive.read(name) for name in names}
    manifest = c.json.loads(members["file_manifest.json"])
    c.require(manifest.get("protocol_id") == c.PROTOCOL and manifest.get("excludes_self") is True,
              "Wrong source manifest")
    rows = manifest["files"]
    c.require(len({r["path"] for r in rows}) == len(rows) and
              {r["path"] for r in rows} | {"file_manifest.json"} == set(members), "Incomplete source ZIP")
    for row in rows:
        content = members[row["path"]]
        c.require(len(content) == row["bytes"] and c.hashlib.sha256(content).hexdigest() == row["sha256"],
                  "Wrong internal source checksum")
    return members


def fetch_artifact(transport, phase):
    run = c.api(f"/actions/runs/{transport['run_id']}/attempts/{transport['run_attempt']}")
    artifact = c.api(f"/actions/artifacts/{transport['artifact_id']}")
    validate_metadata(transport, run, artifact, phase)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, message, headers, new_url):
            return None
    request = urllib.request.Request(
        f"https://api.github.com/repos/{c.REPOSITORY}/actions/artifacts/{transport['artifact_id']}/zip",
        headers={"Authorization": "Bearer " + c.os.environ["GITHUB_TOKEN"], "User-Agent": "mutation-provenance"})
    try:
        urllib.request.build_opener(NoRedirect).open(request, timeout=25)
    except urllib.error.HTTPError as exc:
        c.require(exc.code == 302, "Expected signed artifact redirect")
        location = exc.headers["Location"]
    else:
        raise ValueError("Missing signed artifact redirect")
    c.require(location.startswith("https://"), "Unsafe artifact storage protocol")
    # API credentials are not forwarded to storage.
    with urllib.request.urlopen(location, timeout=25) as response:
        raw = response.read(16*1024*1024 + 1)
    c.require(len(raw) == artifact["size_in_bytes"], "Source ZIP size mismatch")
    return validate_archive(raw, transport["artifact_zip_sha256"]), run


def validate_log_identity(log, bank, method):
    import numpy as np
    c.require(method in ("fixed", "adaptive_mutation"), "Unknown method identity")
    channels = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
    expected_rng = {name: np.random.PCG64(np.random.SeedSequence(
        [76001, bank["task_index"], bank["start_index"], channel])).state for channel, name in enumerate(channels)}
    c.require(log["method"] == method and log["budget"] == 5000 and
              log["problem"] == bank["problem"] and log["initial_masks"] == bank["initial_masks"] and
              log["initial_scores"] == bank["initial_scores"] and log["rng_initial"] == expected_rng,
              "Run identity or registered seed/start mismatch")


def validate_complete_results(results):
    expected = {(task, start, method) for task in ("UC-s000", "WC-s001", "SC-s005", "SC-s000")
                for start in ("cloned", "bank") for method in ("fixed", "adaptive_mutation")}
    identities = [(r["task"], r["start"], r["method"]) for r in results]
    c.require(len(results) == len(set(identities)) == 16 and set(identities) == expected, "Incomplete or duplicate pilot identities")
    c.require(all(r["seed"] == 76001 and r["summary"]["new_calls"] == 5000 and
                  r["verification"]["verification_status"] == "VERIFIED" for r in results), "Incomplete run or replay")
    for row in results:
        if row["task"] == "SC-s000" and row["start"] == "cloned":
            c.require(row["first_improvement_call"] is None and
                      row["summary"]["best_profit"] == row["initial_record"], "Global negative control failed")

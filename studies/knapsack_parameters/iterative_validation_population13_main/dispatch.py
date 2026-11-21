"""Plan bounded main-study work and retain authenticated resume evidence.

This module performs no search, exact solving, bank generation, or journal
replay. Every entry point requires the current explicit CI authorization.
GitHub errors never mean an empty result set or permission to replace a run.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from zipfile import ZipFile

from .common import (REF, REPOSITORY, WORKFLOW, descriptor, guard_main,
                     registered_cases, registered_shards, validate_case_origin)
from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha
from studies.knapsack_parameters.iterative_validation_population13.transport import (
    NoRedirect, download_archive, safe_relative, validate_members,
)


API = "https://api.github.com/repos/" + REPOSITORY
PAYLOADS = {"journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz"}
INPUTS = ("problem", "certificate", "source", "bank")
INDEX_CAP = 1024**2
RAW_CAP = 49 * 1024**2
COLLECT_CAP = 2 * 1024**3


def _write(path, value):
    path = Path(path)
    require(not path.exists(), "Preserve existing dispatch evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    require(len(raw) <= 4 * 1024**2, "Dispatch metadata exceeds its byte cap")
    with path.open("xb") as stream:
        stream.write(raw)


def _token():
    value = os.environ.get("GITHUB_TOKEN", "")
    require(bool(value), "Read-only GitHub artifact token is absent")
    return value


def api_json(path, token):
    """Read fixed-repository metadata without forwarding a credential redirect."""
    require(type(path) is str and re.fullmatch(r"/actions/runs/[0-9]+(?:/(?:artifacts|jobs)\?per_page=100)?", path),
            "Unregistered GitHub metadata endpoint")
    request = Request(API + path, headers={"Authorization": "Bearer " + token,
                      "Accept": "application/vnd.github+json", "User-Agent": "population13-main-dispatch"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            require(response.getcode() == 200 and response.geturl() == API + path,
                    "GitHub metadata response redirected or changed")
            raw = response.read(2 * 1024**2 + 1)
            require(len(raw) <= 2 * 1024**2, "GitHub metadata exceeds its byte bound")
            result = json.loads(raw)
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError("Authenticated GitHub metadata retrieval failed") from None
    require(type(result) is dict, "GitHub metadata must be an object")
    return result


def _run(run_id, origin, token, *, completed):
    metadata = api_json("/actions/runs/" + str(run_id), token)
    require(metadata.get("id") == int(run_id)
            and metadata.get("repository", {}).get("full_name") == REPOSITORY
            and metadata.get("head_repository", {}).get("full_name") == REPOSITORY
            and metadata.get("path") == WORKFLOW
            and metadata.get("event") == "workflow_dispatch"
            and metadata.get("head_branch") == REF.removeprefix("refs/heads/")
            and metadata.get("head_sha") == origin["workflow_commit"]
            and metadata.get("run_attempt") == 1
            and (metadata.get("status") == "completed" if completed
                 else metadata.get("status") in ("in_progress", "completed")),
            "The admitted GitHub run identity differs")
    return metadata


def _artifact_entry(value, kind, shard_id, run_id, commit):
    expected_name = f"population13-main-{kind}-{shard_id}-{run_id}"
    require(type(value) is dict and value.get("name") == expected_name
            and type(value.get("id")) is int and value["id"] > 0
            and value.get("expired") is False
            and type(value.get("size_in_bytes")) is int
            and 0 < value["size_in_bytes"] <= (INDEX_CAP if kind == "index" else RAW_CAP)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", value.get("digest", "")) is not None
            and value.get("workflow_run", {}).get("id") == int(run_id)
            and value["workflow_run"].get("head_sha") == commit,
            "Raw/index artifact has a different immutable origin or byte bound")
    return {"id": value["id"], "name": expected_name, "bytes": value["size_in_bytes"],
            "sha256": value["digest"][7:], "run_id": int(run_id), "commit": commit}


def artifact_pairs(run_id, commit, token):
    """Require exact raw/index pairs; absent metadata is never guessed."""
    response = api_json("/actions/runs/" + str(run_id) + "/artifacts?per_page=100", token)
    rows = response.get("artifacts")
    require(type(rows) is list and response.get("total_count") == len(rows) <= 100
            and len({row.get("id") for row in rows}) == len(rows),
            "Artifact metadata is incomplete, duplicated, or paginated")
    known = {f"population13-main-{kind}-{row['shard_id']}-{run_id}": (kind, row["shard_id"])
             for row in registered_shards() for kind in ("raw", "index")}
    found = {}
    for row in rows:
        name = row.get("name", "")
        if not name.startswith(("population13-main-raw-", "population13-main-index-")):
            continue
        require(name in known and name not in found, "Unknown or duplicated main-study artifact name")
        kind, shard = known[name]
        found[name] = _artifact_entry(row, kind, shard, run_id, commit)
    pairs = {}
    for shard in registered_shards():
        sid = shard["shard_id"]
        raw = found.get(f"population13-main-raw-{sid}-{run_id}")
        index = found.get(f"population13-main-index-{sid}-{run_id}")
        require((raw is None) == (index is None), "A prior raw/index artifact pair is incomplete")
        if raw is not None:
            pairs[sid] = {"raw": raw, "index": index}
    return pairs


def _check_record(record, shard_id, authorization, cases=None):
    fixed = {row["case_id"]: row for row in registered_cases()}
    shard = next(row for row in registered_shards() if row["shard_id"] == shard_id)
    require(type(record) is dict and record.get("case_id") in shard["case_ids"],
            "An index contains a case assigned to another shard")
    require(record.get("schema") == "population13-main-case-v1" and record.get("status") == "VERIFIED"
            and all(type(record.get(key)) is type(value) and record[key] == value
                    for key, value in fixed[record["case_id"]].items()),
            "An index must contain exact verified registered case identities")
    validate_case_origin(record, authorization)
    require(type(record.get("artifact_hashes")) is dict and set(record["artifact_hashes"]) == PAYLOADS
            and all(re.fullmatch(r"[0-9a-f]{64}", value) is not None
                    for value in record["artifact_hashes"].values()),
            "An index has incomplete canonical payload hashes")
    for name in INPUTS:
        value = record.get(name + "_sha256")
        require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
                "An index has an invalid input hash")
        if cases is not None:
            require(value == cases[record["case_id"]][name]["sha256"],
                    "An indexed case differs from the current original input bank or source")
    return record["case_id"]


def _index_records(path, shard_id, authorization, cases):
    records = {}
    with ZipFile(path) as archive:
        members = validate_members(archive)
        require(sum(row.file_size for row in members.values()) <= INDEX_CAP,
                "Index expansion exceeds one MiB")
        for name, member in members.items():
            require(not member.is_dir(), "An index contains an unregistered directory entry")
            if name == "shard.json":
                metadata = json.loads(archive.read(member))
                require(type(metadata) is dict and metadata.get("shard_id") == shard_id,
                        "Index shard metadata differs")
                continue
            parts = safe_relative(name).parts
            require(len(parts) == 2 and parts[1] == "record.json",
                    "An index may contain only case records and shard metadata")
            record = json.loads(archive.read(member))
            case_id = _check_record(record, shard_id, authorization, cases)
            require(case_id == parts[0] and case_id not in records, "Duplicate or aliased index case identity")
            records[case_id] = record
    return records


def _prepared(inputs, authorization):
    """Use byte identities only; do not repeat numerical preparation or replay."""
    root = Path(inputs)
    manifest = read_json(root / "manifest.json")
    require(manifest.get("schema") == "population13-main-inputs-v1"
            and manifest.get("status") == "NINETY_PAIRED_CASES_READY"
            and manifest.get("source_manifest_sha256") == authorization["source_manifest_sha256"]
            and manifest.get("authorization_id") == authorization["authorization_id"]
            and manifest.get("workflow_run_id") == os.environ.get("GITHUB_RUN_ID")
            and manifest.get("workflow_commit") == os.environ.get("GITHUB_SHA"),
            "Dispatch uses a different prepared input origin")
    expected = {row["case_id"]: row for row in registered_cases()}
    rows = manifest.get("cases")
    require(type(rows) is list and len(rows) == 90
            and {row.get("case_id") for row in rows} == set(expected), "Dispatch prepared-case inventory differs")
    for row in rows:
        require(all(type(row.get(k)) is type(v) and row[k] == v for k, v in expected[row["case_id"]].items()),
                "Dispatch prepared task or seed differs")
        for name in INPUTS:
            descriptor(root, row[name])
    return {row["case_id"]: row for row in rows}, sha(root / "manifest.json")


def _current_origin(authorization):
    return {"workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
            "source_manifest_sha256": authorization["source_manifest_sha256"],
            "authorization_id": authorization["authorization_id"]}


def plan(inputs, out, resume_run_id="", authorization_id=None):
    _, authorization = guard_main(authorization_id)
    output = Path(out)
    require(not output.exists(), "Preserve a prior dispatch plan")
    cases, manifest_sha = _prepared(inputs, authorization)
    require(type(resume_run_id) is str and (resume_run_id == "" or re.fullmatch(r"[1-9][0-9]*", resume_run_id)),
            "Resume run identity is malformed")
    admitted = authorization.get("allowed_resume_runs", [])
    require(bool(resume_run_id) == bool(admitted), "Select an explicitly admitted resume run when prior origins exist")
    pairs, indexes = {}, {}
    if resume_run_id:
        matches = [row for row in admitted if row["workflow_run_id"] == resume_run_id]
        require(len(matches) == 1 and resume_run_id != os.environ["GITHUB_RUN_ID"], "Resume origin is not admitted")
        token = _token()
        _run(resume_run_id, matches[0], token, completed=True)
        pairs = artifact_pairs(resume_run_id, matches[0]["workflow_commit"], token)
        with tempfile.TemporaryDirectory(prefix="population13-main-index-") as temporary:
            for shard_id, pair in pairs.items():
                path = Path(temporary) / (shard_id + ".zip")
                download_archive(pair["index"], token, path)
                indexes[shard_id] = _index_records(path, shard_id, authorization, cases)
    completed, active = [], []
    for shard in registered_shards():
        sid = shard["shard_id"]
        prior = pairs.get(sid)
        records = indexes.get(sid, {})
        if set(records) == set(shard["case_ids"]):
            completed.append({"shard_id": sid, "raw": prior["raw"], "index": prior["index"],
                              "case_ids": list(shard["case_ids"])})
        else:
            active.append({"shard_id": sid, "prior_raw": prior["raw"] if prior else None})
    require(len(active) <= authorization["maximum_shards_this_dispatch"],
            "Missing shards exceed the explicitly admitted dispatch allowance")
    matrix = {"include": active or [{"shard_id": "000", "prior_raw": None}]}
    result = {"schema": "population13-main-dispatch-v1", **_current_origin(authorization),
              "inputs_manifest_sha256": manifest_sha, "registered_case_count": 90,
              "resume_run_id": resume_run_id, "completed_prior_shards": completed,
              "active_shards": active, "prior_index_records": indexes, "matrix": matrix,
              "has_cases": bool(active), "ga_runs_started_by_planning": 0}
    output.mkdir(parents=True, exist_ok=False)
    _write(output / "dispatch.json", result)
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("matrix=" + json.dumps(matrix, separators=(",", ":")) + "\n")
            stream.write("has_cases=" + ("true" if active else "false") + "\n")
    return result


def _dispatch(path, authorization):
    value = read_json(path)
    require(value.get("schema") == "population13-main-dispatch-v1"
            and all(value.get(key) == expected for key, expected in _current_origin(authorization).items())
            and re.fullmatch(r"[0-9a-f]{64}", value.get("inputs_manifest_sha256", "")) is not None,
            "Dispatch plan provenance differs")
    active, completed = value.get("active_shards"), value.get("completed_prior_shards")
    require(type(active) is list and type(completed) is list
            and len(active) <= authorization["maximum_shards_this_dispatch"]
            and len(active) + len(completed) == 30
            and {row.get("shard_id") for row in active + completed}
            == {row["shard_id"] for row in registered_shards()}, "Dispatch shard partition differs")
    return value


def _extract(path, output, budget):
    """Expand canonical regular files within one caller-owned evidence root."""
    root = Path(output).resolve()
    with ZipFile(path) as archive:
        entries = validate_members(archive)
        size = sum(row.file_size for row in entries.values())
        require(budget["used"] + size <= budget["limit"], "Collected raw evidence exceeds its expansion cap")
        for name, entry in entries.items():
            if entry.is_dir():
                continue
            target = root.joinpath(*safe_relative(name).parts)
            require(target.resolve().is_relative_to(root) and not target.exists(), "Raw extraction aliases existing evidence")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as incoming, target.open("xb") as outgoing:
                while True:
                    block = incoming.read(1024**2)
                    if not block:
                        break
                    outgoing.write(block)
        budget["used"] += size


def restore(dispatch_plan, shard_id, out, authorization_id=None):
    _, authorization = guard_main(authorization_id)
    value = _dispatch(dispatch_plan, authorization)
    rows = [row for row in value["active_shards"] if row["shard_id"] == shard_id]
    require(len(rows) == 1, "Restore requires one active registered shard")
    output = Path(out)
    require(not output.exists(), "Preserve earlier restored evidence")
    output.mkdir(parents=True, exist_ok=False)
    prior = rows[0]["prior_raw"]
    if prior is not None:
        require(prior["bytes"] <= RAW_CAP, "Restored raw artifact exceeds its byte cap")
        with tempfile.TemporaryDirectory(prefix="population13-main-restore-") as temporary:
            path = Path(temporary) / "raw.zip"
            download_archive(prior, _token(), path)
            _extract(path, output, {"used": 0, "limit": RAW_CAP})
    return {"shard_id": shard_id, "restored": prior is not None, "ga_runs": 0}


def make_index(rawroot, out, shard_id, authorization_id=None):
    _, authorization = guard_main(authorization_id)
    require(shard_id in {row["shard_id"] for row in registered_shards()}, "Unknown shard index")
    root, output = Path(rawroot), Path(out)
    require(root.is_dir() and not root.is_symlink() and not output.exists(), "Invalid index input/output")
    records = {}
    for path in sorted(root.rglob("record.json")):
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
                "Unsafe case index receipt")
        record = read_json(path)
        failure = path.parent / "failure.json"
        if failure.exists():
            require(failure.is_file() and not failure.is_symlink()
                    and failure.resolve().is_relative_to(root.resolve()), "Unsafe failed case receipt")
            failed = read_json(failure)
            require(failed.get("status") == "FAILED_OR_INTERRUPTED"
                    and failed.get("case_id") == record.get("case_id"), "Failed case identity differs")
            continue
        case_id = _check_record(record, shard_id, authorization)
        require(case_id not in records and path.parent.name == case_id
                and {p.name for p in path.parent.iterdir()} == PAYLOADS | {"record.json"},
                "Duplicate or incomplete canonical case cannot enter an index")
        for name, digest in record["artifact_hashes"].items():
            payload = path.parent / name
            require(payload.is_file() and not payload.is_symlink() and sha(payload) == digest,
                    "Indexed canonical payload hash differs")
        records[case_id] = path
    output.mkdir(parents=True, exist_ok=False)
    for case_id, path in records.items():
        target = output / case_id / "record.json"
        target.parent.mkdir()
        target.write_bytes(path.read_bytes())
    shard = root / "shard_receipt.json"
    if shard.is_file():
        require(not shard.is_symlink() and read_json(shard).get("shard_id") == shard_id,
                "Shard index metadata differs")
        (output / "shard.json").write_bytes(shard.read_bytes())
    else:
        _write(output / "shard.json", {"schema": "population13-main-index-status-v1",
               "shard_id": shard_id, "status": "SHARD_RECEIPT_MISSING", "verified_case_ids": sorted(records)})
    require(sum(p.stat().st_size for p in output.rglob("*") if p.is_file()) <= INDEX_CAP,
            "Shard metadata index exceeds one MiB")
    return {"shard_id": shard_id, "verified_cases": len(records), "ga_runs": 0}


def collect(dispatch_plan, out, authorization_id=None):
    _, authorization = guard_main(authorization_id)
    value = _dispatch(dispatch_plan, authorization)
    output = Path(out)
    require(not output.exists(), "Preserve earlier collected evidence")
    token = _token()
    current_id = os.environ["GITHUB_RUN_ID"]
    _run(current_id, _current_origin(authorization), token, completed=False)
    # The current index step may itself fail. Raw evidence is still retained
    # and analysis decides completeness; prior resume pairs are stricter.
    response = api_json("/actions/runs/" + current_id + "/artifacts?per_page=100", token)
    items = response.get("artifacts")
    require(type(items) is list and response.get("total_count") == len(items) <= 100
            and len({row.get("name") for row in items}) == len(items), "Current artifact inventory differs")
    by_name = {row["name"]: row for row in items}
    selected = []
    for row in value["active_shards"]:
        sid = row["shard_id"]
        name = f"population13-main-raw-{sid}-{current_id}"
        require(name in by_name, "A current raw artifact is absent; preserve incomplete status")
        selected.append(_artifact_entry(by_name[name], "raw", sid, current_id, os.environ["GITHUB_SHA"]))
    selected.extend(row["raw"] for row in value["completed_prior_shards"])
    require(len(selected) == 30 and len({row["id"] for row in selected}) == 30,
            "Collected raw shard identities overlap or are incomplete")
    output.mkdir(parents=True, exist_ok=False)
    budget = {"used": 0, "limit": COLLECT_CAP}
    receipts = []
    with tempfile.TemporaryDirectory(prefix="population13-main-collect-") as temporary:
        for entry in selected:
            path = Path(temporary) / (str(entry["id"]) + ".zip")
            download_archive(entry, token, path)
            _extract(path, output / entry["name"], budget)
            receipts.append(dict(entry))
            path.unlink()
    _write(output / "collection_receipt.json", {"schema": "population13-main-collection-v1",
           **_current_origin(authorization), "artifacts": receipts, "expanded_bytes": budget["used"],
           "source_archives_uploaded": False, "ga_runs": 0})
    return {"collected_shards": len(receipts), "expanded_bytes": budget["used"], "ga_runs": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan"); p.add_argument("--inputs", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path); p.add_argument("--resume-run-id", default="")
    p = sub.add_parser("restore"); p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--shard-id", required=True); p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("index"); p.add_argument("--raw", required=True, type=Path)
    p.add_argument("--shard-id", required=True); p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("collect"); p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    for p in sub.choices.values():
        p.add_argument("--authorization-id", required=True)
    a = parser.parse_args()
    if a.command == "plan":
        result = plan(a.inputs, a.out, a.resume_run_id, a.authorization_id)
    elif a.command == "restore":
        result = restore(a.plan, a.shard_id, a.out, a.authorization_id)
    elif a.command == "index":
        result = make_index(a.raw, a.out, a.shard_id, a.authorization_id)
    else:
        result = collect(a.plan, a.out, a.authorization_id)
    print(json.dumps({key: result[key] for key in result if key in (
        "has_cases", "verified_cases", "restored", "collected_shards", "expanded_bytes", "ga_runs")}))


if __name__ == "__main__":
    main()

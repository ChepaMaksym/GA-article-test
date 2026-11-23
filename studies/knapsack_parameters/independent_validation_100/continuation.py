"""Plan missing work, authenticate retained cases and collect compact CI artifacts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from math import ceil
import os
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from time import sleep
from zipfile import ZipFile

from studies.knapsack_parameters.iterative_validation_population13.transport import download_archive, validate_members
from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha
from .common import guard
from .history import api, list_all
from .runner import _checked_cases, SHARD_BYTES, SHARD_SIZE, SCHEMA


MIB = 1024**2
SHARDS = 200
COMPACT_CAP = 4*MIB
OVERHEAD_CAP = 256*MIB
WORKFLOW = ".github/workflows/independent-validation-100.yml"
BRANCH = "research/independent-validation-100"
PLAN_SCHEMA = "independent-validation100-continuation-v1"


def current():
    return int(os.environ["GITHUB_RUN_ID"]), os.environ["GITHUB_SHA"]


def outputs(**values):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        for key, value in values.items():
            print(f"{key}={value}", file=stream)


def jobs_and_resources(run_id):
    jobs = list_all(api, f"/actions/runs/{run_id}/jobs", "jobs")
    minutes = 0
    for job in jobs:
        require(job["run_id"] == run_id and job["status"] == "completed", "Unfinished or mixed charged job")
        if job["conclusion"] != "skipped":
            seconds = (datetime.fromisoformat(job["completed_at"]) -
                       datetime.fromisoformat(job["started_at"])).total_seconds()
            require(seconds >= 0, "Negative billed time")
            minutes += ceil(seconds / 60)
    return jobs, minutes


def artifacts(run_id, commit):
    rows = list_all(api, f"/actions/runs/{run_id}/artifacts", "artifacts")
    pairs = {}
    for item in rows:
        name = item["name"]
        require(type(item["size_in_bytes"]) is int and item["size_in_bytes"] >= 0, "Invalid retained size")
        if not name.startswith(("iv100-compact-", "iv100-raw-")):
            continue
        match = re.fullmatch(r"iv100-(compact|raw)-(0|[1-9][0-9]{0,2})-" + str(run_id), name)
        require(match is not None, "Unregistered shard artifact name")
        kind, index = match[1], int(match[2])
        require(index < SHARDS and kind not in pairs.setdefault(index, {})
                and item["expired"] is False and item["workflow_run"]["id"] == run_id
                and item["workflow_run"]["head_sha"] == commit
                and re.fullmatch(r"sha256:[0-9a-f]{64}", item["digest"])
                and 0 < item["size_in_bytes"] <= (COMPACT_CAP if kind == "compact" else SHARD_BYTES),
                "Duplicate, expired, oversized or mixed shard evidence")
        pairs[index][kind] = {"id": item["id"], "bytes": item["size_in_bytes"], "sha256": item["digest"][7:],
                              "name": name, "run_id": run_id, "commit": commit}
    for pair in pairs.values():
        require(set(pair) == {"raw", "compact"}, "Missing raw or compact shard archive")
    return pairs, sum(r["size_in_bytes"] for r in rows)


def unpack(entry, target, limit):
    require(not target.exists(), "Preserve retained evidence directory")
    with TemporaryDirectory() as temporary:
        archive = Path(temporary) / "artifact.zip"
        for attempt in range(3):
            try:
                download_archive(entry, os.environ["GITHUB_TOKEN"], archive)
                break
            except RuntimeError:
                if attempt == 2:
                    raise
                archive.unlink(missing_ok=True)
                sleep(2**attempt)
        with ZipFile(archive) as zipped:
            members = validate_members(zipped)
            require(sum(info.file_size for info in members.values()) <= limit, "Expanded artifact exceeds limit")
            target.mkdir(parents=True)
            for name, info in members.items():
                if info.is_dir():
                    continue
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream, zipped.open(info) as source:
                    shutil.copyfileobj(source, stream)


def checked_compact(directory, ids, shard, binding, origin, admitted_runs):
    receipt_file = directory / "shard.json"
    if receipt_file.is_file():
        receipt = read_json(receipt_file)
        require(receipt["schema"] == "independent-validation100-shard-v1"
                and receipt["shard_id"] == f"{shard:03d}" and receipt["requested"] == ids
                and receipt["workflow_run_id"] == str(origin["run_id"])
                and receipt["workflow_commit"] == origin["commit"]
                and all(receipt[k] == v for k, v in binding.items()), "Shard, origin or input manifest differs")
        good = receipt["new"] + receipt["reused"]
        failures = receipt["failures"]
        all_ids = good + failures
        require(len(all_ids) == len(set(all_ids)) == len(ids) and set(all_ids) == set(ids)
                and receipt["status"] == ("INCOMPLETE" if failures else "VERIFIED"),
                "Inconsistent completion partition")
        fresh = receipt["new"]
        files = {"shard.json"}
    else:
        # A cancelled runner may already have written replay-verified rows but
        # not yet have emitted the final shard-level receipt. Preserve these rows.
        good = [p.stem for p in (directory/"records").glob("*.json")]
        failures = [p.stem for p in (directory/"failures").glob("*.json")]
        require((good or failures) and set(good + failures).issubset(ids) and set(good).isdisjoint(failures),
                "Partial shard contains unregistered or conflicting cases")
        fresh = []
        files = set()
    files.update(f"records/{i}.json" for i in good)
    files.update(f"failures/{i}.json" for i in failures)
    require(files == {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()},
            "Unexpected, missing or duplicate compact outputs")
    checksums = {}
    for case_id in good:
        path = directory / "records" / (case_id + ".json")
        row = read_json(path)
        require(row["status"] == "VERIFIED" and row["schema"] == SCHEMA and row["case_id"] == case_id
                and all(row[k] == v for k, v in binding.items()) and row["workflow_commit"] == origin["commit"]
                and row["workflow_run_id"] in {str(i) for i in admitted_runs}, "Unverified or foreign saved case")
        if case_id in fresh:
            require(row["workflow_run_id"] == str(origin["run_id"]), "New case reports a different producer")
        checksums[case_id] = sha(path)
    for case_id in failures:
        row = read_json(directory / "failures" / (case_id + ".json"))
        require(row["status"] == "FAILED_OR_INTERRUPTED" and row["case_id"] == case_id
                and row["workflow_run_id"] == str(origin["run_id"]), "Wrong failure evidence")
    return checksums


def case_jobs_missing_evidence(jobs, pairs):
    for job in jobs:
        match = re.fullmatch(r"cases \(([0-9]+)\)", job["name"])
        if not match or job["conclusion"] == "skipped" or int(match[1]) in pairs:
            continue
        # A lost running worker could have finished a verified case before the upload.
        steps = job.get("steps") or []
        executions = [s for s in steps if "execute" in s["name"].lower() or "run and verify" in s["name"].lower()]
        require(job["conclusion"] in ("cancelled", "failure", "timed_out")
                and executions and all(s.get("conclusion") == "skipped" for s in executions),
                "Missing shard evidence after a possibly executed search; audit its logs")


def bound(auth, benchmark, prior_minutes, prior_bytes, active, missing):
    require(benchmark["status"] == "FOUR_OLD_CASES_VERIFIED" and benchmark["holdout_search_runs"] == 0
            and benchmark["forecast"]["physical_main_runs"] == 1200, "A measured old-control forecast is required")
    estimate = benchmark["forecast"]
    require(0 <= missing <= SHARD_SIZE*active <= 1200 and (active == 0 or missing >= active),
            "Invalid number of outstanding cases")
    minutes = ceil(estimate["slowest_case_seconds"]*missing*1.5/60) + active + 30
    sizes = ceil(estimate["largest_case_bytes"]*active*SHARD_SIZE*1.4) + OVERHEAD_CAP
    hard_minutes = 15 + 7*active + 25 + 2
    # Two zip containers per shard have small central directory overhead beyond the raw file cap.
    hard_bytes = active*(SHARD_BYTES+128*1024) + OVERHEAD_CAP
    require(auth["runner_minutes"] == 1600 and auth["artifact_bytes"] == 20*1024**3
            and prior_minutes + max(minutes, hard_minutes) <= auth["runner_minutes"]
            and prior_bytes + max(sizes, hard_bytes) <= auth["artifact_bytes"],
            "Measured or worst-case remaining work exceeds the registered resource ceiling")
    return {"previous_runner_minutes": prior_minutes, "previous_artifact_bytes": prior_bytes,
            "forecast_runner_minutes": minutes, "forecast_artifact_bytes": sizes,
            "worst_runner_minutes": hard_minutes, "worst_additional_artifact_bytes": hard_bytes}


def plan(inputs, benchmark, out, resume_id):
    _, auth = guard("benchmark")
    rid, commit = current()
    registered = _checked_cases(read_json(inputs / "schedule.json"))
    ordered = [r["case_id"] for r in registered]
    ids = [ordered[offset:offset+SHARD_SIZE] for offset in range(0, 1200, SHARD_SIZE)]
    binding = {"source_manifest_sha256": auth["source_manifest_sha256"], "authorization_id": auth["authorization_id"],
               "inputs_manifest_sha256": sha(inputs / "manifest.json")}
    prior = sorted(auth["prior_run_ids"])
    require(len(prior) == len(set(prior)) and all(type(i) is int and 0 < i < rid for i in prior),
            "Invalid registered previous runs")
    need_ack = set()
    best, hashes = {}, {}
    previous_minutes = previous_bytes = 0
    for previous in prior:
        run = api(f"/actions/runs/{previous}")
        require(run["status"] == "completed" and run["conclusion"] != "success" and run["run_attempt"] == 1
                and run["event"] == "workflow_dispatch" and run["head_branch"] == BRANCH and run["path"] == WORKFLOW,
                "Prior failed workflow scope differs")
        pairs, size = artifacts(previous, run["head_sha"])
        jobs, minutes = jobs_and_resources(previous)
        case_jobs_missing_evidence(jobs, pairs)
        previous_minutes += minutes
        previous_bytes += size
        if not pairs:
            continue
        require(run["head_sha"] == commit, "Saved comparative cases require identical source commit")
        need_ack.add(previous)
        def inspect(shard):
            with TemporaryDirectory() as tmp:
                path = Path(tmp) / "compact"
                unpack(pairs[shard]["compact"], path, COMPACT_CAP)
                return shard, checked_compact(path, ids[shard], shard, binding, pairs[shard]["compact"], prior)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for shard, records in pool.map(inspect, pairs):
                require(all(records.get(k)==v for k,v in hashes.get(shard, {}).items()),
                        "A subsequent partial archive lost or changed an independently verified case")
                best[shard], hashes[shard] = pairs[shard], records
    require((not need_ack and (not resume_id or int(resume_id) in prior)) or
            (need_ack and str(max(need_ack)) == resume_id), "Resume input must identify the latest retained case run")
    active = [i for i in range(SHARDS) if len(hashes.get(i, {})) != SHARD_SIZE]
    missing = sum(SHARD_SIZE - len(hashes.get(i, {})) for i in active)
    measured = read_json(benchmark)
    require(measured["workflow_run_id"] == str(rid) and measured["workflow_commit"] == commit
            and measured["source_manifest_sha256"] == binding["source_manifest_sha256"]
            and measured["authorization_id"] == binding["authorization_id"], "Measured forecast provenance differs")
    ledger = bound(auth, measured, previous_minutes, previous_bytes, len(active), missing)
    data = {"schema":PLAN_SCHEMA, "run_id":rid, "commit":commit, "binding":binding, "prior":prior,
            "registered":ids, "retained":best, "active":active, "missing":missing, "resources":ledger}
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    outputs(matrix=json.dumps({"shard":active or [0]},separators=(",", ":")),has_cases=str(bool(active)).lower())
    print(json.dumps({"active_shards":len(active), "missing":missing, "resources":ledger}))


def read_plan(path):
    _, auth = guard("main")
    data = read_json(path)
    rid, commit = current()
    require(data["schema"] == PLAN_SCHEMA and (data["run_id"],data["commit"]) == (rid,commit)
            and data["prior"] == sorted(auth["prior_run_ids"])
            and data["binding"]["source_manifest_sha256"] == auth["source_manifest_sha256"]
            and data["binding"]["authorization_id"] == auth["authorization_id"]
            and len(data["registered"]) == SHARDS, "Foreign dispatch plan")
    return data


def restore(path, shard, out):
    data = read_plan(path)
    require(shard in data["active"] and not out.exists(), "Unregistered active shard or occupied output")
    old = data["retained"].get(str(shard))
    if old is None:
        outputs(run_id="", commit="")
        return
    unpack(old["raw"], out/"raw", SHARD_BYTES)
    unpack(old["compact"], out/"compact", COMPACT_CAP)
    checked_compact(out/"compact", data["registered"][shard], shard, data["binding"], old["compact"], data["prior"])
    outputs(run_id=old["raw"]["run_id"], commit=old["raw"]["commit"])


def collect(path, out):
    data = read_plan(path)
    rid, commit = current()
    require(not out.exists(), "Preserve existing compact dataset")
    latest, _ = artifacts(rid, commit)
    require(set(latest) == set(data["active"]), "Current run has missing or unregistered shard evidence")
    sources = {**{int(k):v for k,v in data["retained"].items()}, **latest}
    require(set(sources) == set(range(SHARDS)), "Incomplete set of shard sources")
    out.mkdir(parents=True)
    def receive(shard):
        target = out/f"{shard:03d}"
        entry = sources[shard]["compact"]
        unpack(entry, target, COMPACT_CAP)
        good = checked_compact(target, data["registered"][shard], shard, data["binding"], entry, [rid,*data["prior"]])
        require(len(good) == SHARD_SIZE, "Source shard is incomplete")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(receive, range(SHARDS)))
    print("Collected all 1,200 replay-verified compact cases.")


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    first = modes.add_parser("plan")
    first.add_argument("--inputs", required=True, type=Path)
    first.add_argument("--benchmark", required=True, type=Path)
    first.add_argument("--resume-run-id", default="")
    first.add_argument("--out", required=True, type=Path)
    for mode in ("restore","collect"):
        sub = modes.add_parser(mode)
        sub.add_argument("--plan", required=True, type=Path)
        sub.add_argument("--out", required=True, type=Path)
        if mode=="restore":
            sub.add_argument("--shard", type=int, required=True)
    args = parser.parse_args()
    if args.mode=="plan":
        plan(args.inputs,args.benchmark,args.out,args.resume_run_id)
    elif args.mode=="restore":
        restore(args.plan,args.shard,args.out)
    else:
        collect(args.plan,args.out)

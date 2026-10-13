"""CI-only test receipts, bounded artifact ingestion and post-run accounting."""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import stat
import unittest
import urllib.request
import zipfile

from .contract import (REPO_ROOT, REPOSITORY, PROTOCOL_ID, api, authenticate,
    canonical_bytes, ci_only, file_identity, matrix_jobs, require, runner_usage,
    source_manifest, validate_tests_receipt, verify_file_manifest, write_file_manifest, write_json)
from .contract import nonsearch_budget_preflight, read_json, STUDY_ROOT


def tests(output):
    identity = authenticate()
    budget_receipt = nonsearch_budget_preflight("tests")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    for relative in ("studies/diversity_crossover/implementation/tests",
                     "studies/diversity_crossover/main_study/tests"):
        suite.addTests(loader.discover(str(REPO_ROOT / relative), top_level_dir=str(REPO_ROOT)))
    with (output / "unittest.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    receipt = {"protocol_id": PROTOCOL_ID, "tests_passed": result.wasSuccessful(),
               "tests_run": result.testsRun, "failure_count": len(result.failures),
               "error_count": len(result.errors), "skipped_count": len(result.skipped),
               "source_manifest": source_manifest(), "provenance": identity}
    write_json(output / "tests_receipt.json", receipt)
    write_json(output / "budget-preflight.json", budget_receipt)
    write_file_manifest(output)
    print("Main tests:", result.testsRun, "passed:", result.wasSuccessful())
    if not result.wasSuccessful():
        print((output / "unittest.txt").read_text(encoding="utf-8"))
        raise SystemExit(1)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def download_zip(artifact, output):
    """Keep bearer credentials on the GitHub API, not on storage redirects."""
    opener = urllib.request.build_opener(_NoRedirect())
    req = urllib.request.Request(f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact['id']}/zip",
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"], "User-Agent": "diversity-main-transport"})
    try:
        response = opener.open(req, timeout=30)
    except urllib.error.HTTPError as exc:
        require(exc.code == 302, "Artifact redirect failed")
        location = exc.headers.get("Location", "")
        exc.close()
    else:
        response.close()
        raise ValueError("Expected signed artifact redirect")
    require(location.startswith("https://"), "Non-HTTPS artifact storage")
    with urllib.request.urlopen(location, timeout=60) as response, Path(output).open("xb") as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)
    identity = file_identity(output)
    require(identity["bytes"] == artifact["size_in_bytes"] and
            artifact.get("digest") == "sha256:" + identity["sha256"], "Artifact ZIP digest mismatch")
    return identity


def extract_zip(archive, target, max_uncompressed=64 * 1024 * 1024):
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    seen = set()
    with zipfile.ZipFile(archive) as zipped:
        require(sum(e.file_size for e in zipped.infolist()) <= max_uncompressed, "Expanded archive exceeds bound")
        for entry in zipped.infolist():
            member = PurePosixPath(entry.filename)
            require(not member.is_absolute() and ".." not in member.parts and ":" not in entry.filename and
                    "\\" not in entry.filename and entry.filename not in seen, "Unsafe or duplicate ZIP member")
            require(not stat.S_ISLNK(entry.external_attr >> 16), "ZIP symlink forbidden")
            require((target / member).resolve().is_relative_to(target), "ZIP escapes destination")
            seen.add(entry.filename)
        zipped.extractall(target)


def _pages(path, field):
    rows, page = [], 1
    while True:
        separator = "&" if "?" in path else "?"
        batch = api(path + separator + f"per_page=100&page={page}")[field]
        rows.extend(batch)
        if len(batch) < 100:
            return rows
        page += 1


def aggregate(output):
    """Never infer completeness from a single artifact or skip failed source jobs."""
    from .analysis import analyze
    from .reporting import report
    identity = authenticate()
    validate_tests_receipt()
    budget_receipt = nonsearch_budget_preflight("aggregate")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    run_id = int(os.environ["GITHUB_RUN_ID"])
    attempt = int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    sha = os.environ["GITHUB_SHA"]
    if os.environ.get("AGGREGATION_PHASE") == "aggregate":
        from .contract import read_json, STUDY_ROOT
        request = read_json(STUDY_ROOT / "main_aggregation_request.json")
        require(request.get("protocol_id") == PROTOCOL_ID, "Wrong aggregation request")
        run_id, sha = request["source_run_id"], request["source_sha"]
        require(type(run_id) is int and run_id > 0 and isinstance(sha, str) and len(sha) == 40,
                "Missing exact aggregation source run/SHA")
        source_run = api(f"/actions/runs/{run_id}")
        require(source_run["status"] == "completed" and source_run["head_sha"] == sha and
                source_run["head_branch"] == "research/masters-ga-diversity-crossover",
                "Standalone aggregation source run is not frozen/completed")
        require(request["source_manifest_sha256"] == source_manifest()["sha256"], "Aggregation source files changed")
        attempt = source_run["run_attempt"]
    latest_sources = {}
    for source_attempt in range(1, attempt + 1):
        jobs = _pages(f"/actions/runs/{run_id}/attempts/{source_attempt}/jobs", "jobs")
        for job in jobs:
            if job["name"].startswith("main ("):
                latest_sources[job["name"]] = dict(job, evidence_attempt=source_attempt)
    source_jobs = list(latest_sources.values())
    require(len(source_jobs) == 104 and all(j["status"] == "completed" for j in source_jobs),
            "All 104 source jobs must finish before aggregation")
    artifacts = _pages(f"/actions/runs/{run_id}/artifacts", "artifacts")
    by_name = {}
    for artifact in artifacts:
        require(artifact["name"] not in by_name, "Duplicate artifact name")
        by_name[artifact["name"]] = artifact
    rows, traces, receipts, seen = [], [], [], set()
    expected_source = source_manifest()
    verify_file_manifest(STUDY_ROOT / "main_inputs")
    frozen_manifest = read_json(STUDY_ROOT / "main_inputs/banks_manifest.json")
    frozen_manifest_sha = file_identity(STUDY_ROOT / "main_inputs/banks_manifest.json")["sha256"]
    problems = {}
    for bank_row in frozen_manifest["banks"]:
        if bank_row["task"] not in problems:
            problems[bank_row["task"]] = read_json(STUDY_ROOT / "main_inputs" / bank_row["path"])["problem"]
    record_verification_calls = 0
    for spec in matrix_jobs():
        source_job = latest_sources.get(f"main ({spec['id']})")
        require(source_job is not None, "Missing named source job")
        source_attempt = source_job["evidence_attempt"]
        prefix = f"diversity-main-{spec['id']}-{run_id}-{source_attempt}"
        compact = by_name.get(prefix + "-compact")
        full = by_name.get(prefix + "-full")
        receipt = {"job": spec, "source_attempt": source_attempt, "source_job_id": source_job["id"],
                   "source_job_conclusion": source_job["conclusion"], "compact_artifact_id": compact["id"] if compact else None,
                   "full_artifact_id": full["id"] if full else None, "status": "MISSING_ARTIFACT"}
        receipts.append(receipt)
        if not compact or not full:
            continue
        for artifact in (compact, full):
            require(not artifact["expired"] and artifact["workflow_run"]["id"] == run_id and
                    artifact["workflow_run"]["head_sha"] == sha and
                    isinstance(artifact.get("digest"), str) and artifact["digest"].startswith("sha256:"),
                    "Invalid artifact provenance or missing digest")
        require(compact["size_in_bytes"] <= 8 * 1024 * 1024, "Compact ZIP exceeds 8 MiB")
        require(full["size_in_bytes"] <= 512 * 1024 * 1024, "Full ZIP exceeds 512 MiB")
        directory = output / "sources" / spec["id"]
        directory.mkdir(parents=True, exist_ok=True)
        archive = directory / "compact.zip"
        zip_identity = download_zip(compact, archive)
        members = directory / "members"
        extract_zip(archive, members)
        manifest = verify_file_manifest(members)
        receipt.update(status="VERIFIED_TRANSPORT", compact_zip_sha256=zip_identity["sha256"],
                       compact_zip_bytes=zip_identity["bytes"], full_zip_sha256=full["digest"].split(":", 1)[1],
                       full_zip_bytes=full["size_in_bytes"], expires_at=full["expires_at"],
                       internal_manifest=file_identity(members / "file_manifest.json"))
        from .contract import read_json
        require(read_json(members / "source_manifest.json") == expected_source, "Mixed main source files")
        source_identity = read_json(members / "provenance.json")
        require(source_identity["implementation_sha"] == sha and source_identity["run_id"] == run_id and
                source_identity["run_attempt"] == source_attempt, "Mixed main source SHA or run")
        task_results = read_json(members / "task_results.json")
        require(task_results["implementation_sha"] == sha and task_results["protocol_id"] == PROTOCOL_ID,
                "Mixed compact task identity")
        from .inputs import job_specs, diagnostic_specs
        expected_job_key = f"{spec['task']}-block{spec['block']}" if spec["kind"] == "main" else f"diagnostic-block{spec['block']}"
        expected_ids = job_specs(spec["task"], spec["block"]) if spec["kind"] == "main" else diagnostic_specs(spec["block"])
        allowed = {(t, s, m, seed) for t, s, seed, m in expected_ids}
        require(task_results["job_key"] == expected_job_key and task_results["expected_runs"] == len(allowed) and
                task_results["run_id"] == run_id and task_results["run_attempt"] == source_attempt and
                task_results["bank_manifest_sha256"] == frozen_manifest_sha and
                task_results["preparation_sha"] == frozen_manifest["preparation_sha"] and
                task_results["source_fingerprint"] == frozen_manifest["source_fingerprint"], "Mixed compact job/bank binding")
        # The runner owns its schema; all summaries must be explicitly embedded.
        for row in task_results["runs"]:
            key = (row["task"], row["start"], row["method"], row["seed"])
            require(key in allowed and row["protocol_id"] == PROTOCOL_ID and row["implementation_sha"] == sha and row["run_id"] == run_id and
                    row["run_attempt"] == source_attempt and row["job_key"] == expected_job_key and
                    row["bank_manifest_sha256"] == frozen_manifest_sha and
                    row["preparation_sha"] == frozen_manifest["preparation_sha"] and
                    row["source_fingerprint"] == frozen_manifest["source_fingerprint"], "Mixed compact run/bank provenance")
            require(key not in seen, "Duplicate source run")
            seen.add(key)
            if row.get("status") == "COMPLETE":
                from ..implementation.verifier import independent_score
                for record in (row["search"]["initial_record"], row["search"]["record"]):
                    require(canonical_bytes(independent_score(problems[row["task"]], record["mask"])) ==
                            canonical_bytes(record["score"]), "Saved record mask/score mismatch")
                    record_verification_calls += 1
            rows.append(row)
        for entry in manifest["files"]:
            if entry["path"] == "verified_traces.json.gz":
                import gzip, json
                with gzip.open(members / entry["path"], "rt", encoding="utf-8") as stream:
                    source_traces = json.load(stream)
                    require(isinstance(source_traces, list), "Verified traces must be a list")
                    for trace in source_traces:
                        require(isinstance(trace, dict) and set(("task", "start", "method", "seed", "points")) <= set(trace),
                                "Illustrative trace must bind its run identity")
                        traces.append(trace)
    write_json(output / "sources.json", {"protocol_id": PROTOCOL_ID, "implementation_sha": sha,
               "run_id": run_id, "run_attempt": attempt, "source_jobs": source_jobs, "artifacts": receipts})
    write_json(output / "provenance.json", identity)
    write_json(output / "budget-preflight.json", budget_receipt)
    write_json(output / "source_manifest.json", expected_source)
    analysis = analyze(rows)
    analysis["aggregate_record_verification_calls"] = record_verification_calls
    if any(j.get("conclusion") != "success" for j in source_jobs):
        analysis.update(status="INCOMPLETE_MAIN", primary=None,
                        technical_status="INCOMPLETE_SOURCE_JOBS", nominal_primary_superiority_claims=None)
    else:
        analysis["technical_status"] = "ALL_104_SOURCE_JOBS_SUCCESS"
    write_json(output / "report-data.json", {"protocol_id": PROTOCOL_ID,
               "implementation_sha": sha, "run_id": run_id, "run_attempt": attempt,
               "runs": rows, "analysis": analysis})
    report(output, rows, analysis, traces=traces)
    write_file_manifest(output)
    print("Main aggregation:", analysis.get("status"), "rows:", len(rows))
    if analysis.get("status") not in ("COMPLETE", "COMPLETE_MAIN"):
        raise SystemExit(1)


def closure(output):
    authenticate(require_runtime=False)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    usage = runner_usage(include_current=True)
    # The current closure is still running: reserve its registered five-minute cap.
    usage["closure_reserved_minutes"] = 5
    usage["upper_bound_runner_minutes_including_current_closure"] = usage["used_runner_minutes"] + 5
    require(usage["upper_bound_runner_minutes_including_current_closure"] <= 1200, "Runner ceiling exceeded")
    write_json(output / "runner_usage.json", usage)
    write_file_manifest(output)
    print("Main rounded usage before current closure:", usage["used_runner_minutes"])


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("tests", "aggregate", "closure"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    ci_only()
    {"tests": tests, "aggregate": aggregate, "closure": closure}[args.phase](args.output)


if __name__ == "__main__":
    main()

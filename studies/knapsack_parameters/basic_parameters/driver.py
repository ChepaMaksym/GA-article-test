"""Only CI may execute science; no imported module starts an experiment."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from .contract import (ROOT, MODULE, PROTOCOL, authenticate, api, identity, manifest,
    pages, phase, preflight, read_json, require, require_current_gate, source_manifest, verify_manifest, write_json)


def gate(output):
    selected = preflight(output)
    if selected in {"pilot", "main"}:
        # Gate runs before the hash-locked scientific environment is installed.
        registration = read_json(MODULE / "registration.json")
        tasks = registration["pilot_tasks"] if selected == "pilot" else [
            f"{kind}-s{index:03d}" for kind in ("UC", "WC", "SC") for index in range(10)]
    else:
        tasks = ["single"]
    timeout = {"tests": 6, "prepare": 4, "pilot": 8, "audit": 10, "certify": 15, "main": 20}[selected]
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write(f"phase={selected}\nmatrix=" + json.dumps({"task": tasks}) + f"\ntimeout={timeout}\n")
    manifest(output)


def compact_search(full, compact):
    """Keep compact transport separate from the inventory of full journals."""
    compact.mkdir(parents=True, exist_ok=True)
    for name in ("summaries.json", "manifest.json", "progress.json", "example_trajectories.json"):
        if (full / name).exists():
            shutil.copyfile(full / name, compact / name)
    if (full / "file_manifest.json").exists():
        shutil.copyfile(full / "file_manifest.json", compact / "full_file_inventory.json")
    manifest(compact)


def execute(output, compact):
    provenance = authenticate(runtime=True)
    selected = phase(os.environ.get("COMMIT_MESSAGE", ""))
    require(selected == os.environ.get("STUDY_PHASE"), "Phase/commit mismatch")
    require_current_gate(provenance, selected)
    task = os.environ["STUDY_TASK"]
    output.mkdir(parents=True, exist_ok=True)
    require(not output.is_relative_to(ROOT), "Output must be outside checkout")
    try:
        if selected == "tests":
            suite = unittest.defaultTestLoader.discover(str(MODULE / "tests"), top_level_dir=str(ROOT))
            with (output / "tests.txt").open("w", encoding="utf-8") as stream:
                result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            write_json(output / "tests.json", {**provenance, "success": result.wasSuccessful(),
                "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                "skipped": len(result.skipped)})
            require(result.wasSuccessful() and not result.skipped and result.testsRun >= 20, "Tests failed or incomplete")
        elif selected == "prepare":
            from .banks import prepare_banks
            # prepare_banks itself requires an empty directory.
            prepare_banks(ROOT, output, provenance)
        elif selected == "audit":
            from .data import audit
            audit(output, provenance)
        elif selected == "certify":
            from .data import certify
            certify(output, provenance)
        elif selected in {"pilot", "main"}:
            from .execution import run_task
            run_task(ROOT, task, selected, output, provenance)
        else:
            raise ValueError("No adaptive phase is authorized")
    except Exception as error:
        write_json(output / "failure.json", {**provenance, "phase": selected,
            "task": task, "status": "INCOMPLETE", "error": type(error).__name__, "message": str(error)})
        raise
    finally:
        manifest(output)
        compact_search(output, compact)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def download_artifact(descriptor, destination):
    """Do not forward GitHub's bearer token to signed external storage."""
    require(not descriptor["expired"] and descriptor["size_in_bytes"] <= 1024**3, "Artifact missing/oversized")
    request = urllib.request.Request(descriptor["archive_download_url"],
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"], "User-Agent": "basic-parameters-evidence"})
    try:
        urllib.request.build_opener(NoRedirect).open(request, timeout=30)
        raise ValueError("Expected artifact storage redirect")
    except urllib.error.HTTPError as response:
        require(response.code == 302, "Artifact transport rejected")
        location = response.headers["Location"]
    url = urllib.parse.urlsplit(location)
    require(url.scheme == "https" and url.hostname and
            (url.hostname.endswith(".blob.core.windows.net") or url.hostname.endswith(".githubusercontent.com")), "Unknown artifact storage")
    with urllib.request.urlopen(location, timeout=60) as response:
        raw = response.read(1024**3 + 1)
    digest = hashlib.sha256(raw).hexdigest()
    require(len(raw) == descriptor["size_in_bytes"] and descriptor.get("digest") == "sha256:" + digest, "ZIP checksum mismatch")
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = set()
        require(sum(e.file_size for e in archive.infolist()) <= 1024**3, "Expanded compact artifact too large")
        for entry in archive.infolist():
            name = entry.filename
            target = (destination / name).resolve()
            require(name not in names and "\\" not in name and ":" not in name and
                    not name.startswith("/") and target.is_relative_to(destination.resolve()), "Unsafe ZIP member")
            names.add(name)
            if not entry.is_dir():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(entry))
    verify_manifest(destination)
    return {"artifact_id": descriptor["id"], "name": descriptor["name"],
            "zip_bytes": len(raw), "zip_sha256": digest, "expires_at": descriptor["expires_at"]}


def aggregate(output):
    provenance = authenticate(runtime=True)
    selected = phase(os.environ.get("COMMIT_MESSAGE", ""))
    require(selected in {"pilot", "main"} and selected == os.environ["STUDY_PHASE"], "Invalid aggregation")
    require_current_gate(provenance, selected)
    from .core import task_ids, PILOT_TASKS
    tasks = PILOT_TASKS if selected == "pilot" else task_ids()
    run, attempt = provenance["run_id"], provenance["run_attempt"]
    jobs = pages(f"/actions/runs/{run}/attempts/{attempt}/jobs", "jobs")
    sources = [j for j in jobs if j["name"].startswith("phase (")]
    require(len(sources) == len(tasks) and all(j["status"] == "completed" for j in sources), "Source jobs not all completed")
    all_success = all(j["conclusion"] == "success" for j in sources)
    artifacts = pages(f"/actions/runs/{run}/artifacts", "artifacts")
    output.mkdir(parents=True, exist_ok=True)
    rows, receipts, jobsummaries = [], [], []
    collection = {**provenance, "status": "COLLECTING", "source_jobs_success": all_success,
        "source_jobs": [{k: j[k] for k in ("id", "name", "status", "conclusion")} for j in sources],
        "expected_runs": 27 if selected == "pilot" else 37500, "observed_runs": 0, "artifacts": receipts,
        "available_source_artifacts": [{k: a[k] for k in ("id", "name", "size_in_bytes", "digest", "expires_at")}
            for a in artifacts if a["name"].startswith((f"basic-full-{selected}-", f"basic-compact-{selected}-"))]}
    write_json(output / "collection.json", collection)
    for task in tasks:
        name = f"basic-compact-{selected}-{task}-{run}-{attempt}"
        matches = [a for a in artifacts if a["name"] == name]
        require(len(matches) == 1, "Missing/duplicate compact artifact")
        directory = output / "source_compact" / task
        receipts.append(download_artifact(matches[0], directory))
        current = read_json(directory / "summaries.json")
        require(current and all(r["implementation_sha"] == provenance["implementation_sha"] and
                r["source_manifest_sha256"] == provenance["source_manifest"]["sha256"] and
                r["phase"] == selected and r["instance_id"] == task for r in current), "Mixed SHA/task/phase")
        rows.extend(current)
        jobsummaries.append(read_json(directory / "manifest.json"))
        collection["observed_runs"] = len(rows)
        write_json(output / "collection.json", collection)
    expected = 27 if selected == "pilot" else 37500
    write_json(output / "collection.json", {**provenance, "source_jobs_success": all_success,
        "expected_runs": expected, "observed_runs": len(rows), "artifacts": receipts,
        "full_artifacts": [{k: a[k] for k in ("id", "name", "size_in_bytes", "digest", "expires_at")}
            for a in artifacts if a["name"].startswith(f"basic-full-{selected}-")]})
    write_json(output / "all_summaries.json", rows)
    require(all_success and len(rows) == expected, "Incomplete source series retained, analysis blocked")
    expected_per_job = 9 if selected == "pilot" else 1250
    require(all(j["status"] == "COMPLETE" and j["completed_runs"] == j["expected_runs"] == expected_per_job and
                j["independent_mismatches"] == 0 and
                j["implementation_sha"] == provenance["implementation_sha"] and
                j["source_manifest_sha256"] == provenance["source_manifest"]["sha256"] and
                j["provenance"] == provenance for j in jobsummaries), "Task manifests incomplete or mixed")
    if selected == "pilot":
        from .core import PILOT_SEED, pilot_grid
        configs = {c.configuration_id: c for c in pilot_grid()}
        keys = [(r["instance_id"], r["repeat_seed"], r["configuration_id"]) for r in rows]
        expected_keys = {(task, PILOT_SEED, cid) for task in tasks for cid in configs}
        require(len(keys) == len(set(keys)) and set(keys) == expected_keys, "Pilot rectangle missing/duplicated")
        require(all(r["verified"] and r["logical_requests"] == r["budget"] == 5000 and
            r["physical_evaluations"] == 5000 - configs[r["configuration_id"]].population_size and
            r["p_m"] == configs[r["configuration_id"]].mutation_numerator / 100 and
            r["p_c"] == configs[r["configuration_id"]].crossover_probability and
            r["N"] == configs[r["configuration_id"]].population_size and
            r["verification"]["status"] == "PASS_REPLAY" and
            r["verification"]["rng_and_operator_replay_verified"] is True for r in rows), "Pilot replay/count mismatch")
        elapsed = max(j["elapsed_seconds"] for j in jobsummaries)
        payload = sum(j["output_bytes"] for j in jobsummaries)
        # Worst observed corner-job cost; 25% margin plus installation/artifacts.
        per_main_seconds = elapsed / 9 * 1250 * 1.25 + 90
        projected_minutes = 30 * math.ceil(per_main_seconds / 60) + 30
        projected_bytes = math.ceil(payload / 27 * 37500 * 1.25)
        projected_job_bytes = math.ceil(max(j["output_bytes"] for j in jobsummaries) / 9 * 1250 * 1.25)
        receipt = {**provenance, "completed_runs": len(rows), "independent_mismatches": 0,
            "source_manifest_sha256": provenance["source_manifest"]["sha256"],
            "projected_main_job_seconds": per_main_seconds,
            "projected_main_job_bytes": projected_job_bytes,
            "projected_total_minutes": projected_minutes, "projected_journal_bytes": projected_bytes,
            "technical_only": True, "pilot_seeds_not_used_for_tuning": True}
        write_json(output / "pilot_receipt.json", receipt)
        require(per_main_seconds <= 1200 and projected_minutes <= 900 and projected_bytes <= 40 * 1024**3 and
                projected_job_bytes <= 1024**3,
                "STOP_RESOURCE: pilot projection does not fit registered limits")
    else:
        from .analysis import aggregate as analyze, write_report
        from .data import load_old
        instances = {i.instance_id: i for i in load_old()}
        registry = read_json(ROOT / "studies/knapsack_parameters/evidence/run-37637475385/registry.json")
        require(identity(ROOT / "studies/knapsack_parameters/evidence/run-37637475385/registry.json")["sha256"] ==
                "7e9b8fc893889426e2d3b57610e3a91c09263fcdff488cf15a2b84efe1bdc70f", "Exact registry changed")
        # The driver obtains optima outside the search, from frozen full cases.
        optima = {}
        for task in tasks:
            matching = [r for r in registry["cases"] if r["instance_id"] == task]
            require(len(matching) == 1, "Exact registry task missing or duplicated")
            case = matching[0]["payload"]
            optima[task] = case["exact"]["confirmed_optimum"]
        require(registry["all_30_accounted"] is True, "Incomplete exact registry")
        report = analyze(rows, instances, optima)
        examples = []
        for directory in (output / "source_compact").iterdir():
            p = directory / "example_trajectories.json"
            if p.exists():
                examples.extend(read_json(p))
        report["example_trajectories"] = examples
        report["provenance"] = provenance
        write_report(report, output)
        from .speed_analysis import analyze as speed_analyze, write_report as write_speed_report
        speed_report = speed_analyze(rows, instances, optima)
        speed_report["provenance"] = provenance
        write_speed_report(speed_report, output)
    manifest(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("gate", "execute", "aggregate"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compact", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "gate":
            gate(args.output)
        elif args.command == "execute":
            require(args.compact is not None, "Compact output missing")
            execute(args.output, args.compact)
        else:
            aggregate(args.output)
    except Exception as error:
        write_json(args.output / "failure.json", {"status": "INCOMPLETE", "error": type(error).__name__, "message": str(error)})
        manifest(args.output)
        raise


if __name__ == "__main__":
    main()

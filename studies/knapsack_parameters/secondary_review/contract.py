"""CI-only identity and budget contract for the registered secondary review."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
MODULE_ROOT = Path(__file__).resolve().parent
STUDY_ROOT = ROOT / "studies/knapsack_parameters"
SOURCE_ROOT = STUDY_ROOT / "ga_study/evidence/run-37793424917"
PROTOCOL_ID = "GA-KNAPSACK-SECONDARY-REVIEW-V1"
PROTOCOL_SHA = "a0cd3e881db1aed494aeed8dc6ec12cdf8dd51b4dcad63a237ff20eaf6bc7fd4"
REGISTRATION_SHA = "b02f9fa1640c3774a41f9d609ac98e5511896d91"
CORRECTION_SHA = "1560e0288193ee70166f292fa05e2e39bcaf5164"
CORRECTION_FILE_SHA = "d99b578af902f5e864e6c447e767811dc9e786e24a5562e7db1a32b3661525e4"
SOURCE_SHA = "5fe14fad17368dd94faa86cc0d6138361d3722cf"
SOURCE_RUN = 37793424917
REPOSITORY = "ChepaMaksym/GA-article-test"
BRANCH = "research/masters-ga-knapsack-parameters"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def file_identity(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def safe_member(root, relative):
    root = Path(root).resolve()
    pure = PurePosixPath(str(relative))
    require(str(relative) and not pure.is_absolute() and ".." not in pure.parts
            and "\\" not in str(relative) and ":" not in str(relative), "unsafe evidence path")
    path = root.joinpath(*pure.parts)
    require(path.resolve().is_relative_to(root) and not path.is_symlink(), "evidence escapes its root")
    return path


def write_file_manifest(directory):
    directory = Path(directory)
    files = [{"path": path.relative_to(directory).as_posix(), **file_identity(path)}
             for path in sorted(directory.rglob("*"))
             if path.is_file() and path.relative_to(directory).as_posix() != "file_manifest.json"]
    result = {"schema_version": "ga-knapsack-files-v1", "excludes_self": True, "files": files}
    write_json(directory / "file_manifest.json", result)
    return result


def verify_file_manifest(directory):
    directory = Path(directory).resolve()
    manifest = read_json(directory / "file_manifest.json")
    require(manifest.get("schema_version") == "ga-knapsack-files-v1"
            and manifest.get("excludes_self") is True, "unexpected file manifest")
    seen = set()
    for row in manifest["files"]:
        require(row["path"] not in seen and row["path"] != "file_manifest.json", "duplicate/self inventory entry")
        seen.add(row["path"])
        require(file_identity(safe_member(directory, row["path"])) ==
                {"bytes": row["bytes"], "sha256": row["sha256"]}, "evidence byte length or hash differs")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    require(actual == seen | {"file_manifest.json"}, "missing or unlisted evidence file")
    return manifest


def output_directory(path):
    path = Path(path).resolve()
    require(not path.is_relative_to(ROOT), "scientific output must be outside checkout")
    require(not path.exists() or not any(path.iterdir()), "existing scientific output cannot be overwritten")
    path.mkdir(parents=True, exist_ok=True)
    return path


def implementation_fingerprint():
    rows = [{"path": path.relative_to(ROOT).as_posix(), **file_identity(path)}
            for path in sorted(MODULE_ROOT.glob("*.py"))]
    return sha256_bytes(canonical_bytes(rows))


def authenticate(expected_sha):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "scientific execution is GitHub Actions only")
    require(re.fullmatch(r"[0-9a-f]{40}", str(expected_sha)) is not None, "full implementation SHA required")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(actual == expected_sha == os.environ.get("GITHUB_SHA"), "checkout identity differs")
    require(os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH
            and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "wrong repository/branch")
    require(platform.python_version() == "3.12.14", "CPython patch differs")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, expected_sha], cwd=ROOT, check=True)
    require(file_identity(MODULE_ROOT / "protocol.json")["sha256"] == PROTOCOL_SHA, "secondary protocol changed")
    registered = subprocess.check_output(["git", "show", REGISTRATION_SHA +
              ":studies/knapsack_parameters/secondary_review/protocol.json"], cwd=ROOT)
    require(registered == (MODULE_ROOT / "protocol.json").read_bytes(), "registration bytes differ")
    protocol = read_json(MODULE_ROOT / "protocol.json")
    require(protocol["protocol_id"] == PROTOCOL_ID and protocol["analysis_role"] ==
            "secondary_exploratory_after_outcomes_seen", "analysis scope changed")
    authority = protocol["resource_authority"]
    require(authority["cumulative_runner_minutes"] == 60 and
            all(authority[key] is False for key in ("new_ga_runs", "new_exact_solver_runs",
                "full_paper_replication", "lambda_calibration_or_main")), "unapproved scientific expansion")
    source = protocol["source"]
    correction_path = MODULE_ROOT / "source_identity_correction.json"
    subprocess.run(["git", "merge-base", "--is-ancestor", CORRECTION_SHA, expected_sha], cwd=ROOT, check=True)
    require(file_identity(correction_path)["sha256"] == CORRECTION_FILE_SHA, "registered correction changed")
    correction_bytes = subprocess.check_output(["git", "show", CORRECTION_SHA +
        ":studies/knapsack_parameters/secondary_review/source_identity_correction.json"], cwd=ROOT)
    require(correction_bytes == correction_path.read_bytes(), "correction commit bytes differ")
    correction = read_json(correction_path)
    require(correction["protocol_id"] == PROTOCOL_ID and
            correction["registration_commit_sha"] == REGISTRATION_SHA and
            correction["field"] == "source.file_manifest_sha256" and
            correction["registered_literal"] == source["file_manifest_sha256"] and
            correction["effective_sha256"] == "3583fe289b65853b81869aa50fd7e4ddb1b5b89da353a8a22fe9043402fb424f" and
            all(correction[key] is False for key in ("historical_source_changed",
                "methods_seeds_endpoints_or_thresholds_changed", "new_analysis_executed_before_correction")),
            "source identity correction is not the preregistered clerical correction")
    runtime = protocol["runtime"]
    checks = (
        (SOURCE_ROOT / "file_manifest.json", correction["effective_sha256"]),
        (SOURCE_ROOT / "run-summaries.jsonl.gz", source["summaries_sha256"]),
        (SOURCE_ROOT / "report-data.json", source["report_sha256"]),
        (SOURCE_ROOT / "sources.json", source["sources_sha256"]),
        (STUDY_ROOT / "inputs/data_manifest.json", source["data_manifest_sha256"]),
        (STUDY_ROOT / "evidence/run-37637475385/registry.json", source["registry_sha256"]),
        (STUDY_ROOT / "ga_study/dependencies/requirements.lock", runtime["requirements_sha256"]),
        (STUDY_ROOT / "ga_study/dependencies/environment.lock.json", runtime["environment_sha256"]),
        (STUDY_ROOT / "ga_study/engine.py", runtime["source_engine_sha256"]),
        (STUDY_ROOT / "ga_study/oracle.py", runtime["source_oracle_sha256"]),
        (STUDY_ROOT / "ga_study/statistics.py", runtime["source_statistics_sha256"]),
    )
    for path, digest in checks:
        require(file_identity(path)["sha256"] == digest, "frozen source/runtime changed: " + path.name)
    import numpy
    import matplotlib
    require(numpy.__version__ == "2.2.6" and matplotlib.__version__ == "3.10.3", "locked scientific versions differ")
    verify_file_manifest(SOURCE_ROOT)
    return {"protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA,
            "registration_commit_sha": REGISTRATION_SHA, "implementation_commit_sha": expected_sha,
            "source_identity_correction_commit_sha": CORRECTION_SHA,
            "source_identity_correction_sha256": CORRECTION_FILE_SHA,
            "implementation_fingerprint": implementation_fingerprint(), "repository": REPOSITORY,
            "run_id": int(os.environ["GITHUB_RUN_ID"]), "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
            "source_run_id": SOURCE_RUN, "source_implementation_commit_sha": SOURCE_SHA,
            "source_summaries_sha256": source["summaries_sha256"],
            "source_report_sha256": source["report_sha256"],
            "data_manifest_sha256": source["data_manifest_sha256"], "registry_sha256": source["registry_sha256"],
            "runtime_lock_sha256": runtime["environment_sha256"], "python_version": platform.python_version(),
            "analysis_role": "secondary_exploratory_after_outcomes_seen", "new_search_runs": 0,
            "new_exact_solver_runs": 0, "lambda_correlations": "NOT_AVAILABLE_NOT_COMPUTED"}


def load_context(expected_sha):
    identity = authenticate(expected_sha)
    from ..feasibility.frozen_inputs import verify_input_bundle
    instances, _ = verify_input_bundle()
    registry = read_json(STUDY_ROOT / "evidence/run-37637475385/registry.json")
    cases = {row["instance_id"]: row for row in registry["cases"]}
    require(len(instances) == len(cases) == 30 and registry["admitted_center_count"] == 14,
            "preparation registry incomplete")
    report = read_json(SOURCE_ROOT / "report-data.json")
    require(report["status"] == "COMPLETE_VERIFIED_MAIN" and report["implementation_commit_sha"] == SOURCE_SHA
            and report["runs"] == 35640 and report["logical_requests"] == 178200000
            and report["random_runs"] == 24300 and report["local_runs"] == 11340,
            "historical source is not the full fixed main series")
    return instances, cases, report, identity


def _date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _api(endpoint):
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + endpoint,
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                 "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def budget_preflight(stage):
    require(stage == "analyze", "unregistered secondary execution stage")
    message = os.environ.get("COMMIT_MESSAGE", "")
    require(re.search(r"\[(?:knapsack|knapsack-ga|lambda-paper):", message) is None,
            "mixed scientific execution markers forbidden")
    cutoff = _api("/commits/" + REGISTRATION_SHA)["commit"]["committer"]["date"]
    branch = urllib.parse.quote(BRANCH, safe="")
    runs, page = [], 1
    while True:
        batch = _api(f"/actions/runs?branch={branch}&per_page=100&page={page}")["workflow_runs"]
        runs.extend(run for run in batch if _date(run.get("updated_at", run["created_at"])) >= _date(cutoff))
        if len(batch) < 100:
            break
        page += 1
    current = int(os.environ["GITHUB_RUN_ID"])
    attempt = int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    legacy_paths = {".github/workflows/knapsack-parameters.yml", ".github/workflows/knapsack-feasibility.yml",
                    ".github/workflows/knapsack-lambda-study.yml"}
    used, rows = 0, []
    for run in runs:
        is_current_legacy = run["head_sha"] == os.environ["GITHUB_SHA"] and run.get("path", "").split("@")[0] in legacy_paths
        if run["id"] == current:
            attempts = range(1, attempt)
        elif is_current_legacy:
            attempts = range(1, run["run_attempt"])
        else:
            require(run["status"] == "completed", "prior branch run still active; budget not final")
            attempts = range(1, run["run_attempt"] + 1)
        minutes = 0
        for old_attempt in attempts:
            job_page = 1
            while True:
                batch = _api(f"/actions/runs/{run['id']}/attempts/{old_attempt}/jobs?per_page=100&page={job_page}")["jobs"]
                for job in batch:
                    if job["conclusion"] == "skipped":
                        continue
                    require(job.get("started_at") and job.get("completed_at"), "unknown prior runner duration")
                    if _date(job["started_at"]) < _date(cutoff):
                        continue
                    seconds = max(0, (_date(job["completed_at"]) - _date(job["started_at"])).total_seconds())
                    minutes += max(1, math.ceil(seconds / 60))
                if len(batch) < 100:
                    break
                job_page += 1
        used += minutes
        rows.append({"run_id": run["id"], "run_attempt": run["run_attempt"],
                     "workflow": run["name"], "head_sha": run["head_sha"], "rounded_runner_minutes": minutes})
    # phase 1 + tests 5 + compact 8 + trace 10 + aggregation 5; existing selectors 5+5+1.
    reserve = 40
    require(used + reserve <= 60, f"secondary runner budget exhausted: prior={used}, reserve={reserve}, ceiling=60")
    return {"schema_version": "ga-secondary-budget-v1", "protocol_id": PROTOCOL_ID,
            "registration_cutoff_utc": cutoff, "previous_runs": rows,
            "previous_rounded_runner_minutes": used, "reserved_current_minutes": reserve,
            "cumulative_ceiling_minutes": 60, "no_new_ga_or_exact_solvers": True}

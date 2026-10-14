"""One-job metadata correction for the exact registered completed source run.

Only ci_support.api is temporarily wrapped. The scientific implementation and
contract.api (including every budget request) remain untouched. Entire raw API
responses and the sole exclusion are retained; concrete source jobs never vanish.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from ..main_study import contract

RECOVERY_ID = "GA-DIVERSITY-CROSSOVER-AGGREGATION-RECOVERY-V1"
REGISTRATION_SHA = "f4d2ef6e07b1efc490751c0a12c5413949d1f58d"
SOURCE_RUN = 38396509102
SOURCE_SHA = "c856c9d6811eda51cb4c8b1786033e122249a52d"
SOURCE_DIGEST = "9359220a9ac47f4bf6df816817c01f526cd25ce4a8ebd9100f1502c51c816d3a"
SOURCE_BRANCH = "research/masters-ga-diversity-crossover"
PLACEHOLDER_ID = 115293051290
PHASE_FAILURE_ID = 115292975476
PLACEHOLDER_NAME = "main (" + "$" + "{{ matrix.id }})"
SOURCE_BASE = f"/actions/runs/{SOURCE_RUN}"
JOB_ENDPOINTS = {attempt: f"{SOURCE_BASE}/attempts/{attempt}/jobs" for attempt in (1, 2)}
FIXED_BINDING = {"protocol_id": contract.PROTOCOL_ID, "source_run_id": SOURCE_RUN,
                 "source_sha": SOURCE_SHA, "source_manifest_sha256": SOURCE_DIGEST,
                 "source_attempts": 2, "placeholder_job_id": PLACEHOLDER_ID,
                 "first_failed_phase_job_id": PHASE_FAILURE_ID}


def checksum(value):
    return hashlib.sha256(contract.canonical_bytes(value)).hexdigest()


def registered_names():
    names = {f"main ({spec['id']})" for spec in contract.matrix_jobs()}
    contract.require(len(names) == 104, "Frozen main matrix must contain 104 concrete names")
    return names


def validate_binding(binding, expected_names):
    contract.require(isinstance(binding, dict) and binding == FIXED_BINDING,
                     "Recovery is bound only to the exact registered run/SHA/placeholder")
    contract.require(type(binding["source_run_id"]) is int and type(binding["source_attempts"]) is int
                     and type(binding["placeholder_job_id"]) is int and type(binding["first_failed_phase_job_id"]) is int,
                     "Recovery numeric identities must not be booleans")
    contract.require(isinstance(expected_names, (set, frozenset)) and expected_names == registered_names(),
                     "Recovery concrete-name inventory differs from the frozen 104-job matrix")


def validate_run(run):
    contract.require(isinstance(run, dict) and run.get("id") == SOURCE_RUN and
                     type(run.get("id")) is int and run.get("head_sha") == SOURCE_SHA and
                     run.get("head_branch") == SOURCE_BRANCH and run.get("status") == "completed" and
                     type(run.get("run_attempt")) is int and run["run_attempt"] == 2,
                     "Source run is not the exact completed two-attempt registered run")


def collect_job_pages(raw_api, endpoint):
    """Fetch the complete raw jobs rectangle before any metadata is excluded."""
    contract.require(endpoint in JOB_ENDPOINTS.values(), "Unregistered source jobs endpoint")
    jobs, pages, total, seen = [], [], None, set()
    for page in range(1, 102):
        path = endpoint + f"?per_page=100&page={page}"
        response = raw_api(path)
        contract.require(isinstance(response, dict) and isinstance(response.get("jobs"), list),
                         "Raw jobs API response has an invalid schema")
        declared = response.get("total_count")
        contract.require(type(declared) is int and 0 <= declared <= 10000,
                         "Raw jobs API total_count is invalid or exceeds transport bound")
        contract.require(total is None or declared == total, "Raw jobs pagination total_count changed")
        total = declared
        batch = response["jobs"]
        contract.require(len(batch) <= 100, "Raw API jobs page exceeds per_page")
        for job in batch:
            contract.require(isinstance(job, dict) and type(job.get("id")) is int and job["id"] > 0
                             and isinstance(job.get("name"), str) and job["id"] not in seen,
                             "Raw jobs contain an invalid or duplicate ID")
            seen.add(job["id"])
            jobs.append(deepcopy(job))
        pages.append({"path": path, "response": deepcopy(response), "sha256": checksum(response)})
        contract.require(len(jobs) <= total, "Raw jobs exceed declared total_count")
        if len(jobs) == total:
            break
        contract.require(len(batch) == 100, "Raw jobs pagination ended before total_count")
    else:
        raise ValueError("Raw jobs pagination exceeded the bounded page count")
    contract.require(len(jobs) == total, "Raw jobs pagination is incomplete")
    return {"endpoint": endpoint, "total_count": total, "jobs": jobs, "pages": pages,
            "jobs_sha256": checksum(jobs)}


def validate_source_metadata(binding, source_run, attempts, expected_names):
    """Pure validation for CI fixtures; no API, search, or statistics is called."""
    validate_binding(binding, expected_names)
    validate_run(source_run)
    contract.require(isinstance(attempts, dict) and set(attempts) == {1, 2}, "Both raw source attempts are required")
    for attempt in (1, 2):
        jobs = attempts[attempt]
        contract.require(isinstance(jobs, list), "Attempt jobs must be a complete raw list")
        seen = set()
        for job in jobs:
            contract.require(isinstance(job, dict) and type(job.get("id")) is int and job["id"] > 0
                             and job["id"] not in seen and isinstance(job.get("name"), str),
                             "Attempt metadata has a missing or duplicate job ID")
            seen.add(job["id"])
            contract.require(type(job.get("run_id")) is int and job["run_id"] == SOURCE_RUN,
                             "Job lacks the exact source run identity")
            contract.require(type(job.get("run_attempt")) is int and job["run_attempt"] == attempt,
                             "Job lacks the exact source attempt identity")
            contract.require(job.get("head_sha") == SOURCE_SHA and job.get("head_branch") == SOURCE_BRANCH,
                             "Job source SHA or branch differs from the fixed source")
    first = attempts[1]
    phase = [job for job in first if job["id"] == PHASE_FAILURE_ID]
    contract.require(len(phase) == 1 and phase[0]["name"] == "phase" and
                     phase[0].get("status") == "completed" and phase[0].get("conclusion") == "failure",
                     "Registered attempt-1 infrastructure phase failure is absent")
    placeholders = [job for job in first if job["id"] == PLACEHOLDER_ID]
    contract.require(len(placeholders) == 1, "Exact registered skipped placeholder ID is absent")
    placeholder = placeholders[0]
    contract.require(placeholder["name"] == PLACEHOLDER_NAME and placeholder.get("status") == "completed"
                     and placeholder.get("conclusion") == "skipped" and placeholder.get("steps") == []
                     and all(placeholder.get(field) is None for field in
                             ("runner_id", "runner_name", "runner_group_id", "runner_group_name")),
                     "Registered placeholder is not demonstrably skipped without execution")
    # GitHub's unused placeholder has reversed timestamps. No duration is inferred
    # here: status/steps/runner prove the narrow exclusion; raw timestamps survive.
    for job in first:
        if job["id"] != PLACEHOLDER_ID:
            contract.require(not job["name"].startswith("main ("),
                             "Attempt 1 contains a concrete or unknown main job; do not filter it")
    second = attempts[2]
    source_jobs = [job for job in second if job["name"].startswith("main (")]
    names = [job["name"] for job in source_jobs]
    contract.require(len(source_jobs) == 104 and len(set(names)) == 104 and set(names) == expected_names,
                     "Attempt 2 must contain exactly the 104 unique registered concrete main names")
    contract.require(all(job.get("status") == "completed" and job.get("conclusion") == "success"
                         for job in source_jobs), "A real source job is pending, failed, or skipped")
    contract.require(PLACEHOLDER_ID not in {job["id"] for job in second}, "Placeholder ID reappeared in attempt 2")
    return {"status": "VALIDATED_EXACT_INFRASTRUCTURE_EXCEPTION", "excluded_count": 1,
            "excluded_job": deepcopy(placeholder), "excluded_job_sha256": checksum(placeholder),
            "reason": "registered_unexpanded_completed_skipped_placeholder_without_steps_or_runner",
            "first_failed_phase": deepcopy(phase[0]), "source_run_sha256": checksum(source_run),
            "source_job_count": 104, "source_jobs_sha256": checksum(source_jobs),
            "attempt_raw_job_counts": {str(attempt): len(attempts[attempt]) for attempt in (1, 2)},
            "attempt_raw_jobs_sha256": {str(attempt): checksum(attempts[attempt]) for attempt in (1, 2)}}


def jobs_view(cache, attempt, path):
    """Re-paginate the entire validated view, including corrected total_count."""
    parsed = urlsplit(path)
    contract.require(not parsed.scheme and not parsed.netloc and not parsed.fragment
                     and parsed.path == JOB_ENDPOINTS[attempt], "Wrong normalized jobs endpoint")
    query = parse_qs(parsed.query, keep_blank_values=True)
    contract.require(set(query) <= {"page", "per_page"} and all(len(values) == 1 for values in query.values()),
                     "Unsupported or duplicate jobs pagination parameters")
    page_text, size_text = query.get("page", ["1"])[0], query.get("per_page", ["100"])[0]
    contract.require(re.fullmatch(r"[1-9][0-9]*", page_text) is not None and
                     re.fullmatch(r"[1-9][0-9]*", size_text) is not None,
                     "Jobs pagination requires positive integer page/per_page")
    page, size = int(page_text), int(size_text)
    contract.require(size <= 100 and page <= 10001, "Jobs pagination exceeds transport bounds")
    raw_jobs = cache[attempt]["jobs"]
    jobs = [job for job in raw_jobs if job["id"] != PLACEHOLDER_ID] if attempt == 1 else raw_jobs
    template = deepcopy(cache[attempt]["pages"][0]["response"])
    template["total_count"] = len(jobs)
    template["jobs"] = deepcopy(jobs[(page - 1) * size:page * size])
    return template


@contextmanager
def filtered_source_api(ci_support, *, raw_api, binding, expected_names, audit_dir):
    """Install exactly one audited metadata exception and always restore the API.

    The caller runs the already authenticated frozen aggregator in the existing
    standalone aggregate mode. Unrelated API responses are returned unmodified;
    contract.api itself is never reassigned, including for resource accounting.
    """
    contract.ci_only()
    audit_dir = Path(audit_dir)
    audit_dir.mkdir(parents=True, exist_ok=True)
    raw_path, audit_path = audit_dir / "raw_api_responses.json", audit_dir / "adapter_audit.json"
    contract.require(not raw_path.exists() and not audit_path.exists(), "Recovery API audit must not be overwritten")
    original = getattr(ci_support, "api", None)
    audit = {"schema_version": 1, "recovery_id": RECOVERY_ID, "registration_sha": REGISTRATION_SHA,
             "binding": deepcopy(binding), "status": "PREVALIDATION_PENDING", "excluded_count": 0,
             "source_run": None, "validation": None, "presented_job_pages": [],
             "contract_api_modified": False, "aggregator_api_restored": False,
             "scientific_files_modified": False, "scientific_searches_performed": False}
    adapter_path = Path(__file__).resolve()
    audit["adapter_identity"] = {"path": adapter_path.relative_to(contract.REPO_ROOT).as_posix(),
                                 **contract.file_identity(adapter_path)}
    responses, installed = [], False

    def observed_raw(path):
        response = raw_api(path)
        responses.append({"path": path, "response": deepcopy(response), "sha256": checksum(response)})
        return response

    try:
        validate_binding(binding, expected_names)
        contract.require(original is raw_api and contract.api is raw_api,
                         "Recovery requires the original unwrapped aggregator and budget API")
        contract.require(contract.source_manifest()["sha256"] == SOURCE_DIGEST,
                         "Frozen scientific source manifest differs before recovery")
        run = observed_raw(SOURCE_BASE)
        validate_run(run)
        audit["source_run"] = deepcopy(run)
        cache = {attempt: collect_job_pages(observed_raw, JOB_ENDPOINTS[attempt]) for attempt in (1, 2)}
        validation = validate_source_metadata(binding, run, {attempt: cache[attempt]["jobs"] for attempt in (1, 2)}, expected_names)
        audit.update(status="VALIDATED_BEFORE_AGGREGATION", excluded_count=1, validation=validation)

        def wrapped_api(path):
            parsed = urlsplit(path)
            if parsed.path in JOB_ENDPOINTS.values():
                attempt = next(key for key, value in JOB_ENDPOINTS.items() if parsed.path == value)
                response = jobs_view(cache, attempt, path)
                audit["presented_job_pages"].append({"path": path, "attempt": attempt,
                    "response_sha256": checksum(response), "total_count": response["total_count"],
                    "job_ids": [job["id"] for job in response["jobs"]]})
                return response
            contract.require(not parsed.path.startswith(SOURCE_BASE + "/attempts/"),
                             "An unregistered source-attempt API path was requested")
            response = observed_raw(path)
            if path == SOURCE_BASE:
                validate_run(response)
            return response

        ci_support.api = wrapped_api
        installed = True
        yield deepcopy(validation)
        audit["status"] = "AGGREGATION_RETURNED_SUCCESSFULLY"
    except BaseException as exc:
        audit["status"] = "AGGREGATION_FAILED" if installed else "PREVALIDATION_REJECTED"
        audit["exception"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        if installed:
            ci_support.api = original
        audit["aggregator_api_restored"] = getattr(ci_support, "api", None) is original
        audit["contract_api_modified"] = contract.api is not raw_api
        raw_payload = {"schema_version": 1, "recovery_id": RECOVERY_ID, "responses": responses}
        contract.write_json(raw_path, raw_payload)
        audit["raw_api_file_identity"] = contract.file_identity(raw_path)
        audit["raw_api_responses_sha256"] = checksum(responses)
        contract.write_json(audit_path, audit)

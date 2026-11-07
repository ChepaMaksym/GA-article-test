"""Registered CI commands; calibration and validation require later grants."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter_ns
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import urllib.request

from . import authority as a
from .io_utils import extract_artifact, identity, safe_child, verify_manifest, write_manifest


def _permit(path):
    path = Path(path)
    return a.read_json(path / "permit.json" if path.is_dir() else path)


def _download(url, target, *, limit, headers=None, follow_redirects=True):
    """Bound transfer size and avoid forwarding API credentials to storage."""
    parsed = urllib.parse.urlsplit(url)
    a.require(parsed.scheme == "https" and bool(parsed.hostname), "HTTPS download required")
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers=headers or {"User-Agent": "knapsack-population-study"})

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None

    opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(NoRedirect)
    try:
        response = opener.open(request, timeout=90)
    except urllib.error.HTTPError as error:
        if follow_redirects or error.code not in (301, 302, 303, 307, 308):
            raise
        destination = urllib.parse.urlsplit(error.headers.get("Location", ""))
        host = destination.hostname or ""
        a.require(destination.scheme == "https" and
                  (host.endswith(".blob.core.windows.net") or host.endswith(".actions.githubusercontent.com")),
                  "Unexpected artifact storage host")
        return _download(destination.geturl(), target, limit=limit)
    with response, target.open("xb") as output:
        size = 0
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            size += len(chunk)
            a.require(size <= limit, "Download exceeds its registered byte allowance")
            output.write(chunk)
    return identity(target)


def download_pilot_source(output):
    """Fetch only the nine registered inputs and the pinned attribution file."""
    from .inputs import SOURCE_COMMIT, task_specs
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    inventory = a.read_json(a.MODULE / "source_tree_manifest.json")
    expected = {row["source_path"]: row for row in inventory["files"]}
    expected["README.md"] = {"source_path": "README.md", "git_blob_sha1":
                              "0ab81c1f1b67e0a9696658950ecb02f3e8b443ad", "bytes": 1309}
    paths = ["README.md", *(row["source_path"] for row in task_specs("pilot"))]
    records = []
    for relative in paths:
        url = f"https://raw.githubusercontent.com/likr/kplib/{SOURCE_COMMIT}/{relative}"
        path = safe_child(root, relative)
        descriptor = _download(url, path, limit=1024 * 1024)
        raw = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        a.require(blob == expected[relative]["git_blob_sha1"] and len(raw) == expected[relative]["bytes"],
                  "Pinned KPLIB bytes do not match the registered Git tree")
        records.append({"source_path": relative, "url": url, "git_blob_sha1": blob, **descriptor})
    a.write_json(root / "source_snapshot.json", {"source_commit": SOURCE_COMMIT, "files": records})
    return root


def frozen_artifact(descriptor_name, destination, expected_phase, report_name):
    """Restore byte-identical evidence from a successful, separately frozen phase."""
    descriptor = a.read_json(a.MODULE / descriptor_name)
    a.require(descriptor.get("status") == "VERIFIED" and descriptor.get("phase") == expected_phase,
              "Missing successful frozen prerequisite")
    a.require(descriptor.get("source_manifest_sha256") == a.source_manifest()["sha256"],
              "Frozen prerequisite used different scientific sources")
    artifact_id, run_id, attempt = (descriptor.get(key) for key in ("artifact_id", "run_id", "run_attempt"))
    a.require(all(type(value) is int and value > 0 for value in (artifact_id, run_id, attempt)),
              "Invalid frozen Actions identifiers")
    artifact = a.api(f"/actions/artifacts/{artifact_id}")
    source_run = a.api(f"/actions/runs/{run_id}/attempts/{attempt}")
    a.require(artifact.get("id") == artifact_id and artifact.get("name") == descriptor.get("artifact_name")
              and artifact.get("workflow_run", {}).get("id") == run_id and artifact.get("expired") is False,
              "Frozen artifact is missing, expired or foreign")
    a.require(source_run.get("id") == run_id and source_run.get("run_attempt") == attempt
              and source_run.get("status") == "completed" and source_run.get("conclusion") == "success"
              and source_run.get("head_branch") == a.BRANCH and source_run.get("path") == a.WORKFLOW,
              "Frozen prerequisite workflow was not successful")
    size = artifact.get("size_in_bytes")
    a.require(type(size) is int and 0 <= size <= a.BYTE_RESERVATIONS[expected_phase],
              "Frozen artifact exceeds its phase allowance")
    token = os.environ.get("GITHUB_TOKEN")
    a.require(bool(token), "Read-only Actions token required")
    destination = Path(destination)
    archive_path = destination.with_suffix(".zip")
    downloaded = _download(f"https://api.github.com/repos/{a.REPOSITORY}/actions/artifacts/{artifact_id}/zip",
        archive_path, limit=a.BYTE_RESERVATIONS[expected_phase], follow_redirects=False,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "knapsack-population-study", "X-GitHub-Api-Version": "2022-11-28"})
    a.require(downloaded["bytes"] == size and downloaded["sha256"] == descriptor.get("archive_sha256"),
              "Frozen artifact archive identity changed")
    extract_artifact(archive_path, destination, compressed_limit=a.BYTE_RESERVATIONS[expected_phase])
    a.require(identity(destination / "file_manifest.json")["sha256"] == descriptor.get("file_manifest_sha256"),
              "Frozen manifest identity changed")
    verify_manifest(destination)
    a.require(identity(destination / report_name)["sha256"] == descriptor.get("report_sha256"),
              "Frozen prerequisite report changed")
    report = a.read_json(destination / report_name)
    provenance = report.get("provenance", {})
    a.require(provenance.get("source_manifest", {}).get("sha256") == descriptor["source_manifest_sha256"]
              and provenance.get("implementation_sha") == source_run.get("head_sha")
              and provenance.get("protocol_id") == a.PROTOCOL and provenance.get("run_id") == run_id
              and provenance.get("run_attempt") == attempt, "Frozen report provenance differs")
    expected_status = "VERIFIED_SOFTWARE_TESTS" if expected_phase == "tests" else "PREPARED_CERTIFIED_PILOT_INPUTS"
    a.require(report.get("status") == expected_status, "Frozen prerequisite report is incomplete")
    return destination


def software_tests(output, permit):
    provenance = a.check_permit(permit, "tests")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = perf_counter_ns()
    suite = unittest.defaultTestLoader.discover(str(a.MODULE / "tests"), pattern="test_*.py", top_level_dir=str(a.ROOT))
    # Observe fixture search events without consuming randomness or changing operators.
    import sys
    engines = [module for name, module in list(sys.modules.items()) if name.endswith("ga_core.engine")]
    with ExitStack() as stack:
        spies = [stack.enter_context(patch.object(module, "record_candidate", wraps=module.record_candidate))
                 for module in engines]
        with (output / "test_output.txt").open("w", encoding="utf-8") as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        observed_calls = sum(spy.call_count for spy in spies)
    report = {"schema": "population-size-software-tests-v1", "provenance": provenance,
              "status": ("VERIFIED_SOFTWARE_TESTS" if result.wasSuccessful() and not result.skipped
                         and result.testsRun > 0 and observed_calls > 0 else "FAILED"),
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(result.skipped), "software_fixture_candidate_events_observed": observed_calls,
              "fixture_search_count_is_not_pilot_evaluations": True, "elapsed_ns": perf_counter_ns() - started}
    a.write_json(output / "software_tests.json", report)
    if report["status"] == "VERIFIED_SOFTWARE_TESTS":
        from .figures import mathematical_figures
        mathematical_figures(output / "mathematics")
    write_manifest(output)
    a.require(report["status"] == "VERIFIED_SOFTWARE_TESTS", "Software checks failed; scientific phases blocked")
    return report


def prepare(output, permit):
    a.check_permit(permit, "prepare-pilot")
    from .execution import prepare_pilot
    with tempfile.TemporaryDirectory(prefix="population-size-preparation-") as temporary:
        temporary = Path(temporary)
        frozen_artifact("frozen_tests.json", temporary / "tests", "tests", "software_tests.json")
        source = download_pilot_source(temporary / "source")
        return prepare_pilot(source, output, permit)


def worker(worker_index, output, permit):
    a.check_permit(permit, "pilot")
    from .execution import run_worker
    with tempfile.TemporaryDirectory(prefix="population-size-worker-") as temporary:
        prepared = frozen_artifact("frozen_pilot.json", Path(temporary) / "inputs", "prepare-pilot", "registry.json")
        return run_worker(prepared, worker_index, output, permit)


def aggregate(workers, output, permit):
    """Report technical costs only; boundary probes cannot select a population."""
    provenance = a.check_permit(permit, "pilot")
    from .inputs import task_specs
    from .mathematics import generation_accounting
    paths = sorted(Path(workers).glob("*/worker_receipt.json"))
    a.require(len(paths) == 9, "Pilot is incomplete: exactly nine verified workers required")
    registered_tasks = task_specs("pilot")
    expected = {row["task_id"] for row in registered_tasks}
    frozen_inputs = a.read_json(a.MODULE / "frozen_pilot.json")
    a.require(frozen_inputs.get("status") == "VERIFIED" and frozen_inputs.get("phase") == "prepare-pilot"
              and frozen_inputs.get("source_manifest_sha256") == provenance["source_manifest"]["sha256"],
              "Missing frozen input identity for pilot aggregation")
    receipts, identities, indices, input_identities = [], set(), set(), set()
    for path in paths:
        verify_manifest(path.parent)
        receipt = a.read_json(path)
        a.require(receipt.get("schema") == "population-size-pilot-worker-v1"
                  and receipt.get("status") == "VERIFIED_TECHNICAL_WORKER", "Unverified pilot worker")
        for field in ("protocol_id", "implementation_sha", "source_manifest", "run_id", "run_attempt"):
            a.require(receipt.get("provenance", {}).get(field) == provenance[field], "Mixed pilot provenance")
        index, task_id = receipt.get("worker_index"), receipt.get("task_id")
        a.require(type(index) is int and 0 <= index < 9 and index not in indices
                  and task_id == registered_tasks[index]["task_id"], "Duplicate or incorrect pilot task")
        indices.add(index)
        prepared_registry = receipt.get("prepared_registry")
        a.require(type(prepared_registry) is dict and set(prepared_registry) == {"bytes", "sha256"}
                  and type(prepared_registry["bytes"]) is int and prepared_registry["bytes"] > 0
                  and prepared_registry["sha256"] == frozen_inputs.get("report_sha256"),
                  "Pilot worker used a different frozen input registry")
        input_identities.add(json.dumps(prepared_registry, sort_keys=True))
        records = receipt.get("records")
        a.require(type(records) is list and len(records) == 2, "Incomplete population pair")
        logical_total = new_search_total = 0
        for row in records:
            a.require(type(row) is dict, "Malformed pilot record")
            identity_row = row.get("identity", {})
            mu = identity_row.get("mu")
            key = (task_id, mu)
            a.require(key not in identities and task_id in expected and type(mu) is int and mu in (2, 25000)
                      and identity_row.get("task_id") == task_id and identity_row.get("seed") == 129999
                      and identity_row.get("total_evaluations") == 50000
                      and all(identity_row.get(name) == registered_tasks[index][name]
                              for name in ("n", "class_label", "family"))
                      and row.get("verification_status") == "VERIFIED", "Incorrect pilot run identity")
            identities.add(key)
            file = row["file"]
            a.require(identity(safe_child(path.parent, file["path"])) ==
                      {"bytes": file["bytes"], "sha256": file["sha256"]}, "Pilot log identity changed")
            accounting = row.get("accounting", {})
            a.require(accounting.get("logical_initial_evaluations") == mu
                      and accounting.get("logical_new_evaluations") == 50000 - mu
                      and accounting.get("logical_total_evaluations") == 50000
                      and accounting.get("known_score_validation_evaluations") == mu
                      and accounting.get("independent_score_checks") == 100000 - mu,
                      "Pilot evaluation accounting differs")
            generation_counts = generation_accounting(mu, 50000)
            a.require(row.get("completed_generations") == generation_counts["complete_generations"]
                      and row.get("terminal_partial_offspring") == generation_counts["partial_offspring"],
                      "Pilot complete or terminal generation accounting differs")
            logical_total += accounting["logical_total_evaluations"]
            new_search_total += accounting["logical_new_evaluations"]
        a.require(receipt.get("logical_total_evaluations") == logical_total
                  and receipt.get("new_search_evaluations") == new_search_total
                  and receipt.get("physical_bank_preparation_evaluations") == 0
                  and receipt.get("independent_bank_verification_evaluations") == 25000,
                  "Pilot worker totals or independent bank verification accounting differs")
        receipts.append(receipt)
    a.require(identities == {(task_id, mu) for task_id in expected for mu in (2, 25000)}
              and len(input_identities) == 1, "Pilot coverage or shared input provenance differs")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema": "population-size-technical-summary-v1", "status": "VERIFIED_TECHNICAL_PILOT",
              "provenance": provenance, "runs_verified": len(identities), "logical_total_evaluations": 900000,
              "population_selection_performed": False, "tuning_authorized": False, "main_authorized": False,
              "workers": receipts, "next_step": "Prepare separately approved measured tuning and validation quotes",
              "cost_limit": "Boundary pilot timings do not bound every intermediate population size"}
    a.write_json(output / "pilot_summary.json", report)
    write_manifest(output)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preflight = commands.add_parser("preflight")
    preflight.add_argument("--phase", choices=a.PHASES, required=True)
    preflight.add_argument("--output", type=Path, required=True)
    for name in ("tests", "prepare", "worker", "aggregate"):
        command = commands.add_parser(name)
        command.add_argument("--permit", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if name == "worker":
            command.add_argument("--worker", type=int, choices=range(9), required=True)
        if name == "aggregate":
            command.add_argument("--workers", type=Path, required=True)
    options = parser.parse_args(argv)
    if options.command == "preflight":
        permit = a.preflight(options.phase)
        options.output.mkdir(parents=True, exist_ok=False)
        a.write_json(options.output / "permit.json", permit)
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("phase=" + options.phase + "\n")
            stream.write("worker_matrix=" + json.dumps({"worker": list(a.PILOT_WORKERS)}, separators=(",", ":")) + "\n")
    else:
        permit = _permit(options.permit)
        if options.command == "tests":
            software_tests(options.output, permit)
        elif options.command == "prepare":
            prepare(options.output, permit)
        elif options.command == "worker":
            worker(options.worker, options.output, permit)
        else:
            aggregate(options.workers, options.output, permit)


if __name__ == "__main__":
    main()

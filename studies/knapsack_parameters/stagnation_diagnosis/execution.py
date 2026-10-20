"""Bounded CI phases: software tests, frozen inputs, and three resource probes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import time
import unittest

from . import contract as c

_OLD_CONTEXT_TEST = (
    "studies.knapsack_parameters.feasibility.tests.test_retained_evidence."
    "RetainedEvidenceTests.test_exact_thirty_case_source_ids_member_bytes_and_scientific_proofs"
)


def regression_suite():
    """All scientific fixtures remain; an old branch-only CI entrypoint is inapplicable."""
    discovered = unittest.TestSuite()
    for relative in ("studies/knapsack_parameters/stagnation_diagnosis/tests",
                     "studies/knapsack_parameters/ga_study/tests",
                     "studies/knapsack_parameters/feasibility/tests"):
        discovered.addTests(unittest.defaultTestLoader.discover(str(c.ROOT / relative),
                           pattern="test_*.py", top_level_dir=str(c.ROOT)))
    def flatten(node):
        for child in node:
            if isinstance(child, unittest.TestSuite):
                yield from flatten(child)
            else:
                yield child
    tests = list(flatten(discovered))
    ids = [test.id() for test in tests]
    c.require(len(ids) == len(set(ids)) and _OLD_CONTEXT_TEST in ids, "Unexpected regression inventory")
    selected = [test for test in tests if test.id() != _OLD_CONTEXT_TEST]
    return unittest.TestSuite(selected), {
        "discovered": len(tests), "selected": len(selected), "selected_ids": [test.id() for test in selected],
        "excluded": [{"test_id": _OLD_CONTEXT_TEST,
                      "reason": "Calls the immutable historical branch-only scientific authority. New authority independently authenticates the frozen inputs and original registry; no historical authorization is weakened."}]}


def run_tests(output, permit):
    identity = c.check_permit(permit, "tests")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    suite, selection = regression_suite()
    started = time.perf_counter()
    with (output / "tests.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    passed = result.wasSuccessful() and not result.skipped and result.testsRun == selection["selected"] > 0
    receipt = {**identity, "schema": "knapsack-stagnation-tests-v1", "tests_passed": passed,
               "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "skipped": len(result.skipped), "selection": selection,
               "elapsed_seconds": time.perf_counter() - started,
               "scientific_KPLIB_search_performed": False, "main_search_performed": False,
               "new_exact_solves_performed": False}
    c.write_json(output / "tests_receipt.json", receipt)
    c.write_manifest(output)
    c.verify_manifest(output)
    print((output / "tests.txt").read_text(encoding="utf-8"))
    c.require(passed, "All selected regression checks must pass without skips")
    return receipt


def prepare(output, permit):
    identity = c.check_permit(permit, "prepare")
    with tempfile.TemporaryDirectory(prefix="stagnation-green-prepare-") as directory:
        c.frozen_bundle("tests", Path(directory) / "tests")
    from .runner import prepare_inputs
    receipt = prepare_inputs(Path(output), identity)
    c.require(receipt.get("bank_count") == 903 and receipt.get("status") == "COMPLETE_VERIFIED_INPUTS",
              "Preparation incomplete")
    c.verify_manifest(output)
    return receipt


def worker(output, permit, instance_id):
    identity = c.check_permit(permit, "worker")
    c.require(instance_id in c.PROBE_CASES, "Unregistered probe identity; main search is not authorized")
    with tempfile.TemporaryDirectory(prefix="stagnation-probe-bank-") as directory:
        bundle = Path(directory) / "banks"
        receipt, transport = c.frozen_bundle("banks", bundle)
        identity["bank_manifest_sha256"] = receipt["bank_manifest_sha256"]
        identity["bank_transport"] = transport
        from .runner import execute_case
        row = execute_case(instance_id, 92999, bundle, Path(output), identity)
    c.verify_manifest(output)
    c.require(row.get("verified") is True and row.get("status") == "COMPLETE" and
              row.get("new_evaluations") == 5000 and row.get("logical_requests") == 5030,
              "Probe incomplete; all available raw evidence is retained")
    return row


def aggregate(output, artifacts, permit):
    identity = c.check_permit(permit, "aggregate")
    output, artifacts = Path(output), Path(artifacts)
    output.mkdir(parents=True, exist_ok=True)
    permit_data = c.read_json(Path(permit) / "permit.json")
    identity["bank_manifest_sha256"] = permit_data["checks"]["banks_receipt"]["bank_manifest_sha256"]
    rows, failures, unverified_rows = [], [], []
    aggregate_replay_seconds = 0.0
    if (artifacts / "transport_errors.json").is_file():
        failures.append(c.read_json(artifacts / "transport_errors.json"))
    ledger_path = artifacts / "transport_ledger.json"
    c.require(ledger_path.is_file(), "Missing authenticated transport ledger")
    ledger = c.read_json(ledger_path)
    c.require(all(ledger.get(k) == identity[k] for k in c.PROVENANCE_KEYS), "Mixed transport ledger")
    seen = set()
    for transport in ledger["artifacts"]:
        receipt = None
        try:
            directory = c.safe_path(artifacts, transport["name"])
            c.verify_manifest(directory)
            c.require(c.identity(directory / "file_manifest.json")["sha256"] ==
                      transport["file_manifest_sha256"], "Worker member ledger changed")
            receipt = c.read_json(directory / "worker_summary.json")
            c.require(all(receipt.get(k) == identity[k] for k in c.PROVENANCE_KEYS), "Mixed worker receipt")
            key = (receipt.get("instance_id"), receipt.get("repeat_seed"))
            c.require(key not in seen and key[0] in c.PROBE_CASES and key[1] == 92999,
                      "Duplicate or unregistered probe")
            seen.add(key)
            from .runner import verify_saved_case
            started = time.perf_counter()
            row = verify_saved_case(directory, identity)
            elapsed = time.perf_counter() - started
            aggregate_replay_seconds += elapsed
            row["aggregation_replay_seconds"] = elapsed
            rows.append(row)
        except Exception as error:
            failures.append({"artifact": transport["name"], "error": type(error).__name__, "message": str(error)})
            if receipt is not None:
                unverified_rows.append({"artifact": transport["name"], "retained_worker_receipt": receipt,
                                        "aggregation_status": "UNVERIFIED", "error": str(error)})
    from .analysis import summarize_runs, write_report
    summary = summarize_runs(rows, expected_identities={(case, 92999) for case in c.PROBE_CASES})
    summary["phase"] = "probe"
    summary.update(provenance=identity, transport_ledger=ledger, execution_errors=failures,
                   unverified_saved_workers=unverified_rows, aggregation_replay_seconds=aggregate_replay_seconds,
                   main_search_performed=False, main_search_authorized=False,
                   runner_minutes="PENDING_FINAL_GITHUB_JOB_TIMINGS")
    if failures:
        summary["status"] = "INCOMPLETE"
        summary["completeness"]["status"] = "INCOMPLETE"
    c.write_json(output / "probe_summary.json", summary)
    c.write_json(output / "verified_rows.json", rows)
    write_report(output, rows, summary, phase="probe")
    c.write_manifest(output)
    c.verify_manifest(output)
    c.require(not failures and len(rows) == 3 and all(row.get("verified") is True and row.get("status") == "COMPLETE"
                                                    for row in rows), "Resource probe incomplete; evidence retained")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("gate", "tests", "prepare", "worker", "aggregate", "download"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--phase", choices=tuple(c.RESERVATIONS))
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--instance-id", choices=c.PROBE_CASES)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--kind", choices=("permit", "workers"))
    args = parser.parse_args(argv)
    if args.command == "gate":
        c.require(args.phase is not None, "Gate phase required")
        c.gate(args.output, args.phase)
    elif args.command == "download":
        c.require(args.kind is not None, "Artifact type required")
        try:
            c.download_current(args.output, args.kind)
        except Exception as error:
            if args.kind == "workers":
                c.write_json(args.output / "transport_errors.json", {**c.authenticate(),
                    "error": type(error).__name__, "message": str(error)})
            raise
    else:
        c.require(args.permit is not None, "Central bounded permit required")
        if args.command == "tests":
            run_tests(args.output, args.permit)
        elif args.command == "prepare":
            prepare(args.output, args.permit)
        elif args.command == "worker":
            c.require(args.instance_id is not None, "Registered probe case required")
            worker(args.output, args.permit, args.instance_id)
        else:
            c.require(args.artifacts is not None, "Authenticated workers required")
            aggregate(args.output, args.artifacts, args.permit)


if __name__ == "__main__":
    main()

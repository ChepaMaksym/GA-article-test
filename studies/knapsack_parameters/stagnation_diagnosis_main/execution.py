"""CI-only software checks, one authorized 900-run matrix, and independent readout."""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import tempfile
import time
import unittest

from . import contract as c


def regression_suite():
    from ..stagnation_diagnosis.execution import regression_suite as historical_suite
    suite, selection = historical_suite()
    added = []
    for source in sorted((c.MODULE / "tests").glob("test_*.py")):
        module_name = ".".join(source.relative_to(c.ROOT).with_suffix("").parts)
        module_suite = unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(module_name))
        def flatten(node):
            for child in node:
                if isinstance(child, unittest.TestSuite):
                    yield from flatten(child)
                else:
                    yield child
        tests = list(flatten(module_suite))
        added.extend(test.id() for test in tests)
        suite.addTests(tests)
    selected = selection["selected_ids"] + added
    c.require(len(selected) == len(set(selected)), "Duplicate regression test identity")
    return suite, {**selection, "historical_selected": selection["selected"], "added_main_tests": added,
                   "selected": len(selected), "selected_ids": selected}


def run_tests(output, permit):
    provenance = c.check_permit(permit, "tests")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    suite, selection = regression_suite()
    started = time.monotonic()
    with (output / "tests.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    passed = result.wasSuccessful() and not result.skipped and result.testsRun == selection["selected"] > 0
    receipt = {**provenance, "schema": "knapsack-stagnation-main-tests-v1", "tests_passed": passed,
               "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "skipped": len(result.skipped), "selection": selection, "elapsed_seconds": time.monotonic() - started,
               "scientific_KPLIB_search_performed": False, "main_search_performed": False,
               "new_exact_solves_performed": False}
    c.write_json(output / "tests_receipt.json", receipt)
    c.write_manifest(output)
    c.verify_manifest(output)
    print((output / "tests.txt").read_text(encoding="utf-8"))
    c.require(c.payload_bytes(output) <= c.TESTS_CAP, "Test evidence cap exceeded")
    c.require(passed, "All selected main and historical checks must pass without skips")
    return receipt


def worker(output, permit, instance_id):
    provenance = c.check_permit(permit, "worker")
    provenance["phase"] = "main"
    from .runner import execute_batch
    with tempfile.TemporaryDirectory(prefix="stagnation-main-frozen-") as temporary:
        bundle = Path(temporary) / "banks"
        receipt, transport = c.frozen_banks(bundle)
        provenance["bank_manifest_sha256"] = receipt["bank_manifest_sha256"]
        provenance["bank_transport"] = transport
        result = execute_batch(instance_id, bundle, output, provenance)
    c.verify_manifest(output)
    c.require(c.payload_bytes(output) <= c.WORKER_CAP, "Worker evidence cap exceeded")
    c.require(result["status"] == "COMPLETE" and result["completed_count"] == 30,
              "Main worker incomplete; all available raw records are retained")
    return result


def aggregate(output, artifacts, permit):
    provenance = c.check_permit(permit, "aggregate")
    provenance["phase"] = "main"
    output, artifacts = Path(output), Path(artifacts)
    output.mkdir(parents=True, exist_ok=True)
    rows, errors, retained = [], [], []
    ledger = c.read_json(artifacts / "transport_ledger.json")
    c.require(all(ledger.get(key) == provenance[key] for key in c.PROVENANCE_KEYS), "Mixed transport ledger")
    if (artifacts / "transport_errors.json").is_file():
        errors.append(c.read_json(artifacts / "transport_errors.json"))
    seen_cases = set()
    started = time.monotonic()
    from .runner import verify_saved_batch
    for transport in ledger["artifacts"]:
        batch = None
        try:
            directory = c.safe_path(artifacts, transport["name"])
            c.verify_manifest(directory)
            c.require(c.identity(directory / "file_manifest.json")["sha256"] == transport["file_manifest_sha256"],
                      "Transported worker member ledger changed")
            batch = c.read_json(directory / "worker_summary.json")
            c.require(all(batch.get(key) == provenance[key] for key in c.PROVENANCE_KEYS), "Mixed main batch")
            case = batch.get("instance_id")
            expected_name = f"knapsack-stagnation-main-worker-{case}-{provenance['run_id']}-{provenance['run_attempt']}"
            c.require(transport["name"] == expected_name and case not in seen_cases, "Duplicate or foreign case worker")
            seen_cases.add(case)
            verified = verify_saved_batch(directory, provenance)
            rows.extend(verified)
        except Exception as error:
            errors.append({"artifact": transport["name"], "error": type(error).__name__, "message": str(error)})
            if batch is not None:
                retained.append({"artifact": transport["name"], "retained_worker_receipt": batch,
                                 "status": "UNVERIFIED_NOT_IMPUTED"})
    from .analysis import summarize_runs, write_report
    rows.sort(key=lambda row: ({"UC": 0, "WC": 1, "SC": 2}[row["class_label"]], row["instance_id"], row["repeat_seed"]))
    summary = summarize_runs(rows)
    summary.update(provenance=provenance, transport_ledger=ledger, execution_errors=errors,
                   retained_unverified_workers=retained,
                   aggregate_replay_seconds=time.monotonic() - started,
                   main_search_authorized=True, main_search_performed=True,
                   final_runner_minutes="PENDING_FINAL_GITHUB_JOB_TIMINGS")
    if errors:
        summary["completeness"]["status"] = "INCOMPLETE"
        summary["inference_status"] = "PARTIAL_DESCRIPTIVE_ONLY"
    c.write_json(output / "verified_rows.json", rows)
    compact = [{key: row[key] for key in ("instance_id", "class_label", "family", "repeat_seed", "source_sha256",
                "logical_requests", "new_evaluations", "initial_evaluations", "status", "verified", "checkpoints",
                "accounting", "aggregate_independent_verification", "optimum")} for row in rows]
    c.write_json(output / "run_registry.json", {**provenance, "runs": compact})
    write_report(output, rows, summary)
    c.write_json(output / "main_summary.json", summary)
    c.write_manifest(output)
    c.verify_manifest(output)
    c.require(c.payload_bytes(output) <= c.SUMMARY_CAP and
              c.payload_bytes(artifacts) + c.payload_bytes(output) <= c.BYTE_CEILING,
              "Aggregate evidence payload cap exceeded")
    c.require(not errors and summary["completeness"]["status"] == "COMPLETE" and len(rows) == 900,
              "Main series incomplete; all available evidence and missing identities are retained")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("gate", "tests", "worker", "aggregate", "download"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--phase", choices=tuple(c.RESERVATIONS))
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--instance-id")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--kind", choices=("permit", "workers"))
    args = parser.parse_args(argv)
    if args.command == "gate":
        c.require(args.phase is not None, "Gate phase required")
        c.gate(args.output, args.phase)
    elif args.command == "download":
        c.require(args.kind is not None, "Artifact kind required")
        try:
            c.download_current(args.output, args.kind)
        except Exception as error:
            if args.kind == "workers":
                c.write_json(args.output / "transport_errors.json", {**c.authenticate(),
                    "error": type(error).__name__, "message": str(error)})
            raise
    else:
        c.require(args.permit is not None, "Main-stage permit required")
        if args.command == "tests":
            run_tests(args.output, args.permit)
        elif args.command == "worker":
            c.require(args.instance_id is not None, "Instance required")
            worker(args.output, args.permit, args.instance_id)
        else:
            c.require(args.artifacts is not None, "Transported artifacts required")
            aggregate(args.output, args.artifacts, args.permit)


if __name__ == "__main__":
    main()

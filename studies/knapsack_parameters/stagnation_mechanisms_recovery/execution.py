"""CI-only three-family replay, immutable artifact reuse, and full analysis."""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import shutil
import tempfile
import time
import unittest

from . import contract as c


def tests(output, permit):
    provenance = c.check_permit(permit, "tests")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    suite, selection = unittest.TestSuite(), []
    for module in (c.base.MODULE, c.MODULE):
        for path in sorted((module / "tests").glob("test_*.py")):
            name = ".".join(path.relative_to(c.ROOT).with_suffix("").parts)
            child = unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(name))
            selection.append({"module": name, "tests": child.countTestCases()})
            suite.addTests(child)
    started = time.monotonic()
    with (output / "tests.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    passed = result.testsRun > 58 and result.wasSuccessful() and not result.skipped
    receipt = {**provenance, "tests_passed": passed, "tests_run": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
               "selection": selection, "elapsed_seconds": time.monotonic() - started,
               "new_search_performed": False, "new_exact_solves_performed": False}
    c.write_json(output / "tests_receipt.json", receipt)
    c.write_json(output / "source_manifest.json", c.source_manifest())
    c.write_manifest(output)
    print((output / "tests.txt").read_text(encoding="utf-8"))
    c.require(c.payload_bytes(output) <= c.CAPS["tests"] and passed, "Recovery checks failed")
    return receipt


def worker(output, permit, family):
    provenance = c.check_permit(permit, "recover")
    c.require(family in c.RECOVER_FAMILIES, "Only the exact three missing families may be replayed")
    from ..stagnation_diagnosis_main.runner import verify_saved_batch
    from ..stagnation_diagnosis.contract import load_context
    from ..stagnation_mechanisms.execution import feature_row
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    original = c.base.source_summary()
    source_identity = original["provenance"]
    instances, _, _ = load_context()
    by_id = {item.instance_id: item for item in instances}
    selected = [r for r in original["transport_ledger"]["artifacts"] if
                any(r["name"] == f"knapsack-stagnation-main-worker-{label}-{family}-39465647096-1"
                    for label in ("UC", "WC", "SC"))]
    c.require(len(selected) == 3, "Incomplete original source family")
    rows, errors, transports = [], [], []
    receipt = {**provenance, "family": family, "status": "INCOMPLETE", "completed_count": 0,
               "source_identity": source_identity, "rows": rows, "errors": errors,
               "source_transport": transports, "new_search_performed": False, "new_exact_solves_performed": False}
    started = time.monotonic()
    c.write_json(output / "worker_summary.json", receipt)
    c.write_manifest(output)
    try:
        for source in sorted(selected, key=lambda r: r["name"]):
            try:
                with tempfile.TemporaryDirectory(prefix="three-family-replay-") as temporary:
                    directory = Path(temporary) / "original"
                    transport = c.base.download_source(source, directory)
                    transports.append({"name": source["name"], **transport})
                    verified = verify_saved_batch(directory, source_identity)
                    for item in verified:
                        instance, seed = item["instance_id"], item["repeat_seed"]
                        row = feature_row(by_id[instance], directory / "runs" / str(seed), item, source_identity)
                        rows.append(row)
                        # Atomic per-run checkpoint for honest retention under interruption.
                        c.write_json(output / "runs" / f"{instance}-{seed}.json", row)
                    receipt["completed_count"] = len(rows)
                    c.write_json(output / "worker_summary.json", receipt)
                    c.write_manifest(output)
            except Exception as error:
                errors.append({"artifact": source["name"], "type": type(error).__name__, "message": str(error)})
        expected = {(f"{label}-{family}", s) for label in ("UC", "WC", "SC") for s in range(93001, 93031)}
        keys = [(r["instance_id"], r["repeat_seed"]) for r in rows]
        if len(keys) == len(set(keys)) and set(keys) == expected and not errors:
            receipt["status"] = "COMPLETE"
    finally:
        receipt["completed_count"] = len(rows)
        receipt["elapsed_seconds"] = time.monotonic() - started
        c.write_json(output / "worker_summary.json", receipt)
        c.write_manifest(output)
    c.require(c.payload_bytes(output) <= c.CAPS["worker"], "Recovery payload cap exceeded")
    c.validate_producer(receipt, family, provenance)
    return receipt


def aggregate(output, permit, artifacts):
    provenance = c.check_permit(permit, "recover")
    output, artifacts = Path(output), Path(artifacts)
    output.mkdir(parents=True, exist_ok=False)
    rows, producers, errors, ledger = [], {}, [], []
    if (artifacts / "transport_errors.json").exists():
        errors.append(c.read_json(artifacts / "transport_errors.json"))
    incoming = artifacts / "transport_ledger.json"
    if incoming.exists():
        current = c.read_json(incoming)
        c.require(all(current.get(k) == provenance[k] for k in c.PROVENANCE_KEYS), "Foreign current transport ledger")
        ledger.extend(current["artifacts"])
    with tempfile.TemporaryDirectory(prefix="retained-seven-families-") as temporary:
        directories = {}
        for family in c.REUSED_FAMILIES:
            try:
                directory = Path(temporary) / family
                transport = c.download_reused(family, directory)
                ledger.append(transport)
                directories[transport["name"]] = directory
            except Exception as error:
                errors.append({"family": family, "kind": "reused", "type": type(error).__name__, "message": str(error)})
        for transport in ledger:
            try:
                reused = transport["kind"] == "reused"
                directory = directories[transport["name"]] if reused else c.safe_path(artifacts, transport["name"])
                c.verify_manifest(directory)
                c.require(c.identity(directory / "file_manifest.json")["sha256"] == transport["file_manifest_sha256"],
                          "Worker member manifest differs from transport")
                receipt = c.read_json(directory / "worker_summary.json")
                family = receipt["family"]
                c.require(family not in producers and (family in c.REUSED_FAMILIES) is reused, "Duplicate or wrong producer kind")
                expected_name = (f"{c.base.PREFIX}worker-{family}-39551196713-1" if reused else
                                 f"{c.PREFIX}worker-{family}-{provenance['run_id']}-{provenance['run_attempt']}")
                c.require(transport["name"] == expected_name, "Foreign producer artifact name")
                verified = c.validate_producer(receipt, family, provenance)
                rows.extend(verified)
                keys = c.base.PROVENANCE_KEYS if reused else c.PROVENANCE_KEYS
                producers[family] = {"kind": "reused" if reused else "recovered", "transport": transport,
                                     "execution_identity": {key: receipt[key] for key in keys}, "records": 90}
                if family == "s000":
                    example = directory / "fixed_example_operators.npz"
                    c.require(example.is_file(), "Original fixed-example operator witness missing")
                    shutil.copyfile(example, output / example.name)
                    c.require(c.identity(example) == c.identity(output / example.name), "Fixed-example copy changed")
            except Exception as error:
                errors.append({"artifact": transport["name"], "type": type(error).__name__, "message": str(error)})
    complete = not errors and len(rows) == 900 and set(producers) == set(c.REUSED_FAMILIES + c.RECOVER_FAMILIES)
    audit = {**provenance, "complete": complete, "verified_rows": len(rows), "errors": errors,
             "producers_by_family": producers, "source_identity": c.base.source_summary()["provenance"],
             "new_search_performed": False, "new_exact_solves_performed": False}
    c.write_json(output / "audit_status.json", audit)
    c.write_json(output / "verified_features.json", rows)
    if not complete:
        c.write_manifest(output)
        raise ValueError("INCOMPLETE recovery; retained records do not replace missing families")
    from ..stagnation_mechanisms.analysis import summarize_features, write_report
    summary = summarize_features(rows)
    summary.update(provenance=provenance, source_identity=audit["source_identity"],
                   producers_by_family=producers, new_search_performed=False, new_exact_solves_performed=False,
                   resource_status="PENDING_FINAL_COMBINED_API_ACCOUNTING")
    c.write_json(output / "secondary_summary.json", summary)
    write_report(output, rows, summary)
    c.write_manifest(output)
    c.verify_manifest(output)
    c.require(c.payload_bytes(output) <= c.CAPS["summary"], "Summary payload cap exceeded")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("gate", "tests", "worker", "aggregate", "download", "present"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--phase", choices=tuple(c.RESERVATIONS))
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--family", choices=c.RECOVER_FAMILIES)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--kind", choices=("permit", "workers"))
    args = parser.parse_args(argv)
    if args.command == "gate":
        c.require(args.phase is not None, "Phase required")
        c.gate(args.output, args.phase)
    elif args.command == "download":
        c.require(args.kind is not None, "Transport kind required")
        try:
            c.download_current(args.output, args.kind)
        except Exception as error:
            if args.kind == "workers":
                c.write_json(args.output / "transport_errors.json", {"type": type(error).__name__, "message": str(error)})
            raise
    else:
        c.require(args.permit is not None, "Explicit recovery permit required")
        if args.command == "tests":
            tests(args.output, args.permit)
        elif args.command == "worker":
            c.require(args.family is not None, "One exact missing family required")
            worker(args.output, args.permit, args.family)
        elif args.command == "present":
            from .presentation import render_presentation
            render_presentation(args.output, args.permit)
        else:
            c.require(args.artifacts is not None, "Current worker evidence required")
            aggregate(args.output, args.permit, args.artifacts)


if __name__ == "__main__":
    main()

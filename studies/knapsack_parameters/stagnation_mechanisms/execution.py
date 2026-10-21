"""CI-only post-hoc replay and analysis, with no search entry point."""
from __future__ import annotations

import argparse
import gzip
import importlib
import json
from pathlib import Path
import tempfile
import time
import unittest

from . import contract as c


def run_tests(output, permit):
    provenance = c.check_permit(permit, "tests")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    suite = unittest.TestSuite()
    selection = []
    for path in sorted((c.MODULE / "tests").glob("test_*.py")):
        module = importlib.import_module(".".join(path.relative_to(c.ROOT).with_suffix("").parts))
        child = unittest.defaultTestLoader.loadTestsFromModule(module)
        selection.append({"module": module.__name__, "tests": child.countTestCases()})
        suite.addTests(child)
    started = time.monotonic()
    with (output / "tests.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    passed = result.testsRun > 0 and result.wasSuccessful() and not result.skipped
    receipt = {**provenance, "tests_passed": passed, "tests_run": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
               "selection": selection, "elapsed_seconds": time.monotonic() - started,
               "new_search_performed": False, "new_exact_solves_performed": False}
    c.write_json(output / "tests_receipt.json", receipt)
    c.write_json(output / "source_manifest.json", c.source_manifest())
    c.write_manifest(output)
    print((output / "tests.txt").read_text(encoding="utf-8"))
    c.require(c.payload_bytes(output) <= c.CAPS["tests"] and passed, "Secondary program checks failed")
    return receipt


def _read_result(directory):
    import numpy as np
    directory = Path(directory)
    with np.load(directory / "raw/requests.npz", allow_pickle=False) as saved:
        requests = {name: saved[name].copy() for name in saved.files}
    with gzip.open(directory / "raw/generations.jsonl.gz", "rt", encoding="utf-8") as stream:
        generations = [json.loads(line) for line in stream]
    return {"requests": requests, "generations": generations,
            "summary": c.read_json(directory / "raw/search_summary.json")}


def feature_row(instance, directory, verified, source_identity, example_output=None):
    from .mathematics import certificate_features, detection_probability, mutation_probability
    from .operators import analyze_operators
    from .analysis import PM_GRID, SAMPLE_BUDGETS
    directory = Path(directory)
    result = _read_result(directory)
    diagnosis = c.read_json(directory / "diagnosis.json")
    features = {}
    # Re-use only an already checked certificate within this run, never a search cache.
    for certificate_id, certificate in diagnosis["certificates"].items():
        features[certificate_id] = certificate_features(certificate, weights=instance.weights,
            profits=instance.profits, capacity=instance.capacity)
    checkpoints = []
    for checkpoint in diagnosis["checkpoints"]:
        feature = features[checkpoint["certificate_id"]]
        checkpoints.append({**checkpoint, **feature,
            "model_probabilities": [{"p": p, "probability": mutation_probability(instance.n, feature["b1"], feature["b2"], p)}
                                    for p in PM_GRID],
            "detection_probabilities": [{"sample_size": size, "probability": detection_probability(
                instance.n + instance.n * (instance.n - 1) // 2, feature["total_better"], size)}
                                        for size in SAMPLE_BUDGETS]})
    operator_summary = analyze_operators(instance, result, diagnosis, example_output)
    return {"instance_id": instance.instance_id, "class_label": instance.class_label,
            "family": instance.family, "repeat_seed": verified["repeat_seed"], "status": "PASS", "verified": True,
            "source_identity": source_identity, "source_members": {
                "file_manifest": c.identity(directory / "file_manifest.json"),
                "raw_file_manifest": c.identity(directory / "raw/file_manifest.json"),
                "diagnosis": c.identity(directory / "diagnosis.json")},
            "checkpoints": checkpoints, "operators": operator_summary,
            "population_trajectory": diagnosis["population_trajectory"],
            "source_reverification": verified["aggregate_independent_verification"],
            "new_search_evaluations": 0,
            "posthoc_intermediate_scores": 5000,
            "posthoc_certificate_neighbors": 5050 * len(features)}


def worker(output, permit, family):
    provenance = c.check_permit(permit, "analyze")
    c.require(family in tuple(f"s{i:03d}" for i in range(10)), "Unregistered family")
    from ..stagnation_diagnosis_main.runner import verify_saved_batch
    from ..stagnation_diagnosis.contract import load_context
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    original = c.source_summary()
    source_identity = original["provenance"]
    instances, _, _ = load_context()
    by_id = {item.instance_id: item for item in instances}
    selected = [row for row in original["transport_ledger"]["artifacts"]
                if any(row["name"] == f"knapsack-stagnation-main-worker-{label}-{family}-39465647096-1"
                       for label in ("UC", "WC", "SC"))]
    c.require(len(selected) == 3, "Incomplete frozen family ledger")
    rows, errors, transports = [], [], []
    started = time.monotonic()
    receipt = {**provenance, "family": family, "status": "INCOMPLETE", "source_identity": source_identity,
               "rows": rows, "errors": errors, "source_transport": transports,
               "new_search_performed": False, "new_exact_solves_performed": False}
    try:
        for ledger_row in sorted(selected, key=lambda r: r["name"]):
            try:
                with tempfile.TemporaryDirectory(prefix="saved-stagnation-family-") as temporary:
                    directory = Path(temporary) / "source"
                    transport = c.download_source(ledger_row, directory)
                    transports.append({"name": ledger_row["name"], **transport})
                    verified_rows = verify_saved_batch(directory, source_identity)
                    for verified in verified_rows:
                        instance_id, seed = verified["instance_id"], verified["repeat_seed"]
                        example = output / "fixed_example_operators.npz" if (instance_id, seed) == ("UC-s000", 93001) else None
                        rows.append(feature_row(by_id[instance_id], directory / "runs" / str(seed),
                                                verified, source_identity, example))
            except Exception as error:
                errors.append({"artifact": ledger_row["name"], "type": type(error).__name__, "message": str(error)})
        keys = {(r["instance_id"], r["repeat_seed"]) for r in rows}
        expected = {(f"{label}-{family}", seed) for label in ("UC", "WC", "SC") for seed in range(93001, 93031)}
        c.require(len(rows) == len(keys), "Duplicate secondary identities")
        if not errors and keys == expected:
            receipt["status"] = "COMPLETE"
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - started
        receipt["completed_count"] = len(rows)
        c.write_json(output / "worker_summary.json", receipt)
        c.write_manifest(output)
    c.require(c.payload_bytes(output) <= c.CAPS["worker"] and receipt["status"] == "COMPLETE",
              "Incomplete family audit; retain available records and do not replace the source")
    return receipt


def aggregate(output, artifacts, permit):
    provenance = c.check_permit(permit, "analyze")
    output, artifacts = Path(output), Path(artifacts)
    output.mkdir(parents=True, exist_ok=False)
    ledger_path = artifacts / "transport_ledger.json"
    ledger = c.read_json(ledger_path) if ledger_path.exists() else {**provenance, "artifacts": []}
    c.require(all(ledger.get(key) == provenance[key] for key in c.PROVENANCE_KEYS), "Mixed current artifact ledger")
    rows, errors, seen_families = [], [], set()
    if (artifacts / "transport_errors.json").exists():
        errors.append(c.read_json(artifacts / "transport_errors.json"))
    source_identity = c.source_summary()["provenance"]
    for transport in ledger["artifacts"]:
        try:
            directory = c.safe_path(artifacts, transport["name"])
            c.verify_manifest(directory)
            c.require(c.identity(directory / "file_manifest.json")["sha256"] == transport["file_manifest_sha256"],
                      "Current worker member ledger changed")
            receipt = c.read_json(directory / "worker_summary.json")
            family = receipt["family"]
            c.require(family in tuple(f"s{i:03d}" for i in range(10)) and family not in seen_families and
                      transport["name"] == f"{c.PREFIX}worker-{family}-{provenance['run_id']}-{provenance['run_attempt']}",
                      "Duplicate or foreign family")
            seen_families.add(family)
            c.require(all(receipt.get(k) == provenance[k] for k in c.PROVENANCE_KEYS) and
                      receipt["source_identity"] == source_identity, "Mixed source or analysis identity")
            c.require(receipt["status"] == "COMPLETE" and receipt["completed_count"] == 90 and
                      not receipt["errors"] and len(receipt["rows"]) == 90, "Incomplete family receipt")
            c.require(all(r["family"] == family and r["source_identity"] == source_identity for r in receipt["rows"]),
                      "Mixed family feature rows")
            rows.extend(receipt["rows"])
        except Exception as error:
            errors.append({"artifact": transport["name"], "type": type(error).__name__, "message": str(error)})
    c.write_json(output / "verified_features.json", rows)
    c.write_json(output / "audit_status.json", {**provenance, "source_identity": source_identity,
        "complete": not errors and len(rows) == 900 and len(seen_families) == 10,
        "verified_rows": len(rows), "errors": errors, "transport_ledger": ledger,
        "new_search_performed": False, "new_exact_solves_performed": False})
    if errors or len(rows) != 900 or len(seen_families) != 10:
        c.write_manifest(output)
        raise ValueError("INCOMPLETE secondary audit; no scientific summary substituted")
    from .analysis import summarize_features, write_report
    summary = summarize_features(rows)
    summary.update(provenance=provenance, source_identity=source_identity, transport_ledger=ledger,
                   new_search_performed=False, new_exact_solves_performed=False,
                   resource_status="PENDING_FINAL_GITHUB_JOB_TIMINGS")
    c.write_json(output / "secondary_summary.json", summary)
    write_report(output, rows, summary)
    c.write_manifest(output)
    c.verify_manifest(output)
    c.require(c.payload_bytes(output) <= c.CAPS["summary"], "Summary payload cap exceeded")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("gate", "download", "tests", "worker", "aggregate"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--phase", choices=tuple(c.RESERVATIONS))
    parser.add_argument("--kind", choices=("permit", "workers"))
    parser.add_argument("--family")
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args(argv)
    if args.command == "gate":
        c.require(args.phase is not None, "Phase required")
        c.gate(args.output, args.phase)
    elif args.command == "download":
        c.require(args.kind is not None, "Artifact kind required")
        try:
            c.download_current(args.output, args.kind)
        except Exception as error:
            if args.kind == "workers":
                c.write_json(args.output / "transport_errors.json", {
                    "type": type(error).__name__, "message": str(error)})
            raise
    else:
        c.require(args.permit is not None, "New secondary-analysis permit required")
        if args.command == "tests":
            run_tests(args.output, args.permit)
        elif args.command == "worker":
            worker(args.output, args.permit, args.family)
        else:
            c.require(args.artifacts is not None, "Current worker evidence required")
            aggregate(args.output, args.artifacts, args.permit)


if __name__ == "__main__":
    main()

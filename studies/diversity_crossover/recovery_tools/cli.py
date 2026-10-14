"""CI-only, separately registered recovery of frozen searches; no new search."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import time
import unittest

from ..main_study import ci_support, contract

RECOVERY_ID = "GA-DIVERSITY-CROSSOVER-AGGREGATION-RECOVERY-V1"
REGISTRATION_SHA = "f4d2ef6e07b1efc490751c0a12c5413949d1f58d"
SOURCE_SHA = "c856c9d6811eda51cb4c8b1786033e122249a52d"
SOURCE_RUN = 38396509102
SOURCE_DIGEST = "9359220a9ac47f4bf6df816817c01f526cd25ce4a8ebd9100f1502c51c816d3a"
PLACEHOLDER_ID = 115293051290
ROOT = Path(__file__).resolve().parent


def recovery_manifest():
    paths = list(ROOT.rglob("*.py"))
    paths += [contract.STUDY_ROOT / "RECOVERY_PROTOCOL_UK.md",
              contract.STUDY_ROOT / "main_aggregation_request.json",
              contract.REPO_ROOT / ".github/workflows/diversity-crossover-recovery.yml"]
    rows = [{"path": p.relative_to(contract.REPO_ROOT).as_posix(), **contract.file_identity(p)}
            for p in sorted(set(paths))]
    return {"schema_version": 1, "recovery_id": RECOVERY_ID, "files": rows,
            "sha256": hashlib.sha256(contract.canonical_bytes(rows)).hexdigest()}


def authenticate(require_runtime=True):
    identity = contract.authenticate(require_runtime=require_runtime)
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA,
                    identity["implementation_sha"]], cwd=contract.REPO_ROOT, check=True)
    relative = "studies/diversity_crossover/RECOVERY_PROTOCOL_UK.md"
    registered = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + relative],
                                         cwd=contract.REPO_ROOT)
    contract.require(registered == (contract.REPO_ROOT / relative).read_bytes(),
                     "Recovery registration changed")
    contract.require(contract.source_manifest()["sha256"] == SOURCE_DIGEST,
                     "Frozen scientific source manifest changed")
    request = contract.read_json(contract.STUDY_ROOT / "main_aggregation_request.json")
    contract.require(request == {"protocol_id": contract.PROTOCOL_ID,
        "source_run_id": SOURCE_RUN, "source_sha": SOURCE_SHA,
        "source_manifest_sha256": SOURCE_DIGEST}, "Recovery source binding changed")
    return dict(identity, recovery_id=RECOVERY_ID, recovery_registration_sha=REGISTRATION_SHA,
                search_implementation_sha=SOURCE_SHA, search_run_id=SOURCE_RUN)


def phase(output):
    authenticate(require_runtime=False)
    message = os.environ.get("COMMIT_MESSAGE", "")
    markers = re.findall(r"\[diversity-recovery:([^\]]+)\]", message)
    contract.require(len(markers) == 1 and markers[0] in ("tests", "aggregate") and
                     not re.search(r"\[(?:diversity-main|diversity|knapsack|knapsack-ga|lambda-paper|knapsack-review):", message),
                     "Unknown or mixed recovery marker")
    stage = markers[0]
    # Same-push inactive workflows may briefly be queued. No computation happens
    # until the unchanged raw API budget guard can account for every workflow.
    for retry in range(11):
        try:
            budget = contract.budget_preflight(stage)
            break
        except ValueError as exc:
            if str(exc) != "Another branch workflow is still active" or retry == 10:
                raise
            time.sleep(2)
    contract.write_json(Path(output) / "budget-preflight.json", budget)
    contract.write_file_manifest(output)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write("phase=" + stage + "\n")
    print("Authorized infrastructure recovery phase:", stage)


def tests(output):
    identity = authenticate()
    budget = contract.nonsearch_budget_preflight("tests")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"),
                                                top_level_dir=str(contract.REPO_ROOT))
    with (output / "unittest.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    receipt = {"recovery_id": RECOVERY_ID, "tests_passed": result.wasSuccessful(),
               "tests_run": result.testsRun, "failure_count": len(result.failures),
               "error_count": len(result.errors), "skipped_count": len(result.skipped),
               "recovery_manifest": recovery_manifest(),
               "scientific_source_manifest": contract.source_manifest(), "provenance": identity}
    contract.write_json(output / "tests_receipt.json", receipt)
    contract.write_json(output / "budget-preflight.json", budget)
    contract.write_file_manifest(output)
    print("Recovery metadata tests:", result.testsRun, "passed:", result.wasSuccessful())
    if not result.wasSuccessful() or result.testsRun == 0 or result.skipped:
        print((output / "unittest.txt").read_text(encoding="utf-8"))
        raise SystemExit(1)


def validate_recovery_receipt():
    receipt = contract.read_json(contract.STUDY_ROOT / "recovery_validated_implementation.json")
    contract.require(receipt.get("recovery_id") == RECOVERY_ID and
        receipt.get("tests_passed") is True and receipt.get("tests_run", 0) > 0 and
        receipt.get("failure_count") == 0 and receipt.get("error_count") == 0 and
        receipt.get("skipped_count") == 0, "Recovery tests are incomplete")
    contract.require(receipt["recovery_manifest"] == recovery_manifest() and
        receipt["scientific_source_manifest"] == contract.source_manifest(),
        "Recovery/scientific source files changed after green tests")
    return contract.validate_artifact_receipt(receipt["tests_run_id"], receipt["tests_artifact_id"],
                                             receipt["tests_sha"], receipt["tests_zip_sha256"])


def aggregate(output):
    from .adapter import filtered_source_api
    identity = authenticate()
    validate_recovery_receipt()
    contract.validate_tests_receipt()
    contract.nonsearch_budget_preflight("aggregate")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    contract.require(os.environ.get("AGGREGATION_PHASE") == "aggregate",
                     "Only registered standalone aggregation is permitted")
    audit_dir = output / "recovery_audit"
    contract.write_json(audit_dir / "recovery_provenance.json", identity)
    contract.write_json(audit_dir / "recovery_source_manifest.json", recovery_manifest())
    request = contract.read_json(contract.STUDY_ROOT / "main_aggregation_request.json")
    binding = dict(request, source_attempts=2, placeholder_job_id=PLACEHOLDER_ID,
                   first_failed_phase_job_id=115292975476)
    expected_names = {f"main ({spec['id']})" for spec in contract.matrix_jobs()}
    try:
        with filtered_source_api(ci_support, raw_api=contract.api, binding=binding,
                                 expected_names=expected_names, audit_dir=audit_dir):
            ci_support.aggregate(output)
    except BaseException as exc:
        contract.write_json(audit_dir / "recovery_failure.json",
                            {"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        contract.write_file_manifest(output)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("phase", "tests", "aggregate", "closure"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    contract.ci_only()
    if args.phase == "closure":
        authenticate(require_runtime=False)
        ci_support.closure(args.output)
    else:
        {"phase": phase, "tests": tests, "aggregate": aggregate}[args.phase](args.output)


if __name__ == "__main__":
    main()

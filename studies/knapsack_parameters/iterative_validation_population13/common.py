"""Independent admission for the prospective six-case technical stage."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys

from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPOSITORY = "ChepaMaksym/GA-article-test"
REF = "refs/heads/research/iterative-validation-population13-technical-20261117"
WORKFLOW = ".github/workflows/iterative-validation-population13-technical.yml"
SOURCE_SHA256 = "70adbcca7b27e645f8a01b7f8662358d62c347bf02a4edb825996ebf62a1af32"
TOTAL = 100000
PILOTS = (("n00100-UC-s000", 0), ("n00100-WC-s001", 1), ("n00100-SC-s005", 2))
COMPATIBILITY = (("n00100-UC-s050", 10), ("n00100-WC-s050", 15), ("n00100-SC-s050", 20))


def registered_cases():
    """Return the complete technical inventory without creating search inputs."""
    pilots = [{"case_id": "pilot-" + task, "task": task, "task_index": index,
               "mode": "pilot", "mu": 13, "seed": 159999, "preparation_seed": 159998}
              for task, index in PILOTS]
    # Original task indices are fixed by the retained preparation manifest.
    compatibility = [{"case_id": "compatibility-" + task, "task": task, "task_index": index,
                      "mode": "compatibility", "mu": mu, "seed": 150001,
                      "preparation_seed": 150000} for index, (task, mu) in enumerate(COMPATIBILITY, 3)]
    return pilots + compatibility


def descriptor(root, entry):
    """Resolve only a uniquely pinned file inside the declared transport root."""
    require(type(entry) is dict, "Required retained input descriptor is unresolved")
    relative = entry.get("path")
    require(type(relative) is str and relative and "\\" not in relative and ":" not in relative,
            "Unsafe retained input path")
    parts = PurePosixPath(relative)
    require(not parts.is_absolute() and ".." not in parts.parts and parts.as_posix() == relative,
            "Unsafe retained input path")
    size = entry.get("bytes")
    bounded_pending_size = size is None and type(entry.get("max_bytes")) is int and entry["max_bytes"] > 0
    require((type(size) is int and size > 0 or bounded_pending_size)
            and re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", "")) is not None,
            "Retained input exact size or strict byte bound and SHA256 are required")
    root = Path(root).resolve()
    path = root.joinpath(*parts.parts)
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),
            "Required retained input is missing or unsafe: " + relative)
    actual_size = path.stat().st_size
    require((actual_size == size if size is not None else 0 < actual_size <= entry["max_bytes"])
            and sha(path) == entry["sha256"],
            "Retained input bytes differ: " + relative)
    return path


def validate_plan(plan):
    """Reject replacement tasks, seeds, banks, or compact compatibility evidence."""
    require(type(plan) is dict and plan.get("schema") == "population13-retained-input-plan-v1"
            and plan.get("source_sha256") == SOURCE_SHA256,
            "The retained source input plan differs")
    rows = plan.get("cases")
    expected = registered_cases()
    require(type(rows) is list and len(rows) == 6
            and all(type(row) is dict for row in rows)
            and {row.get("case_id") for row in rows} == {row["case_id"] for row in expected},
            "The technical plan must contain exactly six distinct registered cases")
    by_id = {row["case_id"]: row for row in rows}
    for fixed in expected:
        row = by_id[fixed["case_id"]]
        require(all(type(row.get(key)) is type(value) and row[key] == value for key, value in fixed.items()),
                "Registered case identity differs: " + fixed["case_id"])
        require(type(row.get("task_index")) is int and row["task_index"] >= 0,
                "Original task index must be pinned")
        for name in ("problem", "certificate"):
            require(type(row.get(name)) is dict, "Unresolved retained input: " + row["case_id"] + "/" + name)
        if row["mode"] == "compatibility":
            require(type(row.get("source")) is dict and type(row.get("bank")) is dict
                    and type(row.get("reference_journal")) is dict,
                    "Exact compatibility requires the original bank and complete journal")
            origin = row.get("origin", {})
            require(type(origin.get("run_id")) is int and origin["run_id"] > 0
                    and re.fullmatch(r"[0-9a-f]{40}", origin.get("commit", "")) is not None
                    and type(origin.get("raw_artifact_name")) is str and origin["raw_artifact_name"]
                    and origin.get("comparison_scope") == "complete_journal_except_timing_ns",
                    "Full historical journal provenance is unresolved")
    require(plan.get("transport_status") in ("PINNED_COMPLETE_FILES", "PINNED_HASHES_PENDING_CI_MEMBER_LENGTHS"),
            "Historical transport is unresolved; a compact record cannot replace a full journal")
    return by_id


def verify_source(authorization):
    """Verify the new wrapper and every immutable execution dependency."""
    seal = HERE / "source_manifest.json"
    require(seal.is_file() and sha(seal) == authorization.get("source_manifest_sha256"),
            "A matching source seal is required")
    manifest = read_json(seal)
    require(manifest.get("schema") == "population13-technical-source-v1",
            "Population-thirteen source seal is absent")
    rows = manifest.get("files")
    require(type(rows) is list and rows, "The technical source manifest is empty")
    seen = set()
    for row in rows:
        require(row.get("path") not in seen, "Duplicate source dependency")
        path = descriptor(ROOT, row)
        seen.add(path.relative_to(ROOT).as_posix())
    required = {path.relative_to(ROOT).as_posix() for path in HERE.glob("*.py")}
    required.update({WORKFLOW,
                     "studies/knapsack_parameters/ga_study/dependencies/requirements.lock",
                     "studies/knapsack_parameters/iterative_validation/protocol.json",
                     "studies/knapsack_parameters/iterative_validation/PROTOCOL_UK.md",
                     "studies/knapsack_parameters/initial_grid_100/data/retained_inputs.zip"})
    required.update((HERE / name).relative_to(ROOT).as_posix()
                    for name in ("protocol.json", "PROTOCOL_UK.md", "retained_input_plan.json", "reference_sources.json"))
    required.update(path.relative_to(ROOT).as_posix()
                    for path in (HERE.parent / "crossover_population/program/ga_core").glob("*.py"))
    required.update("studies/knapsack_parameters/" + name for name in (
        "crossover_population/verification.py", "crossover_population/observations.py",
        "population_validation_100/common.py", "population_validation_100/preparation.py",
        "population_validation_100_main/runner.py", "initial_grid_100/preparation.py",
        "population_validation_100_main/common.py", "initial_grid_100/common.py",
        "population_size_study/inputs.py", "population_size_study/io_utils.py",
        "initial_grid_100/data/source_registry.json"))
    required.update("studies/knapsack_parameters/population_validation_100/data/technical/" + task + ".source.json"
                    for task, _ in PILOTS)
    require(required.issubset(seen), "The source manifest omits a required technical dependency")
    for name in ("protocol.json", "PROTOCOL_UK.md", "retained_input_plan.json"):
        field = {"protocol.json": "protocol_sha256", "PROTOCOL_UK.md": "protocol_document_sha256",
                 "retained_input_plan.json": "retained_input_plan_sha256"}[name]
        require(sha(HERE / name) == authorization.get(field), "Authorization payload differs: " + name)
    return sha(seal)


def guard_technical(authorization_id=None):
    """Admit only a fresh explicit grant, never the older analysis allowance."""
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Technical execution is permitted only in GitHub Actions")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
            and os.environ.get("GITHUB_REF") == REF
            and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "Unregistered manual technical execution")
    require(re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", "")) is not None
            and re.fullmatch(r"[0-9]+", os.environ.get("GITHUB_RUN_ID", "")) is not None,
            "A real workflow commit and run identity are required")
    import numpy as np
    require(sys.version_info[:3] == (3, 12, 14) and np.__version__ == "2.2.6",
            "Frozen Python/NumPy versions differ")
    protocol = read_json(HERE / "protocol.json")
    require(protocol.get("schema") == "population13-technical-protocol-v1"
            and protocol.get("technical_runs") == 6
            and protocol.get("total_evaluations_including_initial") == TOTAL
            and protocol.get("main_runs_authorized") is False,
            "Registered technical scope differs")
    authorization = read_json(HERE / "resource_authorization.json")
    require(authorization.get("schema") == "population13-technical-resource-authorization-v1"
            and authorization.get("status") == "AUTHORIZED"
            and authorization.get("stage") == "population13_technical"
            and authorization.get("repository") == REPOSITORY and authorization.get("ref") == REF
            and authorization.get("historical_budgets_inherited") is False
            and authorization.get("fresh_approval") is True
            and authorization.get("main_runs_authorized") is False
            and authorization.get("additional_dispatches_authorized") is False,
            "A separate population-thirteen technical resource grant is required")
    requested = authorization_id if authorization_id is not None else os.environ.get("POPULATION13_AUTHORIZATION_ID")
    require(type(requested) is str and requested == authorization.get("authorization_id")
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", requested) is not None,
            "The requested technical authorization identity differs")
    limits = protocol["resources_proposal"]
    for name in ("runner_minutes", "artifact_bytes"):
        require(type(authorization.get(name)) is int and authorization[name] > 0
                and authorization[name] == limits[name], "Distinct numerical resource ceiling differs: " + name)
    verify_source(authorization)
    require(authorization.get("retained_source_sha256") == SOURCE_SHA256,
            "The accepted historical source differs")
    validate_plan(read_json(HERE / "retained_input_plan.json"))
    return protocol, authorization


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization-id", required=True)
    args = parser.parse_args()
    protocol, authorization = guard_technical(args.authorization_id)
    print(json.dumps({"status": "ADMITTED_POPULATION13_TECHNICAL", "technical_runs": 6,
                      "runner_minutes": protocol["resources_proposal"]["runner_minutes"],
                      "authorization_id": authorization["authorization_id"], "main_runs_authorized": False}), flush=True)


if __name__ == "__main__":
    main()

"""Admit the registered ninety-case study and its finite source inventory."""
from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import re
import sys

from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPOSITORY = "ChepaMaksym/GA-article-test"
REF = "refs/heads/research/iterative-validation-population13-main-20261118"
WORKFLOW = ".github/workflows/iterative-validation-population13-main.yml"
SOURCE_SHA256 = "70adbcca7b27e645f8a01b7f8662358d62c347bf02a4edb825996ebf62a1af32"
TOTAL = 100000
FAMILIES = tuple(f"s{number:03d}" for number in range(50, 60))
TYPES = ("UC", "WC", "SC")
SEEDS = (150001, 150002, 150003)


def registered_cases():
    """Return the ninety identities without reading, scoring, or generating data."""
    return [{"case_id": f"n00100-{kind}-{family}-seed-{seed}-mu13",
             "task": f"n00100-{kind}-{family}",
             "task_index": 3 + 3 * family_index + kind_index,
             "family": family, "class_label": kind, "seed": seed,
             "mu": 13, "pc_percentage": 90, "mutation_basis_points": 100,
             "preparation_seed": 150000}
            for family_index, family in enumerate(FAMILIES)
            for kind_index, kind in enumerate(TYPES) for seed in SEEDS]


def registered_shards():
    """Keep three repeats of one task together, with a deterministic shard order."""
    cases = registered_cases()
    return [{"shard_id": f"{index // 3:03d}",
             "case_ids": [row["case_id"] for row in cases[index:index + 3]]}
            for index in range(0, len(cases), 3)]


def descriptor(root, entry):
    """Resolve one exact, canonical, non-linked file below the declared root."""
    require(type(entry) is dict, "A pinned file descriptor is required")
    relative = entry.get("path")
    require(type(relative) is str and relative and "\\" not in relative and ":" not in relative
            and all(32 <= ord(char) != 127 for char in relative), "Unsafe source path")
    parts = PurePosixPath(relative)
    require(not parts.is_absolute() and ".." not in parts.parts and "." not in parts.parts
            and parts.as_posix() == relative, "Noncanonical source path")
    require(type(entry.get("bytes")) is int and entry["bytes"] > 0
            and re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", "")) is not None,
            "An exact file length and SHA256 are required")
    root = Path(root).resolve()
    path = root.joinpath(*parts.parts)
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),
            "A pinned file is missing or unsafe: " + relative)
    require(path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"],
            "Pinned file bytes differ: " + relative)
    return path


def validate_case_origin(record, authorization):
    """Admit current evidence or an explicitly pinned prior run with identical code."""
    require(type(record) is dict and record.get("source_manifest_sha256")
            == authorization.get("source_manifest_sha256"), "Mixed source seals are forbidden")
    origin_fields = ("workflow_run_id", "workflow_commit", "authorization_id",
                     "source_manifest_sha256", "inputs_manifest_sha256")
    require(type(record.get("workflow_run_id")) is str
            and re.fullmatch(r"[0-9]+", record["workflow_run_id"]) is not None
            and re.fullmatch(r"[0-9a-f]{40}", record.get("workflow_commit", "")) is not None
            and re.fullmatch(r"[0-9a-f]{64}", record.get("inputs_manifest_sha256", "")) is not None,
            "Case provenance is incomplete")
    if record["workflow_run_id"] == os.environ.get("GITHUB_RUN_ID"):
        require(record["workflow_commit"] == os.environ.get("GITHUB_SHA")
                and record.get("authorization_id") == authorization.get("authorization_id"),
                "Current workflow identity differs")
        return {key: record[key] for key in origin_fields}
    admitted = authorization.get("allowed_resume_runs", [])
    matches = [row for row in admitted if all(row.get(key) == record.get(key) for key in origin_fields)]
    require(len(matches) == 1, "A prior result has no unique admitted immutable origin")
    return matches[0]


def verify_source(authorization):
    """Authenticate the complete finite execution closure without importing it."""
    path = HERE / "source_manifest.json"
    require(sha(path) == authorization.get("source_manifest_sha256"), "Source seal differs")
    manifest = read_json(path)
    require(manifest.get("schema") == "population13-main-source-v1", "Wrong source inventory")
    rows = manifest.get("files")
    require(type(rows) is list and rows and len({row.get("path") for row in rows}) == len(rows),
            "Source inventory is empty or duplicated")
    for row in rows:
        descriptor(ROOT, row)
    seen = {row["path"] for row in rows}
    required = {p.relative_to(ROOT).as_posix() for p in HERE.glob("*.py")}
    required.update((HERE / name).relative_to(ROOT).as_posix() for name in
                    ("protocol.json", "PROTOCOL_UK.md", "ELIGIBILITY_AUDIT_UK.md", ".gitattributes"))
    required.update({WORKFLOW, "studies/knapsack_parameters/ga_study/dependencies/requirements.lock",
                     "studies/knapsack_parameters/iterative_validation/data/validated_records.json.gz",
                     "studies/knapsack_parameters/iterative_validation/data/selection.json",
                     "studies/knapsack_parameters/iterative_validation/data/all-configurations.csv"})
    require(required.issubset(seen), "Required source dependencies are unsealed")
    for name, key in (("protocol.json", "protocol_sha256"),
                      ("PROTOCOL_UK.md", "protocol_document_sha256")):
        require(sha(HERE / name) == authorization.get(key), "Registration binding differs: " + name)
    return sha(path)


def guard_main(authorization_id=None):
    """Require genuine CI, explicit stage permission, source identity, and resource room."""
    require(os.environ.get("GITHUB_ACTIONS") == "true", "This study runs only in GitHub Actions")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
            and os.environ.get("GITHUB_REF") == REF
            and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "Unregistered execution context")
    require(re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", "")) is not None
            and re.fullmatch(r"[0-9]+", os.environ.get("GITHUB_RUN_ID", "")) is not None,
            "A real commit and workflow run are required")
    import numpy as np
    require(sys.version_info[:3] == (3, 12, 14) and np.__version__ == "2.2.6",
            "Frozen Python or NumPy versions differ")
    protocol = read_json(HERE / "protocol.json")
    require(protocol.get("schema") == "population13-main-protocol-v1"
            and protocol.get("main_runs") == 90 and protocol.get("total_evaluations") == TOTAL
            and protocol.get("configuration") == {"mu": 13, "pc_percentage": 90,
                "mutation_basis_points": 100, "tournament_size": 2, "elite_count": 1}
            and protocol.get("independent_validation") is False, "Registered scientific scope differs")
    authorization = read_json(HERE / "resource_authorization.json")
    require(authorization.get("schema") == "population13-main-resource-authorization-v1"
            and authorization.get("status") == "AUTHORIZED"
            and authorization.get("fresh_approval") is True
            and authorization.get("public_release_approved") is True
            and authorization.get("historical_budgets_inherited") is False
            and authorization.get("repository") == REPOSITORY and authorization.get("ref") == REF,
            "A new main-series resource and publication permission is required")
    requested = authorization_id if authorization_id is not None else os.environ.get("POPULATION13_MAIN_AUTHORIZATION_ID")
    require(type(requested) is str and requested == authorization.get("authorization_id")
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", requested) is not None,
            "Requested resource identity differs")
    limits = protocol["resources_proposal"]
    for key in ("runner_minutes", "artifact_bytes"):
        require(type(authorization.get(key)) is int and authorization[key] == limits[key],
                "The separate numerical main-series ceiling differs")
    remaining = authorization.get("remaining_runner_minutes")
    maximum = authorization.get("maximum_shards_this_dispatch")
    require(type(remaining) is int and 0 < remaining <= authorization["runner_minutes"]
            and type(maximum) is int and 0 <= maximum <= 30
            and 5 + 10 + 4 * maximum + 2 <= remaining,
            "Remaining resources cannot cover the admitted dispatch")
    resumes = authorization.get("allowed_resume_runs")
    require(type(resumes) is list and all(type(row) is dict for row in resumes)
            and len({row.get("workflow_run_id") for row in resumes}) == len(resumes),
            "Resume origin inventory is missing or duplicated")
    for row in resumes:
        require(set(row) == {"workflow_run_id", "workflow_commit", "authorization_id",
                             "source_manifest_sha256", "inputs_manifest_sha256"}
                and type(row["workflow_run_id"]) is str and row["workflow_run_id"].isdigit()
                and re.fullmatch(r"[0-9a-f]{40}", row.get("workflow_commit", "")) is not None
                and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", row.get("authorization_id", "")) is not None
                and re.fullmatch(r"[0-9a-f]{64}", row.get("inputs_manifest_sha256", "")) is not None
                and row["source_manifest_sha256"] == authorization.get("source_manifest_sha256"),
                "A resume origin is malformed or uses different source code")
    verify_source(authorization)
    technical = read_json(descriptor(ROOT, protocol["technical_summary"]))
    require(technical.get("status") == "SIX_TECHNICAL_CASES_VERIFIED"
            and technical.get("verified_cases") == 6
            and technical.get("technical_search_evaluations") == 600000
            and technical.get("scientific_winner_selected_from_pilot") is False
            and len(technical.get("cases", [])) == 6
            and all(row.get("status") == "VERIFIED"
                    and row.get("workflow_run_id") == str(protocol["technical_passed_run_id"])
                    and row.get("workflow_commit") == protocol["technical_passed_commit"]
                    for row in technical["cases"]),
            "The completed six-case technical admission is absent or differs")
    require(sha(ROOT / "studies/knapsack_parameters/iterative_validation/data/validated_records.json.gz")
            == SOURCE_SHA256, "Historical 2790-record source differs")
    return protocol, authorization


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization-id", required=True)
    args = parser.parse_args()
    _, admitted = guard_main(args.authorization_id)
    print(json.dumps({"status": "MAIN_RESOURCE_ADMITTED", "authorization_id": admitted["authorization_id"],
                      "main_runs": 90, "main_runs_started_by_admission": 0}))

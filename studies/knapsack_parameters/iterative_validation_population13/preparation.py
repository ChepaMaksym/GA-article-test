"""Authenticate explicit retained files and prepare only three new pilot banks.

All numerical checks and bank generation are authorized CI operations. There is
no network client, fallback bank generation, exact solver, or GA call here.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import time

from .common import HERE, descriptor, guard_technical, validate_plan
from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha
from studies.knapsack_parameters.population_validation_100_main.runner import _used_bytes, _write_bounded


def validate_retained_certificate(problem, certificate, raw=None, *, require_input_hashes=False):
    """Recheck witnesses and optional source fields without invoking a solver.

    Original main certificates predate the optional problem/source hash fields.
    Their exact file hashes and independently pinned source/problem bytes are
    authenticated before this function. Preserve the original certificate form.
    """
    from studies.knapsack_parameters.population_validation_100_main.runner import _verify_certificates
    from studies.knapsack_parameters.population_size_study.inputs import problem_sha256
    if require_input_hashes:
        require("problem_sha256" in certificate and "source_sha256" in certificate,
                "The retained pilot certificate must preserve its original problem and source hashes")
    if "problem_sha256" in certificate:
        require(certificate["problem_sha256"] == problem_sha256(problem),
                "Retained certificate identifies a different problem")
    if "source_sha256" in certificate:
        require(type(raw) is bytes and certificate["source_sha256"] == sha256(raw).hexdigest(),
                "Retained certificate identifies different source bytes")
    _verify_certificates(problem, certificate)


def authenticate_transport(root, plan, authorization):
    """Retain authenticated archive provenance and all resolved member lengths."""
    root = Path(root)
    path = root / "transport_manifest.json"
    transport = read_json(path)
    registry_path = HERE / "reference_sources.json"
    registry = read_json(registry_path)
    require(transport.get("schema") == "population13-retained-transport-v1"
            and transport.get("status") == "AUTHENTICATED_SELECTED_MEMBERS"
            and transport.get("reference_sources_sha256") == sha(registry_path)
            and transport.get("retained_input_plan_sha256") == sha(HERE / "retained_input_plan.json")
            and transport.get("source_manifest_sha256") == authorization["source_manifest_sha256"]
            and transport.get("authorization_id") == authorization["authorization_id"]
            and transport.get("workflow_run_id") == os.environ.get("GITHUB_RUN_ID")
            and transport.get("workflow_commit") == os.environ.get("GITHUB_SHA")
            and transport.get("ga_runs") == 0 and transport.get("banks_generated") == 0
            and transport.get("exact_solver_calls") == 0 and transport.get("raw_source_archives_uploaded") is False,
            "Authenticated transport provenance differs")
    archives = transport.get("archives")
    require(type(archives) is list and len(archives) == 5
            and len({entry.get("id") for entry in archives}) == 5,
            "Original transport archive inventory differs")
    by_id = {entry["id"]: entry for entry in archives}
    for expected in registry["remote_artifacts"]:
        actual = by_id.get(expected["id"], {})
        require(all(actual.get(name) == expected[name] for name in
                    ("id", "name", "bytes", "sha256", "run_id", "commit")),
                "Original remote archive authentication receipt differs")
    local = by_id.get("committed-retained-inputs", {})
    require(all(local.get(name) == registry["local_input_archive"][name] for name in ("path", "bytes", "sha256"))
            and transport.get("remote_archive_bytes") == plan["remote_archive_bytes"],
            "Local archive or remote transport byte total differs")
    files = transport.get("files")
    require(type(files) is list and len(files) == 24
            and len({entry.get("path") for entry in files}) == 24
            and all(type(entry.get("bytes")) is int and entry["bytes"] > 0 for entry in files),
            "Transport must resolve twenty-four exact member lengths")
    expected_files = {row[name]["path"]: row[name] for row in plan["cases"]
                      for name in ("problem", "certificate", "source", "bank", "reference_journal")
                      if row.get(name) is not None}
    require({entry["path"] for entry in files} == set(expected_files), "Transport selected-member inventory differs")
    for entry in files:
        actual = descriptor(root, entry)
        expected = expected_files[entry["path"]]
        require(sha(actual) == expected["sha256"], "Transport member differs from the sealed input plan")
        if expected["bytes"] is None:
            require(actual.stat().st_size <= expected["max_bytes"], "Resolved journal exceeds its sealed byte bound")
        else:
            require(actual.stat().st_size == expected["bytes"], "Resolved member size differs from its sealed input plan")
    require(transport.get("selected_file_bytes") == sum(entry["bytes"] for entry in files),
            "Selected transport byte accounting differs")
    return path, transport


def prepare(retained_root, out, authorization_id=None):
    protocol, authorization = guard_technical(authorization_id)
    started = time.perf_counter()
    plan_path = HERE / "retained_input_plan.json"
    plan = read_json(plan_path)
    rows = validate_plan(plan)
    retained_root, output = Path(retained_root), Path(out)
    require(not output.exists(), "Preserve completed or interrupted input preparation")
    transport_path, transport = authenticate_transport(retained_root, plan, authorization)
    # Resolve the entire inventory before creating any bank or output directory.
    sources = {}
    for case_id, row in rows.items():
        names = ["problem", "certificate"]
        if row.get("source") is not None:
            names.append("source")
        if row["mode"] == "compatibility":
            names += ["bank", "reference_journal"]
        sources[case_id] = {name: descriptor(retained_root, row[name]) for name in names}
    from studies.knapsack_parameters.population_validation_100.preparation import make_bank, validate_source
    from studies.knapsack_parameters.population_validation_100.common import read_json as load
    registry = load(HERE.parent / "initial_grid_100/data/source_registry.json")
    entries = {row["task_id"]: row for row in registry["historical_cases"]}
    output.mkdir(parents=True, exist_ok=False)
    budget = {"limit": protocol["limits"]["preparation_artifact_bytes"], "used": 0}
    require(transport_path.stat().st_size <= budget["limit"] - 128 * 1024,
            "Transport receipt exceeds the preparation artifact bound")
    with transport_path.open("rb") as incoming, (output / "transport_manifest.json").open("xb") as outgoing:
        for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
            outgoing.write(chunk)
            budget["used"] += len(chunk)
    cases = []
    for case_id, row in rows.items():
        paths = sources[case_id]
        problem, certificate = load(paths["problem"]), load(paths["certificate"])
        raw = None
        if "source" in paths:
            raw = paths["source"].read_bytes()
            require(row["task"] in entries and validate_source(raw, entries[row["task"]]) == problem,
                    "Retained task source and problem differ")
        validate_retained_certificate(problem, certificate, raw, require_input_hashes=row["mode"] == "pilot")
        folder = output / case_id
        folder.mkdir()
        copied = [("problem", "problem.json"), ("certificate", "certificate.json")]
        if "source" in paths:
            copied.append(("source", "source.kp"))
        for name, filename in copied:
            source = paths[name]
            require(budget["used"] + source.stat().st_size <= budget["limit"] - 128 * 1024,
                    "Prepared input artifact cap reached")
            with source.open("rb") as incoming, (folder / filename).open("xb") as outgoing:
                for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
                    outgoing.write(chunk)
                    budget["used"] += len(chunk)
        if row["mode"] == "pilot":
            bank = make_bank(problem, row["task_index"], row["seed"], row["preparation_seed"])
            _write_bounded(folder / "bank.json", bank, budget)
        else:
            # Copy authenticated bytes; never regenerate the compatibility bank.
            for name, filename in (("bank", "bank.json"), ("reference_journal", "reference_journal.json.gz")):
                source = paths[name]
                require(budget["used"] + source.stat().st_size <= budget["limit"] - 128 * 1024,
                        "Prepared retained evidence exceeds the input artifact cap")
                with source.open("rb") as incoming, (folder / filename).open("xb") as outgoing:
                    for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
                        outgoing.write(chunk)
                        budget["used"] += len(chunk)
            bank = load(folder / "bank.json")
        require(bank.get("task_index") == row["task_index"] and bank.get("search_seed") == row["seed"]
                and bank.get("preparation_seed") == row["preparation_seed"]
                and len(bank.get("masks", [])) == len(bank.get("scores", [])) == 30,
                "Registered bank identity differs")
        cases.append({key: value for key, value in row.items()
                      if key in {"case_id", "task", "task_index", "mode", "mu", "seed", "preparation_seed", "origin"}})
    files = [{"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}
             for path in sorted(output.rglob("*")) if path.is_file()]
    require(_used_bytes(output) == budget["used"], "Prepared artifact byte accounting differs")
    manifest = {"schema": "population13-technical-inputs-v1", "status": "SIX_CASES_AUTHENTICATED",
                "cases": cases, "files": files, "retained_input_plan_sha256": sha(plan_path),
                "source_manifest_sha256": authorization["source_manifest_sha256"],
                "transport_manifest_sha256": sha(transport_path),
                "remote_archive_bytes": transport["remote_archive_bytes"],
                "new_bank_count": 3, "retained_bank_count": 3,
                "physical_initial_score_checks": 90, "exact_solver_calls": 0, "ga_runs": 0,
                "certificate_witness_score_checks": 12,
                "preparation_seconds": time.perf_counter() - started}
    _write_bounded(output / "manifest.json", manifest, budget)
    require(_used_bytes(output) == budget["used"] <= budget["limit"], "Prepared artifact ceiling differs")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retained-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--authorization-id", required=True)
    args = parser.parse_args()
    prepare(args.retained_root, args.out, args.authorization_id)


if __name__ == "__main__":
    main()

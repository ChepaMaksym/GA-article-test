"""Run exactly one admitted full-budget technical identity, preserving evidence."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import time
import traceback

from .common import HERE, TOTAL, descriptor, guard_technical, validate_plan
from .search import make_log
from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha
from studies.knapsack_parameters.population_validation_100_main.runner import _used_bytes, _write_bounded


def comparable_log(log):
    """Ignore only measured execution time; retain every search and RNG field."""
    return {key: value for key, value in log.items() if key != "timing_ns"}


def check_accounting(log, mu, total=TOTAL):
    """Check total-budget and terminal partial-generation semantics explicitly."""
    summary = log["summary"]
    new = total - mu
    full, partial = divmod(new, mu - 1)
    require(log["budget"] == len(log["candidates"]) == summary["new_calls"] == new
            and summary["physical_evaluations"] == new
            and len(log["initial_masks"]) == summary["known_score_validation_evaluations"] == mu,
            "Total evaluation accounting differs")
    require(summary["full_generations"] == full and summary["partial_children"] == partial
            and len(log["generations"]) == full + int(partial > 0),
            "Complete and terminal partial generation accounting differs")
    if partial:
        last = log["generations"][-1]
        require(last["complete"] is False and last["controller_event"] == "PARTIAL_NO_UPDATE"
                and last["population_after"] == last["population_before"]
                and last["parameters_after"] == last["parameters_before"]
                and summary["final_population"] == last["population_before"],
                "A terminal partial block must retain the committed population and controller")
        require(last["record_after"] == summary["best_profit"],
                "Terminal partial children must remain eligible to update best-so-far")
    return {"initial_evaluations": mu, "new_evaluations": new, "total_evaluations": total,
            "completed_generations": full, "terminal_partial_children": partial}


def run_case(inputs, case_id, out, authorization_id=None):
    protocol, authorization = guard_technical(authorization_id)
    planned = validate_plan(read_json(HERE / "retained_input_plan.json"))
    require(case_id in planned, "Unregistered technical case")
    case = planned[case_id]
    inputs, output = Path(inputs), Path(out)
    require(not output.exists(), "Preserve completed or interrupted technical case evidence")
    started = time.perf_counter()
    manifest_path = inputs / "manifest.json"
    manifest = read_json(manifest_path)
    require(manifest.get("schema") == "population13-technical-inputs-v1"
            and manifest.get("status") == "SIX_CASES_AUTHENTICATED"
            and manifest.get("ga_runs") == 0 and manifest.get("new_bank_count") == 3
            and manifest.get("retained_bank_count") == 3
            and manifest.get("retained_input_plan_sha256") == sha(HERE / "retained_input_plan.json")
            and manifest.get("source_manifest_sha256") == authorization["source_manifest_sha256"],
            "Prepared six-case input provenance differs")
    rows = manifest.get("cases", [])
    require(len(rows) == 6 and {row.get("case_id") for row in rows} == set(planned),
            "Prepared technical inventory is incomplete or duplicated")
    matched = [row for row in rows if row["case_id"] == case_id]
    require(len(matched) == 1 and all(matched[0].get(key) == case[key]
            for key in ("task", "task_index", "mode", "mu", "seed", "preparation_seed")),
            "Prepared case identity differs from the pinned plan")
    inventory = manifest.get("files")
    require(type(inventory) is list and inventory, "Prepared file inventory is absent")
    require(all(type(row) is dict and type(row.get("bytes")) is int and row["bytes"] > 0 for row in inventory),
            "Prepared inputs must resolve every exact member byte length before search")
    require(len({row.get("path") for row in inventory}) == len(inventory), "Duplicate prepared file")
    paths = {row["path"]: descriptor(inputs, row) for row in inventory}
    folder = inputs / case_id
    required_names = {f"{case_id}/{name}" for name in ("problem.json", "certificate.json", "bank.json")}
    if case["mode"] == "compatibility":
        required_names.update({f"{case_id}/reference_journal.json.gz", f"{case_id}/source.kp"})
    require(required_names.issubset(paths), "Prepared case files are incomplete")
    require("transport_manifest.json" in paths
            and sha(inputs / "transport_manifest.json") == manifest.get("transport_manifest_sha256"),
            "Prepared archive authentication receipt is absent or changed")
    problem, bank = read_json(folder / "problem.json"), read_json(folder / "bank.json")
    require(bank.get("preparation_seed") == case["preparation_seed"], "Prepared bank seed differs")
    for name, filename in (("problem", "problem.json"), ("certificate", "certificate.json")):
        require(sha(folder / filename) == case[name]["sha256"], "Prepared task input differs from its sealed source: " + name)
    if case.get("source") is not None:
        require(sha(folder / "source.kp") == case["source"]["sha256"], "Prepared source bytes differ")
    # Recheck exact retained bank/reference hashes against the sealed source plan.
    if case["mode"] == "compatibility":
        require(sha(folder / "bank.json") == case["bank"]["sha256"]
                and sha(folder / "reference_journal.json.gz") == case["reference_journal"]["sha256"],
                "Prepared compatibility evidence differs from its original pinned bytes")
    input_seconds = time.perf_counter() - started
    output.mkdir(parents=True, exist_ok=False)
    budget = {"limit": protocol["limits"]["per_case_artifact_bytes"], "used": 0}
    try:
        from studies.knapsack_parameters.crossover_population.verification import verify_log
        from studies.knapsack_parameters.crossover_population.observations import extract
        mark = time.perf_counter()
        log = make_log(problem, bank, case["mu"], case["seed"], case["task_index"], TOTAL)
        search_seconds = time.perf_counter() - mark
        accounting = check_accounting(log, case["mu"])
        mark = time.perf_counter()
        _write_bounded(output / "journal.json.gz", log, budget)
        journal_write_seconds = time.perf_counter() - mark
        mark = time.perf_counter()
        verified = verify_log(log)
        verification_seconds = time.perf_counter() - mark
        require(verified["verification_status"] == "VERIFIED" and verified["new_calls"] == TOTAL - case["mu"],
                "Independent replay failed")
        bins = verified.pop("derived_metrics")["operator_bins"]
        _write_bounded(output / "verification.json", verified, budget)
        _write_bounded(output / "operator_bins.json", {"operator_bins": bins,
                       "premutation_score_checks": verified["premutation_score_checks"]}, budget)
        compatibility_seconds = 0.0
        if case["mode"] == "compatibility":
            mark = time.perf_counter()
            reference = read_json(folder / "reference_journal.json.gz")
            require(comparable_log(log) == comparable_log(reference),
                    "Complete historical journal comparison failed outside timing_ns")
            compatibility_seconds = time.perf_counter() - mark
            del reference
        # Oracle metadata enters only the postsearch observation layer.
        certificate = read_json(folder / "certificate.json")
        mark = time.perf_counter()
        observed = extract(log, TOTAL, certificate["optimum"], checkpoints=tuple(protocol["checkpoints"]))
        observations_seconds = time.perf_counter() - mark
        require(observed["final_best_profit"] == verified["record_profit"], "Postsearch observations differ from replay")
        _write_bounded(output / "observations.json.gz", observed, budget)
        names = ("journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz")
        receipt = {"schema": "population13-technical-case-v1", "status": "VERIFIED",
                   **{key: case[key] for key in ("case_id", "task", "task_index", "mode", "mu", "seed", "preparation_seed")},
                   **accounting, "pc_percentage": 90, "mutation_basis_points": 100,
                   "tournament_size": 2, "elite_count": 1,
                   "known_start_score_validation_checks": case["mu"],
                   "replay_score_checks": verified["independent_score_checks"],
                   "premutation_score_checks": verified["premutation_score_checks"],
                   "reference_journal_sha256": case.get("reference_journal", {}).get("sha256"),
                   "compatibility_scope": "complete_journal_except_timing_ns" if case["mode"] == "compatibility" else None,
                   "bank_sha256": sha(folder / "bank.json"), "certificate_sha256": sha(folder / "certificate.json"),
                   "inputs_manifest_sha256": sha(manifest_path),
                   "transport_manifest_sha256": manifest["transport_manifest_sha256"],
                   "retained_input_plan_sha256": sha(HERE / "retained_input_plan.json"),
                   "source_manifest_sha256": authorization["source_manifest_sha256"],
                   "artifact_hashes": {name: sha(output / name) for name in names},
                   "input_validation_seconds": input_seconds, "search_seconds": search_seconds,
                   "journal_write_seconds": journal_write_seconds, "verification_seconds": verification_seconds,
                   "compatibility_seconds": compatibility_seconds, "observations_seconds": observations_seconds,
                   "case_seconds_before_receipt": time.perf_counter() - started,
                   "artifact_bytes_before_receipt": _used_bytes(output),
                   "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
                   "authorization_id": authorization["authorization_id"], "main_ga_runs": 0}
        _write_bounded(output / "record.json", receipt, budget)
        require(_used_bytes(output) == budget["used"] <= budget["limit"], "Technical case artifact accounting differs")
        return receipt
    except Exception as error:
        _write_bounded(output / "failure.json", {"status": "FAILED_OR_INTERRUPTED", "case_id": case_id,
                       "error_type": type(error).__name__, "message": str(error)[:1000],
                       "traceback": traceback.format_exc(limit=8),
                       "elapsed_seconds": time.perf_counter() - started}, budget, emergency=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--authorization-id", required=True)
    args = parser.parse_args()
    run_case(args.inputs, args.case_id, args.out, args.authorization_id)


if __name__ == "__main__":
    main()

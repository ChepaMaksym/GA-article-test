"""Validate every technical receipt and estimate later, separately authorized stages."""
import argparse
import math
import os
from pathlib import Path

from .common import HERE, guard_stage, read_json, require, sha, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = guard_stage("technical")
    require(not args.out.exists(), "Preserve previous forecasts")
    rows, seen, input_seals = [], set(), set()
    for file in sorted(args.artifacts.rglob("technical.json")):
        block = read_json(file)
        require(block.get("schema") == "mutation-grid-100-technical-shard-v1"
                and block.get("status") == "VERIFIED"
                and block.get("workflow_run_id") == os.environ["GITHUB_RUN_ID"]
                and block.get("workflow_commit") == os.environ["GITHUB_SHA"]
                and block.get("source_manifest_sha256") == sha(HERE / "source_manifest.json")
                and block.get("new_tuning_runs") == block.get("new_validation_runs") == 0,
                "Technical block provenance or stage differs")
        input_seals.add(block["inputs_manifest_sha256"])
        for row in block["runs"]:
            identity = row["task"], row["mu"], row["mutation_basis_points"], row["seed"], row["mode"]
            require(identity not in seen and row["status"] == "VERIFIED"
                    and row["pc_percentage"] == 100 and row["total_evaluations"] == 100000
                    and row["initial_evaluations"] == row["mu"]
                    and row["new_evaluations"] == 100000 - row["mu"], "Technical case differs")
            seen.add(identity)
            root = file.parent / f'pm{row["mutation_basis_points"]}bp'
            require(set(row["artifact_hashes"]) == {
                "journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz"},
                "Technical artifact inventory differs")
            for name, digest in row["artifact_hashes"].items():
                require(sha(root / name) == digest, "Technical evidence hash differs")
            receipt = read_json(root / "record.json")
            require(all(receipt[key] == value for key, value in row.items()
                        if key not in {"case_seconds", "artifact_bytes"}), "Receipt and summary differ")
            require(row["case_seconds"] > 0 and row["artifact_bytes"] > 0, "Measured costs absent")
            rows.append(row)
    t = protocol["technical"]
    expected = {(task, mu, rate, t["seed"], "pilot") for task in t["tasks"]
                for mu in t["populations"] for rate in t["mutation_basis_points"]}
    expected |= {(task, mu, 100, t["compatibility_seed"], "compatibility")
                 for task in t["compatibility_tasks"] for mu in t["populations"]}
    require(seen == expected and len(rows) == 27 and len(input_seals) == 1,
            "All eighteen pilots and nine compatibility cases are required")
    measured = {mu: {"max_case_seconds": max(r["case_seconds"] for r in rows if r["mu"] == mu),
                     "max_artifact_bytes": max(r["artifact_bytes"] for r in rows if r["mu"] == mu)}
                for mu in (10, 15, 20)}
    reserve = 1.35

    def estimate(counts):
        total = sum(counts.values())
        return {"physical_runs": total,
                "runner_minutes_with_reserve": reserve * sum(counts[mu] * measured[mu]["max_case_seconds"]
                                                              for mu in counts) / 60 + math.ceil(total / 6) + 25,
                "artifact_bytes_with_reserve": math.ceil(reserve * sum(counts[mu] * measured[mu]["max_artifact_bytes"]
                                                                        for mu in counts)) + 256 * 1024**2,
                "assumed_cases_per_job": 6, "assumed_setup_upload_minutes_per_job": 1,
                "assumed_stage_preparation_analysis_minutes": 25}

    # A candidate may come from the retained grid and have population25.
    # Use the largest observed time/bytes as its provisional conservative proxy.
    measured[25] = {key: max(measured[mu][key] for mu in (10, 15, 20))
                    for key in ("max_case_seconds", "max_artifact_bytes")}
    scenarios = []
    for first in (10, 15, 20, 25):
        for second in (10, 15, 20, 25):
            counts = {10: 300, 15: 300, 20: 300, 25: 0}
            counts[first] += 300
            counts[second] += 300
            scenarios.append({"quality_population": first, "speed_population": second,
                              "assumes_five_distinct_configurations": True, **estimate(counts)})
    args.out.mkdir(parents=True)
    write_json(args.out / "forecast.json", {
        "schema": "mutation-grid-100-measured-forecast-v1",
        "status": "TECHNICAL_27_VERIFIED_MAIN_STAGES_NOT_AUTHORIZED",
        "technical_runs": 27, "measured_by_population": measured, "reserve_factor": reserve,
        "source_manifest_sha256": sha(HERE / "source_manifest.json"),
        "tuning": estimate({10: 450, 15: 450, 20: 450}), "validation_scenarios": scenarios,
        "limitations": ["Observed pilot maxima are forecasts, not runtime or precision guarantees.",
                        "Population25 cost uses the largest pilot maximum as a provisional proxy.",
                        "Validation must be recalculated after selection and configuration deduplication."],
        "new_tuning_runs": 0, "new_validation_runs": 0, "main_stages_authorized": False})
    print("All27 technical cases verified; measured main-stage forecasts saved.", flush=True)


if __name__ == "__main__":
    main()

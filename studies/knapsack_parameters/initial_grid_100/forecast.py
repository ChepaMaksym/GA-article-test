"""Measure technical costs and forecast separately authorized later stages."""
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
    require(not args.out.exists(), "Retain a previously recorded forecast")
    rows, case_ids = [], set()
    sources, inputs = set(), set()
    for file in sorted(args.artifacts.rglob("technical.json")):
        data = read_json(file)
        require(data.get("schema") == "initial-grid-100-technical-shard-v1"
                and data.get("status") == "VERIFIED"
                and data["workflow_run_id"] == os.environ["GITHUB_RUN_ID"]
                and data["workflow_commit"] == os.environ["GITHUB_SHA"], "Technical source or workflow differs")
        sources.add(data["source_manifest_sha256"])
        inputs.add(data["inputs_manifest_sha256"])
        require(data["new_tuning_runs"] == data["new_validation_runs"] == 0,
                "Technical records must exclude new main searches")
        for row in data["runs"]:
            identity = row["task"], row["mu"], row["pc_percentage"], row["seed"], row["mode"]
            require(identity not in case_ids and row["status"] == "VERIFIED"
                    and row["total_evaluations"] == 100000
                    and row["initial_evaluations"] + row["new_evaluations"] == 100000,
                    "Duplicated, incomplete or miscounted technical case")
            case_ids.add(identity)
            root = file.parent / ("pc" + str(row["pc_percentage"]))
            for name, digest in row["artifact_hashes"].items():
                require(name in {"journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz"}
                        and sha(root / name) == digest, "Technical evidence digest differs")
            saved = read_json(root / "record.json")
            require(all(saved[key] == value for key, value in row.items()
                        if key not in {"case_seconds", "artifact_bytes"}), "Technical record differs from its summary")
            require(row["case_seconds"] > 0 and row["artifact_bytes"] > 0, "Missing measured cost")
            rows.append(row)
    tasks = protocol["technical"]["cases"]
    expected = {(task, mu, pc, 159999, "pilot") for task in tasks for mu in (15, 25) for pc in (70, 100)}
    expected |= {(task, mu, 90, 149999, "compatibility") for task in tasks for mu in (10, 20)}
    require(case_ids == expected and len(rows) == 18 and len(inputs) == 1
            and sources == {sha(HERE / "source_manifest.json")}, "The exact eighteen-case technical plan is incomplete")
    # Use a conservative observed maximum per population. Crossover combinations
    # not sampled in the pilot inherit that population's maximum measured cost.
    measured = {mu: {"max_case_seconds": max(r["case_seconds"] for r in rows if r["mu"] == mu),
                     "max_artifact_bytes": max(r["artifact_bytes"] for r in rows if r["mu"] == mu)}
                for mu in (10, 15, 20, 25)}
    tuning_counts = {10: 270, 15: 360, 20: 270, 25: 360}
    reserve = 1.35
    def estimate(counts):
        total = sum(counts.values())
        jobs = math.ceil(total / 6)
        return {"physical_runs": total,
                "runner_minutes_with_reserve": reserve * sum(counts[mu] * measured[mu]["max_case_seconds"] for mu in counts) / 60 + jobs + 20,
                "artifact_bytes_with_reserve": math.ceil(reserve * sum(counts[mu] * measured[mu]["max_artifact_bytes"] for mu in counts)) + 128 * 1024**2,
                "assumed_cases_per_job": 6, "assumed_setup_upload_minutes_per_job": 1,
                "assumed_stage_preparation_analysis_minutes": 20}
    validations = []
    for winner_mu in (10, 15, 20, 25):
        counts = {mu: 0 for mu in (10, 15, 20, 25)}
        counts[10] += 300
        counts[20] += 300
        counts[winner_mu] += 300
        validations.append({"selected_population_scenario": winner_mu,
                            "assumes_distinct_selected_pair": True, **estimate(counts)})
    args.out.mkdir(parents=True)
    write_json(args.out / "forecast.json", {"schema": "initial-grid-100-measured-forecast-v1",
               "status": "TECHNICAL_18_VERIFIED_MAIN_STAGES_NOT_AUTHORIZED", "technical_runs": 18,
               "source_manifest_sha256": sha(HERE / "source_manifest.json"), "measured_by_population": measured,
               "reserve_factor": reserve, "tuning": estimate(tuning_counts),
               "validation_scenarios": validations,
               "limitations": ["Observed maxima from three old tasks are not guarantees for all new tasks.",
                                "Setup/upload allowances are planning assumptions, not operator timings.",
                                "Validation must be recalculated after the pair is selected and deduplicated."],
               "main_stages_authorized": False, "new_tuning_runs": 0, "new_validation_runs": 0})
    print("Verified eighteen technical cases and forecast later stages; no main stage started.", flush=True)


if __name__ == "__main__":
    main()

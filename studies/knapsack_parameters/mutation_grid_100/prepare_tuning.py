"""Authenticate technical-stage inputs and register only missing mutation cases."""
import argparse
import json
import os
from pathlib import Path
import shutil

from .analysis import OLD_CONFIGS, MUTATION_CONFIGS, normalize_retained, validate_union
from .common import HERE, guard_stage, read_json, require, sha, write_json
from studies.knapsack_parameters.population_validation_100_main.runner import _verify_files, _used_bytes


def build_schedule(tasks):
    cases = []
    for task in sorted(tasks, key=lambda t: t["task_index"]):
        for seed in (150001, 150002, 150003):
            for mu in (10, 15, 20):
                for rate in (25, 50, 75, 150, 200):
                    cases.append({"task": task["task"], "task_index": task["task_index"],
                                  "family": task["family"], "class_label": task["class_label"],
                                  "seed": seed, "mu": mu, "pc_percentage": 100,
                                  "mutation_basis_points": rate})
    require(len(tasks) == 30 and len(cases) == 1350, "Mutation schedule count differs")
    identities = {(r["task"], r["seed"], r["mu"], r["pc_percentage"], r["mutation_basis_points"]) for r in cases}
    require(len(identities) == len(cases), "Duplicated mutation identity")
    return [{"shard_id": f"{i // 6:03d}", "cases": cases[i:i + 6]} for i in range(0, len(cases), 6)]


def prepare(inputs, out):
    guard_stage("tuning")
    inputs, out = Path(inputs), Path(out)
    require(not out.exists(), "Preserve prior or partial stage preparation")
    require(sha(inputs / "manifest.json") == "502886cc9b2ccbea5de2002d7f7182cd994c070604bfea3062dae3e79540d8c9",
            "Technical input manifest differs from verified run 42988256361")
    manifest = read_json(inputs / "manifest.json")
    require(manifest.get("schema") == "mutation-grid-100-technical-inputs-v1"
            and manifest.get("status") == "TECHNICAL_INPUTS_PREPARED"
            and manifest.get("retained_grid_count") == 1440
            and manifest.get("reused_mutation_count") == 270
            and manifest.get("validation_ga_runs") == 0 and manifest.get("exact_solvers_rerun") is False,
            "Technical source manifest differs")
    _verify_files(inputs, manifest["files"])
    retained = read_json(inputs / "retained_grid.json.gz")
    require(retained.get("status") == "VERIFIED_1440_RETAINED" and len(retained.get("runs", [])) == 1440,
            "Retained 1440-case grid is absent")
    rows = [normalize_retained(row) for row in retained["runs"]]
    reused = read_json(inputs / "reused_mutation.json.gz")
    require(reused.get("status") == "VERIFIED_270_RETAINED" and len(reused.get("runs", [])) == 270,
            "Retained 270-case mutation overlap is absent")
    identity = lambda row: (row["task"], row["seed"], row["mu"], row["pc_percentage"], row["mutation_basis_points"])
    retained_by_id = {identity(row): row for row in rows}
    require(len(retained_by_id) == 1440 and {identity(row) for row in reused["runs"]} ==
            {identity(row) for row in rows if (row["mu"], row["pc_percentage"]) in ((10, 100), (15, 100), (20, 100))}
            and all(retained_by_id[identity(row)] == row for row in reused["runs"]),
            "Retained overlap differs from the authenticated grid")
    original = inputs / "source/tuning/prepared"
    prepared = read_json(original / "manifest.json")
    require(prepared.get("schema") == "population-validation-100-main-inputs-v1"
            and prepared.get("status") == "PAIRED_BANKS_PREPARED" and prepared.get("main_ga_runs") == 0,
            "Paired initial-bank source differs")
    _verify_files(original, prepared["files"])
    tasks = prepared["tasks"]
    expected = {f"n00100-{kind}-s{family:03d}" for family in range(50, 60) for kind in ("UC", "WC", "SC")}
    require(len(tasks) == 30 and {task["task"] for task in tasks} == expected,
            "Tuning task identities differ")
    shards = build_schedule(tasks)
    out.mkdir(parents=True)
    shutil.copytree(original, out / "prepared", symlinks=False)
    _verify_files(out / "prepared", prepared["files"])
    write_json(out / "retained_grid.json.gz", {"schema": "mutation-grid-100-retained-grid-v1",
               "status": "VERIFIED_1440_RETAINED", "runs": rows,
               "technical_manifest_sha256": sha(inputs / "manifest.json")})
    write_json(out / "schedule.json", {"schema": "mutation-grid-100-schedule-v1", "physical_runs": 1350,
               "shards": shards})
    require(len(shards) == 225 and _used_bytes(out) <= 256 * 1024**2,
            "Tuning preparation exceeds its planned count or byte cap")
    write_json(out / "stage_manifest.json", {"schema": "mutation-grid-100-tuning-inputs-v1",
               "status": "STAGE_INPUTS_PREPARED", "stage": "tuning", "new_case_count": 1350,
               "retained_count": 1440, "overlap_count": 270,
               "technical_manifest_sha256": sha(inputs / "manifest.json"),
               "prepared_manifest_sha256": sha(out / "prepared/manifest.json"),
               "retained_grid_sha256": sha(out / "retained_grid.json.gz"),
               "schedule_sha256": sha(out / "schedule.json"),
               "source_manifest_sha256": sha(HERE / "source_manifest.json"),
               "independent_validation_started": False})
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("shards=" + json.dumps([block["shard_id"] for block in shards], separators=(",", ":")) + "\n")
    print("Registered 1350 missing identities and authenticated 1440 retained cases.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.inputs, args.out)


if __name__ == "__main__":
    main()

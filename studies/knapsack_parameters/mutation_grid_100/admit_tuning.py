"""Admit verified case receipts and freeze the two descriptive recommendations."""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

from .analysis import identity, validate_row, validate_union, export_tuning
from .common import HERE, guard_stage, read_json, require, sha
from studies.knapsack_parameters.population_validation_100_main.runner import _verify_files


def artifact_inventory(run_id, token):
    """Pin uploaded raw archive metadata; never download or print signed URLs."""
    require(type(run_id) is str and run_id.isdigit() and bool(token), "Workflow identity or token absent")
    result, page = {}, 1
    while True:
        url = (f"https://api.github.com/repos/ChepaMaksym/GA-article-test/actions/runs/{run_id}"
               f"/artifacts?per_page=100&page={page}")
        headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                   "User-Agent": "mutation-grid-100-analysis"}
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            data = json.load(response)
        artifacts = data["artifacts"]
        for entry in artifacts:
            name = entry["name"]
            if name.startswith("mutation-grid100-tuning-raw-"):
                require(name not in result and entry.get("expired") is False
                        and entry.get("workflow_run", {}).get("id") == int(run_id)
                        and re.fullmatch(r"sha256:[0-9a-f]{64}", entry.get("digest", ""))
                        and type(entry.get("size_in_bytes")) is int and entry["size_in_bytes"] > 0,
                        "Raw archive metadata is missing, duplicated or expired")
                result[name] = {"id": entry["id"], "sha256": entry["digest"][7:],
                                "bytes": entry["size_in_bytes"]}
        if page * 100 >= data["total_count"]:
            return result
        page += 1


def collect(inputs, blocks, archives):
    inputs, blocks = Path(inputs), Path(blocks)
    stage = read_json(inputs / "stage_manifest.json")
    require(stage.get("schema") == "mutation-grid-100-tuning-inputs-v1"
            and stage.get("status") == "STAGE_INPUTS_PREPARED" and stage.get("new_case_count") == 1350
            and stage.get("retained_count") == 1440 and stage.get("overlap_count") == 270,
            "Prepared tuning inputs differ")
    for path, key in (("schedule.json", "schedule_sha256"), ("retained_grid.json.gz", "retained_grid_sha256"),
                      ("prepared/manifest.json", "prepared_manifest_sha256")):
        require(sha(inputs / path) == stage[key], "Prepared tuning input hash differs")
    source_sha = sha(HERE / "source_manifest.json")
    require(stage.get("source_manifest_sha256") == source_sha, "Prepared source seal differs")
    prepared = read_json(inputs / "prepared/manifest.json")
    _verify_files(inputs / "prepared", prepared["files"])
    tasks = {task["task"]: task for task in prepared["tasks"]}
    schedule = read_json(inputs / "schedule.json")
    expected_blocks = {block["shard_id"]: block["cases"] for block in schedule["shards"]}
    require(len(expected_blocks) == 225 and schedule.get("physical_runs") == 1350,
            "Registered mutation block inventory differs")
    shards = sorted(blocks.rglob("shard.json"))
    require(len(shards) == 225, "All 225 complete block receipts are required")
    rows, provenance, seen_blocks = [], [], set()
    for file in shards:
        require(not file.is_symlink() and file.resolve().is_relative_to(blocks.resolve()), "Unsafe block path")
        block = read_json(file)
        block_id = block.get("shard_id")
        raw_name = f'mutation-grid100-tuning-raw-{block_id}-{os.environ["GITHUB_RUN_ID"]}'
        require(block.get("schema") == "mutation-grid-100-tuning-shard-v1" and block.get("status") == "VERIFIED"
                and block_id in expected_blocks and block_id not in seen_blocks
                and block.get("workflow_run_id") == os.environ["GITHUB_RUN_ID"]
                and block.get("workflow_commit") == os.environ["GITHUB_SHA"]
                and block.get("stage_manifest_sha256") == sha(inputs / "stage_manifest.json")
                and block.get("source_manifest_sha256") == source_sha
                and block.get("raw_artifact_name") == raw_name and raw_name in archives,
                "Block provenance differs or the raw archive is absent")
        seen_blocks.add(block_id)
        block_rows = block.get("runs")
        expected = {identity(case) for case in expected_blocks[block_id]}
        require(type(block_rows) is list and len(block_rows) == 6
                and {identity(row) for row in block_rows} == expected, "Block identity inventory differs")
        receipts = sorted((file.parent / "records").glob("*.json"))
        require(len(receipts) == 6 and {identity(read_json(p)): read_json(p) for p in receipts} ==
                {identity(row): row for row in block_rows}, "Per-case receipts differ from the completed block")
        for row in block_rows:
            validate_row(row)
            task = tasks[row["task"]]
            bank = next(item for item in task["banks"] if item["seed"] == row["seed"])
            require(row["task_index"] == task["task_index"] and row["bank_sha256"] == bank["sha256"]
                    and row["certificate_sha256"] == task["certificate_sha256"]
                    and row["optimum"] == read_json(inputs / "prepared" / row["task"] / "certificate.json")["optimum"],
                    "A new case differs from its paired bank or exact reference")
            rows.append(row)
        provenance.append({"shard_id": block_id, "compact_sha256": sha(file),
                           "raw_artifact_name": raw_name, **archives[raw_name]})
    require(seen_blocks == set(expected_blocks) and len(rows) == 1350 and len(archives) == 225,
            "New results or raw archive metadata are incomplete")
    retained = read_json(inputs / "retained_grid.json.gz")
    require(retained.get("status") == "VERIFIED_1440_RETAINED" and len(retained.get("runs", [])) == 1440,
            "Retained grid differs")
    rows.extend(retained["runs"])
    validate_union(rows)
    rows.sort(key=identity)
    ledger = {"status": "ALL_CASES_INDEPENDENTLY_VERIFIED", "new_cases": 1350,
              "retained_cases": 1440, "raw_archives": provenance,
              "retained_artifact_sha256": "4de51008ac16a045475183af019fe309adb1b19fa9e9659887ccc734f77ecbb0",
              "technical_manifest_sha256": stage["technical_manifest_sha256"],
              "stage_manifest_sha256": sha(inputs / "stage_manifest.json"),
              "source_manifest_sha256": source_sha,
              "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"]}
    return rows, ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--blocks", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    guard_stage("tuning")
    inventory = artifact_inventory(os.environ["GITHUB_RUN_ID"], os.environ.get("GH_TOKEN", ""))
    rows, provenance = collect(args.inputs, args.blocks, inventory)
    export_tuning(rows, args.out, provenance)
    print("Admitted all 2790 verified results and froze quality and speed selections.", flush=True)


if __name__ == "__main__":
    main()

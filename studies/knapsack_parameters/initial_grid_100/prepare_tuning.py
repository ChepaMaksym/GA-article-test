"""Authenticate retained starts and register the 1260 missing tuning cases."""
import argparse
import json
from pathlib import Path

from .common import HERE, guard_checks, guard_stage, read_json, require, sha, write_json
from studies.knapsack_parameters.population_size_study.io_utils import extract_artifact
from studies.knapsack_parameters.population_validation_100_main.runner import _used_bytes, _verify_files
from studies.knapsack_parameters.population_validation_100_main.analysis import validate_row

ORIGINAL_COMMIT = "653b7a3f9c5e66d31ec8ca93fb4e710bd0078ff8"
ORIGINAL_SEAL = "ce799ba032c1178a988e8a608daaf1b44ee074c47e9e88f10671924e3565798a"


def tuning_schedule(tasks):
    """Generate only cases that are absent from the two retained configurations."""
    cases = []
    for task in sorted(tasks, key=lambda row: row["task_index"]):
        for seed in (150001, 150002, 150003):
            for mu in (10, 15, 20, 25):
                for pc in (70, 80, 90, 100):
                    if (mu, pc) in ((10, 90), (20, 90)):
                        continue
                    cases.append({"task": task["task"], "task_index": task["task_index"],
                                  "family": task["family"], "class_label": task["class_label"],
                                  "seed": seed, "mu": mu, "pc_percentage": pc})
    require(len(tasks) == 30 and len(cases) == 1260, "Registered tuning schedule differs")
    identities = {(c["task"], c["seed"], c["mu"], c["pc_percentage"]) for c in cases}
    require(len(identities) == 1260, "Duplicate tuning identity")
    return [{"shard_id": f"{index // 6:03d}", "cases": cases[index:index + 6]}
            for index in range(0, len(cases), 6)]


def prepare(out, retained, *, audit_only=False):
    protocol = guard_checks() if audit_only else guard_stage("tuning")
    out, retained = Path(out), Path(retained)
    require(not out.exists(), "Preserve a prior or partial tuning preparation")
    registry = HERE / "data/retained_tuning_registry.json"
    require(sha(retained / "origin.json") == sha(registry), "Retained source registry differs")
    out.mkdir(parents=True)
    origin = read_json(retained / "origin.json")
    require(origin.get("schema") == "initial-grid-100-retained-tuning-v1"
            and origin.get("original_run_id") == 42813784277
            and origin.get("original_commit") == ORIGINAL_COMMIT
            and origin.get("original_code_manifest_sha256") == ORIGINAL_SEAL,
            "Retained experiment provenance differs")
    descriptors = origin["archives"]
    names = {p.relative_to(retained).as_posix() for p in retained.rglob("*") if p.is_file()}
    require(len(descriptors) == 21 and {r["path"] for r in descriptors} == names - {"origin.json"},
            "Retained archive registry differs")
    for entry in descriptors:
        relative = entry["path"]
        require(type(relative) is str and "\\" not in relative and ":" not in relative
                and not Path(relative).is_absolute() and ".." not in Path(relative).parts, "Unsafe retained path")
        archive = (retained / relative).resolve()
        require(archive.is_relative_to(retained.resolve()) and archive.is_file()
                and archive.stat().st_size == entry["bytes"] and sha(archive) == entry["sha256"],
                "Retained inner artifact digest differs")
        if relative == "prepared.zip":
            extract_artifact(archive, out / "prepared", compressed_limit=2 * 1024**2, expanded_limit=32 * 1024**2)
        else:
            name = Path(relative).name.removesuffix(".zip")
            extract_artifact(archive, out / "retained" / name, compressed_limit=1024**2, expanded_limit=8 * 1024**2)
    prepared = out / "prepared"
    manifest = read_json(prepared / "manifest.json")
    require(manifest.get("schema") == "population-validation-100-main-inputs-v1"
            and manifest.get("status") == "PAIRED_BANKS_PREPARED" and manifest.get("main_ga_runs") == 0
            and manifest.get("source_commit") == protocol["source_commit"] and manifest.get("bank_count") == 300,
            "Original paired-bank manifest differs")
    _verify_files(prepared, manifest["files"])
    tasks = manifest["tasks"]
    expected_tasks = {f"n00100-{kind}-s{family:03d}" for family in range(50, 60) for kind in ("UC", "WC", "SC")}
    require(len(tasks) == 30 and {r["task"] for r in tasks} == expected_tasks,
            "Retained task inventory differs")
    for task in tasks:
        expected_index = 3 + (int(task["family"][1:]) - 50) * 3 + ("UC", "WC", "SC").index(task["class_label"])
        require(task["task_index"] == expected_index and task["task"] == f'n00100-{task["class_label"]}-{task["family"]}',
                "Retained task index or identity differs")
    by_task = {r["task"]: r for r in tasks}
    records, seen, provenance = [], set(), []
    for entry in descriptors:
        if entry["path"] == "prepared.zip":
            continue
        root = out / "retained" / Path(entry["path"]).name.removesuffix(".zip")
        pieces = entry["name"].split("-")
        family, mu = pieces[-3], int(pieces[-2].removeprefix("mu"))
        require(family in protocol["tuning"]["families"] and mu in (10, 20), "Retained profile differs")
        selected = []
        for f in sorted((root / "records").rglob("seed-*.json")):
            row = read_json(f)
            if row["seed"] not in (150001, 150002, 150003):
                continue
            validate_row(row, family, mu)
            task = by_task[row["task"]]
            bank = next(b for b in task["banks"] if b["seed"] == row["seed"])
            require(row["task_index"] == task["task_index"] and row["bank_sha256"] == bank["sha256"]
                    and row["certificate_sha256"] == task["certificate_sha256"]
                    and row["optimum"] == read_json(prepared / row["task"] / "certificate.json")["optimum"],
                    "Retained record and paired source differ")
            identity = row["task"], row["seed"], mu, 90
            require(identity not in seen, "Retained case is duplicated")
            seen.add(identity)
            item = dict(row)
            item["pc_percentage"] = 90
            item["reuse_origin"] = {"artifact_id": entry["id"], "artifact_sha256": entry["sha256"],
                                    "original_run_id": 42813784277, "original_commit": ORIGINAL_COMMIT,
                                    "original_source_manifest_sha256": ORIGINAL_SEAL}
            selected.append(item)
        require(len(selected) == 9, "Each retained family/profile requires three tasks and three repeats")
        records.extend(selected)
        provenance.append({"artifact_name": entry["name"], "artifact_id": entry["id"], "sha256": entry["sha256"],
                           "selected_cases": len(selected)})
    require(len(records) == len(seen) == 180 and len(provenance) == 20, "Exactly 180 retained cases are required")
    records.sort(key=lambda r: (r["task_index"], r["seed"], r["mu"]))
    write_json(out / "reused.json", {"schema": "initial-grid-100-reused-v1", "status": "VERIFIED_180_RETAINED",
               "runs": records, "provenance": provenance, "original_run_id": 42813784277})
    shards = tuning_schedule(tasks)
    require(len(shards) == 210 and all(len(s["cases"]) == 6 for s in shards), "Tuning blocks differ")
    write_json(out / "schedule.json", {"schema": "initial-grid-100-schedule-v1", "stage": "tuning",
               "physical_runs": 1260, "shards": shards})
    write_json(out / "stage_manifest.json", {"schema": "initial-grid-100-stage-inputs-v1",
               "status": "AUDIT_ONLY_NO_SEARCH_AUTHORIZED" if audit_only else "STAGE_INPUTS_PREPARED",
               "stage": "tuning", "tasks": tasks,
               "prepared_manifest_sha256": sha(prepared / "manifest.json"),
               "schedule_sha256": sha(out / "schedule.json"), "reused_sha256": sha(out / "reused.json"),
               "retained_registry_sha256": sha(registry), "retained_count": 180, "new_case_count": 1260,
               "original_run_id": 42813784277, "original_commit": ORIGINAL_COMMIT})
    require(_used_bytes(out) <= 536870912, "Prepared input artifact exceeds its reserved cap")
    output = __import__("os").environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write("shards=" + json.dumps([s["shard_id"] for s in shards], separators=(",", ":")) + "\n")
    print("Authenticated 180 retained cases and froze 1260 missing identities in 210 blocks.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--retained", type=Path, required=True)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    prepare(args.out, args.retained, audit_only=args.audit_only)


if __name__ == "__main__":
    main()

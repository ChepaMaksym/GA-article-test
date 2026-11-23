"""Measure four registered old cases and verify replay against frozen tuning records."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from math import ceil
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from zipfile import ZipFile

from studies.knapsack_parameters.iterative_validation_population13.transport import download_archive
from studies.knapsack_parameters.mutation_grid_100.program.ga_core import (
    create_random_generators, parameter_controller, run_ga,
)
from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha, write_json

from .common import guard
from .runner import PROFILES, TOTAL, _expected_parameters, execute_case, identity


SOURCE = Path(__file__).resolve().parents[1] / "iterative_validation/data/validated_records.json.gz"
SOURCE_HASH = "70adbcca7b27e645f8a01b7f8662358d62c347bf02a4edb825996ebf62a1af32"
MANIFEST_HASH = "f29b9c33def8e74adbf13aeabda1d6851ca3d64258468640ceba6968f3e4d96d"
PREPARED = {"id": 13762967913, "name": "population100-main-prepared-42813784277",
            "bytes": 574487, "sha256": "ff19ca444ea38399bd30d913f18e6e56affa358f5a293bb84ddfb906092e75e7",
            "run_id": 42813784277, "commit": "653b7a3f9c5e66d31ec8ca93fb4e710bd0078ff8"}
OLD_CASES = (("UC", 3, 10, 90), ("WC", 4, 15, 90), ("UC", 3, 15, 100), ("SC", 5, 20, 90))
COMPARE = ("task", "family", "class_label", "task_index", "seed", "mu", "pc_percentage",
           "mutation_basis_points", "best", "optimum", "events", "checkpoints", "targets",
           "duplicates", "completed_generations", "certificate_sha256", "bank_sha256")


def old_log(problem, bank, profile, seed, task_index, total):
    require(profile in PROFILES and seed == 150001 and bank["search_seed"] == seed
            and bank["task_index"] == task_index and bank["preparation_seed"] == 150000
            and total == TOTAL and problem.get("n") == 100
            and set(problem) == {"n", "weights", "profits", "capacity"},
            "Benchmark task, retained start or configuration differs")
    mu, pc, bp = profile
    generators = create_random_generators(seed, task_index, 0)
    require(bank["rng_states"] == {name: deepcopy(r.bit_generator.state) for name, r in generators.items()},
            "Old initial RNG states differ")
    return run_ga(problem, {"masks": bank["masks"][:mu], "scores": bank["scores"][:mu]},
                  parameter_controller(0), generators, budget=total-mu,
                  initial_parameters=_expected_parameters({"mu": mu, "pc_percentage": pc,
                                                          "mutation_basis_points": bp}),
                  configuration_contract="fixed-mutation-grid-v1")


def forecast(timings):
    require(len(timings) == 4 and all(row["case_seconds"] > 0 and row["artifact_bytes"] > 0 for row in timings),
            "Four measured old cases are required")
    slowest = max(row["case_seconds"] for row in timings)
    largest = max(row["artifact_bytes"] for row in timings)
    return {"physical_main_runs": 1200, "slowest_case_seconds": slowest, "largest_case_bytes": largest,
            "runner_minutes_with_reserve": ceil(slowest*1200*1.5/60) + 200 + 30,
            "artifact_bytes_with_reserve": ceil(largest*1200*1.40) + 256*1024**2,
            "time_basis": "slowest old case x 1200 x 1.5, plus one minute per shard and 30 setup/analysis minutes",
            "size_basis": "largest raw case x 1200 x 1.4, plus 256 MiB for compact inputs, indices and analysis",
            "independent_runs_started": 0}


def run_benchmark(out, archived=None):
    _, auth = guard("benchmark")
    out = Path(out)
    require(not out.exists(), "Preserve previous benchmark evidence")
    require(sha(SOURCE) == SOURCE_HASH, "Frozen tuning archive differs")
    records = read_json(SOURCE)["runs"]
    require(len(records) == 2790, "Wrong old tuning population")
    out.mkdir(parents=True)
    budget = {"limit": 90*1024**2, "used": 0}
    results = []
    origin = {"workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
              "authorization_id": auth["authorization_id"], "source_manifest_sha256": auth["source_manifest_sha256"],
              "inputs_manifest_sha256": MANIFEST_HASH}
    with TemporaryDirectory() as temp:
        path = Path(archived) if archived else Path(temp) / "prepared.zip"
        if not archived:
            download_archive(PREPARED, os.environ["GITHUB_TOKEN"], path)
        require(path.stat().st_size == PREPARED["bytes"] and sha(path) == PREPARED["sha256"],
                "Benchmark inputs differ from the pinned original ZIP")
        with ZipFile(path) as archive:
            raw_manifest = archive.read("manifest.json")
            require(sha256(raw_manifest).hexdigest() == MANIFEST_HASH, "Benchmark manifest differs")
            files = {row["path"]:row for row in json.loads(raw_manifest)["files"]}
            for kind, task_index, mu, pc in OLD_CASES:
                task = f"n00100-{kind}-s050"
                case = {"task":task, "task_index":task_index, "family":"s050", "class_label":kind,
                        "mu":mu, "pc_percentage":pc, "mutation_basis_points":100, "seed":150001}
                case["case_id"] = identity(case)
                matches = [r for r in records if all(r[k] == case[k] for k in
                           ("task","task_index","mu","pc_percentage","mutation_basis_points","seed"))]
                require(len(matches) == 1, "Expected one pinned historical reference")
                names = {"problem":"problem.json", "certificate":"certificate.json", "source":"source.kp",
                         "bank":"banks/seed-150001.json"}
                items, descriptors = {}, {}
                for role, name in names.items():
                    key = task + "/" + name
                    raw, desc = archive.read(key), files[key]
                    require(len(raw) == desc["bytes"] and sha256(raw).hexdigest() == desc["sha256"],
                            "Benchmark input checksum differs")
                    descriptors[role] = desc
                    if role != "source":
                        items[role] = json.loads(raw)
                started = time.perf_counter()
                row = execute_case(case, items["problem"], items["bank"], items["certificate"], descriptors,
                                   origin, out/"raw", out/"compact", budget, search=old_log, phase="tuning")
                require(all(row[k] == matches[0][k] for k in COMPARE),
                        "Independent replay output differs from measured historical outcomes")
                results.append({"case_id":case["case_id"], "case_seconds":time.perf_counter()-started,
                                "artifact_bytes":row["timing"]["artifact_bytes"],
                                "status":"HISTORICAL_NUMERICAL_MATCH_AND_REPLAY_VERIFIED"})
    report = {"schema":"independent-validation100-benchmark-v1", "status":"FOUR_OLD_CASES_VERIFIED",
              "compared_fields": list(COMPARE), "historical_records_sha256":SOURCE_HASH, **origin,
              "cases": results, "forecast":forecast(results), "holdout_search_runs":0}
    write_json(out/"benchmark.json",report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--prepared-zip", type=Path)
    args = parser.parse_args()
    print(json.dumps(run_benchmark(args.out, args.prepared_zip)["forecast"]))

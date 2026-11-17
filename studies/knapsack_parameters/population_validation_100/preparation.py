"""Prepare shared banks and audit pinned source bytes outside the search core."""
import argparse
import base64
from copy import deepcopy
from hashlib import sha1, sha256
from pathlib import Path
import re
import time
from urllib.request import urlopen

import numpy as np

from .common import HERE, REPOSITORY, guard_technical, read_json, require, require_ci, sha, write_json
from studies.knapsack_parameters.population_size_study.inputs import (
    parse_kp_bytes, problem_sha256, unordered_problem_sha256,
)


def score(problem, mask):
    require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"}, "Invalid initial mask")
    weight = sum(w for w, bit in zip(problem["weights"], mask) if bit == "1")
    profit = sum(p for p, bit in zip(problem["profits"], mask) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def validate_source(raw, entry):
    require_ci()
    require(re.fullmatch(r"(?:00Uncorrelated|01WeaklyCorrelated|02StronglyCorrelated)/n00100/R01000/s[0-9]{3}\.kp",
                         entry.get("source_path", "")) is not None, "Source path must identify a registered 100-item problem")
    length = entry.get("bytes", entry.get("source_bytes"))
    require(type(raw) is bytes and len(raw) == length, "Pinned source length differs")
    require(sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest() == entry["git_blob_sha1"],
            "Pinned Git blob differs")
    if entry.get("source_sha256") is not None:
        require(sha256(raw).hexdigest() == entry["source_sha256"], "Pinned SHA-256 differs")
    return parse_kp_bytes(raw, 100)


def make_bank(problem, task_index, seed, preparation_seed):
    require_ci()
    require(problem["n"] == 100, "This study only admits 100-item instances")
    require(all(type(value) is int and value >= 0 for value in (task_index, seed, preparation_seed)), "Invalid bank identity")
    from studies.knapsack_parameters.crossover_population.program.ga_core import create_random_generators
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence([preparation_seed, task_index, seed])))
    masks = ["0" * 100] + ["".join(str(int(bit)) for bit in generator.integers(0, 2, 100)) for _ in range(29)]
    rngs = create_random_generators(seed, task_index, 0)
    return {"masks": masks, "scores": [score(problem, mask) for mask in masks],
            "rng_states": {name: deepcopy(rng.bit_generator.state) for name, rng in rngs.items()},
            "task_index": task_index, "search_seed": seed, "preparation_seed": preparation_seed,
            "preparation_rng_final": deepcopy(generator.bit_generator.state), "physical_initial_score_checks": 30}


def _fetch(entry, registry):
    source_path = entry["source_path"]
    parts = Path(source_path).parts
    require(".." not in parts and not source_path.startswith(("/", "\\")) and ":" not in source_path,
            "Unsafe source path")
    url = registry["source_base_url"] + source_path
    prefix = "https://raw.githubusercontent.com/likr/kplib/" + registry["source_commit"] + "/"
    require(url.startswith(prefix), "Unpinned source URL")
    with urlopen(url, timeout=30) as response:
        require(response.geturl().startswith(prefix), "Source redirected outside the pinned revision")
        raw = response.read(entry.get("bytes", entry.get("source_bytes")) + 1)
    return raw


def prepare(out):
    """Audit inputs only; this command cannot invoke run_ga."""
    protocol = guard_technical()
    registry = read_json(HERE / "data" / "source_registry.json")
    require(registry["source_commit"] == protocol["source_commit"], "Source revision differs")
    main = registry["main_cases"]
    require(len(main) == 30 and len({r["task_id"] for r in main}) == 30, "Holdout inventory differs")
    require(registry["holdout_audit"]["ga_results_found"] is False, "Available audit found previous holdout search results")
    destination = Path(out)
    require(not destination.exists(), "Choose an empty output directory; preserve incomplete evidence")
    destination.mkdir(parents=True)
    begin = time.perf_counter()
    from studies.knapsack_parameters.population_size_study.exact import certify_problem
    history_keys = set()
    readme = _fetch({"source_path": "README.md", "bytes": 1309}, registry)
    require(sha1(b"blob " + str(len(readme)).encode("ascii") + b"\0" + readme).hexdigest() ==
            "0ab81c1f1b67e0a9696658950ecb02f3e8b443ad", "Pinned source license README differs")
    require(b"CC-BY-4.0" in readme or b"creativecommons.org/licenses/by/4.0" in readme, "Expected source attribution license not found")
    (destination / "KPLIB_README.md").write_bytes(readme)
    historical = registry["historical_duplicate_inventory"]["cases"]
    for entry in historical:
        descriptors = entry["local_sources"]
        require(len({r["sha256"] for r in descriptors}) == 1 and len({r["bytes"] for r in descriptors}) == 1,
                "Historical copies disagree")
        raw = _fetch({"source_path": entry["source_path"], "bytes": descriptors[0]["bytes"]}, registry)
        require(len(raw) == descriptors[0]["bytes"] and sha256(raw).hexdigest() == descriptors[0]["sha256"],
                "Pinned historical source differs from retained bytes")
        problem = parse_kp_bytes(raw, 100)
        history_keys.add(unordered_problem_sha256(problem))
    extension = read_json(HERE / "data" / "history_source_extension.json")
    require(extension["commit"] == registry["source_commit"], "Historical extension revision differs")
    missing = registry["historical_duplicate_inventory"]["missing_source_paths"]
    require({r["source_path"] for r in extension["files"]} == set(missing), "Historical extension incomplete")
    for entry in extension["files"]:
        raw = _fetch(entry, registry)
        history_keys.add(unordered_problem_sha256(validate_source(raw, entry)))
    tasks = []
    known_keys = set()
    for entry in registry["technical_cases"]:
        task = entry["task_id"]
        problem_path = HERE / "data" / "technical" / (task + ".problem.json")
        certificate_path = HERE / "data" / "technical" / (task + ".certificate.json")
        problem, certificate = read_json(problem_path), read_json(certificate_path)
        raw_reference = read_json(HERE / entry["source_file"]["path"])
        raw = base64.b64decode(raw_reference["raw_base64"], validate=True)
        require(validate_source(raw, entry) == problem and sha256(raw).hexdigest() == raw_reference["raw_sha256"],
                "Technical source bytes and retained problem differ")
        for kind in ("problem_file", "certificate_file", "source_file"):
            reference = entry[kind]
            require(sha(HERE / reference["path"]) == reference["sha256"], "Retained technical input differs")
        require(problem["n"] == 100 and certificate["status"] == "CERTIFIED_TWO_INDEPENDENT_EXACT_ORACLES", "Technical reference differs")
        require(certificate["optimum"] > 0, "Technical optimum missing")
        require(certificate["problem_sha256"] == problem_sha256(problem)
                and certificate["source_sha256"] == sha256(raw).hexdigest(), "Retained exact certificate identity differs")
        for name in ("capacity_certificate", "profit_certificate"):
            witness = certificate[name]
            measured = score(problem, witness["witness_mask"])
            require(measured["feasible"] and measured["profit"] == witness["optimum_profit"] == certificate["optimum"],
                    "Retained exact witnesses disagree")
            require(measured["weight"] == witness["witness_weight"] and measured["profit"] == witness["witness_profit"],
                    "Retained witness scores differ")
        bank = make_bank(problem, entry["task_index"], protocol["pilot"]["seed"], protocol["pilot"]["preparation_seed"])
        write_json(destination / task / "problem.json", problem)
        write_json(destination / task / "certificate.json", certificate)
        write_json(destination / task / "bank.json", bank)
        tasks.append({"task": task, "task_index": entry["task_index"], "phase": "technical",
                      "problem_sha256": problem_sha256(problem), "known_certificate_sha256": sha(certificate_path)})
    for entry in main:
        raw = _fetch(entry, registry)
        problem = validate_source(raw, entry)
        key = unordered_problem_sha256(problem)
        require(key not in known_keys and key not in history_keys, "Duplicate or previously used holdout problem")
        known_keys.add(key)
        started = time.perf_counter()
        certificate = certify_problem(problem, memory_limit_bytes=512 * 1024 * 1024, deadline=time.monotonic() + 30)
        require(certificate["status"] == "CERTIFIED_TWO_INDEPENDENT_EXACT_ORACLES", "Dual exact certification failed")
        folder = destination / entry["task_id"]
        folder.mkdir()
        (folder / "source.kp").write_bytes(raw)
        write_json(folder / "problem.json", problem)
        write_json(folder / "certificate.json", certificate)
        tasks.append({"task": entry["task_id"], "task_index": entry["task_index"], "phase": "main",
                      "source_sha256": sha256(raw).hexdigest(), "git_blob_sha1": entry["git_blob_sha1"],
                      "problem_sha256": problem_sha256(problem), "unordered_problem_sha256": key,
                      "certificate_seconds": time.perf_counter() - started})
    files = [{"path": path.relative_to(destination).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}
             for path in sorted(destination.rglob("*")) if path.is_file()]
    write_json(destination / "manifest.json", {"status": "INPUTS_AUDITED_AND_CERTIFIED", "tasks": tasks, "files": files,
               "holdout_tasks": 30, "technical_tasks": 3, "source_commit": registry["source_commit"],
               "historical_duplicate_inputs_checked": len(historical) + len(extension["files"]), "preparation_seconds": time.perf_counter() - begin,
               "readme_sha256": sha256(readme).hexdigest(), "license": "CC-BY-4.0",
               "main_ga_runs": 0, "main_banks_prepared": False,
               "independence_scope": "available project source and execution inventory; external searches cannot be ruled out"})
    print("Prepared 3 technical cases and 30 certified holdout inputs; no main GA runs.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.out)


if __name__ == "__main__":
    main()

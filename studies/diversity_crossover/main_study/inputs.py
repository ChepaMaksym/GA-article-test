"""CI-only preparation and authentication of all registered main-series starts.

The preparation cache is shared only within one objective. Search callers receive
known scores, never that cache, exact witnesses or neighbor certificates.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path

import numpy as np

from ..implementation.engine import evaluate, make_rngs
from ..implementation.verifier import independent_score
from .contract import (AUTHORITY, PROTOCOL_ID, REGISTRATION_SHA, STUDY_ROOT,
                       authenticate, canonical_bytes, ci_only, file_identity,
                       read_json, require, source_manifest,
                       validate_tests_receipt, verify_file_manifest,
                       write_file_manifest, write_json, nonsearch_budget_preflight)

REPO_ROOT = Path(__file__).resolve().parents[3]
N, MU, BUDGET = 100, 30, 5000
MODELS = ("Flat", "OneMax", "Jump4", "Jump8")
KNAPSACK_TASKS = tuple(f"{group}-s{index:03d}" for group in ("UC", "WC", "SC") for index in range(10))
TASKS = MODELS + KNAPSACK_TASKS
STARTS = ("cloned", "bank")
METHODS = ("baseline", "directed", "repeated", "mutation_control")
MAIN_SEEDS = tuple(range(71001, 71031))
DIAGNOSTIC_SEED = 71901
LOCAL_TASKS = tuple(AUTHORITY["inputs"]["admitted_centers"])
GLOBAL_TASKS = tuple(AUTHORITY["inputs"]["global_diagnostic_centers"])
CLONED_TASKS = MODELS + LOCAL_TASKS
CHANNELS = ("initialization", "parents", "branch", "crossover", "mutation", "ties")
BANK_SCHEMA = "diversity-main-bank-v1"
MANIFEST_SCHEMA = "diversity-main-banks-v1"
EXPECTED_BANKS = 1576
FROZEN_INPUTS = STUDY_ROOT / "main_inputs"


def _same(left, right):
    return canonical_bytes(left) == canonical_bytes(right)


def _digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def starts_for(task):
    require(task in TASKS, "unregistered main task")
    return STARTS if task in CLONED_TASKS else ("bank",)


def bank_specs():
    """The exact preparation order; no seeds or difficult cases are replaced."""
    return [(task, start, seed) for task in TASKS for seed in MAIN_SEEDS for start in starts_for(task)] + [
        (task, "cloned", DIAGNOSTIC_SEED) for task in GLOBAL_TASKS]


def job_specs(task, block):
    require(task in TASKS and type(block) is int and 0 <= block < 3, "invalid main job identity")
    return [(task, start, seed, method)
            for seed in MAIN_SEEDS[block * 10:(block + 1) * 10]
            for start in starts_for(task) for method in METHODS]


def diagnostic_specs(block):
    require(type(block) is int and block in (0, 1), "invalid diagnostic block")
    return [(task, "cloned", DIAGNOSTIC_SEED, method)
            for task in GLOBAL_TASKS[block * 8:(block + 1) * 8] for method in METHODS]


def bank_path(task, start, seed):
    require((task, start, seed) in set(bank_specs()), "unregistered bank identity")
    return f"banks/{task}-{start}-{seed}.json"


def load_context():
    """Read retained evidence; do not run a historical solver or its authority."""
    ci_only()
    from studies.knapsack_parameters.feasibility.frozen_inputs import verify_input_bundle
    instances, data_manifest = verify_input_bundle()
    input_authority = AUTHORITY["inputs"]
    for name in ("data_manifest", "registry"):
        require(file_identity(REPO_ROOT / input_authority[f"{name}_path"])["sha256"] ==
                input_authority[f"{name}_sha256"], "retained input identity changed")
    require(tuple(input_authority["models"]) == MODELS and
            tuple(input_authority["knapsack_instances"]) == KNAPSACK_TASKS,
            "registered task order changed")
    require(tuple(AUTHORITY["settings"]["main_seeds"]) == MAIN_SEEDS and
            AUTHORITY["settings"]["diagnostic_seed"] == DIAGNOSTIC_SEED,
            "registered seed ledger changed")
    registry = read_json(REPO_ROOT / input_authority["registry_path"])
    require(registry["all_30_accounted"] is True and registry["case_count"] == 30 and
            registry["admitted_center_count"] == 14, "historical registry incomplete")
    cases = {row["instance_id"]: row["payload"] for row in registry["cases"]}
    objects = {obj.instance_id: obj for obj in instances}
    require(tuple(cases) == tuple(objects) == KNAPSACK_TASKS, "historical case order changed")
    actual_local = tuple(task for task in KNAPSACK_TASKS
                         if cases[task]["status"] in ("ADMITTED_STRICT_LOCAL", "ADMITTED_PLATEAU_LOCAL"))
    actual_global = tuple(task for task in KNAPSACK_TASKS
                          if cases[task]["status"] == "EXCLUDED_GLOBAL_CENTER")
    require(actual_local == LOCAL_TASKS and actual_global == GLOBAL_TASKS and
            len(LOCAL_TASKS) == 14 and len(GLOBAL_TASKS) == 16, "center eligibility changed")
    require(cases["SC-s005"]["status"] == "ADMITTED_PLATEAU_LOCAL" and
            sum(cases[task]["status"] == "ADMITTED_STRICT_LOCAL" for task in LOCAL_TASKS) == 13,
            "strict/plateau classification changed")
    problems, centers, metadata = {}, {}, {}
    for task in TASKS:
        if task in ("Flat", "OneMax"):
            problems[task] = {"kind": "flat" if task == "Flat" else "onemax", "n": N}
            centers[task] = "0" * N
            metadata[task] = {"center_type": "NEUTRAL" if task == "Flat" else "ZERO_START",
                              "posthoc_known_optimum": None if task == "Flat" else N}
        elif task in ("Jump4", "Jump8"):
            gap = int(task[4:])
            problems[task] = {"kind": "jump", "n": N, "k": gap}
            centers[task] = "1" * (N - gap) + "0" * gap
            metadata[task] = {"center_type": "JUMP_PLATEAU", "posthoc_known_optimum": N + gap}
        else:
            obj, case = objects[task], cases[task]
            require(obj.n == case["n"] == N, "historical dimension changed")
            problems[task] = {"kind": "knapsack", "n": N, "capacity": obj.capacity,
                              "weights": list(obj.weights), "profits": list(obj.profits)}
            centers[task] = case["certificate"]["center"]["mask"]
            metadata[task] = {"center_type": case["status"], "source_path": obj.source_path,
                              "source_identity": case["source_identity"],
                              "posthoc_known_optimum": case["exact"]["confirmed_optimum"]}
    return problems, centers, metadata, data_manifest


def generate_masks(task, center, rng, start):
    require(task in TASKS and start in STARTS and len(center) == N and set(center) <= {"0", "1"},
            "invalid preparation identity")
    if start == "cloned":
        return [center] * MU
    result = [center if task.startswith("Jump") else "0" * N]
    for _ in range(MU - 1):
        if task.startswith("Jump"):
            bits = np.ones(N, dtype=np.uint8)
            bits[rng.choice(N, int(task[4:]), replace=False)] = 0
        else:
            bits = (rng.random(N) < 0.5).astype(np.uint8)
        result.append("".join(str(int(value)) for value in bits))
    return result


def validate_bank(bank, *, problem, center, metadata):
    """Independently replay initialization and all thirty known-score positions."""
    ci_only()
    require(bank.get("schema_version") == BANK_SCHEMA and bank.get("protocol_id") == PROTOCOL_ID,
            "wrong main-bank schema/protocol")
    task, start, seed = bank.get("task"), bank.get("start"), bank.get("seed")
    require((task, start, seed) in set(bank_specs()) and type(seed) is int,
            "unregistered bank identity")
    require(bank["task_index"] == TASKS.index(task) and bank["start_index"] == STARTS.index(start) and
            bank["n"] == N and bank["mu"] == MU, "bank parameters changed")
    require(_same(bank["problem"], problem) and _same(bank["metadata"], metadata),
            "bank objective or posthoc metadata changed")
    require(len(bank["masks"]) == len(bank["scores"]) == MU, "incomplete bank")
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [seed, TASKS.index(task), STARTS.index(start), 0])))
    require(_same(generator.bit_generator.state, bank["initialization_before"]), "wrong preparation RNG")
    if start == "cloned":
        expected = [center for _ in range(MU)]
    else:
        expected = [center if task.startswith("Jump") else "0" * N]
        for _ in range(MU - 1):
            if task.startswith("Jump"):
                positions = set(int(i) for i in generator.choice(N, int(task[4:]), replace=False))
                expected.append("".join("0" if i in positions else "1" for i in range(N)))
            else:
                values = generator.random(N)
                expected.append("".join("1" if float(value) < 0.5 else "0" for value in values))
    require(bank["masks"] == expected and
            _same(generator.bit_generator.state, bank["initialization_after"]),
            "bank draw order or masks changed")
    for mask, score in zip(bank["masks"], bank["scores"], strict=True):
        require(_same(independent_score(problem, mask), score), "independent initial score differs")
    physical = bank["physical_preparation_evaluations"]
    require(type(physical) is int and 0 <= physical <= len(set(expected)) and
            bank["logical_initial_positions"] == bank["independent_verification_evaluations"] == MU,
            "bank accounting changed")
    return bank


def verify_cache_accounting(banks, manifest):
    """Verify initial-only deduplication with mask sets, not the scoring cache."""
    seen = {task: set() for task in TASKS}
    physical = 0
    require(len(banks) == EXPECTED_BANKS, "wrong bank count for preparation accounting")
    for bank, expected in zip(banks, bank_specs(), strict=True):
        require((bank["task"], bank["start"], bank["seed"]) == expected,
                "initial accounting order changed")
        task = bank["task"]
        fresh = set(bank["masks"]) - seen[task]
        require(len(fresh) == bank["physical_preparation_evaluations"],
                "initial-only shared cache accounting differs")
        physical += len(fresh)
        seen[task].update(bank["masks"])
    require(manifest["physical_preparation_evaluations"] == physical and
            manifest["logical_initial_positions"] == manifest["independent_verification_evaluations"] ==
            MU * EXPECTED_BANKS, "initial preparation totals changed")


def prepare(output, expected_sha):
    ci_only()
    provenance = authenticate(expected_sha)
    validate_tests_receipt()
    budget_receipt = nonsearch_budget_preflight("prepare")
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()), "prepare output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    problems, centers, metadata, _ = load_context()
    source = source_manifest()
    fingerprint = _digest(source)
    caches = {task: {} for task in TASKS}
    banks, records = [], []
    for task, start, seed in bank_specs():
        rngs = make_rngs(TASKS.index(task), STARTS.index(start), seed=seed)
        rng = rngs["initialization"]
        before = copy.deepcopy(rng.bit_generator.state)
        masks = generate_masks(task, centers[task], rng, start)
        after = copy.deepcopy(rng.bit_generator.state)
        cache = caches[task]
        previous = len(cache)
        for mask in masks:
            if mask not in cache:
                cache[mask] = evaluate(problems[task], mask)
        bank = {"schema_version": BANK_SCHEMA, "protocol_id": PROTOCOL_ID,
                "registration_sha": REGISTRATION_SHA, "preparation_sha": expected_sha,
                "source_fingerprint": fingerprint, "task": task, "task_index": TASKS.index(task),
                "start": start, "start_index": STARTS.index(start), "seed": seed, "n": N, "mu": MU,
                "problem": problems[task], "masks": masks,
                "scores": [copy.deepcopy(cache[mask]) for mask in masks],
                "initialization_before": before, "initialization_after": after,
                "physical_preparation_evaluations": len(cache) - previous,
                "logical_initial_positions": MU, "independent_verification_evaluations": MU,
                "metadata": metadata[task]}
        validate_bank(bank, problem=problems[task], center=centers[task], metadata=metadata[task])
        relative = bank_path(task, start, seed)
        write_json(output / relative, bank)
        records.append({"task": task, "start": start, "seed": seed, "path": relative,
                        **file_identity(output / relative)})
        banks.append(bank)
    manifest = {"schema_version": MANIFEST_SCHEMA, "protocol_id": PROTOCOL_ID,
                "registration_sha": REGISTRATION_SHA, "preparation_sha": expected_sha,
                "source_fingerprint": fingerprint, "count": len(records), "tasks": list(TASKS),
                "main_seeds": list(MAIN_SEEDS), "diagnostic_seed": DIAGNOSTIC_SEED,
                "banks": records, "physical_preparation_evaluations": sum(
                    bank["physical_preparation_evaluations"] for bank in banks),
                "logical_initial_positions": MU * len(records),
                "independent_verification_evaluations": MU * len(records),
                "initial_preparation_cache_only": True,
                "data_manifest_sha256": AUTHORITY["inputs"]["data_manifest_sha256"],
                "registry_sha256": AUTHORITY["inputs"]["registry_sha256"]}
    verify_cache_accounting(banks, manifest)
    write_json(output / "banks_manifest.json", manifest)
    write_json(output / "budget-preflight.json", budget_receipt)
    write_json(output / "source_manifest.json", source)
    write_json(output / "provenance.json", provenance)
    write_file_manifest(output)
    return manifest


def load_banks(directory=None, identities=None):
    """Authenticate every frozen member, independently replay requested banks only."""
    ci_only()
    from .contract import validate_artifact_receipt
    directory = Path(directory or FROZEN_INPUTS)
    verify_file_manifest(directory)
    manifest = read_json(directory / "banks_manifest.json")
    source = read_json(directory / "source_manifest.json")
    transport = read_json(directory / "frozen_transport.json")
    validate_artifact_receipt(transport["prepare_run_id"], transport["prepare_artifact_id"],
                              transport["preparation_sha"], transport["prepare_zip_sha256"])
    require(transport["banks_manifest_sha256"] == file_identity(directory / "banks_manifest.json")["sha256"] and
            transport["source_manifest_sha256"] == file_identity(directory / "source_manifest.json")["sha256"] and
            transport["preparation_sha"] == manifest["preparation_sha"], "frozen main transport changed")
    require(manifest["schema_version"] == MANIFEST_SCHEMA and manifest["protocol_id"] == PROTOCOL_ID and
            manifest["registration_sha"] == REGISTRATION_SHA and manifest["count"] == EXPECTED_BANKS,
            "wrong main-bank manifest")
    require(manifest["tasks"] == list(TASKS) and manifest["main_seeds"] == list(MAIN_SEEDS) and
            manifest["diagnostic_seed"] == DIAGNOSTIC_SEED and
            manifest["initial_preparation_cache_only"] is True,
            "registered preparation scope changed")
    require(_same(source, source_manifest()) and manifest["source_fingerprint"] == _digest(source),
            "prepared implementation differs from currently tested sources")
    for name in ("data_manifest", "registry"):
        require(manifest[f"{name}_sha256"] == AUTHORITY["inputs"][f"{name}_sha256"],
                "prepared historical input identity differs")
    expected = bank_specs()
    require([(row["task"], row["start"], row["seed"]) for row in manifest["banks"]] == expected,
            "missing, duplicate or reordered prepared banks")
    selected = set(expected if identities is None else identities)
    require(selected <= set(expected), "requested unregistered banks")
    problems, centers, metadata, _ = load_context()
    result, accounting_banks = {}, []
    for row in manifest["banks"]:
        key = (row["task"], row["start"], row["seed"])
        relative = bank_path(*key)
        require(row["path"] == relative and file_identity(directory / relative) ==
                {"bytes": row["bytes"], "sha256": row["sha256"]}, "frozen member identity differs")
        bank = read_json(directory / relative)
        require((bank["task"], bank["start"], bank["seed"]) == key and
                bank["preparation_sha"] == manifest["preparation_sha"] and
                bank["registration_sha"] == REGISTRATION_SHA and
                bank["source_fingerprint"] == manifest["source_fingerprint"], "mixed bank provenance")
        accounting_banks.append(bank)
        if key in selected:
            result[key] = validate_bank(bank, problem=problems[key[0]], center=centers[key[0]],
                                        metadata=metadata[key[0]])
    verify_cache_accounting(accounting_banks, manifest)
    require(set(result) == selected, "requested frozen bank missing")
    return result, manifest


def verify_frozen_header(problem, event, bank, method, pc):
    """Main-series binding, without changing the immutable seed-70001 verifier."""
    ci_only()
    require(method in ("baseline", "directed", "repeated") and pc in (0.0, 0.9),
            "invalid kernel profile")
    require((bank["task"], bank["start"], bank["seed"]) in set(bank_specs()), "unknown frozen header seed")
    require(_same(event.get("problem"), problem) and _same(problem, bank["problem"]),
            "frozen header objective differs")
    require(event.get("event") == "initial" and event.get("schema_version") == 1 and
            event.get("method") == method, "frozen header schema/profile differs")
    require(_same(event.get("population"), bank["masks"]) and _same(event.get("scores"), bank["scores"]),
            "frozen header initial positions differ")
    require(_same(event.get("params"), {"mu": MU, "n": N, "budget": BUDGET,
                                        "pc": float(pc), "mutation_probability": 1 / N,
                                        "repeated_offspring": 4}), "frozen header settings differ")
    expected = {}
    for channel, name in enumerate(CHANNELS):
        generator = np.random.PCG64(np.random.SeedSequence(
            [bank["seed"], TASKS.index(bank["task"]), STARTS.index(bank["start"]), channel]))
        expected[name] = generator.state
    require(_same(bank["initialization_before"], expected["initialization"]), "frozen header seed differs")
    expected["initialization"] = bank["initialization_after"]
    require(_same(event.get("rng_start"), expected), "frozen header RNG states differ")
    best = max(range(MU), key=lambda index: tuple(bank["scores"][index]["key"]))
    require(_same(event.get("initial_record"), {"mask": bank["masks"][best],
                                               "score": bank["scores"][best], "call": 0}),
            "frozen header initial record differs")
    return {"status": "VERIFIED_FROZEN_MAIN_HEADER", "seed": bank["seed"], "objective_evaluations": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args(argv)
    prepare(args.output, args.expected_sha)


if __name__ == "__main__":
    main()

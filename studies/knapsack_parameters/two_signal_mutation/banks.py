"""Frozen initial populations; exact historical references are never solved again."""
from __future__ import annotations

from copy import deepcopy
import io
from pathlib import Path
import subprocess
from time import perf_counter_ns

from . import authority as a

PILOT_TASKS = ("UC-s000", "WC-s001", "SC-s005", "SC-s000")
STARTS = ("cloned", "bank")
CLASSES = ("UC", "WC", "SC")


def expected_conditions(stage):
    a.require(stage in ("pilot", "main"), "Unknown bank stage")
    if stage == "pilot":
        return [{"task": task, "family": task[3:], "task_index": task_index,
                 "start": start, "start_index": start_index, "seed": 93999}
                for task_index, task in enumerate(PILOT_TASKS) for start_index, start in enumerate(STARTS)]
    return [{"task": f"{label}-s{index:03d}", "family": f"s{index:03d}",
             "task_index": 3 * (index - 10) + class_index, "start": "bank", "start_index": 1, "seed": seed}
            for index in range(10, 20) for class_index, label in enumerate(CLASSES)
            for seed in range(94001, 94031)]


def independent_score(problem, mask):
    a.require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"}, "Invalid initial mask")
    weight = sum(problem["weights"][i] for i in range(problem["n"]) if mask[i] == "1")
    profit = sum(problem["profits"][i] for i in range(problem["n"]) if mask[i] == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def source_case(task, stage):
    """Read and hash existing inputs/references. No solver or neighbor traversal."""
    registration = a.read_json(a.MODULE / "registration.json")
    if stage == "main":
        registry_path = a.ROOT / "studies/knapsack_parameters/basic_parameters/evidence/run-39030726467/registry.json"
        a.require(a.identity(registry_path)["sha256"] == registration["holdout_registry_sha256"], "Holdout registry changed")
        registry = a.read_json(registry_path)
        found = [row for row in registry["records"] if row["instance_id"] == task]
        source_root = a.ROOT / "studies/knapsack_parameters/basic_parameters/inputs/holdout"
    else:
        a.require(stage == "pilot", "Unknown source stage")
        registry_path = a.ROOT / "studies/knapsack_parameters/evidence/run-37637475385/registry.json"
        a.require(a.identity(registry_path)["sha256"] == registration["historical_registry_sha256"], "Historical registry changed")
        registry = a.read_json(registry_path)
        found = [row["payload"] for row in registry["cases"] if row["instance_id"] == task]
        source_root = a.ROOT / "studies/knapsack_parameters/inputs"
    a.require(len(found) == 1, "Missing or duplicate source task")
    row = found[0]
    source = row["source_identity"]
    path = a.safe_child(source_root, source["path"])
    a.require(a.identity(path) == {"bytes": source["bytes"], "sha256": source["sha256"]}, "Source bytes changed")
    tokens = [int(token) for token in path.read_text(encoding="utf-8").split()]
    a.require(len(tokens) == 202 and tokens[0] == 100 and tokens[1] >= 0, "Expected original n100 KPLIB format")
    problem = {"n": 100, "capacity": tokens[1], "profits": tokens[2::2], "weights": tokens[3::2]}
    a.require(all(value > 0 for value in problem["profits"] + problem["weights"]), "Nonpositive item")
    exact = row["exact"]
    optimum = exact["confirmed_optimum"]
    a.require(type(optimum) is int and optimum > 0 and exact["witness_verified"] is True and
              exact["capacity"]["optimum_profit"] == exact["profit"]["optimum_profit"] == optimum,
              "Two existing exact references disagree")
    center = row["preparation"]["center"]
    score = independent_score(problem, center["mask"])
    a.require(score["feasible"] and score["profit"] == center["profit"] and score["weight"] == center["weight"] and
              score["profit"] <= optimum, "Stored center disagrees with input")
    return {"problem": problem, "optimum": optimum, "center_mask": center["mask"],
            "source_identity": {"path": path.relative_to(a.ROOT).as_posix(), **a.identity(path)},
            "registry_identity": a.identity(registry_path)}


def prepare(stage, output, provenance):
    import numpy as np
    conditions = expected_conditions(stage)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for condition in conditions:
        started = perf_counter_ns()
        source = source_case(condition["task"], stage)
        generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
            [94000, 0 if stage == "pilot" else 1, condition["task_index"], condition["seed"]])))
        before = deepcopy(generator.bit_generator.state)
        if condition["start"] == "cloned":
            masks = [source["center_mask"]] * 30
        else:
            masks = ["0" * 100] + ["".join(map(str, generator.integers(0, 2, size=100).tolist())) for _ in range(29)]
        scores_by_mask = {mask: independent_score(source["problem"], mask) for mask in dict.fromkeys(masks)}
        scores = [deepcopy(scores_by_mask[mask]) for mask in masks]
        bank = {**provenance, "schema": "two-signal-bank-v1", "stage": stage, **condition,
                "problem": source["problem"], "source_identity": source["source_identity"],
                "registry_identity": source["registry_identity"], "initial_masks": masks,
                "initial_scores": scores, "initialization_before": before,
                "initialization_after": deepcopy(generator.bit_generator.state),
                "physical_preparation_evaluations": len(scores_by_mask), "logical_initial_positions": 30,
                "preparation_ns": perf_counter_ns() - started,
                "new_search_calls": 0, "new_exact_solves": 0}
        relative = f"banks/{condition['task']}-{condition['start']}-{condition['seed']}.json"
        a.write_json(output / relative, bank)
        rows.append({**condition, "path": relative, **a.identity(output / relative)})
    registry = {**provenance, "schema": "two-signal-bank-registry-v1", "stage": stage, "conditions": len(rows),
                "banks": rows, "preparation_seed": 94000, "new_search_calls": 0, "new_exact_solves": 0}
    a.write_json(output / "bank_registry.json", registry)
    a.write_manifest(output)
    return registry


def validate_bank(bank, source):
    """Independent reconstruction of the registered preparation, CI workers only."""
    import numpy as np

    a.require(bank["stage"] in ("pilot", "main"), "Invalid bank stage")
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [94000, int(bank["stage"] == "main"), bank["task_index"], bank["seed"]])))
    before = deepcopy(generator.bit_generator.state)
    if bank["start"] == "cloned":
        expected_masks = [source["center_mask"]] * 30
    else:
        expected_masks = ["0" * 100]
        for _ in range(29):
            values = generator.integers(low=0, high=2, size=100)
            expected_masks.append("".join("1" if bit else "0" for bit in values))
    a.require(bank["initial_masks"] == expected_masks and
              a.canonical(bank["initialization_before"]) == a.canonical(before) and
              a.canonical(bank["initialization_after"]) == a.canonical(generator.bit_generator.state),
              "Bank masks or preparation RNG states disagree with frozen seed")
    actual = []
    for mask in expected_masks:
        weight = profit = 0
        for index, bit in enumerate(mask):
            if bit == "1":
                weight += source["problem"]["weights"][index]
                profit += source["problem"]["profits"][index]
        actual.append({"weight": weight, "profit": profit, "feasible": weight <= source["problem"]["capacity"]})
    a.require(a.canonical(actual) == a.canonical(bank["initial_scores"]), "Independent bank scores disagree")
    a.require(type(bank.get("physical_preparation_evaluations")) is int and
              bank["physical_preparation_evaluations"] == len(set(expected_masks)) and
              type(bank.get("preparation_ns")) is int and bank["preparation_ns"] >= 0 and
              type(bank["logical_initial_positions"]) is int and bank["logical_initial_positions"] == 30 and
              type(bank["new_search_calls"]) is int and bank["new_search_calls"] == 0 and
              type(bank["new_exact_solves"]) is int and bank["new_exact_solves"] == 0,
              "Invalid physical/logical preparation accounting")


def seal_frozen_files(stage, directory, freeze_sha, manifest):
    """Compare all current evidence bytes with the separate data-only Git commit."""
    paths = [a.MODULE / f"frozen_{stage}_banks.json", directory / "file_manifest.json"]
    paths += [a.safe_child(directory, row["path"]) for row in manifest["files"]]
    queries = b"".join((freeze_sha + ":" + path.relative_to(a.ROOT).as_posix() + "\n").encode() for path in paths)
    stream = io.BytesIO(subprocess.check_output(["git", "cat-file", "--batch"], input=queries, cwd=a.ROOT))
    for path in paths:
        header = stream.readline().split()
        a.require(len(header) == 3 and header[1] == b"blob", "Frozen evidence blob missing")
        content = stream.read(int(header[2]))
        a.require(stream.read(1) == b"\n" and content == path.read_bytes(), "Evidence changed after data freeze")
    a.require(stream.read() == b"", "Unexpected freeze inventory")


def load_frozen_banks(stage, check_scores=True, selected_worker=None):
    directory = a.MODULE / "inputs" / stage
    manifest = a.verify_manifest(directory)
    frozen = a.read_json(a.MODULE / f"frozen_{stage}_banks.json")
    a.require(frozen.get("frozen") is True and frozen.get("stage") == stage and
              frozen.get("registry_identity") == a.identity(directory / "bank_registry.json"), "Banks are not frozen")
    registry = a.read_json(directory / "bank_registry.json")
    a.require(registry.get("schema") == "two-signal-bank-registry-v1" and registry.get("stage") == stage and
              registry.get("preparation_seed") == 94000 and registry.get("new_search_calls") == 0 and
              registry.get("new_exact_solves") == 0, "Wrong bank registry")
    a.validate_source_receipt(registry, "prepare-" + stage)
    artifact = a.api(f"/actions/artifacts/{frozen['artifact_id']}")
    a.require(artifact.get("expired") is False and artifact.get("workflow_run", {}).get("id") == registry["run_id"] and
              artifact.get("digest") == "sha256:" + frozen["zip_sha256"], "Frozen bank artifact unavailable")
    freeze_sha = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", a.REL + f"frozen_{stage}_banks.json"],
                                         cwd=a.ROOT, text=True).strip()
    a.require(freeze_sha and freeze_sha != registry["implementation_sha"], "Separate data freeze commit required")
    changed = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", freeze_sha],
                                      cwd=a.ROOT, text=True).splitlines()
    a.require(bool(changed) and all(name.startswith(a.REL + f"inputs/{stage}/") or
                                   name == a.REL + f"frozen_{stage}_banks.json" for name in changed),
              "Frozen banks commit must contain only the relevant data")
    seal_frozen_files(stage, directory, freeze_sha, manifest)
    expected = {(c["task"], c["start"], c["seed"]): c for c in expected_conditions(stage)}
    allowed_workers = set(PILOT_TASKS) if stage == "pilot" else {f"s{i:03d}" for i in range(10, 20)}
    a.require(selected_worker is None or selected_worker in allowed_workers, "Unknown bank worker filter")
    seen, result = set(), []
    for row in registry["banks"]:
        key = row["task"], row["start"], row["seed"]
        a.require(key in expected and key not in seen, "Duplicate or foreign bank condition")
        seen.add(key)
        path = a.safe_child(directory, row["path"])
        a.require(row["path"] == f"banks/{row['task']}-{row['start']}-{row['seed']}.json", "Noncanonical bank filename")
        a.require(a.identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Bank payload changed")
        bank = a.read_json(path)
        for field, value in expected[key].items():
            a.require(bank.get(field) == value, "Mixed bank condition")
        a.require(bank.get("implementation_sha") == registry["implementation_sha"] and
                  bank.get("source_manifest") == registry["source_manifest"] and bank.get("stage") == stage and
                  bank.get("schema") == "two-signal-bank-v1", "Mixed bank provenance or problem")
        a.require(len(bank["initial_masks"]) == len(bank["initial_scores"]) == 30 and
                  bank["logical_initial_positions"] == 30 and bank["new_search_calls"] == bank["new_exact_solves"] == 0,
                  "Wrong initial accounting")
        wanted = selected_worker is None or (bank["task"] if stage == "pilot" else bank["family"]) == selected_worker
        if not wanted:
            continue
        if check_scores:
            source = source_case(bank["task"], stage)
            a.require(bank.get("problem") == source["problem"] and bank.get("source_identity") == source["source_identity"] and
                      bank.get("registry_identity") == source["registry_identity"], "Bank problem or source identity changed")
            validate_bank(bank, source)
        result.append(bank)
    a.require(seen == set(expected) and registry["conditions"] == len(expected), "Incomplete bank rectangle")
    return result

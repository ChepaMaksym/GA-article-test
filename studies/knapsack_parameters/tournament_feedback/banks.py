"""Prepared shared beginnings, independent exact references and donor freezes."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
from time import perf_counter_ns
import urllib.request

from . import authority as a
from studies.knapsack_parameters.parameter_dynamics.banks import exact_capacity, exact_profit, independent_score, parse_source

CLASSES = ("UC", "WC", "SC")
SOURCE_DIRS = ("00Uncorrelated", "01WeaklyCorrelated", "02StronglyCorrelated")
SOURCE_COMMIT = "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c"


def expected_conditions(stage):
    a.require(stage in ("pilot", "main"), "Unknown bank stage")
    if stage == "pilot":
        return [{"task": task, "family": task[3:], "task_index": i, "start": start, "start_index": j,
                 "seed": 109999, "donor_seed": 109997, "condition_index": 2 * i + j, "worker": task}
                for i, task in enumerate(a.PILOT_TASKS) for j, start in enumerate(("cloned", "bank"))]
    return [{"task": f"{label}-s{i:03d}", "family": f"s{i:03d}", "task_index": 3 * (i - 40) + c,
             "start": "bank", "start_index": 1, "seed": seed, "donor_seed": seed + 1000,
             "condition_index": 30 * (3 * (i - 40) + c) + seed - 110001, "worker": f"s{i:03d}"}
            for i in range(40, 50) for c, label in enumerate(CLASSES) for seed in range(110001, 110031)]


def digest_problem(problem):
    return hashlib.sha256(a.canonical(problem)).hexdigest()


def independent_line_parse(raw):
    rows = [line.strip() for line in raw.decode("utf-8").splitlines() if line.strip()]
    a.require(len(rows) == 102 and len(rows[0].split()) == len(rows[1].split()) == 1, "Unexpected KPLIB lines")
    n, capacity = int(rows[0]), int(rows[1])
    pairs = [line.split() for line in rows[2:]]
    a.require(n == 100 and all(len(pair) == 2 for pair in pairs), "Wrong item lines")
    return {"n": n, "capacity": capacity, "profits": [int(pair[0]) for pair in pairs], "weights": [int(pair[1]) for pair in pairs]}


def historical_source_identities():
    from studies.knapsack_parameters.two_signal_mutation.banks import source_case as old
    from studies.knapsack_parameters.parameter_dynamics.banks import source_case as dynamics
    records = []
    for i in range(30):
        for label in CLASSES:
            task = f"{label}-s{i:03d}"
            source = old(task, "pilot" if i < 10 else "main") if i < 20 else dynamics(task, "main")
            records.append({"task": task, "sha256": source["source_identity"]["sha256"], "problem_sha256": digest_problem(source["problem"])})
    # Include every additional already-prepared cohort, without opening any search outcome.
    for path in sorted((a.ROOT / "studies/knapsack_parameters").rglob("source_registry.json")):
        if a.MODULE in path.parents:
            continue
        registry = a.read_json(path)
        for row in registry.get("records", []):
            if not isinstance(row, dict) or not row.get("task") or not row.get("source_identity"):
                continue
            identity = row["source_identity"]
            if "path" not in identity:
                continue
            source_path = a.safe_child(path.parent, identity["path"])
            if source_path.is_file():
                a.require(a.identity(source_path) == {"bytes": identity["bytes"], "sha256": identity["sha256"]}, "Historical source checksum changed")
                problem = parse_source(source_path.read_bytes())
                item = {"task": row["task"], "sha256": identity["sha256"], "problem_sha256": digest_problem(problem)}
                if item not in records:
                    records.append(item)
    a.require(len(records) >= 90, "Incomplete previous-cohort inventory")
    return records


def prepare_main_sources(directory, provenance):
    started = perf_counter_ns()
    historical = historical_source_identities()
    seen_raw = {row["sha256"] for row in historical}
    seen_problem = {row["problem_sha256"] for row in historical}
    records = []
    for i in range(40, 50):
        for c, label in enumerate(CLASSES):
            relative = f"source/{SOURCE_DIRS[c]}/n00100/R01000/s{i:03d}.kp"
            url = f"https://raw.githubusercontent.com/likr/kplib/{SOURCE_COMMIT}/" + relative.removeprefix("source/")
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tournament-feedback-audit"}), timeout=60) as response:
                raw = response.read()
            problem = parse_source(raw)
            a.require(problem == independent_line_parse(raw), "Independent parsers disagree")
            digest, semantic = hashlib.sha256(raw).hexdigest(), digest_problem(problem)
            a.require(digest not in seen_raw and semantic not in seen_problem, "Duplicate new/previous task")
            seen_raw.add(digest)
            seen_problem.add(semantic)
            path = a.safe_child(directory, relative)
            a.require(not path.exists(), "Source overwrite refused")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            capacity, profit = exact_capacity(problem), exact_profit(problem)
            a.require(capacity["optimum_profit"] == profit["optimum_profit"], "Independent exact references disagree")
            records.append({"task": f"{label}-s{i:03d}", "source_identity": {"path": relative, **a.identity(path)},
                            "problem_sha256": semantic, "exact": {"capacity": capacity, "profit": profit}, "optimum": capacity["optimum_profit"]})
    registry = {**provenance, "schema": "tournament-feedback-sources-v1", "source_commit": SOURCE_COMMIT,
                "records": records, "historical_duplicate_inventory": historical, "new_exact_solves": 60,
                "source_preparation_ns": perf_counter_ns() - started, "license": "KPLIB CC-BY-4.0"}
    a.write_json(Path(directory) / "source_registry.json", registry)
    return registry


def source_case(task, stage, directory=None):
    if stage == "pilot":
        from studies.knapsack_parameters.two_signal_mutation.banks import source_case as old
        return old(task, "pilot")
    a.require(stage == "main", "Unknown source stage")
    directory = Path(directory) if directory else a.MODULE / "inputs/main"
    path = directory / "source_registry.json"
    registry = a.read_json(path)
    a.require(registry.get("schema") == "tournament-feedback-sources-v1" and registry.get("source_commit") == SOURCE_COMMIT and
              registry.get("new_exact_solves") == 60 and len(registry["records"]) == 30 and
              {row["task"] for row in registry["records"]} == {f"{label}-s{i:03d}" for label in CLASSES for i in range(40, 50)}, "Incomplete source audit")
    matches = [row for row in registry["records"] if row["task"] == task]
    a.require(len(matches) == 1, "Missing or duplicate source task")
    row = matches[0]
    entry = row["source_identity"]
    rawpath = a.safe_child(directory, entry["path"])
    a.require(a.identity(rawpath) == {"bytes": entry["bytes"], "sha256": entry["sha256"]}, "Source bytes changed")
    problem = parse_source(rawpath.read_bytes())
    a.require(problem == independent_line_parse(rawpath.read_bytes()) and digest_problem(problem) == row["problem_sha256"], "Source semantics changed")
    for exact in row["exact"].values():
        score = independent_score(problem, exact["witness_mask"])
        a.require(score["feasible"] and score["profit"] == row["optimum"] == exact["optimum_profit"] and score["weight"] == exact["witness_weight"], "Invalid exact witness")
    return {"problem": problem, "optimum": row["optimum"], "source_identity": entry, "registry_identity": a.identity(path)}


def prepare(stage, output, provenance):
    import numpy as np
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if stage == "main":
        prepare_main_sources(output, provenance)
    conditions = expected_conditions(stage)
    sources = {task: source_case(task, stage, output if stage == "main" else None) for task in dict.fromkeys(row["task"] for row in conditions)}
    rows = []
    for condition in conditions:
        started = perf_counter_ns()
        source = sources[condition["task"]]
        generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence([109998 if stage == "pilot" else 110000, condition["task_index"], condition["seed"], condition["start_index"]])))
        before = deepcopy(generator.bit_generator.state)
        masks = [source["center_mask"]] * 30 if condition["start"] == "cloned" else ["0" * 100] + ["".join(map(str, generator.integers(0, 2, size=100).tolist())) for _ in range(29)]
        unique_scores = {mask: independent_score(source["problem"], mask) for mask in dict.fromkeys(masks)}
        bank = {**provenance, **condition, "schema": "tournament-feedback-bank-v1", "stage": stage,
                "problem": source["problem"], "source_identity": source["source_identity"], "registry_identity": source["registry_identity"],
                "initial_masks": masks, "initial_scores": [deepcopy(unique_scores[mask]) for mask in masks],
                "initialization_before": before, "initialization_after": deepcopy(generator.bit_generator.state),
                "physical_preparation_evaluations": len(unique_scores), "logical_initial_positions": 30,
                "new_search_calls": 0, "preparation_ns": perf_counter_ns() - started}
        validate_bank(bank, source)
        relative = f"banks/{condition['task']}-{condition['start']}-{condition['seed']}.json"
        a.write_json(output / relative, bank)
        rows.append({**condition, "path": relative, **a.identity(output / relative)})
    registry = {**provenance, "schema": "tournament-feedback-banks-v1", "stage": stage, "conditions": len(rows), "banks": rows,
                "new_search_calls": 0, "new_exact_solves": 60 if stage == "main" else 0,
                "physical_preparation_evaluations": sum(a.read_json(output / row["path"])["physical_preparation_evaluations"] for row in rows),
                "independent_initial_score_checks": 30 * len(rows)}
    a.write_json(output / "bank_registry.json", registry)
    a.write_manifest(output)
    return registry


def validate_bank(bank, source):
    import numpy as np
    stage = bank["stage"]
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence([109998 if stage == "pilot" else 110000, bank["task_index"], bank["seed"], bank["start_index"]])))
    before = deepcopy(generator.bit_generator.state)
    masks = [source["center_mask"]] * 30 if bank["start"] == "cloned" else ["0" * 100] + ["".join(map(str, generator.integers(0, 2, size=100).tolist())) for _ in range(29)]
    a.require(bank["initial_masks"] == masks and bank["initial_scores"] == [independent_score(source["problem"], mask) for mask in masks] and bank["problem"] == source["problem"] and
              bank["initialization_before"] == before and bank["initialization_after"] == generator.bit_generator.state and
              bank["physical_preparation_evaluations"] == len(set(masks)) and bank["logical_initial_positions"] == 30 and bank["new_search_calls"] == 0,
              "Independent bank reconstruction failed")


def load_frozen_banks(stage, check_scores=True, selected_worker=None):
    registry, directory = a.frozen_receipt(stage + "_banks", "prepare-" + stage)
    a.require(directory == a.MODULE / "inputs" / stage and registry.get("schema") == "tournament-feedback-banks-v1" and registry.get("stage") == stage and registry.get("new_search_calls") == 0, "Wrong bank registry")
    expected = {(row["task"], row["start"], row["seed"]): row for row in expected_conditions(stage)}
    seen, result, sources = set(), [], {}
    for row in registry["banks"]:
        key = row["task"], row["start"], row["seed"]
        a.require(key in expected and key not in seen, "Foreign or duplicate bank")
        seen.add(key)
        path = a.safe_child(directory, row["path"])
        a.require(a.identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Bank checksum changed")
        bank = a.read_json(path)
        a.require(all(bank.get(k) == v for k, v in expected[key].items()) and bank.get("source_manifest") == registry["source_manifest"] and bank.get("implementation_sha") == registry["implementation_sha"], "Mixed bank provenance")
        if selected_worker is not None and bank["worker"] != selected_worker:
            continue
        if check_scores:
            source = sources.setdefault(bank["task"], source_case(bank["task"], stage))
            validate_bank(bank, source)
        bank["bank_identity"] = a.identity(path)
        result.append(bank)
    a.require(seen == set(expected), "Incomplete frozen bank rectangle")
    return result


def load_frozen_schedules(stage):
    registry, directory = a.frozen_receipt(stage + "_schedules", stage + "-donors")
    a.require(directory == a.MODULE / "schedules" / stage and registry.get("schema") == "tournament-feedback-schedules-v1" and registry.get("stage") == stage and registry.get("complete") is True, "Wrong donor schedule registry")
    expected = {(row["task"], row["start"], row["seed"]): row for row in expected_conditions(stage)}
    seen, result = set(), {}
    for row in registry["schedules"]:
        key = row["task"], row["start"], row["seed"]
        a.require(key in expected and key not in seen, "Foreign or duplicate donor")
        seen.add(key)
        path = a.safe_child(directory, row["path"])
        a.require(a.identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Donor schedule changed")
        schedule = a.read_json(path)
        a.require(set(schedule) == {"task", "start", "seed", "donor_seed", "bank_identity", "source_manifest", "implementation_sha", "donor_journal_sha256", "values"} and
                  all(schedule.get(k) == expected[key][k] for k in ("task", "start", "seed", "donor_seed")) and schedule["donor_seed"] != schedule["seed"] and
                  schedule["source_manifest"] == registry["source_manifest"] and schedule["implementation_sha"] == registry["implementation_sha"] and
                  len(schedule["values"]) == 173 and schedule["values"][0] == 2 and all(type(k) is int and 2 <= k <= 5 for k in schedule["values"]), "Invalid independent applied donor schedule")
        result[key] = schedule
    a.require(seen == set(expected), "Incomplete donor schedule rectangle")
    return result, registry

"""CI preparation, exact references and separately frozen shared beginnings.

Main data are a new cohort.  Its sources and two independent exact witnesses
are prepared only after a separate main approval; no historical cohort is
substituted.  Search receives only problem, initial masks and known scores.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
from pathlib import Path
import subprocess
from time import perf_counter_ns
import urllib.request

from . import authority as a

PILOT_TASKS = a.PILOT_TASKS
STARTS = ("cloned", "bank")
CLASSES = ("UC", "WC", "SC")
SOURCE_DIRS = ("00Uncorrelated", "01WeaklyCorrelated", "02StronglyCorrelated")
SOURCE_COMMIT = "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c"


def expected_conditions(stage):
    a.require(stage in ("pilot", "main"), "Unknown bank stage")
    if stage == "pilot":
        return [{"task": task, "family": task[3:], "task_index": index,
                 "start": start, "start_index": start_index, "seed": 96999, "worker": task}
                for index, task in enumerate(PILOT_TASKS)
                for start_index, start in enumerate(STARTS)]
    return [{"task": f"{label}-s{index:03d}", "family": f"s{index:03d}",
             "task_index": 3 * (index - 20) + class_index, "start": "bank", "start_index": 1,
             "seed": seed, "seed_block": (seed - 97001) // 6,
             "worker": f"s{index:03d}-b{(seed - 97001) // 6}"}
            for index in range(20, 30) for class_index, label in enumerate(CLASSES)
            for seed in range(97001, 97031)]


def independent_score(problem, mask):
    a.require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"}, "Invalid mask")
    weight = sum(problem["weights"][i] for i, bit in enumerate(mask) if bit == "1")
    profit = sum(problem["profits"][i] for i, bit in enumerate(mask) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def parse_source(raw):
    a.require(type(raw) is bytes, "Source must retain original bytes")
    tokens = [int(token) for token in raw.decode("utf-8").split()]
    a.require(len(tokens) == 202 and tokens[0] == 100 and tokens[1] >= 0, "Expected original n100 KPLIB format")
    problem = {"n": 100, "capacity": tokens[1], "profits": tokens[2::2], "weights": tokens[3::2]}
    a.require(all(value > 0 for value in problem["profits"] + problem["weights"]), "Nonpositive item")
    return problem


def _problem_digest(problem):
    return hashlib.sha256(a.canonical(problem)).hexdigest()


def exact_capacity(problem):
    """At-most-capacity maximum-profit DP with independently checked witness."""
    import numpy as np

    a.require(sum(problem["profits"]) < 2 ** 62, "Exact capacity arithmetic exceeds safe int64 range")
    capacity, n = problem["capacity"], problem["n"]
    values = np.zeros(capacity + 1, dtype=np.int64)
    decisions = np.zeros((n, capacity + 1), dtype=bool)
    for index, (weight, profit) in enumerate(zip(problem["weights"], problem["profits"], strict=True)):
        if weight > capacity:
            continue
        proposed = values[:-weight].copy() + profit
        changed = proposed > values[weight:]
        decisions[index, weight:] = changed
        values[weight:] = np.maximum(values[weight:], proposed)
    optimum, remaining, mask = int(values[capacity]), capacity, ["0"] * n
    for index in range(n - 1, -1, -1):
        if bool(decisions[index, remaining]):
            mask[index] = "1"
            remaining -= problem["weights"][index]
    witness = "".join(mask)
    score = independent_score(problem, witness)
    a.require(score["feasible"] and score["profit"] == optimum, "Capacity DP witness failed")
    return {"method": "independent_capacity_max_profit_dp", "optimum_profit": optimum,
            "witness_mask": witness, "witness_weight": score["weight"], "witness_profit": score["profit"],
            "tie_rule": "exclude_current_item_on_equal"}


def exact_profit(problem):
    """Exact-profit minimum-weight DP; distinct state, transition and backtrack."""
    import numpy as np

    a.require(sum(problem["weights"]) < 2 ** 62, "Exact profit arithmetic exceeds safe int64 range")
    total_profit, n = sum(problem["profits"]), problem["n"]
    unreachable = sum(problem["weights"]) + 1
    weights = np.full(total_profit + 1, unreachable, dtype=np.int64)
    weights[0] = 0
    take = np.zeros((n, total_profit + 1), dtype=bool)
    for index in range(n):
        value, item_weight = problem["profits"][index], problem["weights"][index]
        previous = weights[:-value].copy()
        candidate = previous + item_weight
        better = (previous < unreachable) & (candidate < weights[value:])
        take[index, value:] = better
        target = weights[value:]
        target[better] = candidate[better]
    feasible_profits = np.flatnonzero(weights <= problem["capacity"])
    optimum, target, mask = int(feasible_profits[-1]), int(feasible_profits[-1]), ["0"] * n
    for item in reversed(range(n)):
        if bool(take[item, target]):
            mask[item] = "1"
            target -= problem["profits"][item]
    witness = "".join(mask)
    verified = independent_score(problem, witness)
    a.require(target == 0 and verified["feasible"] and verified["profit"] == optimum, "Profit DP witness failed")
    return {"method": "independent_profit_min_weight_dp", "optimum_profit": optimum,
            "witness_mask": witness, "witness_weight": verified["weight"], "witness_profit": verified["profit"],
            "unreachable_sentinel": unreachable, "tie_rule": "exclude_current_item_on_equal"}


def historical_source_identities():
    """Verify all sixty already-used tasks, including their actual source bytes."""
    from studies.knapsack_parameters.two_signal_mutation import banks as historical

    result = []
    for index in range(20):
        stage = "pilot" if index < 10 else "main"
        for label in CLASSES:
            source = historical.source_case(f"{label}-s{index:03d}", stage)
            result.append({"task": f"{label}-s{index:03d}", "sha256": source["source_identity"]["sha256"],
                           "problem_sha256": _problem_digest(source["problem"])})
    a.require(len(result) == 60, "Incomplete historical duplicate inventory")
    return result


def prepare_main_sources(directory, provenance):
    a.grant_for("prepare-main")
    old = historical_source_identities()
    seen_bytes = {row["sha256"] for row in old}
    seen_problems = {row["problem_sha256"] for row in old}
    directory, records = Path(directory), []
    for index in range(20, 30):
        for class_index, label in enumerate(CLASSES):
            task = f"{label}-s{index:03d}"
            relative = f"source/{SOURCE_DIRS[class_index]}/n00100/R01000/s{index:03d}.kp"
            url = f"https://raw.githubusercontent.com/likr/kplib/{SOURCE_COMMIT}/" + relative.removeprefix("source/")
            request = urllib.request.Request(url, headers={"User-Agent": "parameter-dynamics-source-audit"})
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
            digest = hashlib.sha256(raw).hexdigest()
            problem = parse_source(raw)
            canonical_digest = _problem_digest(problem)
            a.require(digest not in seen_bytes and canonical_digest not in seen_problems,
                      "New task duplicates a new or previously used source")
            seen_bytes.add(digest)
            seen_problems.add(canonical_digest)
            path = a.safe_child(directory, relative)
            a.require(not path.exists(), "Refusing to overwrite a source")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            capacity, profit = exact_capacity(problem), exact_profit(problem)
            a.require(capacity["optimum_profit"] == profit["optimum_profit"], "Independent exact solvers disagree")
            records.append({"task": task, "family": task[3:], "class_label": label,
                            "source_identity": {"path": relative, **a.identity(path)},
                            "problem_sha256": canonical_digest,
                            "exact": {"capacity": capacity, "profit": profit,
                                      "confirmed_optimum": capacity["optimum_profit"], "witness_verified": True}})
    registry = {**provenance, "schema": "parameter-dynamics-source-registry-v1", "source_commit": SOURCE_COMMIT,
                "tasks": 30, "records": records, "historical_duplicate_inventory": old,
                "new_search_calls": 0, "new_exact_solves": 60}
    a.write_json(directory / "source_registry.json", registry)
    return registry


def source_case(task, stage, source_directory=None):
    if stage == "pilot":
        from studies.knapsack_parameters.two_signal_mutation import banks as historical
        return historical.source_case(task, "pilot")
    a.require(stage == "main", "Unknown source stage")
    directory = Path(source_directory) if source_directory is not None else a.MODULE / "inputs" / "main"
    registry_path = directory / "source_registry.json"
    registry = a.read_json(registry_path)
    expected = {f"{label}-s{index:03d}" for index in range(20, 30) for label in CLASSES}
    a.require(registry.get("schema") == "parameter-dynamics-source-registry-v1" and
              registry.get("source_commit") == SOURCE_COMMIT and registry.get("tasks") == 30 and
              registry.get("new_search_calls") == 0 and registry.get("new_exact_solves") == 60 and
              len(registry["records"]) == 30 and {row["task"] for row in registry["records"]} == expected and
              len(registry.get("historical_duplicate_inventory", [])) == 60,
              "Incomplete new source audit")
    found = [row for row in registry["records"] if row["task"] == task]
    a.require(len(found) == 1, "Missing or duplicate new source task")
    row = found[0]
    identity = row["source_identity"]
    path = a.safe_child(directory, identity["path"])
    a.require(a.identity(path) == {"bytes": identity["bytes"], "sha256": identity["sha256"]}, "New source bytes changed")
    problem = parse_source(path.read_bytes())
    a.require(_problem_digest(problem) == row["problem_sha256"], "New problem changed")
    exact, optimum = row["exact"], row["exact"]["confirmed_optimum"]
    a.require(type(optimum) is int and optimum > 0 and exact.get("witness_verified") is True and
              exact["capacity"]["optimum_profit"] == exact["profit"]["optimum_profit"] == optimum,
              "Independent reference values disagree")
    for method in ("capacity", "profit"):
        score = independent_score(problem, exact[method]["witness_mask"])
        a.require(score["feasible"] and score["profit"] == optimum and score["weight"] == exact[method]["witness_weight"],
                  "Exact witness does not match source")
    return {"problem": problem, "optimum": optimum, "source_identity": identity,
            "registry_identity": a.identity(registry_path)}


def prepare(stage, output, provenance):
    import numpy as np

    conditions = expected_conditions(stage)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if stage == "main":
        prepare_main_sources(output, provenance)
    sources = {task: source_case(task, stage, output if stage == "main" else None)
               for task in dict.fromkeys(condition["task"] for condition in conditions)}
    rows = []
    for condition in conditions:
        started = perf_counter_ns()
        source = sources[condition["task"]]
        generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
            [97000, int(stage == "main"), condition["task_index"], condition["seed"]])))
        before = deepcopy(generator.bit_generator.state)
        masks = ([source["center_mask"]] * 30 if condition["start"] == "cloned" else
                 ["0" * 100] + ["".join(map(str, generator.integers(0, 2, size=100).tolist())) for _ in range(29)])
        scores_by_mask = {mask: independent_score(source["problem"], mask) for mask in dict.fromkeys(masks)}
        bank = {**provenance, "schema": "parameter-dynamics-bank-v1", "stage": stage, **condition,
                "problem": source["problem"], "source_identity": source["source_identity"],
                "registry_identity": source["registry_identity"], "initial_masks": masks,
                "initial_scores": [deepcopy(scores_by_mask[mask]) for mask in masks],
                "initialization_before": before, "initialization_after": deepcopy(generator.bit_generator.state),
                "physical_preparation_evaluations": len(scores_by_mask), "logical_initial_positions": 30,
                "preparation_ns": perf_counter_ns() - started, "new_search_calls": 0, "new_exact_solves": 0}
        validate_bank(bank, source)
        relative = f"banks/{condition['task']}-{condition['start']}-{condition['seed']}.json"
        a.write_json(output / relative, bank)
        rows.append({**condition, "path": relative, **a.identity(output / relative)})
    registry = {**provenance, "schema": "parameter-dynamics-bank-registry-v1", "stage": stage,
                "conditions": len(rows), "banks": rows, "preparation_seed": 97000,
                "new_search_calls": 0, "new_exact_solves": 60 if stage == "main" else 0,
                "independent_initial_score_checks": 30 * len(rows)}
    a.write_json(output / "bank_registry.json", registry)
    a.write_manifest(output)
    return registry


def validate_bank(bank, source):
    import numpy as np

    a.require(bank["stage"] in ("pilot", "main"), "Invalid bank stage")
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [97000, int(bank["stage"] == "main"), bank["task_index"], bank["seed"]])))
    before = deepcopy(generator.bit_generator.state)
    if bank["start"] == "cloned":
        a.require(bank["stage"] == "pilot", "Main cloned beginnings are not registered")
        expected_masks = [source["center_mask"]] * 30
    else:
        a.require(bank["start"] == "bank", "Unknown start")
        expected_masks = ["0" * 100]
        for _ in range(29):
            expected_masks.append("".join("1" if bit else "0" for bit in generator.integers(0, 2, size=100)))
    a.require(bank["initial_masks"] == expected_masks and
              a.canonical(bank["initialization_before"]) == a.canonical(before) and
              a.canonical(bank["initialization_after"]) == a.canonical(generator.bit_generator.state),
              "Initial bank or preparation generator changed")
    checked = []
    for mask in expected_masks:
        weight = profit = 0
        for index, bit in enumerate(mask):
            if bit == "1":
                weight += source["problem"]["weights"][index]
                profit += source["problem"]["profits"][index]
        checked.append({"weight": weight, "profit": profit, "feasible": weight <= source["problem"]["capacity"]})
    a.require(a.canonical(checked) == a.canonical(bank["initial_scores"]), "Independent initial scores disagree")
    a.require(type(bank.get("physical_preparation_evaluations")) is int and
              bank["physical_preparation_evaluations"] == len(set(expected_masks)) and
              type(bank.get("preparation_ns")) is int and bank["preparation_ns"] >= 0 and
              bank.get("logical_initial_positions") == 30 and bank.get("new_search_calls") == 0 and
              bank.get("new_exact_solves") == 0, "Wrong initial accounting")


def seal_frozen_files(stage, directory, freeze_sha, manifest):
    paths = [a.MODULE / f"frozen_{stage}_banks.json", directory / "file_manifest.json"]
    paths += [a.safe_child(directory, row["path"]) for row in manifest["files"]]
    queries = b"".join((freeze_sha + ":" + path.relative_to(a.ROOT).as_posix() + "\n").encode() for path in paths)
    stream = io.BytesIO(subprocess.check_output(["git", "cat-file", "--batch"], input=queries, cwd=a.ROOT))
    for path in paths:
        header = stream.readline().split()
        a.require(len(header) == 3 and header[1] == b"blob", "Frozen evidence blob missing")
        raw = stream.read(int(header[2]))
        a.require(stream.read(1) == b"\n" and raw == path.read_bytes(), "Evidence changed after data freeze")
    a.require(stream.read() == b"", "Unexpected freeze inventory")


def load_frozen_banks(stage, check_scores=True, selected_worker=None):
    directory = a.MODULE / "inputs" / stage
    manifest = a.verify_manifest(directory)
    frozen = a.read_json(a.MODULE / f"frozen_{stage}_banks.json")
    a.require(frozen.get("frozen") is True and frozen.get("stage") == stage and
              frozen.get("registry_identity") == a.identity(directory / "bank_registry.json"), "Banks are not frozen")
    registry = a.read_json(directory / "bank_registry.json")
    a.require(registry.get("schema") == "parameter-dynamics-bank-registry-v1" and registry.get("stage") == stage and
              registry.get("preparation_seed") == 97000 and registry.get("new_search_calls") == 0 and
              registry.get("new_exact_solves") == (60 if stage == "main" else 0), "Wrong bank registry")
    a.validate_source_receipt(registry, "prepare-" + stage)
    artifact = a.api(f"/actions/artifacts/{frozen['artifact_id']}")
    a.require(artifact.get("expired") is False and artifact.get("workflow_run", {}).get("id") == registry["run_id"] and
              artifact.get("digest") == "sha256:" + frozen["zip_sha256"], "Frozen bank artifact unavailable")
    freeze_sha = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", a.REL + f"frozen_{stage}_banks.json"],
                                         cwd=a.ROOT, text=True).strip()
    a.require(freeze_sha and freeze_sha != registry["implementation_sha"], "Separate data freeze commit required")
    changed = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", freeze_sha],
                                      cwd=a.ROOT, text=True).splitlines()
    a.require(changed and all(name.startswith(a.REL + f"inputs/{stage}/") or
                              name == a.REL + f"frozen_{stage}_banks.json" for name in changed),
              "Bank freeze must contain only its data")
    seal_frozen_files(stage, directory, freeze_sha, manifest)
    expected = {(row["task"], row["start"], row["seed"]): row for row in expected_conditions(stage)}
    allowed_workers = set(PILOT_TASKS if stage == "pilot" else a.MAIN_WORKERS)
    a.require(selected_worker is None or selected_worker in allowed_workers, "Unknown bank worker filter")
    seen, result = set(), []
    for row in registry["banks"]:
        key = row["task"], row["start"], row["seed"]
        a.require(key in expected and key not in seen, "Duplicate or foreign bank condition")
        seen.add(key)
        path = a.safe_child(directory, row["path"])
        a.require(row["path"] == f"banks/{row['task']}-{row['start']}-{row['seed']}.json" and
                  a.identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Bank bytes changed")
        bank = a.read_json(path)
        a.require(all(bank.get(field) == value for field, value in expected[key].items()), "Mixed bank condition")
        a.require(bank.get("implementation_sha") == registry["implementation_sha"] and
                  bank.get("source_manifest") == registry["source_manifest"] and bank.get("stage") == stage and
                  bank.get("schema") == "parameter-dynamics-bank-v1" and
                  len(bank["initial_masks"]) == len(bank["initial_scores"]) == 30 and
                  bank.get("logical_initial_positions") == 30 and bank.get("new_search_calls") == 0 and
                  bank.get("new_exact_solves") == 0, "Mixed bank provenance or accounting")
        if selected_worker is not None and bank["worker"] != selected_worker:
            continue
        if check_scores:
            source = source_case(bank["task"], stage)
            a.require(bank.get("problem") == source["problem"] and bank.get("source_identity") == source["source_identity"] and
                      bank.get("registry_identity") == source["registry_identity"], "Bank/source identity differs")
            validate_bank(bank, source)
        result.append(bank)
    a.require(seen == set(expected) and registry.get("conditions") == len(expected), "Incomplete bank rectangle")
    return result

"""New input binding; historical release checks are never weakened or edited.

The authorized probe reuses original bytes, not a fresh random beginning.
No held-out bank preparation or search is released by this module.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parent
OLD = ROOT / "studies/knapsack_parameters/adaptation_analysis"
CONDITIONS = (("UC-s000", "cloned"), ("SC-s005", "bank"))
HISTORICAL_FREEZE_SHA = "fc2b0e989ab7bb8149720657cf542c405c05be8c"
HISTORICAL_PREP_SHA = "b50a77eaf7006c879a650f4da6c7a3fa7c46c98b"
HISTORICAL_PREP_RUN = 39121501789
HOLDOUT_MANIFEST = "studies/knapsack_parameters/basic_parameters/inputs/holdout/data_manifest.json"
HOLDOUT_REGISTRY = "studies/knapsack_parameters/basic_parameters/evidence/run-39030726467/registry.json"
LOCAL_TASKS = frozenset(("UC-s011", "UC-s015", "UC-s016", "UC-s018", "UC-s019",
                         "WC-s010", "WC-s011", "WC-s012", "WC-s014", "WC-s015", "WC-s018", "WC-s019"))


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _protected(path):
    path = Path(path)
    rel = path.relative_to(ROOT).as_posix()
    digest = _read(MODULE / "registration.json")["protected_sha256"].get(rel)
    _require(digest is not None and _identity(path)["sha256"] == digest,
             "Unregistered or changed historical input: " + rel)


def probe_binding():
    """Metadata only: freeze these identities after green source checks."""
    files = [OLD / "frozen_banks.json", OLD / "inputs/pilot/bank_registry.json",
             OLD / "inputs/pilot/file_manifest.json"]
    files += [OLD / f"inputs/pilot/banks/{task}-{start}-86001.json" for task, start in CONDITIONS]
    rows = []
    for path in files:
        _protected(path)
        rows.append({"path": path.relative_to(ROOT).as_posix(), **_identity(path)})
    return {"schema": "knapsack-final-probe-input-binding-v1", "conditions": [list(x) for x in CONDITIONS],
            "search_seed": 86001, "historical_freeze_sha": HISTORICAL_FREEZE_SHA,
            "historical_preparation_sha": HISTORICAL_PREP_SHA,
            "historical_preparation_run": HISTORICAL_PREP_RUN, "files": rows,
            "new_preparation_evaluations": 0, "holdout_search_authorized": False}


def validate_probe_freeze(provenance):
    """A new data-only receipt binds the old bank bytes to the new green code."""
    path = MODULE / "frozen_probe_inputs.json"
    _require(path.is_file(), "Probe inputs have not been bound to the new green code")
    frozen = _read(path)
    from . import authority as a
    green = a.validated_tests()
    _require(frozen.get("frozen") is True and frozen.get("input_binding") == probe_binding() and
             frozen.get("source_manifest") == provenance.get("source_manifest") and
             frozen.get("source_manifest") == green.get("source_manifest") and
             frozen.get("implementation_sha") == green.get("implementation_sha") and
             frozen.get("green_tests_run_id") == green.get("run_id") and
             frozen.get("implementation_sha") != provenance.get("implementation_sha") and
             frozen.get("holdout_search_authorized") is False,
             "Stale or foreign probe input freeze")
    # This receipt must be committed separately after the tested implementation.
    relative = path.relative_to(ROOT).as_posix()
    freeze_sha = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", relative],
                                         cwd=ROOT, text=True).strip()
    _require(freeze_sha and freeze_sha != frozen["implementation_sha"], "Separate input freeze commit required")
    changed = subprocess.check_output(["git", "diff", "--name-only", freeze_sha + "^", freeze_sha],
                                      cwd=ROOT, text=True).splitlines()
    allowed = {relative, "studies/knapsack_parameters/final_study/frozen_tests.json"}
    _require(changed and all(name in allowed or
             name.startswith("studies/knapsack_parameters/final_study/evidence/") for name in changed),
             "Input binding commit must contain receipts/data only")
    return frozen


def load_probe_bank(task, start, validate_initial=True):
    from . import authority as a
    from studies.knapsack_parameters.mutation_population.driver import source_task, independent_score
    _require(os.environ.get("GITHUB_ACTIONS") == "true" and
             os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
             os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover",
             "Input verification is restricted to the registered CI repository and branch")
    _require((task, start) in CONDITIONS, "Only the two registered resource-probe conditions are admitted")
    probe_binding()
    root = OLD / "inputs/pilot"
    manifest = _read(root / "file_manifest.json")
    expected_names = set()
    for row in manifest["files"]:
        name = row["path"]
        _require(type(name) is str and not Path(name).is_absolute() and
                 ".." not in Path(name).parts and "\\" not in name and ":" not in name and
                 name not in expected_names, "Unsafe or duplicate historical bank member")
        expected_names.add(name)
        _require(_identity(root / name) == {"bytes": row["bytes"], "sha256": row["sha256"]},
                 "Corrupted historical bank member")
    _require(expected_names | {"file_manifest.json"} ==
             {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()},
             "Incomplete historical bank manifest")
    frozen = _read(OLD / "frozen_banks.json")
    registry = _read(root / "bank_registry.json")
    _require(_identity(root / "bank_registry.json") == frozen.get("registry_identity") and
             registry.get("run_id") == frozen.get("preparation_run_id") == HISTORICAL_PREP_RUN and
             registry.get("implementation_sha") == frozen.get("preparation_sha") == HISTORICAL_PREP_SHA and
             registry.get("scientific_search_calls") == 0 and registry.get("initial_conditions") == 8,
             "Historical preparation receipt differs")
    source = a.api(f"/actions/runs/{HISTORICAL_PREP_RUN}/attempts/1")
    artifact = a.api(f"/actions/artifacts/{frozen['artifact_id']}")
    _require(source.get("conclusion") == "success" and source.get("head_sha") == HISTORICAL_PREP_SHA and
             source.get("head_branch") == a.BRANCH and source.get("event") == "push" and
             source.get("path") == ".github/workflows/knapsack-adaptation-pilot.yml" and
             artifact.get("workflow_run", {}).get("id") == HISTORICAL_PREP_RUN and
             artifact.get("workflow_run", {}).get("head_sha") == HISTORICAL_PREP_SHA and
             artifact.get("digest") == "sha256:" + frozen["zip_sha256"] and artifact.get("expired") is False,
             "Historical preparation source/artifact unavailable or mismatched")
    relative = f"banks/{task}-{start}-86001.json"
    entries = [row for row in registry["banks"] if (row["task"], row["start"], row["seed"]) ==
               (task, start, 86001)]
    _require(len(entries) == 1 and entries[0]["path"] == relative and _identity(root / relative) ==
             {key: entries[0][key] for key in ("bytes", "sha256")}, "Bank is not the frozen input")
    original = subprocess.check_output(["git", "show", HISTORICAL_FREEZE_SHA + ":" +
        (root / relative).relative_to(ROOT).as_posix()], cwd=ROOT)
    _require(original == (root / relative).read_bytes(), "Input bytes differ from the historical freeze commit")
    bank = _read(root / relative)
    problem, case, source_identity = source_task(task)
    historical = _read(ROOT / "studies/knapsack_parameters/evidence/run-37637475385/registry.json")
    ti, si = historical["case_order"].index(task), ("cloned", "bank").index(start)
    _require(bank.get("problem") == problem and bank.get("source_identity") == source_identity and
             bank.get("task") == task and bank.get("start") == start and
             bank.get("search_seed") == 86001 and bank.get("preparation_seed") == 86000 and
             bank.get("task_index") == ti and bank.get("start_index") == si and
             len(bank.get("initial_masks", [])) == len(bank.get("initial_scores", [])) == 30,
             "Bank problem, mask count or stream identity differs")
    if validate_initial:
        import numpy as np
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([86000, 86001, ti, si, 0])))
        before = deepcopy(rng.bit_generator.state)
        masks = ([case["certificate"]["center"]["mask"]] * 30 if start == "cloned" else
                 ["0" * 100] + ["".join("1" if bit else "0" for bit in rng.random(100) < 0.5)
                                 for _ in range(29)])
        _require(bank["initial_masks"] == masks and bank["initial_scores"] ==
                 [independent_score(problem, mask) for mask in masks] and
                 bank.get("initialization_before") == before and
                 bank.get("initialization_after") == rng.bit_generator.state,
                 "Independent reconstruction of the frozen beginning differs")
    return bank


def holdout_inventory():
    """Verify existing identities/statuses, not solve or open any GA outcome."""
    for relative in (HOLDOUT_MANIFEST, HOLDOUT_REGISTRY):
        _protected(ROOT / relative)
    registry = _read(ROOT / HOLDOUT_REGISTRY)
    records = registry.get("records")
    _require(registry.get("completed") == registry.get("expected") == 30 and
             type(records) is list and len(records) == 30, "Incomplete exact preparation")
    expected = {f"{kind}-s{index:03d}" for kind in ("UC", "WC", "SC") for index in range(10, 20)}
    seen, local, families, global_count = set(), set(), set(), 0
    for row in records:
        task = row["instance_id"]
        _require(task in expected - seen and row.get("n") == 100 and row.get("failure") is None and
                 row.get("exact", {}).get("witness_verified") is True and
                 row["exact"]["capacity"]["optimum_profit"] == row["exact"]["profit"]["optimum_profit"] ==
                 row["exact"]["confirmed_optimum"], "Incomplete or duplicate exact reference")
        seen.add(task)
        certificate = row["certificate"]
        _require(certificate["neighbor_count"] == certificate["expected_neighbor_count"] == 5050 and
                 certificate["higher_feasible"] == 0 and certificate["local_maximum"] is True,
                 "Missing independent N2 preparation certificate")
        if row["status"] == "ADMITTED_STRICT_LOCAL":
            _require(certificate["strict"] is True and
                     certificate["center"]["profit"] < row["exact"]["confirmed_optimum"],
                     "Incorrect strict nonglobal admission")
            local.add(task)
            families.add(row["family"])
        else:
            _require(row["status"] == "EXCLUDED_GLOBAL_CENTER" and
                     certificate["center"]["profit"] == row["exact"]["confirmed_optimum"],
                     "Unregistered held-out admission status")
            global_count += 1
    _require(seen == expected and local == LOCAL_TASKS and len(families) == 8 and global_count == 18,
             "Held-out preparation composition differs")
    return {"tasks": 30, "families_random": 10, "nonglobal_centers": 12,
            "families_local": 8, "global_centers": 18, "local_tasks": sorted(local),
            "GA_outcomes_opened": False, "search_authorized": False}


def prepare_holdout_banks(*args, **kwargs):
    raise ValueError("BLOCKED_MAIN_RESOURCE_APPROVAL: held-out search/preparation not released by the probe")

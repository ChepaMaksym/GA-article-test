"""CI-only preparation of the sixteen preregistered, immutable starts."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

import numpy as np

from .contract import (AUTHORITY, REPO_ROOT, STUDY_ROOT, authenticate,
                       canonical_bytes, ci_only, file_identity, read_json,
                       require, sha256_bytes, source_manifest,
                       verify_file_manifest, write_file_manifest, write_json)
from .engine import evaluate, make_rngs
from .verifier import independent_score

TASKS = ("Flat", "OneMax", "Jump4", "Jump8", "UC-s000", "WC-s001", "SC-s005", "SC-s000")
STARTS = ("cloned", "bank")
METHODS = ("baseline", "directed", "repeated", "mutation_control")
BANK_SCHEMA = "diversity-pilot-bank-v1"
MANIFEST_SCHEMA = "diversity-pilot-banks-v1"
PROTOCOL = "GA-DIVERSITY-CROSSOVER-TECHNICAL-PILOT-V1"
SEED, N, MU = 70001, 100, 30


def _same(a, b):
    return canonical_bytes(a) == canonical_bytes(b)


def load_context():
    """Verify retained inputs without invoking historical CI authorization."""
    ci_only()
    from studies.knapsack_parameters.feasibility.frozen_inputs import verify_input_bundle
    instances, manifest = verify_input_bundle()
    provenance = read_json(STUDY_ROOT / "provenance.json")
    for row in provenance["retained_inputs"]:
        require(file_identity(REPO_ROOT / row["path"])["sha256"] == row["sha256"],
                "a retained historical input changed")
        require((REPO_ROOT / row["path"]).stat().st_size == row["bytes"], "retained input size mismatch")
    registry_path = REPO_ROOT / "studies/knapsack_parameters/evidence/run-37637475385/registry.json"
    registry = read_json(registry_path)
    require(registry["all_30_accounted"] is True and registry["case_count"] == 30 and
            registry["admitted_center_count"] == 14, "historical registry is incomplete")
    cases = {row["instance_id"]: row["payload"] for row in registry["cases"]}
    require(len(cases) == 30 and tuple(cases) == tuple(x.instance_id for x in instances),
            "case identities/order changed")
    objects = {x.instance_id: x for x in instances}
    problems, centers, annotations = {}, {}, {}
    for task in TASKS:
        if task == "Flat":
            problems[task] = {"kind": "flat", "n": N}
            centers[task] = "0" * N
            annotations[task] = {"center_type": "NEUTRAL", "escape_applicable": False}
        elif task == "OneMax":
            problems[task] = {"kind": "onemax", "n": N}
            centers[task] = "0" * N
            annotations[task] = {"center_type": "ZERO_START", "escape_applicable": False}
        elif task.startswith("Jump"):
            k = int(task[4:])
            problems[task] = {"kind": "jump", "n": N, "k": k}
            centers[task] = "1" * (N - k) + "0" * k
            annotations[task] = {"center_type": "JUMP_PLATEAU", "escape_applicable": True,
                                 "posthoc_known_optimum": N + k}
        else:
            obj, case = objects[task], cases[task]
            require(obj.n == N and case["n"] == N, "pilot input dimension changed")
            # Intentionally narrow: no global witness, optimum or neighbor certificate.
            problems[task] = {"kind": "knapsack", "n": N, "capacity": obj.capacity,
                              "weights": list(obj.weights), "profits": list(obj.profits)}
            centers[task] = case["certificate"]["center"]["mask"]
            annotations[task] = {"center_type": case["status"], "escape_applicable": True,
                                 "source_path": obj.source_path,
                                 "source_identity": case["source_identity"],
                                 "posthoc_known_optimum": case["exact"]["confirmed_optimum"]}
    require(cases["UC-s000"]["status"] == "ADMITTED_STRICT_LOCAL" and
            cases["WC-s001"]["status"] == "ADMITTED_STRICT_LOCAL" and
            cases["SC-s005"]["status"] == "ADMITTED_PLATEAU_LOCAL" and
            cases["SC-s000"]["status"] == "EXCLUDED_GLOBAL_CENTER", "pilot center types changed")
    return problems, centers, annotations, manifest


def generate_masks(task, center, rng, *, start, n=N, mu=MU):
    """Use the registered draw order; duplicates are deliberately retained."""
    require(start in STARTS and len(center) == n and set(center) <= {"0", "1"}, "invalid start")
    if start == "cloned":
        return [center] * mu
    masks = [center if task.startswith("Jump") else "0" * n]
    for _ in range(mu - 1):
        if task.startswith("Jump"):
            bits = np.ones(n, dtype=np.uint8)
            bits[rng.choice(n, int(task[4:]), replace=False)] = 0
        else:
            bits = (rng.random(n) < 0.5).astype(np.uint8)
        masks.append("".join(str(int(b)) for b in bits))
    return masks


def prepare(output, expected_sha):
    ci_only()
    identity = authenticate(expected_sha)
    from .contract import validate_tests_receipt
    validate_tests_receipt()
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()), "output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    problems, centers, annotations, data = load_context()
    source = source_manifest()
    records = []
    physical_total, verified_total = 0, 0
    for task_index, task in enumerate(TASKS):
        cache = {}  # Shared starts, but never shared across different objectives.
        for start_index, start in enumerate(STARTS):
            rngs = make_rngs(task_index, start_index, seed=SEED)
            rng = rngs["initialization"]
            before = copy.deepcopy(rng.bit_generator.state)
            masks = generate_masks(task, centers[task], rng, start=start)
            after = copy.deepcopy(rng.bit_generator.state)
            previous_count = len(cache)
            for mask in masks:
                if mask not in cache:
                    cache[mask] = evaluate(problems[task], mask)
            scores = [copy.deepcopy(cache[mask]) for mask in masks]
            for mask, score in zip(masks, scores, strict=True):
                require(_same(score, independent_score(problems[task], mask)), "initial evaluation mismatch")
            new_count = len(cache) - previous_count
            physical_total += new_count
            verified_total += len(masks)
            bank = {"schema_version": BANK_SCHEMA, "protocol_id": PROTOCOL,
                    "preparation_sha": expected_sha, "task": task, "task_index": task_index,
                    "start": start, "start_index": start_index, "seed": SEED, "n": N, "mu": MU,
                    "problem": problems[task], "masks": masks, "scores": scores,
                    "initialization_before": before, "initialization_after": after,
                    "physical_preparation_evaluations": new_count, "logical_initial_positions": MU,
                    "independent_verification_evaluations": MU,
                    "metadata": annotations[task], "source_fingerprint": sha256_bytes(canonical_bytes(source))}
            path = f"banks/{task}-{start}.json"
            write_json(output / path, bank)
            records.append({"task": task, "start": start, "path": path,
                            **file_identity(output / path)})
    write_json(output / "source_manifest.json", source)
    write_json(output / "provenance.json", identity)
    manifest = {"schema_version": MANIFEST_SCHEMA, "protocol_id": PROTOCOL,
                "preparation_sha": expected_sha, "seed": SEED, "count": len(records),
                "tasks": list(TASKS), "starts": list(STARTS), "banks": records,
                "physical_preparation_evaluations": physical_total,
                "independent_verification_evaluations": verified_total,
                "logical_initial_positions": MU * len(records),
                "initial_preparation_cache_only": True,
                "data_manifest_sha256": sha256_bytes(canonical_bytes(data)),
                "source_fingerprint": sha256_bytes(canonical_bytes(source))}
    write_json(output / "banks_manifest.json", manifest)
    write_file_manifest(output)
    return manifest


def validate_bank(bank, *, expected_task=None, expected_start=None):
    require(bank["schema_version"] == BANK_SCHEMA and bank["protocol_id"] == PROTOCOL, "wrong bank protocol/schema")
    task, start = bank["task"], bank["start"]
    require(task in TASKS and start in STARTS and bank["task_index"] == TASKS.index(task) and
            bank["start_index"] == STARTS.index(start), "invalid bank identity")
    require(expected_task is None or task == expected_task, "wrong bank task")
    require(expected_start is None or start == expected_start, "wrong bank start")
    require(bank["seed"] == SEED and bank["n"] == N and bank["mu"] == MU, "bank parameters changed")
    require(len(bank["masks"]) == len(bank["scores"]) == MU, "bank positions incomplete")
    require(all(isinstance(m, str) and len(m) == N and set(m) <= {"0", "1"} for m in bank["masks"]), "invalid bank mask")
    require(set(bank["problem"]) <= {"kind", "n", "k", "capacity", "weights", "profits"}, "oracle leaked into problem")
    require(0 <= bank["physical_preparation_evaluations"] <= len(set(bank["masks"])) and
            bank["logical_initial_positions"] == MU and
            bank["independent_verification_evaluations"] == MU, "bank accounting mismatch")
    # Independent replay: do not call the production RNG or mask generator.
    expected_rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [70001, TASKS.index(task), STARTS.index(start), 0])))
    require(_same(expected_rng.bit_generator.state, bank["initialization_before"]), "initialization stream seed changed")
    if task.startswith("Jump"):
        k = int(task[4:])
        center = "1" * (N - k) + "0" * k
    elif task in ("Flat", "OneMax"):
        center = "0" * N
    else:
        center = bank["masks"][0] if start == "cloned" else "0" * N
    if start == "cloned":
        expected_masks = [center for _ in range(MU)]
    else:
        expected_masks = [center if task.startswith("Jump") else "0" * N]
        for _ in range(MU - 1):
            if task.startswith("Jump"):
                zero_positions = set(int(i) for i in expected_rng.choice(N, int(task[4:]), replace=False))
                expected_masks.append("".join("0" if i in zero_positions else "1" for i in range(N)))
            else:
                draws = expected_rng.random(N)
                expected_masks.append("".join("1" if float(value) < 0.5 else "0" for value in draws))
    require(expected_masks == bank["masks"] and _same(expected_rng.bit_generator.state, bank["initialization_after"]),
            "bank masks/draw order differ from registered preparation")
    for mask, score in zip(bank["masks"], bank["scores"], strict=True):
        require(_same(score, independent_score(bank["problem"], mask)), "bank score mismatch")
    return bank


def load_banks(directory=None):
    ci_only()
    directory = Path(directory or STUDY_ROOT / "pilot_inputs")
    verify_file_manifest(directory)
    manifest = read_json(directory / "banks_manifest.json")
    transport = read_json(directory / "frozen_transport.json")
    from .contract import validate_artifact_receipt
    validate_artifact_receipt(transport["prepare_run_id"], transport["prepare_artifact_id"],
                              transport["preparation_sha"], transport["prepare_zip_sha256"])
    require(transport["banks_manifest_sha256"] == file_identity(directory / "banks_manifest.json")["sha256"] and
            transport["source_manifest_sha256"] == file_identity(directory / "source_manifest.json")["sha256"] and
            transport["preparation_sha"] == manifest["preparation_sha"], "prepared artifact transport mismatch")
    require(type(transport["prepare_run_id"]) is int and type(transport["prepare_artifact_id"]) is int and
            transport["prepare_run_id"] > 0 and transport["prepare_artifact_id"] > 0 and
            isinstance(transport["prepare_zip_sha256"], str) and len(transport["prepare_zip_sha256"]) == 64,
            "incomplete prepared artifact provenance")
    require(manifest["schema_version"] == MANIFEST_SCHEMA and manifest["protocol_id"] == PROTOCOL and
            manifest["count"] == 16 and manifest["seed"] == SEED, "wrong bank manifest")
    require(manifest["tasks"] == list(TASKS) and manifest["starts"] == list(STARTS), "bank order changed")
    require(manifest["source_fingerprint"] == sha256_bytes(canonical_bytes(source_manifest())), "prepared source hashes do not match current code")
    problems, centers, annotations, _ = load_context()
    result = {}
    for row in manifest["banks"]:
        identity = (row["task"], row["start"])
        require(identity not in result, "duplicate bank identity")
        expected_path = f"banks/{identity[0]}-{identity[1]}.json"
        require(row["path"] == expected_path, "unsafe bank path")
        require(file_identity(directory / expected_path)["sha256"] == row["sha256"], "bank hash mismatch")
        bank = validate_bank(read_json(directory / expected_path), expected_task=identity[0], expected_start=identity[1])
        require(_same(bank["problem"], problems[identity[0]]) and _same(bank["metadata"], annotations[identity[0]]),
                "bank task/oracle metadata do not match retained inputs")
        if identity[1] == "cloned":
            require(bank["masks"] == [centers[identity[0]]] * MU, "cloned historical center changed")
        require(bank["preparation_sha"] == manifest["preparation_sha"] and
                bank["source_fingerprint"] == manifest["source_fingerprint"], "mixed bank provenance")
        result[identity] = bank
    require(set(result) == {(t, s) for t in TASKS for s in STARTS}, "missing bank")
    for task in TASKS:
        seen = set()
        for start in STARTS:
            bank = result[(task, start)]
            fresh = set(bank["masks"]) - seen
            require(bank["physical_preparation_evaluations"] == len(fresh), "shared preparation cache accounting changed")
            seen.update(bank["masks"])
    require(sum(b["physical_preparation_evaluations"] for b in result.values()) ==
            manifest["physical_preparation_evaluations"], "preparation total mismatch")
    return result, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    prepare(args.output, args.expected_sha)


if __name__ == "__main__":
    main()

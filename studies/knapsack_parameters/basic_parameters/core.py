"""Pure adapters to the unchanged classical GA and its independent oracle."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re

import numpy as np

from ..feasibility.data_audit import parse_instance
from ..feasibility.frozen_inputs import DATA_MANIFEST_SHA256
from ..ga_study.engine import Config, make_rngs, run_search
from ..ga_study.oracle import verify_search
from .contract import BRANCH, PROTOCOL, REPOSITORY, canonical, read_json, require

CLASS_CODES = {"UC": 0, "WC": 1, "SC": 2}
DIRECTORIES = {"UC": "00Uncorrelated", "WC": "01WeaklyCorrelated", "SC": "02StronglyCorrelated"}
CHANNELS = ("initialization", "selection", "crossover", "mutation", "tie")
MUTATION_NUMERATORS = (0.0, 0.5, 1.0, 3.0, 8.0)
CROSSOVER_PROBABILITIES = (0.0, 0.25, 0.5, 0.9, 1.0)
POPULATION_SIZES = (10, 20, 30, 50, 100)
DEVELOPMENT_SEEDS = tuple(range(81001, 81011))
PILOT_SEED = 83001
PILOT_TASKS = ("UC-s000", "WC-s001", "SC-s005")
BANK_SIZE = 100
BUDGET = 5000


def ci_only():
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific execution is CI-only")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Wrong CI authority")


def grid():
    """The registered 125 fixed configurations; n is always 100."""
    return tuple(Config(m, c, size) for m in MUTATION_NUMERATORS
                 for c in CROSSOVER_PROBABILITIES for size in POPULATION_SIZES)


def pilot_grid():
    return tuple(Config(m, c, size) for m in (0.0, 8.0)
                 for c in (0.0, 1.0) for size in (10, 100)) + (Config(1.0, 0.9, 30),)


def baseline():
    return Config(1.0, 0.9, 30)


def task_ids():
    return tuple(f"{label}-s{index:03d}" for label in CLASS_CODES for index in range(10))


def validate_development_instance(instance):
    require(instance.n == 100 and instance.class_label in CLASS_CODES and
            type(instance.index) is int and instance.index in range(10) and
            instance.family == f"s{instance.index:03d}" and instance.instance_id in task_ids(),
            "Only registered 100-item development tasks are released")


def parse_task(task_id):
    match = re.fullmatch(r"(UC|WC|SC)-s([0-9]{3})", str(task_id))
    require(match is not None, "Invalid task identity")
    label, index = match[1], int(match[2])
    require(index in range(10), "Holdout search is not released")
    return label, index


def load_instance(root, task_id):
    """Authenticate one original development file without historical CLI calls."""
    label, index = parse_task(task_id)
    directory = Path(root) / "studies/knapsack_parameters/inputs"
    raw_manifest = (directory / "data_manifest.json").read_bytes()
    require(hashlib.sha256(raw_manifest).hexdigest() == DATA_MANIFEST_SHA256,
            "Historical data manifest changed")
    manifest = read_json(directory / "data_manifest.json")
    source_path = f"{DIRECTORIES[label]}/n00100/R01000/s{index:03d}.kp"
    entries = [row for row in manifest["source_files"] if row["source_path"] == source_path]
    require(len(entries) == 1, "Source missing or duplicated")
    raw = (directory / "source" / source_path).read_bytes()
    require(len(raw) == entries[0]["bytes"] and hashlib.sha256(raw).hexdigest() == entries[0]["sha256"],
            "Original source bytes changed")
    return parse_instance(raw, source_path, class_label=label, family=f"s{index:03d}", index=index)


def _independent_rng_replay(instance, seed):
    """Independent SeedSequence construction, not production make_rngs."""
    require(type(seed) is int and seed >= 0, "Seed must be a nonnegative exact integer")
    require(instance.class_label in CLASS_CODES and type(instance.index) is int,
            "Unknown RNG task identity")
    states = {}
    masks = np.zeros((BANK_SIZE, instance.n), dtype=np.uint8)
    for channel, name in enumerate(CHANNELS):
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
            [CLASS_CODES[instance.class_label], instance.index, seed, channel])))
        if channel == 0:
            masks[1:] = (rng.random((BANK_SIZE - 1, instance.n)) < .5).astype(np.uint8)
        states[name] = deepcopy(rng.bit_generator.state)
    return states, masks


def expected_rng_states(instance, seed):
    return _independent_rng_replay(instance, seed)[0]


def verify_seed_binding(instance, seed, bank_metadata, result):
    """Close the oracle's intentional gap between logged states and claimed seed."""
    require(bank_metadata["instance_id"] == instance.instance_id and
            bank_metadata["repeat_seed"] == seed and bank_metadata["bank_size"] == BANK_SIZE,
            "Bank/seed identity mismatch")
    expected, masks = _independent_rng_replay(instance, seed)
    require(bank_metadata["rng_after"] == expected["initialization"], "Bank generator state not seed-bound")
    summary = result["summary"]
    require(summary["rng_states_start"] == expected and
            result["generations"][0]["rng_states"] == expected,
            "Search initial RNG states do not match the claimed seed/bank")
    require(bank_metadata["mask_sha256"] == hashlib.sha256(masks.tobytes()).hexdigest() and
            np.array_equal(result["requests"]["masks"][:summary["N"]], masks[:summary["N"]]),
            "Search initial masks do not match the claimed seed/bank")
    require(summary["rng_state_sha256_start"] == hashlib.sha256(canonical(expected)).hexdigest(),
            "Seed-bound state checksum mismatch")
    return True


def run_checked(instance, config, arrays, bank_metadata, seed, *, budget=BUDGET):
    """Run and replay; smaller limits exist only for CI mechanism fixtures."""
    ci_only()
    validate_development_instance(instance)
    require(config in grid(), "Unregistered configuration")
    size = config.population_size
    masks = arrays["masks"][:size].copy()
    scores = {key: arrays[key][:size].copy() for key in ("weight", "profit", "feasible")}
    rngs = make_rngs(CLASS_CODES[instance.class_label], instance.index, seed)
    rngs["initialization"].bit_generator.state = deepcopy(bank_metadata["rng_after"])
    result = run_search(instance, config, masks, scores, rngs, budget=budget)
    verify_seed_binding(instance, seed, bank_metadata, result)
    verdict = verify_search(instance, config, result, initial_masks=masks, initial_scores=scores)
    require(verdict["status"] == "PASS_REPLAY", "Independent replay rejected the run")
    return result, verdict

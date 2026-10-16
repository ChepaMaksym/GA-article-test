"""100-mask banks, independent scalar/seed replay, and immutable inventories."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path, PurePosixPath

import numpy as np

from ..ga_study.engine import evaluate_masks, make_rngs
from .contract import PROTOCOL, canonical, identity, manifest, read_json, require, write_json
from .core import (BANK_SIZE, CLASS_CODES, DEVELOPMENT_SEEDS, PILOT_SEED, PILOT_TASKS,
                   ci_only, load_instance, task_ids, validate_development_instance)

SCHEMA = "knapsack-basic-bank-v1"
MANIFEST_SCHEMA = "knapsack-basic-banks-v1"


def bank_identities():
    return tuple((task, seed) for task in task_ids() for seed in DEVELOPMENT_SEEDS) + tuple(
        (task, PILOT_SEED) for task in PILOT_TASKS)


def create_bank(instance, seed, provenance=None):
    ci_only()
    validate_development_instance(instance)
    require(type(seed) is int and (instance.instance_id, seed) in bank_identities(), "Unregistered bank identity")
    rng = make_rngs(CLASS_CODES[instance.class_label], instance.index, seed)["initialization"]
    before = deepcopy(rng.bit_generator.state)
    masks = np.zeros((BANK_SIZE, instance.n), dtype=np.uint8)
    masks[1:] = (rng.random((BANK_SIZE - 1, instance.n)) < 0.5).astype(np.uint8)
    after = deepcopy(rng.bit_generator.state)
    arrays = {"masks": masks, **evaluate_masks(instance, masks)}
    metadata = {"schema_version": SCHEMA, "protocol_id": PROTOCOL,
                "instance_id": instance.instance_id, "repeat_seed": seed,
                "n": instance.n, "bank_size": BANK_SIZE, "physical_evaluations": BANK_SIZE,
                "independent_verification_evaluations": BANK_SIZE,
                "rng_entropy": [CLASS_CODES[instance.class_label], instance.index, seed, 0],
                "rng_before": before, "rng_after": after,
                "rng_before_sha256": hashlib.sha256(canonical(before)).hexdigest(),
                "rng_after_sha256": hashlib.sha256(canonical(after)).hexdigest(),
                "mask_sha256": hashlib.sha256(masks.tobytes()).hexdigest(),
                "bit_order": "original source row order", "provenance": deepcopy(provenance)}
    validate_bank(instance, seed, arrays, metadata)
    return arrays, metadata


def validate_bank(instance, seed, arrays, metadata):
    """No production generator helper/evaluator is used by this checker."""
    ci_only()
    validate_development_instance(instance)
    require(type(seed) is int and (instance.instance_id, seed) in bank_identities(), "Unregistered bank identity")
    require(set(arrays) == {"masks", "weight", "profit", "feasible"}, "Wrong bank array schema")
    require(instance.n == 100 and metadata["schema_version"] == SCHEMA and
            metadata["protocol_id"] == PROTOCOL and metadata["instance_id"] == instance.instance_id and
            metadata["repeat_seed"] == seed and metadata["n"] == instance.n and
            metadata["bank_size"] == metadata["physical_evaluations"] == BANK_SIZE and
            metadata["independent_verification_evaluations"] == BANK_SIZE, "Wrong bank identity/accounting")
    expected_dtypes = {"masks": np.dtype("uint8"), "weight": np.dtype("int64"),
                       "profit": np.dtype("int64"), "feasible": np.dtype("bool")}
    for key, value in arrays.items():
        require(isinstance(value, np.ndarray) and value.dtype == expected_dtypes[key] and
                value.shape == ((BANK_SIZE, instance.n) if key == "masks" else (BANK_SIZE,)),
                "Wrong bank shape/dtype")
    masks = arrays["masks"]
    require(np.all((masks == 0) | (masks == 1)) and not np.any(masks[0]), "Bank masks are not binary/empty-first")
    entropy = [CLASS_CODES[instance.class_label], instance.index, seed, 0]
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy)))
    require(metadata["rng_entropy"] == entropy and metadata["rng_before"] == rng.bit_generator.state,
            "Bank generator initial state/entropy mismatch")
    # Scalar-row draws independently reconstruct the same PCG64 stream.
    expected = np.zeros_like(masks)
    for row in range(1, BANK_SIZE):
        expected[row] = (rng.random(instance.n) < 0.5).astype(np.uint8)
    require(np.array_equal(masks, expected) and metadata["rng_after"] == rng.bit_generator.state,
            "Bank masks/final state do not match the seed")
    for label in ("before", "after"):
        require(metadata[f"rng_{label}_sha256"] == hashlib.sha256(canonical(metadata[f"rng_{label}"])).hexdigest(),
                "Bank RNG checksum mismatch")
    require(metadata["mask_sha256"] == hashlib.sha256(masks.tobytes()).hexdigest(), "Bank mask checksum mismatch")
    for row, bits in enumerate(masks):
        w = sum(int(bit) * item for bit, item in zip(bits, instance.weights, strict=True))
        v = sum(int(bit) * item for bit, item in zip(bits, instance.profits, strict=True))
        require((int(arrays["weight"][row]), int(arrays["profit"][row]), bool(arrays["feasible"][row])) ==
                (w, v, w <= instance.capacity), "Independent initial objective check failed")
    return True


def prepare_banks(root, output, provenance):
    ci_only()
    require(provenance["protocol_id"] == PROTOCOL, "Wrong preparation protocol")
    output = Path(output).resolve()
    require(not output.is_relative_to(Path(root).resolve()), "Preparation evidence must be outside checkout")
    require(not output.exists() or not any(output.iterdir()), "Existing bank evidence is not overwritten")
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    instances = {task: load_instance(root, task) for task in task_ids()}
    for task, seed in bank_identities():
        arrays, metadata = create_bank(instances[task], seed, provenance)
        folder = output / task / str(seed)
        folder.mkdir(parents=True)
        np.savez_compressed(folder / "bank.npz", **arrays)
        write_json(folder / "bank.json", metadata)
        entries.append({"instance_id": task, "repeat_seed": seed,
                        "arrays_path": (folder / "bank.npz").relative_to(output).as_posix(),
                        "metadata_path": (folder / "bank.json").relative_to(output).as_posix(),
                        "arrays": identity(folder / "bank.npz"), "metadata": identity(folder / "bank.json")})
        write_json(output / "progress.json", {"completed_banks": len(entries), "expected_banks": 303})
    value = {"schema_version": MANIFEST_SCHEMA, "protocol_id": PROTOCOL,
             "bank_count": 303, "instance_count": 30, "bank_size": BANK_SIZE,
             "physical_evaluations": 30300, "independent_verification_evaluations": 30300,
             "provenance": deepcopy(provenance), "banks": entries}
    write_json(output / "banks_manifest.json", value)
    manifest(output)
    return value


def load_bank(bundle, instance, seed, *, expected_manifest_sha256=None):
    ci_only()
    bundle = Path(bundle).resolve()
    value = read_json(bundle / "banks_manifest.json")
    require(value["schema_version"] == MANIFEST_SCHEMA and value["protocol_id"] == PROTOCOL and
            value["bank_count"] == 303 and value["bank_size"] == BANK_SIZE and
            value["physical_evaluations"] == 30300, "Wrong bank registry")
    if expected_manifest_sha256 is not None:
        require(identity(bundle / "banks_manifest.json")["sha256"] == expected_manifest_sha256,
                "Bank registry differs from frozen receipt")
    found = [(row["instance_id"], row["repeat_seed"]) for row in value["banks"]]
    require(len(found) == 303 and len(set(found)) == 303 and set(found) == set(bank_identities()),
            "Bank registry identities are incomplete/duplicated")
    matches = [row for row in value["banks"] if (row["instance_id"], row["repeat_seed"]) == (instance.instance_id, seed)]
    require(len(matches) == 1, "Requested bank is absent")
    row = matches[0]
    members = []
    for field, descriptor in (("arrays_path", "arrays"), ("metadata_path", "metadata")):
        relative = row[field]
        pure = PurePosixPath(relative)
        require(not pure.is_absolute() and ".." not in pure.parts and ":" not in relative and "\\" not in relative,
                "Unsafe bank path")
        path = bundle / pure
        require(path.resolve().is_relative_to(bundle) and not path.is_symlink() and identity(path) == row[descriptor],
                "Bank member checksum mismatch")
        members.append(path)
    with np.load(members[0], allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    metadata = read_json(members[1])
    require(metadata["provenance"] == value["provenance"], "Mixed preparation provenance")
    validate_bank(instance, seed, arrays, metadata)
    return arrays, metadata

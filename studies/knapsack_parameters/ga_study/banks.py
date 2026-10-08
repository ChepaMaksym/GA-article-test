"""CI-only initial-bank preparation and immutable bank verification."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path

import numpy as np

from .contract import (CLASS_CODES, DATA_SHA, PROTOCOL_ID, REGISTRY_SHA, canonical_bytes,
                       file_identity, load_context, output_directory, read_json, require,
                       safe_member, sha256_bytes, verify_file_manifest, write_file_manifest,
                       write_json)
from .engine import evaluate_masks, make_rngs


def create_bank(instance, seed):
    rng = make_rngs(CLASS_CODES[instance.class_label], instance.index, seed)["initialization"]
    before = deepcopy(rng.bit_generator.state)
    masks = np.zeros((50, instance.n), dtype=np.uint8)
    masks[1:] = (rng.random((49, instance.n)) < 0.5).astype(np.uint8)
    after = deepcopy(rng.bit_generator.state)
    scores = evaluate_masks(instance, masks)
    return {"masks": masks, **scores}, {"schema_version": "ga-knapsack-bank-v1",
            "instance_id": instance.instance_id, "repeat_seed": seed, "bank_size": 50,
            "physical_evaluations": 50, "rng_before": before, "rng_after": after,
            "rng_before_sha256": sha256_bytes(canonical_bytes(before)),
            "rng_after_sha256": sha256_bytes(canonical_bytes(after)),
            "rng_entropy": [CLASS_CODES[instance.class_label], instance.index, seed, 0],
            "first_mask": "empty feasible mask; no RNG draws", "bit_order": "original source rows"}


def validate_bank(instance, arrays, metadata, seed):
    require(set(arrays) == {"masks", "weight", "profit", "feasible"}, "unexpected bank arrays")
    masks = arrays["masks"]
    require(masks.dtype == np.uint8 and masks.shape == (50, instance.n) and np.all((masks == 0) | (masks == 1)), "invalid bank masks")
    require(np.all(masks[0] == 0), "first bank mask must be empty")
    require(metadata["instance_id"] == instance.instance_id and metadata["repeat_seed"] == seed and metadata["physical_evaluations"] == 50, "bank identity mismatch")
    for name in ("weight", "profit"):
        require(arrays[name].dtype == np.int64 and arrays[name].shape == (50,), "bank integer array mismatch")
    require(arrays["feasible"].dtype == np.bool_ and arrays["feasible"].shape == (50,), "bank feasibility array mismatch")
    # Independent scalar integer sums; no production evaluator or regenerated masks.
    for index, mask in enumerate(masks):
        weight = sum(int(bit) * int(value) for bit, value in zip(mask, instance.weights, strict=True))
        profit = sum(int(bit) * int(value) for bit, value in zip(mask, instance.profits, strict=True))
        require(weight == int(arrays["weight"][index]) and profit == int(arrays["profit"][index]) and
                bool(arrays["feasible"][index]) == (weight <= instance.capacity), "bank score mismatch")
    for label in ("before", "after"):
        require(sha256_bytes(canonical_bytes(metadata[f"rng_{label}"])) == metadata[f"rng_{label}_sha256"], "bank RNG state hash mismatch")
    return True


def prepare_banks(expected_sha, output):
    instances, cases, _, identity = load_context(expected_sha)
    output = output_directory(output)
    rows = []
    for instance in instances:
        for seed in range(51001, 51031):
            arrays, metadata = create_bank(instance, seed)
            validate_bank(instance, arrays, metadata, seed)
            directory = output / "banks" / instance.instance_id / str(seed)
            directory.mkdir(parents=True)
            np.savez_compressed(directory / "bank.npz", **arrays)
            metadata.update(provenance=identity)
            write_json(directory / "bank.json", metadata)
            rows.append({"instance_id": instance.instance_id, "repeat_seed": seed,
                         "arrays_path": (directory / "bank.npz").relative_to(output).as_posix(),
                         "metadata_path": (directory / "bank.json").relative_to(output).as_posix(),
                         "arrays": file_identity(directory / "bank.npz"), "metadata": file_identity(directory / "bank.json")})
    require(len(rows) == 900, "bank registry must contain exactly 900 banks")
    manifest = {"schema_version": "ga-knapsack-banks-manifest-v1", "protocol_id": PROTOCOL_ID,
                "bank_count": 900, "instance_count": 30, "physical_evaluations": 45000,
                "data_manifest_sha256": DATA_SHA, "registry_sha256": REGISTRY_SHA,
                "provenance": identity, "banks": rows}
    write_json(output / "banks_manifest.json", manifest)
    write_file_manifest(output)
    return manifest


def load_bank(bundle, instance, seed, *, descriptor=None):
    bundle = Path(bundle)
    manifest = read_json(bundle / "banks_manifest.json")
    require(manifest["schema_version"] == "ga-knapsack-banks-manifest-v1" and
            manifest["protocol_id"] == PROTOCOL_ID and manifest["bank_count"] == 900 and
            len(manifest["banks"]) == 900 and manifest["data_manifest_sha256"] == DATA_SHA and
            manifest["registry_sha256"] == REGISTRY_SHA, "bank registry incomplete or incompatible")
    identities = [(row["instance_id"], row["repeat_seed"]) for row in manifest["banks"]]
    require(len(set(identities)) == 900, "duplicate bank identities")
    if descriptor:
        require(file_identity(bundle / "banks_manifest.json")["sha256"] == descriptor["banks_manifest_sha256"], "frozen bank manifest hash mismatch")
    matches = [row for row in manifest["banks"] if row["instance_id"] == instance.instance_id and row["repeat_seed"] == seed]
    require(len(matches) == 1, "bank missing or duplicated")
    row = matches[0]
    arrays_path = safe_member(bundle, row["arrays_path"])
    metadata_path = safe_member(bundle, row["metadata_path"])
    require(file_identity(arrays_path) == row["arrays"] and file_identity(metadata_path) == row["metadata"], "bank member checksum mismatch")
    with np.load(arrays_path, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    metadata = read_json(metadata_path)
    validate_bank(instance, arrays, metadata, seed)
    return arrays, metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = prepare_banks(args.expected_sha, args.output)
    print(f"Prepared and independently verified {result['bank_count']} banks; GA was not run")


if __name__ == "__main__":
    main()

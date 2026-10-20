"""Registered known starts, with a separately reconstructed bank audit.

No computation runs on import. Preparation and tests belong to GitHub Actions.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import numpy as np


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _identity(case_ordinal, seed):
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0
           for value in (case_ordinal, seed)):
        raise ValueError("bank identity requires nonnegative integer ordinal and seed")


def prepare_bank(instance, case_ordinal: int, seed: int):
    """Thirty masks, zero first; these scores never consume search RNGs."""
    _identity(case_ordinal, seed)
    if not isinstance(instance.n, int) or instance.n < 1:
        raise ValueError("positive instance dimension required")
    if len(instance.weights) != instance.n or len(instance.profits) != instance.n:
        raise ValueError("inconsistent item dimension")
    if any(not isinstance(v, (int, np.integer)) or isinstance(v, (bool, np.bool_))
           or v <= 0 for v in tuple(instance.weights) + tuple(instance.profits)):
        raise ValueError("positive integer item values required")
    if not isinstance(instance.capacity, int) or isinstance(instance.capacity, bool) or instance.capacity < 0:
        raise ValueError("nonnegative integer capacity required")
    if max(sum(map(int, instance.weights)), sum(map(int, instance.profits)),
           instance.capacity) > np.iinfo(np.int64).max:
        raise ValueError("bank exact integer storage bound exceeded")
    generator = np.random.Generator(np.random.PCG64(
        np.random.SeedSequence([93000, case_ordinal, seed])))
    start = deepcopy(generator.bit_generator.state)
    masks = np.zeros((30, instance.n), dtype=np.uint8)
    masks[1:] = generator.random((29, instance.n)) < 0.5
    weight = masks.astype(np.int64) @ np.asarray(instance.weights, dtype=np.int64)
    profit = masks.astype(np.int64) @ np.asarray(instance.profits, dtype=np.int64)
    bank = {"masks": masks, "weight": weight, "profit": profit,
            "feasible": weight <= instance.capacity}
    payload = {name: value.tolist() for name, value in bank.items()}
    metadata = {"schema_version": "knapsack-stagnation-bank-v1",
                "case_ordinal": case_ordinal, "search_seed": seed,
                "seed_sequence": [93000, case_ordinal, seed],
                "population_size": 30, "n": instance.n,
                "physical_initial_evaluations": 30,
                "logical_initial_evaluations": 30,
                "rng_state_start": start,
                "rng_state_terminal": deepcopy(generator.bit_generator.state),
                "bank_sha256": hashlib.sha256(_canonical(payload)).hexdigest()}
    return bank, metadata


def verify_bank(instance, case_ordinal: int, seed: int, bank, metadata):
    """Independent draw reconstruction and original-order Python integer sums."""
    _identity(case_ordinal, seed)
    if set(bank) != {"masks", "weight", "profit", "feasible"}:
        raise ValueError("unexpected bank arrays")
    masks = np.asarray(bank["masks"])
    if masks.shape != (30, instance.n) or not np.all((masks == 0) | (masks == 1)):
        raise ValueError("bank mask dimension or bit values invalid")
    if any(np.asarray(bank[key]).shape != (30,) for key in ("weight", "profit", "feasible")):
        raise ValueError("bank score dimension invalid")
    if any(np.asarray(bank[key]).dtype.kind not in "iu" for key in ("weight", "profit")):
        raise ValueError("bank objective arrays must be integer")
    if np.asarray(bank["feasible"]).dtype.kind != "b":
        raise ValueError("bank feasibility must be Boolean")
    bit_generator = np.random.PCG64(np.random.SeedSequence([93000, case_ordinal, seed]))
    expected_start = deepcopy(bit_generator.state)
    independent_rng = np.random.Generator(bit_generator)
    expected_masks = [[0] * instance.n]
    for _ in range(29):
        expected_masks.append([int(float(value) < 0.5)
                               for value in independent_rng.random(instance.n)])
    if masks.tolist() != expected_masks:
        raise ValueError("bank differs from registered draws or zero first mask")
    expected_weight, expected_profit = [], []
    for bits in expected_masks:
        expected_weight.append(sum(int(w) for bit, w in zip(bits, instance.weights) if bit))
        expected_profit.append(sum(int(p) for bit, p in zip(bits, instance.profits) if bit))
    if np.asarray(bank["weight"]).tolist() != expected_weight:
        raise ValueError("bank weight differs from independent integer sum")
    if np.asarray(bank["profit"]).tolist() != expected_profit:
        raise ValueError("bank profit differs from independent integer sum")
    if np.asarray(bank["feasible"]).tolist() != [w <= instance.capacity for w in expected_weight]:
        raise ValueError("bank feasibility inconsistent")
    payload = {key: np.asarray(value).tolist() for key, value in bank.items()}
    expected_metadata = {
        "schema_version": "knapsack-stagnation-bank-v1",
        "case_ordinal": case_ordinal, "search_seed": seed,
        "seed_sequence": [93000, case_ordinal, seed], "population_size": 30,
        "n": instance.n, "physical_initial_evaluations": 30,
        "logical_initial_evaluations": 30, "rng_state_start": expected_start,
        "rng_state_terminal": deepcopy(bit_generator.state),
        "bank_sha256": hashlib.sha256(_canonical(payload)).hexdigest(),
    }
    if metadata != expected_metadata:
        raise ValueError("bank metadata, RNG provenance or hash mismatch")
    return {"status": "PASS_BANK", "verified_initial_evaluations": 30,
            "bank_sha256": expected_metadata["bank_sha256"]}

"""Pinned corpus auditing and prefix-consistent initial banks outside the GA.

No network request or search is performed here. The external immutable-URL
fetcher supplies source_snapshot.json; the audit verifies the retained bytes.
Preparation, certification and bank validation are separate measured phases.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

import numpy as np


SOURCE_COMMIT = "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c"
SOURCE_BASE = f"https://raw.githubusercontent.com/likr/kplib/{SOURCE_COMMIT}/"
SIZES = (100, 200, 500)
CLASSES = (("UC", "00Uncorrelated"), ("WC", "01WeaklyCorrelated"), ("SC", "02StronglyCorrelated"))
PILOT_CASES = (("UC", 0), ("WC", 1), ("SC", 5))
BANK_SCHEMA = "knapsack-population-prefix-bank-v1"
CORPUS_SCHEMA = "knapsack-population-corpus-v1"
README_BLOB = {"source_path": "README.md", "git_blob_sha1": "0ab81c1f1b67e0a9696658950ecb02f3e8b443ad", "bytes": 1309}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "Input preparation is allowed only in GitHub Actions")


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": _sha(raw)}


def _integer(value, name, minimum=0):
    _require(type(value) is int and value >= minimum, f"{name} must be an integer >= {minimum}")


def _validate_problem(problem):
    _require(type(problem) is dict and set(problem) == {"n", "capacity", "profits", "weights"},
             "Only the four kernel problem fields are accepted")
    _integer(problem["n"], "n", 1)
    _integer(problem["capacity"], "capacity")
    for name in ("weights", "profits"):
        _require(isinstance(problem[name], (list, tuple)) and len(problem[name]) == problem["n"],
                 "Wrong item-vector length")
        _require(all(type(value) is int and value > 0 for value in problem[name]),
                 "Item entries must be positive non-boolean integers")


def parse_kp_bytes(raw, n):
    """Read original profit/weight rows strictly, preserving their source order."""
    _require(type(raw) is bytes, "KPLIB input must be raw bytes")
    _integer(n, "expected n", 1)
    rows = [line.split() for line in raw.decode("utf-8", errors="strict").splitlines() if line.strip()]
    _require(len(rows) == n + 2, "Unexpected number of nonempty KPLIB rows")
    _require(len(rows[0]) == len(rows[1]) == 1, "n and capacity need one integer each")
    _require(all(len(row) == 2 for row in rows[2:]), "Each item row must contain profit and weight")
    _require(all(re.fullmatch(r"[0-9]+", item) for row in rows for item in row),
             "Only unsigned decimal source integers are accepted")
    count, capacity = int(rows[0][0]), int(rows[1][0])
    _require(count == n and capacity > 0, "Source dimension or capacity is invalid")
    problem = {"n": count, "capacity": capacity,
               "profits": [int(row[0]) for row in rows[2:]],
               "weights": [int(row[1]) for row in rows[2:]]}
    _validate_problem(problem)
    return problem


def problem_sha256(problem):
    """Identify exact vectors in source order, including dimension and capacity."""
    _validate_problem(problem)
    return _sha(canonical_bytes(problem))


def unordered_problem_sha256(problem):
    """Detect equivalent source problems even when item rows were permuted."""
    _validate_problem(problem)
    value = {"n": problem["n"], "capacity": problem["capacity"],
             "items": sorted(zip(problem["profits"], problem["weights"], strict=True))}
    return _sha(canonical_bytes(value))


def task_specs(mode):
    """Return the registered task identities; never substitute missing source files."""
    _require(mode in ("pilot", "train", "holdout"), "Unknown corpus mode")
    result = []
    for size_index, n in enumerate(SIZES):
        cases = PILOT_CASES if mode == "pilot" else tuple(
            (label, index) for label, _ in CLASSES
            for index in (range(10) if mode == "train" else range(50, 60)))
        for label, index in cases:
            class_index = tuple(name for name, _ in CLASSES).index(label)
            source_path = f"{dict(CLASSES)[label]}/n{n:05d}/R01000/s{index:03d}.kp"
            result.append({"task_id": f"n{n:05d}-{label}-s{index:03d}", "n": n,
                           "class_label": label, "family": f"s{index:03d}", "index": index,
                           "task_index": size_index * 300 + class_index * 100 + index,
                           "source_path": source_path, "url": SOURCE_BASE + source_path})
    return result


def _git_blob_sha1(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _pinned_inventory():
    """Read the independently retained complete immutable Git-tree inventory."""
    path = Path(__file__).with_name("source_tree_manifest.json")
    tree = json.loads(path.read_text(encoding="utf-8"))
    _require(tree.get("schema") == "ga-knapsack-population-source-tree-v1"
             and tree.get("repository") == "likr/kplib" and tree.get("commit") == SOURCE_COMMIT,
             "Wrong registered Git-tree identity")
    rows = tree.get("files")
    _require(type(rows) is list and len(rows) == 180, "Registered Git-tree inventory is incomplete")
    expected = {row["source_path"] for mode in ("train", "holdout") for row in task_specs(mode)}
    _require({row.get("source_path") for row in rows} == expected, "Registered Git-tree paths differ from the full design")
    inventory = {}
    for row in rows:
        _require(type(row.get("git_blob_sha1")) is str and re.fullmatch(r"[0-9a-f]{40}", row["git_blob_sha1"]),
                 "Malformed registered Git blob identity")
        _integer(row.get("bytes"), "registered source bytes", 1)
        inventory[row["source_path"]] = dict(row)
    inventory["README.md"] = dict(README_BLOB)
    return inventory


def _safe_file(source_root, relative):
    pure = PurePosixPath(relative)
    _require(not pure.is_absolute() and all(part not in ("", ".", "..") for part in pure.parts)
             and ":" not in relative and "\\" not in relative, "Unsafe source-relative path")
    root = Path(source_root).absolute()
    _require(root.is_dir() and not root.is_symlink(), "Source root must be a real directory")
    path = root / pure
    _require(path.is_file() and path.resolve().is_relative_to(root.resolve()), "Source path is absent or escapes its root")
    cursor = path
    while cursor != root:
        _require(not cursor.is_symlink(), "Symbolic-link source members are not accepted")
        cursor = cursor.parent
    return path


def audit_corpus(source_root, mode, *, provenance=None, previous_manifests=()):
    """Audit offline immutable-download evidence, identities and exact duplicates.

    The snapshot contains source_commit and files with source_path, url,
    sha256 and bytes. Transport provenance is retained without treating local
    hashes alone as proof of upstream availability. Holdout admission also
    requires a completed training manifest for cross-stage duplicate checks.
    """
    _ci_only()
    specs = task_specs(mode)
    snapshot_path = _safe_file(source_root, "source_snapshot.json")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    _require(type(snapshot) is dict and snapshot.get("source_commit") == SOURCE_COMMIT,
             "Wrong pinned KPLIB revision")
    _require(type(snapshot.get("files")) is list, "Source snapshot needs a file inventory")
    rows = snapshot["files"]
    _require(all(type(row) is dict and {"source_path", "url", "sha256", "bytes", "git_blob_sha1"} <= set(row) for row in rows),
             "Source snapshot descriptors are incomplete")
    paths = [row["source_path"] for row in rows]
    _require(all(type(path) is str for path in paths) and len(paths) == len(set(paths)),
             "Source snapshot paths are invalid or duplicated")
    entries = {row["source_path"]: row for row in rows}
    pinned = _pinned_inventory()
    for relative, row in entries.items():
        _require(relative in pinned and row["url"] == SOURCE_BASE + relative
                 and row["git_blob_sha1"] == pinned[relative]["git_blob_sha1"]
                 and row["bytes"] == pinned[relative]["bytes"], "Snapshot metadata differs from the pinned complete Git-tree inventory")
    _require("README.md" in entries, "The pinned data-license declaration is absent")
    needed = ["README.md"] + [row["source_path"] for row in specs]
    files, cases = [], []
    for relative in needed:
        _require(relative in entries, "A registered input is absent from the frozen source snapshot")
        descriptor = entries[relative]
        _require(descriptor["url"] == SOURCE_BASE + relative, "Source URL is not the pinned immutable URL")
        _integer(descriptor["bytes"], "source byte count", 1)
        _require(type(descriptor["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]),
                 "Malformed source checksum")
        path = _safe_file(source_root, relative)
        identity = _identity(path)
        _require(identity == {"bytes": descriptor["bytes"], "sha256": descriptor["sha256"]},
                 "Source bytes differ from the frozen immutable-download snapshot")
        raw = path.read_bytes()
        _require(_git_blob_sha1(raw) == pinned[relative]["git_blob_sha1"], "Source bytes do not match the registered immutable Git blob")
        files.append({"source_path": relative, "url": descriptor["url"],
                      "git_blob_sha1": pinned[relative]["git_blob_sha1"], **identity})
        if relative == "README.md":
            _require("Creative Commons Attribution 4.0 International License" in raw.decode("utf-8"),
                     "The pinned source README does not declare the expected data license")
            continue
        spec = next(row for row in specs if row["source_path"] == relative)
        problem = parse_kp_bytes(raw, spec["n"])
        cases.append({**spec, "source_sha256": identity["sha256"], "source_bytes": identity["bytes"],
                      "problem": problem, "problem_sha256": problem_sha256(problem),
                      "unordered_problem_sha256": unordered_problem_sha256(problem),
                      "original_item_order_preserved": True})
    prior_cases = []
    for manifest in previous_manifests:
        _require(type(manifest) is dict and manifest.get("schema") == CORPUS_SCHEMA
                 and manifest.get("status") == "AUDITED_LOCAL_PINNED_BYTES"
                 and manifest.get("source_commit") == SOURCE_COMMIT, "Invalid previous corpus audit")
        prior_cases.extend(manifest["cases"])
    if mode == "holdout":
        _require(any(value.get("mode") == "train" and len(value.get("cases", [])) == 90
                     for value in previous_manifests), "Holdout audit needs the complete training manifest")
    unique_ids = set()
    signatures = {}
    duplicates = []
    for row in prior_cases + cases:
        identifier = row["task_id"]
        if identifier in unique_ids:
            # A pilot case can intentionally reappear in the training corpus.
            existing = next(value for value in prior_cases + cases if value["task_id"] == identifier)
            _require(existing["problem_sha256"] == row["problem_sha256"], "A task identity has inconsistent vectors")
            continue
        unique_ids.add(identifier)
        signature = row["unordered_problem_sha256"]
        if signature in signatures:
            duplicates.append({"tasks": [signatures[signature], identifier], "kind": "same_items_and_capacity_allowing_row_permutation"})
        else:
            signatures[signature] = identifier
    _require(not duplicates, "Exact or reordered duplicate problems invalidate corpus admission")
    _require(len(cases) == (9 if mode == "pilot" else 90), "Registered corpus is incomplete")
    return {"schema": CORPUS_SCHEMA, "status": "AUDITED_LOCAL_PINNED_BYTES", "mode": mode,
            "source_commit": SOURCE_COMMIT, "source_snapshot": _identity(snapshot_path),
            "source_tree_manifest": _identity(Path(__file__).with_name("source_tree_manifest.json")),
            "source_files": files, "cases": cases, "case_count": len(cases),
            "license": {"identifier": "CC-BY-4.0", "attribution_url": f"https://github.com/likr/kplib/tree/{SOURCE_COMMIT}"},
            "duplicate_audit": {"compared_unique_tasks": len(unique_ids), "duplicates": duplicates,
                                "cross_stage_checked": bool(previous_manifests),
                                "criterion": "exact_instance_equivalence_not_statistical_independence"},
            "provenance": deepcopy(provenance), "ga_search_performed": False,
            "exact_certification_performed": False}


def _score(problem, mask):
    weight = sum(value for value, bit in zip(problem["weights"], mask, strict=True) if bit == "1")
    profit = sum(value for value, bit in zip(problem["profits"], mask, strict=True) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def make_bank(problem, seed, task_index, bank_size=25000):
    """Prepare one known bank; every population uses its matching prefix.

    Changing bank_size never changes an already defined prefix. This generator
    is independent of the six streams consumed by the search operators.
    """
    _ci_only()
    _validate_problem(problem)
    _integer(seed, "seed")
    _integer(task_index, "task_index")
    _integer(bank_size, "bank_size", 2)
    _require(bank_size <= 25000, "Bank exceeds the registered population domain")
    entropy = [seed, task_index, problem["n"], 0]
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy)))
    before = deepcopy(generator.bit_generator.state)
    random_bits = (generator.random((bank_size - 1, problem["n"])) < 0.5).astype(np.uint8)
    masks = ["0" * problem["n"]]
    masks.extend((row + np.uint8(48)).tobytes().decode("ascii") for row in random_bits)
    after = deepcopy(generator.bit_generator.state)
    scores = [_score(problem, mask) for mask in masks]
    bank = {"masks": masks, "scores": scores}
    metadata = {"schema": BANK_SCHEMA, "n": problem["n"], "problem_sha256": problem_sha256(problem),
                "bank_size": bank_size, "seed": seed, "task_index": task_index,
                "rng_entropy": entropy, "rng_before": before, "rng_after": after,
                "mask_sha256": _sha("".join(masks).encode("ascii")),
                "scores_sha256": _sha(canonical_bytes(scores)),
                "physical_preparation_evaluations": bank_size,
                "search_operator_rng_consumed": False, "empty_mask_first": True,
                "item_order": "original_source_order", "bank_verification_performed": False}
    return bank, metadata


def validate_bank(problem, bank, metadata):
    """Independently replay row-sized draws and scalar scores, without the builder."""
    _ci_only()
    _validate_problem(problem)
    _require(type(bank) is dict and set(bank) == {"masks", "scores"}, "Wrong known-bank fields")
    _require(type(metadata) is dict and metadata.get("schema") == BANK_SCHEMA, "Wrong bank schema")
    size = metadata.get("bank_size")
    _integer(size, "bank_size", 2)
    _require(size <= 25000 and metadata.get("n") == problem["n"]
             and metadata.get("problem_sha256") == problem_sha256(problem), "Wrong bank problem identity")
    _require(type(bank["masks"]) is list and type(bank["scores"]) is list
             and len(bank["masks"]) == len(bank["scores"]) == size, "Wrong bank lengths")
    _integer(metadata.get("seed"), "seed")
    _integer(metadata.get("task_index"), "task_index")
    entropy = [metadata["seed"], metadata["task_index"], problem["n"], 0]
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy)))
    _require(metadata.get("rng_entropy") == entropy and metadata.get("rng_before") == rng.bit_generator.state,
             "Wrong bank initial random state")
    for position in range(size):
        expected = "0" * problem["n"] if position == 0 else "".join(
            "1" if value < 0.5 else "0" for value in rng.random(problem["n"]))
        actual = bank["masks"][position]
        _require(type(actual) is str and actual == expected, "A bank mask differs from its registered random stream")
        measured_weight = sum(w for i, w in enumerate(problem["weights"]) if actual[i] == "1")
        measured_profit = sum(v for i, v in enumerate(problem["profits"]) if actual[i] == "1")
        score = {"weight": measured_weight, "profit": measured_profit,
                 "feasible": measured_weight <= problem["capacity"]}
        actual_score = bank["scores"][position]
        _require(type(actual_score) is dict and set(actual_score) == {"weight", "profit", "feasible"}
                 and type(actual_score["weight"]) is int and type(actual_score["profit"]) is int
                 and type(actual_score["feasible"]) is bool and actual_score == score,
                 "An independently recomputed bank score differs")
    _require(metadata.get("rng_after") == rng.bit_generator.state, "Wrong bank final random state")
    _require(metadata.get("mask_sha256") == _sha("".join(bank["masks"]).encode("ascii"))
             and metadata.get("scores_sha256") == _sha(canonical_bytes(bank["scores"])), "Wrong bank checksum")
    _require(metadata.get("physical_preparation_evaluations") == size
             and metadata.get("search_operator_rng_consumed") is False, "Wrong bank preparation accounting")
    return {"status": "VERIFIED_BANK", "masks_verified": size,
            "independent_verification_evaluations": size, "search_evaluations": 0}

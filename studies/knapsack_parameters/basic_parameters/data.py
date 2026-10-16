"""Pinned holdout-byte audit and separate preparation; never called by GA."""
from __future__ import annotations

from itertools import combinations
from pathlib import Path
import time

from ..feasibility.data_audit import (CLASSES, SOURCE_SHA, check_license,
    download_source, parse_instance)
from ..feasibility.prepare_case import prepare_instance
from .contract import ROOT, MODULE, identity, read_json, require, write_json


def source_path(label, index):
    directory = dict(CLASSES)[label]
    return f"{directory}/n00100/R01000/s{index:03d}.kp"


def load_old():
    base = ROOT / "studies/knapsack_parameters/inputs"
    manifest = read_json(base / "data_manifest.json")
    require(identity(base / "data_manifest.json")["sha256"] ==
            "528fee8da7d7cb776fb851e6a05949133830e9533c4091cbb4e8698ac19fb0df", "Old data identity changed")
    instances = []
    for row in manifest["source_files"]:
        path = base / row["path"]
        require(identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Old source bytes changed")
        if row["source_path"] == "README.md":
            continue
        spec = next(p for p in manifest["instances"] if p["source_path"] == row["source_path"])
        instances.append(parse_instance(path.read_bytes(), row["source_path"],
            class_label=spec["class_label"], family=spec["family"], index=spec["index"]))
    require(len(instances) == 30, "Incomplete old data")
    return instances


def duplicate_audit(instances):
    """Exhaustive exact identity checks, not a claim of statistical independence."""
    identities = [i.instance_id for i in instances]
    require(len(identities) == len(set(identities)), "Duplicate task identity")
    exact = []
    family = []
    for a, b in combinations(instances, 2):
        fields = {"weights_equal": a.weights == b.weights,
                  "profits_equal": a.profits == b.profits,
                  "capacity_equal": a.capacity == b.capacity}
        if all(fields.values()):
            exact.append({"tasks": [a.instance_id, b.instance_id], **fields})
        if a.family == b.family:
            family.append({"family": a.family, "tasks": [a.instance_id, b.instance_id], **fields})
    return {"exact_duplicates": exact, "same_family_comparisons": family,
            "pairs_checked": len(instances) * (len(instances) - 1) // 2,
            "inference": "Exact equality only; independence is not established"}


def audit(output, provenance, fetcher=download_source):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    require(not (output / "data_manifest.json").exists(), "Existing audit is not overwritten")
    old = load_old()
    specs = [(None, None, "README.md")] + [(label, index, source_path(label, index))
        for label, _ in CLASSES for index in range(10, 20)]
    rows, parsed = [], []
    for label, index, path in specs:
        raw, attempts = fetcher(path)
        target = output / "source" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        row = {"source_path": path, "path": "source/" + path,
               **identity(target), "download_attempts": attempts}
        if label is None:
            license_info = check_license(raw)
        else:
            instance = parse_instance(raw, path, class_label=label, family=f"s{index:03d}", index=index)
            parsed.append(instance)
            row.update(task_id=instance.instance_id, class_label=label, index=index,
                       family=instance.family, n=instance.n, capacity=instance.capacity,
                       original_item_order=True)
        rows.append(row)
    require(len(parsed) == 30, "Holdout source audit incomplete")
    report = {"protocol_id": provenance["protocol_id"], "provenance": provenance,
              "status": "PASS_BYTE_AUDIT", "source_commit": SOURCE_SHA,
              "source_files": rows, "new_tasks": 30, "old_tasks_checked": 30,
              "license": license_info, **duplicate_audit(old + parsed),
              "ga_holdout_outcomes_opened": False, "dp_performed": False}
    # Exact duplicate test-vs-development would invalidate unqualified holdout use.
    report["development_holdout_duplicates"] = [p for p in report["exact_duplicates"]
        if (int(p["tasks"][0][-3:]) < 10) != (int(p["tasks"][1][-3:]) < 10)]
    report["holdout_search_eligible"] = not report["development_holdout_duplicates"]
    write_json(output / "data_manifest.json", report)
    return report


def frozen_holdout():
    directory = MODULE / "inputs/holdout"
    receipt = read_json(MODULE / "inputs/frozen_holdout.json")
    require(identity(directory / "data_manifest.json")["sha256"] == receipt["data_manifest_sha256"], "Holdout manifest mismatch")
    value = read_json(directory / "data_manifest.json")
    require(value["status"] == "PASS_BYTE_AUDIT" and value["new_tasks"] == 30, "Holdout not audited")
    instances = []
    for row in value["source_files"]:
        path = directory / row["path"]
        require(identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Holdout bytes mismatch")
        if "task_id" in row:
            instances.append(parse_instance(path.read_bytes(), row["source_path"],
                class_label=row["class_label"], family=row["family"], index=row["index"]))
    return value, instances


def certify(output, provenance):
    value, instances = frozen_holdout()
    output = Path(output)
    records = []
    for instance in instances:
        source = next(r for r in value["source_files"] if r.get("task_id") == instance.instance_id)
        record = prepare_instance(instance, provenance, source,
            output / "cases" / instance.instance_id, deadline=time.monotonic() + 1740)
        records.append(record)
        write_json(output / "registry.json", {"protocol_id": provenance["protocol_id"],
            "provenance": provenance, "expected": 30, "completed": len(records), "records": records})
    valid = {"ADMITTED_STRICT_LOCAL", "ADMITTED_PLATEAU_LOCAL", "EXCLUDED_GLOBAL_CENTER", "EXCLUDED_PREPARATION_CAP"}
    require(len(records) == 30 and all(r["status"] in valid for r in records), "Holdout preparation incomplete")
    return records

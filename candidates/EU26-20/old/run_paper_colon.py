#!/usr/bin/env python3
"""Run one independent clean-room Colon OLD paper profile."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

from paper_profile import baseline_accuracy, load_colon, run_paper_profile

EXPECTED_COMMIT = "d24e61e78ac197ad75342e8f4be5d63d17bd9e7a"
RESULT_PREFIX = "EU26_20_PAPER_RESULT="


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.STDOUT
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    root = args.upstream.resolve()
    commit = git(root, "rev-parse", "HEAD")
    if commit != EXPECTED_COMMIT:
        raise SystemExit(f"unexpected upstream commit: {commit}")

    dataset = root / "Datasets" / "Colon.xlsx"
    features_path = (
        root
        / "The top 50 features selected from each ranker (CEI, MI, and FR) and their concatenation (features.npy)"
        / "Colon"
        / "features.npy"
    )
    source = root / "CMF-AGAwER.py"
    for path in (dataset, features_path, source):
        if not path.is_file():
            raise SystemExit(f"required upstream artifact missing: {path}")

    x, y, search_space = load_colon(root)
    baseline = baseline_accuracy(x, y)
    if baseline != 0.69:
        raise SystemExit(f"Colon baseline changed: {baseline}")

    result = run_paper_profile(x, y, search_space, args.seed)
    labels, counts = np.unique(y, return_counts=True)
    result.update(
        {
            "upstream_commit": commit,
            "dataset_rows": int(x.shape[0]),
            "raw_features": int(x.shape[1]),
            "class_labels": [int(value) for value in labels.tolist()],
            "class_counts": [int(value) for value in counts.tolist()],
            "search_space_size": len(search_space),
            "baseline_accuracy": baseline,
            "source_sha256": sha256(source),
            "dataset_sha256": sha256(dataset),
            "features_sha256": sha256(features_path),
        }
    )

    if result["dataset_rows"] != 62 or result["raw_features"] != 2000:
        raise SystemExit("Colon structure mismatch")
    if result["class_counts"] != [22, 40] or result["search_space_size"] != 128:
        raise SystemExit("Colon class/search-space mismatch")
    if not result["features"] or len(result["features"]) != result["subset_length"]:
        raise SystemExit("invalid final feature subset")
    if len(result["features"]) != len(set(result["features"])):
        raise SystemExit("duplicate final features")
    if result["nfe"] <= 0 or result["iterations"] < 0:
        raise SystemExit("invalid effort accounting")

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    compact = dict(result)
    compact.pop("trace", None)
    print(RESULT_PREFIX + json.dumps(compact, sort_keys=True))


if __name__ == "__main__":
    main()

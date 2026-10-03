"""Authenticate two fixed historical archives and reaggregate without searches.

Only GitHub Actions executes this entrypoint. Original extracted files are
retained byte-for-byte in the new artifact; no historical seed is regenerated.
The two profiles have different estimands and are never pooled with each other
or with prospective bridge seeds.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from common_bridge.fetch_source_artifacts import (
    GitHubReader, _file_sha256, _load_json, _verify_artifact, _write_json,
)

REPOSITORY = "ChepaMaksym/GA-article-test"
SOURCES = {
    "source_compatible": {
        "id": 9260332711,
        "name": "eu26-21-old-vs-hybrid-1-thirty-seed-v2-corrected",
        "digest": "sha256:8efc217b690f1c3e6698cb9aa0f55207d93f10e6390087c6e9f425d935bea21a",
        "run_id": 31934816828,
        "head_sha": "62b267f850b9bdd09934ca27507c272c35cb34e3",
    },
    "corrected_official_uci": {
        "id": 9297184026,
        "name": "eu26-21-corrected-applied-secure-final",
        "digest": "sha256:13d2f691eefb46067d3cdffbad4c22c032c429ce91600a33addbd3f5887bbdeb",
        "run_id": 32049437836,
        "head_sha": "9006a9f0f0a339dbc27cfb95aa51031dfcad1447",
    },
}


def seed_rows(directory: Path) -> list[dict]:
    paths = sorted(directory.rglob("seed-*.json"))
    if len(paths) != 30:
        raise ValueError(f"expected exactly 30 historical rows, found {len(paths)}")
    rows = [_load_json(path) for path in paths]
    seeds = [row.get("seed") if isinstance(row, dict) else None for row in rows]
    if any(type(seed) is not int for seed in seeds):
        raise ValueError("historical seed must be an integer")
    if sorted(seeds) != list(range(1, 31)):
        raise ValueError("historical seed ledger must be exactly 1..30 without duplicates")
    return sorted(rows, key=lambda row: row["seed"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("historical evidence verification is CI-only")
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise SystemExit("historical evidence repository mismatch")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    api = GitHubReader(os.environ.get("GH_TOKEN", ""))
    verified = {}
    for profile, source in SOURCES.items():
        identity = {key: source[key] for key in ("id", "name", "digest")}
        metadata = _verify_artifact(
            api, repository=REPOSITORY, source_run_id=source["run_id"],
            source_head_sha=source["head_sha"], expected=identity, output_dir=output,
        )
        rows = seed_rows(output / source["name"])
        if profile == "source_compatible":
            from hybrid_1.audit_validation import evaluate_strict
            from hybrid_1.paired_comparison import DEFAULT_TARGETS
            report = evaluate_strict(rows, DEFAULT_TARGETS)
            primary = {key: report[key] for key in ("h1", "h2", "h3")}
        else:
            from corrected_applied.secure_aggregate import evaluate_secure
            report = evaluate_secure(rows, environment_profile="corrected_secure_2026")
            primary = {key: report[key] for key in
                       ("h1_corrected", "h2_corrected", "h8_reset_ablation")}
        report_path = output / f"{profile}-reaggregated.json"
        _write_json(report_path, report)
        verified[profile] = {
            "source": source, "verification": metadata, "seed_count": 30,
            "report": report_path.name, "report_sha256": _file_sha256(report_path),
            "primary": primary,
        }
        print(json.dumps({"profile": profile, "primary": primary}, sort_keys=True))
    manifest = {
        "schema": "eu26-21-historical-evidence-audit-v1",
        "repository": REPOSITORY,
        "audit_sha": os.environ["GITHUB_SHA"],
        "audit_run_id": int(os.environ["GITHUB_RUN_ID"]),
        "audit_run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
        "seed_rows_regenerated": False, "optimizer_rerun": False,
        "profiles_pooled": False, "prospective_bridge_included": False,
        "profiles": verified,
    }
    _write_json(output / "historical-audit-manifest.json", manifest)
    print("PASS: both fixed archives authenticated and separately reaggregated")


if __name__ == "__main__":
    main()

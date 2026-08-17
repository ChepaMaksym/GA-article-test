#!/usr/bin/env python3
"""Strict aggregation for the modern corrected applied environment.

The statistical decisions are delegated to :mod:`corrected_applied.aggregate`.
This layer adds fail-closed checks for package versions, 40-bit masks, selected-
index consistency, and exclusion of raw instance-weight index 24.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from . import aggregate as base

RUNS = 30
EXPECTED_ENVIRONMENT_PROFILE = "corrected_secure_2026"
EXPECTED_PACKAGES = {
    "numpy": "2.4.6",
    "pandas": "3.0.3",
    "scipy": "1.17.1",
    "scikit-learn": "1.9.0",
    "matplotlib": "3.11.1",
    "pillow": "12.3.0",
    "deap": "1.4.4",
    "pyswarms": "1.3.0",
}
RESULT_KEYS = (
    "baseline",
    "old",
    "hybrid_h1",
    "hybrid_reset",
    "hybrid_no_reset",
)


def _hex_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} must be a 64-character digest")
    if any(character not in "0123456789abcdef" for character in value.lower()):
        raise ValueError(f"{label} is not hexadecimal")
    return value.lower()


def _validate_mask_result(
    result: Mapping[str, Any], *, seed: int, label: str
) -> None:
    mask = result.get("selected_mask")
    if not isinstance(mask, list) or len(mask) != 40:
        raise ValueError(f"seed {seed}: {label} mask must contain 40 bits")
    normalized = []
    for value in mask:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"seed {seed}: {label} mask has non-integer bit")
        if value not in (0, 1):
            raise ValueError(f"seed {seed}: {label} mask is not binary")
        normalized.append(value)
    selected = [index for index, bit in enumerate(normalized) if bit]
    if not selected:
        raise ValueError(f"seed {seed}: {label} mask is empty")

    official = result.get("official_test_metrics")
    if not isinstance(official, Mapping):
        raise ValueError(f"seed {seed}: {label} official metrics missing")
    if official.get("selected_predictive_indices") != selected:
        raise ValueError(f"seed {seed}: {label} indices disagree with mask")
    if int(official.get("selected_feature_count", -1)) != len(selected):
        raise ValueError(f"seed {seed}: {label} count disagrees with mask")
    raw_indices = official.get("selected_raw_indices")
    names = official.get("selected_feature_names")
    if not isinstance(raw_indices, list) or len(raw_indices) != len(selected):
        raise ValueError(f"seed {seed}: {label} raw-index ledger invalid")
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value < 41
        for value in raw_indices
    ):
        raise ValueError(f"seed {seed}: {label} raw index invalid")
    if len(set(raw_indices)) != len(raw_indices):
        raise ValueError(f"seed {seed}: {label} raw indices duplicated")
    if 24 in raw_indices:
        raise ValueError(
            f"seed {seed}: {label} selected forbidden instance-weight index 24"
        )
    if not isinstance(names, list) or len(names) != len(selected):
        raise ValueError(f"seed {seed}: {label} name ledger invalid")


def validate_secure_row(
    row: Mapping[str, Any],
    seed: int,
    *,
    environment_profile: str = EXPECTED_ENVIRONMENT_PROFILE,
) -> None:
    base.validate_row(row, seed)
    protocol = row["protocol"]
    assert isinstance(protocol, Mapping)
    if protocol.get("environment_profile") != environment_profile:
        raise ValueError(f"seed {seed}: environment profile mismatch")
    python_version = protocol.get("python_version")
    if not isinstance(python_version, str) or not python_version.startswith("3.11."):
        raise ValueError(f"seed {seed}: Python version mismatch")
    if protocol.get("package_versions") != EXPECTED_PACKAGES:
        raise ValueError(f"seed {seed}: package-version ledger mismatch")
    if int(row.get("initial_population", -1)) != 50:
        raise ValueError(f"seed {seed}: initial population mismatch")
    _hex_digest(row.get("initial_masks_sha256"), f"seed {seed} initial masks")

    baseline = row["baseline"]
    old = row["old"]
    h1 = row["hybrid_h1"]
    reset = row["hybrid_reset"]
    no_reset = row["hybrid_no_reset"]
    assert all(
        isinstance(value, Mapping)
        for value in (baseline, old, h1, reset, no_reset)
    )
    if h1.get("workers") != 4 or h1.get("reset") is not True or h1.get("budget") != 400:
        raise ValueError(f"seed {seed}: H1 configuration mismatch")
    if (
        reset.get("reset") is not True
        or no_reset.get("reset") is not False
        or reset.get("workers") != 1
        or no_reset.get("workers") != 1
        or reset.get("budget") != 2500
        or no_reset.get("budget") != 2500
    ):
        raise ValueError(f"seed {seed}: reset ablation mismatch")
    if int(reset.get("reset_events", -1)) < 0:
        raise ValueError(f"seed {seed}: invalid reset-event count")
    if int(no_reset.get("reset_events", -1)) != 0:
        raise ValueError(f"seed {seed}: no-reset run recorded reset events")

    for label, result in (
        ("baseline", baseline),
        ("old", old),
        ("hybrid_h1", h1),
        ("hybrid_reset", reset),
        ("hybrid_no_reset", no_reset),
    ):
        _validate_mask_result(result, seed=seed, label=label)
        weighted = result["official_test_metrics"]["weighted"]
        no_information = float(weighted.get("no_information_rate", math.nan))
        if not math.isfinite(no_information) or not 0.5 <= no_information <= 1.0:
            raise ValueError(f"seed {seed}: {label} no-information rate invalid")
    if baseline.get("selected_mask") != [1] * 40:
        raise ValueError(f"seed {seed}: baseline is not all-feature mask")


def evaluate_secure(
    rows: Sequence[Mapping[str, Any]],
    *,
    environment_profile: str = EXPECTED_ENVIRONMENT_PROFILE,
) -> Dict[str, Any]:
    if len(rows) != RUNS:
        raise ValueError("secure campaign requires exactly 30 rows")
    for seed, row in enumerate(rows, start=1):
        validate_secure_row(row, seed, environment_profile=environment_profile)
    report = base.evaluate(rows)
    report["schema"] = "eu26-21-corrected-applied-secure-report-v1"
    report["secure_environment"] = {
        "profile": environment_profile,
        "python": "3.11",
        "package_versions": EXPECTED_PACKAGES,
        "all_rows_verified": True,
        "instance_weight_raw_index_excluded_from_every_mask": True,
    }
    report["secure_audit_status"] = "PASS_SECURE_ROW_VALIDATION"
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows_dir", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--plots-dir", type=Path, required=True)
    parser.add_argument("--environment-profile", default=EXPECTED_ENVIRONMENT_PROFILE)
    args = parser.parse_args()

    candidates = sorted(args.rows_dir.resolve().rglob("seed-*.json"))
    if len(candidates) != RUNS:
        raise SystemExit(f"expected 30 secure rows, found {len(candidates)}")
    by_seed: Dict[int, Mapping[str, Any]] = {}
    for path in candidates:
        row = json.loads(path.read_text(encoding="utf-8"))
        seed = int(row.get("seed", -1))
        if seed in by_seed:
            raise SystemExit(f"duplicate secure row for seed {seed}")
        by_seed[seed] = row
    if sorted(by_seed) != list(range(1, RUNS + 1)):
        raise SystemExit("secure seed ledger is incomplete")
    rows = [by_seed[seed] for seed in range(1, RUNS + 1)]
    report = evaluate_secure(rows, environment_profile=args.environment_profile)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    base._write_csv(rows, args.output_csv)
    base._plot_results(rows, report, args.plots_dir)
    print(
        json.dumps(
            {
                "claim_status": report["claim_status"],
                "secure_audit_status": report["secure_audit_status"],
                "h1_corrected": report["h1_corrected"],
                "h2_corrected": report["h2_corrected"],
                "h8_reset_ablation": report["h8_reset_ablation"],
                "secure_environment": report["secure_environment"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

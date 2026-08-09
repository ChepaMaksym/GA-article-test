"""Compose immutable EU26-11 evidence from authenticated inputs."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

from .artifact import extract_numeric_table, l2_star_discrepancy, parse_point_set
from .source import verify_source_checkout


def load_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def file_identity(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"artifact is not a regular file: {path}")
    payload = path.read_bytes()
    sha256 = hashlib.sha256(payload).hexdigest()
    if len(payload) != expected["bytes"]:
        raise ValueError(f"artifact byte-size mismatch: {path}")
    if sha256 != expected["sha256"]:
        raise ValueError(f"artifact SHA-256 mismatch: {path}")
    return {"bytes": len(payload), "sha256": sha256}


def compose_report(
    *,
    contract: dict[str, Any],
    point_path: Path,
    numeric_path: Path,
    source_checkout: Path,
) -> dict[str, Any]:
    point_identity = file_identity(point_path, contract["point_set"])
    numeric_identity = file_identity(numeric_path, contract["numeric_block"])
    point_payload = point_path.read_bytes()
    point_set = parse_point_set(
        point_payload,
        expected_header=contract["point_set"]["header"],
        expected_rows=contract["point_set"]["rows"],
        expected_dimension=contract["point_set"]["dimension"],
    )
    observed_l2 = l2_star_discrepancy(point_set.points)
    observed_log10 = math.log10(observed_l2)

    numeric_contract = contract["numeric_block"]
    numeric_table = extract_numeric_table(
        numeric_path.read_bytes(),
        dimensions=numeric_contract["dimensions"],
        algorithms=numeric_contract["algorithms"],
        expected_block_bytes=numeric_contract["binary64_block_bytes"],
    )
    endpoint = contract["endpoint"]
    archived_l2 = numeric_table[(endpoint["algorithm"], endpoint["dimension"])]
    reference_l2 = float(endpoint["l2_star_reference"])
    reference_log10 = float(endpoint["log10_reference"])
    if abs(observed_l2 - reference_l2) > endpoint["l2_absolute_tolerance"]:
        raise ValueError("independent L2-star value differs from the frozen oracle")
    if abs(observed_log10 - reference_log10) > endpoint["log10_absolute_tolerance"]:
        raise ValueError("independent log10 value differs from the frozen oracle")
    if abs(observed_l2 - archived_l2) > endpoint["l2_absolute_tolerance"]:
        raise ValueError("point-set result differs from the archived numeric cell")
    paper_display = format(observed_log10, ".2f")
    if paper_display != endpoint["paper_display"]:
        raise ValueError("independent result does not reproduce the paper display")

    source_report = verify_source_checkout(source_checkout, contract["source"])
    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "candidate_id": contract["candidate_id"],
        "status": "PASS_TARGET_ARTIFACT_REPLAY",
        "scope": contract["status"],
        "paper_level_status": contract["paper_level_status"],
        "forbidden_claims": contract["forbidden_claims"],
        "target": {
            "figure": endpoint["figure"],
            "algorithm": endpoint["algorithm"],
            "dimension": endpoint["dimension"],
            "paper_display": endpoint["paper_display"],
        },
        "observed": {
            "l2_star": observed_l2,
            "log10_l2_star": observed_log10,
            "display_two_decimals": paper_display,
            "archived_l2_star": archived_l2,
            "absolute_difference_from_archive": abs(observed_l2 - archived_l2),
        },
        "inputs": {
            "point_set": point_identity,
            "numeric_block": numeric_identity,
        },
        "source_gate": source_report,
        "gates": {
            "A1_identity": "PASS",
            "A2_parser": "PASS",
            "A3_independent_formula": "PASS",
            "A4_archived_numeric_cell": "PASS",
            "A5_paper_display": "PASS",
            "A6_source_adaptation": "PASS_SOURCE_ADAPTATION_GATE",
            "A8_fail_closed": "PASS_BY_TEST_SUITE",
            "A9_claim_boundary": {
                "status": contract["paper_level_status"],
                "forbidden_claims": contract["forbidden_claims"],
            },
        },
    }
    digest_payload = json.dumps(
        report, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    report["report_digest"] = hashlib.sha256(
        b"EU26-11-TARGET-REPORT-V1\0" + digest_payload
    ).hexdigest()
    return report


def write_new_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"output path must not exist: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True
    ) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise

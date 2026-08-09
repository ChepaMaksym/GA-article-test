"""Canonical cross-language fixture derived from the authenticated safe parse."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes
from .contract import CANDIDATE_ROOT
from .errors import VerificationError
from .safe_pickle import ParseResult


FIXTURE_JSON = CANDIDATE_ROOT / "fixtures" / "frozen_endpoint.json"
FIXTURE_CSV = CANDIDATE_ROOT / "fixtures" / "run0_cycles.csv"


def _float_text(value: float) -> str:
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    if math.isnan(value):
        raise VerificationError("fixture cannot contain NaN")
    return repr(value)


def build_fixture(parsed: ParseResult, contract: dict[str, Any]) -> tuple[dict[str, Any], str]:
    root = parsed.value
    run0_cycles = root["cycles_per_seed"][0]
    first_improvement = root["improvements"][0].row(0)
    last_improvement = root["improvements"][0].row(-1)
    fixture = {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-14",
        "status": "TARGETED_ARTIFACT_REPLAY_ONLY",
        "paper_mapping": "PAPER_CONTEXT_ONLY",
        "source_archive_sha256": contract["files"]["source.tar.gz"]["sha256"],
        "result_archive_sha256": contract["files"]["msc_cec2020.tar.zst"]["sha256"],
        "member": {
            "path": contract["member"]["path"],
            "tar_data_offset": contract["member"]["tar_data_offset"],
            "bytes": contract["member"]["bytes"],
            "sha256": contract["member"]["sha256"],
        },
        "endpoint": {
            "suite": root["suite"],
            "dimension": root["dim"],
            "function": root["func"],
            "f_opt": _float_text(root["f_opt"]),
            "algorithm": root["algorithm"],
            "budget": root["maxevals"],
            "n_runs": root["n_runs"],
            "seeds": list(root["seeds"].values),
        },
        "environment": dict(root["meta"]),
        "run0": {
            "error": _float_text(root["errors"].scalar(0)),
            "improvements_shape": list(root["improvements"][0].shape),
            "first_improvement": [_float_text(item) for item in first_improvement],
            "last_improvement": [_float_text(item) for item in last_improvement],
            "cycle_count": len(run0_cycles),
            "pre_refine_error": _float_text(root["pre_refine_errors_per_seed"].scalar(0)),
            "nfev_pre_refine": root["nfev_pre_refine_per_seed"].scalar(0),
            "nfev_total": root["nfev_total_per_seed"].scalar(0),
        },
        "stop_semantic_conflict": {
            "nominal_budget": root["maxevals"],
            "run0_nfev_total": root["nfev_total_per_seed"].scalar(0),
            "unspent_evaluations": root["maxevals"]
            - root["nfev_total_per_seed"].scalar(0),
            "budget_exhaustion_claim_forbidden": True,
        },
        "forbidden_claims": contract["forbidden_claims"],
    }
    output = io.StringIO(newline="")
    columns = [
        "cycle",
        "mode",
        "nfev_start",
        "nfev_end",
        "nfev_delta",
        "best_f_start",
        "best_f_end",
        "improvement",
        "nfev_phase0",
        "n_basins_phase0",
        "phi_used",
        "sampling_method",
        "sample_reused",
    ]
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for cycle in run0_cycles:
        writer.writerow(
            {
                "cycle": cycle["cycle"],
                "mode": cycle["mode"],
                "nfev_start": cycle["nfev_start"],
                "nfev_end": cycle["nfev_end"],
                "nfev_delta": cycle["nfev_end"] - cycle["nfev_start"],
                "best_f_start": _float_text(cycle["best_f_start"]),
                "best_f_end": _float_text(cycle["best_f_end"]),
                "improvement": _float_text(cycle["improvement"]),
                "nfev_phase0": cycle["nfev_phase0"],
                "n_basins_phase0": cycle["n_basins_phase0"],
                "phi_used": _float_text(cycle["phi_used"]),
                "sampling_method": cycle["sampling_method"],
                "sample_reused": "true" if cycle["nfev_phase0"] == 0 else "false",
            }
        )
    return fixture, output.getvalue()


def verify_committed_fixture(
    parsed: ParseResult,
    contract: dict[str, Any],
    json_path: Path = FIXTURE_JSON,
    csv_path: Path = FIXTURE_CSV,
) -> dict[str, Any]:
    expected_json, expected_csv = build_fixture(parsed, contract)
    try:
        observed_json = json.loads(json_path.read_text(encoding="utf-8"))
        observed_csv = csv_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read committed fixture: {error}") from error
    if observed_json != expected_json:
        raise VerificationError("committed JSON fixture differs from safe parse")
    if observed_csv != expected_csv:
        raise VerificationError("committed CSV fixture differs from safe parse")
    digest = hashlib.sha256(
        b"EU26-14-FIXTURE-V1\0" + canonical_bytes(expected_json) + b"\0" + expected_csv.encode("utf-8")
    ).hexdigest()
    return {
        "gate": "PASS_COMMITTED_FIXTURE",
        "json_path": str(json_path.relative_to(CANDIDATE_ROOT)),
        "csv_path": str(csv_path.relative_to(CANDIDATE_ROOT)),
        "digest": f"sha256:{digest}",
    }

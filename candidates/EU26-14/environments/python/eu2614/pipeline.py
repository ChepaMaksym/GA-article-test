"""End-to-end targeted artifact pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contract import CONTRACT_SHA256, load_contract
from .endpoint import verify_endpoint
from .fixture import verify_committed_fixture
from .metadata import verify_zenodo_record
from .result_archive import extract_frozen_member, verify_checksum_manifest
from .safe_pickle import parse_numpy_pickle
from .source_archive import load_source_manifest, verify_source_archive


def verify_artifacts(
    *,
    record_json: Path,
    checksum_manifest: Path,
    source_archive: Path,
    result_archive: Path,
) -> dict[str, Any]:
    contract = load_contract()
    metadata = verify_zenodo_record(record_json, contract)
    checksums = verify_checksum_manifest(checksum_manifest, contract)
    source = verify_source_archive(source_archive, contract, load_source_manifest())
    payload, archive = extract_frozen_member(result_archive, contract)
    parsed = parse_numpy_pickle(payload)
    endpoint = verify_endpoint(parsed, contract)
    fixture = verify_committed_fixture(parsed, contract)
    run0 = contract["endpoint"]["run0"]
    return {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-14",
        "status": "TARGETED_ARTIFACT_REPLAY_ONLY",
        "paper_mapping": "PAPER_CONTEXT_ONLY",
        "contract": {
            "schema_version": contract["schema_version"],
            "sha256": CONTRACT_SHA256,
            "amendments": contract["amendments"],
        },
        "overall_gate": "PASS_TARGETED_ARTIFACT_REPLAY",
        "source_native_gate": "NOT_ATTEMPTED_OUT_OF_SCOPE",
        "zenodo": metadata,
        "checksum_manifest": checksums,
        "source": source,
        "result_archive": archive,
        "safe_endpoint": endpoint,
        "fixture": fixture,
        "frozen_endpoint": {
            "seed": 0,
            "error": run0["error"],
            "improvements_shape": run0["improvements_shape"],
            "first_improvement": run0["first_improvement"],
            "last_improvement": run0["last_improvement"],
            "cycles": run0["cycle_count"],
            "pre_refine_error": run0["pre_refine_error"],
            "nfev_pre_refine": run0["nfev_pre_refine"],
            "nfev_total": run0["nfev_total"],
        },
        "documented_conflicts": contract["documented_conflicts"],
        "forbidden_claims": contract["forbidden_claims"],
    }

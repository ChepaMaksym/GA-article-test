"""Strict access to the preregistered EU26-14 contract."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from .errors import VerificationError


PYTHON_ENV = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = PYTHON_ENV.parents[1]
CONTRACT_PATH = CANDIDATE_ROOT / "config" / "verification_contract.json"
CONTRACT_SHA256 = "47ac507e09bb9ad705fa934af672763bd6e2fd02d8b18fe74fedb1498b39ff49"

_TOP_LEVEL = {
    "schema_version",
    "candidate_id",
    "status",
    "paper_mapping",
    "readiness",
    "amendments",
    "forbidden_claims",
    "paper",
    "upstream",
    "zenodo",
    "files",
    "member",
    "endpoint",
    "safe_pickle",
    "cross_language",
    "execution",
    "documented_conflicts",
}


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    """Load the byte-frozen contract and reject any schema or constant drift."""
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise VerificationError(f"cannot load contract: {error}") from error
    observed_digest = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(observed_digest, CONTRACT_SHA256):
        raise VerificationError("contract byte identity differs")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot decode contract: {error}") from error
    if not isinstance(value, dict) or set(value) != _TOP_LEVEL:
        raise VerificationError("contract top-level schema differs")
    if value["schema_version"] != "1.1.0":
        raise VerificationError("unsupported contract schema")
    if value["candidate_id"] != "EU26-14":
        raise VerificationError("candidate identity differs")
    if value["status"] != "TARGETED_ARTIFACT_REPLAY_ONLY":
        raise VerificationError("claim ceiling differs")
    if value["paper_mapping"] != "PAPER_CONTEXT_ONLY":
        raise VerificationError("paper mapping differs")
    if value["readiness"] != "ADMITTED_TARGETED_ARTIFACT":
        raise VerificationError("readiness differs")
    if value["amendments"] != [
        {
            "id": "001",
            "path": "preregistration/amendment-001-safe-pickle-and-verifier-hardening.md",
            "recorded": "2026-08-09",
            "endpoint_changed": False,
            "claim_ceiling_changed": False,
        }
    ]:
        raise VerificationError("amendment ledger differs")
    required_forbidden = {
        "PASS_FULL",
        "PASS_EXACT_SOURCE_NATIVE",
        "PASS_LITERAL_PAPER_ENDPOINT",
        "HISTORICAL_ENVIRONMENT_PROVEN",
        "PAPER_BUDGET_EXHAUSTION_CONFIRMED",
    }
    forbidden = value["forbidden_claims"]
    if (
        not isinstance(forbidden, list)
        or len(forbidden) != len(required_forbidden)
        or set(forbidden) != required_forbidden
    ):
        raise VerificationError("forbidden-claim set differs")
    if value["execution"].get("source_native") != "NOT_ATTEMPTED_OUT_OF_SCOPE":
        raise VerificationError("source-native boundary differs")
    if value["safe_pickle"].get("general_unpickling_forbidden") is not True:
        raise VerificationError("safe-pickle boundary differs")
    if value["safe_pickle"] != {
        "allowed_globals": ["numpy._core.numeric._frombuffer", "numpy.dtype"],
        "general_unpickling_forbidden": True,
        "dtype_reduce_codes": ["i8", "f8"],
        "dtype_reduce_align": False,
        "dtype_reduce_copy": True,
        "dtype_build_state": [3, "<", None, None, None, -1, -1, 0],
        "frombuffer_order": "C",
        "exact_slot_types_required": True,
    }:
        raise VerificationError("safe-pickle contract differs")
    if value["cross_language"] != {
        "python_report_domain": "EU26-14-ARTIFACT-REPORT-V1",
        "cross_language_report_domain": "EU26-14-CROSS-LANGUAGE-REPORT-V1",
        "fixture_json_sha256": "9439e0b14370b7685e769d96b17f9f92f9b24dc51dc1f9fcb047bc35e1d431bf",
        "fixture_csv_sha256": "e00b4af33a678a3e87cf7e6474d77fef6962c65be0051a5765909359983d5320",
        "fixture_digest": "sha256:7a42a84bab8cc67822d33cbb3b636f60c422107a643a16c0cc2708aece5e636c",
        "octave_static_assert_call_sites": 48,
    }:
        raise VerificationError("cross-language contract differs")
    return value

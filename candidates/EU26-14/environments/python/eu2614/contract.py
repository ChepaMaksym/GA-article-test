"""Strict access to the preregistered EU26-14 contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import VerificationError


PYTHON_ENV = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = PYTHON_ENV.parents[1]
CONTRACT_PATH = CANDIDATE_ROOT / "config" / "verification_contract.json"

_TOP_LEVEL = {
    "schema_version",
    "candidate_id",
    "status",
    "paper_mapping",
    "readiness",
    "forbidden_claims",
    "paper",
    "upstream",
    "zenodo",
    "files",
    "member",
    "endpoint",
    "safe_pickle",
    "execution",
    "documented_conflicts",
}


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    """Load the immutable contract and reject schema/ceiling drift."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot load contract: {error}") from error
    if not isinstance(value, dict) or set(value) != _TOP_LEVEL:
        raise VerificationError("contract top-level schema differs")
    if value["schema_version"] != "1.0.0":
        raise VerificationError("unsupported contract schema")
    if value["candidate_id"] != "EU26-14":
        raise VerificationError("candidate identity differs")
    if value["status"] != "TARGETED_ARTIFACT_REPLAY_ONLY":
        raise VerificationError("claim ceiling differs")
    if value["paper_mapping"] != "PAPER_CONTEXT_ONLY":
        raise VerificationError("paper mapping differs")
    required_forbidden = {
        "PASS_FULL",
        "PASS_EXACT_SOURCE_NATIVE",
        "PASS_LITERAL_PAPER_ENDPOINT",
        "HISTORICAL_ENVIRONMENT_PROVEN",
        "PAPER_BUDGET_EXHAUSTION_CONFIRMED",
    }
    forbidden = value["forbidden_claims"]
    if not isinstance(forbidden, list) or set(forbidden) != required_forbidden:
        raise VerificationError("forbidden-claim set differs")
    if value["execution"].get("source_native") != "NOT_ATTEMPTED_OUT_OF_SCOPE":
        raise VerificationError("source-native boundary differs")
    if value["safe_pickle"].get("general_unpickling_forbidden") is not True:
        raise VerificationError("safe-pickle boundary differs")
    return value

"""Load and minimally validate the frozen EU26-09 contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CANDIDATE_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = CANDIDATE_ROOT / "config" / "verification_contract.json"
ENVIRONMENT_PATH = CANDIDATE_ROOT / "config" / "source_native_environment.json"


class ContractError(ValueError):
    """Raised if a frozen candidate-local contract is malformed."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read JSON contract {path}: {error}") from error
    if not isinstance(value, dict):
        raise ContractError(f"JSON contract {path} must contain an object")
    return value


def load_contract() -> dict[str, Any]:
    """Return the frozen contract only when the claim boundary is intact."""

    value = _read_json(CONTRACT_PATH)
    if value.get("candidate_id") != "EU26-09":
        raise ContractError("candidate_id is not EU26-09")
    if value.get("status") != "TARGETED_ARTIFACT_REPLAY":
        raise ContractError("status must remain TARGETED_ARTIFACT_REPLAY")
    if value.get("paper_mapping") != "PAPER_FIGURE_CONTEXT_ONLY":
        raise ContractError("paper mapping must remain context-only")
    forbidden = value.get("forbidden_claims")
    required = {
        "PASS_FULL",
        "PASS_LITERAL_PAPER_ENDPOINT",
        "HISTORICAL_DEPENDENCY_ENVIRONMENT_PROVEN",
    }
    if not isinstance(forbidden, list) or not required.issubset(set(forbidden)):
        raise ContractError("mandatory forbidden claims are incomplete")
    raw = value.get("raw_member")
    endpoint = value.get("endpoint")
    upstream = value.get("upstream")
    if not all(isinstance(item, dict) for item in (raw, endpoint, upstream)):
        raise ContractError("raw_member, endpoint, and upstream must be objects")
    if endpoint.get("runs") != 500 or endpoint.get("dimension") != 100:
        raise ContractError("frozen endpoint dimension or run count changed")
    return value


def load_environment_contract() -> dict[str, Any]:
    value = _read_json(ENVIRONMENT_PATH)
    if value.get("selection_frozen_before_replay") is not True:
        raise ContractError("source-native environment was not frozen before replay")
    if value.get("upstream_dependency_lock_present") is not False:
        raise ContractError("upstream dependency-lock blocker was removed")
    return value

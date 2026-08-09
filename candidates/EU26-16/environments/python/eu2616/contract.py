from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any


class ContractError(ValueError):
    """Raised when the frozen claim boundary is malformed or weakened."""


EXPECTED_STATUS = "FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY"
EXPECTED_READINESS = "CONDITIONAL_NONELIGIBLE"
EXPECTED_PAPER_MAPPING = "TABLE_7_NOT_REPLAYABLE_FROM_SHIPPED_ARTIFACTS"
MANDATORY_FORBIDDEN = {
    "PASS_FULL",
    "PASS_TABLE_7_REPLAY",
    "PASS_EMPIRICAL_REPRODUCTION",
    "DATASET_LICENSE_RESOLVED",
}
MANDATORY_BLOCKERS = {
    "PAPER_TEN_SEEDS_NOT_ENUMERATED",
    "ONLY_FOLD_1_SHIPPED",
    "CONFIG_REFERENCES_ABSENT_FOLD_2",
    "NO_FIVE_FOLD_DATA_MANIFEST",
    "NO_RAW_FIFTY_RUN_TABLE_7_LEDGER",
    "TABLE_7_VARIANT_CONFIG_NOT_FULLY_BOUND",
    "DATASET_LICENSE_UNRESOLVED",
}


def candidate_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _safe_member_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError("required member path must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ContractError(f"unsafe required member path: {value!r}")
    return value


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if contract.get("candidate_id") != "EU26-16":
        raise ContractError("wrong candidate_id")
    if contract.get("status") != EXPECTED_STATUS:
        raise ContractError("formula-only status was changed")
    if contract.get("readiness") != EXPECTED_READINESS:
        raise ContractError("conditional noneligibility was changed")
    if contract.get("paper_mapping") != EXPECTED_PAPER_MAPPING:
        raise ContractError("Table 7 claim boundary was changed")
    if not MANDATORY_FORBIDDEN.issubset(set(contract.get("forbidden_claims", []))):
        raise ContractError("mandatory forbidden claims are missing")
    if not MANDATORY_BLOCKERS.issubset(set(contract.get("blockers", []))):
        raise ContractError("mandatory empirical blockers are missing")

    upstream = contract.get("upstream", {})
    if upstream.get("commit") != "a800162492ee8ccb4e20f692b879610cb607db07":
        raise ContractError("upstream commit changed")
    if upstream.get("tree") != "8377a7be53e33bc6759cf079f22f30126dd50f83":
        raise ContractError("upstream tree changed")
    if upstream.get("tag") != "v3.0":
        raise ContractError("upstream tag changed")

    transition = contract.get("transition", {})
    if transition.get("probability_clamp") is not False:
        raise ContractError("source must remain guard-only, without a clamp")
    if transition.get("global_bounds_claim") is not False:
        raise ContractError("publication-lattice endpoints cannot become global bounds")
    if transition.get("decimal_update") != 0.02:
        raise ContractError("transition step changed")
    if transition.get("early_stop_patience") != 10:
        raise ContractError("early-stop patience changed")

    protocol = contract.get("paper_protocol", {})
    if protocol.get("table_7_target_enabled") is not False:
        raise ContractError("Table 7 target must remain disabled")
    if protocol.get("seed_values_enumerated") is not False:
        raise ContractError("paper seed identities must remain unreported")

    members = contract.get("required_members")
    if not isinstance(members, list) or len(members) != 6:
        raise ContractError("exactly six required upstream members are expected")
    paths = [_safe_member_path(member.get("path")) for member in members]
    if len(set(paths)) != len(paths):
        raise ContractError("required member paths must be unique")
    for member in members:
        if not isinstance(member.get("bytes"), int) or member["bytes"] <= 0:
            raise ContractError("required member byte size must be positive")
        sha256 = member.get("sha256", "")
        git_blob = member.get("git_blob", "")
        if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
            raise ContractError("invalid required member SHA-256")
        if len(git_blob) != 40 or any(char not in "0123456789abcdef" for char in git_blob):
            raise ContractError("invalid required member Git blob")
    return contract


def load_contract(path: Path | None = None) -> dict[str, Any]:
    contract_path = path or candidate_root() / "config" / "verification_contract.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot load contract: {error}") from error
    if not isinstance(contract, dict):
        raise ContractError("contract root must be an object")
    return validate_contract(contract)

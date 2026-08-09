"""Load the pre-implementation EU26-15 contract without permitting drift."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CANDIDATE_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = CANDIDATE_ROOT / "config" / "verification_contract.json"
FIXTURE_PATH = CANDIDATE_ROOT / "fixtures" / "fuzzy_transition_cases.json"
SOURCE_MANIFEST_PATH = CANDIDATE_ROOT / "source_manifest" / "sources.csv"

CONTRACT_SHA256 = "be6a54889ae28febd2c71de64316794b58500483d8b322a11142140a534f2114"
FIXTURE_SHA256 = "5d4d49ab993184bfb9f335cd62154d0ad41f2f2e27e7c76fb6fea76d5049ecb0"
SOURCE_MANIFEST_SHA256 = (
    "1191d6ad090b7d0c8456514884ced51c1596f760e837882ffed86b6a9460bfe4"
)


class ContractError(ValueError):
    """Raised when a frozen contract or its scientific boundary drifts."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_bound_json(path: Path, expected_sha256: str) -> dict[str, Any]:
    payload = path.read_bytes()
    actual = sha256_bytes(payload)
    if actual != expected_sha256:
        raise ContractError(
            f"frozen file drift for {path}: expected {expected_sha256}, got {actual}"
        )
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"expected a JSON object in {path}")
    return value


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema_version") != "1.0.0":
        raise ContractError("unsupported contract schema")
    if contract.get("candidate_id") != "EU26-15":
        raise ContractError("wrong candidate identity")
    if contract.get("candidate_status") != "CONDITIONAL_NONELIGIBLE":
        raise ContractError("candidate status promotion or drift is forbidden")
    if (
        contract.get("verification_scope")
        != "FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY"
    ):
        raise ContractError("verification scope drift")
    if contract.get("pass_full") is not False:
        raise ContractError("PASS_FULL must remain false")

    boundary = contract.get("claim_boundary", {})
    forbidden = set(boundary.get("forbidden", []))
    required_forbidden = {
        "PASS_FULL",
        "empirical GARBO replay",
        "Table 2 replay",
        "dataset license established",
    }
    if not required_forbidden.issubset(forbidden):
        raise ContractError("claim boundary no longer forbids every required claim")

    upstream = contract.get("upstream", {})
    if (
        upstream.get("licensed_revision")
        != "9727e017371484dd5837a0859b41c195a87fd8d0"
        or upstream.get("licensed_tree")
        != "995ee6c51315ea52d0e82211fb708e32b45800bb"
        or upstream.get("paper_era_revision")
        != "1854385ffb0be85ef8deeeda45980aaed6e50207"
    ):
        raise ContractError("upstream revision identity drift")

    quirks = contract.get("source_quirks", {})
    if quirks.get("mutation_antecedent") != "intFV(ft_input)":
        raise ContractError("the upstream intFV(ft_input) quirk must be preserved")
    if quirks.get("intFT_declared_but_not_used_by_mutation") is not True:
        raise ContractError("intFT non-use marker drift")
    if quirks.get("substitution_formula") != "1-(pDeletion+pInsertion)":
        raise ContractError("mutation operator complement drift")
    if quirks.get("additional_mutop_normalization") is not False:
        raise ContractError("upstream performs no extra mutop normalization")

    override = contract.get("override", {})
    if override.get("strict") is not True or override.get("threshold") != 0.75:
        raise ContractError("similarity override must remain strict ssc > 0.75")
    if override.get("mutop") != [0.9, 0.1, 0.0]:
        raise ContractError("similarity override state drift")

    dimension = contract.get("applied_dimension", {})
    if dimension.get("predictors") != 1599:
        raise ContractError("applied dimension drift")
    if dimension.get("dataset_license_status") != "UNRESOLVED_NOT_CLAIMED":
        raise ContractError("dataset license must remain unresolved and unclaimed")


def load_contract() -> dict[str, Any]:
    contract = _load_bound_json(CONTRACT_PATH, CONTRACT_SHA256)
    validate_contract(contract)
    if sha256_file(SOURCE_MANIFEST_PATH) != SOURCE_MANIFEST_SHA256:
        raise ContractError("source manifest drift")
    return contract


def load_fixtures() -> dict[str, Any]:
    fixture = _load_bound_json(FIXTURE_PATH, FIXTURE_SHA256)
    if fixture.get("candidate_id") != "EU26-15":
        raise ContractError("fixture candidate identity drift")
    if fixture.get("absolute_tolerance") != 5e-12:
        raise ContractError("fixture tolerance drift")
    return fixture

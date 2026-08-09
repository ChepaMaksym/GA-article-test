"""Load and validate the preregistered EU26-13 contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import VerificationError


CANDIDATE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTRACT = CANDIDATE_ROOT / "config" / "verification_contract.json"


def require(condition: bool, stage: str, detail: str) -> None:
    if not condition:
        raise VerificationError(stage, detail)


def exact(actual: Any, expected: Any, stage: str, field: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise VerificationError(
            stage,
            f"{field} mismatch: expected {expected!r}, received {actual!r}",
        )


def load_contract(path: Path | str = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract_path = Path(path)
    try:
        raw = contract_path.read_text(encoding="utf-8")
        contract = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError("CONTRACT", f"cannot load {contract_path}: {exc}") from exc
    require(isinstance(contract, dict), "CONTRACT", "root must be an object")
    validate_contract(contract)
    return contract


def validate_contract(contract: dict[str, Any]) -> None:
    """Fail closed if the status boundary or immutable execution policy changed."""

    exact(contract.get("schema_version"), "1.0.0", "CONTRACT", "schema_version")
    exact(contract.get("candidate_id"), "EU26-13", "CONTRACT", "candidate_id")
    exact(
        contract.get("status"),
        "TARGETED_ARTIFACT_REPLAY_ONLY",
        "CONTRACT",
        "status",
    )
    exact(
        contract.get("readiness"),
        "ADMITTED_TARGETED_ARTIFACT",
        "CONTRACT",
        "readiness",
    )
    exact(
        contract.get("paper_mapping"),
        "PAPER_CONTEXT_ONLY",
        "CONTRACT",
        "paper_mapping",
    )
    exact(
        contract.get("source_native_status"),
        "BLOCKED_UNPINNED_TOOLCHAIN_DEPS",
        "CONTRACT",
        "source_native_status",
    )
    forbidden = contract.get("forbidden_claims")
    require(isinstance(forbidden, list), "CONTRACT", "forbidden_claims must be a list")
    for claim in (
        "PASS_FULL",
        "PASS_LITERAL_PAPER_ENDPOINT",
        "PASS_EXACT_SOURCE_NATIVE_REPLAY",
        "HISTORICAL_DEPENDENCY_ENVIRONMENT_PROVEN",
        "FULL_ARCHIVE_MD5_RECOMPUTED",
        "ARCHIVE_SOURCE_MATCHES_PUBLIC_GIT_COMMIT",
    ):
        require(claim in forbidden, "CONTRACT", f"missing forbidden claim {claim}")

    policy = contract.get("verification_execution")
    require(isinstance(policy, dict), "CONTRACT", "verification_execution missing")
    exact(policy.get("maximum_range_bytes_per_request"), 4_000_000, "CONTRACT", "range cap")
    for field in (
        "full_outer_archive_download_forbidden",
        "full_nested_archive_download_forbidden",
        "require_exact_content_range",
        "require_zero_skips",
        "require_report_write_once",
        "source_native_execution_forbidden_under_v1",
    ):
        exact(policy.get(field), True, "CONTRACT", field)

    large = contract.get("zenodo_files", {}).get("repelling.zip", {})
    exact(large.get("bytes"), 17_573_142_426, "CONTRACT", "repelling.zip bytes")
    exact(
        large.get("md5"),
        "5bf7f5e28ca5c6f26859c94c3eb1fcee",
        "CONTRACT",
        "repelling.zip declared MD5",
    )
    exact(
        large.get("md5_status"),
        "ZENODO_DECLARED_NOT_RECOMPUTED",
        "CONTRACT",
        "repelling.zip MD5 status",
    )
    exact(
        contract.get("source_snapshot", {}).get("git_revision"),
        None,
        "CONTRACT",
        "source Git revision",
    )
    exact(
        contract.get("source_snapshot", {}).get("archive_maps_to_public_git_commit"),
        False,
        "CONTRACT",
        "archive/public Git mapping",
    )

    endpoint = contract.get("endpoint", {})
    exact(endpoint.get("dimension"), 20, "CONTRACT", "endpoint dimension")
    exact(endpoint.get("runs"), 500, "CONTRACT", "endpoint run count")
    exact(endpoint.get("seed"), 0, "CONTRACT", "endpoint seed")
    exact(
        endpoint.get("best_y_decimal"),
        "7.379046076174201e-09",
        "CONTRACT",
        "endpoint decimal",
    )

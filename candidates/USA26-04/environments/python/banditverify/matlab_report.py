"""Canonical cross-language payload for authenticated MATLAB/Octave H2 reports."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from .canonical import sha256_file
from .provenance import matlab_source_hashes
from .security import EvidenceValidationError, require_exact_keys, require_string


REPORT_SCHEMA = "USA26-04-MATLAB-H2-REPORT-v1"
PAYLOAD_DOMAIN = "USA26-04-MATLAB-H2-PAYLOAD-v1"
MATLAB_SOURCE_NAMES = (
    "bandit_ambiguity_witnesses.m",
    "bandit_nesterov_update.m",
    "bandit_objective.m",
    "bandit_printed_eq2_literal.m",
    "bandit_reward.m",
    "bandit_run_fixed_tape.m",
    "bandit_tile_index.m",
    "write_fixed_tape_report.m",
)


def _number(value: Any, context: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceValidationError(f"{context} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise EvidenceValidationError(f"{context} must be finite")
    return format(number, ".17g")


def _number_list(value: Any, context: str) -> str:
    if not isinstance(value, list):
        raise EvidenceValidationError(f"{context} must be an array")
    return ",".join(_number(item, f"{context}[{index}]") for index, item in enumerate(value))


def canonical_matlab_payload(payload: Any) -> str:
    """Return the exact language-neutral line serialization hashed by H2."""

    payload = require_exact_keys(
        payload,
        {
            "verification_scope",
            "paper_level_status",
            "published_result_status",
            "state_provenance",
            "base_weights",
            "branch",
            "argmax_tile",
            "selected_tile",
            "log_rate",
            "rate",
            "immediate_reward",
            "updates",
        },
        "matlab_report.payload",
    )
    lines = [
        PAYLOAD_DOMAIN,
        f"verification_scope={require_string(payload['verification_scope'], 'payload.verification_scope')}",
        f"paper_level_status={require_string(payload['paper_level_status'], 'payload.paper_level_status')}",
        f"published_result_status={require_string(payload['published_result_status'], 'payload.published_result_status')}",
        f"state_provenance={require_string(payload['state_provenance'], 'payload.state_provenance')}",
        f"base_weights={_number_list(payload['base_weights'], 'payload.base_weights')}",
        f"branch={require_string(payload['branch'], 'payload.branch')}",
        f"argmax_tile={_number(payload['argmax_tile'], 'payload.argmax_tile')}",
        f"selected_tile={_number(payload['selected_tile'], 'payload.selected_tile')}",
        f"log_rate={_number(payload['log_rate'], 'payload.log_rate')}",
        f"rate={_number(payload['rate'], 'payload.rate')}",
        f"immediate_reward={_number(payload['immediate_reward'], 'payload.immediate_reward')}",
    ]
    updates = payload["updates"]
    if not isinstance(updates, list) or len(updates) != 2:
        raise EvidenceValidationError("payload.updates must contain exactly two updates")
    for index, update in enumerate(updates):
        update = require_exact_keys(
            update,
            {
                "coding",
                "paper_index",
                "history",
                "max_reward",
                "gradient",
                "momentum",
                "value",
            },
            f"payload.updates[{index}]",
        )
        prefix = f"updates[{index}]"
        lines.extend(
            [
                f"{prefix}.coding={_number(update['coding'], prefix + '.coding')}",
                f"{prefix}.paper_index={_number(update['paper_index'], prefix + '.paper_index')}",
                f"{prefix}.history={_number_list(update['history'], prefix + '.history')}",
                f"{prefix}.max_reward={_number(update['max_reward'], prefix + '.max_reward')}",
                f"{prefix}.gradient={_number(update['gradient'], prefix + '.gradient')}",
                f"{prefix}.momentum={_number(update['momentum'], prefix + '.momentum')}",
                f"{prefix}.value={_number(update['value'], prefix + '.value')}",
            ]
        )
    return "\n".join(lines) + "\n"


def payload_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_matlab_payload(payload).encode("utf-8")).hexdigest()


def validate_matlab_report(
    report: Any,
    candidate: Path,
    current_head: str,
    *,
    expected_engine: str | None = None,
) -> dict[str, Any]:
    """Validate a parsed report against the exact current checkout."""

    report = require_exact_keys(
        report,
        {
            "schema_version",
            "protocol_id",
            "git_sha",
            "implementation",
            "engine",
            "matlab_sources",
            "fixture_path",
            "fixture_sha256",
            "payload",
            "canonical_payload",
            "canonical_payload_sha256",
        },
        "matlab_report",
    )
    if report["schema_version"] != REPORT_SCHEMA:
        raise EvidenceValidationError("MATLAB report schema version mismatch")
    if report["protocol_id"] != "USA26-04-FORMULA-PORTABILITY-v1":
        raise EvidenceValidationError("MATLAB report protocol mismatch")
    if report["git_sha"] != current_head:
        raise EvidenceValidationError("MATLAB report Git SHA does not match current HEAD")
    if report["implementation"] != "matlab_octave_clean_room":
        raise EvidenceValidationError("MATLAB implementation identity is missing")
    engine = require_exact_keys(report["engine"], {"name", "version"}, "matlab_report.engine")
    engine_name = require_string(engine["name"], "matlab_report.engine.name")
    require_string(engine["version"], "matlab_report.engine.version")
    if engine_name not in {"GNU Octave", "MATLAB"}:
        raise EvidenceValidationError("unrecognized MATLAB report engine")
    if expected_engine is not None and engine_name != expected_engine:
        raise EvidenceValidationError("MATLAB report engine differs from invoked engine")

    source_rows = report["matlab_sources"]
    if not isinstance(source_rows, list) or len(source_rows) != len(MATLAB_SOURCE_NAMES):
        raise EvidenceValidationError("MATLAB report source list is incomplete")
    reported_sources: dict[str, str] = {}
    for index, row in enumerate(source_rows):
        row = require_exact_keys(row, {"path", "sha256"}, f"matlab_sources[{index}]")
        name = require_string(row["path"], f"matlab_sources[{index}].path")
        digest = require_string(row["sha256"], f"matlab_sources[{index}].sha256")
        if name in reported_sources:
            raise EvidenceValidationError("duplicate MATLAB source path")
        reported_sources[name] = digest
    if tuple(sorted(reported_sources)) != MATLAB_SOURCE_NAMES:
        raise EvidenceValidationError("MATLAB report exact source-name set changed")
    if reported_sources != matlab_source_hashes(candidate):
        raise EvidenceValidationError("MATLAB source hashes differ from current checkout")

    fixture_path = candidate / "fixtures" / "fixed_controller_tape.json"
    if report["fixture_path"] != "fixtures/fixed_controller_tape.json":
        raise EvidenceValidationError("MATLAB fixture path changed")
    fixture_digest = sha256_file(fixture_path)
    if report["fixture_sha256"] != fixture_digest:
        raise EvidenceValidationError("MATLAB fixture hash differs from current checkout")
    canonical_payload = canonical_matlab_payload(report["payload"])
    if report["canonical_payload"] != canonical_payload:
        raise EvidenceValidationError("MATLAB canonical payload text mismatch")
    canonical_digest = payload_sha256(report["payload"])
    if report["canonical_payload_sha256"] != canonical_digest:
        raise EvidenceValidationError("MATLAB canonical payload digest mismatch")
    return {
        "engine": engine,
        "matlab_source_sha256": reported_sources,
        "fixture_sha256": fixture_digest,
        "canonical_payload_sha256": canonical_digest,
    }

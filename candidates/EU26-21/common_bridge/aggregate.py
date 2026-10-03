#!/usr/bin/env python3
"""Strict aggregation for the prospective EU26-21 common-objective bridge.

This module never runs either optimizer.  It consumes the five immutable files
produced for each seed, validates their byte and semantic bindings, constructs
a canonical ledger, and then applies the frozen paired-median BCa analysis.

A negative or null scientific decision is a valid result and exits zero.
Missing, malformed, inconsistent, or unauthenticated evidence exits non-zero,
after writing a complete diagnostic output set.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import sys
from pathlib import Path, PurePosixPath
from statistics import NormalDist
from typing import Any, Mapping, Sequence


ROW_SCHEMA = "eu26-21-common-bridge-row-v1"
TRACE_SCHEMA = "eu26-21-common-bridge-trace-v1"
STATUS_SCHEMA = "eu26-21-common-bridge-seed-status-v1"
MANIFEST_SCHEMA = "eu26-21-common-bridge-seed-manifest-v1"
LEDGER_SCHEMA = "eu26-21-common-bridge-canonical-ledger-v1"
REPORT_SCHEMA = "eu26-21-common-bridge-report-v1"
AGGREGATE_STATUS_SCHEMA = "eu26-21-common-bridge-aggregate-status-v1"
AGGREGATE_MANIFEST_SCHEMA = "eu26-21-common-bridge-aggregate-manifest-v1"
SOURCE_VERIFICATION_SCHEMA = (
    "eu26-21-common-bridge-source-artifact-verification-v1"
)
SOURCE_LEDGER_SCHEMA = "eu26-21-common-bridge-source-artifact-ledger-v1"
SOURCE_WORKFLOW_PATH = ".github/workflows/eu26-21-common-bridge-30-paired.yml"
MODEL_EVIDENCE_SCHEMA = "eu26-21-common-bridge-model-evidence-v1"

PROTOCOL_ID = "EU26-21-COMMON-WBA-BSF-AUC-400-V1"
STUDY_ID = "EU26-21-CWB-01"
EXPECTED_SEEDS = tuple(range(41001, 41031))
EXPECTED_UPSTREAM_COMMIT = "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6"
EXPECTED_PROTOCOL_SHA256 = (
    "730cd436db59d23da7dab5e24c49bc7b28d65379136fad7fd2d2370e0a436205"
)
EXPECTED_ARCHIVE_SHA256 = (
    "54fd206becffcfaf099544c3938c681d64a65709800c94c00a4fba0a00df10c9"
)
EXPECTED_TRAIN_SHA256 = (
    "3676a81db7d3528f3f8b9f3c699d0f0aa28db45e6e994fa0b8ed38327539ee86"
)
EXPECTED_TEST_SHA256 = (
    "98402b1ab879573d0a7f38a699a40258080e25e33d3401e7bf9c96d3fa0fab8c"
)
EXPECTED_CALLS = 400
EXPECTED_INITIAL_CALLS = 50
ANALYSIS_SEED = 41031
BOOTSTRAP_RESAMPLES = 50_000
NONINFERIORITY_MARGIN = -0.001
CHC_ARM = "chc_harmonized"
LAMBDA_ARM = "lambda_no_reset"
ARM_NAMES = (CHC_ARM, LAMBDA_ARM)
EXPECTED_ALGORITHM_IDS = {
    CHC_ARM: "harmonized_pinned_source_chc_feature_mask_search",
    LAMBDA_ARM: "self_adjusting_one_plus_lambda_lambda_no_reset",
}

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SHA256_WITH_PREFIX = re.compile(r"sha256:[0-9a-f]{64}\Z")


class EvidenceError(ValueError):
    """Raised when immutable evidence fails a protocol or provenance gate."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    _require(isinstance(value, list), f"{label} must be an array")
    return value


def _strict_int(value: Any, label: str, *, minimum: int | None = None) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool),
        f"{label} must be an integer",
    )
    normalized = int(value)
    if minimum is not None:
        _require(normalized >= minimum, f"{label} must be >= {minimum}")
    return normalized


def _finite_float(
    value: Any,
    label: str,
    *,
    lower: float | None = None,
    upper: float | None = None,
) -> float:
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{label} must be numeric",
    )
    normalized = float(value)
    _require(math.isfinite(normalized), f"{label} must be finite")
    if lower is not None:
        _require(normalized >= lower, f"{label} must be >= {lower}")
    if upper is not None:
        _require(normalized <= upper, f"{label} must be <= {upper}")
    return normalized


def _string(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(value), f"{label} must be a string")
    return value


def _hex(value: Any, label: str, pattern: re.Pattern[str]) -> str:
    normalized = _string(value, label).lower()
    _require(pattern.fullmatch(normalized) is not None, f"{label} is malformed")
    return normalized


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise EvidenceError(f"non-finite JSON constant is forbidden: {value}")


def _walk_finite(value: Any, label: str = "JSON") -> None:
    if isinstance(value, float):
        _require(math.isfinite(value), f"{label} contains a non-finite number")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _require(isinstance(key, str), f"{label} contains a non-string key")
            _walk_finite(item, f"{label}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_finite(item, f"{label}[{index}]")


def _load_json(path: Path) -> Any:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, EvidenceError) as exc:
        raise EvidenceError(f"cannot parse strict JSON {path}: {exc}") from exc
    _walk_finite(payload, path.name)
    return payload


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise EvidenceError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _validate_protocol(protocol: Mapping[str, Any], protocol_sha256: str) -> None:
    _require(
        protocol_sha256 == EXPECTED_PROTOCOL_SHA256,
        "protocol bytes differ from the frozen pre-implementation manifest",
    )
    _require(
        protocol.get("schema") == "eu26-21-common-wba-bridge-protocol-v1",
        "protocol schema mismatch",
    )
    _require(protocol.get("study_id") == STUDY_ID, "study ID mismatch")
    _require(protocol.get("protocol_id") == PROTOCOL_ID, "protocol ID mismatch")

    source = _mapping(protocol.get("source_boundary"), "protocol.source_boundary")
    _require(
        source.get("upstream_commit") == EXPECTED_UPSTREAM_COMMIT,
        "protocol upstream commit mismatch",
    )
    data = _mapping(protocol.get("data_protocol"), "protocol.data_protocol")
    _require(
        data.get("archive_sha256") == EXPECTED_ARCHIVE_SHA256,
        "protocol archive SHA mismatch",
    )
    _require(
        data.get("train_sha256") == EXPECTED_TRAIN_SHA256,
        "protocol train SHA mismatch",
    )
    _require(
        data.get("test_sha256") == EXPECTED_TEST_SHA256,
        "protocol test SHA mismatch",
    )
    pairing = _mapping(protocol.get("pairing_and_rng"), "protocol.pairing_and_rng")
    _require(
        pairing.get("seed_ledger") == list(EXPECTED_SEEDS),
        "protocol seed ledger mismatch",
    )
    budget = _mapping(protocol.get("budget"), "protocol.budget")
    _require(
        budget.get("objective_calls_per_arm_per_seed") == EXPECTED_CALLS,
        "protocol objective-call budget mismatch",
    )
    _require(
        budget.get("initial_population_calls") == EXPECTED_INITIAL_CALLS,
        "protocol initial-call budget mismatch",
    )
    analysis = _mapping(protocol.get("analysis_plan"), "protocol.analysis_plan")
    _require(analysis.get("analysis_seed") == ANALYSIS_SEED, "analysis seed mismatch")
    _require(
        analysis.get("bootstrap_resamples") == BOOTSTRAP_RESAMPLES,
        "bootstrap count mismatch",
    )
    _require(
        analysis.get("noninferiority_margin") == NONINFERIORITY_MARGIN,
        "non-inferiority margin mismatch",
    )
    _require(HEX64.fullmatch(protocol_sha256) is not None, "bad protocol SHA")


PROVENANCE_REQUIRED_KEYS = (
    "protocol_id",
    "protocol_sha256",
    "protocol_content_freeze_commit_sha",
    "implementation_sha",
    "implementation_files_sha256",
    "config_sha256",
    "requirements_sha256",
    "environment_sha256",
    "run_id",
    "run_attempt",
    "ref",
    "workflow_sha",
    "upstream_commit",
    "upstream_evolution_blob_sha1",
    "upstream_evolution_sha256",
    "archive_sha256",
    "train_sha256",
    "test_sha256",
)


def _validate_provenance(
    value: Any,
    *,
    label: str,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    provenance = _mapping(value, label)
    for key in PROVENANCE_REQUIRED_KEYS:
        _require(key in provenance, f"{label}.{key} is missing")

    normalized: dict[str, Any] = {
        "protocol_id": _string(provenance["protocol_id"], f"{label}.protocol_id"),
        "protocol_sha256": _hex(
            provenance["protocol_sha256"], f"{label}.protocol_sha256", HEX64
        ),
        "protocol_content_freeze_commit_sha": _hex(
            provenance["protocol_content_freeze_commit_sha"],
            f"{label}.protocol_content_freeze_commit_sha",
            HEX40,
        ),
        "implementation_sha": _hex(
            provenance["implementation_sha"], f"{label}.implementation_sha", HEX40
        ),
        "implementation_files_sha256": _hex(
            provenance["implementation_files_sha256"],
            f"{label}.implementation_files_sha256",
            HEX64,
        ),
        "config_sha256": _hex(
            provenance["config_sha256"], f"{label}.config_sha256", HEX64
        ),
        "requirements_sha256": _hex(
            provenance["requirements_sha256"],
            f"{label}.requirements_sha256",
            HEX64,
        ),
        "environment_sha256": _hex(
            provenance["environment_sha256"],
            f"{label}.environment_sha256",
            HEX64,
        ),
        "run_id": _strict_int(provenance["run_id"], f"{label}.run_id", minimum=1),
        "run_attempt": _strict_int(
            provenance["run_attempt"], f"{label}.run_attempt", minimum=1
        ),
        "ref": _string(provenance["ref"], f"{label}.ref"),
        "workflow_sha": _hex(
            provenance["workflow_sha"], f"{label}.workflow_sha", HEX40
        ),
        "upstream_commit": _hex(
            provenance["upstream_commit"], f"{label}.upstream_commit", HEX40
        ),
        "upstream_evolution_blob_sha1": _hex(
            provenance["upstream_evolution_blob_sha1"],
            f"{label}.upstream_evolution_blob_sha1",
            HEX40,
        ),
        "upstream_evolution_sha256": _hex(
            provenance["upstream_evolution_sha256"],
            f"{label}.upstream_evolution_sha256",
            HEX64,
        ),
        "archive_sha256": _hex(
            provenance["archive_sha256"], f"{label}.archive_sha256", HEX64
        ),
        "train_sha256": _hex(
            provenance["train_sha256"], f"{label}.train_sha256", HEX64
        ),
        "test_sha256": _hex(
            provenance["test_sha256"], f"{label}.test_sha256", HEX64
        ),
    }

    _require(normalized["protocol_id"] == PROTOCOL_ID, f"{label}: protocol mismatch")
    _require(
        normalized["upstream_commit"] == EXPECTED_UPSTREAM_COMMIT,
        f"{label}: upstream mismatch",
    )
    _require(
        normalized["archive_sha256"] == EXPECTED_ARCHIVE_SHA256,
        f"{label}: archive mismatch",
    )
    _require(
        normalized["train_sha256"] == EXPECTED_TRAIN_SHA256,
        f"{label}: train data mismatch",
    )
    _require(
        normalized["test_sha256"] == EXPECTED_TEST_SHA256,
        f"{label}: test data mismatch",
    )
    if "environment" in provenance:
        environment = _mapping(provenance["environment"], f"{label}.environment")
        _walk_finite(environment, f"{label}.environment")
        _require(
            _canonical_sha256(environment) == normalized["environment_sha256"],
            f"{label}: structured environment SHA mismatch",
        )
        normalized["environment"] = dict(environment)
    if "implementation_files" in provenance:
        implementation_files = _mapping(
            provenance["implementation_files"], f"{label}.implementation_files"
        )
        _require(
            _canonical_sha256(implementation_files)
            == normalized["implementation_files_sha256"],
            f"{label}: structured implementation-file SHA mismatch",
        )
    # Normalize structured fields before comparing row/status/manifest identity.
    # Otherwise a valid row's environment is compared against a missing value.
    for key, expected_value in expected.items():
        if expected_value is not None:
            _require(
                normalized.get(key) == expected_value,
                f"{label}.{key}={normalized.get(key)!r}, expected {expected_value!r}",
            )
    return normalized


PAIRING_KEYS = (
    "split_sha256",
    "active_indices_sha256",
    "evaluator_sha256",
    "initial_masks_sha256",
    "first_50_evaluations_sha256",
)


def _validate_pairing(
    value: Any,
    label: str,
    *,
    seed: int,
) -> dict[str, Any]:
    pairing = _mapping(value, label)
    expected_keys = {
        "seed",
        "split_seed",
        "active_sample_seed",
        "search_seed",
        "initial_mask_seed",
        "initial_mask_count",
        "dimension",
        *PAIRING_KEYS,
    }
    _require(set(pairing) == expected_keys, f"{label}: pairing field set mismatch")
    normalized: dict[str, Any] = {
        "seed": _strict_int(pairing["seed"], f"{label}.seed"),
        "split_seed": _strict_int(pairing["split_seed"], f"{label}.split_seed"),
        "active_sample_seed": _strict_int(
            pairing["active_sample_seed"], f"{label}.active_sample_seed"
        ),
        "search_seed": _strict_int(
            pairing["search_seed"], f"{label}.search_seed"
        ),
        "initial_mask_seed": _strict_int(
            pairing["initial_mask_seed"], f"{label}.initial_mask_seed"
        ),
        "initial_mask_count": _strict_int(
            pairing["initial_mask_count"], f"{label}.initial_mask_count"
        ),
        "dimension": _strict_int(pairing["dimension"], f"{label}.dimension"),
    }
    _require(normalized["seed"] == seed, f"{label}: seed mismatch")
    _require(
        normalized["split_seed"] == 2_026_081_700 + seed,
        f"{label}: split-seed formula mismatch",
    )
    _require(
        normalized["active_sample_seed"] == 2_026_081_800 + seed,
        f"{label}: active-sample-seed formula mismatch",
    )
    _require(
        normalized["search_seed"] == seed + 1_000_003,
        f"{label}: search-seed formula mismatch",
    )
    _require(
        normalized["initial_mask_seed"] == seed + 1_000_102,
        f"{label}: initial-mask-seed formula mismatch",
    )
    _require(
        normalized["initial_mask_count"] == EXPECTED_INITIAL_CALLS,
        f"{label}: initial-mask count mismatch",
    )
    _require(normalized["dimension"] == 40, f"{label}: dimension mismatch")
    for key in PAIRING_KEYS:
        normalized[key] = _hex(pairing[key], f"{label}.{key}", HEX64)
    return normalized


def _validate_mask(value: Any, label: str) -> list[int]:
    mask = _list(value, label)
    _require(len(mask) == 40, f"{label} must contain 40 bits")
    normalized: list[int] = []
    for index, bit in enumerate(mask):
        _require(
            isinstance(bit, int) and not isinstance(bit, bool) and bit in (0, 1),
            f"{label}[{index}] must be 0 or 1",
        )
        normalized.append(int(bit))
    return normalized


def _reject_test_outcomes(value: Any, label: str) -> None:
    """Forbid test outcomes in search traces while allowing immutable identity.

    A trace may bind the frozen test file by SHA and may explicitly assert that
    test data were not used during search.  It may not contain any held-out
    metric, prediction, confusion matrix, or selection derived from the test.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if "test" in lowered:
                _require(
                    lowered in {"test_file_sha256", "test_data_used_during_search"},
                    f"{label} leaks a test outcome at key {key!r}",
                )
                if lowered == "test_file_sha256":
                    _require(
                        _hex(item, f"{label}.{key}", HEX64) == EXPECTED_TEST_SHA256,
                        f"{label}.{key} does not identify the frozen test file",
                    )
                else:
                    _require(item is False, f"{label}.{key} must be false")
            _require(
                lowered
                not in {
                    "roc_auc",
                    "confusion_matrix",
                    "predictions",
                    "predicted_labels",
                    "selected_on_test",
                },
                f"{label} leaks held-out outcome data at key {key!r}",
            )
            _reject_test_outcomes(item, f"{label}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_test_outcomes(item, f"{label}[{index}]")


def _validate_trace_provenance(
    value: Any,
    *,
    label: str,
    expected_provenance: Mapping[str, Any],
) -> None:
    provenance = _mapping(value, label)
    required = (
        "protocol_id",
        "protocol_sha256",
        "protocol_content_freeze_commit_sha",
        "implementation_sha",
        "config_sha256",
        "upstream_commit",
        "upstream_evolution_blob_sha1",
        "upstream_evolution_sha256",
    )
    for key in required:
        _require(key in provenance, f"{label}.{key} is missing")
        _require(
            provenance[key] == expected_provenance[key],
            f"{label}.{key} disagrees with row provenance",
        )


def _validate_evaluation(
    value: Any,
    *,
    seed: int,
    arm: str,
    expected_call: int,
) -> dict[str, Any]:
    label = f"seed {seed} {arm} evaluation {expected_call}"
    row = _mapping(value, label)
    required = (
        "call",
        "mask",
        "mask_sha256",
        "validation_weighted_balanced_accuracy",
        "negative_selected_feature_fraction",
        "selected_feature_count",
        "best_so_far_weighted_balanced_accuracy",
        "terminal_best_update",
    )
    for key in required:
        _require(key in row, f"{label}.{key} is missing")
    call = _strict_int(row["call"], f"{label}.call", minimum=1)
    _require(call == expected_call, f"{label}: non-contiguous objective-call ledger")
    mask = _validate_mask(row["mask"], f"{label}.mask")
    mask_sha = _hex(row["mask_sha256"], f"{label}.mask_sha256", HEX64)
    _require(
        mask_sha == _canonical_sha256(mask),
        f"{label}: mask SHA does not bind the 40-bit mask",
    )
    count = _strict_int(
        row["selected_feature_count"], f"{label}.selected_feature_count", minimum=0
    )
    _require(count <= 40, f"{label}: selected-feature count exceeds 40")
    _require(count == sum(mask), f"{label}: feature count disagrees with mask")
    wba = _finite_float(
        row["validation_weighted_balanced_accuracy"],
        f"{label}.validation_weighted_balanced_accuracy",
        lower=0.0,
        upper=1.0,
    )
    negative_fraction = _finite_float(
        row["negative_selected_feature_fraction"],
        f"{label}.negative_selected_feature_fraction",
        lower=-1.0,
        upper=0.0,
    )
    expected_secondary = -1.0 if count == 0 else -count / 40.0
    _require(
        math.isclose(
            negative_fraction,
            expected_secondary,
            rel_tol=0.0,
            abs_tol=1e-15,
        ),
        f"{label}: sparsity objective disagrees with mask",
    )
    if count == 0:
        _require(wba == 0.0, f"{label}: empty-mask primary fitness must be zero")
    best = _finite_float(
        row["best_so_far_weighted_balanced_accuracy"],
        f"{label}.best_so_far_weighted_balanced_accuracy",
        lower=0.0,
        upper=1.0,
    )
    _require(
        isinstance(row["terminal_best_update"], bool),
        f"{label}.terminal_best_update must be boolean",
    )
    return {
        "call": call,
        "mask": mask,
        "mask_sha256": mask_sha,
        "validation_weighted_balanced_accuracy": wba,
        "negative_selected_feature_fraction": negative_fraction,
        "selected_feature_count": count,
        "best_so_far_weighted_balanced_accuracy": best,
        "terminal_best_update": bool(row["terminal_best_update"]),
    }


def _terminal_from_evaluations(evaluations: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    best = evaluations[0]
    for candidate in evaluations[1:]:
        candidate_fitness = (
            candidate["validation_weighted_balanced_accuracy"],
            candidate["negative_selected_feature_fraction"],
        )
        best_fitness = (
            best["validation_weighted_balanced_accuracy"],
            best["negative_selected_feature_fraction"],
        )
        if candidate_fitness > best_fitness:
            best = candidate
    return best


def _validate_trace(
    path: Path,
    *,
    seed: int,
    arm: str,
    expected_provenance: Mapping[str, Any],
    expected_pairing: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _mapping(_load_json(path), path.name)
    _reject_test_outcomes(payload, path.name)
    _require(payload.get("schema") == TRACE_SCHEMA, f"{path.name}: schema mismatch")
    _require(payload.get("seed") == seed, f"{path.name}: seed mismatch")
    _require(payload.get("arm") == arm, f"{path.name}: arm mismatch")
    _validate_trace_provenance(
        payload.get("provenance"),
        label=f"{path.name}.provenance",
        expected_provenance=expected_provenance,
    )
    pairing = _validate_pairing(
        payload.get("pairing"),
        f"{path.name}.pairing",
        seed=seed,
    )
    _require(pairing == expected_pairing, f"{path.name}: pairing ledger mismatch")
    _require(
        payload.get("config_sha256") == expected_provenance["config_sha256"],
        f"{path.name}: top-level config SHA mismatch",
    )
    _require(
        _strict_int(payload.get("objective_calls"), f"{path.name}.objective_calls")
        == EXPECTED_CALLS,
        f"{path.name}: objective-call budget mismatch",
    )
    _require(
        _strict_int(
            payload.get("initial_population_calls"),
            f"{path.name}.initial_population_calls",
        )
        == EXPECTED_INITIAL_CALLS,
        f"{path.name}: initial-call budget mismatch",
    )
    _require(payload.get("reset") is False, f"{path.name}: reset must be false")
    _require(
        _strict_int(payload.get("reset_events"), f"{path.name}.reset_events") == 0,
        f"{path.name}: reset-event count must be zero",
    )
    termination_phase = _string(
        payload.get("termination_phase"), f"{path.name}.termination_phase"
    )
    terminal_state = dict(
        _mapping(payload.get("terminal_state"), f"{path.name}.terminal_state")
    )
    if arm == CHC_ARM:
        _require(
            termination_phase
            in {
                "partial_chc_offspring_prefix",
                "complete_cataclysmic_generation",
                "complete_chc_generation",
            },
            f"{path.name}: invalid CHC termination phase",
        )
        _strict_int(
            terminal_state.get("generation_count"),
            f"{path.name}.terminal_state.generation_count",
            minimum=1,
        )
        _strict_int(
            terminal_state.get("final_distance"),
            f"{path.name}.terminal_state.final_distance",
            minimum=0,
        )
        _require(
            terminal_state.get("population_size") == EXPECTED_INITIAL_CALLS,
            f"{path.name}: CHC terminal population size mismatch",
        )
        _require(
            isinstance(terminal_state.get("partial_population_update_skipped"), bool),
            f"{path.name}: CHC partial-update flag must be boolean",
        )
        _require(
            terminal_state["partial_population_update_skipped"]
            == (termination_phase == "partial_chc_offspring_prefix"),
            f"{path.name}: CHC phase/partial-update state mismatch",
        )
    else:
        _require(
            termination_phase
            in {"paired_mutant_crossover_tail", "complete_lambda_generation"},
            f"{path.name}: invalid lambda termination phase",
        )
        _strict_int(
            terminal_state.get("generation_count"),
            f"{path.name}.terminal_state.generation_count",
            minimum=1,
        )
        _finite_float(
            terminal_state.get("final_lambda"),
            f"{path.name}.terminal_state.final_lambda",
            lower=1.0,
            upper=40.0,
        )
        _hex(
            terminal_state.get("parent_mask_sha256"),
            f"{path.name}.terminal_state.parent_mask_sha256",
            HEX64,
        )
        parent_fitness = _list(
            terminal_state.get("parent_fitness"),
            f"{path.name}.terminal_state.parent_fitness",
        )
        _require(len(parent_fitness) == 2, f"{path.name}: parent fitness arity mismatch")
        _finite_float(parent_fitness[0], f"{path.name}.terminal_state.parent_fitness[0]")
        _finite_float(parent_fitness[1], f"{path.name}.terminal_state.parent_fitness[1]")
        _require(
            isinstance(terminal_state.get("tail_truncated"), bool),
            f"{path.name}: lambda tail flag must be boolean",
        )
        _require(
            terminal_state["tail_truncated"]
            == (termination_phase == "paired_mutant_crossover_tail"),
            f"{path.name}: lambda phase/tail state mismatch",
        )
        _require(
            terminal_state.get("workers") == 1,
            f"{path.name}: lambda worker count mismatch",
        )
    terminal = _mapping(payload.get("terminal"), f"{path.name}.terminal")
    _require(
        isinstance(payload.get("generation_trace"), list),
        f"{path.name}.generation_trace must be an array",
    )

    raw_evaluations = _list(payload.get("evaluations"), f"{path.name}.evaluations")
    _require(
        len(raw_evaluations) == EXPECTED_CALLS,
        f"{path.name}: expected exactly {EXPECTED_CALLS} evaluations",
    )
    evaluations = [
        _validate_evaluation(item, seed=seed, arm=arm, expected_call=index)
        for index, item in enumerate(raw_evaluations, start=1)
    ]
    from .trace_contract import validate_generations

    try:
        validate_generations(arm, payload["generation_trace"], evaluations, terminal_state)
    except (ValueError, TypeError, KeyError, IndexError) as error:
        raise EvidenceError(f"{path.name}: invalid generation transcript: {error}") from error
    running_best = -math.inf
    terminal_fitness: tuple[float, float] | None = None
    for evaluation in evaluations:
        running_best = max(
            running_best, evaluation["validation_weighted_balanced_accuracy"]
        )
        _require(
            evaluation["best_so_far_weighted_balanced_accuracy"] == running_best,
            f"{path.name}: incorrect best-so-far value at call {evaluation['call']}",
        )
        current_fitness = (
            evaluation["validation_weighted_balanced_accuracy"],
            evaluation["negative_selected_feature_fraction"],
        )
        expected_terminal_update = (
            terminal_fitness is None or current_fitness > terminal_fitness
        )
        _require(
            evaluation["terminal_best_update"] == expected_terminal_update,
            f"{path.name}: incorrect terminal-best flag at call {evaluation['call']}",
        )
        if expected_terminal_update:
            terminal_fitness = current_fitness

    expected_first_50_sha = _canonical_sha256(evaluations[:EXPECTED_INITIAL_CALLS])
    _require(
        pairing["first_50_evaluations_sha256"] == expected_first_50_sha,
        f"{path.name}: first-50 digest mismatch",
    )
    expected_initial_masks_sha = _canonical_sha256(
        [item["mask"] for item in evaluations[:EXPECTED_INITIAL_CALLS]]
    )
    _require(
        pairing["initial_masks_sha256"] == expected_initial_masks_sha,
        f"{path.name}: initial-mask digest mismatch",
    )
    auc = statistics.fmean(
        item["best_so_far_weighted_balanced_accuracy"] for item in evaluations
    )
    recorded_auc = _finite_float(
        payload.get("normalized_auc_best_so_far_validation_wba_1_400"),
        f"{path.name}.normalized_auc_best_so_far_validation_wba_1_400",
        lower=0.0,
        upper=1.0,
    )
    _require(
        math.isclose(auc, recorded_auc, rel_tol=0.0, abs_tol=1e-15),
        f"{path.name}: normalized AUC does not match the 400-call trace",
    )
    post_initial = statistics.fmean(
        item["best_so_far_weighted_balanced_accuracy"]
        for item in evaluations[EXPECTED_INITIAL_CALLS:]
    )
    recorded_post = _finite_float(
        payload.get("normalized_auc_best_so_far_validation_wba_51_400"),
        f"{path.name}.normalized_auc_best_so_far_validation_wba_51_400",
        lower=0.0,
        upper=1.0,
    )
    _require(
        math.isclose(post_initial, recorded_post, rel_tol=0.0, abs_tol=1e-15),
        f"{path.name}: calls-51-400 AUC mismatch",
    )

    derived_terminal = _terminal_from_evaluations(evaluations)
    for key, expected_value in (
        ("call", derived_terminal["call"]),
        ("mask", derived_terminal["mask"]),
        (
            "fitness",
            [
                derived_terminal["validation_weighted_balanced_accuracy"],
                derived_terminal["negative_selected_feature_fraction"],
            ],
        ),
        ("selected_feature_count", derived_terminal["selected_feature_count"]),
        ("mask_sha256", derived_terminal["mask_sha256"]),
        (
            "validation_weighted_balanced_accuracy",
            derived_terminal["validation_weighted_balanced_accuracy"],
        ),
        (
            "negative_selected_feature_fraction",
            derived_terminal["negative_selected_feature_fraction"],
        ),
    ):
        _require(
            terminal.get(key) == expected_value,
            f"{path.name}: terminal.{key} disagrees with earliest best query",
        )

    return {
        "payload": dict(payload),
        "pairing": pairing,
        "evaluations": evaluations,
        "auc": recorded_auc,
        "post_initial_auc": recorded_post,
        "termination_phase": termination_phase,
        "terminal_state": terminal_state,
        "terminal": dict(terminal),
        "first_50": evaluations[:EXPECTED_INITIAL_CALLS],
    }


def _validate_terminal(
    value: Any,
    *,
    label: str,
    trace_terminal: Mapping[str, Any],
) -> dict[str, Any]:
    terminal = _mapping(value, label)
    required = (
        "call",
        "mask",
        "fitness",
        "selected_feature_count",
        "test_weighted_balanced_accuracy",
        "test_metrics",
    )
    for key in required:
        _require(key in terminal, f"{label}.{key} is missing")
    for key in ("call", "mask", "fitness", "selected_feature_count"):
        _require(
            terminal[key] == trace_terminal[key],
            f"{label}.{key} disagrees with search trace",
        )
    test_wba = _finite_float(
        terminal["test_weighted_balanced_accuracy"],
        f"{label}.test_weighted_balanced_accuracy",
        lower=0.0,
        upper=1.0,
    )
    metrics = dict(_mapping(terminal["test_metrics"], f"{label}.test_metrics"))
    _walk_finite(metrics, f"{label}.test_metrics")
    weighted = _mapping(metrics.get("weighted"), f"{label}.test_metrics.weighted")
    metric_wba = _finite_float(
        weighted.get("balanced_accuracy"),
        f"{label}.test_metrics.weighted.balanced_accuracy",
        lower=0.0,
        upper=1.0,
    )
    _require(metric_wba == test_wba, f"{label}: nested weighted test WBA mismatch")
    selected_count = _strict_int(
        terminal["selected_feature_count"],
        f"{label}.selected_feature_count",
        minimum=1,
    )
    mask = _validate_mask(terminal["mask"], f"{label}.mask")
    _require(selected_count == sum(mask), f"{label}: terminal mask/count mismatch")
    _require(
        metrics.get("selected_feature_count") == selected_count,
        f"{label}: official-test selected-feature count mismatch",
    )
    expected_indices = [index for index, bit in enumerate(mask) if bit]
    _require(
        metrics.get("selected_predictive_indices") == expected_indices,
        f"{label}: official-test selected indices disagree with terminal mask",
    )
    if "mask_sha256" in terminal:
        _require(
            _hex(terminal["mask_sha256"], f"{label}.mask_sha256", HEX64)
            == _canonical_sha256(mask),
            f"{label}: terminal mask SHA mismatch",
        )
    return {
        "call": _strict_int(terminal["call"], f"{label}.call", minimum=1),
        "mask": mask,
        "fitness": list(_list(terminal["fitness"], f"{label}.fitness")),
        "selected_feature_count": selected_count,
        "test_weighted_balanced_accuracy": test_wba,
        "test_metrics": metrics,
    }


def _validate_arm(
    value: Any,
    *,
    seed: int,
    arm: str,
    expected_trace_name: str,
    trace_path: Path,
    trace: Mapping[str, Any],
) -> dict[str, Any]:
    label = f"seed {seed} row arm {arm}"
    result = _mapping(value, label)
    required = (
        "algorithm_id",
        "objective_calls",
        "initial_population_calls",
        "test_evaluations",
        "reset",
        "reset_events",
        "trace_file",
        "trace_sha256",
        "normalized_auc_best_so_far_validation_wba_1_400",
        "normalized_auc_best_so_far_validation_wba_51_400",
        "termination_phase",
        "terminal_state",
        "terminal",
    )
    for key in required:
        _require(key in result, f"{label}.{key} is missing")
    expected_algorithm = EXPECTED_ALGORITHM_IDS[arm]
    _require(result["algorithm_id"] == expected_algorithm, f"{label}: algorithm mismatch")
    _require(result["objective_calls"] == EXPECTED_CALLS, f"{label}: calls mismatch")
    _require(
        result["initial_population_calls"] == EXPECTED_INITIAL_CALLS,
        f"{label}: initial calls mismatch",
    )
    _require(result["test_evaluations"] == 1, f"{label}: test must be evaluated once")
    _require(result["reset"] is False, f"{label}: reset must be false")
    _require(result["reset_events"] == 0, f"{label}: reset events must be zero")
    _require(result["trace_file"] == expected_trace_name, f"{label}: trace filename mismatch")
    _require(
        _hex(result["trace_sha256"], f"{label}.trace_sha256", HEX64)
        == _file_sha256(trace_path),
        f"{label}: trace byte SHA mismatch",
    )
    auc = _finite_float(
        result["normalized_auc_best_so_far_validation_wba_1_400"],
        f"{label}.normalized_auc_best_so_far_validation_wba_1_400",
        lower=0.0,
        upper=1.0,
    )
    _require(auc == trace["auc"], f"{label}: AUC disagrees with trace")
    post_initial_auc = _finite_float(
        result["normalized_auc_best_so_far_validation_wba_51_400"],
        f"{label}.normalized_auc_best_so_far_validation_wba_51_400",
        lower=0.0,
        upper=1.0,
    )
    _require(
        post_initial_auc == trace["post_initial_auc"],
        f"{label}: calls-51-400 AUC disagrees with trace",
    )
    termination_phase = _string(result["termination_phase"], f"{label}.termination_phase")
    _require(
        termination_phase == trace["termination_phase"],
        f"{label}: termination phase disagrees with trace",
    )
    terminal_state = dict(_mapping(result["terminal_state"], f"{label}.terminal_state"))
    _require(terminal_state == trace["terminal_state"], f"{label}: terminal state mismatch")
    terminal = _validate_terminal(
        result["terminal"], label=f"{label}.terminal", trace_terminal=trace["terminal"]
    )
    return {
        "algorithm_id": expected_algorithm,
        "auc": auc,
        "post_initial_auc": post_initial_auc,
        "termination_phase": termination_phase,
        "terminal_state": terminal_state,
        "terminal": terminal,
    }


def _expected_seed_filenames(seed: int) -> tuple[str, ...]:
    return (
        f"seed-{seed}.json",
        f"seed-{seed}-chc-trace.json",
        f"seed-{seed}-lambda-trace.json",
        f"seed-{seed}-status.json",
        f"seed-{seed}-manifest.json",
        f"seed-{seed}-chc-model.joblib",
        f"seed-{seed}-lambda-model.joblib",
    )


def _index_seed_files(rows_dir: Path) -> dict[str, Path]:
    _require(rows_dir.is_dir(), f"rows directory does not exist: {rows_dir}")
    allowed = {
        name for seed in EXPECTED_SEEDS for name in _expected_seed_filenames(seed)
    }
    _require(not any(path.is_symlink() for path in rows_dir.rglob("*")),
             "symlinked evidence is forbidden")
    regular_files = sorted(path for path in rows_dir.rglob("*") if path.is_file())
    _require(
        len(regular_files) == len(allowed) == 210,
        "evidence directory must contain exactly the 210 expected regular files",
    )
    matches: dict[str, list[Path]] = {}
    for path in regular_files:
        _require(path.name in allowed, f"unexpected seed JSON file: {path}")
        matches.setdefault(path.name, []).append(path)
    missing = sorted(allowed - set(matches))
    duplicates = {
        name: [str(path) for path in paths]
        for name, paths in matches.items()
        if len(paths) != 1
    }
    _require(not missing, f"missing seed files: {missing}")
    _require(not duplicates, f"duplicate seed files: {duplicates}")
    _require(len(matches) == len(allowed) == 210, "seed file ledger is not exact")
    return {name: paths[0] for name, paths in matches.items()}


def _validate_status(
    payload: Any,
    *,
    seed: int,
    expected_provenance: Mapping[str, Any],
    expected_artifact_name: str,
    paths: Mapping[str, Path],
) -> None:
    status = _mapping(payload, f"seed {seed} status")
    _require(status.get("schema") == STATUS_SCHEMA, f"seed {seed}: status schema mismatch")
    _require(status.get("seed") == seed, f"seed {seed}: status seed mismatch")
    _require(status.get("classification") == "PASS", f"seed {seed}: status is not PASS")
    _require(status.get("exit_code") == 0, f"seed {seed}: runner exit was non-zero")
    _require(status.get("row_exists") is True, f"seed {seed}: row was not recorded")
    _require(
        status.get("status") == "PASS_INFRASTRUCTURE_AND_SCHEMA",
        f"seed {seed}: status classification detail mismatch",
    )
    _require(
        status.get("scientific_decision") == "NOT_APPLICABLE_PER_SEED",
        f"seed {seed}: per-seed scientific decision must be inapplicable",
    )
    _require(
        status.get("negative_or_null_scientific_result_is_failure") is False,
        f"seed {seed}: negative-result policy changed",
    )
    _require(
        status.get("artifact_name") == expected_artifact_name,
        f"seed {seed}: status artifact name mismatch",
    )
    provenance = _validate_provenance(
        status.get("provenance"),
        label=f"seed {seed} status.provenance",
        expected=expected_provenance,
    )
    _require(provenance == expected_provenance, f"seed {seed}: status provenance mismatch")
    row_name = f"seed-{seed}.json"
    _require(status.get("row_file") == row_name, f"seed {seed}: status row filename mismatch")
    _require(
        _hex(status.get("row_sha256"), f"seed {seed} status row SHA", HEX64)
        == _file_sha256(paths[row_name]),
        f"seed {seed}: status row SHA mismatch",
    )
    _require(
        status.get("objective_calls")
        == {CHC_ARM: EXPECTED_CALLS, LAMBDA_ARM: EXPECTED_CALLS},
        f"seed {seed}: status objective-call ledger mismatch",
    )
    _require(
        status.get("test_evaluations") == {CHC_ARM: 1, LAMBDA_ARM: 1},
        f"seed {seed}: status test-evaluation ledger mismatch",
    )
    trace_sha = _mapping(status.get("trace_sha256"), f"seed {seed} status trace SHA")
    expected_traces = {
        CHC_ARM: f"seed-{seed}-chc-trace.json",
        LAMBDA_ARM: f"seed-{seed}-lambda-trace.json",
    }
    _require(set(trace_sha) == set(expected_traces), f"seed {seed}: status trace arm set mismatch")
    for arm, name in expected_traces.items():
        _require(
            _hex(trace_sha[arm], f"seed {seed} status {arm} trace SHA", HEX64)
            == _file_sha256(paths[name]),
            f"seed {seed}: status {arm} trace SHA mismatch",
        )


def _expected_manifest_contract(provenance: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "protocol_id": PROTOCOL_ID,
        "implementation_sha": provenance["implementation_sha"],
        "data_sha256": {
            "archive": EXPECTED_ARCHIVE_SHA256,
            "train": EXPECTED_TRAIN_SHA256,
            "test": EXPECTED_TEST_SHA256,
        },
        "arms": [CHC_ARM, LAMBDA_ARM],
        "algorithm_id": dict(EXPECTED_ALGORITHM_IDS),
        "budget": {
            "call_unit": "logical_objective_invocation",
            "objective_calls_per_arm": EXPECTED_CALLS,
            "initial_population_calls": EXPECTED_INITIAL_CALLS,
            "objective_cache": False,
            "duplicates_consume_calls": True,
        },
        "objective": {
            "primary": "validation_weighted_balanced_accuracy",
            "secondary": "negative_selected_feature_fraction",
            "comparison": "lexicographic",
        },
        "tie_break": {
            "terminal": "earliest_objective_call",
            CHC_ARM: "stable_first_in_parent_plus_offspring_order",
            LAMBDA_ARM: "uniform_using_arm_local_numpy_rng",
        },
        "reset": {CHC_ARM: False, LAMBDA_ARM: False},
    }


def _validate_manifest(
    payload: Any,
    *,
    seed: int,
    paths: Mapping[str, Path],
    expected_provenance: Mapping[str, Any],
    expected_artifact_name: str,
) -> dict[str, dict[str, Any]]:
    manifest = _mapping(payload, f"seed {seed} manifest")
    _require(
        manifest.get("schema") == MANIFEST_SCHEMA,
        f"seed {seed}: manifest schema mismatch",
    )
    _require(manifest.get("seed") == seed, f"seed {seed}: manifest seed mismatch")
    _require(manifest.get("model_evidence_format") == MODEL_EVIDENCE_SCHEMA,
             f"seed {seed}: model evidence format mismatch")
    _require(
        manifest.get("artifact_name") == expected_artifact_name,
        f"seed {seed}: manifest artifact name mismatch",
    )
    provenance = _validate_provenance(
        manifest.get("provenance"),
        label=f"seed {seed} manifest.provenance",
        expected=expected_provenance,
    )
    _require(provenance == expected_provenance, f"seed {seed}: manifest provenance mismatch")
    contract = _mapping(manifest.get("contract"), f"seed {seed} manifest.contract")
    _walk_finite(contract, f"seed {seed} manifest.contract")
    _require(
        dict(contract) == _expected_manifest_contract(provenance),
        f"seed {seed}: manifest frozen contract mismatch",
    )
    files = _mapping(manifest.get("files"), f"seed {seed} manifest.files")
    manifest_name = f"seed-{seed}-manifest.json"
    expected_names = set(_expected_seed_filenames(seed)) - {manifest_name}
    _require(set(files) == expected_names, f"seed {seed}: manifest file set mismatch")
    normalized: dict[str, dict[str, Any]] = {}
    for name in sorted(expected_names):
        entry = _mapping(files[name], f"seed {seed} manifest.files.{name}")
        digest = _hex(entry.get("sha256"), f"seed {seed} {name} SHA", HEX64)
        size = _strict_int(entry.get("bytes"), f"seed {seed} {name} bytes", minimum=0)
        _require(digest == _file_sha256(paths[name]), f"seed {seed}: {name} SHA mismatch")
        _require(size == paths[name].stat().st_size, f"seed {seed}: {name} size mismatch")
        normalized[name] = {"sha256": digest, "bytes": size}
    return normalized


def _validate_source_ledger(
    path: Path | None,
) -> tuple[dict[int, Any], Any | None, str]:
    if path is None:
        raise EvidenceError("a fixed source run/artifact ledger is required")
    payload = _mapping(_load_json(path), "source artifact verification")
    schema = payload.get("schema")
    _require(
        schema in {SOURCE_LEDGER_SCHEMA, SOURCE_VERIFICATION_SCHEMA},
        "source artifact ledger schema mismatch",
    )
    if schema == SOURCE_VERIFICATION_SCHEMA:
        _require(
            payload.get("verification_status") == "PASS",
            "source artifact verification did not pass",
        )
        mode = "immutable_reaggregation"
    else:
        mode = "campaign_api_snapshot"
    _require(
        isinstance(payload.get("repository"), str) and "/" in payload["repository"],
        "source repository is malformed",
    )
    source_run_id = _strict_int(payload.get("source_run_id"), "source run ID", minimum=1)
    source_run_attempt = _strict_int(
        payload.get("source_run_attempt"), "source run attempt", minimum=1
    )
    _hex(payload.get("source_head_sha"), "source head SHA", HEX40)
    _string(payload.get("source_ref"), "source ref")
    _hex(payload.get("source_workflow_sha"), "source workflow SHA", HEX40)
    _require(
        payload.get("source_workflow_path") == SOURCE_WORKFLOW_PATH,
        "source workflow path mismatch",
    )
    artifacts = _list(payload.get("artifacts"), "source artifacts")
    _require(len(artifacts) == 30, "source artifact ledger must contain 30 artifacts")
    by_seed: dict[int, Any] = {}
    ids: set[int] = set()
    for raw_entry in artifacts:
        entry = _mapping(raw_entry, "source artifact")
        seed = _strict_int(entry.get("seed"), "source artifact seed")
        artifact_id = _strict_int(entry.get("id"), f"source seed {seed} artifact id", minimum=1)
        _require(seed in EXPECTED_SEEDS, f"unexpected source artifact seed {seed}")
        _require(seed not in by_seed, f"duplicate source artifact seed {seed}")
        _require(artifact_id not in ids, f"duplicate source artifact ID {artifact_id}")
        digest = _hex(entry.get("digest"), f"source seed {seed} digest", SHA256_WITH_PREFIX)
        name = _string(entry.get("name"), f"source seed {seed} artifact name")
        entry_attempt = _strict_int(entry.get("run_attempt", source_run_attempt),
                                    f"source seed {seed} attempt", minimum=1)
        _require(entry_attempt <= source_run_attempt, "artifact attempt is from the future")
        _require(
            name
            == f"eu26-21-common-bridge-seed-{seed}-{source_run_id}-{entry_attempt}",
            f"source seed {seed}: artifact name mismatch",
        )
        if schema == SOURCE_VERIFICATION_SCHEMA:
            downloaded = _hex(
                entry.get("downloaded_zip_sha256"),
                f"source seed {seed} downloaded ZIP SHA",
                HEX64,
            )
            _require(
                digest == f"sha256:{downloaded}",
                f"source seed {seed}: ZIP digest mismatch",
            )
            _require(
                entry.get("api_run_id") == payload.get("source_run_id"),
                f"source seed {seed}: run mismatch",
            )
            _require(
                entry.get("api_head_sha") == payload.get("source_head_sha"),
                f"source seed {seed}: head mismatch",
            )
        by_seed[seed] = {**entry, "run_attempt": entry_attempt}
        ids.add(artifact_id)
    _require(set(by_seed) == set(EXPECTED_SEEDS), "source artifact seed ledger mismatch")
    metadata = dict(payload)
    metadata["ledger_file_sha256"] = _file_sha256(path)
    return by_seed, metadata, mode


def _verify_source_file_binding(
    source_entry: Mapping[str, Any], *, seed: int, paths: Mapping[str, Path]
) -> None:
    if "extracted_files" not in source_entry:
        return
    extracted = _list(source_entry.get("extracted_files"), f"source seed {seed} files")
    _require(
        len(extracted) == len(_expected_seed_filenames(seed)) == 7,
        f"source seed {seed}: artifact must contain exactly seven regular files",
    )
    expected_directory = _string(
        source_entry.get("name"), f"source seed {seed} artifact name"
    )
    by_basename: dict[str, Mapping[str, Any]] = {}
    for raw in extracted:
        entry = _mapping(raw, f"source seed {seed} extracted file")
        relative = PurePosixPath(_string(entry.get("path"), "extracted path"))
        _require(
            len(relative.parts) == 2 and relative.parts[0] == expected_directory,
            f"source seed {seed}: extracted file escaped its artifact directory",
        )
        name = relative.name
        _require(
            name in _expected_seed_filenames(seed),
            f"source seed {seed}: unexpected extracted file {name}",
        )
        _require(name not in by_basename, f"source seed {seed}: duplicate extracted {name}")
        by_basename[name] = entry
    _require(
        set(by_basename) == set(_expected_seed_filenames(seed)),
        f"source seed {seed}: extracted file ledger mismatch",
    )
    for name, path in paths.items():
        digest = _hex(by_basename[name].get("sha256"), f"source {name} SHA", HEX64)
        _require(digest == _file_sha256(path), f"source artifact binding failed for {name}")


def _validate_models(row: Mapping[str, Any], *, seed: int, paths: Mapping[str, Path]) -> None:
    from sklearn.tree import DecisionTreeClassifier

    _require(row.get("model_evidence_format") == MODEL_EVIDENCE_SCHEMA, "model format mismatch")
    models = _mapping(row.get("models"), "models")
    _require(set(models) == set(ARM_NAMES), "model arm set mismatch")
    for arm, suffix in ((CHC_ARM, "chc"), (LAMBDA_ARM, "lambda")):
        model = _mapping(models[arm], f"seed {seed} {arm} model")
        name = f"seed-{seed}-{suffix}-model.joblib"
        _require(model.get("schema") == MODEL_EVIDENCE_SCHEMA, "model schema mismatch")
        _require(model.get("seed") == seed and model.get("arm") == arm, "model identity mismatch")
        _require(model.get("file") == name, "model filename mismatch")
        _require(_hex(model.get("sha256"), "model SHA", HEX64) == _file_sha256(paths[name]),
                 "model byte hash mismatch")
        _require(_strict_int(model.get("bytes"), "model size", minimum=1) == paths[name].stat().st_size,
                 "model byte length mismatch")
        terminal = row["arms"][arm]["terminal"]
        _require(_validate_mask(model.get("mask"), "model mask") == terminal["mask"],
                 "model mask differs from validation winner")
        from corrected_applied.data_protocol import TRANSFORMED_FEATURE_NAMES

        expected_names = [name for name, bit in zip(TRANSFORMED_FEATURE_NAMES, terminal["mask"]) if bit]
        _require(model.get("selected_feature_names") == expected_names, "model feature mapping mismatch")
        _require(model.get("classifier") == "DecisionTreeClassifier(random_state=0)", "classifier mismatch")
        _require(model.get("classifier_parameters") == DecisionTreeClassifier(random_state=0).get_params(deep=False),
                 "terminal classifier parameters changed")
        for field in ("preprocessing_fit_partition", "terminal_fit_partition"):
            _require(model.get(field) == "internal_training_only", "model fitting leakage")
        _require(model.get("reload_verification") == "PASS_EXACT_NON_TEST_PROBE", "model reload not verified")
        _require(model.get("probe_source") == "first_8_internal_training_rows" and model.get("probe_rows") == 8,
                 "model probe differs from frozen evidence extension")
        _require(model.get("test_access_during_reload") is False, "test accessed during model reload")
        for field in ("probe_transformed_sha256", "probe_prediction_sha256", "probe_probability_sha256"):
            _hex(model.get(field), field, HEX64)


def _validate_campaign(
    rows_dir: Path,
    *,
    protocol_sha256: str,
    expected_provenance: Mapping[str, Any],
    source_artifacts: Mapping[int, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    file_index = _index_seed_files(rows_dir)
    rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    common_provenance: dict[str, Any] | None = None

    for seed in EXPECTED_SEEDS:
        names = _expected_seed_filenames(seed)
        paths = {name: file_index[name] for name in names}
        row_path = paths[f"seed-{seed}.json"]
        row = _mapping(_load_json(row_path), row_path.name)
        _require(row.get("schema") == ROW_SCHEMA, f"seed {seed}: row schema mismatch")
        _require(row.get("study_id") == STUDY_ID, f"seed {seed}: study ID mismatch")
        _require(row.get("protocol_id") == PROTOCOL_ID, f"seed {seed}: protocol ID mismatch")
        _require(row.get("seed") == seed, f"seed {seed}: row seed mismatch")
        raw_provenance = _mapping(row.get("provenance"), f"seed {seed} row.provenance")
        artifact_name = _string(
            raw_provenance.get("artifact_name"),
            f"seed {seed} row.provenance.artifact_name",
        )
        _require(
            "/" not in artifact_name and "\\" not in artifact_name,
            f"seed {seed}: unsafe artifact name",
        )
        if source_artifacts:
            _require(
                artifact_name == source_artifacts[seed]["name"],
                f"seed {seed}: row artifact name disagrees with API ledger",
            )
        seed_expected = dict(expected_provenance)
        if source_artifacts:
            seed_expected["run_attempt"] = source_artifacts[seed].get(
                "run_attempt", expected_provenance.get("run_attempt")
            )
        provenance = _validate_provenance(
            raw_provenance,
            label=f"seed {seed} row.provenance",
            expected=seed_expected,
        )
        _require(
            provenance["protocol_sha256"] == protocol_sha256,
            f"seed {seed}: row does not bind the supplied protocol",
        )
        shared_provenance = {key: value for key, value in provenance.items() if key != "run_attempt"}
        if common_provenance is None:
            common_provenance = shared_provenance
        else:
            _require(shared_provenance == common_provenance, f"seed {seed}: provenance drift")
        pairing = _validate_pairing(
            row.get("pairing"),
            f"seed {seed} row.pairing",
            seed=seed,
        )

        trace_paths = {
            CHC_ARM: paths[f"seed-{seed}-chc-trace.json"],
            LAMBDA_ARM: paths[f"seed-{seed}-lambda-trace.json"],
        }
        traces = {
            arm: _validate_trace(
                path,
                seed=seed,
                arm=arm,
                expected_provenance=provenance,
                expected_pairing=pairing,
            )
            for arm, path in trace_paths.items()
        }
        _require(
            traces[CHC_ARM]["first_50"] == traces[LAMBDA_ARM]["first_50"],
            f"seed {seed}: the two arms do not share identical first 50 evaluations",
        )
        arms_payload = _mapping(row.get("arms"), f"seed {seed} row.arms")
        _require(set(arms_payload) == set(ARM_NAMES), f"seed {seed}: arm set mismatch")
        arms = {
            CHC_ARM: _validate_arm(
                arms_payload[CHC_ARM],
                seed=seed,
                arm=CHC_ARM,
                expected_trace_name=f"seed-{seed}-chc-trace.json",
                trace_path=trace_paths[CHC_ARM],
                trace=traces[CHC_ARM],
            ),
            LAMBDA_ARM: _validate_arm(
                arms_payload[LAMBDA_ARM],
                seed=seed,
                arm=LAMBDA_ARM,
                expected_trace_name=f"seed-{seed}-lambda-trace.json",
                trace_path=trace_paths[LAMBDA_ARM],
                trace=traces[LAMBDA_ARM],
            ),
        }

        _validate_models(row, seed=seed, paths=paths)
        status_path = paths[f"seed-{seed}-status.json"]
        _validate_status(
            _load_json(status_path),
            seed=seed,
            expected_provenance=provenance,
            expected_artifact_name=artifact_name,
            paths=paths,
        )
        manifest_path = paths[f"seed-{seed}-manifest.json"]
        manifest_files = _validate_manifest(
            _load_json(manifest_path),
            seed=seed,
            paths=paths,
            expected_provenance=provenance,
            expected_artifact_name=artifact_name,
        )
        if source_artifacts:
            _verify_source_file_binding(source_artifacts[seed], seed=seed, paths=paths)

        row_record = {
            "seed": seed,
            "provenance": provenance,
            "pairing": pairing,
            "arms": arms,
            "models": row["models"],
        }
        rows.append(row_record)
        ledger_rows.append(
            {
                "seed": seed,
                "source_artifact": (
                    {
                        "id": source_artifacts[seed]["id"],
                        "name": source_artifacts[seed]["name"],
                        "digest": source_artifacts[seed]["digest"],
                    }
                    if source_artifacts
                    else None
                ),
                "files": {
                    name: {
                        "sha256": _file_sha256(path),
                        "bytes": path.stat().st_size,
                    }
                    for name, path in sorted(paths.items())
                },
                "manifest_bound_files": manifest_files,
                "pairing": pairing,
            }
        )
    return rows, ledger_rows


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    _require(bool(ordered), "cannot take a quantile of an empty sample")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _paired_median_bca(values: Sequence[float]) -> dict[str, Any]:
    _require(len(values) == 30, "paired BCa requires exactly 30 values")
    normalized = [
        _finite_float(value, f"paired value {index}")
        for index, value in enumerate(values, start=1)
    ]
    point = float(statistics.median(normalized))
    generator = random.Random(ANALYSIS_SEED)
    bootstrap: list[float] = []
    n = len(normalized)
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = [normalized[generator.randrange(n)] for _ in range(n)]
        bootstrap.append(float(statistics.median(sample)))

    less = sum(value < point for value in bootstrap)
    equal = sum(value == point for value in bootstrap)
    probability = (less + 0.5 * equal) / BOOTSTRAP_RESAMPLES
    epsilon = 0.5 / BOOTSTRAP_RESAMPLES
    probability = min(max(probability, epsilon), 1.0 - epsilon)
    normal = NormalDist()
    bias = normal.inv_cdf(probability)

    jackknife = [
        float(statistics.median(normalized[:index] + normalized[index + 1 :]))
        for index in range(n)
    ]
    jackknife_mean = statistics.fmean(jackknife)
    centered = [jackknife_mean - value for value in jackknife]
    denominator = 6.0 * sum(value * value for value in centered) ** 1.5
    acceleration = (
        0.0 if denominator == 0.0 else sum(value**3 for value in centered) / denominator
    )

    endpoints: list[float] = []
    adjusted_probabilities: list[float] = []
    for alpha in (0.025, 0.975):
        z_alpha = normal.inv_cdf(alpha)
        inner = bias + z_alpha
        correction = 1.0 - acceleration * inner
        adjusted = alpha if abs(correction) < 1e-12 else normal.cdf(bias + inner / correction)
        adjusted = min(max(adjusted, 0.0), 1.0)
        adjusted_probabilities.append(adjusted)
        endpoints.append(_quantile(bootstrap, adjusted))
    return {
        "method": "paired_median_BCa",
        "analysis_seed": ANALYSIS_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "point_median": point,
        "two_sided_95_lower": endpoints[0],
        "two_sided_95_upper": endpoints[1],
        "adjusted_quantiles": adjusted_probabilities,
        "bias_correction": bias,
        "acceleration": acceleration,
        "paired_values": normalized,
    }


def canonical_sha256(value: Any) -> str:
    """Return the protocol's compact, sorted, ASCII JSON SHA-256 binding."""

    _walk_finite(value, "canonical value")
    return _canonical_sha256(value)


def paired_median_bca(values: Sequence[float]) -> dict[str, Any]:
    """Public deterministic implementation of the frozen 30-pair BCa method."""

    return _paired_median_bca(values)


def analyze_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Apply the frozen decisions to 30 already-normalized paired rows."""

    _require(len(rows) == 30, "analysis requires exactly 30 paired rows")
    return _analyze(rows)


def _analyze(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    quality = [
        row["arms"][LAMBDA_ARM]["terminal"]["test_weighted_balanced_accuracy"]
        - row["arms"][CHC_ARM]["terminal"]["test_weighted_balanced_accuracy"]
        for row in rows
    ]
    quality_interval = _paired_median_bca(quality)
    quality_pass = quality_interval["two_sided_95_lower"] > NONINFERIORITY_MARGIN
    quality_result = {
        "contrast": "lambda_no_reset_minus_chc_harmonized_test_weighted_balanced_accuracy",
        "noninferiority_margin": NONINFERIORITY_MARGIN,
        "operator": "two_sided_95_lower_strictly_greater_than_margin",
        **quality_interval,
        "decision": "PASS_NONINFERIORITY" if quality_pass else "FAIL_NONINFERIORITY",
    }

    auc_values = [
        row["arms"][LAMBDA_ARM]["auc"] - row["arms"][CHC_ARM]["auc"]
        for row in rows
    ]
    auc_interval: dict[str, Any] = _paired_median_bca(auc_values)
    auc_pass = quality_pass and auc_interval["two_sided_95_lower"] > 0.0
    if not quality_pass:
        auc_decision = "BLOCKED_BY_QUALITY_NONINFERIORITY"
        auc_role = "descriptive_interval_confirmatory_claim_blocked"
    elif auc_pass:
        auc_decision = "PASS_AUC_SUPERIORITY"
        auc_role = "confirmatory"
    else:
        auc_decision = "FAIL_AUC_SUPERIORITY"
        auc_role = "confirmatory"
    auc_result = {
        "contrast": "lambda_no_reset_minus_chc_harmonized_normalized_auc",
        "operator": "two_sided_95_lower_strictly_greater_than_zero",
        "role": auc_role,
        **auc_interval,
        "decision": auc_decision,
    }

    post_initial_auc_values = [
        row["arms"][LAMBDA_ARM]["post_initial_auc"]
        - row["arms"][CHC_ARM]["post_initial_auc"]
        for row in rows
    ]
    post_initial_auc_result = {
        "contrast": (
            "lambda_no_reset_minus_chc_harmonized_normalized_auc_calls_51_400"
        ),
        "role": "descriptive_sensitivity_only",
        **_paired_median_bca(post_initial_auc_values),
        "decision": "DESCRIPTIVE_ONLY",
    }

    feature_values = [
        row["arms"][LAMBDA_ARM]["terminal"]["selected_feature_count"]
        - row["arms"][CHC_ARM]["terminal"]["selected_feature_count"]
        for row in rows
    ]
    feature_result = {
        "contrast": "lambda_no_reset_minus_chc_harmonized_selected_feature_count",
        "role": "secondary_descriptive_after_quality_gate",
        "point_median": float(statistics.median(feature_values)),
        "paired_values": feature_values,
        "lambda_fewer": sum(value < 0 for value in feature_values),
        "equal": sum(value == 0 for value in feature_values),
        "lambda_more": sum(value > 0 for value in feature_values),
        "decision": "DESCRIPTIVE_ONLY" if quality_pass else "BLOCKED_BY_QUALITY_NONINFERIORITY",
    }

    if not quality_pass:
        joint = "FAIL_JOINT_BRIDGE_CLAIM_QUALITY_NONINFERIORITY"
    elif not auc_pass:
        joint = "FAIL_JOINT_BRIDGE_CLAIM_AUC_SUPERIORITY"
    else:
        joint = "PASS_JOINT_BRIDGE_CLAIM"
    return {
        "quality_noninferiority": quality_result,
        "auc_superiority": auc_result,
        "auc_calls_51_400_descriptive": post_initial_auc_result,
        "feature_count_secondary": feature_result,
        "joint_decision": joint,
    }


def _report_markdown(report: Mapping[str, Any]) -> str:
    if report.get("protocol_status") != "PASS_STRICT_EVIDENCE_VALIDATION":
        return (
            "# EU26-21 common bridge aggregate\n\n"
            "Protocol status: `FAIL_INVALID_EVIDENCE`.\n\n"
            f"Evidence is not evaluable: {report.get('error', 'unknown validation error')}\n"
        )
    analysis = report["analysis"]
    quality = analysis["quality_noninferiority"]
    auc = analysis["auc_superiority"]
    post_initial_auc = analysis["auc_calls_51_400_descriptive"]
    feature = analysis["feature_count_secondary"]
    lines = [
        "# EU26-21 common bridge aggregate",
        "",
        "Protocol status: `PASS_STRICT_EVIDENCE_VALIDATION`.",
        f"Joint scientific decision: `{analysis['joint_decision']}`.",
        "",
        "## Quality non-inferiority",
        "",
        f"- Decision: `{quality['decision']}`",
        f"- Paired median lambda minus CHC: `{quality['point_median']:.12g}`",
        (
            "- 95% BCa interval: "
            f"`[{quality['two_sided_95_lower']:.12g}, "
            f"{quality['two_sided_95_upper']:.12g}]`"
        ),
        f"- Frozen margin: `{NONINFERIORITY_MARGIN}` (strict lower-bound gate)",
        "",
        "## Anytime-efficiency AUC",
        "",
        f"- Decision: `{auc['decision']}`",
    ]
    if "point_median" in auc:
        lines.extend(
            [
                f"- Paired median lambda minus CHC: `{auc['point_median']:.12g}`",
                (
                    "- 95% BCa interval: "
                    f"`[{auc['two_sided_95_lower']:.12g}, "
                    f"{auc['two_sided_95_upper']:.12g}]`"
                ),
            ]
        )
    else:
        lines.append(
            f"- Descriptive paired median: `{auc['point_median_descriptive']:.12g}`"
        )
    lines.extend(
        [
            "",
            "## Post-initial AUC sensitivity (calls 51-400)",
            "",
            "- Role: `descriptive_sensitivity_only`",
            (
                "- Paired median lambda minus CHC: "
                f"`{post_initial_auc['point_median']:.12g}`"
            ),
            (
                "- 95% BCa interval: "
                f"`[{post_initial_auc['two_sided_95_lower']:.12g}, "
                f"{post_initial_auc['two_sided_95_upper']:.12g}]`"
            ),
            "",
            "## Secondary feature count",
            "",
            f"- Paired median lambda minus CHC: `{feature['point_median']:.12g}`",
            (
                "- Lambda fewer/equal/more pairs: "
                f"`{feature['lambda_fewer']}/{feature['equal']}/{feature['lambda_more']}`"
            ),
            "",
            "A negative or null scientific decision is a protocol-valid result; it is not a CI failure.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_output_set(
    output_dir: Path,
    *,
    report: Mapping[str, Any],
    ledger: Mapping[str, Any],
    status: Mapping[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"
    ledger_path = output_dir / "canonical-ledger.json"
    status_path = output_dir / "aggregate-status.json"
    _write_json(report_path, report)
    markdown_path.write_text(_report_markdown(report), encoding="utf-8")
    _write_json(ledger_path, ledger)
    _write_json(status_path, status)
    output_files = (report_path, markdown_path, ledger_path, status_path)
    aggregate_manifest = {
        "schema": AGGREGATE_MANIFEST_SCHEMA,
        "self_hash_excluded": True,
        "files": {
            path.name: {
                "sha256": _file_sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in output_files
        },
    }
    _write_json(output_dir / "aggregate-manifest.json", aggregate_manifest)


def _build_expected_provenance(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": _hex(
            args.expected_protocol_sha256, "expected protocol SHA", HEX64
        ),
        "protocol_content_freeze_commit_sha": _hex(
            args.expected_content_freeze_commit,
            "expected content-freeze commit",
            HEX40,
        ),
        "implementation_sha": _hex(
            args.expected_implementation_sha, "expected implementation SHA", HEX40
        ),
        "config_sha256": _hex(
            args.expected_config_sha256, "expected config SHA", HEX64
        ),
        "requirements_sha256": (
            _hex(args.expected_requirements_sha256, "expected requirements SHA", HEX64)
            if args.expected_requirements_sha256
            else None
        ),
        "environment_sha256": (
            _hex(args.expected_environment_sha256, "expected environment SHA", HEX64)
            if args.expected_environment_sha256
            else None
        ),
        "run_id": args.expected_run_id,
        "run_attempt": args.expected_run_attempt,
        "ref": args.expected_ref,
        "workflow_sha": _hex(args.expected_workflow_sha, "expected workflow SHA", HEX40),
        "upstream_commit": EXPECTED_UPSTREAM_COMMIT,
        "archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "train_sha256": EXPECTED_TRAIN_SHA256,
        "test_sha256": EXPECTED_TEST_SHA256,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows_dir", type=Path)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--expected-content-freeze-commit", required=True)
    parser.add_argument("--expected-implementation-sha", required=True)
    parser.add_argument("--expected-config-sha256", required=True)
    parser.add_argument("--expected-requirements-sha256")
    parser.add_argument("--expected-environment-sha256")
    parser.add_argument("--expected-run-id", type=int, required=True)
    parser.add_argument("--expected-run-attempt", type=int, required=True)
    parser.add_argument("--expected-ref", required=True)
    parser.add_argument("--expected-workflow-sha", required=True)
    parser.add_argument("--source-artifact-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    try:
        _require(args.expected_run_id > 0, "expected run ID must be positive")
        _require(args.expected_run_attempt > 0, "expected run attempt must be positive")
        expected_provenance = _build_expected_provenance(args)
        protocol_path = args.protocol.resolve()
        protocol_sha = _file_sha256(protocol_path)
        _require(
            protocol_sha == expected_provenance["protocol_sha256"],
            "supplied protocol byte SHA does not match expected SHA",
        )
        protocol = _mapping(_load_json(protocol_path), "protocol")
        _validate_protocol(protocol, protocol_sha)
        source_artifacts, source_metadata, aggregation_mode = _validate_source_ledger(
            args.source_artifact_ledger.resolve() if args.source_artifact_ledger else None
        )
        if source_metadata is not None:
            _require(
                source_metadata.get("source_run_id") == args.expected_run_id,
                "source ledger run ID disagrees with expected run ID",
            )
            _require(
                source_metadata.get("source_run_attempt") == args.expected_run_attempt,
                "source ledger run attempt disagrees with expected attempt",
            )
            _require(
                source_metadata.get("source_head_sha")
                == args.expected_implementation_sha,
                "source ledger head SHA disagrees with implementation SHA",
            )
            _require(
                source_metadata.get("source_ref") == args.expected_ref,
                "source ledger ref disagrees with expected ref",
            )
            _require(
                source_metadata.get("source_workflow_sha")
                == args.expected_workflow_sha,
                "source ledger workflow SHA disagrees with expected workflow SHA",
            )

        rows, ledger_rows = _validate_campaign(
            args.rows_dir.resolve(),
            protocol_sha256=protocol_sha,
            expected_provenance=expected_provenance,
            source_artifacts=source_artifacts,
        )
        ledger_core = {
            "schema": LEDGER_SCHEMA,
            "study_id": STUDY_ID,
            "protocol_id": PROTOCOL_ID,
            "protocol_sha256": protocol_sha,
            "protocol_content_freeze_commit_sha": args.expected_content_freeze_commit,
            "implementation_sha": args.expected_implementation_sha,
            "config_sha256": args.expected_config_sha256,
            "run_id": args.expected_run_id,
            "run_attempt": args.expected_run_attempt,
            "ref": args.expected_ref,
            "workflow_sha": args.expected_workflow_sha,
            "aggregation_mode": aggregation_mode,
            "optimizer_rerun": False,
            "source_artifact_verification": source_metadata,
            "expected_seeds": list(EXPECTED_SEEDS),
            "rows": ledger_rows,
        }
        ledger_sha = _canonical_sha256(ledger_core)
        ledger = {
            **ledger_core,
            "canonicalization": "UTF-8 JSON; sort_keys=true; separators=(',', ':'); ensure_ascii=true",
            "canonical_sha256_scope": "ledger object without canonicalization and digest fields",
            "canonical_sha256": ledger_sha,
        }
        analysis = analyze_rows(rows)
        report = {
            "schema": REPORT_SCHEMA,
            "study_id": STUDY_ID,
            "protocol_id": PROTOCOL_ID,
            "protocol_status": "PASS_STRICT_EVIDENCE_VALIDATION",
            "scientific_result_is_separate_from_ci_status": True,
            "seed_count": len(rows),
            "seeds": list(EXPECTED_SEEDS),
            "canonical_ledger_sha256": ledger_sha,
            "aggregation_mode": aggregation_mode,
            "optimizer_rerun": False,
            "analysis": analysis,
            "claim_boundary": {
                "reset_benefit": False,
                "wall_clock_speedup": False,
                "literal_printed_chc_qx_reproduction": False,
                "cross_dataset_generality": False,
            },
        }
        status = {
            "schema": AGGREGATE_STATUS_SCHEMA,
            "execution_class": "PASS",
            "protocol_valid": True,
            "scientific_decision": analysis["joint_decision"],
            "exit_code": 0,
            "seed_count": len(rows),
            "canonical_ledger_sha256": ledger_sha,
            "aggregation_mode": aggregation_mode,
            "optimizer_rerun": False,
        }
        _write_output_set(output_dir, report=report, ledger=ledger, status=status)
        print(json.dumps(status, sort_keys=True))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        invalid_ledger_core = {
            "schema": LEDGER_SCHEMA,
            "study_id": STUDY_ID,
            "protocol_id": PROTOCOL_ID,
            "validation": "FAIL_INVALID_EVIDENCE",
            "error": error,
            "rows": [],
        }
        invalid_ledger = {
            **invalid_ledger_core,
            "canonicalization": "UTF-8 JSON; sort_keys=true; separators=(',', ':'); ensure_ascii=true",
            "canonical_sha256": _canonical_sha256(invalid_ledger_core),
        }
        invalid_report = {
            "schema": REPORT_SCHEMA,
            "study_id": STUDY_ID,
            "protocol_id": PROTOCOL_ID,
            "protocol_status": "FAIL_INVALID_EVIDENCE",
            "scientific_decision": "NOT_EVALUABLE",
            "error": error,
        }
        invalid_status = {
            "schema": AGGREGATE_STATUS_SCHEMA,
            "execution_class": "PROTOCOL_INVALID",
            "protocol_valid": False,
            "scientific_decision": "NOT_EVALUABLE",
            "exit_code": 1,
            "error": error,
        }
        try:
            _write_output_set(
                output_dir,
                report=invalid_report,
                ledger=invalid_ledger,
                status=invalid_status,
            )
        except Exception as write_exc:
            print(f"failed to write aggregate diagnostics: {write_exc}", file=sys.stderr)
        print(json.dumps(invalid_status, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run one frozen, paired EU26-21 common-bridge seed.

The runner is intentionally fail closed.  It authenticates the protocol,
runtime configuration, implementation checkout, requirements, data files, and
pinned upstream Evolution module before preparing data or calling either
optimizer.  Both validation traces are serialized and hashed before either
terminal official-test evaluation is invoked.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib import metadata as importlib_metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence

import numpy as np


THIS_DIRECTORY = Path(__file__).resolve().parent
CANDIDATE_DIRECTORY = THIS_DIRECTORY.parent
REPOSITORY_ROOT = THIS_DIRECTORY.parents[2]
if str(CANDIDATE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(CANDIDATE_DIRECTORY))

from corrected_applied.data_protocol import (  # noqa: E402
    PREDICTIVE_DIMENSION,
    WeightedBalancedFeatureObjective,
    prepare_corrected_census,
)
from hybrid_1.core import source_density_population  # noqa: E402

try:  # Support both ``python -m`` and direct script execution.
    from .model_evidence import SCHEMA as MODEL_SCHEMA, evaluate_and_persist
    from .search import SearchResult, run_harmonized_chc, run_lambda_no_reset
    from .validate_protocol import validate as validate_protocol
except ImportError:  # pragma: no cover - direct CLI route
    from model_evidence import SCHEMA as MODEL_SCHEMA, evaluate_and_persist
    from search import SearchResult, run_harmonized_chc, run_lambda_no_reset
    from validate_protocol import validate as validate_protocol


HEX_40 = re.compile(r"[0-9a-f]{40}")
HEX_64 = re.compile(r"[0-9a-f]{64}")
STATUS_SCHEMA = "eu26-21-common-bridge-seed-status-v1"
EXPECTED_PROTOCOL_SHA256 = (
    "730cd436db59d23da7dab5e24c49bc7b28d65379136fad7fd2d2370e0a436205"
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> tuple[str, int]:
    content = _json_bytes(value)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest(), len(content)


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def _validated_hex(value: str, label: str, length: int) -> str:
    pattern = HEX_40 if length == 40 else HEX_64
    _require(bool(pattern.fullmatch(value)), f"{label} must be {length} lowercase hex")
    return value


def _validate_config(
    config: Mapping[str, Any],
    protocol: Mapping[str, Any],
) -> None:
    _require(
        config.get("schema") == "eu26-21-common-bridge-config-v1",
        "unexpected runtime config schema",
    )
    _require(config.get("protocol_id") == protocol["protocol_id"], "config protocol mismatch")
    _require(config.get("dimension") == 40, "config dimension changed")
    _require(
        config.get("seed_ledger") == {"first": 41001, "last": 41030, "count": 30},
        "config seed ledger changed",
    )
    rng = config["rng"]
    _require(rng["search_seed_offset"] == 1_000_003, "search seed offset changed")
    _require(rng["initial_mask_seed_offset"] == 1_000_102, "initial-mask seed offset changed")
    _require(rng["chc_stream"] == "python_random.Random", "CHC RNG changed")
    _require(rng["lambda_stream"] == "numpy.random.default_rng", "lambda RNG changed")
    _require(
        rng["initial_mask_stream"] == "numpy.random.default_rng",
        "initial-mask RNG changed",
    )
    budget = config["budget"]
    _require(
        budget
        == {
            "dimension": 40,
            "objective_calls": 400,
            "initial_population_calls": 50,
            "objective_cache": False,
            "duplicates_consume_calls": True,
            "terminal_exact_tie_rule": "earliest_objective_call",
        },
        "runtime budget configuration changed",
    )
    objective = config["objective"]
    _require(
        objective
        == {
            "primary": "validation_weighted_balanced_accuracy",
            "secondary": "negative_selected_feature_fraction",
            "comparison": "lexicographic",
            "auc_calls": [1, 400],
            "descriptive_auc_calls": [51, 400],
        },
        "runtime objective configuration changed",
    )
    source = config["source"]
    _require(
        source["upstream_commit"] == protocol["source_boundary"]["upstream_commit"],
        "config upstream commit differs from protocol",
    )
    _require(source["upstream_evolution_path"] == "code/Evolution.py", "Evolution path changed")
    _require(
        source["upstream_evolution_blob_sha1"]
        == "05b0d8afc02faee688e5d1ff8e24531ae41307c7",
        "Evolution blob changed",
    )
    chc = config["arms"]["chc_harmonized"]
    _require(
        chc["algorithm_id"]
        == "harmonized_pinned_source_chc_feature_mask_search",
        "CHC algorithm ID changed",
    )
    _require(chc["initial_distance"] == 10, "CHC distance changed")
    _require(chc["hux"] == "pinned_source_HUX", "CHC HUX changed")
    _require(
        chc["cataclysmic_mutation_probability"] == 1.0 / 3.0,
        "CHC mutation probability changed",
    )
    _require(
        chc["population_exact_tie_rule"]
        == "stable_first_in_parent_plus_offspring_order",
        "CHC tie rule changed",
    )
    _require(
        chc["terminal_rule"]
        == "fresh_offspring_prefix_and_no_partial_population_update",
        "CHC terminal rule changed",
    )
    lambda_arm = config["arms"]["lambda_no_reset"]
    _require(
        lambda_arm["algorithm_id"]
        == "self_adjusting_one_plus_lambda_lambda_no_reset",
        "lambda algorithm ID changed",
    )
    _require(lambda_arm["lambda_initial"] == 1.0, "initial lambda changed")
    _require(lambda_arm["lambda_min"] == 1.0, "minimum lambda changed")
    _require(lambda_arm["lambda_max"] == 40.0, "maximum lambda changed")
    _require(lambda_arm["update_factor"] == 1.5, "lambda update factor changed")
    _require(lambda_arm["reset"] is False, "lambda reset enabled")
    _require(lambda_arm["workers"] == 1, "lambda workers changed")
    _require(
        lambda_arm["offspring_rounding"] == "nearest_integer_half_up",
        "lambda offspring rounding changed",
    )
    _require(
        lambda_arm["search_exact_tie_rule"]
        == "uniform_using_arm_local_numpy_rng",
        "lambda tie rule changed",
    )
    _require(
        lambda_arm["terminal_rule"]
        == "paired_mutant_crossover_tail_truncated_to_remaining_even_budget",
        "lambda terminal rule changed",
    )
    _require(
        config["schemas"]
        == {
            "row": "eu26-21-common-bridge-row-v1",
            "trace": "eu26-21-common-bridge-trace-v1",
            "status": "eu26-21-common-bridge-seed-status-v1",
            "manifest": "eu26-21-common-bridge-seed-manifest-v1",
        },
        "artifact schemas changed",
    )


def _validate_ci_environment() -> dict[str, Any]:
    values = {
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "ref": os.environ.get("GITHUB_REF", ""),
        "workflow_sha": os.environ.get("BRIDGE_WORKFLOW_SHA", ""),
    }
    _require(values["run_id"].isdigit() and int(values["run_id"]) > 0, "invalid GITHUB_RUN_ID")
    _require(
        values["run_attempt"].isdigit() and int(values["run_attempt"]) > 0,
        "invalid GITHUB_RUN_ATTEMPT",
    )
    _require(values["ref"].startswith("refs/"), "invalid GITHUB_REF")
    _validated_hex(values["workflow_sha"], "BRIDGE_WORKFLOW_SHA", 40)
    return {
        "run_id": int(values["run_id"]),
        "run_attempt": int(values["run_attempt"]),
        "ref": values["ref"],
        "workflow_sha": values["workflow_sha"],
    }


def _verify_upstream_evolution(
    upstream: Path,
    source_config: Mapping[str, Any],
) -> dict[str, str]:
    root = upstream.resolve()
    commit = _git(root, "rev-parse", "HEAD")
    expected_commit = str(source_config["upstream_commit"])
    _require(commit == expected_commit, f"unexpected upstream commit: {commit}")
    relative = str(source_config["upstream_evolution_path"])
    path = root / Path(relative)
    _require(path.is_file(), "pinned upstream Evolution.py is missing")
    expected_blob = str(source_config["upstream_evolution_blob_sha1"])
    committed_blob = _git(root, "rev-parse", f"HEAD:{relative}")
    _require(committed_blob == expected_blob, "committed Evolution.py blob changed")
    working_blob = _git(root, "hash-object", relative)
    _require(working_blob == expected_blob, "working-tree Evolution.py differs from pin")
    source_text = path.read_text(encoding="utf-8")
    for token in ("def HUX", "def CHC", "mutFlipBit"):
        _require(token in source_text, f"pinned Evolution.py lacks {token}")
    return {
        "upstream_commit": commit,
        "upstream_evolution_blob_sha1": committed_blob,
        "upstream_evolution_sha256": _file_sha256(path),
    }


def _requirements_environment(requirements_path: Path) -> dict[str, Any]:
    package_names: list[str] = []
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            package_names.append(line.split("==", 1)[0])
    versions = {
        name: importlib_metadata.version(name)
        for name in sorted(set(package_names) | {"joblib", "threadpoolctl"})
    }
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "packages": versions,
    }


def _array_sha256(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(
        _canonical_bytes(
            {"dtype": contiguous.dtype.str, "shape": list(contiguous.shape)}
        )
    )
    digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def _validation_objective(prepared: Any) -> WeightedBalancedFeatureObjective:
    active = prepared.active_instances
    return WeightedBalancedFeatureObjective(
        x_active=prepared.x_train[active],
        y_active=prepared.y_train[active],
        weight_active=prepared.weight_train[active],
        x_validation=prepared.x_validation,
        y_validation=prepared.y_validation,
        weight_validation=prepared.weight_validation,
    )


def _pairing_payload(
    prepared: Any,
    initial_masks: Sequence[Sequence[int]],
    first_fifty: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    search_seed: int,
    initial_mask_seed: int,
) -> dict[str, Any]:
    split_sha256 = _canonical_sha256(
        {
            "split_seed": prepared.metadata["split_seed"],
            "train_rows": prepared.metadata["train_partition_rows"],
            "validation_rows": prepared.metadata["validation_partition_rows"],
            "train_y_sha256": _array_sha256(prepared.y_train),
            "validation_y_sha256": _array_sha256(prepared.y_validation),
            "train_weight_sha256": _array_sha256(prepared.weight_train),
            "validation_weight_sha256": _array_sha256(prepared.weight_validation),
        }
    )
    evaluator_sha256 = _canonical_sha256(
        {
            "objective": "weighted_balanced_accuracy_then_sparsity",
            "classifier": "DecisionTreeClassifier(random_state=0)",
            "dimension": PREDICTIVE_DIMENSION,
            "split_sha256": split_sha256,
            "active_indices_sha256": prepared.metadata["active_indices_sha256"],
        }
    )
    return {
        "seed": seed,
        "split_seed": prepared.metadata["split_seed"],
        "active_sample_seed": 2_026_081_800 + seed,
        "search_seed": search_seed,
        "initial_mask_seed": initial_mask_seed,
        "split_sha256": split_sha256,
        "active_indices_sha256": prepared.metadata["active_indices_sha256"],
        "evaluator_sha256": evaluator_sha256,
        "initial_masks_sha256": _canonical_sha256(
            [list(mask) for mask in initial_masks]
        ),
        "first_50_evaluations_sha256": _canonical_sha256(list(first_fifty)),
        "initial_mask_count": len(initial_masks),
        "dimension": PREDICTIVE_DIMENSION,
    }


def _assert_trace_has_no_test_key(value: Any, path: str = "trace") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _require("test" not in str(key).lower(), f"test-bearing trace key: {path}.{key}")
            _assert_trace_has_no_test_key(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_trace_has_no_test_key(child, f"{path}[{index}]")


def _arm_row(
    result: SearchResult,
    *,
    algorithm_id: str,
    trace_file: str,
    trace_sha256: str,
    test_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    terminal = result.terminal_payload()
    terminal["test_weighted_balanced_accuracy"] = float(
        test_metrics["weighted"]["balanced_accuracy"]
    )
    terminal["test_metrics"] = dict(test_metrics)
    return {
        "algorithm_id": algorithm_id,
        "objective_calls": result.objective_calls,
        "initial_population_calls": result.initial_population_calls,
        "test_evaluations": 1,
        "reset": result.reset,
        "reset_events": result.reset_events,
        "trace_file": trace_file,
        "trace_sha256": trace_sha256,
        "normalized_auc_best_so_far_validation_wba_1_400": (
            result.normalized_auc_best_so_far_validation_wba_1_400
        ),
        "normalized_auc_best_so_far_validation_wba_51_400": (
            result.normalized_auc_best_so_far_validation_wba_51_400
        ),
        "termination_phase": result.termination_phase,
        "terminal_state": dict(result.terminal_state),
        "terminal": terminal,
    }


def run_paired_seed(
    *,
    protocol_path: Path,
    config_path: Path,
    upstream: Path,
    official_train: Path,
    official_test: Path,
    seed: int,
    expected_sha: str,
    expected_protocol_sha256: str,
    expected_config_sha256: str,
    expected_requirements_sha256: str,
    output_dir: Path,
    artifact_name: str,
) -> dict[str, Any]:
    """Execute and persist one paired seed under the authenticated contract."""

    expected_sha = _validated_hex(expected_sha, "expected implementation SHA", 40)
    expected_protocol_sha256 = _validated_hex(
        expected_protocol_sha256, "expected protocol SHA256", 64
    )
    _require(
        expected_protocol_sha256 == EXPECTED_PROTOCOL_SHA256,
        "expected protocol SHA is not the frozen pre-implementation digest",
    )
    expected_config_sha256 = _validated_hex(
        expected_config_sha256, "expected config SHA256", 64
    )
    expected_requirements_sha256 = _validated_hex(
        expected_requirements_sha256, "expected requirements SHA256", 64
    )
    _require(41001 <= seed <= 41030, "seed is outside frozen ledger 41001..41030")
    _require(bool(artifact_name.strip()), "artifact name must not be empty")
    _require("/" not in artifact_name and "\\" not in artifact_name, "artifact name must be a basename")

    protocol_path = protocol_path.resolve()
    config_path = config_path.resolve()
    requirements_path = CANDIDATE_DIRECTORY / "corrected_applied" / "requirements.txt"
    actual_protocol_sha256 = _file_sha256(protocol_path)
    actual_config_sha256 = _file_sha256(config_path)
    actual_requirements_sha256 = _file_sha256(requirements_path)
    _require(actual_protocol_sha256 == expected_protocol_sha256, "protocol byte SHA256 mismatch")
    _require(actual_config_sha256 == expected_config_sha256, "config byte SHA256 mismatch")
    _require(
        actual_requirements_sha256 == expected_requirements_sha256,
        "requirements byte SHA256 mismatch",
    )

    implementation_sha = _git(REPOSITORY_ROOT, "rev-parse", "HEAD")
    _require(implementation_sha == expected_sha, "implementation checkout SHA mismatch")
    _require(
        _git(
            REPOSITORY_ROOT,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
        == "",
        "implementation checkout is not clean",
    )
    ci = _validate_ci_environment()
    _require(ci["workflow_sha"] == expected_sha, "workflow SHA differs from implementation")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_config(config, protocol)
    protocol_validation = validate_protocol(
        protocol_path,
        protocol_path.with_name("PROTOCOL.md"),
    )
    _require(
        protocol_validation["protocol_sha256"] == actual_protocol_sha256,
        "protocol validator hash mismatch",
    )
    source = _verify_upstream_evolution(upstream, config["source"])

    actual_train_sha256 = _file_sha256(official_train.resolve())
    actual_test_sha256 = _file_sha256(official_test.resolve())
    _require(
        actual_train_sha256 == protocol["data_protocol"]["train_sha256"],
        "official training data SHA256 mismatch",
    )
    _require(
        actual_test_sha256 == protocol["data_protocol"]["test_sha256"],
        "official test data SHA256 mismatch",
    )
    environment = _requirements_environment(requirements_path)
    environment_sha256 = _canonical_sha256(environment)
    implementation_files = {
        str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"): _file_sha256(path)
        for path in (
            THIS_DIRECTORY / "__init__.py",
            THIS_DIRECTORY / "search.py",
            THIS_DIRECTORY / "run_seed.py",
            THIS_DIRECTORY / "model_evidence.py",
            THIS_DIRECTORY / "trace_contract.py",
            THIS_DIRECTORY / "validate_protocol.py",
            CANDIDATE_DIRECTORY / "corrected_applied" / "data_protocol.py",
            CANDIDATE_DIRECTORY / "hybrid_1" / "core.py",
            config_path,
        )
    }
    implementation_files_sha256 = _canonical_sha256(implementation_files)

    prepared = prepare_corrected_census(
        official_train.resolve(),
        official_test.resolve(),
        seed=seed,
        active_sample_size=protocol["data_protocol"]["active_sample_size"],
    )
    _require(
        prepared.metadata["predictive_dimension"] == config["dimension"],
        "prepared data dimension differs from runtime config",
    )
    objective = _validation_objective(prepared)
    search_seed = seed + config["rng"]["search_seed_offset"]
    initial_mask_seed = seed + config["rng"]["initial_mask_seed_offset"]
    initial_rng = np.random.default_rng(initial_mask_seed)
    initial_masks = tuple(
        source_density_population(
            config["budget"]["initial_population_calls"],
            config["dimension"],
            initial_rng,
        )
    )

    chc_config = config["arms"]["chc_harmonized"]
    lambda_config = config["arms"]["lambda_no_reset"]
    chc_result = run_harmonized_chc(
        objective,
        initial_masks,
        seed=search_seed,
        budget=config["budget"]["objective_calls"],
        initial_distance=chc_config["initial_distance"],
        cataclysmic_mutation_probability=chc_config[
            "cataclysmic_mutation_probability"
        ],
    )
    lambda_result = run_lambda_no_reset(
        objective,
        initial_masks,
        seed=search_seed,
        budget=config["budget"]["objective_calls"],
        lambda_initial=lambda_config["lambda_initial"],
        lambda_min=lambda_config["lambda_min"],
        lambda_max=lambda_config["lambda_max"],
        update_factor=lambda_config["update_factor"],
    )
    _require(chc_result.objective_calls == 400, "CHC did not use exactly 400 calls")
    _require(lambda_result.objective_calls == 400, "lambda arm did not use exactly 400 calls")
    _require(chc_result.reset_events == 0 and lambda_result.reset_events == 0, "unexpected reset event")

    chc_first_fifty = [record.to_dict() for record in chc_result.evaluations[:50]]
    lambda_first_fifty = [record.to_dict() for record in lambda_result.evaluations[:50]]
    _require(
        chc_first_fifty == lambda_first_fifty,
        "paired arms disagree on ordered first 50 evaluations",
    )
    pairing = _pairing_payload(
        prepared,
        initial_masks,
        chc_first_fifty,
        seed=seed,
        search_seed=search_seed,
        initial_mask_seed=initial_mask_seed,
    )
    search_provenance = {
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": actual_protocol_sha256,
        "protocol_content_freeze_commit_sha": protocol_validation[
            "protocol_content_freeze_commit_sha"
        ],
        "content_freeze_commit_sha": protocol_validation[
            "protocol_content_freeze_commit_sha"
        ],
        "config_sha256": actual_config_sha256,
        "requirements_sha256": actual_requirements_sha256,
        "implementation_sha": implementation_sha,
        "implementation_files_sha256": implementation_files_sha256,
        "environment_sha256": environment_sha256,
        **source,
    }

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"seed-{seed}"
    chc_trace_name = f"{prefix}-chc-trace.json"
    lambda_trace_name = f"{prefix}-lambda-trace.json"
    chc_trace = chc_result.to_trace_dict(
        seed=seed,
        provenance=search_provenance,
        pairing=pairing,
    )
    lambda_trace = lambda_result.to_trace_dict(
        seed=seed,
        provenance=search_provenance,
        pairing=pairing,
    )
    _assert_trace_has_no_test_key(chc_trace)
    _assert_trace_has_no_test_key(lambda_trace)

    # This is the leakage barrier: complete search traces and immutable terminal
    # masks are serialized and hashed before the first official-test call.
    chc_trace_sha256, chc_trace_bytes = _write_json(
        output_dir / chc_trace_name,
        chc_trace,
    )
    lambda_trace_sha256, lambda_trace_bytes = _write_json(
        output_dir / lambda_trace_name,
        lambda_trace,
    )
    terminal_masks = (
        tuple(chc_result.terminal_mask),
        tuple(lambda_result.terminal_mask),
    )
    model_provenance = {**search_provenance, **ci}
    chc_test_metrics, chc_model = evaluate_and_persist(
        prepared, terminal_masks[0], path=output_dir / f"{prefix}-chc-model.joblib",
        seed=seed, arm="chc_harmonized", provenance=model_provenance,
    )
    lambda_test_metrics, lambda_model = evaluate_and_persist(
        prepared, terminal_masks[1], path=output_dir / f"{prefix}-lambda-model.joblib",
        seed=seed, arm="lambda_no_reset", provenance=model_provenance,
    )

    provenance = {
        **search_provenance,
        "archive_sha256": protocol["data_protocol"]["archive_sha256"],
        "train_sha256": actual_train_sha256,
        "test_sha256": actual_test_sha256,
        "environment": environment,
        "run_id": ci["run_id"],
        "run_attempt": ci["run_attempt"],
        "ref": ci["ref"],
        "workflow_sha": ci["workflow_sha"],
        "artifact_name": artifact_name,
        "implementation_files": implementation_files,
    }
    row = {
        "schema": config["schemas"]["row"],
        "study_id": protocol["study_id"],
        "protocol_id": protocol["protocol_id"],
        "seed": seed,
        "provenance": provenance,
        "pairing": pairing,
        "model_evidence_format": MODEL_SCHEMA,
        "models": {"chc_harmonized": chc_model, "lambda_no_reset": lambda_model},
        "arms": {
            "chc_harmonized": _arm_row(
                chc_result,
                algorithm_id=chc_config["algorithm_id"],
                trace_file=chc_trace_name,
                trace_sha256=chc_trace_sha256,
                test_metrics=chc_test_metrics,
            ),
            "lambda_no_reset": _arm_row(
                lambda_result,
                algorithm_id=lambda_config["algorithm_id"],
                trace_file=lambda_trace_name,
                trace_sha256=lambda_trace_sha256,
                test_metrics=lambda_test_metrics,
            ),
        },
    }
    row_name = f"{prefix}.json"
    row_sha256, row_bytes = _write_json(output_dir / row_name, row)
    status_name = f"{prefix}-status.json"
    status = {
        "schema": config["schemas"]["status"],
        "seed": seed,
        "classification": "PASS",
        "exit_code": 0,
        "row_exists": True,
        "provenance": provenance,
        "status": "PASS_INFRASTRUCTURE_AND_SCHEMA",
        "scientific_decision": "NOT_APPLICABLE_PER_SEED",
        "negative_or_null_scientific_result_is_failure": False,
        "artifact_name": artifact_name,
        "objective_calls": {"chc_harmonized": 400, "lambda_no_reset": 400},
        "test_evaluations": {"chc_harmonized": 1, "lambda_no_reset": 1},
        "row_file": row_name,
        "row_sha256": row_sha256,
        "trace_sha256": {
            "chc_harmonized": chc_trace_sha256,
            "lambda_no_reset": lambda_trace_sha256,
        },
    }
    status_sha256, status_bytes = _write_json(output_dir / status_name, status)
    files = {
        model["file"]: {"sha256": model["sha256"], "bytes": model["bytes"]}
        for model in (chc_model, lambda_model)
    }
    files.update({
        row_name: {
            "sha256": row_sha256,
            "bytes": row_bytes,
        },
        chc_trace_name: {
            "sha256": chc_trace_sha256,
            "bytes": chc_trace_bytes,
        },
        lambda_trace_name: {
            "sha256": lambda_trace_sha256,
            "bytes": lambda_trace_bytes,
        },
        status_name: {
            "sha256": status_sha256,
            "bytes": status_bytes,
        },
    })
    manifest = {
        "schema": config["schemas"]["manifest"],
        "seed": seed,
        "artifact_name": artifact_name,
        "model_evidence_format": MODEL_SCHEMA,
        "provenance": provenance,
        "contract": {
            "protocol_id": protocol["protocol_id"],
            "implementation_sha": implementation_sha,
            "data_sha256": {
                "archive": protocol["data_protocol"]["archive_sha256"],
                "train": actual_train_sha256,
                "test": actual_test_sha256,
            },
            "arms": ["chc_harmonized", "lambda_no_reset"],
            "algorithm_id": {
                "chc_harmonized": chc_config["algorithm_id"],
                "lambda_no_reset": lambda_config["algorithm_id"],
            },
            "budget": {
                "call_unit": "logical_objective_invocation",
                "objective_calls_per_arm": config["budget"]["objective_calls"],
                "initial_population_calls": config["budget"][
                    "initial_population_calls"
                ],
                "objective_cache": config["budget"]["objective_cache"],
                "duplicates_consume_calls": config["budget"][
                    "duplicates_consume_calls"
                ],
            },
            "objective": {
                "primary": config["objective"]["primary"],
                "secondary": config["objective"]["secondary"],
                "comparison": config["objective"]["comparison"],
            },
            "tie_break": {
                "terminal": config["budget"]["terminal_exact_tie_rule"],
                "chc_harmonized": chc_config["population_exact_tie_rule"],
                "lambda_no_reset": lambda_config["search_exact_tie_rule"],
            },
            "reset": {
                "chc_harmonized": chc_result.reset,
                "lambda_no_reset": lambda_result.reset,
            },
        },
        "files": files,
        "manifest_self_hash_excluded": True,
    }
    manifest_name = f"{prefix}-manifest.json"
    _write_json(output_dir / manifest_name, manifest)
    return row


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--official-train", type=Path, required=True)
    parser.add_argument("--official-test", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--expected-config-sha256", required=True)
    parser.add_argument("--expected-requirements-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--artifact-name", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        row = run_paired_seed(
            protocol_path=args.protocol,
            config_path=args.config,
            upstream=args.upstream,
            official_train=args.official_train,
            official_test=args.official_test,
            seed=args.seed,
            expected_sha=args.expected_sha,
            expected_protocol_sha256=args.expected_protocol_sha256,
            expected_config_sha256=args.expected_config_sha256,
            expected_requirements_sha256=args.expected_requirements_sha256,
            output_dir=args.output_dir,
            artifact_name=args.artifact_name,
        )
    except Exception as error:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": STATUS_SCHEMA,
            "seed": args.seed,
            "classification": "FAIL",
            "exit_code": 1,
            "row_exists": (
                args.output_dir / f"seed-{args.seed}.json"
            ).is_file(),
            "status": "FAIL_INFRASTRUCTURE_OR_SCHEMA",
            "scientific_decision": "NOT_APPLICABLE_PER_SEED",
            "error_type": type(error).__name__,
            "error": str(error),
        }
        _write_json(args.output_dir / f"seed-{args.seed}-status.json", failure)
        raise
    print(
        json.dumps(
            {
                "schema": row["schema"],
                "seed": row["seed"],
                "status": "PASS_INFRASTRUCTURE_AND_SCHEMA",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

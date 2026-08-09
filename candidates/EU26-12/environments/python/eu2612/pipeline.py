"""Compose authenticated EU26-12 metadata, code, range, endpoint, and controls."""

from __future__ import annotations

from typing import Any, Mapping

from .artifact import parse_companion_dat, parse_endpoint
from .code import validate_code_archive, validate_runner, validate_zenodo_record
from .controls import fixture_report
from .zip64 import RangeReader, extract_member, inspect_archive


def verify_artifact_inputs(
    *,
    contract: Mapping[str, Any],
    zenodo_record: bytes,
    code_archive: bytes,
    runner: bytes,
    raw_reader: RangeReader,
) -> dict[str, Any]:
    """Verify all bounded inputs and return an unbound evidence report."""

    metadata = validate_zenodo_record(zenodo_record, contract)
    code = validate_code_archive(code_archive, contract)
    runner_identity = validate_runner(runner, contract)
    layout, entries = inspect_archive(raw_reader, contract)
    json_member = extract_member(raw_reader, entries, contract["raw_members"]["json"])
    dat_member = extract_member(raw_reader, entries, contract["raw_members"]["dat"])
    endpoint = parse_endpoint(json_member.payload, contract)
    dat = parse_companion_dat(
        dat_member.payload,
        contract,
        expected_run_evaluations=endpoint.run_evaluations,
    )
    controls = fixture_report(contract)
    return {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-12",
        "status": "TARGETED_ARTIFACT_REPLAY_ONLY",
        "paper_mapping": "PAPER_EXPERIMENT_ARTIFACT_MAPPING",
        "artifact_gate": "PASS_ARTIFACT_ENDPOINT",
        "metadata_gate": "PASS_ZENODO_METADATA",
        "code_gate": "PASS_CODE_IDENTITY",
        "range_gate": "PASS_RANGE_AUTHENTICATED_MEMBER",
        "control_gate": "PASS_CONTROL_TRANSITIONS",
        "forbidden_claims": contract["forbidden_claims"],
        "mandatory_conflicts": [
            "exact_single_run_value_not_printed_in_paper",
            "static_code_archive_is_not_exact_upstream_git_tree",
            "upstream_dependencies_have_lower_bounds_only",
            "legacy_numpy_rng_api_without_exact_numpy_lock",
            "default_argsort_ties_not_explicitly_stabilized",
            "released_F_memory_uses_arithmetic_not_Lehmer_mean",
            "initialization_excluded_from_used_budget",
            "whole_generation_stop_overshoots_to_50002",
            "DAT_rounds_exact_JSON_value_to_zero",
            "full_raw_archive_md5_declared_not_recomputed",
        ],
        "zenodo": metadata,
        "code": code,
        "runner": runner_identity,
        "zip64": {
            "archive_bytes": layout.archive_size,
            "entry_count": layout.entry_count,
            "central_directory_offset": layout.central_directory_offset,
            "central_directory_bytes": layout.central_directory_bytes,
            "central_directory_sha256": layout.central_directory_sha256,
            "tail_sha256": layout.tail_sha256,
            "zip64_eocd_offset": layout.zip64_eocd_offset,
            "zip64_locator_offset": layout.zip64_locator_offset,
            "classic_eocd_offset": layout.classic_eocd_offset,
            "full_archive_md5": contract["zenodo_files"]["raw_data.zip"]["md5"],
            "full_archive_md5_status": "ZENODO_DECLARED_NOT_RECOMPUTED",
        },
        "members": {
            "json": {
                "path": json_member.entry.path,
                "bytes": len(json_member.payload),
                "crc32": f"{json_member.entry.crc32:08x}",
                "sha256": json_member.sha256,
            },
            "dat": {
                "path": dat_member.entry.path,
                "bytes": len(dat_member.payload),
                "crc32": f"{dat_member.entry.crc32:08x}",
                "sha256": dat_member.sha256,
            },
        },
        "endpoint": {
            "json_pointer": contract["endpoint"]["json_pointer"],
            "run_count": endpoint.run_count,
            "instance": endpoint.selected_instance,
            "seed": endpoint.selected_seed,
            "logged_evaluations": endpoint.logged_evaluations,
            "best_evaluation": endpoint.best_evaluation,
            "best_y_decimal": endpoint.best_y_decimal,
            "ioh_version": endpoint.ioh_version,
        },
        "dat_diagnostic": {
            "run_count": dat.run_count,
            "row_count": dat.row_count,
            "first_run_final_evaluation": dat.first_run_final_evaluation,
            "first_run_final_raw_y": dat.first_run_final_raw_y,
            "accepted_as_exact_endpoint": False,
        },
        "control_fixtures": controls,
    }

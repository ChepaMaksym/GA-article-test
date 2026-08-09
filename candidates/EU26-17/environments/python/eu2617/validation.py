"""Compose the EU26-17 formula/source evidence report without replay claims."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .evidence import (
    authenticate_uci_archive,
    parse_experiment_protocol,
    parse_paper_table,
    parse_parkinson_csv,
    parse_parkinson_loader,
)
from .formula import RateState, SAGA1Config, adjust_rates
from .source_probe import authenticate_sources, execute_source_methods


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _fixture_results(
    fixture: dict[str, Any],
    source: str,
) -> list[dict[str, object]]:
    tolerance = float(fixture["tolerance"])
    config = SAGA1Config(**fixture["config"])
    results: list[dict[str, object]] = []
    for case in fixture["cases"]:
        state = RateState(**case["state"])
        clean = adjust_rates(case["fitness"], state, config)
        source_result = execute_source_methods(source, case["fitness"], state, config)
        expected = case["expected"]
        values = {
            "gdm": clean.gdm,
            "mutation_rate": clean.current.mutation_rate,
            "crossover_rate": clean.current.crossover_rate,
        }
        for name, actual in values.items():
            if not math.isclose(
                actual, float(expected[name]), rel_tol=0.0, abs_tol=tolerance
            ):
                raise ValueError(
                    f"{case['name']} clean-room {name} mismatch: "
                    f"{actual} != {expected[name]}"
                )
            if not math.isclose(
                actual, float(source_result[name]), rel_tol=0.0, abs_tol=tolerance
            ):
                raise ValueError(
                    f"{case['name']} source-body {name} mismatch: "
                    f"{source_result[name]} != {actual}"
                )
        if clean.branch != expected["branch"]:
            raise ValueError(f"{case['name']} branch mismatch")
        results.append(
            {
                "name": case["name"],
                **values,
                "branch": clean.branch,
                "authenticated_source_body_match": True,
            }
        )
    return results


def _equality_witnesses(config: SAGA1Config) -> list[dict[str, object]]:
    witnesses = [
        ("equal_v_min", [1.0] + [0.0] * 199, config.v_min),
        ("equal_v_max", [1.0] * 3 + [0.0] * 17, config.v_max),
    ]
    result: list[dict[str, object]] = []
    for name, fitness, expected in witnesses:
        transition = adjust_rates(fitness, RateState(), config)
        if transition.gdm != expected:
            raise ValueError(
                f"{name} did not construct exact equality: {transition.gdm!r}"
            )
        if transition.current != RateState() or transition.branch != "no_change":
            raise ValueError(f"{name} changed a rate at threshold equality")
        result.append(
            {
                "name": name,
                "gdm": transition.gdm,
                "mutation_rate": transition.current.mutation_rate,
                "crossover_rate": transition.current.crossover_rate,
                "branch": transition.branch,
            }
        )
    return result


def _source_guard_divergence(source: str) -> dict[str, object]:
    zero = execute_source_methods(source, [0.0, 0.0])
    if not math.isnan(float(zero["gdm"])):
        raise ValueError("upstream zero-maximum witness no longer produces NaN")
    if zero["mutation_rate"] != 0.025 or zero["crossover_rate"] != 0.75:
        raise ValueError("upstream zero-maximum witness unexpectedly changes rates")
    nonfinite = execute_source_methods(source, [float("nan"), 1.0])
    if not math.isnan(float(nonfinite["gdm"])):
        raise ValueError("upstream NaN witness no longer produces NaN")
    if nonfinite["mutation_rate"] != 0.025 or nonfinite["crossover_rate"] != 0.75:
        raise ValueError("upstream NaN witness unexpectedly changes rates")
    empty_error: str | None = None
    try:
        execute_source_methods(source, [])
    except ValueError as exc:
        empty_error = type(exc).__name__ + ": " + str(exc)
    if empty_error is None:
        raise ValueError("upstream empty-population witness unexpectedly succeeded")
    return {
        "upstream_has_explicit_guard": False,
        "upstream_zero_maximum": {
            "gdm": "NaN",
            "rates_unchanged": True,
            "runtime_warnings": zero["warnings"],
        },
        "upstream_nonfinite": {
            "gdm": "NaN",
            "rates_unchanged": True,
            "runtime_warnings": nonfinite["warnings"],
        },
        "upstream_empty_population": {
            "result": "NUMPY_REDUCTION_ERROR_NOT_EXPLICIT_SOURCE_GUARD",
            "error": empty_error,
        },
        "clean_room_policy": "REJECT_BEFORE_DIVISION",
        "attribution": "VALIDATION_HARNESS_ONLY",
    }


def _parse_octave_tsv(
    path: Path,
    fixture: dict[str, Any],
) -> dict[str, object]:
    expected_by_name = {case["name"]: case["expected"] for case in fixture["cases"]}
    tolerance = float(fixture["tolerance"])
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    if {row["name"] for row in rows} != set(expected_by_name):
        raise ValueError("Octave output case set differs from the frozen fixture")
    for row in rows:
        expected = expected_by_name[row["name"]]
        for name in ("gdm", "mutation_rate", "crossover_rate"):
            if not math.isclose(
                float(row[name]), float(expected[name]), rel_tol=0.0, abs_tol=tolerance
            ):
                raise ValueError(
                    f"Octave {row['name']} {name} mismatch: "
                    f"{row[name]} != {expected[name]}"
                )
        if row["branch"] != expected["branch"]:
            raise ValueError(f"Octave {row['name']} branch mismatch")
    return {
        "status": "PASS_CROSS_LANGUAGE",
        "environment": "MATLAB_COMPATIBLE_GNU_OCTAVE",
        "case_count": len(rows),
        "absolute_tolerance": tolerance,
    }


def build_report(
    candidate_root: Path,
    core_repo: Path,
    experiment_repo: Path,
    paper_pdf: Path,
    uci_archive: Path,
    octave_tsv: Path | None = None,
) -> dict[str, object]:
    contract = _load_json(candidate_root / "config" / "verification_contract.json")
    amendment = _load_json(candidate_root / "config" / "amendment-001.json")
    object_amendment = _load_json(candidate_root / "config" / "amendment-002.json")
    fixture = _load_json(candidate_root / "fixtures" / "transition_cases.json")
    source_evidence, source, members = authenticate_sources(
        core_repo, experiment_repo, contract
    )
    resolved_addition = source_evidence["core_algorithm_addition"]
    expected_addition = object_amendment["algorithm_addition"]
    for actual_key, expected_key in (
        ("requested_revision", "requested_revision"),
        ("commit", "resolved_commit"),
        ("tree", "tree"),
    ):
        if resolved_addition[actual_key] != expected_addition[expected_key]:
            raise ValueError(
                "algorithm-addition object resolution differs from amendment 002: "
                f"{actual_key}={resolved_addition[actual_key]}"
            )
    protocol = parse_experiment_protocol(members)
    loader = parse_parkinson_loader(members["problems/datasets/base.py"])
    dataset = parse_parkinson_csv(
        members["problems/datasets/data/parkinson.csv"], loader
    )
    uci = authenticate_uci_archive(
        uci_archive, members["problems/datasets/data/parkinson.csv"]
    )
    paper = parse_paper_table(paper_pdf)
    if dataset["input_dimension"] != paper["input_dimension"]:
        raise ValueError("loader/CSV input dimension does not match paper Table I")
    if dataset["rows"] != paper["sample_count"]:
        raise ValueError("CSV row count does not match paper Table I")
    if amendment["overrides"]["c2_count"] != dataset["input_dimension"]:
        raise ValueError("amendment C2 count differs from authenticated evidence")
    if amendment["overrides"]["g7_license"] != uci["license"]:
        raise ValueError("amendment license differs from the primary-input record")

    transitions = _fixture_results(fixture, source)
    equality = _equality_witnesses(SAGA1Config(**fixture["config"]))
    cross_language: dict[str, object]
    outcomes = [
        "PASS_SOURCE_IDENTITY",
        "PASS_SOURCE_METHOD_TRANSITIONS",
        "PASS_PARKINSON_DIMENSION_FACT",
        "PASS_APPLIED_DIMENSION",
        "PASS_LAWFUL_INPUT",
        "HARD_FAIL_ELIGIBILITY_UNCHANGED",
    ]
    if octave_tsv is None:
        cross_language = {"status": "NOT_RUN", "reason": "no Octave TSV supplied"}
    else:
        cross_language = _parse_octave_tsv(octave_tsv, fixture)
        outcomes.insert(2, "PASS_CROSS_LANGUAGE")
    allowed_outcomes = set(contract["permitted_outcomes"]) | set(
        amendment["new_permitted_outcomes"]
    )
    if not set(outcomes).issubset(allowed_outcomes):
        raise ValueError(f"validator attempted an unpermitted outcome: {outcomes}")
    forbidden_outcomes = set(contract["forbidden_claims"])
    if forbidden_outcomes.intersection(outcomes):
        raise ValueError("validator attempted a forbidden claim")

    report = {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-17",
        "artifact_scope": "FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY",
        "eligibility_status": "HARD_FAIL",
        "eligibility_score": None,
        "published_numeric_endpoint": None,
        "acceptance_tolerance": None,
        "effective_amendments": [1, 2],
        "effective_gate_status": {
            "direct_only": "pass",
            "c2_meaningful_applied_parameters": "pass",
            "g7_lawful_reproducible_inputs": "pass",
            "g8_literal_numeric_published_target": "fail",
            "g9_stochastic_protocol_and_provenance": "fail",
            "g10_source_native_historical_replay": "fail",
        },
        "outcomes": outcomes,
        "source_identity": source_evidence,
        "source_method_transitions": {
            "status": "PASS_SOURCE_METHOD_TRANSITIONS",
            "fixture_cases": transitions,
            "threshold_equalities": equality,
            "guard_divergence": _source_guard_divergence(source),
        },
        "cross_language": cross_language,
        "experiment_protocol": protocol,
        "parkinson": {
            "status": "PASS_PARKINSON_DIMENSION_FACT",
            "applied_dimension_status": "PASS_APPLIED_DIMENSION",
            "loader": loader,
            "repository_data": dataset,
            "uci_primary_input": uci,
            "paper_table": paper,
        },
        "claim_boundary": {
            "decisive_failure": "G8_NO_LITERAL_UNAMBIGUOUS_NUMERIC_PAPER_CELL",
            "raw_mlruns_present": False,
            "author_pinned_experiment_core": False,
            "historical_execution_revision_proven": False,
            "forbidden_claims": contract["forbidden_claims"],
            "approximate_prose_used_as_target": False,
            "paper_plot_digitization_used": False,
        },
    }
    json.dumps(report, allow_nan=False)
    return report


def write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

"""Strict IOH JSON/DAT parsers for the frozen EU26-12 endpoint."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence


DAT_ROW = re.compile(r"(?P<evaluations>[1-9][0-9]*) (?P<raw_y>(?:0|[1-9][0-9]*)\.[0-9]{10})")


class ArtifactError(ValueError):
    """Raised when an authenticated member violates frozen semantic shape."""


@dataclass(frozen=True)
class EndpointResult:
    run_count: int
    selected_instance: int
    selected_seed: int
    logged_evaluations: int
    best_evaluation: int
    best_y_decimal: str
    ioh_version: str
    run_evaluations: tuple[int, ...]


@dataclass(frozen=True)
class DatSummary:
    run_count: int
    row_count: int
    first_run_final_evaluation: int
    first_run_final_raw_y: str


def _reject_constant(token: str) -> None:
    raise ArtifactError(f"non-finite JSON constant is forbidden: {token}")


def _unique_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ArtifactError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, name: str) -> None:
    observed = set(value)
    if observed != expected:
        raise ArtifactError(f"{name} keys differ: {sorted(observed)!r}")


def _integer(value: Any, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ArtifactError(f"{name} must be an integer >= {minimum}")
    return value


def _decimal(value: Any, *, name: str, minimum: Decimal | None = None) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ArtifactError(f"{name} must be a finite JSON decimal")
    if minimum is not None and value < minimum:
        raise ArtifactError(f"{name} is below {minimum}")
    return value


def parse_endpoint(payload: bytes, contract: Mapping[str, Any]) -> EndpointResult:
    """Parse exact IOH JSON and bind its first eligible run to seed zero."""

    if not isinstance(payload, bytes):
        raise ArtifactError("JSON member must be bytes")
    if b"\x00" in payload or b"\r" in payload:
        raise ArtifactError("JSON member contains NUL or CR bytes")
    try:
        value = json.loads(
            payload.decode("utf-8", errors="strict"),
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (UnicodeError, json.JSONDecodeError, InvalidOperation) as error:
        raise ArtifactError(f"JSON member is invalid: {error}") from error
    if not isinstance(value, dict):
        raise ArtifactError("IOH JSON root must be an object")
    _exact_keys(
        value,
        {"version", "suite", "function_id", "function_name", "maximization", "algorithm", "attributes", "scenarios"},
        name="IOH root",
    )
    if value["version"] != "0.3.5" or value["suite"] != "unknown_suite":
        raise ArtifactError("IOH logger version or suite differs")
    if value["function_id"] != 1 or value["function_name"] != "Sphere":
        raise ArtifactError("IOH function identity differs")
    if value["maximization"] is not False:
        raise ArtifactError("selected endpoint must be a minimization run")
    if value["attributes"] != ["evaluations", "raw_y"]:
        raise ArtifactError("IOH logged attributes differ")
    algorithm = value["algorithm"]
    if not isinstance(algorithm, dict):
        raise ArtifactError("algorithm metadata must be an object")
    _exact_keys(algorithm, {"name", "info"}, name="algorithm")
    if algorithm != {"name": "L-SHADE", "info": "algorithm_info"}:
        raise ArtifactError("algorithm metadata differs")
    scenarios = value["scenarios"]
    if not isinstance(scenarios, list) or len(scenarios) != 1:
        raise ArtifactError("exactly one dimension scenario is required")
    scenario = scenarios[0]
    if not isinstance(scenario, dict):
        raise ArtifactError("scenario must be an object")
    _exact_keys(scenario, {"dimension", "path", "runs"}, name="scenario")
    endpoint = contract["endpoint"]
    if scenario["dimension"] != endpoint["dimension"]:
        raise ArtifactError("scenario dimension differs")
    expected_dat = "data_f1_Sphere/IOHprofiler_f1_DIM20.dat"
    if scenario["path"] != expected_dat:
        raise ArtifactError("scenario DAT path differs")
    runs = scenario["runs"]
    if not isinstance(runs, list) or len(runs) != endpoint["runs"]:
        raise ArtifactError("run count differs")
    expected_instances = [instance for instance in range(10) for _seed in range(5)]
    for index, (run, expected_instance) in enumerate(zip(runs, expected_instances)):
        if not isinstance(run, dict):
            raise ArtifactError(f"run {index} must be an object")
        _exact_keys(run, {"instance", "evals", "best"}, name=f"run {index}")
        if run["instance"] != expected_instance:
            raise ArtifactError(f"run {index} instance order differs")
        evaluations = _integer(run["evals"], name=f"run {index} evals", minimum=1)
        if evaluations > endpoint["logged_evaluations"]:
            raise ArtifactError(f"run {index} exceeds the frozen whole-generation ceiling")
        best = run["best"]
        if not isinstance(best, dict):
            raise ArtifactError(f"run {index} best must be an object")
        _exact_keys(best, {"evals", "y", "x"}, name=f"run {index} best")
        best_evaluation = _integer(best["evals"], name=f"run {index} best evals", minimum=1)
        if best_evaluation > evaluations:
            raise ArtifactError(f"run {index} best evaluation exceeds total")
        _decimal(best["y"], name=f"run {index} best y", minimum=Decimal(0))
        x = best["x"]
        if not isinstance(x, list) or len(x) != endpoint["dimension"]:
            raise ArtifactError(f"run {index} best x dimension differs")
        for axis, coordinate in enumerate(x):
            _decimal(coordinate, name=f"run {index} x[{axis}]")

    selected = runs[endpoint["run_index"]]
    best = selected["best"]
    selected_y = format(best["y"], "e")
    frozen_literal = f'"y": {endpoint["best_y_decimal"]}'.encode("ascii")
    if payload.count(frozen_literal) != 1:
        raise ArtifactError("frozen endpoint decimal literal is absent or duplicated")
    observed = {
        "instance": selected["instance"],
        "logged_evaluations": selected["evals"],
        "best_evaluation": best["evals"],
        "best_y_decimal": selected_y,
    }
    expected = {
        "instance": endpoint["instance"],
        "logged_evaluations": endpoint["logged_evaluations"],
        "best_evaluation": endpoint["best_evaluation"],
        "best_y_decimal": endpoint["best_y_decimal"],
    }
    if observed != expected:
        raise ArtifactError(f"selected endpoint differs: {observed!r}")
    return EndpointResult(
        run_count=len(runs),
        selected_instance=selected["instance"],
        selected_seed=endpoint["seed"],
        logged_evaluations=selected["evals"],
        best_evaluation=best["evals"],
        best_y_decimal=selected_y,
        ioh_version=value["version"],
        run_evaluations=tuple(run["evals"] for run in runs),
    )


def parse_companion_dat(
    payload: bytes,
    contract: Mapping[str, Any],
    *,
    expected_run_evaluations: Sequence[int] | None = None,
) -> DatSummary:
    """Validate the rounded DAT grammar and document why it is not the target."""

    if not isinstance(payload, bytes) or b"\x00" in payload or b"\r" in payload:
        raise ArtifactError("DAT member must be LF-only bytes without NUL")
    try:
        lines = payload.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as error:
        raise ArtifactError("DAT member is not strict UTF-8") from error
    headers = [index for index, line in enumerate(lines) if line == "evaluations raw_y"]
    if len(headers) != contract["endpoint"]["runs"] or not headers or headers[0] != 0:
        raise ArtifactError("DAT run headers differ")
    row_count = 0
    first_final: tuple[int, str] | None = None
    for run_index, start in enumerate(headers):
        end = headers[run_index + 1] if run_index + 1 < len(headers) else len(lines)
        previous_evaluation = 0
        last: tuple[int, str] | None = None
        for line_number, line in enumerate(lines[start + 1 : end], start=start + 2):
            match = DAT_ROW.fullmatch(line)
            if match is None:
                raise ArtifactError(f"DAT line {line_number} violates exact grammar")
            evaluation = int(match.group("evaluations"))
            raw_y = match.group("raw_y")
            if evaluation <= previous_evaluation:
                raise ArtifactError(f"DAT run {run_index} evaluations are not increasing")
            try:
                value = Decimal(raw_y)
            except InvalidOperation as error:
                raise ArtifactError(f"DAT line {line_number} has invalid decimal") from error
            if not value.is_finite() or value < 0:
                raise ArtifactError(f"DAT line {line_number} raw_y is invalid")
            previous_evaluation = evaluation
            last = (evaluation, raw_y)
            row_count += 1
        if last is None:
            raise ArtifactError(f"DAT run {run_index} has no rows")
        if last[0] > contract["endpoint"]["logged_evaluations"]:
            raise ArtifactError(f"DAT run {run_index} exceeds the evaluation ceiling")
        if expected_run_evaluations is not None:
            if len(expected_run_evaluations) != len(headers):
                raise ArtifactError("JSON/DAT run counts differ")
            if last[0] != expected_run_evaluations[run_index]:
                raise ArtifactError(f"DAT/JSON final evaluation differs for run {run_index}")
        if run_index == 0:
            first_final = last
    if first_final != (50002, "0.0000000000"):
        raise ArtifactError("first DAT run no longer demonstrates rounded zero")
    return DatSummary(
        run_count=len(headers),
        row_count=row_count,
        first_run_final_evaluation=first_final[0],
        first_run_final_raw_y=first_final[1],
    )

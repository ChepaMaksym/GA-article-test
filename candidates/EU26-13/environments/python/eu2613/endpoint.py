"""Strict IOH JSON endpoint validation."""

from __future__ import annotations

import json
import re
from typing import Any

from .contract import exact, require
from .errors import VerificationError


DECIMAL_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")


class DecimalToken(str):
    """A JSON number token retained verbatim rather than a JSON string value."""


def _reject_constant(token: str) -> None:
    raise VerificationError("A6_ENDPOINT", f"non-finite JSON number {token}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError("A6_ENDPOINT", f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def parse_endpoint(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="strict")
        document = json.loads(
            text,
            parse_float=DecimalToken,
            parse_int=int,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError("A6_ENDPOINT", f"invalid UTF-8 JSON: {exc}") from exc
    require(isinstance(document, dict), "A6_ENDPOINT", "JSON root is not an object")
    return document


def _keys(value: Any, expected: list[str], field: str) -> None:
    require(isinstance(value, dict), "A6_ENDPOINT", f"{field} is not an object")
    exact(list(value.keys()), expected, "A6_ENDPOINT", f"{field} key order")


def validate_endpoint(raw: bytes, contract: dict[str, Any]) -> dict[str, Any]:
    endpoint = contract["endpoint"]
    document = parse_endpoint(raw)
    _keys(
        document,
        ["version", "suite", "function_id", "function_name", "maximization", "algorithm", "attributes", "scenarios"],
        "root",
    )
    exact(document["version"], endpoint["json_version"], "A6_ENDPOINT", "version")
    exact(document["suite"], endpoint["suite"], "A6_ENDPOINT", "suite")
    exact(document["function_id"], endpoint["function_id"], "A6_ENDPOINT", "function_id")
    exact(document["function_name"], endpoint["function_name"], "A6_ENDPOINT", "function_name")
    exact(document["maximization"], endpoint["maximization"], "A6_ENDPOINT", "maximization")
    _keys(document["algorithm"], ["name", "info"], "algorithm")
    exact(document["algorithm"]["name"], endpoint["algorithm_name"], "A6_ENDPOINT", "algorithm name")
    exact(document["algorithm"]["info"], "algorithm_info", "A6_ENDPOINT", "algorithm info")
    exact(document["attributes"], ["evaluations", "raw_y"], "A6_ENDPOINT", "attributes")

    scenarios = document["scenarios"]
    require(isinstance(scenarios, list), "A6_ENDPOINT", "scenarios is not a list")
    exact([scenario.get("dimension") for scenario in scenarios], endpoint["scenario_dimensions"], "A6_ENDPOINT", "scenario order")
    for scenario_index, scenario in enumerate(scenarios):
        _keys(scenario, ["dimension", "path", "runs"], "scenario")
        require(type(scenario["dimension"]) is int and scenario["dimension"] > 0, "A6_ENDPOINT", "invalid dimension")
        require(isinstance(scenario["path"], str) and scenario["path"], "A6_ENDPOINT", "invalid scenario path")
        require(isinstance(scenario["runs"], list), "A6_ENDPOINT", "scenario runs is not a list")
        exact(len(scenario["runs"]), endpoint["runs"], "A6_ENDPOINT", "scenario run count")
        for index, run in enumerate(scenario["runs"]):
            label = f"scenario {scenario_index} run {index}"
            _keys(run, ["instance", "evals", "best"], label)
            expected_instance = index // endpoint["runs_per_instance"] + 1
            exact(run["instance"], expected_instance, "A6_ENDPOINT", f"{label} instance")
            require(type(run["evals"]) is int and run["evals"] > 0, "A6_ENDPOINT", f"{label} evals")
            _keys(run["best"], ["evals", "y", "x"], f"{label} best")
            best = run["best"]
            require(type(best["evals"]) is int and 0 < best["evals"] <= run["evals"], "A6_ENDPOINT", f"{label} best evals")
            require(type(best["y"]) is DecimalToken and DECIMAL_RE.fullmatch(best["y"]) is not None, "A6_ENDPOINT", f"{label} best y token")
            require(isinstance(best["x"], list) and len(best["x"]) == scenario["dimension"], "A6_ENDPOINT", f"{label} best x")
            require(all(type(value) is DecimalToken and DECIMAL_RE.fullmatch(value) for value in best["x"]), "A6_ENDPOINT", f"{label} x numeric tokens")

    selected = scenarios[endpoint["scenario_index"]]
    exact(selected["dimension"], endpoint["dimension"], "A6_ENDPOINT", "selected dimension")
    exact(selected["path"], endpoint["scenario_path"], "A6_ENDPOINT", "selected path")

    run = selected["runs"][endpoint["run_index"]]
    exact(run["instance"], endpoint["instance"], "A6_ENDPOINT", "target instance")
    exact(run["evals"], endpoint["evals"], "A6_ENDPOINT", "target evaluations")
    exact(run["best"]["evals"], endpoint["best_evals"], "A6_ENDPOINT", "target best evaluations")
    exact(str(run["best"]["y"]), endpoint["best_y_decimal"], "A6_ENDPOINT", "target decimal token")
    exact(len(run["best"]["x"]), endpoint["best_x_length"], "A6_ENDPOINT", "target vector length")
    inferred_seed = 42 * (endpoint["run_index"] % endpoint["runs_per_instance"])
    exact(inferred_seed, endpoint["seed"], "A6_ENDPOINT", "inferred driver seed")
    return {
        "status": "PASS_ARTIFACT_ENDPOINT",
        "json_pointer": endpoint["json_pointer"],
        "dimension": selected["dimension"],
        "scenario_count": len(scenarios),
        "runs": len(selected["runs"]),
        "instance": run["instance"],
        "run_index": endpoint["run_index"],
        "inferred_seed": inferred_seed,
        "evals": run["evals"],
        "best_evals": run["best"]["evals"],
        "best_y_decimal": str(run["best"]["y"]),
        "best_x_length": len(run["best"]["x"]),
    }

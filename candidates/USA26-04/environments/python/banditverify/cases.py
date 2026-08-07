"""Frozen deterministic formula cases used by the portability profiles."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .controller import run_fixed_controller_tape
from .objectives import evaluate_objective
from .rewards import evaluate_reward


EXPECTED_CASE_IDS = {
    "ackley-mixed",
    "griewank-mixed",
    "rastrigin-mixed",
    "rosenbrock-mixed",
    "sphere-mixed",
    "linear-mixed",
    "reward-signs",
    "controller-fixed-tape",
}


def load_matrix(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        raw = list(csv.DictReader(handle))
    if len(raw) != len(EXPECTED_CASE_IDS):
        raise ValueError("hardware formula matrix must contain exactly eight cases")
    if {row.get("case_id") for row in raw} != EXPECTED_CASE_IDS:
        raise ValueError("hardware formula matrix case IDs changed")
    cases: list[dict[str, Any]] = []
    for row in raw:
        try:
            iterations = int(row["iterations"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("every formula case needs an integer iteration count") from exc
        if iterations != 20000:
            raise ValueError("the frozen formula workload requires 20000 iterations per case")
        cases.append(
            {
                "case_id": row["case_id"],
                "operation": row["operation"],
                "fixture": row["fixture"],
                "iterations": iterations,
            }
        )
    return sorted(cases, key=lambda item: item["case_id"])


def _close(actual: float, expected: float, atol: float, rtol: float) -> bool:
    return math.isclose(actual, expected, abs_tol=atol, rel_tol=rtol)


def _controller_projection(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "verification_scope": result["verification_scope"],
        "paper_level_status": result["paper_level_status"],
        "published_result_status": result["published_result_status"],
        "state_provenance": result["state_provenance"],
        "base_weights": result["base_weights"],
        "branch": result["branch"],
        "argmax_tile": result["argmax_tile"],
        "selected_tile": result["selected_tile"],
        "log_rate": result["log_rate"],
        "rate": result["rate"],
        "immediate_reward": result["immediate_reward"],
        "updates": result["updates"],
    }


def execute_case(case: dict[str, Any], candidate: Path) -> dict[str, Any]:
    oracles = json.loads(
        (candidate / "fixtures" / "formula_oracles.json").read_text(encoding="utf-8")
    )
    atol = float(oracles["tolerance"]["absolute"])
    rtol = float(oracles["tolerance"]["relative"])
    operation = case["operation"]
    iterations = case["iterations"]

    if operation.startswith("objective:"):
        name = operation.split(":", 1)[1]
        anchor = oracles["objective_anchors"][case["fixture"]]
        actual = None
        for _ in range(iterations):
            actual = evaluate_objective(name, anchor["vector"])
        assert actual is not None
        expected = float(anchor["expected"][name])
        passed = _close(actual, expected, atol, rtol)
        result: dict[str, Any] = {
            "objective": name,
            "actual": actual,
            "expected": expected,
            "absolute_error": abs(actual - expected),
        }
    elif operation == "rewards":
        fixture = oracles["reward_sign"]
        actual_rewards: dict[str, float] = {}
        for _ in range(iterations):
            actual_rewards = {
                semantics: evaluate_reward(
                    semantics, fixture["parent"], fixture["child"]
                )
                for semantics in ("P1", "P2", "P3")
            }
        passed = all(
            _close(actual_rewards[key], fixture["expected"][key], atol, rtol)
            for key in ("P1", "P2", "P3")
        ) and actual_rewards["P2"] > 0 > actual_rewards["P3"]
        result = {
            "actual": actual_rewards,
            "expected": fixture["expected"],
            "sign_conflict_confirmed": actual_rewards["P2"] > 0 > actual_rewards["P3"],
            "semantics_resolved": False,
        }
    elif operation == "controller":
        fixture = json.loads(
            (candidate / "fixtures" / "fixed_controller_tape.json").read_text(
                encoding="utf-8"
            )
        )
        actual_controller: dict[str, Any] | None = None
        for _ in range(iterations):
            actual_controller = run_fixed_controller_tape(fixture)
        assert actual_controller is not None
        projection = _controller_projection(actual_controller)
        expected = fixture["expected"]
        numeric_pass = all(
            _close(projection[key], expected[key], atol, rtol)
            for key in ("log_rate", "rate", "immediate_reward")
        ) and all(
            _close(left, right, atol, rtol)
            for left, right in zip(projection["base_weights"], expected["base_weights"])
        )
        update_pass = len(projection["updates"]) == len(expected["updates"])
        for actual_update, expected_update in zip(projection["updates"], expected["updates"]):
            update_pass = update_pass and all(
                _close(actual_update[key], expected_update[key], atol, rtol)
                for key in ("max_reward", "gradient", "momentum", "value")
            )
            update_pass = update_pass and actual_update["paper_index"] == expected_update["paper_index"]
        passed = (
            numeric_pass
            and update_pass
            and projection["branch"] == expected["branch"]
            and projection["selected_tile"] == expected["selected_tile"]
            and projection["argmax_tile"] == expected["argmax_tile"]
            and projection["state_provenance"] == "synthetic_fixture_not_article_state"
            and projection["paper_level_status"] == "BLOCKED_G5_G9"
            and projection["published_result_status"] == "INCONCLUSIVE_PUBLISHED_RESULT"
        )
        result = projection
    else:
        raise ValueError(f"unknown frozen operation: {operation!r}")

    return {
        "case_id": case["case_id"],
        "operation": operation,
        "fixture": case["fixture"],
        "iterations": iterations,
        "status": "PASS_FORMULA_CASE" if passed else "FAIL_FORMULA_CASE",
        "result": result,
        "paper_level_status": "BLOCKED_G5_G9",
        "published_result_status": "INCONCLUSIVE_PUBLISHED_RESULT",
    }


def controller_projection(result: dict[str, Any]) -> dict[str, Any]:
    """Public projection helper used by strict cross-language comparison."""

    return _controller_projection(result)

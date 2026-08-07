"""Fail-closed validation of the frozen protocol and absence declarations."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


CANDIDATE = Path(__file__).resolve().parents[3]

EXPECTED_SOURCE_HASHES = {
    "NSF_FULL_TEXT": (3765486, "808fa86ff865d7228959c39d6793c8d4e18d965ea37269d340371f9ff8a1effb"),
    "ARXIV_PDF": (3554426, "74f07de64535fdf3e3a058a196ee95ec30c8dd8b6d94e39eaa8e0fb7d4002543"),
    "ARXIV_SOURCE": (4741270, "d64694271e3f57a409ad7be419db835cb1dc90d572392dd64a15d871cc8db017"),
    "ARXIV_MAIN_TEX": (66195, "1fb58c7a7c6a080e27ffb23f0c78d4baacee761b071fe74398c90458516dc638"),
    "AUTHOR_FORK_LICENSE": (14199, "721c2da257578bace3332b14d8ea06643d7d26753e7ef25a837b4e904edc0bf5"),
}
EXPECTED_BANDIT_TEXT = {
    "Ackley": "10.1",
    "Griewank": "4.69e-3",
    "Rastrigin": "3686",
    "Rosenbrock": "105",
    "Sphere": "5.56e-8",
    "Linear": "-2.91e46",
}
REQUIRED_ABSENCES = {
    "paper_specific_controller_code",
    "paper_pinned_code_revision",
    "continuous_mutation_transition",
    "controller_initial_values",
    "controller_initial_momenta",
    "controller_initial_histories",
    "empty_or_partial_history_rule",
    "argmax_tie_break",
    "upper_boundary_rule",
    "rng_family",
    "rng_stream_partition",
    "seed_ledger",
    "raw_per_run_results",
    "numeric_confidence_intervals",
    "environment_lock",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_protocol(candidate: Path = CANDIDATE) -> dict[str, Any]:
    protocol = _load_json(candidate / "config" / "protocol.json")
    required_top = {
        "candidate_id": "USA26-04",
        "protocol_id": "USA26-04-FORMULA-PORTABILITY-v1",
        "scope": "FORMULA_AND_AMBIGUITY_VALIDATION_ONLY",
        "overall_status": "BLOCKED_G5_G9",
        "published_result_status": "INCONCLUSIVE_PUBLISHED_RESULT",
        "registry_status": "conditional_noneligible",
        "pass_full_forbidden": True,
        "table1_execution_forbidden": True,
        "full_ga_forbidden": True,
    }
    for key, expected in required_top.items():
        if protocol.get(key) != expected:
            raise AssertionError(f"protocol.{key} must remain {expected!r}")

    primary = protocol.get("primary_descriptive_cell", {})
    expected_primary = {
        "method": "Bandit",
        "function": "rastrigin",
        "dimension": 100,
        "initial_sd": 10.0,
        "non_elite_population": 100,
        "elite_population": 1,
        "truncation_size": 10,
        "generations": 1000,
        "reported_runs": 50,
        "reported_mean_text": "3686",
        "executable_target": False,
    }
    for key, expected in expected_primary.items():
        if primary.get(key) != expected:
            raise AssertionError(f"primary_descriptive_cell.{key} changed")
    if primary.get("rounding_interval_descriptive_only") != [3685.5, 3686.5]:
        raise AssertionError("the descriptive rounding interval changed")

    if protocol.get("reward_semantics") != {
        "P1": "mean(parent_error - child_error)",
        "P2": "mean(log1p(parent_error) - log1p(child_error))",
        "P3": "mean(log1p(child_error) - log1p(parent_error))",
    }:
        raise AssertionError("P1/P2/P3 semantics changed")
    absences = protocol.get("required_absences")
    if not isinstance(absences, dict) or set(absences) != REQUIRED_ABSENCES:
        raise AssertionError("required absence manifest keys changed")
    if any(value is not False for value in absences.values()):
        raise AssertionError("an absent source fact was silently promoted")

    with (candidate / "source_manifest" / "sources.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        sources = {row["source_id"]: row for row in csv.DictReader(handle)}
    for source_id, (expected_bytes, expected_hash) in EXPECTED_SOURCE_HASHES.items():
        row = sources.get(source_id)
        if row is None:
            raise AssertionError(f"missing source row {source_id}")
        if int(row["bytes"]) != expected_bytes or row["sha256"] != expected_hash:
            raise AssertionError(f"source identity changed for {source_id}")

    with (candidate / "fixtures" / "published_table1_descriptive.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        table = list(csv.DictReader(handle))
    if len(table) != 6 or {row["problem"] for row in table} != set(EXPECTED_BANDIT_TEXT):
        raise AssertionError("Table 1 descriptive rows changed")
    for row in table:
        if row["bandit_text"] != EXPECTED_BANDIT_TEXT[row["problem"]]:
            raise AssertionError(f"Table 1 text changed for {row['problem']}")
        if row["executable_target"].lower() != "false":
            raise AssertionError("a descriptive Table 1 value became executable")
    primary_rows = [row for row in table if row["role"] == "primary_descriptive_only"]
    if len(primary_rows) != 1 or primary_rows[0]["problem"] != "Rastrigin":
        raise AssertionError("the primary descriptive cell changed")

    return {
        "protocol_id": protocol["protocol_id"],
        "scope": protocol["scope"],
        "paper_level_status": protocol["overall_status"],
        "published_result_status": protocol["published_result_status"],
        "registry_status": protocol["registry_status"],
        "source_identity_count": len(EXPECTED_SOURCE_HASHES),
        "absence_count": len(REQUIRED_ABSENCES),
        "descriptive_target_count": len(table),
        "executable_target_count": 0,
    }

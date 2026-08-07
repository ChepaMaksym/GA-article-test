#!/usr/bin/env python3
"""Fail-closed validator for the 2026 direct adaptive-GA cohort."""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
COHORT = Path(__file__).resolve().parent
REGISTRY_PATH = COHORT / "registry.json"
ASSESSMENTS_PATH = COHORT / "hard_gate_assessments.json"
DEFINITIONS_PATH = COHORT / "gate_definitions.json"
RANKING_PATH = COHORT / "ranking.csv"
# Frozen identities keep cohort de-duplication independent of later edits to the
# historical registry while preserving its exact committed provenance.
OLD_REGISTRY_PATH = COHORT / "prior_cohort_identities.json"

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
VALID_STATUSES = {"hard_pass", "conditional_noneligible", "hard_fail"}
VALID_GATE_STATUSES = {"pass", "unresolved", "fail"}
REQUIRED_GATES = tuple(f"g{i}" for i in range(3, 11))
CANONICAL_GATE_SCHEMA = {
    "g3": (
        "runtime_ga_control_change",
        ("target_kinds", "within_run_change", "publication_configuration", "change_witness"),
    ),
    "g4": ("not_surrogate_only", ("adapted_component", "ga_control_link")),
    "g5": (
        "complete_adaptation_semantics",
        (
            "rule_or_algorithm",
            "initial_value",
            "minimum",
            "maximum",
            "update_frequency",
            "update_order",
            "trigger_or_feedback",
            "boundary_behavior",
        ),
    ),
    "g6": (
        "complete_ga_pipeline",
        (
            "objective",
            "representation",
            "constraints",
            "initialization",
            "selection",
            "crossover",
            "mutation",
            "replacement_or_elitism",
            "termination",
        ),
    ),
    "g7": (
        "lawful_reproducible_inputs",
        ("input_mode", "required_closed_dependency", "input_or_generator_evidence"),
    ),
    "g8": (
        "literal_numeric_published_target",
        ("numeric_targets", "protocol_mapping", "precision_or_rounding"),
    ),
    "g9": (
        "stochastic_protocol_and_provenance",
        (
            "run_count",
            "seed_or_rng_protocol",
            "independence_unit",
            "budget_or_stopping",
            "aggregation_or_analysis",
            "provenance",
        ),
    ),
    "g10": (
        "cross_environment_feasibility",
        (
            "matlab_clean_room_feasible",
            "source_native_artifact_claimed",
            "source_native_replay_possible",
            "environment_evidence",
        ),
    ),
}
VALID_TARGET_KINDS = {
    "mutation_rate",
    "mutation_operator",
    "crossover_rate",
    "crossover_operator",
    "selection_probability",
    "selection_operator",
    "tournament_size",
    "elitism",
    "replacement",
    "operator_selection_probability",
}


class ValidationError(AssertionError):
    """Raised when a preregistered registry invariant is violated."""


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalize_doi(value: str) -> str:
    match = DOI_RE.search(value)
    if not match:
        raise ValidationError(f"No DOI found in {value!r}")
    return match.group(0).rstrip(".,;)]}").lower()


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)


def contains_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, dict):
        return any(contains_number(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_number(child) for child in value)
    return False


def require_nonempty_strings(record: dict[str, Any], keys: Iterable[str], context: str) -> None:
    for key in keys:
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{context}.{key} must be a non-empty string")


def validate_gate(candidate_id: str, gate_id: str, gate: dict[str, Any], required: list[str]) -> None:
    context = f"{candidate_id}.{gate_id}"
    if gate.get("status") not in VALID_GATE_STATUSES:
        raise ValidationError(f"{context}.status is invalid")
    require_nonempty_strings(gate, ["evidence"], context)
    missing = [key for key in required if key not in gate]
    if missing:
        raise ValidationError(f"{context} is missing fields: {', '.join(missing)}")

    if gate_id == "g3" and gate["status"] == "pass":
        kinds = gate["target_kinds"]
        if not isinstance(kinds, list) or not kinds or not set(kinds) <= VALID_TARGET_KINDS:
            raise ValidationError(f"{context} has no valid GA-control target")
        if gate["within_run_change"] != "confirmed":
            raise ValidationError(f"{context} pass requires a confirmed within-run change")

    if gate_id == "g4" and gate["status"] == "pass":
        if gate["adapted_component"] not in {"ga_control", "ga_and_auxiliary"}:
            raise ValidationError(f"{context} pass cannot be surrogate/fitness/forward-only")

    if gate_id == "g5" and gate["status"] == "pass":
        require_nonempty_strings(gate, required, context)
        forbidden = ("missing", "unresolved", "unknown", "contradict")
        for key in required:
            if any(token in gate[key].lower() for token in forbidden):
                raise ValidationError(f"{context}.{key} is not complete enough for pass")

    if gate_id == "g6" and gate["status"] == "pass":
        require_nonempty_strings(gate, required, context)
        forbidden = ("missing", "unresolved", "unknown", "incomplete", "ambiguous")
        for key in required:
            if any(token in gate[key].lower() for token in forbidden):
                raise ValidationError(f"{context}.{key} is not executable enough for pass")

    if gate_id == "g7" and gate["status"] == "pass":
        if gate["input_mode"] not in {"lawful_complete", "synthetic_fully_defined"}:
            raise ValidationError(f"{context} pass requires lawful complete inputs or a full generator")
        if gate["required_closed_dependency"] is not False:
            raise ValidationError(f"{context} pass forbids a required closed dependency")

    if gate_id == "g8" and gate["status"] == "pass":
        targets = gate["numeric_targets"]
        if not isinstance(targets, list) or not targets or not contains_number(targets):
            raise ValidationError(f"{context} pass requires a literal numeric target")
        if gate["protocol_mapping"] != "exact":
            raise ValidationError(f"{context} pass requires exact protocol mapping")
        require_nonempty_strings(gate, ["precision_or_rounding"], context)

    if gate_id == "g9" and gate["status"] == "pass":
        if not isinstance(gate["run_count"], int) or gate["run_count"] < 1:
            raise ValidationError(f"{context} pass requires a positive run count")
        require_nonempty_strings(
            gate,
            ["seed_or_rng_protocol", "independence_unit", "budget_or_stopping", "aggregation_or_analysis", "provenance"],
            context,
        )
        if any(token in gate["seed_or_rng_protocol"].lower() for token in ("missing", "conflict", "unknown")):
            raise ValidationError(f"{context} pass requires a reproducible seed/RNG protocol")

    if gate_id == "g10" and gate["status"] == "pass":
        if gate["matlab_clean_room_feasible"] is not True:
            raise ValidationError(f"{context} pass requires MATLAB clean-room feasibility")
        claimed = gate["source_native_artifact_claimed"]
        possible = gate["source_native_replay_possible"]
        if not isinstance(claimed, bool):
            raise ValidationError(f"{context}.source_native_artifact_claimed must be boolean")
        if claimed and possible is not True:
            raise ValidationError(f"{context} pass requires source-native replay for claimed code")


def validate_paths(
    registry_path: Path = REGISTRY_PATH,
    assessments_path: Path = ASSESSMENTS_PATH,
    definitions_path: Path = DEFINITIONS_PATH,
    ranking_path: Path = RANKING_PATH,
    old_registry_path: Path = OLD_REGISTRY_PATH,
) -> dict[str, Any]:
    registry = load_json(registry_path)
    assessments = load_json(assessments_path)
    definitions = load_json(definitions_path)
    old_registry = load_json(old_registry_path)

    if not isinstance(registry, list) or len(registry) != 12:
        raise ValidationError("The cohort must contain exactly 12 registry records")
    if not isinstance(assessments, list) or len(assessments) != 12:
        raise ValidationError("The cohort must contain exactly 12 hard-gate assessments")

    regions = Counter(record.get("region") for record in registry)
    if regions != Counter({"USA": 6, "EU": 6}):
        raise ValidationError(f"Region quota must be 6 USA + 6 EU, got {dict(regions)}")

    ids = [record.get("candidate_id") for record in registry]
    titles = [record.get("title") for record in registry]
    dois = [normalize_doi(record.get("doi", "")) for record in registry]
    for label, values in (("candidate ID", ids), ("title", titles), ("DOI", dois)):
        if len(set(values)) != len(values):
            raise ValidationError(f"Duplicate {label} in cohort")

    old_dois: set[str] = set()
    for text in iter_strings(old_registry):
        match = DOI_RE.search(text)
        if match:
            old_dois.add(match.group(0).rstrip(".,;)]}").lower())
    overlap = sorted(set(dois) & old_dois)
    if overlap:
        raise ValidationError(f"New cohort overlaps the old registry: {overlap}")

    assessment_by_id = {item.get("candidate_id"): item for item in assessments}
    if set(assessment_by_id) != set(ids) or len(assessment_by_id) != 12:
        raise ValidationError("Registry and hard-gate assessment candidate IDs must match exactly")

    hard_gate_definitions = definitions.get("adaptive_hard_gates")
    if not isinstance(hard_gate_definitions, dict):
        raise ValidationError("Gate definitions must contain adaptive_hard_gates")
    required_by_gate = {
        gate_id: gate_def.get("required_fields")
        for gate_id, gate_def in hard_gate_definitions.items()
    }
    if tuple(sorted(required_by_gate, key=lambda value: int(value[1:]))) != REQUIRED_GATES:
        raise ValidationError("Gate definitions must contain exactly g3 through g10")
    for gate_id, (canonical_name, canonical_fields) in CANONICAL_GATE_SCHEMA.items():
        gate_definition = hard_gate_definitions[gate_id]
        if gate_definition.get("name") != canonical_name:
            raise ValidationError(f"{gate_id} semantic name must be {canonical_name!r}")
        required_fields = gate_definition.get("required_fields")
        if not isinstance(required_fields, list) or tuple(required_fields) != canonical_fields:
            raise ValidationError(f"{gate_id} required fields do not match the frozen criterion")

    hard_pass_ids: list[str] = []
    status_counts: Counter[str] = Counter()
    for record in registry:
        candidate_id = record["candidate_id"]
        status = record.get("eligibility_status")
        if status not in VALID_STATUSES:
            raise ValidationError(f"{candidate_id} has invalid eligibility_status")
        status_counts[status] += 1

        if record.get("direct_not_inverse") is not True:
            raise ValidationError(f"{candidate_id} violates the direct-only scope")
        if record.get("claimed_adaptation_within_run") is not True:
            raise ValidationError(f"{candidate_id} is not even claimed to adapt a GA control within-run")
        dimension = record.get("selected_decision_dimension")
        if not isinstance(dimension, int) or dimension < 11:
            raise ValidationError(f"{candidate_id} selected dimension must be an integer >=11")
        require_nonempty_strings(record, ["title", "doi", "full_text_url", "adaptive_locus", "critical_blocker"], candidate_id)
        if not record["full_text_url"].startswith("https://"):
            raise ValidationError(f"{candidate_id}.full_text_url must be HTTPS")

        assessment = assessment_by_id[candidate_id]
        for preliminary in ("scope_direct_only", "c1_full_text", "c2_dimension"):
            gate = assessment.get(preliminary, {})
            if gate.get("status") not in VALID_GATE_STATUSES:
                raise ValidationError(f"{candidate_id}.{preliminary}.status is invalid")
            require_nonempty_strings(gate, ["evidence"], f"{candidate_id}.{preliminary}")
        if assessment["scope_direct_only"]["status"] != "pass":
            raise ValidationError(f"{candidate_id} cannot occupy the direct-only quota")
        if assessment["c2_dimension"].get("selected_dimension") != dimension:
            raise ValidationError(f"{candidate_id} dimension differs between registry and assessment")

        for gate_id in REQUIRED_GATES:
            gate = assessment.get(gate_id)
            if not isinstance(gate, dict):
                raise ValidationError(f"{candidate_id} is missing {gate_id}")
            validate_gate(candidate_id, gate_id, gate, required_by_gate[gate_id])

        gate_statuses = [assessment[key]["status"] for key in ("scope_direct_only", "c1_full_text", "c2_dimension", *REQUIRED_GATES)]
        all_pass = all(value == "pass" for value in gate_statuses)
        any_fail = any(value == "fail" for value in gate_statuses)
        decisive = assessment.get("decisive_exclusion")
        if not isinstance(decisive, bool):
            raise ValidationError(f"{candidate_id}.decisive_exclusion must be boolean")
        if decisive != any_fail:
            raise ValidationError(f"{candidate_id} decisive_exclusion must match presence of a failed gate")

        expected_status = "hard_pass" if all_pass else ("hard_fail" if decisive else "conditional_noneligible")
        if status != expected_status:
            raise ValidationError(f"{candidate_id} status {status!r} must be {expected_status!r}")

        score = record.get("final_score")
        if status == "hard_pass":
            hard_pass_ids.append(candidate_id)
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
                raise ValidationError(f"{candidate_id} hard_pass requires score in [0,100]")
        elif score is not None:
            raise ValidationError(f"{candidate_id} noneligible record must have null final_score")

    with ranking_path.open(newline="", encoding="utf-8") as handle:
        ranking_rows = list(csv.DictReader(handle))
    ranking_ids = [row.get("candidate_id") for row in ranking_rows]
    if set(ranking_ids) != set(hard_pass_ids) or len(ranking_ids) != len(hard_pass_ids):
        raise ValidationError("ranking.csv must contain exactly the hard_pass candidates")
    if len(set(ranking_ids)) != len(ranking_ids):
        raise ValidationError("ranking.csv contains duplicate candidates")

    return {
        "records": len(registry),
        "regions": dict(regions),
        "statuses": dict(status_counts),
        "hard_pass_ids": hard_pass_ids,
        "ranking_rows": len(ranking_rows),
    }


def main() -> int:
    try:
        summary = validate_paths()
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"REGISTRY VALIDATION FAIL: {exc}", file=sys.stderr)
        return 1
    print("REGISTRY VALIDATION PASS")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed validator for the prospective EU26-21 common bridge."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


EXPECTED_TRAIN_SHA256 = (
    "3676a81db7d3528f3f8b9f3c699d0f0aa28db45e6e994fa0b8ed38327539ee86"
)
EXPECTED_TEST_SHA256 = (
    "98402b1ab879573d0a7f38a699a40258080e25e33d3401e7bf9c96d3fa0fab8c"
)
EXPECTED_ARCHIVE_SHA256 = (
    "54fd206becffcfaf099544c3938c681d64a65709800c94c00a4fba0a00df10c9"
)
PROTOCOL_CONTENT_FREEZE_COMMIT_SHA = (
    "939914a33d21709526ef12538170ce806b45e3a3"
)
EXPECTED_PROTOCOL_SHA256 = (
    "730cd436db59d23da7dab5e24c49bc7b28d65379136fad7fd2d2370e0a436205"
)
EXPECTED_DOCUMENT_SHA256 = (
    "7bcfe905612274cadb4cf398c21c5417d1c8493ee0ae2c6c242a515f543708c9"
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(protocol_path: Path, document_path: Path) -> dict[str, Any]:
    protocol_sha256 = _sha256(protocol_path)
    document_sha256 = _sha256(document_path)
    _require(
        protocol_sha256 == EXPECTED_PROTOCOL_SHA256,
        "protocol bytes differ from the frozen pre-implementation manifest",
    )
    _require(
        document_sha256 == EXPECTED_DOCUMENT_SHA256,
        "protocol document bytes differ from the frozen pre-implementation text",
    )
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    document = document_path.read_text(encoding="utf-8")

    _require(
        protocol.get("schema") == "eu26-21-common-wba-bridge-protocol-v1",
        "unexpected protocol schema",
    )
    _require(protocol.get("study_id") == "EU26-21-CWB-01", "wrong study ID")
    _require(
        protocol.get("protocol_id") == "EU26-21-COMMON-WBA-BSF-AUC-400-V1",
        "wrong protocol ID",
    )
    _require(
        protocol.get("evidence_class")
        == "prospective_confirmatory_followup_informed_by_retrospective_results",
        "wrong evidence class",
    )
    _require(
        protocol.get("protocol_status")
        == "FROZEN_BEFORE_ANY_41001_41030_OUTCOME",
        "protocol is not prospectively frozen",
    )
    freeze = protocol["freeze"]
    _require(freeze["date_utc"] == "2026-08-23", "freeze date changed")
    _require(
        freeze["implementation_present_at_freeze"] is False,
        "implementation was present at freeze",
    )
    _require(
        freeze["prospective_seed_outcomes_inspected_at_freeze"] is False,
        "prospective outcomes were inspected before freeze",
    )

    boundary = protocol["source_boundary"]
    _require(
        boundary["printed_algorithm_1_equivalence"] is False,
        "paper/source boundary lost",
    )
    _require(
        boundary["full_printed_chc_qx_profile"] is False,
        "bridge mislabeled as full CHC-QX",
    )
    _require(
        boundary["upstream_commit"]
        == "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6",
        "upstream commit changed",
    )
    _require(
        boundary["comparator_id"]
        == "harmonized_pinned_source_chc_feature_mask_search",
        "comparator changed",
    )

    data = protocol["data_protocol"]
    _require(
        data["archive_sha256"] == EXPECTED_ARCHIVE_SHA256,
        "archive hash changed",
    )
    _require(data["train_sha256"] == EXPECTED_TRAIN_SHA256, "train hash changed")
    _require(data["test_sha256"] == EXPECTED_TEST_SHA256, "test hash changed")
    _require(data["train_rows"] == 199523, "train row count changed")
    _require(data["test_rows"] == 99762, "test row count changed")
    _require(data["raw_column_count"] == 42, "raw column count changed")
    _require(data["target_raw_index"] == 41, "target index changed")
    _require(data["instance_weight_raw_index"] == 24, "weight index changed")
    _require(data["predictive_dimension"] == 40, "predictive dimension changed")
    _require(
        data["instance_weight_as_predictor"] is False,
        "weight leaked into predictors",
    )
    _require(
        data["instance_weight_as_sample_weight"] is True,
        "weights not used",
    )
    _require(data["validation_fraction"] == 0.2, "validation split changed")
    _require(data["active_sample_size"] == 14964, "active sample changed")

    pairing = protocol["pairing_and_rng"]
    _require(
        pairing["seed_ledger"] == list(range(41001, 41031)),
        "seed ledger changed",
    )
    _require(pairing["run_count"] == 30, "run count changed")
    _require(
        pairing["arm_rng_isolation"] is True,
        "arm RNG streams are not isolated",
    )
    _require(
        pairing["arm_rng_streams"]
        == {
            "chc_harmonized": "python_random_seeded_with_search_seed",
            "lambda_no_reset": "numpy_default_rng_seeded_with_search_seed",
        },
        "arm RNG stream definitions changed",
    )
    _require(
        pairing["split_seed_formula"] == "2026081700 + seed",
        "split seed formula changed",
    )
    _require(
        pairing["active_sample_seed_formula"] == "2026081800 + seed",
        "active sample seed formula changed",
    )
    _require(
        pairing["search_seed_formula"] == "seed + 1000003",
        "search seed formula changed",
    )
    _require(
        pairing["initial_mask_seed_formula"] == "seed + 1000102",
        "initial-mask seed formula changed",
    )
    _require(
        pairing["initial_mask_generator"] == "source_density_population",
        "initial mask generator changed",
    )

    objective = protocol["objective"]
    _require(
        objective["fitness"]
        == [
            "validation_weighted_balanced_accuracy",
            "negative_selected_feature_fraction",
        ],
        "objective changed",
    )
    _require(objective["comparison"] == "lexicographic", "tie-break changed")
    _require(
        objective["terminal_exact_tie_rule"] == "earliest_objective_call",
        "terminal exact-tie rule changed",
    )
    _require(
        objective["test_data_used_during_search"] is False,
        "test leakage allowed",
    )

    budget = protocol["budget"]
    _require(
        budget["call_unit"] == "logical_objective_invocation",
        "objective-call unit changed",
    )
    _require(budget["objective_calls_per_arm_per_seed"] == 400, "budget changed")
    _require(budget["initial_population_calls"] == 50, "initial population changed")
    _require(budget["early_stopping"] is False, "early stopping enabled")
    _require(budget["objective_cache"] is False, "objective cache enabled")
    _require(budget["duplicates_consume_calls"] is True, "duplicate policy changed")
    _require(
        budget["endpoint"]
        == "lexicographic_best_among_first_400_queried_masks",
        "endpoint changed",
    )
    _require(
        budget["chc_terminal_rule"]
        == (
            "evaluate_generated_fresh_offspring_prefix_through_call_400_then_"
            "skip_partial_generation_population_update"
        ),
        "CHC terminal rule changed",
    )
    _require(
        budget["lambda_terminal_rule"]
        == "paired_mutant_crossover_tail_truncated_to_remaining_even_budget",
        "lambda terminal rule changed",
    )

    lambda_arm = protocol["arms"]["lambda_no_reset"]
    chc_arm = protocol["arms"]["chc_harmonized"]
    _require(chc_arm["fitness_arity"] == 2, "CHC fitness lost sparsity tie-break")
    _require(
        chc_arm["selection_tie_break"] == "lexicographic_sparsity",
        "CHC tie-break changed",
    )
    _require(
        chc_arm["population_exact_tie_rule"]
        == "stable_first_in_parent_plus_offspring_order",
        "CHC exact-tie rule changed",
    )
    _require(
        chc_arm["offspring_evaluation_order"]
        == "generated_fresh_offspring_list_order",
        "CHC evaluation order changed",
    )
    _require(
        chc_arm["partial_final_generation_population_update"] is False,
        "partial CHC generation update enabled",
    )
    _require(lambda_arm["reset"] is False, "reset enabled")
    _require(lambda_arm["required_reset_events"] == 0, "reset count changed")
    _require(lambda_arm["update_factor"] == 1.5, "update factor changed")
    _require(lambda_arm["lambda_initial"] == 1.0, "initial lambda changed")
    _require(lambda_arm["lambda_min"] == 1.0, "minimum lambda changed")
    _require(lambda_arm["lambda_max"] == 40.0, "maximum lambda changed")
    _require(lambda_arm["workers"] == 1, "worker count changed")
    _require(
        lambda_arm["search_exact_tie_rule"]
        == "uniform_using_arm_local_numpy_rng",
        "lambda search exact-tie rule changed",
    )

    efficiency = protocol["efficiency_estimand"]
    _require(
        efficiency["name"]
        == "normalized_area_under_best_so_far_validation_wba_calls_1_400",
        "efficiency estimand changed",
    )
    _require(
        efficiency["definition"]
        == "mean(max(primary_fitness[1..k]) for k=1..400)",
        "efficiency definition changed",
    )
    _require(efficiency["not_roc_auc"] is True, "efficiency confused with ROC-AUC")
    _require(efficiency["not_wall_clock"] is True, "logical calls mislabeled as time")

    test_policy = protocol["official_test_policy"]
    _require(test_policy["evaluations_per_seed_per_arm"] == 1, "test access count changed")
    _require(test_policy["used_for_model_selection"] is False, "test selection enabled")
    _require(
        test_policy["fit_scope"] == "internal_80_percent_training_partition_only",
        "official-test fit scope changed",
    )

    analysis = protocol["analysis_plan"]
    _require(analysis["analysis_seed"] == 41031, "analysis seed changed")
    _require(analysis["bootstrap_method"] == "paired_median_BCa", "method changed")
    _require(analysis["bootstrap_resamples"] == 50000, "bootstrap count changed")
    _require(analysis["two_sided_interval"] == 0.95, "interval level changed")
    _require(analysis["noninferiority_margin"] == -0.001, "NI margin changed")
    _require(
        analysis["noninferiority_operator"]
        == "lower_95_bca_strictly_greater_than_margin",
        "NI decision operator changed",
    )
    _require(
        analysis["efficiency_operator"]
        == "lower_95_bca_strictly_greater_than_zero",
        "efficiency decision operator changed",
    )
    _require(
        analysis["decision_order"]
        == ["quality_noninferiority", "auc_superiority_if_quality_passes"],
        "decision hierarchy changed",
    )

    required_document_tokens = (
        "not the full printed CHC-QX/Algorithm 1 profile",
        "Reset is disabled",
        "exactly 400",
        "logical objective calls",
        "skips the partial generation's population",
        "earlier objective-call index",
        "It is not ROC-AUC",
        "strictly greater than `-0.001`",
        "PASS_JOINT_BRIDGE_CLAIM",
        "negative or null hypothesis decision is a valid scientific result",
    )
    normalized_document = re.sub(r"\s+", " ", document)
    for token in required_document_tokens:
        normalized_token = re.sub(r"\s+", " ", token)
        _require(
            normalized_token in normalized_document,
            f"protocol document lost required boundary: {token}",
        )

    github_sha = os.environ.get("GITHUB_SHA", "")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        _require(bool(re.fullmatch(r"[0-9a-f]{40}", github_sha)), "invalid CI commit SHA")

    return {
        "schema": "eu26-21-common-wba-bridge-protocol-validation-v1",
        "study_id": protocol["study_id"],
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol_sha256,
        "document_sha256": document_sha256,
        "protocol_content_freeze_commit_sha": PROTOCOL_CONTENT_FREEZE_COMMIT_SHA,
        "validated_commit_sha": github_sha or None,
        "seed_count": len(pairing["seed_ledger"]),
        "pass": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = validate(args.protocol.resolve(), args.document.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

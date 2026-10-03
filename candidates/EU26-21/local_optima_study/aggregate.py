#!/usr/bin/env python3
"""Freeze complete cases, then analyse complete paired escapes in CI.

The bootstrap unit is one prepared case containing all five paired repetitions,
not a repetition, person, or pooled confusion-matrix cell.
"""
from __future__ import annotations

import argparse
import csv
from itertools import combinations
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Mapping, Sequence
import warnings

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from scipy.stats import bootstrap

from local_optima_study.contract import (
    ALL_ARMS, CASE_SCHEMA, CASE_SEEDS, ESCAPE_ARMS, ESCAPE_SCHEMA,
    PROTOCOL_ID, PROTOCOL_SHA256, REGISTRY_SCHEMA, SEARCH_ARMS,
    THIS_DIRECTORY, TRANSFORMED_FEATURE_NAMES, authenticate, canonical_sha256, file_sha256,
    mask_fitness, per_class_metrics, read_json, require,
    verify_manifest, write_json,
)


def validate_search_trace(trace: Mapping[str, Any], *, escape: bool = False) -> None:
    require(trace["objective_calls"] == 400, "search did not use exactly 400 objective calls")
    require(trace["initial_population_calls"] == (0 if escape else 50), "initial call count mismatch")
    require(trace["reset"] is False and trace["reset_events"] == 0, "unexpected reset")
    records = trace["evaluations"]
    require(len(records) == 400 and [row["call"] for row in records] == list(range(1, 401)),
            "missing or duplicate search-call indices")
    known: dict[tuple[int, ...], tuple[float, float]] = {}
    initial = trace.get("initial")
    if escape:
        require(initial is not None and initial["call"] == 0, "missing q0 known parent")
        best_mask, best_score = mask_fitness(initial["mask"], initial["fitness"])
        known[best_mask] = best_score
        best_call, best_primary = 0, best_score[0]
    else:
        best_mask, best_score, best_call, best_primary = None, None, None, None
    trajectory = []
    first_exit = None
    for row in records:
        fitness = row.get("fitness", [row.get("validation_weighted_balanced_accuracy"),
                                     row.get("negative_selected_feature_fraction")])
        mask, score = mask_fitness(row["mask"], fitness)
        require(mask not in known or known[mask] == score, "repeated mask score is nondeterministic")
        known[mask] = score
        improvement = best_score is None or score > best_score
        require(row["terminal_best_update"] is improvement, "terminal-update flag mismatch")
        if improvement:
            best_mask, best_score, best_call = mask, score, row["call"]
        best_primary = max(score[0], best_primary if best_primary is not None else score[0])
        require(row["best_so_far_weighted_balanced_accuracy"] == best_primary, "best-so-far path mismatch")
        trajectory.append(best_primary)
        if escape and first_exit is None and score[0] > initial["fitness"][0]:
            first_exit = row["call"]
    terminal_mask, terminal_score = mask_fitness(trace["terminal"]["mask"], trace["terminal"]["fitness"])
    require((terminal_mask, terminal_score, trace["terminal"]["call"]) == (best_mask, best_score, best_call),
            "terminal mask is not the earliest lexicographic best queried mask")
    require(math.isclose(trace["normalized_auc_best_so_far_validation_wba_1_400"],
                         statistics.fmean(trajectory), rel_tol=0, abs_tol=1e-15), "AUC mismatch")
    if escape:
        event = trace["escape"]
        require(event["first_exit_call"] == first_exit, "first-exit call mismatch")
        require(event["censored"] is (first_exit is None), "censoring flag mismatch")
        require(event["restricted_calls"] == (first_exit if first_exit is not None else 400),
                "restricted calls omit or change nonexits")
        accepted_exit = event["first_accepted_exit_call"]
        require(accepted_exit is None or (first_exit is not None and first_exit <= accepted_exit <= 400),
                "accepted exit precedes queried exit")
        accepted_from_journal = next((generation["calls_after"] for generation in trace["generation_trace"]
                                     if generation["accepted"] and generation["eligible_count"] > 0
                                     and generation["parent_fitness_after"][0] > initial["fitness"][0]), None)
        require(accepted_exit == accepted_from_journal, "accepted escape not linked to generation journal")
        require(trace["normalized_auc_best_so_far_validation_wba_51_400"] is None,
                "escape was assigned a population-initialization AUC")
    else:
        require(math.isclose(trace["normalized_auc_best_so_far_validation_wba_51_400"],
                             statistics.fmean(trajectory[50:]), rel_tol=0, abs_tol=1e-15), "post-initialization AUC mismatch")
    if trace["arm"] == "lambda_fixed1":
        require(trace["terminal_state"]["final_lambda"] == 1, "fixed lambda changed")
        require(all(row["lambda_before"] == 1 and row["lambda_after"] == 1
                    for row in trace["generation_trace"]), "fixed lambda generation changed")


def validate_lambda_generation_journal(trace: Mapping[str, Any], *, escape: bool = False) -> None:
    """Independently check recorded transitions; no evaluator or RNG replay.

    Any tied maximizing mutant/candidate is permitted, but the selected mutant
    must be the same recorded reference for crossover and final selection.
    """
    require(trace["arm"] in ESCAPE_ARMS, "generation journal is not a lambda arm")
    records = trace["evaluations"]
    cursor = 0 if escape else 50
    state = trace["terminal_state"]
    if escape:
        parent, parent_score = mask_fitness(trace["initial"]["mask"], trace["initial"]["fitness"])
        start_wba = parent_score[0]
        require(state["initial_parent_index"] is None, "known-parent run selected a population parent")
    else:
        initial_index = state["initial_parent_index"]
        require(type(initial_index) is int and 0 <= initial_index < 50, "invalid initial parent reference")
        initial_scores = []
        for index, record in enumerate(records[:50]):
            require(record["phase"] == "initial_population" and record["phase_index"] == index
                    and record["generation"] == 0, "initial phase call references mismatch")
            initial_scores.append(mask_fitness(record["mask"], record["fitness"])[1])
        parent, parent_score = mask_fitness(records[initial_index]["mask"], records[initial_index]["fitness"])
        require(parent_score == max(initial_scores), "initial parent does not maximize initial fitness")
        start_wba = None
    lambda_real = 1.0
    any_tail = False
    generations = trace["generation_trace"]
    require(generations, "lambda journal lacks its required generations")
    for number, generation in enumerate(generations, 1):
        require(generation["generation"] == number and generation["calls_before"] == cursor,
                "generation numbering/call boundary mismatch")
        require(type(generation["lambda_before"]) in (int, float)
                and math.isfinite(generation["lambda_before"])
                and 1 <= generation["lambda_before"] <= 40
                and generation["lambda_before"] == lambda_real, "adaptive lambda bound/transition mismatch")
        planned = math.floor(lambda_real + 0.5)
        count = min(planned, (400 - cursor) // 2)
        require(count > 0 and generation["planned_offspring_count_per_phase"] == planned
                and generation["evaluated_offspring_count_per_phase"] == count,
                "lambda phase counts differ from planned paired-tail rule")
        require(generation["mutation_probability"] == lambda_real / 40
                and generation["crossover_probability"] == 1 / lambda_real,
                "tail counts changed lambda-based mutation/crossover probabilities")
        require(tuple(generation["parent_before"]) == parent
                and tuple(generation["parent_fitness_before"]) == parent_score,
                "generation parent does not match preceding transition")
        strength = generation["mutation_strength"]
        require(type(strength) is int and 0 <= strength <= 40, "invalid shared mutation strength")
        finish = cursor + 2 * count
        require(generation["calls_after"] == finish and finish <= 400, "generation call total mismatch")
        mutants, crossovers = records[cursor:cursor + count], records[cursor + count:finish]
        require(len(mutants) == count and len(crossovers) == count, "mutation/crossover phases are not equally complete")
        for phase, phase_records in (("mutation", mutants), ("crossover", crossovers)):
            for index, record in enumerate(phase_records):
                require(record["generation"] == number and record["phase"] == phase
                        and record["phase_index"] == index, "generation phase/index reference mismatch")
        mutant_values = [mask_fitness(record["mask"], record["fitness"]) for record in mutants]
        require(all(sum(first != second for first, second in zip(mask, parent)) == strength
                    for mask, _ in mutant_values), "mutants do not share the recorded Hamming strength")
        chosen_index = generation["selected_mutant_index"]
        require(type(chosen_index) is int and 0 <= chosen_index < count, "chosen mutant index invalid")
        chosen_mask, chosen_score = mutant_values[chosen_index]
        require(chosen_score == max(score for _, score in mutant_values), "chosen mutant is not a maximizing mutant")
        require(tuple(generation["selected_mutant_mask"]) == chosen_mask
                and tuple(generation["selected_mutant_fitness"]) == chosen_score,
                "crossover/selection chosen-mutant reference was redrawn")
        crossover_values = [mask_fitness(record["mask"], record["fitness"]) for record in crossovers]
        if lambda_real == 1:
            require(all(mask == chosen_mask for mask, _ in crossover_values),
                    "unit crossover probability did not reproduce chosen mutant")
        if lambda_real == 40:
            require(strength == 40, "unit mutation probability did not flip every bit")
        require(all(all(bit == parent[index] or bit == chosen_mask[index] for index, bit in enumerate(mask))
                    for mask, _ in crossover_values), "crossover contains an allele outside parent/chosen mutant")
        pool = [(chosen_mask, chosen_score, "mutation", chosen_index)] + [
            (mask, score, "crossover", index) for index, (mask, score) in enumerate(crossover_values)]
        eligible = [item for item in pool if item[0] != parent]
        require(generation["eligible_count"] == len(eligible), "selection removed duplicates or retained parent copies")
        candidate, candidate_score = mask_fitness(generation["candidate_mask"], generation["candidate_fitness"])
        reference = (candidate, candidate_score, generation["candidate_phase"], generation["candidate_phase_index"])
        if eligible:
            require(reference in eligible and candidate_score == max(item[1] for item in eligible),
                    "candidate is not a maximizing eligible pool reference")
        else:
            require(reference == (parent, parent_score, "parent", None), "empty eligible pool did not retain parent")
        success, accepted = candidate_score > parent_score, candidate_score >= parent_score
        after_parent, after_score = (candidate, candidate_score) if accepted else (parent, parent_score)
        require(generation["strict_success"] is success and generation["accepted"] is accepted
                and generation["parent_changed"] is (after_parent != parent), "acceptance/success transition mismatch")
        require(tuple(generation["parent_after"]) == after_parent
                and tuple(generation["parent_fitness_after"]) == after_score, "post-selection parent mismatch")
        accepted_at = finish if accepted and eligible else None
        require(generation["accepted_at_call"] == accepted_at, "acceptance call reference mismatch")
        generation_records = mutants + crossovers
        require(generation["first_strict_improvement_call"] == next(
            (row["call"] for row in generation_records if tuple(row["fitness"]) > parent_score), None),
            "first strict-generation improvement reference mismatch")
        require(generation["first_higher_start_wba_call"] == next(
            (row["call"] for row in generation_records if escape and row["fitness"][0] > start_wba), None),
            "first higher-start-WBA reference mismatch")
        expected_accepted_exit = bool(escape and accepted_at is not None and after_score[0] > start_wba)
        require(generation["accepted_higher_start_wba"] is expected_accepted_exit, "accepted quality-exit flag mismatch")
        if trace["arm"] == "lambda_fixed1":
            lambda_after = 1.0
        else:
            lambda_after = max(1.0, lambda_real / 1.5) if success else min(40.0, lambda_real * 1.5 ** 0.25)
        require(generation["lambda_after"] == lambda_after and generation["reset_event"] is False,
                "lambda update differs from registered factor or enabled reset")
        truncated = count < planned
        require(generation["tail_truncated"] is truncated, "terminal paired-tail flag mismatch")
        any_tail = any_tail or truncated
        parent, parent_score, lambda_real, cursor = after_parent, after_score, lambda_after, finish
    require(cursor == 400, "generation journal does not account for all 400 calls")
    require(state["generation_count"] == len(generations) and state["final_lambda"] == lambda_real
            and tuple(state["parent_mask"]) == parent and tuple(state["parent_fitness"]) == parent_score
            and state["parent_mask_sha256"] == canonical_sha256(list(parent))
            and state["tail_truncated"] is any_tail and state["workers"] == 1,
            "terminal lambda/parent state differs from generation journal")
    expected_phase = "paired_mutant_crossover_tail" if generations[-1]["tail_truncated"] else "complete_lambda_generation"
    require(trace["termination_phase"] == expected_phase, "termination phase differs from final generation")


def validate_preparation(preparation: Mapping[str, Any]) -> None:
    require(preparation["schema"] == "eu26-21-local-optima-preparation-v1", "preparation schema mismatch")
    require(preparation["dimension"] == 40, "certificate dimension mismatch")
    center, score = mask_fitness(preparation["center_mask"], preparation["center_fitness"])
    source, source_score = mask_fitness(preparation["source_mask"], preparation["source_fitness"])
    records = preparation["evaluations"]
    require(1 <= preparation["one_bit_passes"] <= 20, "unregistered ascent-pass count")
    require(preparation["diagnostic_calls"] == len(records) <= 1622, "diagnostic call count mismatch")
    require([row["call"] for row in records] == list(range(1, len(records) + 1)), "diagnostic call-index mismatch")
    known = {source: source_score}
    for row in records:
        mask, fitness = mask_fitness(row["mask"], row["fitness"])
        require(mask not in known or known[mask] == fitness, "diagnostic objective not deterministic")
        known[mask] = fitness
    require(tuple(records[0]["mask"]) == source and tuple(records[0]["fitness"]) == source_score,
            "source center failed to reproduce")
    require(records[0]["phase"] == "source_center_recheck", "source recheck phase mismatch")
    cursor = 1
    ascent_center, ascent_score = source, source_score
    ascent = preparation["ascent_trace"]
    require(len(ascent) == preparation["one_bit_passes"], "ascent journal length mismatch")
    for pass_number, journal in enumerate(ascent, 1):
        candidates = []
        for bit in range(40):
            row = records[cursor]
            mask, fitness = mask_fitness(row["mask"], row["fitness"])
            changed = [index for index in range(40) if mask[index] != ascent_center[index]]
            require(row["phase"] == "ascent_one_bit" and row["one_bit_pass"] == pass_number
                    and changed == [bit], "ascent is not a complete ordered N1 pass")
            candidates.append((fitness, bit, mask))
            cursor += 1
        best_score, best_bit, best_mask = max(candidates, key=lambda item: item[0])
        moved = best_score > ascent_score
        require(journal["pass"] == pass_number and journal["calls_before"] == cursor - 40
                and journal["calls_after"] == cursor, "ascent call boundaries mismatch")
        require(tuple(journal["center_before"]) == ascent_center and tuple(journal["fitness_before"]) == ascent_score,
                "ascent center changed outside registered move")
        require(journal["best_neighbor_bit"] == best_bit and tuple(journal["best_neighbor_mask"]) == best_mask
                and tuple(journal["best_neighbor_fitness"]) == best_score and journal["moved"] is moved,
                "ascent did not select best fitness / lowest bit tie")
        if moved:
            ascent_center, ascent_score = best_mask, best_score
        else:
            require(pass_number == len(ascent), "ascent continued after a converged full pass")
        require(tuple(journal["center_after"]) == ascent_center and tuple(journal["fitness_after"]) == ascent_score,
                "ascent post-move mismatch")
    require((ascent_center, ascent_score) == (center, score), "final center differs from ascent endpoint")
    require(preparation["pass_cap_hit"] is (len(ascent) == 20 and ascent[-1]["moved"]),
            "ascent pass-cap status mismatch")
    certificate = preparation["certificate"]
    neighbors = certificate["neighbors"]
    require(certificate["complete"] is True and len(neighbors) == 40, "incomplete N1 certificate")
    require([row["bit"] for row in neighbors] == list(range(40)), "N1 certificate misses or duplicates a bit")
    require(tuple(certificate["center_recheck_fitness"]) == score, "audited center changed")
    require(certificate["audit_calls_before"] == cursor and certificate["audit_calls_after"] == cursor + 41,
            "independent audit call boundaries mismatch")
    require(records[cursor]["phase"] == "audit_center_recheck" and tuple(records[cursor]["mask"]) == center
            and tuple(records[cursor]["fitness"]) == score, "independent audit center missing")
    cursor += 1
    neighbor_scores = []
    for row in neighbors:
        mask, fitness = mask_fitness(row["mask"], row["fitness"])
        changed = [index for index in range(40) if mask[index] != center[index]]
        require(changed == [row["bit"]], "N1 certificate does not flip its declared bit")
        require(records[row["call"] - 1]["mask"] == row["mask"]
                and records[row["call"] - 1]["fitness"] == row["fitness"], "N1 score not linked to diagnostic ledger")
        require(row["call"] == cursor + 1 and records[cursor]["phase"] == "audit_one_bit", "audit neighbor order mismatch")
        cursor += 1
        neighbor_scores.append(fitness)
    expected_flags = {
        "lexicographic_local_maximum": all(fitness <= score for fitness in neighbor_scores),
        "wba_local_maximum": all(fitness[0] <= score[0] for fitness in neighbor_scores),
        "strict_wba_local_maximum": all(fitness[0] < score[0] for fitness in neighbor_scores),
        "strict_lexicographic_local_maximum": all(fitness < score for fitness in neighbor_scores),
    }
    for key, value in expected_flags.items():
        require(certificate[key] is value, f"certificate {key} flag mismatch")
    require(certificate["equal_wba_neighbors"] == [row["bit"] for row in neighbors if row["fitness"][0] == score[0]],
            "plateau-neighbor list mismatch")
    equal_full = [row["bit"] for row in neighbors if tuple(row["fitness"]) == score]
    require(certificate["equal_full_fitness_neighbors"] == equal_full
            and certificate["wba_plateau"] is bool(certificate["equal_wba_neighbors"])
            and certificate["lexicographic_plateau"] is bool(equal_full), "plateau certificate flags mismatch")
    witness = preparation["witness"]
    require(0 <= preparation["witness_calls"] <= 780, "witness-call cap mismatch")
    witness_records = records[cursor:]
    require(len(witness_records) == preparation["witness_calls"], "witness ledger size mismatch")
    expected_bit_pairs = list(combinations(range(40), 2))
    for index, row in enumerate(witness_records):
        mask, fitness = mask_fitness(row["mask"], row["fitness"])
        changed = [bit for bit in range(40) if mask[bit] != center[bit]]
        require(row["phase"] == "two_bit_witness" and tuple(changed) == expected_bit_pairs[index],
                "witness enumeration is not registered lexicographic prefix")
        require(index == len(witness_records) - 1 or fitness[0] <= score[0], "witness search skipped an earlier higher WBA")
    if witness is not None:
        mask, fitness = mask_fitness(witness["mask"], witness["fitness"])
        changed = [index for index in range(40) if mask[index] != center[index]]
        require(changed == witness["changed_bits"] and len(changed) == 2, "witness not a two-bit neighbor")
        require(fitness[0] > score[0], "witness WBA is not higher")
        require(records[witness["call"] - 1]["mask"] == witness["mask"]
                and records[witness["call"] - 1]["fitness"] == witness["fitness"], "witness not linked to diagnostic ledger")
        require(witness["call"] == len(records), "witness enumeration did not stop at first higher WBA")
    elif expected_flags["lexicographic_local_maximum"] and expected_flags["wba_local_maximum"]:
        require(len(witness_records) == 780 and all(row["fitness"][0] <= score[0] for row in witness_records),
                "local case without witness lacks complete N2 search")
    else:
        require(not witness_records, "witness search ran for a nonlocal center")
    eligible = expected_flags["lexicographic_local_maximum"] and expected_flags["wba_local_maximum"] and witness is not None
    require(preparation["eligible"] is eligible, "eligibility contradicts certificate")
    expected_status = ("eligible" if eligible else "ineligible_final_one_bit_not_local"
                       if not (expected_flags["lexicographic_local_maximum"] and expected_flags["wba_local_maximum"])
                       else "ineligible_no_two_bit_witness")
    require(preparation["status"] == expected_status, "preparation status mismatch")


def _artifact_ledger(path: Path, *, prefix: str, expected_sha: str, source_run_id: int) -> dict[str, dict[str, Any]]:
    raw = read_json(path)
    require(isinstance(raw, dict) and isinstance(raw.get("artifacts"), list), "invalid source artifact ledger")
    output = {}
    ids = set()
    for artifact in raw["artifacts"]:
        name = artifact["name"]
        require(name.startswith(prefix), "unscoped artifact in pinned ledger")
        require(name not in output and artifact["id"] not in ids, "duplicate source artifact name or ID")
        require(type(artifact["id"]) is int and artifact["id"] > 0, "invalid source artifact ID")
        require(artifact.get("expired") is not True, "source artifact expired")
        workflow = artifact["workflow_run"]
        require(workflow["head_sha"] == expected_sha and workflow["id"] == source_run_id,
                "source artifact belongs to wrong SHA or workflow run")
        output[name] = artifact
        ids.add(artifact["id"])
    return output


def load_cases(cases_dir: Path, ledger_path: Path, *, expected_sha: str, source_run_id: int) -> list[dict[str, Any]]:
    ledger = _artifact_ledger(ledger_path, prefix="eu26-21-local-case-", expected_sha=expected_sha, source_run_id=source_run_id)
    require(len(ledger) == 30, "source ledger must contain exactly 30 case artifacts")
    cases = {}
    used_names = set()
    for path in cases_dir.rglob("manifest.json"):
        manifest = verify_manifest(path, expected_sha=expected_sha)
        require(manifest["repeat"] is None, "escape artifact appeared among prepared cases")
        seed = manifest["seed"]
        require(type(seed) is int and seed in CASE_SEEDS and seed not in cases, "wrong or duplicate case seed")
        name = manifest["artifact_name"]
        require(name in ledger, "downloaded case lacks a fixed source artifact ID")
        row = read_json(path.parent / manifest["row_file"])
        require(row["schema"] == CASE_SCHEMA and row["seed"] == seed, "case row schema or seed mismatch")
        require(row["provenance"] == manifest["provenance"], "case/manifest provenance mismatch")
        require(row["provenance"]["run_id"] == source_run_id, "case source run mismatch")
        require(set(row["arms"]) == set(ALL_ARMS), "comparison arms missing or extra")
        require(row["feature_names"] == list(TRANSFORMED_FEATURE_NAMES), "invalid transformed feature mapping")
        for arm in SEARCH_ARMS:
            trace_identity = row["arms"][arm]["trace"]
            trace_path = path.parent / trace_identity["file"]
            require(file_sha256(trace_path) == trace_identity["sha256"], "comparison trace hash mismatch")
            trace = read_json(trace_path)
            require(trace["arm"] == arm and trace["seed"] == seed and trace["pairing"] == row["pairing"],
                    "comparison trace identity mismatch")
            validate_search_trace(trace)
            if arm in ESCAPE_ARMS:
                validate_lambda_generation_journal(trace)
            require(trace["terminal"] == row["arms"][arm]["terminal"], "comparison terminal differs from trace")
            normalized_first = [{"mask": record["mask"], "fitness": record.get("fitness", [
                record.get("validation_weighted_balanced_accuracy"), record.get("negative_selected_feature_fraction")])}
                for record in trace["evaluations"][:50]]
            require(normalized_first == row["initial_evaluations"], "ordered initial scores differ across comparison arms")
            require([record["mask"] for record in normalized_first] == row["initial_masks"], "initial mask order mismatch")
        require(row["pairing"]["initial_masks_sha256"] == canonical_sha256(row["initial_masks"])
                and row["pairing"]["first_50_evaluations_sha256"] == canonical_sha256(row["initial_evaluations"]),
                "initial-mask/evaluation pairing hash mismatch")
        full = row["arms"]["full40"]
        mask_fitness(full["terminal"]["mask"], full["terminal"]["fitness"])
        require(full["objective_calls"] == 1 and full["terminal"]["mask"] == [1] * 40
                and full["initial_population_calls"] == 0 and full["terminal"]["selected_feature_count"] == 40
                and full["normalized_auc_best_so_far_validation_wba_1_400"] is None
                and full["normalized_auc_best_so_far_validation_wba_51_400"] is None
                and full["reset"] is False and full["reset_events"] == 0, "full40 baseline misclassified as search")
        ablation_specs = {"without_occupation": ("occupation_code", "major_occupation_code"),
                          "without_weeks": ("weeks_worked_in_year",)}
        require(set(row["ablations"]) == set(ablation_specs), "missing or unregistered feature ablation")
        for arm, removed in ablation_specs.items():
            ablation = row["ablations"][arm]
            expected_mask = [int(name not in removed) for name in TRANSFORMED_FEATURE_NAMES]
            mask_fitness(ablation["mask"], ablation["fitness"])
            require(ablation["mask"] == expected_mask and ablation["removed_feature_names"] == list(removed)
                    and ablation["objective_calls"] == 1 and ablation["test_evaluations"] == 0,
                    "ablation changed fixed masks, removed names or evaluation scope")
        freeze_path = path.parent / row["terminal_masks_freeze"]["file"]
        require(file_sha256(freeze_path) == row["terminal_masks_freeze"]["sha256"], "terminal freeze digest mismatch")
        freeze = read_json(freeze_path)
        require(freeze["test_evaluations_so_far"] == 0 and freeze["selected_by"] == "validation_only",
                "terminal masks were not frozen before test")
        for arm in ALL_ARMS:
            require(freeze["arms"][arm] == row["arms"][arm]["terminal"], "terminal mask changed after freeze")
            require(row["arms"][arm]["test_evaluations"] == 1, "terminal test evaluated more than once")
            model = row["models"][arm]
            require(model["file"] in manifest["files"]
                    and model["sha256"] == manifest["files"][model["file"]]["sha256"]
                    and model["bytes"] == manifest["files"][model["file"]]["bytes"], "retained model file identity mismatch")
            require(model["mask"] == row["arms"][arm]["terminal"]["mask"], "retained model mask mismatch")
            selected = [feature for feature, bit in zip(row["feature_names"], model["mask"]) if bit]
            require(model["selected_feature_names"] == selected, "selected feature mapping mismatch")
            for scale in ("weighted", "unweighted"):
                metrics = row["arms"][arm]["test_metrics"][scale]
                matrix = np.asarray(metrics["confusion_matrix"], dtype=float)
                if scale == "unweighted":
                    require(np.equal(matrix, np.floor(matrix)).all() and float(matrix.sum()) == 99762,
                            "unweighted confusion matrix is not 99762 record counts")
                require(metrics["classes"] == per_class_metrics(metrics["confusion_matrix"]), "per-class metrics mismatch")
                require(math.isclose(float(matrix[0].sum()), metrics["negative_support"], rel_tol=1e-10, abs_tol=1e-10)
                        and math.isclose(float(matrix[1].sum()), metrics["positive_support"], rel_tol=1e-10, abs_tol=1e-10),
                        "class support differs from confusion matrix")
                recalls = [metrics["classes"][label]["recall"] for label in ("0", "1")]
                require(math.isclose(statistics.fmean(recalls), metrics["balanced_accuracy"], abs_tol=1e-12),
                        "balanced accuracy differs from mean class recalls")
        preparation_path = path.parent / row["preparation"]["file"]
        require(file_sha256(preparation_path) == row["preparation"]["sha256"], "preparation digest mismatch")
        preparation = read_json(preparation_path)
        validate_preparation(preparation)
        require(preparation["source_mask"] == row["arms"]["chc_harmonized"]["terminal"]["mask"]
                and preparation["source_fitness"] == row["arms"]["chc_harmonized"]["terminal"]["fitness"],
                "prepared center source is not the CHC terminal")
        require(row["preparation"]["eligible"] is preparation["eligible"]
                and row["preparation"]["status"] == preparation["status"], "preparation row status mismatch")
        require(row["counts"] == {"comparison_search_calls": 1200, "static_validation_calls": 3,
                                  "diagnostic_calls": preparation["diagnostic_calls"], "test_evaluations": 4}
                and row["preparation"]["diagnostic_calls"] == preparation["diagnostic_calls"], "case call totals mismatch")
        require(row["preparation"]["center_sha256"] == canonical_sha256({
            "mask": preparation["center_mask"], "fitness": preparation["center_fitness"]}), "prepared center identity mismatch")
        cases[seed] = {"row": row, "preparation": preparation, "directory": path.parent,
                       "manifest_path": path, "artifact": ledger[name]}
        used_names.add(name)
    require(set(cases) == set(CASE_SEEDS) and used_names == set(ledger), "case completeness is not 30/30")
    return [cases[seed] for seed in CASE_SEEDS]


def freeze_cases(cases: Sequence[Mapping[str, Any]], *, expected_sha: str,
                 source_run_id: int, output_dir: Path) -> dict[str, Any]:
    require(len(cases) == 30, "cannot freeze an incomplete case registry")
    entries = []
    for case in cases:
        row = case["row"]
        entries.append({"seed": row["seed"], "eligible": case["preparation"]["eligible"],
                        "status": case["preparation"]["status"],
                        "source_artifact_id": case["artifact"]["id"], "source_artifact_name": case["artifact"]["name"],
                        "source_artifact_digest": case["artifact"].get("digest"),
                        "source_run_attempt": row["provenance"]["run_attempt"],
                        "manifest_sha256": file_sha256(case["manifest_path"]),
                        "row_sha256": file_sha256(case["directory"] / "case.json"),
                        "preparation_sha256": row["preparation"]["sha256"],
                        "center_sha256": row["preparation"]["center_sha256"],
                        "pairing": row["pairing"]})
    registry = {"schema": REGISTRY_SCHEMA, "protocol_id": PROTOCOL_ID,
                "protocol_sha256": PROTOCOL_SHA256, "implementation_sha": expected_sha,
                "source_run_id": source_run_id, "all_case_records_frozen": 30,
                "escape_outcomes_inspected": False, "cases": entries}
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "registry.json", registry)
    include = [{"seed": entry["seed"], "repeat": repeat}
               for entry in entries if entry["eligible"] for repeat in range(1, 6)]
    # An empty matrix is retained honestly. The workflow skips its matrix job
    # via eligible_count before materializing the strategy.
    write_json(output_dir / "matrix.json", {"include": include})
    write_json(output_dir / "freeze-summary.json", {"case_count": 30,
               "eligible_count": sum(entry["eligible"] for entry in entries), "escape_pair_count": len(include),
               "registry_sha256": file_sha256(output_dir / "registry.json"), "hypothesis_analysis_performed": False})
    return registry


def load_escapes(directory: Path, ledger_path: Path, *, registry: Mapping[str, Any],
                 registry_sha256: str, expected_sha: str, source_run_id: int) -> list[dict[str, Any]]:
    ledger = _artifact_ledger(ledger_path, prefix="eu26-21-local-escape-", expected_sha=expected_sha, source_run_id=source_run_id)
    eligible = {entry["seed"]: entry for entry in registry["cases"] if entry["eligible"]}
    expected_pairs = {(seed, repeat) for seed in eligible for repeat in range(1, 6)}
    require(len(ledger) == len(expected_pairs), "escape source ledger incomplete or contains extra pairs")
    output = {}
    used_names = set()
    for path in directory.rglob("manifest.json"):
        manifest = verify_manifest(path, expected_sha=expected_sha)
        pair = (manifest["seed"], manifest["repeat"])
        require(pair in expected_pairs and pair not in output, "wrong or duplicate escape pair")
        require(manifest["artifact_name"] in ledger, "escape lacks fixed source artifact ID")
        row = read_json(path.parent / manifest["row_file"])
        require(row["schema"] == ESCAPE_SCHEMA and (row["seed"], row["repeat"]) == pair, "escape row identity mismatch")
        require(row["source_registry_sha256"] == registry_sha256 and row["source_case"] == eligible[pair[0]],
                "escape did not use frozen certified case")
        require(row["provenance"] == manifest["provenance"] and row["source_run_id"] == registry["source_run_id"],
                "escape provenance mismatch")
        require(row["pairing"] == eligible[pair[0]]["pairing"], "escape evaluator pairing mismatch")
        require(row["search_seed"] == 10000000 + 100 * (pair[0] - 42001) + pair[1], "escape RNG seed mismatch")
        require(row["test_evaluations"] == 0 and set(row["arms"]) == set(ESCAPE_ARMS), "escape accessed test or changed arms")
        for arm in ESCAPE_ARMS:
            trace_path = path.parent / row["arms"][arm]["trace"]["file"]
            require(file_sha256(trace_path) == row["arms"][arm]["trace"]["sha256"], "escape trace digest mismatch")
            trace = read_json(trace_path)
            require(trace["arm"] == arm and trace["seed"] == row["search_seed"], "escape kernel identity mismatch")
            validate_search_trace(trace, escape=True)
            validate_lambda_generation_journal(trace, escape=True)
            require(trace["initial"] == row["arms"][arm]["initial"] and trace["escape"] == row["arms"][arm]["escape"],
                    "escape summary differs from retained trace")
            require(canonical_sha256({"mask": trace["initial"]["mask"], "fitness": trace["initial"]["fitness"]})
                    == eligible[pair[0]]["center_sha256"], "escape initial state is not certified center")
        require(row["arms"]["lambda_adaptive"]["initial"] == row["arms"]["lambda_fixed1"]["initial"],
                "escape arms did not start from same parent")
        output[pair] = {"row": row, "artifact": ledger[manifest["artifact_name"]],
                        "manifest_sha256": file_sha256(path)}
        used_names.add(manifest["artifact_name"])
    require(set(output) == expected_pairs and used_names == set(ledger), "escape pairs incomplete")
    return [output[pair] for pair in sorted(output)]


def case_cluster_analysis(escapes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    for item in escapes:
        row = item.get("row", item)
        grouped.setdefault(row["seed"], []).append(row)
    differences = []
    case_rows = []
    for seed in sorted(grouped):
        rows = grouped[seed]
        require(sorted(row["repeat"] for row in rows) == [1, 2, 3, 4, 5], "case lacks five unique paired repetitions")
        rates, times, success_counts = {}, {}, {}
        for arm in ESCAPE_ARMS:
            success_counts[arm] = sum(row["arms"][arm]["escape"]["first_exit_call"] is not None for row in rows)
            rates[arm] = success_counts[arm] / 5
            times[arm] = statistics.fmean(row["arms"][arm]["escape"]["restricted_calls"] for row in rows)
        # Equal integer success-count differences must remain exactly equal;
        # subtracting rounded rates can invent spurious bootstrap variance.
        difference = (success_counts["lambda_adaptive"] - success_counts["lambda_fixed1"]) / 5
        differences.append(difference)
        case_rows.append({"seed": seed, "adaptive_escape_rate": rates["lambda_adaptive"],
                          "fixed1_escape_rate": rates["lambda_fixed1"], "difference": difference,
                          "adaptive_restricted_mean_calls": times["lambda_adaptive"],
                          "fixed1_restricted_mean_calls": times["lambda_fixed1"]})
    count = len(differences)
    result = {"eligible_case_count": count, "paired_repeat_count": len(escapes), "bootstrap_unit": "entire_case",
              "bootstrap_resamples": 50000, "analysis_seed": 42031, "confidence_level": 0.95,
              "estimate": statistics.fmean(differences) if differences else None,
              "interval": None, "advantage": False, "cases": case_rows,
              "status": "NO_CERTIFIED_CASES" if count == 0 else "INTERVAL_UNAVAILABLE",
              "unavailable_reason": "fewer_than_two_eligible_cases" if count < 2 else None}
    if count < 2:
        return result
    if len(set(differences)) == 1:
        result["unavailable_reason"] = "constant_case_differences"
        return result
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        fitted = bootstrap((np.asarray(differences, dtype=float),), np.mean,
                           vectorized=True, n_resamples=50000, method="BCa", confidence_level=0.95,
                           batch=2000, rng=np.random.default_rng(42031))
    low, high = float(fitted.confidence_interval.low), float(fitted.confidence_interval.high)
    if not np.isfinite(fitted.bootstrap_distribution).all() or not math.isfinite(low) or not math.isfinite(high):
        result["unavailable_reason"] = "nonfinite_BCa"
    elif float(np.std(fitted.bootstrap_distribution)) == 0 or not low < high:
        result["unavailable_reason"] = "zero_bootstrap_variance_or_degenerate_interval"
    else:
        result.update({"interval": [low, high], "advantage": low > 0,
                       "status": "ADVANTAGE_CONFIRMED" if low > 0 else "ADVANTAGE_NOT_CONFIRMED",
                       "unavailable_reason": None})
    return result


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    names = list(fieldnames or (list(rows[0]) if rows else []))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


def _make_plots(cases: Sequence[Mapping[str, Any]], analysis: Mapping[str, Any], output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = {"chc_harmonized": "CHC", "lambda_adaptive": "Адаптивний",
              "lambda_fixed1": "Фіксований λ=1", "full40": "Усі 40 ознак"}
    scales = {"unweighted": "Кількість записів", "weighted": "Сума ваг"}
    selected = next(case for case in cases if case["row"]["seed"] == 42001)
    figure, axes = plt.subplots(2, 4, figsize=(13, 6), constrained_layout=True)
    for column, arm in enumerate(ALL_ARMS):
        for row_index, scale in enumerate(("unweighted", "weighted")):
            matrix = np.asarray(selected["row"]["arms"][arm]["test_metrics"][scale]["confusion_matrix"])
            axis = axes[row_index, column]
            axis.imshow(matrix / matrix.sum(axis=1, keepdims=True), vmin=0, vmax=1, cmap="Blues")
            for y in range(2):
                for x in range(2):
                    value = f"{matrix[y, x]:.0f}" if scale == "unweighted" else f"{matrix[y, x]:.1f}".replace(".", ",")
                    axis.text(x, y, value, ha="center", va="center")
            axis.set(title=f"{labels[arm]}\n{scales[scale]}", xlabel="Прогнозований клас", ylabel="Фактичний клас",
                     xticks=[0, 1], yticks=[0, 1])
    figure.suptitle("Пара 42001: кількість записів і суми ваг окремих моделей")
    figure.savefig(output / "confusion-matrices-42001.png", dpi=170)
    plt.close(figure)
    figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
    for arm in SEARCH_ARMS:
        trajectories = [np.asarray([row["best_so_far_weighted_balanced_accuracy"]
                                   for row in read_json(case["directory"] / case["row"]["arms"][arm]["trace"]["file"])["evaluations"]])
                        for case in cases]
        axis.plot(range(1, 401), np.mean(trajectories, axis=0), label=labels[arm])
    axis.plot([1], [statistics.fmean(case["row"]["arms"]["full40"]["terminal"]["fitness"][0] for case in cases)],
              marker="D", linestyle="None", label="Усі 40 ознак: одна оцінка", color="black")
    axis.set(xlabel="Кількість оцінювань", ylabel="Середня найкраща валідаційна WBA",
             title="Описове порівняння середніх валідаційних траєкторій")
    axis.legend(fontsize=8)
    figure.savefig(output / "comparison-trajectories.png", dpi=170)
    plt.close(figure)
    eligible = [case for case in cases if case["preparation"]["eligible"]]
    if eligible:
        preparation = eligible[0]["preparation"]
        figure, axis = plt.subplots(figsize=(9, 4), constrained_layout=True)
        center_wba = preparation["center_fitness"][0]
        axis.scatter(range(1, 41), [neighbor["fitness"][0] - center_wba
                                  for neighbor in preparation["certificate"]["neighbors"]], label="Однобітні сусіди")
        axis.axhline(0, color="black", linewidth=1)
        axis.scatter([41], [preparation["witness"]["fitness"][0] - center_wba], color="red", label="Кращий двобітний свідок")
        axis.set(xlabel="Позиція сусіда (1-40) або свідка (41)", ylabel="Валідаційна WBA мінус оцінка центру",
                 title=f"Підтверджений локальний максимум, випадок {eligible[0]['row']['seed']}")
        axis.legend(fontsize=8)
        figure.savefig(output / "certified-neighborhood.png", dpi=170)
        plt.close(figure)
        rows = analysis["cases"]
        figure, axis = plt.subplots(figsize=(10, 4), constrained_layout=True)
        axis.plot([row["seed"] for row in rows], [row["adaptive_escape_rate"] for row in rows], "o-", label="Адаптивний")
        axis.plot([row["seed"] for row in rows], [row["fixed1_escape_rate"] for row in rows], "o-", label="Фіксований λ=1")
        axis.set(ylim=(-0.05, 1.05), xlabel="Початкове значення генератора випадку", ylabel="Частка виходів у п'яти повтореннях",
                 title="П'ять парних повторень для кожного підготовленого випадку")
        axis.legend()
        figure.savefig(output / "escape-rates-by-case.png", dpi=170)
        plt.close(figure)


def build_report(cases: Sequence[Mapping[str, Any]], escapes: Sequence[Mapping[str, Any]],
                 registry: Mapping[str, Any], *, output_dir: Path,
                 registry_sha256: str) -> dict[str, Any]:
    analysis = case_cluster_analysis(escapes)
    comparisons, class_rows, ablation_rows, preparation_rows = [], [], [], []
    for case in cases:
        row, preparation = case["row"], case["preparation"]
        for arm in ALL_ARMS:
            result = row["arms"][arm]
            comparisons.append({"seed": row["seed"], "arm": arm,
                                "validation_wba": result["terminal"]["fitness"][0],
                                "test_wba": result["test_metrics"]["weighted"]["balanced_accuracy"],
                                "selected_features": sum(result["terminal"]["mask"]),
                                "objective_calls": result["objective_calls"],
                                "bsf_auc": result["normalized_auc_best_so_far_validation_wba_1_400"]})
            for scale in ("unweighted", "weighted"):
                block = result["test_metrics"][scale]
                for label in ("0", "1"):
                    class_rows.append({"seed": row["seed"], "arm": arm, "scale": scale,
                                       "class": label, **per_class_metrics(block["confusion_matrix"])[label]})
        for name, ablation in row["ablations"].items():
            ablation_rows.append({"seed": row["seed"], "arm": name, "validation_wba": ablation["fitness"][0],
                                 "difference_from_full40": ablation["fitness"][0] - row["arms"]["full40"]["terminal"]["fitness"][0]})
        preparation_rows.append({"seed": row["seed"], "status": preparation["status"], "eligible": preparation["eligible"],
                                 "diagnostic_calls": preparation["diagnostic_calls"], "one_bit_passes": preparation["one_bit_passes"],
                                 "center_wba": preparation["center_fitness"][0], "center_features": sum(preparation["center_mask"]),
                                 "equal_wba_neighbor_count": len(preparation["certificate"]["equal_wba_neighbors"]),
                                 "strict_wba_local_maximum": preparation["certificate"]["strict_wba_local_maximum"],
                                 "witness_wba": preparation["witness"]["fitness"][0] if preparation["witness"] else None})
    summaries = {}
    for arm in ALL_ARMS:
        rows = [row for row in comparisons if row["arm"] == arm]
        summaries[arm] = {"median_validation_wba": statistics.median(row["validation_wba"] for row in rows),
                          "median_test_wba": statistics.median(row["test_wba"] for row in rows),
                          "median_selected_features": statistics.median(row["selected_features"] for row in rows),
                          "median_bsf_auc": None if arm == "full40" else statistics.median(row["bsf_auc"] for row in rows)}
    report = {"schema": "eu26-21-local-optima-study-report-v1", "protocol_id": PROTOCOL_ID,
              "implementation_sha": registry["implementation_sha"], "source_run_id": registry["source_run_id"],
              "source_registry_sha256": registry_sha256, "case_count": len(cases),
              "comparison_summary": summaries, "primary_escape_analysis": analysis,
              "counts": {"comparison_search_calls": 1200 * len(cases), "static_validation_calls": 3 * len(cases),
                         "diagnostic_calls": sum(case["preparation"]["diagnostic_calls"] for case in cases),
                         "escape_search_calls": 800 * len(escapes), "test_evaluations": 4 * len(cases)},
              "historical_noninferiority_status": "FAIL_NONINFERIORITY_UNCHANGED",
              "confusion_matrices_pooled_across_models": False,
              "escape_source_artifacts": [{"id": item["artifact"]["id"], "name": item["artifact"]["name"],
                                            "digest": item["artifact"].get("digest"), "manifest_sha256": item["manifest_sha256"]}
                                           for item in escapes],
              "limits": ["prepared_cases_not_natural_trapping_frequency", "fixed1_not_best_tuned_static_lambda",
                         "validation_escape_not_test_quality_superiority", "known_test_benchmark_not_new_external_data",
                         "conditional_empirical_landscape_not_population_causality"]}
    require(sum(report["counts"][key] for key in ("comparison_search_calls", "static_validation_calls", "diagnostic_calls", "escape_search_calls"))
            <= 204750, "campaign exceeds validation-call upper bound")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "summary.json", report)
    _write_csv(output_dir / "comparison.csv", comparisons)
    _write_csv(output_dir / "per-class-metrics.csv", class_rows)
    _write_csv(output_dir / "feature-ablations.csv", ablation_rows)
    _write_csv(output_dir / "prepared-cases.csv", preparation_rows)
    _write_csv(output_dir / "escape-case-clusters.csv", analysis["cases"], ["seed", "adaptive_escape_rate", "fixed1_escape_rate",
               "difference", "adaptive_restricted_mean_calls", "fixed1_restricted_mean_calls"])
    pair_rows = [{"seed": item["row"]["seed"], "repeat": item["row"]["repeat"], "arm": arm,
                  **item["row"]["arms"][arm]["escape"]} for item in escapes for arm in ESCAPE_ARMS]
    _write_csv(output_dir / "escape-repetitions.csv", pair_rows, ["seed", "repeat", "arm", "first_exit_call", "first_accepted_exit_call", "censored", "restricted_calls"])
    lines = ["# Помилки класифікації та вихід із підготовлених локальних максимумів", "",
             "Нову серію відокремлено від історичного результату FAIL_NONINFERIORITY. "
             "Матриці різних моделей не об'єднано як незалежні спостереження.", "",
             "## Порівняння чотирьох методів", "", "Наведено медіани 30 запусків, не довірчі інтервали.", "",
             "| Метод | Валідаційна WBA | Тестова WBA | Кількість ознак | BSF-AUC |", "| --- | ---: | ---: | ---: | ---: |"]
    for arm, values in summaries.items():
        auc = "не застосовується" if values["median_bsf_auc"] is None else f"{values['median_bsf_auc']:.6f}"
        lines.append(f"| {arm} | {values['median_validation_wba']:.6f} | {values['median_test_wba']:.6f} | {values['median_selected_features']:g} | {auc} |")
    lines.extend(["", "## Контрольований вихід", "", f"Допущено {analysis['eligible_case_count']} із 30 підготовлених випадків. "
                  f"Кількість парних повторень: {analysis['paired_repeat_count']}.", "",
                  f"Статус первинної перевірки: `{analysis['status']}`."])
    if analysis["estimate"] is not None:
        lines.append(f"Середня різниця часток виходу adaptive − fixed1: {analysis['estimate']:.6f}.")
    if analysis["interval"] is not None:
        lines.append(f"95% BCa-інтервал: [{analysis['interval'][0]:.6f}; {analysis['interval'][1]:.6f}].")
    else:
        lines.append(f"Інтервал недоступний: {analysis['unavailable_reason']}.")
    lines.extend(["", "Кожна повторна вибірка містить цілі випадки разом з обома алгоритмами та всіма п'ятьма повтореннями. "
                  "Невиходи залишено з обмеженням на 400 оцінюваннях.", "",
                  "*Висновок стосується підготовлених станів цього набору даних. Порівняння з λ=1 не визначає "
                  "найкращого фіксованого λ. Вища частота виходу не доводить кращої тестової класифікації. "
                  "Причинний вплив професії чи трудової активності на дохід не встановлюється.*", ""])
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    _make_plots(cases, analysis, output_dir)
    identities = {path.name: {"sha256": file_sha256(path), "bytes": path.stat().st_size}
                  for path in sorted(output_dir.iterdir()) if path.is_file()}
    write_json(output_dir / "report-manifest.json", {"schema": "eu26-21-local-optima-report-manifest-v1",
               "implementation_sha": registry["implementation_sha"], "source_run_id": registry["source_run_id"],
               "protocol_sha256": PROTOCOL_SHA256, "registry_sha256": registry_sha256, "files": identities})
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze-cases", action="store_true")
    mode.add_argument("--report", action="store_true")
    for name in ("cases-dir", "case-ledger", "output-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--registry-sha256")
    parser.add_argument("--escapes-dir", type=Path)
    parser.add_argument("--escape-ledger", type=Path)
    args = parser.parse_args()
    authenticate(protocol_path=THIS_DIRECTORY / "protocol.json", expected_sha=args.expected_sha,
                 expected_protocol_sha256=PROTOCOL_SHA256)
    cases = load_cases(args.cases_dir, args.case_ledger, expected_sha=args.expected_sha, source_run_id=args.source_run_id)
    if args.freeze_cases:
        freeze_cases(cases, expected_sha=args.expected_sha, source_run_id=args.source_run_id, output_dir=args.output_dir)
        print("PASS_COMPLETE_30_CASE_REGISTRY_FROZEN")
        return
    require(all(value is not None for value in (args.registry, args.registry_sha256, args.escapes_dir, args.escape_ledger)),
            "report needs registry digest and all source escape artifacts")
    require(file_sha256(args.registry) == args.registry_sha256, "report registry byte digest mismatch")
    registry = read_json(args.registry)
    # Recreate identity records into a transient comparison object, not by
    # rewriting the downloaded immutable registry.
    expected_entries = []
    for case in cases:
        row = case["row"]
        expected_entries.append({"seed": row["seed"], "eligible": case["preparation"]["eligible"],
            "status": case["preparation"]["status"], "source_artifact_id": case["artifact"]["id"],
            "source_artifact_name": case["artifact"]["name"], "source_artifact_digest": case["artifact"].get("digest"),
            "source_run_attempt": row["provenance"]["run_attempt"], "manifest_sha256": file_sha256(case["manifest_path"]),
            "row_sha256": file_sha256(case["directory"] / "case.json"), "preparation_sha256": row["preparation"]["sha256"],
            "center_sha256": row["preparation"]["center_sha256"], "pairing": row["pairing"]})
    require(registry["schema"] == REGISTRY_SCHEMA and registry["cases"] == expected_entries,
            "registry no longer matches exact 30 fixed source artifacts")
    require(registry["implementation_sha"] == args.expected_sha and registry["source_run_id"] == args.source_run_id
            and registry["protocol_sha256"] == PROTOCOL_SHA256 and registry["escape_outcomes_inspected"] is False,
            "registry contract mismatch")
    escapes = load_escapes(args.escapes_dir, args.escape_ledger, registry=registry,
                           registry_sha256=args.registry_sha256, expected_sha=args.expected_sha,
                           source_run_id=args.source_run_id)
    report = build_report(cases, escapes, registry, output_dir=args.output_dir, registry_sha256=args.registry_sha256)
    print(f"PASS_COMPLETE_CAMPAIGN_REPORT {report['primary_escape_analysis']['status']}")


if __name__ == "__main__":
    main()

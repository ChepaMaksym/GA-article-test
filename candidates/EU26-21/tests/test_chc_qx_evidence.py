"""CI-only positive and tampered-row checks for independent evidence validation."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chc_qx_alignment_study.diagnostics import certify_snapshot
from chc_qx_alignment_study.search import run_qx_search
from chc_qx_alignment_study.validate_evidence import validate_diagnostic, validate_search


def _initial():
    return [tuple(index % 2 for index in range(40))]*50


def _run(arm="lambda_fixed1_qx", **changes):
    values = {
        "arm": arm, "initial_masks": _initial(), "initial_scores": [0.5]*50,
        "active_objective": lambda _mask: 0.5, "full_objective": lambda _mask: 0.7,
        "seed": 44001,
    }
    values.update(changes)
    return run_qx_search(**values)


def _source_fixture():
    from deap import base

    class ScalarFitness(base.Fitness):
        weights = (1.0,)

    class Individual(list):
        def __init__(self, values=()):
            super().__init__(values)
            self.fitness = ScalarFitness()

    def create_toolbox(*_arguments):
        toolbox = base.Toolbox()
        toolbox.register("evaluate", lambda _mask: (0.5,))
        return toolbox

    def native_chc(_dataset, toolbox, distance, population, **_keywords):
        child = copy.deepcopy(population[0])
        child[0] = 1-child[0]
        child.fitness.values = toolbox.evaluate(child)
        return None, [child]+population[1:], distance

    return SimpleNamespace(create_toolbox=create_toolbox, CHC=native_chc), SimpleNamespace(Individual=Individual)


class SearchEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixed = _run()
        cls.adaptive = _run("lambda_adaptive_qx")
        source, creator = _source_fixture()
        cls.chc = _run("chc_qx", evolution=source, deap_creator=creator)

    def _reject(self, trace, mutate, pattern=None):
        changed = copy.deepcopy(trace)
        mutate(changed)
        context = self.assertRaises(ValueError) if pattern is None else self.assertRaisesRegex(ValueError, pattern)
        with context:
            validate_search(changed, _initial(), [0.5]*50)

    def test_generated_scalar_traces_of_all_three_arms_pass(self):
        for trace in (self.fixed, self.adaptive, self.chc):
            with self.subTest(arm=trace["arm"]):
                validate_search(trace, _initial(), [0.5]*50)

    def test_initial_mask_order_and_frozen_scores_are_authenticated(self):
        wrong_masks = _initial()
        wrong_masks[0] = (1,)*40
        with self.assertRaises(ValueError):
            validate_search(self.fixed, wrong_masks, [0.5]*50)
        with self.assertRaises(ValueError):
            validate_search(self.fixed, _initial(), [0.4]+[0.5]*49)
        self._reject(self.fixed, lambda row: row["active_trace"][0].update(physical=True))
        self._reject(self.fixed, lambda row: row.update(initial_physical_calls=50))

    def test_duplicate_calls_and_best_so_far_are_independently_checked(self):
        self._reject(self.fixed, lambda row: row["active_trace"][1].update(wba=0.4), "duplicate active")
        self._reject(self.fixed, lambda row: row["active_trace"][50].update(call=50))
        self._reject(self.fixed, lambda row: row["active_trace"][50].update(best_so_far_wba=0.6))
        self._reject(self.fixed, lambda row: row["active_trace"][50].update(physical=False))

    def test_scalar_success_acceptance_and_lambda_proposal_are_checked(self):
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(strict_success=True))
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(accepted=False))
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(proposed_lambda_after=1.0))
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(applied_lambda_after=2.0))
        self._reject(self.adaptive, lambda row: row["generation_trace"][1].update(lambda_before=1.0))
        self._reject(self.adaptive, lambda row: row["generation_trace"][0].update(reset_event=True))

    def test_lexicographic_or_full_score_feedback_cannot_masquerade_as_scalar_search(self):
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(parent_fitness_before=[0.5, -0.5]))
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(parent_fitness_after=[0.7, 0.0]))
        self._reject(self.fixed, lambda row: row["terminal_state"].update(parent_active_wba=0.7))

    def test_whole_generations_and_mutation_strength_are_checked(self):
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(objective_calls=1))
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(calls_after=51))
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(offspring_count=2))
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(mutation_strength=41))
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(
            mutation_strength=(row["generation_trace"][0]["mutation_strength"]+1)%41))
        self._reject(self.fixed, lambda row: row["generation_trace"].pop())
        self._reject(self.chc, lambda row: row["generation_trace"][0].update(completed_generations=9))

    def test_selected_mutant_reuse_and_nonparent_duplicate_multiplicity_are_checked(self):
        self._reject(self.fixed, lambda row: row["generation_trace"][0]["selection"].update(selected_mutant_index=1))
        self._reject(self.fixed, lambda row: row["generation_trace"][0]["selection"].update(selected_mutant=[0]*40))
        self._reject(self.fixed, lambda row: row["generation_trace"][0]["selection"].update(eligible_count=99))
        self._reject(self.fixed, lambda row: row["generation_trace"][0]["selection"].update(candidate_phase="parent"))
        self._reject(self.fixed, lambda row: row["generation_trace"][0].update(crossover_probability=0.5))

    def test_checkpoint_scope_and_persistent_cache_are_checked(self):
        self._reject(self.fixed, lambda row: row["checkpoints"][0]["candidate_visits"].append(
            copy.deepcopy(row["checkpoints"][0]["candidate_visits"][0])))
        self._reject(self.chc, lambda row: row["checkpoints"][0]["candidate_visits"].pop())
        self._reject(self.chc, lambda row: row["checkpoints"][0]["candidate_visits"][0].update(cache_hit=True))
        self._reject(self.chc, lambda row: row["checkpoints"][1]["candidate_visits"][0].update(cache_hit=False))
        self._reject(self.fixed, lambda row: row["full_evaluations"].append(copy.deepcopy(row["full_evaluations"][0])))
        self._reject(self.fixed, lambda row: row["full_evaluations"][0].update(chunk=0))

    def test_full_tie_break_no_change_and_natural_stop_priority_are_checked(self):
        self._reject(self.chc, lambda row: row.update(selected_mask=row["full_evaluations"][0]["mask"]))
        self._reject(self.fixed, lambda row: row["checkpoints"][1].update(no_change=0))
        self._reject(self.fixed, lambda row: row["terminal_state"].update(outer_stop_reason="censored_safety_cap"))
        early_cap = _run(max_chunks=2)
        with self.assertRaisesRegex(ValueError, "20-chunk cap"):
            validate_search(early_cap, _initial(), [0.5]*50)

    def test_first_whole_stagnation_snapshot_is_not_a_selected_generation(self):
        self._reject(self.fixed, lambda row: row["snapshot"].update(chunk=2))
        self._reject(self.fixed, lambda row: row["snapshot"].update(generation=1))
        self._reject(self.fixed, lambda row: row["snapshot"].update(reason="stagnation_not_observed"))

    def test_zero_full_scores_preserve_explicit_no_winner(self):
        trace = _run(full_objective=lambda _mask: 0.0)
        validate_search(trace, _initial(), [0.5]*50)
        self._reject(trace, lambda row: row.update(selected_mask=list(_initial()[0])))

    def test_malformed_and_nonfinite_evidence_raise_value_error(self):
        self._reject(self.fixed, lambda row: row.pop("terminal_state"))
        self._reject(self.fixed, lambda row: row["active_trace"][0].update(wba=float("nan")))
        self._reject(self.fixed, lambda row: row["active_trace"][0].update(mask=[True]+[0]*39))
        self._reject(self.fixed, lambda row: row.update(seed=44031))


class DiagnosticEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "mask": list(_initial()[0]), "active_wba": 0.5, "chunk": 1,
            "generation": 10, "whole_chunk_generations": 10,
            "best_active_before": 0.5, "best_active_after": 0.5,
            "reason": "first_whole_chunk_without_active_gain",
        }

    def _diag(self, approximate, full):
        return certify_snapshot(snapshot=self.snapshot, active_objective=approximate, full_objective=full)

    def _reject(self, diag, mutate):
        changed = copy.deepcopy(diag)
        mutate(changed)
        with self.assertRaises(ValueError):
            validate_diagnostic(changed, self.snapshot)

    def test_all_four_local_classifications_and_strict_plateau_distinction_pass(self):
        center = tuple(self.snapshot["mask"])
        nonlocal_score = lambda mask: 0.5 if mask == center else 0.6
        strict = lambda mask: 0.5 if mask == center else 0.4
        plateau = lambda _mask: 0.5
        cases = [
            (nonlocal_score, nonlocal_score, "neither_local"),
            (plateau, nonlocal_score, "approximate_only_false_local"),
            (strict, plateau, "both_local"),
            (nonlocal_score, strict, "full_only_local"),
        ]
        for approximate, full, classification in cases:
            with self.subTest(classification=classification):
                diag = self._diag(approximate, full)
                self.assertEqual(diag["classification"], classification)
                validate_diagnostic(diag, self.snapshot)

    def test_center_reevaluation_and_all_ordered_neighbors_are_required(self):
        diag = self._diag(lambda _mask: 0.5, lambda _mask: 0.5)
        self._reject(diag, lambda row: row["approximate"]["evaluations"].pop())
        self._reject(diag, lambda row: row["approximate"]["evaluations"][1].update(bit=1))
        self._reject(diag, lambda row: row["full"]["evaluations"][2].update(mask=row["center_mask"]))
        self._reject(diag, lambda row: row.update(independent_center_reevaluation=False))
        self._reject(diag, lambda row: row["approximate"].update(center_wba=0.6))

    def test_relations_counts_and_global_claims_are_reconstructed(self):
        diag = self._diag(lambda _mask: 0.5, lambda _mask: 0.5)
        self._reject(diag, lambda row: row["approximate"].update(strict_local_maximum=True))
        self._reject(diag, lambda row: row["full"].update(higher_neighbors=1))
        self._reject(diag, lambda row: row["full"]["evaluations"][1].update(relation="higher"))
        self._reject(diag, lambda row: row["full"]["evaluations"][1].update(difference_from_center=0.01))
        self._reject(diag, lambda row: row.update(classification="neither_local"))
        self._reject(diag, lambda row: row["full"].update(global_optimality="proven"))
        self._reject(diag, lambda row: row["full"].update(numerical_tolerance=0.001))
        self._reject(diag, lambda row: row.update(feed_back_to_search=True))

    def test_malformed_certificate_and_wrong_call_counts_fail_closed(self):
        diag = self._diag(lambda _mask: 0.5, lambda _mask: 0.5)
        self._reject(diag, lambda row: row.pop("full"))
        self._reject(diag, lambda row: row.update(objective_calls=80))
        self._reject(diag, lambda row: row["full"]["evaluations"][1].update(wba=float("inf")))


if __name__ == "__main__":
    unittest.main()

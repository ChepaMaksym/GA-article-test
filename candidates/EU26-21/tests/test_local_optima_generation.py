"""CI-only mechanical checks, not independent scientific replications."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from local_optima import generation  # noqa: E402


class ControlledRng:
    """Two different tied mutants; a second mutant selection would choose last.

    Crossover uniforms are all one, so every crossover returns the parent.
    The second *final* selection therefore has only the chosen mutant available.
    """

    def __init__(self, strength: int = 1) -> None:
        self.strength = strength
        self.position_draws = 0
        self.selection_options: list[tuple[int, ...]] = []
        self.events: list[str] = []

    def binomial(self, _n, _p):
        self.events.append("binomial")
        return self.strength

    def choice(self, values, size=None, replace=True):
        self.events.append("choice")
        if size is not None:
            if replace or size != 1:
                raise AssertionError("controlled mutation must flip one distinct bit")
            position = self.position_draws % int(values)
            self.position_draws += 1
            return np.asarray([position])
        options = tuple(int(value) for value in values)
        self.selection_options.append(options)
        return options[0] if len(self.selection_options) == 1 else options[-1]

    def random(self, count):
        self.events.append("random")
        return np.ones(count)


def _generation_arguments(rng):
    return {
        "parent": (0, 0, 0, 0), "parent_fitness": 0,
        "lambda_real": 2.0, "update_factor": 1.5, "reset": False,
        "rng": rng, "call_offset": 10,
    }


def _selection_arguments(rng):
    return {
        "parent": (0, 0, 0, 0), "parent_fitness": 0,
        "mutants": [(1, 0, 0, 0), (0, 1, 0, 0)],
        "mutant_fitness": [1, 1], "selected_mutant_index": 0,
        "crossovers": [(0, 0, 0, 0)] * 2, "crossover_fitness": [0, 0],
        "rng": rng,
    }


class GenerationTests(unittest.TestCase):
    def test_tied_mutant_is_selected_once_and_used_for_both_roles(self):
        rng = ControlledRng()
        with (
            patch.object(generation, "make_crossovers", wraps=generation.make_crossovers) as cross,
            patch.object(
                generation, "select_from_chosen_mutant",
                wraps=generation.select_from_chosen_mutant,
            ) as select,
        ):
            result = generation.run_generation(sum, **_generation_arguments(rng))
        first, second = (1, 0, 0, 0), (0, 1, 0, 0)
        self.assertEqual(select.call_args.kwargs["mutants"], [first, second])
        self.assertEqual(select.call_args.kwargs["mutant_fitness"], [(1.0, 0.0)] * 2)
        self.assertEqual(select.call_args.kwargs["selected_mutant_index"], 0)
        self.assertEqual(cross.call_args.args[1], first)
        self.assertEqual(result.selection.selected_mutant, first)
        self.assertEqual(result.selection.candidate, first)
        self.assertEqual(result.selection.eligible_count, 1)
        # Legacy redraw would produce [(0, 1), (0, 1), (0,)] and select second.
        self.assertEqual(rng.selection_options, [(0, 1), (0,)])
        self.assertNotEqual(result.parent_after, second)

    def test_ledger_order_first_query_and_acceptance_are_distinct(self):
        objective = Mock(side_effect=sum)
        result = generation.run_generation(objective, **_generation_arguments(ControlledRng()))
        self.assertEqual(objective.call_count, 4)
        self.assertEqual(result.objective_calls, 4)
        self.assertEqual(result.calls_after, 14)
        self.assertEqual([row.call for row in result.evaluations], [11, 12, 13, 14])
        self.assertEqual([row.phase for row in result.evaluations], ["mutation"] * 2 + ["crossover"] * 2)
        self.assertEqual([row.phase_index for row in result.evaluations], [0, 1, 0, 1])
        self.assertEqual(result.first_strict_improvement_call, 11)
        self.assertEqual(result.accepted_at_call, 14)
        self.assertEqual(result.selection.candidate_phase, "mutation")
        self.assertEqual(result.selection.candidate_phase_index, 0)
        self.assertAlmostEqual(result.lambda_after, 2.0 / 1.5)
        self.assertFalse(result.reset_event)

    def test_neutral_move_does_not_count_as_control_success(self):
        args = _generation_arguments(ControlledRng())
        args["parent_fitness"] = 1
        result = generation.run_generation(lambda _mask: 1, **args)
        self.assertTrue(result.accepted)
        self.assertTrue(result.parent_changed)
        self.assertFalse(result.strict_success)
        self.assertIsNone(result.first_strict_improvement_call)
        self.assertGreater(result.lambda_after, result.lambda_before)

    def test_secondary_component_is_part_of_strict_success(self):
        args = _generation_arguments(ControlledRng())
        args["parent_fitness"] = (1, -0.75)
        result = generation.run_generation(
            lambda mask: (1, -0.25) if any(mask) else (1, -0.75), **args,
        )
        self.assertTrue(result.strict_success)
        self.assertEqual(result.first_strict_improvement_call, 11)
        self.assertEqual(result.parent_fitness_after, (1.0, -0.25))

    def test_worse_candidate_is_not_accepted(self):
        args = _generation_arguments(ControlledRng())
        args["parent_fitness"] = 2
        result = generation.run_generation(lambda mask: 1 if any(mask) else 2, **args)
        self.assertFalse(result.accepted)
        self.assertFalse(result.parent_changed)
        self.assertEqual(result.parent_after, args["parent"])
        self.assertIsNone(result.accepted_at_call)

    def test_zero_strength_duplicates_still_count_as_objective_calls(self):
        # L=0 is reachable at lambda=2, n=4, unlike at the lambda=n cap.
        rng = ControlledRng(strength=0)
        args = _generation_arguments(rng)
        objective = Mock(return_value=0)
        result = generation.run_generation(objective, **args)
        self.assertEqual(objective.call_count, 4)
        self.assertEqual(result.objective_calls, 4)
        self.assertEqual(result.calls_after, 14)
        self.assertEqual(len(result.evaluations), 4)
        self.assertTrue(all(row.mask == args["parent"] for row in result.evaluations))
        self.assertEqual(result.selection.eligible_count, 0)
        self.assertEqual(result.selection.candidate_phase, "parent")
        self.assertIsNone(result.selection.candidate_phase_index)
        self.assertEqual(result.parent_after, args["parent"])
        self.assertFalse(result.parent_changed)
        self.assertIsNone(result.accepted_at_call)
        self.assertIsNone(result.first_strict_improvement_call)
        self.assertFalse(result.reset_event)
        self.assertAlmostEqual(result.lambda_after, 2.0 * 1.5 ** 0.25)
        self.assertEqual(rng.selection_options, [(0, 1)])

    def test_reachable_cap_reset_changes_control_not_selected_parent(self):
        results = []
        for reset in (False, True):
            with self.subTest(reset=reset):
                args = _generation_arguments(np.random.default_rng(29))
                args.update(lambda_real=4.0, reset=reset)
                objective = Mock(return_value=0)
                result = generation.run_generation(objective, **args)
                results.append(result)
                self.assertEqual(result.mutation_strength, 4)
                self.assertEqual(result.mutation_probability, 1.0)
                self.assertTrue(all(row.mask == (1, 1, 1, 1) for row in result.evaluations[:4]))
                self.assertEqual(objective.call_count, 8)
                self.assertEqual(result.objective_calls, 8)
                self.assertEqual(result.calls_after, 18)
                self.assertGreater(result.selection.eligible_count, 0)
                self.assertTrue(result.accepted)
                self.assertFalse(result.strict_success)
                self.assertEqual(result.parent_after, result.selection.candidate)
                self.assertIsNone(result.first_strict_improvement_call)
                self.assertEqual(result.reset_event, reset)
                self.assertEqual(result.lambda_after, 1.0 if reset else 4.0)
        no_reset, reset = results
        self.assertEqual(no_reset.evaluations, reset.evaluations)
        self.assertEqual(no_reset.selection, reset.selection)
        self.assertEqual(no_reset.parent_after, reset.parent_after)
        self.assertEqual(no_reset.parent_fitness_after, reset.parent_fitness_after)

    def test_rounding_controls_and_shared_mutation_strength(self):
        args = _generation_arguments(ControlledRng())
        args["lambda_real"] = 2.5
        result = generation.run_generation(sum, **args)
        self.assertEqual(result.offspring_count, 3)
        self.assertEqual(result.objective_calls, 6)
        self.assertEqual(result.mutation_probability, 0.625)
        self.assertEqual(result.crossover_probability, 0.4)
        self.assertEqual(result.mutation_strength, 1)
        self.assertTrue(all(sum(row.mask) == 1 for row in result.evaluations[:3]))

    def test_deterministic_given_same_rng_and_immutable_result(self):
        first = generation.run_generation(sum, **_generation_arguments(np.random.default_rng(23)))
        second = generation.run_generation(sum, **_generation_arguments(np.random.default_rng(23)))
        self.assertEqual(first, second)
        with self.assertRaises(FrozenInstanceError):
            first.lambda_after = 9.0
        with self.assertRaises(FrozenInstanceError):
            first.evaluations[0].call = 1

    def test_static_invalid_inputs_have_no_objective_or_rng_effects(self):
        invalid = [
            ("parent", (0, True, 0, 0)), ("parent", (0, np.bool_(True), 0, 0)),
            ("parent", (0, 0.5, 0, 0)), ("parent", (0, "1", 0, 0)),
            ("parent", (0, 2)), ("parent", (0,)), ("parent", ()),
            ("parent_fitness", True), ("parent_fitness", (0, np.bool_(False))),
            ("parent_fitness", (0, float("nan"))), ("parent_fitness", float("inf")),
            ("parent_fitness", (0, 0, 0)), ("parent_fitness", "0"),
            ("lambda_real", True), ("lambda_real", np.bool_(True)),
            ("lambda_real", float("nan")), ("lambda_real", float("inf")),
            ("lambda_real", 0.9), ("lambda_real", 5), ("lambda_real", "2"),
            ("update_factor", True), ("update_factor", float("nan")),
            ("update_factor", float("inf")), ("update_factor", 1),
            ("update_factor", "1.5"), ("reset", 1), ("reset", np.bool_(True)),
            ("call_offset", True), ("call_offset", -1), ("call_offset", 1.5),
            ("rng", object()),
        ]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                rng = ControlledRng()
                args = _generation_arguments(rng)
                args[field] = value
                objective = Mock(return_value=0)
                with self.assertRaises((TypeError, ValueError)):
                    generation.run_generation(objective, **args)
                objective.assert_not_called()
                self.assertEqual(rng.events, [])
        rng = ControlledRng()
        with self.assertRaises(TypeError):
            generation.run_generation(None, **_generation_arguments(rng))
        self.assertEqual(rng.events, [])

    def test_invalid_objective_return_is_not_recorded_as_success(self):
        for score in (True, (0, False), float("nan"), (0, float("inf")), (1, 2, 3)):
            with self.subTest(score=score):
                objective = Mock(return_value=score)
                with self.assertRaises((TypeError, ValueError)):
                    generation.run_generation(objective, **_generation_arguments(ControlledRng()))
                self.assertEqual(objective.call_count, 1)


class ChosenMutantSelectionTests(unittest.TestCase):
    def test_explicit_second_tied_mutant_is_not_redrawn(self):
        rng = ControlledRng()
        args = _selection_arguments(rng)
        args["selected_mutant_index"] = 1
        selection = generation.select_from_chosen_mutant(**args)
        self.assertEqual(selection.selected_mutant, (0, 1, 0, 0))
        self.assertEqual(selection.candidate, selection.selected_mutant)
        self.assertEqual(selection.candidate_phase_index, 1)
        self.assertEqual(rng.selection_options, [(0,)])

    def test_duplicate_candidates_remain_distinct_but_parent_copies_do_not(self):
        rng = ControlledRng()
        args = _selection_arguments(rng)
        args["crossovers"] = [(1, 0, 0, 0)] * 2 + [(0, 0, 0, 0)]
        args["crossover_fitness"] = [1, 1, 0]
        selection = generation.select_from_chosen_mutant(**args)
        self.assertEqual(selection.eligible_count, 3)
        self.assertEqual(rng.selection_options, [(0, 1, 2)])

    def test_crossover_can_be_selected_with_its_original_phase_index(self):
        args = _selection_arguments(ControlledRng())
        args["crossovers"] = [(0, 0, 0, 0), (1, 1, 0, 0)]
        args["crossover_fitness"] = [0, 2]
        selection = generation.select_from_chosen_mutant(**args)
        self.assertEqual(selection.candidate, (1, 1, 0, 0))
        self.assertEqual(selection.candidate_phase, "crossover")
        self.assertEqual(selection.candidate_phase_index, 1)

    def test_invalid_indices_masks_alignment_and_scores_fail_before_rng(self):
        invalid = [
            {"selected_mutant_index": True}, {"selected_mutant_index": 0.0},
            {"selected_mutant_index": -1}, {"selected_mutant_index": 2},
            {"selected_mutant_index": 1, "mutant_fitness": [2, 1]},
            {"mutants": []}, {"mutant_fitness": [1]},
            {"crossovers": [(0, 0)] * 2}, {"crossover_fitness": [0]},
            {"mutant_fitness": [True, 1]}, {"crossover_fitness": [0, float("nan")]},
            {"mutants": [(True, 0, 0, 0), (0, 1, 0, 0)]},
            {"parent_fitness": (0, float("inf"))}, {"rng": object()},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                rng = ControlledRng()
                args = _selection_arguments(rng)
                args.update(changes)
                with self.assertRaises((TypeError, ValueError)):
                    generation.select_from_chosen_mutant(**args)
                self.assertEqual(rng.events, [])


if __name__ == "__main__":
    unittest.main()

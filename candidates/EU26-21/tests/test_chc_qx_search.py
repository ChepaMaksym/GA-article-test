"""CI-only checks of scalar state, QX checkpoints, native source and accounting."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chc_qx_alignment_study import search  # noqa: E402


def _initial():
    return [tuple(index % 2 for index in range(40))] * 50


def _arguments(**changes):
    arguments = {
        "arm": "lambda_fixed1_qx", "initial_masks": _initial(),
        "initial_scores": [0.5] * 50, "active_objective": lambda _mask: 0.5,
        "full_objective": lambda _mask: 0.7, "seed": 44001,
    }
    arguments.update(changes)
    return arguments


def _fake_source(*, fail=False):
    from deap import base

    class ScalarFitness(base.Fitness):
        weights = (1.0,)

    class Individual(list):
        def __init__(self, values=()):
            super().__init__(values)
            self.fitness = ScalarFitness()

    calls = []

    def create_toolbox(*_args):
        toolbox = base.Toolbox()
        toolbox.register("evaluate", lambda _individual: (0.5,))
        return toolbox

    def native_chc(_dataset, toolbox, distance, population, *, max_generations, verbose):
        calls.append({
            "python": random.random(), "numpy": float(np.random.random()),
            "distance": distance, "generations": max_generations,
            "fitness_valid": all(ind.fitness.valid for ind in population),
        })
        if fail:
            raise RuntimeError("synthetic source failure")
        child = copy.deepcopy(population[0])
        child[0] = 1 - child[0]
        child.fitness.values = toolbox.evaluate(child)
        return None, [child] + population[1:], distance

    return SimpleNamespace(create_toolbox=create_toolbox, CHC=native_chc), SimpleNamespace(Individual=Individual), calls


class ImprovingRng:
    """CI tape that flips successive zero bits while lambda stays at one."""

    def __init__(self):
        self.position = 0

    def binomial(self, _dimension, _probability):
        return 1

    def choice(self, values, size=None, replace=True):
        if size is None:
            return values[0]
        if size != 1 or replace:
            raise AssertionError("this tape requires one distinct flipped bit")
        result = np.asarray([self.position], dtype=int)
        self.position += 1
        return result

    def random(self, count):
        return np.zeros(count)

    @property
    def bit_generator(self):
        return SimpleNamespace(state={"position": self.position})


class StatefulSearchTests(unittest.TestCase):
    def test_initial_scores_are_replayed_not_recomputed_and_duplicates_are_charged(self):
        active = Mock(return_value=0.5)
        full = Mock(return_value=0.7)
        result = search.run_qx_search(**_arguments(active_objective=active, full_objective=full))
        self.assertEqual(result["chunks"], 3)
        self.assertEqual(result["active_logical_calls"], 110)
        self.assertEqual(result["active_physical_calls"], 60)
        self.assertEqual(active.call_count, 60)
        self.assertEqual(full.call_count, result["full_calls"])
        self.assertEqual(result["checkpoint_visits"], 3)
        self.assertEqual(result["stop_reason"], "full_no_change")
        self.assertEqual(result["status"], "evaluable")
        self.assertEqual([row["call"] for row in result["active_trace"]], list(range(1, 111)))
        self.assertTrue(all(not row["physical"] for row in result["active_trace"][:50]))
        self.assertTrue(all(row["physical"] for row in result["active_trace"][50:]))
        self.assertTrue(any(row["mask"] == result["active_trace"][0]["mask"]
                            for row in result["active_trace"][1:50]))
        json.dumps(result, allow_nan=False)

    def test_neutral_fitness_and_feature_changes_do_not_trigger_lambda_success(self):
        result = search.run_qx_search(**_arguments(arm="lambda_adaptive_qx"))
        self.assertTrue(all(not row["strict_success"] for row in result["generation_trace"]))
        self.assertTrue(all(row["parent_fitness_before"][1] == 0.0
                            and row["parent_fitness_after"][1] == 0.0
                            for row in result["generation_trace"]))
        self.assertGreater(result["terminal_state"]["final_lambda"], 1.0)
        self.assertTrue(any(row["parent_changed"] for row in result["generation_trace"]))
        self.assertEqual(result["snapshot"]["chunk"], 1)
        self.assertEqual(result["snapshot"]["reason"], "first_whole_chunk_without_active_gain")

    def test_fixed_applied_update_is_not_its_hypothetical_adaptive_proposal(self):
        result = search.run_qx_search(**_arguments())
        self.assertTrue(all(row["lambda_before"] == 1.0 and row["lambda_after"] == 1.0
                            and row["applied_lambda_after"] == 1.0
                            for row in result["generation_trace"]))
        self.assertTrue(all(row["proposed_lambda_after"] > 1.0
                            for row in result["generation_trace"]))
        self.assertEqual(result["terminal_state"]["final_lambda"], 1.0)

    def test_search_state_is_invariant_to_chunk_partition_without_checkpoint_feedback(self):
        for arm in ("lambda_adaptive_qx", "lambda_fixed1_qx"):
            with self.subTest(arm=arm):
                first = search.run_qx_search(**_arguments(
                    arm=arm, chunk_generations=10, max_chunks=2, no_change_limit=100,
                ))
                second = search.run_qx_search(**_arguments(
                    arm=arm, chunk_generations=5, max_chunks=4, no_change_limit=100,
                ))
                self.assertEqual(first["terminal_state"]["parent_mask"], second["terminal_state"]["parent_mask"])
                self.assertEqual(first["terminal_state"]["final_lambda"], second["terminal_state"]["final_lambda"])
                self.assertEqual(first["terminal_state"]["rng_state"], second["terminal_state"]["rng_state"])
                self.assertEqual([(row["mask"], row["wba"], row["phase"]) for row in first["active_trace"]],
                                 [(row["mask"], row["wba"], row["phase"]) for row in second["active_trace"]])

    def test_completed_chunk_progress_is_json_safe_and_does_not_change_search(self):
        for arm in search.ARMS:
            for maximum in (2, 3):
                with self.subTest(arm=arm, max_chunks=maximum):
                    source_args = {}
                    if arm == "chc_qx":
                        evolution, creator, _calls = _fake_source()
                        source_args = {"evolution": evolution, "deap_creator": creator}
                    expected = search.run_qx_search(**_arguments(
                        arm=arm, max_chunks=maximum, **source_args,
                    ))
                    progress_rows = []

                    def save_progress(progress):
                        progress_rows.append(json.loads(json.dumps(progress, allow_nan=False)))
                        # The detached callback payload must not change the incumbent.
                        if progress["selected_mask"] is not None:
                            progress["selected_mask"][0] = 9
                        progress["best_full_wba"] = -1.0

                    actual = search.run_qx_search(**_arguments(
                        arm=arm, max_chunks=maximum,
                        on_chunk_completed=save_progress, **source_args,
                    ))
                    self.assertEqual(actual, expected)
                    self.assertEqual(len(progress_rows), actual["chunks"])
                    for progress, checkpoint in zip(progress_rows, actual["checkpoints"]):
                        self.assertEqual(progress["chunk"], checkpoint["chunk"])
                        self.assertEqual(progress["generation"], checkpoint["generation"])
                        for name in ("active_logical_calls", "active_physical_calls",
                                     "full_calls", "checkpoint_visits", "no_change"):
                            self.assertEqual(progress[name], checkpoint[name])
                        self.assertEqual(progress["best_active_wba"], checkpoint["best_active"])
                        self.assertEqual(progress["best_full_wba"], checkpoint["best_full"])
                    self.assertTrue(all(row["stop_reason"] is None for row in progress_rows[:-1]))
                    self.assertEqual(progress_rows[-1]["stop_reason"], actual["stop_reason"])
                    self.assertEqual(progress_rows[-1]["censored"], maximum == 2)
                    self.assertEqual(progress_rows[-1]["current_lambda"],
                                     actual["terminal_state"]["final_lambda"])

    def test_full_fitness_does_not_replace_active_parent_score(self):
        result = search.run_qx_search(**_arguments(full_objective=lambda _mask: 0.9))
        self.assertEqual(result["full_validation_wba"], 0.9)
        self.assertEqual(result["terminal_state"]["parent_active_wba"], 0.5)
        self.assertTrue(all(row["parent_fitness_before"][0] == 0.5
                            for row in result["generation_trace"]))

    def test_initial_parent_tie_uses_rng_not_feature_count(self):
        initial = [(1,) * 40 if index % 2 == 0 else (1,) + (0,) * 39 for index in range(50)]
        rng = np.random.default_rng(44001 + search.SEARCH_SEED_OFFSET)
        expected = int(rng.choice(np.arange(50, dtype=int)))
        result = search.run_qx_search(**_arguments(initial_masks=initial))
        self.assertEqual(result["terminal_state"]["initial_parent_index"], expected)
        self.assertEqual(result["generation_trace"][0]["parent_before"], list(initial[expected]))

    def test_natural_stop_has_priority_over_safety_cap(self):
        result = search.run_qx_search(**_arguments(max_chunks=3))
        self.assertEqual(result["chunks"], 3)
        self.assertEqual(result["stop_reason"], "full_no_change")
        capped = search.run_qx_search(**_arguments(max_chunks=2))
        self.assertEqual(capped["chunks"], 2)
        self.assertEqual(capped["terminal_state"]["generation_count"], 20)
        self.assertEqual(capped["stop_reason"], "censored_safety_cap")
        self.assertEqual(capped["terminal_state"]["no_change"], 1)

    def test_no_positive_full_winner_remains_explicit_without_invented_mask(self):
        result = search.run_qx_search(**_arguments(full_objective=lambda _mask: 0.0))
        self.assertEqual(result["chunks"], 2)
        self.assertEqual(result["status"], "no_full_winner")
        self.assertEqual(result["stop_reason"], "no_full_winner")
        self.assertEqual(result["terminal_state"]["outer_stop_reason"], "full_no_change")
        self.assertIsNone(result["selected_mask"])
        self.assertIsNone(result["full_validation_wba"])
        self.assertIsNotNone(result["snapshot"])

    def test_terminal_snapshot_is_labeled_when_no_complete_no_gain_chunk_occurs(self):
        with patch.object(search.np.random, "default_rng", return_value=ImprovingRng()):
            result = search.run_qx_search(**_arguments(
                initial_masks=[(0,) * 40] * 50,
                active_objective=lambda mask: 0.5 + sum(mask) / 100,
                max_chunks=2,
            ))
        self.assertEqual(result["snapshot"]["reason"], "stagnation_not_observed")
        self.assertEqual(result["snapshot"]["chunk"], 2)
        self.assertEqual(result["snapshot"]["generation"], 20)
        self.assertGreater(result["snapshot"]["best_active_after"], result["snapshot"]["best_active_before"])
        self.assertEqual(result["snapshot"]["mask"], result["terminal_state"]["parent_mask"])

    def test_scalar_api_rejects_lexicographic_fitness_and_invalid_initialization(self):
        invalid = [
            {"arm": "unknown"}, {"seed": True}, {"chunk_generations": 0},
            {"initial_scores": [(0.5, -0.5)] * 50}, {"initial_scores": [float("nan")] * 50},
            {"initial_masks": [(True,) + (0,) * 39] * 50}, {"initial_masks": [(0,) * 39] * 50},
            {"initial_scores": [0.5] * 49}, {"max_chunks": 0}, {"on_chunk_completed": 0},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                active, full = Mock(return_value=0.5), Mock(return_value=0.7)
                with self.assertRaises((TypeError, ValueError)):
                    search.run_qx_search(**_arguments(active_objective=active, full_objective=full, **changes))
                active.assert_not_called()
                full.assert_not_called()
        with self.assertRaises(TypeError):
            search.run_qx_search(**_arguments(active_objective=lambda _mask: (0.5, -0.2)))

    def test_duplicate_initial_masks_require_consistent_scores(self):
        with self.assertRaises(ValueError):
            search.run_qx_search(**_arguments(initial_scores=[0.4] + [0.5] * 49))


class SourceChunkAdapterTests(unittest.TestCase):
    def test_source_calls_use_valid_shared_initial_fitness_and_full_population_checkpoints(self):
        evolution, creator, calls = _fake_source()
        full = Mock(return_value=0.7)
        result = search.run_qx_search(**_arguments(
            arm="chc_qx", evolution=evolution, deap_creator=creator, full_objective=full,
        ))
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(call["fitness_valid"] and call["generations"] == 10 for call in calls))
        self.assertEqual(result["active_physical_calls"], 3)
        self.assertEqual(result["active_logical_calls"], 53)
        self.assertEqual(result["checkpoint_visits"], 150)
        self.assertEqual(result["full_calls"], 2)
        self.assertEqual(full.call_count, 2)
        self.assertEqual([checkpoint["new_full_calls"] for checkpoint in result["checkpoints"]], [2, 0, 0])
        self.assertEqual(result["snapshot"]["mask"], result["checkpoints"][0]["candidate_visits"][0]["mask"])
        self.assertEqual(result["snapshot"]["reason"], "first_whole_chunk_without_active_gain")
        # First child has one more bit than the initial alternating mask. The
        # equal full score selects the smaller initial mask but does not reset
        # the outer no-change counter at later checkpoints.
        self.assertEqual(result["selected_mask"], list(_initial()[0]))
        self.assertEqual(result["terminal_state"]["no_change"], 2)

    def test_same_feature_full_tie_keeps_earliest_full_query_even_on_later_cache_visit(self):
        evolution, creator, _ = _fake_source()

        def swap_chunk(_dataset, toolbox, distance, population, **_kwargs):
            child = copy.deepcopy(population[0])
            child[0], child[1] = child[1], child[0]
            child.fitness.values = toolbox.evaluate(child)
            return None, [child] + population[1:], distance

        evolution.CHC = swap_chunk
        result = search.run_qx_search(**_arguments(arm="chc_qx", evolution=evolution, deap_creator=creator))
        self.assertEqual(result["full_calls"], 2)
        self.assertEqual(result["selected_mask"], result["full_evaluations"][0]["mask"])
        self.assertEqual(result["terminal_state"]["selected_full_call"], 1)
        self.assertEqual(sum(result["full_evaluations"][0]["mask"]), sum(result["full_evaluations"][1]["mask"]))
        self.assertEqual(result["terminal_state"]["no_change"], 2)

    def test_native_python_and_numpy_rng_continue_and_external_states_are_restored(self):
        python_before, numpy_before = random.getstate(), np.random.get_state()
        evolution, creator, calls = _fake_source()
        result = search.run_qx_search(**_arguments(arm="chc_qx", evolution=evolution, deap_creator=creator))
        self.assertEqual(random.getstate(), python_before)
        numpy_after = np.random.get_state()
        self.assertEqual(numpy_after[0], numpy_before[0])
        np.testing.assert_array_equal(numpy_after[1], numpy_before[1])
        self.assertEqual(numpy_after[2:], numpy_before[2:])
        py_rng = random.Random(44001 + search.SEARCH_SEED_OFFSET)
        np_rng = np.random.RandomState(44001 + search.SEARCH_SEED_OFFSET)
        self.assertEqual([row["python"] for row in calls], [py_rng.random() for _ in calls])
        self.assertEqual([row["numpy"] for row in calls], [float(np_rng.random_sample()) for _ in calls])
        self.assertEqual(result["terminal_state"]["generation_count"], 30)
        json.dumps(result, allow_nan=False)

    def test_source_error_restores_both_external_random_states(self):
        python_before, numpy_before = random.getstate(), np.random.get_state()
        evolution, creator, _ = _fake_source(fail=True)
        with self.assertRaisesRegex(RuntimeError, "synthetic source failure"):
            search.run_qx_search(**_arguments(arm="chc_qx", evolution=evolution, deap_creator=creator))
        self.assertEqual(random.getstate(), python_before)
        numpy_after = np.random.get_state()
        np.testing.assert_array_equal(numpy_after[1], numpy_before[1])
        self.assertEqual(numpy_after[2:], numpy_before[2:])


class PinnedNativeSourceTests(unittest.TestCase):
    def test_actual_source_chc_chunks_and_scalar_population_are_used(self):
        configured = os.environ.get("EU26_21_UPSTREAM")
        if not configured:
            self.skipTest("CI must provide the pinned source checkout")
        source = Path(configured) / "code"
        sys.path.insert(0, str(source))
        try:
            from Evolution import Evolution
            from deap import creator
            active = Mock(return_value=0.5)
            result = search.run_qx_search(**_arguments(
                arm="chc_qx", evolution=Evolution, deap_creator=creator,
                active_objective=active,
            ))
        finally:
            sys.path.remove(str(source))
        self.assertEqual(result["chunks"], 3)
        self.assertEqual(result["checkpoint_visits"], 150)
        self.assertEqual(result["active_physical_calls"], active.call_count)
        self.assertEqual(result["active_logical_calls"], 50 + active.call_count)
        self.assertEqual(len(result["terminal_state"]["population"]), 50)
        self.assertEqual(result["terminal_state"]["generation_count"], 30)
        self.assertTrue(all(row["active_wba"] == 0.5 for row in result["terminal_state"]["population"]))


if __name__ == "__main__":
    unittest.main()

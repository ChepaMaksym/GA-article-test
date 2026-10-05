"""Source-QX reference tests. Execute only in the authenticated CI workflows."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chc_qx_alignment_study.reference import source_compatible_qx
from chc_qx_alignment_study.source_gate import (
    ClockTape, authenticate, fixture_gate, load_evolution, run_fixture,
)


class _Individual(list):
    def __init__(self, mask, score):
        super().__init__(mask)
        self.fitness = SimpleNamespace(valid=True, values=(score,))


class _TinyEvolution:
    """Controller-only fixture: repeated checkpoints must use persistent cache."""

    def __init__(self):
        self.events = []
        self.population = [_Individual([1, 0], 0.9), _Individual([0, 1], 0.8)]

    def select_instances(self, q, baseline):
        self.events.append(("select_instances", q))
        return [1], [SimpleNamespace(features=[0], ValidationAccuracy=0.999)]

    def create_toolbox(self, *arguments):
        return SimpleNamespace()

    def create_population(self, size, dimension):
        self.events.append(("create_population", size, dimension))
        return self.population

    def CHC(self, dataset, toolbox, d, population, *, max_generations, verbose):
        self.events.append(("CHC", max_generations, tuple(dataset.instances)))
        return None, population, d

    def evaluate(self, individual, task, target, baseline):
        self.events.append(("full_evaluate", tuple(individual)))
        return (0.6 if individual[0] else 0.7,)


class _Baseline:
    X_train = SimpleNamespace(shape=(4, 2))
    instances = [0, 1, 2, 3]

    def set_instances(self, selected):
        self.instances = list(selected)


class ControllerReferenceTests(unittest.TestCase):
    def _tiny(self):
        engine = _TinyEvolution()
        clock = ClockTape()
        with redirect_stdout(io.StringIO()):
            log, models = source_compatible_qx(engine, _Baseline(), population_size=2, clock=clock.time)
        return engine, log, models

    def test_no_initial_full_checkpoint_or_q_control_winner(self):
        engine, log, _ = self._tiny()
        full_calls = [event for event in engine.events if event[0] == "full_evaluate"]
        first_full = next(index for index, event in enumerate(engine.events) if event[0] == "full_evaluate")
        first_chunk = next(index for index, event in enumerate(engine.events) if event[0] == "CHC")
        self.assertGreater(first_full, first_chunk)
        self.assertEqual(full_calls, [("full_evaluate", (1, 0)), ("full_evaluate", (0, 1))])
        self.assertEqual(float(log.iloc[-1]["fitness"]), 0.7)

    def test_full_checkpoint_cache_survives_three_native_chunks(self):
        engine, _, _ = self._tiny()
        chunks = [event for event in engine.events if event[0] == "CHC"]
        self.assertEqual(chunks, [("CHC", 10, (1,))]*3)
        self.assertEqual(len([event for event in engine.events if event[0] == "full_evaluate"]), 2)

    def test_full_scores_never_overwrite_approximate_individual_fitness(self):
        engine, _, _ = self._tiny()
        self.assertEqual([ind.fitness.values for ind in engine.population], [(0.9,), (0.8,)])

    def test_zero_full_scores_keep_the_source_empty_improvement_log(self):
        engine = _TinyEvolution()
        engine.evaluate = lambda *arguments: (0.0,)
        with redirect_stdout(io.StringIO()):
            log, _ = source_compatible_qx(engine, _Baseline(), population_size=2, clock=ClockTape().time)
        self.assertTrue(log.empty)
        self.assertEqual(len([event for event in engine.events if event[0] == "CHC"]), 2)

    def test_source_gate_refuses_non_ci_execution_before_git_or_io(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), patch(
            "chc_qx_alignment_study.source_gate._git"
        ) as git:
            with self.assertRaisesRegex(ValueError, "CI-only"):
                authenticate(Path("unused"), "0"*40)
            git.assert_not_called()

    def test_clock_replay_requires_all_and_only_recorded_reads(self):
        tape = ClockTape()
        expected = tape.time()
        replay = ClockTape(tape.tape)
        self.assertEqual(replay.time(), expected)
        replay.complete()
        with self.assertRaisesRegex(ValueError, "exhausted"):
            replay.time()
        with self.assertRaisesRegex(ValueError, "complete tape"):
            ClockTape(tape.tape).complete()


class PinnedSourceControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get("EU26_21_UPSTREAM")
        if not value:
            raise unittest.SkipTest("pinned upstream required: EU26_21_UPSTREAM")
        cls.upstream = Path(value).resolve()
        cls.module = load_evolution(cls.upstream)

    def test_complete_native_qx_and_wrapper_fixed_clock_tape_equivalence(self):
        report = fixture_gate(self.upstream)
        self.assertEqual(report["status"], "PASS_SOURCE_CONTROLLER_EQUIVALENCE")
        self.assertEqual(len(report["cases"]), 3)
        self.assertTrue(all(case["native_chunks"] >= 3 for case in report["cases"][:2]))

    def test_fixture_restores_source_methods_and_rng_states(self):
        engine = self.module.Evolution
        methods = [engine.CHC, engine.evaluate, engine.select_instances]
        before_python, before_numpy = random.getstate(), np.random.get_state()
        original_time = self.module.time
        run_fixture(self.module, wrapped=False)
        self.assertEqual([engine.CHC, engine.evaluate, engine.select_instances], methods)
        self.assertIs(self.module.time, original_time)
        self.assertEqual(random.getstate(), before_python)
        after_numpy = np.random.get_state()
        self.assertEqual(before_numpy[0], after_numpy[0])
        np.testing.assert_array_equal(before_numpy[1], after_numpy[1])
        self.assertEqual(before_numpy[2:], after_numpy[2:])

    def test_degenerate_spearman_failure_is_not_replaced_by_fallback(self):
        reference = run_fixture(self.module, wrapped=False, constant=True)
        actual = run_fixture(self.module, wrapped=True, constant=True, tape=reference["clock_tape"])
        self.assertEqual(actual, reference)
        self.assertEqual(reference["error"]["type"], "UnboundLocalError")
        self.assertIsNone(reference["selected_rows"])
        self.assertEqual(reference["chunks"], [])


if __name__ == "__main__":
    unittest.main()

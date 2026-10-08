"""Small deterministic mechanism fixtures; scientific execution is CI-only."""

from copy import deepcopy
import unittest

import numpy as np

from studies.knapsack_parameters.feasibility.data_audit import Instance
from studies.knapsack_parameters.ga_study import engine
from studies.knapsack_parameters.ga_study.oracle import verify_search


def fixture(profits=(10, 8, 8), weights=(6, 5, 5), capacity=10):
    return Instance(len(profits), capacity, tuple(profits), tuple(weights),
                    "teaching.kp", "UC", "s000", 0)


def execute(instance, config, masks, budget=50, seed=51001):
    bits = np.asarray(masks, dtype=np.uint8)
    scores = engine.evaluate_masks(instance, bits)
    return engine.run_search(instance, config, bits, scores,
                             engine.make_rngs(0, 0, seed), budget=budget)


class EngineTests(unittest.TestCase):
    def test_grid_order_and_single_baseline(self):
        grid = engine.configurations()
        self.assertEqual(len(grid), 27)
        self.assertEqual(len({c.configuration_id for c in grid}), 27)
        self.assertEqual([(c.mutation_numerator, c.crossover_probability, c.population_size) for c in grid],
            [(m, p, n) for m in (0.5, 1.0, 3.0) for p in (0.0, 0.5, 0.9) for n in (10, 30, 50)])
        self.assertEqual(sum(c == engine.Config(1.0, 0.9, 30) for c in grid), 1)
        self.assertEqual(engine.configuration_id(grid[0]), grid[0].configuration_id)

    def test_exact_objective_original_bit_order_and_feasibility(self):
        value = engine.evaluate_masks(fixture(), np.asarray([[1, 0, 0], [0, 1, 1], [1, 1, 1], [0, 0, 0]], dtype=np.uint8))
        self.assertEqual(value["weight"].tolist(), [6, 10, 16, 0])
        self.assertEqual(value["profit"].tolist(), [10, 16, 26, 0])
        self.assertEqual(value["feasible"].tolist(), [True, True, False, True])
        self.assertEqual(value["weight"].dtype, np.dtype("int64"))

    def test_objective_validation_and_overflow_guards(self):
        for masks in ([[1, 2, 0]], [[1, 0]], [1, 0, 0]):
            with self.assertRaises(ValueError):
                engine.evaluate_masks(fixture(), masks)
        with self.assertRaises(ValueError):
            engine.evaluate_masks(fixture((1 << 64,), (1,), 1), [[1]])
        with self.assertRaises(ValueError):
            engine.evaluate_masks(fixture((1,), (-1,), 1), [[1]])

    def test_preference_feasibility_and_no_infeasible_profit_tiebreak(self):
        self.assertGreater(engine._key(10, 1, 10), engine._key(11, 1000, 10))
        self.assertGreater(engine._key(5, 9, 10), engine._key(6, 8, 10))
        self.assertGreater(engine._key(11, 1, 10), engine._key(12, 1000, 10))
        self.assertEqual(engine._key(11, 1, 10), engine._key(11, 1000, 10))

    def test_isolated_registered_seedsequence_channels(self):
        first, second = engine.make_rngs(2, 7, 51003), engine.make_rngs(2, 7, 51003)
        self.assertEqual(set(first), {"initialization", "selection", "crossover", "mutation", "tie"})
        self.assertEqual(len({id(g) for g in first.values()}), 5)
        for name, channel in engine.CHANNELS.items():
            expected = np.random.Generator(np.random.PCG64(np.random.SeedSequence([2, 7, 51003, channel])))
            self.assertEqual(first[name].bit_generator.state, expected.bit_generator.state)
        prior = deepcopy(first["mutation"].bit_generator.state)
        first["selection"].random(10)
        self.assertEqual(first["mutation"].bit_generator.state, prior)
        self.assertNotEqual(first["selection"].bit_generator.state, second["selection"].bit_generator.state)

    def test_deterministic_complete_trace_and_external_init_copy(self):
        instance, config = fixture(), engine.Config(1.0, 0.9, 3)
        masks = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 1]], dtype=np.uint8)
        scores = engine.evaluate_masks(instance, masks)
        a = engine.run_search(instance, config, masks, scores, engine.make_rngs(0, 0, 51001), budget=39)
        b = engine.run_search(instance, config, masks, scores, engine.make_rngs(0, 0, 51001), budget=39)
        self.assertEqual(a["summary"], b["summary"])
        self.assertEqual(a["generations"], b["generations"])
        for key in a["requests"]:
            np.testing.assert_array_equal(a["requests"][key], b["requests"][key])
        masks[:] = 1
        self.assertEqual(a["requests"]["masks"][0].tolist(), [0, 0, 0])
        self.assertEqual(verify_search(instance, config, a)["status"], "PASS_REPLAY")

    def test_partial_generation_counts_candidates_not_population(self):
        instance, config = fixture((10,), (1,), 1), engine.Config(1.0, 0.0, 3)
        result = execute(instance, config, [[0], [0], [0]], budget=4)
        last = result["generations"][-1]
        self.assertFalse(last["complete"])
        self.assertEqual(last["population_before"], [0, 1, 2])
        self.assertEqual(last["population_after"], [0, 1, 2])
        self.assertEqual(result["summary"]["complete_generations"], 0)
        self.assertTrue(result["summary"]["terminal_partial"])
        self.assertEqual(result["summary"]["best_request"], 4)
        self.assertEqual(result["summary"]["best_mask"], "1")
        verdict = verify_search(instance, config, result, initial_center_profit=0)
        self.assertTrue(verdict["escape_event"])
        self.assertEqual(verdict["first_escape_request"], 4)
        self.assertFalse(verdict["censored"])

    def test_one_elite_and_worse_children_can_persist(self):
        instance, config = fixture((10,), (1,), 1), engine.Config(1.0, 0.0, 3)
        result = execute(instance, config, [[1], [1], [1]], budget=5)
        refs = result["summary"]["terminal_population_requests"]
        self.assertEqual(result["requests"]["masks"][refs].tolist(), [[1], [0], [0]])
        self.assertEqual(result["generations"][-1]["metrics_after"]["mean_feasible_profit"], 10 / 3)
        self.assertEqual(result["summary"]["best_request"], 1)
        self.assertEqual(result["summary"]["physical_evaluations"], 2)
        verify_search(instance, config, result)

    def test_duplicates_invalid_and_no_improvement_do_not_stop(self):
        instance, config = fixture((10,), (3,), 1), engine.Config(0.0, 0.0, 3)
        result = execute(instance, config, [[1], [1], [1]], budget=17)
        self.assertEqual(result["summary"]["logical_requests"], 17)
        self.assertEqual(result["summary"]["physical_evaluations"], 14)
        self.assertEqual(result["summary"]["duplicate_count"], 16)
        self.assertEqual(result["summary"]["invalid_request_count"], 17)
        self.assertIsNone(result["summary"]["best_mask"])
        self.assertIsNone(result["generations"][-1]["metrics_after"]["mean_feasible_profit"])
        verify_search(instance, config, result)

    def test_initial_only_budget_consumes_no_operator_stream(self):
        instance, config = fixture(), engine.Config(1.0, 0.5, 3)
        result = execute(instance, config, [[0, 0, 0], [1, 0, 0], [0, 1, 1]], budget=3)
        self.assertEqual(len(result["generations"]), 1)
        self.assertEqual(result["summary"]["physical_evaluations"], 0)
        self.assertEqual(result["summary"]["rng_states_start"], result["summary"]["rng_states_terminal"])
        verify_search(instance, config, result)

    def test_tied_duplicate_positions_consume_two_position_tie_draw(self):
        instance, config = fixture(), engine.Config(0.0, 0.0, 3)
        masks = np.zeros((3, 3), dtype=np.uint8)
        rngs = engine.make_rngs(0, 0, 51001)
        class AlwaysSameTournament:
            # Scripted mechanism fixture only: force both sampled positions
            # to contain the identical index, while preserving other channels.
            bit_generator = np.random.PCG64(0)
            def integers(self, low, high, size):
                return np.asarray([0, 0], dtype=np.int64)
        rngs["selection"] = AlwaysSameTournament()
        expected = engine.make_rngs(0, 0, 51001)["tie"]
        expected.integers(0, 3)  # One uniform elite tie.
        for _ in range(2):
            expected.integers(0, 2)  # First parent: two drawn positions.
            expected.integers(0, 2)  # Second parent, despite no crossover.
        result = engine.run_search(instance, config, masks, engine.evaluate_masks(instance, masks), rngs, budget=5)
        self.assertEqual(result["summary"]["rng_states_terminal"]["tie"], expected.bit_generator.state)
        self.assertTrue(np.all(result["requests"]["tournaments"][3:] == 0))

    def test_crossover_application_draw_even_at_zero_and_no_choice_draws(self):
        instance = fixture()
        masks = np.zeros((3, 3), dtype=np.uint8)
        for probability in (0.0, 1.0):
            config = engine.Config(0.0, probability, 3)
            result = execute(instance, config, masks, budget=8)
            expected = engine.make_rngs(0, 0, 51001)["crossover"]
            for _ in range(5):
                expected.random()
                if probability == 1.0:
                    expected.random(3)
            self.assertEqual(result["summary"]["rng_states_terminal"]["crossover"], expected.bit_generator.state)
            self.assertTrue(np.all(result["requests"]["crossover_applied"][3:] == bool(probability)))
            if probability == 0.0:
                self.assertFalse(np.any(result["requests"]["crossover_bits"]))
            verify_search(instance, config, result)

    def test_run_rejects_malformed_initial_scores_rng_and_budgets(self):
        instance, config = fixture(), engine.Config(1.0, 0.5, 3)
        masks = np.zeros((3, 3), dtype=np.uint8)
        known = engine.evaluate_masks(instance, masks)
        for budget in (2, True, 3.5):
            with self.assertRaises(ValueError):
                engine.run_search(instance, config, masks, known, engine.make_rngs(0, 0, 51001), budget=budget)
        bad = dict(known)
        bad["feasible"] = ~bad["feasible"]
        with self.assertRaises(ValueError):
            engine.run_search(instance, config, masks, bad, engine.make_rngs(0, 0, 51001))
        bad = dict(known)
        bad["profit"] = bad["profit"].astype(float)
        with self.assertRaises(ValueError):
            engine.run_search(instance, config, masks, bad, engine.make_rngs(0, 0, 51001))
        repeated = engine.make_rngs(0, 0, 51001)
        repeated["tie"] = repeated["mutation"]
        with self.assertRaises(ValueError):
            engine.run_search(instance, config, masks, known, repeated)

    def test_search_signature_has_no_reference_or_escape_threshold(self):
        import inspect
        parameters = set(inspect.signature(engine.run_search).parameters)
        self.assertEqual(parameters, {"instance", "config", "initial_masks", "initial_scores", "rngs", "budget"})


if __name__ == "__main__":
    unittest.main()

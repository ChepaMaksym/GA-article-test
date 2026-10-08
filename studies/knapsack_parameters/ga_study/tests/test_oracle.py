"""Independent replay corruption and endpoint fixtures, run only in CI."""

from copy import deepcopy
import unittest
from unittest.mock import patch

import numpy as np

from studies.knapsack_parameters.feasibility.data_audit import Instance
from studies.knapsack_parameters.ga_study import engine, oracle


def case(n=3):
    return Instance(n, n, tuple(range(1, n + 1)), (1,) * n,
                    "teaching.kp", "UC", "s000", 0)


def make_result(n=3, budget=38, numerator=1.0, crossover=0.9):
    instance, config = case(n), engine.Config(numerator, crossover, 3)
    bits = np.zeros((3, n), dtype=np.uint8)
    scores = engine.evaluate_masks(instance, bits)
    result = engine.run_search(instance, config, bits, scores,
                             engine.make_rngs(0, 0, 51001), budget=budget)
    return instance, config, result


class OracleTests(unittest.TestCase):
    def test_independent_oracle_uses_no_production_evaluator_controller(self):
        instance, config, result = make_result()
        with patch.object(engine, "evaluate_masks", side_effect=AssertionError("production evaluator forbidden")), \
             patch.object(engine, "_key", side_effect=AssertionError("production comparator forbidden")), \
             patch.object(engine, "run_search", side_effect=AssertionError("production controller forbidden")), \
             patch.object(engine, "rng_snapshot", side_effect=AssertionError("production state function forbidden")):
            report = oracle.verify_search(instance, config, result, initial_center_profit=0)
        self.assertEqual(report["status"], "PASS_REPLAY")
        self.assertEqual(report["exact_requests_verified"], 38)
        self.assertTrue(report["rng_and_operator_replay_verified"])

    def test_all_objective_scores_verified_and_not_just_best(self):
        instance, config, original = make_result()
        for key in ("weight", "profit", "feasible"):
            changed = deepcopy(original)
            if key == "feasible":
                changed["requests"][key][5] ^= True
            else:
                changed["requests"][key][5] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                oracle.verify_search(instance, config, changed)

    def test_operator_parent_and_tournament_corruption_rejected(self):
        instance, config, original = make_result()
        for key in ("masks", "parents", "tournaments", "crossover_bits", "mutation_bits"):
            changed = deepcopy(original)
            flattened = changed["requests"][key].reshape(changed["requests"][key].shape[0], -1)
            flattened[4, 0] ^= 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                oracle.verify_search(instance, config, changed)
        changed = deepcopy(original)
        changed["requests"]["crossover_applied"][4] ^= True
        with self.assertRaises(ValueError):
            oracle.verify_search(instance, config, changed)

    def test_rng_full_state_checksum_and_partial_population_verified(self):
        instance, config, original = make_result(budget=4)
        for kind in ("rng", "digest", "elite", "replacement", "metrics", "completion"):
            changed = deepcopy(original)
            event = changed["generations"][-1]
            if kind == "rng":
                event["rng_states"]["tie"]["state"]["state"] += 1
            elif kind == "digest":
                event["rng_state_sha256"] = "0" * 64
            elif kind == "elite":
                event["elite"]["population_index"] = (event["elite"]["population_index"] + 1) % 3
            elif kind == "replacement":
                event["population_after"][1] = 3
            elif kind == "metrics":
                event["metrics_after"]["diversity"] = 0.0
            else:
                event["complete"] = True
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                oracle.verify_search(instance, config, changed)

    def test_corrupted_duplicate_request_generation_and_summary_rejected(self):
        instance, config, original = make_result()
        for key in ("duplicate", "request", "generation", "phase"):
            changed = deepcopy(original)
            changed["requests"][key][4] ^= 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                oracle.verify_search(instance, config, changed)
        for key in ("best_profit", "best_request", "physical_evaluations", "complete_generations"):
            changed = deepcopy(original)
            changed["summary"][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                oracle.verify_search(instance, config, changed)

    def test_missing_generation_arrays_and_object_dtype_fail_closed(self):
        instance, config, original = make_result()
        changed = deepcopy(original)
        changed["generations"].pop()
        with self.assertRaises(ValueError):
            oracle.verify_search(instance, config, changed)
        changed = deepcopy(original)
        changed["requests"]["profit"] = changed["requests"]["profit"][:-1]
        with self.assertRaises(ValueError):
            oracle.verify_search(instance, config, changed)
        changed = deepcopy(original)
        changed["requests"]["profit"] = changed["requests"]["profit"].astype(object)
        with self.assertRaises(ValueError):
            oracle.verify_search(instance, config, changed)

    def test_last_request_event_distinguished_from_right_censoring(self):
        instance, config, result = make_result(n=1, budget=4, numerator=1.0, crossover=0.0)
        report = oracle.verify_search(instance, config, result, initial_center_profit=0)
        self.assertEqual(report["first_escape_request"], 4)
        self.assertEqual(report["escape_time"], 4)
        self.assertTrue(report["escape_event"])
        self.assertFalse(report["censored"])
        instance, config, result = make_result(n=1, budget=4, numerator=0.0, crossover=0.0)
        report = oracle.verify_search(instance, config, result, initial_center_profit=0)
        self.assertIsNone(report["first_escape_request"])
        self.assertEqual(report["escape_time"], 4)
        self.assertFalse(report["escape_event"])
        self.assertTrue(report["censored"])

    def test_initial_provenance_and_center_clones_verified(self):
        instance, config, result = make_result()
        with self.assertRaises(ValueError):
            oracle.verify_search(instance, config, result, initial_masks=np.ones((3, 3), dtype=np.uint8))
        scores = {key: result["requests"][key][:3].copy() for key in ("weight", "profit", "feasible")}
        scores["profit"][0] += 1
        with self.assertRaises(ValueError):
            oracle.verify_search(instance, config, result, initial_scores=scores)
        with self.assertRaises(ValueError):
            oracle.verify_search(instance, config, result, initial_center_profit=1)

    def test_every_grid_configuration_small_fixture_replays(self):
        # No asserted quality improvement; these are deterministic mechanism
        # checks, not a scientific comparison or favorable-seed selection.
        instance = case(5)
        for grid in engine.configurations():
            config = grid
            patterns = [[0] * 5, [1, 0, 1, 0, 0], [0, 1, 0, 0, 1]]
            masks = np.asarray([patterns[i % 3] for i in range(config.population_size)], dtype=np.uint8)
            scores = engine.evaluate_masks(instance, masks)
            result = engine.run_search(instance, config, masks, scores, engine.make_rngs(1, 3, 51009), budget=config.population_size * 3)
            with self.subTest(config=config.configuration_id):
                self.assertEqual(oracle.verify_search(instance, config, result)["status"], "PASS_REPLAY")


if __name__ == "__main__":
    unittest.main()

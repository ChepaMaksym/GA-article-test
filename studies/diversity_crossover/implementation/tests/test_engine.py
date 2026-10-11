"""Registered unit scenarios; execute only in GitHub Actions."""

import copy
import itertools
import os
import unittest
from unittest.mock import patch

import numpy as np

from studies.diversity_crossover.implementation import engine


class EngineTests(unittest.TestCase):
    def _run(self, problem=None, masks=None, method="baseline", budget=12, pc=0.9,
             seed=70001, scores=None):
        problem = problem or {"kind": "onemax", "n": 4}
        masks = masks or ["0000", "1000", "1100", "1110"]
        scores = scores or [engine.evaluate(problem, mask) for mask in masks]
        records = []
        summary = engine.run_search(problem, masks, scores, method,
                                    engine.make_rngs(0, 0, seed), records.append,
                                    budget=budget, pc=pc)
        return records, summary

    def test_ci_only(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            for call in (lambda: engine.evaluate({"kind": "flat", "n": 1}, "0"),
                         lambda: engine.make_rngs(0, 0),
                         lambda: engine.metrics(["0"], [{"key": [1, 0], "value": 0, "weight": None, "feasible": True}])):
                with self.assertRaises(ValueError):
                    call()

    def test_exact_function_values(self):
        self.assertEqual(engine.evaluate({"kind": "flat", "n": 4}, "1111")["value"], 0)
        self.assertEqual(engine.evaluate({"kind": "onemax", "n": 4}, "1011")["value"], 3)
        jump = {"kind": "jump", "n": 6, "k": 2}
        self.assertEqual([engine.evaluate(jump, "1" * i + "0" * (6 - i))["value"]
                          for i in range(7)], [2, 3, 4, 5, 6, 1, 8])

    def test_knapsack_feasibility_order_and_empty(self):
        problem = {"kind": "knapsack", "n": 3, "weights": [6, 5, 5],
                   "profits": [10, 8, 8], "capacity": 10}
        empty, center, best, invalid = [engine.evaluate(problem, mask)
                                         for mask in ("000", "100", "011", "110")]
        self.assertEqual(empty, {"key": [1, 0], "weight": 0, "value": 0, "feasible": True})
        self.assertGreater(tuple(empty["key"]), tuple(invalid["key"]))
        self.assertGreater(tuple(best["key"]), tuple(center["key"]))
        self.assertEqual(invalid["key"], [0, -1])

    def test_rejects_oracle_fields_and_bad_masks(self):
        for name in ("optimal_value", "optimum", "certificate", "neighbors"):
            with self.assertRaises(ValueError):
                engine.evaluate({"kind": "flat", "n": 2, name: None}, "00")
        for mask in ("", "0", "012", "01a", [0, 1, 0]):
            with self.assertRaises(ValueError):
                engine.evaluate({"kind": "onemax", "n": 3}, mask)
        with self.assertRaises(ValueError):
            engine.evaluate({"kind": "knapsack", "n": 1, "weights": [0],
                             "profits": [1], "capacity": 2}, "0")

    def test_rng_channels_seed_formula_and_restoration(self):
        rngs = engine.make_rngs(4, 1, 70001)
        for i, name in enumerate(engine.CHANNELS):
            expected = np.random.Generator(np.random.PCG64(np.random.SeedSequence([70001, 4, 1, i])))
            self.assertEqual(rngs[name].bit_generator.state, expected.bit_generator.state)
        rngs["initialization"].random(17)
        state = copy.deepcopy(rngs["initialization"].bit_generator.state)
        restored = engine.make_rngs(4, 1, initialization_state=state)
        self.assertEqual(restored["initialization"].bit_generator.state, state)
        self.assertEqual(restored["parents"].bit_generator.state,
                         engine.make_rngs(4, 1)["parents"].bit_generator.state)

    def test_rng_alias_is_rejected(self):
        rngs = engine.make_rngs(0, 0)
        rngs["parents"] = rngs["initialization"]
        p = {"kind": "flat", "n": 1}
        with self.assertRaises(ValueError):
            engine.run_search(p, ["0"], [engine.evaluate(p, "0")], "baseline", rngs, lambda _: None)

    def test_metrics_independent_pairwise_calculation(self):
        population = ["0000", "1100", "1111", "1100"]
        scores = [engine.evaluate({"kind": "onemax", "n": 4}, x) for x in population]
        result = engine.metrics(population, scores)
        distance = sum(sum(x != y for x, y in zip(a, b))
                       for a, b in itertools.combinations(population, 2))
        self.assertEqual(result["unique_fraction"], 3 / 4)
        self.assertEqual(result["diversity"], 2 * distance / (4 * 3 * 4))
        self.assertEqual(result["mean_feasible_value"], 2)
        self.assertEqual(result["feasible_fraction"], 1)

    def test_metrics_clones_singleton_and_no_feasible_mean(self):
        p = {"kind": "flat", "n": 2}
        score = engine.evaluate(p, "00")
        self.assertEqual(engine.metrics(["00"] * 30, [score] * 30)["diversity"], 0)
        self.assertEqual(engine.metrics(["00"], [score])["diversity"], 0)
        p = {"kind": "knapsack", "n": 2, "weights": [2, 2], "profits": [1, 1], "capacity": 1}
        result = engine.metrics(["10", "01"], [engine.evaluate(p, m) for m in ("10", "01")])
        self.assertIsNone(result["mean_feasible_value"])
        self.assertEqual(result["feasible_fraction"], 0)

    def test_counterexample_crossover_productivity_zero_and_quarter(self):
        p = {"kind": "knapsack", "n": 4, "weights": [2, 2, 1, 1],
             "profits": [2, 2, 2, 2], "capacity": 2}
        probabilities = []
        for first, second in (("1000", "0100"), ("0010", "0001")):
            differing = [i for i in range(4) if first[i] != second[i]]
            successes = 0
            for choices in itertools.product((0, 1), repeat=len(differing)):
                child = list(first)
                for i, bit in zip(differing, choices):
                    child[i] = first[i] if bit else second[i]
                score = engine.evaluate(p, "".join(child))
                successes += int(score["feasible"] and score["value"] > 2)
            probabilities.append(successes / 2 ** len(differing))
        self.assertEqual(probabilities, [0, 0.25])

    def test_determinism_full_log(self):
        for method in engine.METHODS:
            a, summary_a = self._run(method=method, budget=19)
            b, summary_b = self._run(method=method, budget=19)
            self.assertEqual(a, b)
            self.assertEqual(summary_a, summary_b)

    def test_mutation_only_three_methods_identical(self):
        logs = []
        for method in engine.METHODS:
            records, _ = self._run(method=method, budget=17, pc=0)
            records[0].pop("method")
            records[-1]["summary"].pop("method")
            logs.append(records)
        self.assertEqual(logs[0], logs[1])
        self.assertEqual(logs[1], logs[2])
        for record in logs[0]:
            if record["event"] == "step":
                self.assertEqual(len(record["parent_indices"]), 1)
                self.assertIsNone(record["anchor_index"])
                self.assertEqual(record["planned_offspring"], 1)

    def test_first_baseline_repeated_candidate_matches(self):
        logs = [self._run(method=method, budget=4, pc=1)[0]
                for method in ("baseline", "repeated")]
        first = [next(r for r in records if r["event"] == "candidate") for records in logs]
        self.assertEqual(first[0], first[1])

    def test_operator_draws_reconstructed_independently(self):
        records, _ = self._run(budget=1, pc=1)
        initial = records[0]
        step = next(r for r in records if r["event"] == "step")
        candidate = next(r for r in records if r["event"] == "candidate")
        rngs = engine.make_rngs(0, 0)
        parents = [int(rngs["parents"].integers(4)), int(rngs["parents"].integers(4))]
        bits = rngs["crossover"].random(4) < 0.5
        pre = "".join(initial["population"][parents[0] if bits[i] else parents[1]][i] for i in range(4))
        changes = np.flatnonzero(rngs["mutation"].random(4) < 0.25).tolist()
        expected = list(pre)
        for i in changes:
            expected[i] = "1" if expected[i] == "0" else "0"
        self.assertEqual(step["parent_indices"], parents)
        self.assertEqual(candidate["pre_mutation_mask"], pre)
        self.assertEqual(candidate["mutation_bits"], changes)
        self.assertEqual(candidate["mask"], "".join(expected))
        self.assertEqual(initial["rng_start"]["branch"], records[-1]["summary"]["rng_final"]["branch"])

    def test_directed_preserves_score_and_maximizes_distance(self):
        population = ["1100", "1010", "1001", "0110"]
        records, _ = self._run(masks=population, method="directed", budget=1, pc=1)
        step = next(r for r in records if r["event"] == "step")
        first, second = step["parent_indices"]
        self.assertEqual(step["eligible_indices"], [0, 1, 2, 3])
        maximum = max(sum(a != b for a, b in zip(population[first], other)) for other in population)
        self.assertEqual(step["parent_distance"], maximum)
        self.assertEqual(step["directed_active"], population[second] != population[step["anchor_index"]])

    def test_directed_one_genotype_inactive(self):
        p = {"kind": "flat", "n": 4}
        records, summary = self._run(problem=p, masks=["0000"] * 30,
                                     method="directed", budget=1, pc=1)
        step = next(r for r in records if r["event"] == "step")
        self.assertFalse(step["directed_active"])
        self.assertEqual(summary["directed_active_steps"], 0)
        self.assertEqual(step["parent_distance"], 0)

    def test_directed_never_crosses_anchor_fitness_class(self):
        population = ["1000", "1100", "1010", "1110"]
        for seed in range(8):
            records, _ = self._run(masks=population, method="directed", budget=1,
                                   pc=1, seed=seed)
            step = next(r for r in records if r["event"] == "step")
            scores = records[0]["scores"]
            anchor_key = scores[step["anchor_index"]]["key"]
            expected = [i for i, score in enumerate(scores) if score["key"] == anchor_key]
            self.assertEqual(step["eligible_indices"], expected)
            self.assertEqual(scores[step["parent_indices"][1]]["key"], anchor_key)

    def test_zero_strength_mutation_keeps_candidate_and_counts_duplicate(self):
        p = {"kind": "flat", "n": 4}
        with patch.object(engine.np, "flatnonzero", return_value=np.array([], dtype=int)):
            records, summary = self._run(problem=p, masks=["1000"], budget=1, pc=0)
        candidate = next(r for r in records if r["event"] == "candidate")
        self.assertEqual(candidate["mutation_bits"], [])
        self.assertEqual(candidate["mask"], "1000")
        self.assertEqual(summary["duplicate_candidates"], 1)

    def test_known_initial_scores_not_physically_reevaluated(self):
        p = {"kind": "onemax", "n": 4}
        masks = ["0000", "1000", "1100"]
        scores = [engine.evaluate(p, m) for m in masks]
        real = engine._score
        with patch.object(engine, "_score", wraps=real) as evaluation:
            _, summary = self._run(problem=p, masks=masks, scores=scores, budget=9)
        self.assertEqual(evaluation.call_count, 9)
        self.assertEqual(summary["new_calls"], 9)

    def test_repeated_partial_batch_keeps_population(self):
        records, summary = self._run(method="repeated", budget=3, pc=1)
        finish = next(r for r in records if r["event"] == "finish_step")
        self.assertFalse(finish["completed"])
        self.assertIsNone(finish["selected_slot"])
        self.assertIsNone(finish["replacement_index"])
        self.assertFalse(finish["accepted"])
        self.assertEqual(summary["new_calls"], 3)
        self.assertEqual(summary["incomplete_steps"], 1)
        self.assertEqual(summary["population_hash"], engine.population_hash(records[0]["population"]))
        self.assertEqual([r["call"] for r in records if r["event"] == "candidate"], [1, 2, 3])

    def test_last_prefix_candidate_records_improvement_without_replacement(self):
        p = {"kind": "flat", "n": 4}
        masks = ["0000"] * 3
        known = [engine.evaluate(p, mask) for mask in masks]
        scripted = [{"key": [1, i], "weight": None, "value": i, "feasible": True}
                    for i in (0, 0, 1)]
        with patch.object(engine, "_score", side_effect=scripted):
            records, summary = self._run(problem=p, masks=masks, scores=known,
                                         method="repeated", budget=3, pc=1)
        self.assertEqual(summary["first_improvement_call"], 3)
        self.assertEqual(summary["record"]["call"], 3)
        self.assertEqual(summary["record"]["score"]["value"], 1)
        self.assertEqual(summary["metrics"]["mean_feasible_value"], 0)

    def test_tie_is_accepted_from_current_population(self):
        p = {"kind": "flat", "n": 4}
        records, summary = self._run(problem=p, budget=1, pc=0)
        finish = next(r for r in records if r["event"] == "finish_step")
        self.assertTrue(finish["accepted"])
        self.assertIn(finish["replacement_index"], range(4))
        self.assertEqual(finish["selected_slot"], 0)
        self.assertEqual(summary["accepted_steps"], 1)
        self.assertEqual(summary["initial_record"]["mask"], "0000")

    def test_worse_child_rejected_and_initial_record_tie_is_earliest(self):
        p = {"kind": "onemax", "n": 1}
        records, summary = self._run(problem=p, masks=["1", "1"], budget=1, pc=0)
        finish = next(r for r in records if r["event"] == "finish_step")
        self.assertFalse(finish["accepted"])
        self.assertIsNone(finish["replacement_index"])
        self.assertEqual(summary["initial_record"]["mask"], "1")
        self.assertEqual(summary["record"]["call"], 0)
        self.assertIsNone(summary["first_improvement_call"])

    def test_duplicate_and_invalid_queries_all_counted(self):
        p = {"kind": "knapsack", "n": 1, "weights": [2], "profits": [1], "capacity": 1}
        records, summary = self._run(problem=p, masks=["0"], budget=3, pc=0)
        self.assertEqual(summary["new_calls"], 3)
        self.assertEqual(summary["invalid_candidates"], 3)
        self.assertEqual(summary["duplicate_candidates"], 2)
        self.assertEqual(summary["physical_calls"], 3)
        self.assertEqual(summary["candidate_feasible"], 0)

    def test_checkpoint_observes_before_replacement(self):
        p = {"kind": "onemax", "n": 1}
        records, _ = self._run(problem=p, masks=["0"], budget=1, pc=0)
        end_checkpoint = [r for r in records if r["event"] == "checkpoint"][-1]
        finish = next(r for r in records if r["event"] == "finish_step")
        self.assertEqual(end_checkpoint["population"], ["0"])
        self.assertEqual(end_checkpoint["record"]["mask"], "1")
        self.assertEqual(end_checkpoint["stage"], "AFTER_EVALUATION_BEFORE_REPLACEMENT")
        self.assertEqual(finish["population_hash"], engine.population_hash(["1"]))

    def test_nonflat_parameters_and_invalid_known_score(self):
        with self.assertRaises(ValueError):
            self._run(method="combined")
        with self.assertRaises(ValueError):
            self._run(pc=1.1)
        with self.assertRaises(ValueError):
            self._run(budget=0)
        with self.assertRaises(ValueError):
            self._run(masks=["0000"], scores=[{"key": [1, 0], "weight": None,
                                             "value": 3, "feasible": True}])


if __name__ == "__main__":
    unittest.main()

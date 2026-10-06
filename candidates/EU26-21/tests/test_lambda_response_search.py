"""CI-only tests: no scientific experiment is executed by local editing."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lambda_response_study.search import run_search
from lambda_response_study.oracle import expected_lambda, validate_trace

class LambdaResponseSearchTests(unittest.TestCase):
    def run_one(self, arm="adaptive"):
        return run_search(lambda mask: sum(mask)/40, problem="onemax", arm=arm,
                          initial_mask=[0]*40, initial_score=0, search_seed=150001)

    def test_complete_generations_fixed_counts_and_pair(self):
        adaptive, fixed = self.run_one(), self.run_one("fixed10")
        self.assertEqual(len(adaptive["generation_trace"]), 20)
        self.assertEqual(fixed["counts"]["physical_calls"], 400)
        self.assertLessEqual(adaptive["counts"]["physical_calls"], 1600)
        self.assertEqual(adaptive["evaluations"][:20], fixed["evaluations"][:20])
        self.assertEqual(adaptive["generation_trace"][0]["RNG_state_after"],
                         fixed["generation_trace"][0]["RNG_state_after"])
        self.assertTrue(all(g["lambda_before"] == g["applied_lambda_after"] == 10
                            for g in fixed["generation_trace"]))
        self.assertEqual(fixed["counts"]["actual_tree_fits"], 0)

    def test_deterministic_persistent_rng(self):
        self.assertEqual(self.run_one(), self.run_one())

    def test_neutral_events_and_bounds(self):
        trace = run_search(lambda mask: .5 if sum(mask) else 0,
                           problem="census", arm="adaptive", initial_mask=[1]+[0]*39,
                           initial_score=.5, search_seed=1234)
        self.assertTrue(all(not g["strict_success"] for g in trace["generation_trace"]))
        self.assertEqual(trace["final"]["lambda"], 40)
        self.assertEqual(trace["final"]["score"], .5)
        self.assertEqual(validate_trace(trace)["mismatches"], 0)
        self.assertGreater(trace["counts"]["duplicate_queries"], 0)

    def test_every_duplicate_is_physically_evaluated(self):
        calls = []
        def objective(mask):
            calls.append(mask)
            return sum(mask)/40
        trace = run_search(objective, problem="onemax", arm="fixed10",
                           initial_mask=[0]*40, initial_score=0, search_seed=17)
        self.assertEqual(len(calls), trace["counts"]["physical_calls"])
        self.assertEqual(len(calls), 400)
        self.assertEqual(len(set(calls)), trace["counts"]["unique_masks"])

    def test_first_update_is_observable(self):
        trace = self.run_one()
        event = trace["generation_trace"][0]
        self.assertTrue(event["strict_success"])
        self.assertAlmostEqual(event["applied_lambda_after"], 10/1.5)
        self.assertAlmostEqual(event["lambda_delta_percent"], -100/3)

    def test_invalid_initial_masks_scores_and_arm(self):
        for kwargs in (
            {"initial_mask": [0]*39}, {"initial_mask": [True]*40},
            {"initial_score": float("nan")}, {"initial_score": True},
            {"search_seed": True}, {"arm": "fixed1"},
        ):
            args = dict(problem="onemax",arm="adaptive",initial_mask=[0]*40,initial_score=0,search_seed=1)
            args.update(kwargs)
            with self.assertRaises((ValueError, TypeError)):
                run_search(lambda mask: sum(mask)/40, **args)

    def test_changed_known_mask_score_rejected(self):
        counter = [0]
        def objective(mask):
            counter[0] += 1
            return .5 + .000001 * counter[0] if sum(mask) else 0
        with self.assertRaises(ValueError):
            run_search(objective,problem="census",arm="fixed10",initial_mask=[1]+[0]*39,
                       initial_score=.5,search_seed=12)

    def test_oracle_rejects_tampering_and_missing_candidates(self):
        original = self.run_one()
        for modify in (
            lambda t: t["evaluations"].pop(),
            lambda t: t["generation_trace"][0].update(applied_lambda_after=9),
            lambda t: t["generation_trace"][0].update(strict_success=False),
            lambda t: t["generation_trace"][0].update(offspring_count=9),
            lambda t: t["generation_trace"][1].update(RNG_state_before={}),
            lambda t: t["counts"].update(actual_tree_fits=1),
            lambda t: t["evaluations"][0].update(best_so_far_score=.9),
            lambda t: t["final"].update(score=.99),
        ):
            trace = deepcopy(original)
            modify(trace)
            with self.assertRaises(ValueError):
                validate_trace(trace)

class LambdaOracleTests(unittest.TestCase):
    def test_success_gain_size_does_not_change_lambda(self):
        for gain in (.0001,.001,.05):
            self.assertEqual(expected_lambda(10,strict_success=(.5+gain > .5),arm="adaptive"),10/1.5)

    def test_tie_and_rejected_worse_same_growth(self):
        for candidate in (.5,.49):
            self.assertAlmostEqual(expected_lambda(10,strict_success=(candidate>.5),arm="adaptive"),
                                   10*1.5**.25)

    def test_bounds_and_clipped_percent(self):
        self.assertEqual(expected_lambda(1,strict_success=True,arm="adaptive"),1)
        self.assertEqual(expected_lambda(1.2,strict_success=True,arm="adaptive"),1)
        self.assertEqual(expected_lambda(40,strict_success=False,arm="adaptive"),40)
        self.assertEqual(expected_lambda(39,strict_success=False,arm="adaptive"),40)

    def test_fixed_control_is_not_adaptive_proposal(self):
        self.assertEqual(expected_lambda(10,strict_success=True,arm="fixed10"),10)
        self.assertEqual(expected_lambda(10,strict_success=False,arm="fixed10"),10)
        with self.assertRaises(ValueError):
            expected_lambda(9,strict_success=True,arm="fixed10")

    def test_oracle_has_no_production_function_imports(self):
        text = (Path(__file__).resolve().parents[1]/"lambda_response_study/oracle.py").read_text()
        self.assertNotIn("from hybrid_1",text)
        self.assertNotIn("from local_optima",text)
        self.assertNotIn("next_lambda(",text)
        self.assertNotIn("controls(",text)

if __name__ == "__main__":
    unittest.main()

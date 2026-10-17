"""CI-only checks of the new adapter and independently reconstructed evidence.

Fixtures below are teaching examples, not KPLIB observations or scientific
replications. No local execution, publication-effect test, or bootstrap belongs
to this suite.
"""
from __future__ import annotations

import copy
import itertools
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.adaptive_parameters.mutation_only import engine, verifier
from studies.knapsack_parameters.mutation_population import observations, reporting, search


def problem(n=10, capacity=None):
    return {"n": n, "weights": [1] * n, "profits": list(range(1, n + 1)),
            "capacity": n if capacity is None else capacity}


def score(instance, mask):
    """A deliberately independent exact evaluator for test initialization."""
    weight = sum(instance["weights"][i] for i, bit in enumerate(mask) if bit == "1")
    profit = sum(instance["profits"][i] for i, bit in enumerate(mask) if bit == "1")
    return {"weight": weight, "profit": profit,
            "feasible": weight <= instance["capacity"]}


def bundle(*, instance=None, masks=None, method="adaptive_mutation", budget=61, seed=7):
    instance = problem() if instance is None else instance
    masks = ["0" * instance["n"]] * 30 if masks is None else masks
    return search.run_profile(instance, masks, [score(instance, mask) for mask in masks],
                              method, seed, 0, 0, budget=budget)


class MutationPopulationCoreTests(unittest.TestCase):
    def test_adapter_independently_verifies_every_new_request(self):
        result = bundle()
        self.assertEqual(set(result), {"log", "verification"})
        self.assertEqual(result["verification"]["verification_status"], "VERIFIED")
        self.assertEqual(result["verification"]["independent_score_checks"], 91)
        self.assertEqual(result["verification"]["summary"], result["log"]["summary"])
        self.assertEqual(result["log"]["summary"]["new_calls"], 61)
        self.assertEqual(result["log"]["summary"]["physical_evaluations"], 61)

    def test_both_methods_have_the_same_first_generation(self):
        fixed = bundle(method="fixed", budget=58)["log"]
        adaptive = bundle(budget=58)["log"]
        self.assertEqual(fixed["candidates"][:29], adaptive["candidates"][:29])
        self.assertEqual(fixed["rng_initial"], adaptive["rng_initial"])
        self.assertIsInstance(search.verify_paired_first_generation(fixed, adaptive), dict)

    def test_pair_check_rejects_a_changed_candidate(self):
        fixed = bundle(method="fixed", budget=29)["log"]
        adaptive = bundle(budget=29)["log"]
        adaptive["candidates"][0]["mask"] = "1" * 10
        with self.assertRaises(ValueError):
            search.verify_paired_first_generation(fixed, adaptive)

    def test_determinism_and_no_input_mutation(self):
        instance = problem()
        masks = ["0" * 10] * 30
        before = copy.deepcopy((instance, masks))
        first = bundle(instance=instance, masks=masks)
        self.assertEqual(first, bundle(instance=instance, masks=masks))
        self.assertEqual((instance, masks), before)

    def test_unadmitted_population_profile_is_not_a_fixed_method_alias(self):
        with self.assertRaises(ValueError):
            bundle(method="adaptive_population", budget=1)

    def test_oracle_metadata_and_wrong_known_score_are_refused(self):
        invalid = problem()
        invalid["exact_optimum"] = 55
        with self.assertRaises(ValueError):
            bundle(instance=invalid, budget=1)
        instance = problem()
        scores = [score(instance, "0" * 10) for _ in range(30)]
        scores[0]["profit"] = 1
        with self.assertRaises(ValueError):
            search.run_profile(instance, ["0" * 10] * 30, scores, "fixed", 7, 0, 0, budget=1)

    def test_search_is_not_authorized_outside_actions(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                bundle(budget=1)

    def test_exact_budget_and_terminal_prefix_have_no_state_update(self):
        for budget, complete, partial in ((28, 0, 28), (29, 1, 0), (30, 1, 1), (61, 2, 3)):
            with self.subTest(budget=budget):
                log = bundle(budget=budget)["log"]
                self.assertEqual(len(log["candidates"]), budget)
                self.assertEqual(log["summary"]["full_generations"], complete)
                self.assertEqual(log["summary"]["partial_children"], partial)
                if partial:
                    event = log["generations"][-1]
                    self.assertFalse(event["complete"])
                    self.assertEqual(event["population_after"], event["population_before"])
                    self.assertEqual(event["p_m_next"], event["p_m"])
                    self.assertEqual(event["stagnation_after"], event["stagnation_before"])
                    self.assertEqual(event["controller_event"], "PARTIAL_NO_UPDATE")

    def test_registered_5000_new_calls_are_not_5000_total(self):
        log = bundle(instance=problem(2), masks=["11"] * 30, budget=5000)["log"]
        self.assertEqual(log["summary"]["new_calls"], 5000)
        self.assertEqual(log["summary"]["known_score_validation_evaluations"], 30)
        self.assertEqual(log["summary"]["full_generations"], 172)
        self.assertEqual(log["summary"]["partial_children"], 12)
        self.assertEqual(len(log["summary"]["final_population"]), 30)

    def test_stagnant_flat_feasible_record_doubles_mutation_not_population(self):
        instance = problem(100, 0)
        log = bundle(instance=instance, budget=29 * 5)["log"]
        self.assertEqual(log["generations"][-1]["controller_event"], "STAGNATION_DOUBLE")
        self.assertEqual(log["generations"][-1]["p_m_next"], .02)
        self.assertEqual(log["summary"]["best_profit"], 0)
        self.assertTrue(all(len(event["population_after"]) == 30 for event in log["generations"]))
        self.assertTrue(all(event["p_m"] == .01 for event in log["generations"]))

    def test_fixed_controller_never_changes_probability(self):
        log = bundle(instance=problem(100, 0), method="fixed", budget=29 * 6)["log"]
        self.assertTrue(all(event["p_m"] == event["p_m_next"] == .01
                            for event in log["generations"]))

    def test_controller_bounds_and_ties_do_not_become_strict_successes(self):
        probability, stagnant = .01, 0
        for target in (.02, .04, .08, .08):
            for _ in range(5):
                probability, stagnant, event = engine.update_mutation(100, probability, stagnant, False)
            self.assertEqual((probability, stagnant, event), (target, 0, "STAGNATION_DOUBLE"))
        self.assertEqual(engine.update_mutation(100, .08, 4, True), (.04, 0, "SUCCESS_HALVE"))
        self.assertEqual(engine.update_mutation(100, .01, 4, True), (.01, 0, "SUCCESS_HALVE"))
        for args in ((100, float("nan"), 0, False), (100, .009, 0, False),
                     (100, .09, 0, False), (100, .01, 5, False),
                     (100, .01, True, False), (100, .01, 0, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                engine.update_mutation(*args)

    def test_elite_does_not_mean_rejection_of_every_worse_child(self):
        log = bundle(masks=["1" * 10] * 30, budget=29)["log"]
        event = log["generations"][0]
        self.assertEqual(event["population_after"], [event["elite_index"], *range(30, 59)])
        self.assertEqual(log["summary"]["best_profit"], 55)
        self.assertTrue(any(child["profit"] < 55 for child in log["candidates"]))

    def test_replay_does_not_use_production_adaptation_or_evaluation(self):
        log = bundle()["log"]
        with patch.object(engine, "evaluate", side_effect=AssertionError("production evaluator")), \
                patch.object(engine, "update_mutation", side_effect=AssertionError("production controller")), \
                patch.object(engine, "run_search", side_effect=AssertionError("production search")):
            self.assertEqual(verifier.verify_log(log)["verification_status"], "VERIFIED")

    def test_replay_rejects_controller_operator_and_accounting_corruption(self):
        original = bundle()["log"]
        edits = (
            lambda item: item["candidates"][0].__setitem__("profit", 100000),
            lambda item: item["candidates"][0].__setitem__("mutation_bits", [-1]),
            lambda item: item["candidates"][0].__setitem__("duplicate", not item["candidates"][0]["duplicate"]),
            lambda item: item["generations"][0].__setitem__("p_m_next", .9),
            lambda item: item["generations"][-1].__setitem__("complete", True),
            lambda item: item["summary"].__setitem__("physical_evaluations", 0),
        )
        for index, change in enumerate(edits):
            with self.subTest(edit=index):
                modified = copy.deepcopy(original)
                change(modified)
                with self.assertRaises(ValueError):
                    verifier.verify_log(modified)

    def test_observer_reconstructs_initial_record_and_real_zero(self):
        log = bundle(instance=problem(2, 0), budget=30)["log"]
        result = observations.summarize_log(log, 1, checkpoints=(0, 29, 30), reference_profit=0)
        self.assertEqual(result["initial_record"]["profit"], 0)
        self.assertEqual(result["final_record"]["profit"], 0)
        self.assertFalse(result["escaped"])
        self.assertIsNone(result["first_escape"])
        self.assertEqual(result["capped_calls"], 30)
        self.assertEqual(result["record_trace"][0]["call"], 0)

    def test_independent_strict_three_bit_local_maximum(self):
        instance = {"n": 3, "weights": [6, 5, 5], "profits": [10, 8, 8], "capacity": 10}
        certificate = observations.certify_n2(instance, "100", 16)
        self.assertEqual(certificate["neighbor_count"], 6)
        self.assertEqual(certificate["better_feasible_count"], 0)
        self.assertEqual(certificate["equal_feasible_count"], 0)
        self.assertEqual(certificate["locality"], "N2_STRICT_LOCAL")
        self.assertEqual(certificate["global_status"], "NONGLOBAL")
        self.assertEqual(certificate["independent_evaluations"], 7)
        self.assertEqual(score(instance, "011"), {"weight": 10, "profit": 16, "feasible": True})
        self.assertEqual(sum(a != b for a, b in zip("100", "011")), 3)

    def test_certificate_preserves_plateau_and_nonlocal_and_global(self):
        instance = {"n": 3, "weights": [1, 1, 1], "profits": [1, 1, 1], "capacity": 1}
        plateau = observations.certify_n2(instance, "100", 1)
        self.assertEqual(plateau["locality"], "N2_PLATEAU")
        self.assertEqual(plateau["global_status"], "GLOBAL")
        self.assertEqual(plateau["equal_feasible_count"], 2)
        nonlocal_case = observations.certify_n2(instance, "000", 1)
        self.assertEqual(nonlocal_case["locality"], "N2_NOT_LOCAL")
        self.assertEqual(nonlocal_case["better_feasible_count"], 3)

    def test_n100_certificate_covers_every_one_and_two_bit_neighbor_once(self):
        instance = {"n": 100, "weights": [1] * 100, "profits": [1] * 100, "capacity": 0}
        certificate = observations.certify_n2(instance, "0" * 100, 0)
        self.assertEqual(certificate["neighbor_count"], 5050)
        self.assertEqual(certificate["independent_evaluations"], 5051)
        identities = {tuple(row["flipped_bits"]) for row in certificate["neighbors"]}
        expected = {(i,) for i in range(100)} | set(itertools.combinations(range(100), 2))
        self.assertEqual(identities, expected)
        self.assertEqual(len({row["mask"] for row in certificate["neighbors"]}), 5050)
        self.assertTrue(all(not row["feasible"] for row in certificate["neighbors"]))

    def test_instructional_three_bit_probability_is_not_overall_success_probability(self):
        # Exactly this three-bit target, not any three flips or any improvement.
        p = .5
        self.assertEqual(p ** 3 * (1 - p) ** (4 - 3), 1 / 16)

    def test_reporting_rejects_incomplete_pilot_before_drawing(self):
        with self.assertRaises(ValueError):
            reporting._data({"results": []}, {})

    def test_ci_plot_smoke_uses_only_small_instructional_logs(self):
        # This is a rendering fixture, not a sixteen-run KPLIB pilot. It never
        # calls build_report or writes a scientific status/measurement file.
        logs, indexed = {}, {}
        for method in ("fixed", "adaptive_mutation"):
            log = bundle(method=method, budget=30)["log"]
            observed = observations.summarize_log(log, 55)
            for start in ("cloned", "bank"):
                key = "UC-s000", start, method
                logs[key] = log
                indexed[key] = {"observations": observed}
        with tempfile.TemporaryDirectory() as directory:
            names = reporting._draw_trajectories(Path(directory), logs, indexed)
            self.assertEqual(len(names), 2)
            self.assertTrue(all((Path(directory) / name).stat().st_size > 1000 for name in names))


if __name__ == "__main__":
    unittest.main()

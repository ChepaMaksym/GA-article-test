"""CI-only transfer checks using small instructional, non-KPLIB problems.

These fixtures verify software semantics, not statistical algorithm superiority.
No exact solver, external optimum or scientific search series is invoked.
"""

from copy import deepcopy
import inspect
import os
import unittest
from unittest.mock import patch

from studies.adaptive_parameters.mutation_only.engine import make_rngs, run_search
from studies.knapsack_parameters.bntga_selection import knapsack
from studies.knapsack_parameters.bntga_selection.knapsack_verifier import (
    verify_archive_log, verify_log,
)


def instructional_problem():
    return {"n": 4, "weights": [1, 2, 3, 4], "profits": [2, 4, 6, 8], "capacity": 4}


def score(problem, mask):
    weight = sum(problem["weights"][i] for i, bit in enumerate(mask) if bit == "1")
    profit = sum(problem["profits"][i] for i, bit in enumerate(mask) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def initial_bank(problem):
    masks = ["0000", "1000", "0100", "0010", "0001", "1100"] * 5
    return masks, [score(problem, mask) for mask in masks]


def small_log(balanced=True, budget=61, seed=17001):
    problem = instructional_problem()
    masks, scores = initial_bank(problem)
    return knapsack.run_archive_search(
        problem, masks, scores, balanced, make_rngs(seed, 0, 0), budget=budget
    )


class KnapsackTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("The registered transfer checks run only in GitHub Actions")

    def test_both_archive_profiles_replayed_independently(self):
        for balanced in (False, True):
            with self.subTest(balanced=balanced):
                receipt = verify_archive_log(small_log(balanced))
                self.assertEqual(receipt["verification_status"], "VERIFIED")
                self.assertEqual(receipt["new_calls"], 61)
                self.assertEqual(receipt["independent_score_checks"], 91)
                self.assertEqual(receipt["completed_generations"], 2)
                self.assertEqual(receipt["partial_generations"], 1)
                self.assertEqual(receipt["summary"]["partial_children"], 3)

    def test_first_complete_generation_is_identical_in_pair(self):
        fixed = small_log(False)
        balanced = small_log(True)
        self.assertEqual(fixed["rng_initial"], balanced["rng_initial"])
        self.assertEqual(fixed["initial_archive"], balanced["initial_archive"])
        self.assertEqual(fixed["candidates"][:29], balanced["candidates"][:29])
        self.assertEqual(fixed["generations"][0]["rng_after"],
                         balanced["generations"][0]["rng_after"])

    def test_unchanged_classical_fixed_log_delegates_independent_verifier(self):
        problem = instructional_problem()
        masks, scores = initial_bank(problem)
        log = run_search(problem, masks, scores, "fixed", make_rngs(17001, 0, 0), budget=61)
        self.assertEqual(verify_log(log)["verification_status"], "VERIFIED")
        self.assertEqual(log["summary"]["physical_evaluations"], 61)

    def test_5000_query_singleton_negative_control_and_last_prefix(self):
        # Capacity zero admits only the empty mask.  This is a software fixture,
        # not a 5000-query KPLIB experiment or evidence of algorithm superiority.
        problem = {"n": 2, "weights": [1, 1], "profits": [1, 1], "capacity": 0}
        masks = ["00"] * 30
        scores = [score(problem, mask) for mask in masks]
        log = knapsack.run_archive_search(
            problem, masks, scores, True, make_rngs(17002, 0, 0), budget=5000
        )
        receipt = verify_archive_log(log)
        self.assertEqual(receipt["new_calls"], 5000)
        self.assertEqual(receipt["independent_score_checks"], 5030)
        self.assertEqual(log["summary"]["full_generations"], 172)
        self.assertEqual(log["summary"]["partial_children"], 12)
        self.assertEqual(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["best_call"], 0)
        self.assertEqual(log["rng_initial"]["selection"], log["rng_final"]["selection"])
        self.assertEqual(log["summary"]["final_archive"][0]["selected"], 0)
        self.assertGreater(log["summary"]["duplicate_calls"], 0)
        self.assertGreater(log["summary"]["infeasible_calls"], 0)

    def test_terminal_prefix_retains_record_not_population_or_archive(self):
        log = small_log(True, budget=12)
        verify_archive_log(log)
        last = log["generations"][-1]
        self.assertFalse(last["complete"])
        self.assertEqual(last["population_after"], last["population_before"])
        self.assertEqual(last["archive_after"], last["archive_before"])
        self.assertEqual(log["summary"]["final_archive"], log["initial_archive"])
        self.assertEqual(sum(last["working_counts"].values()), 24)
        self.assertEqual(log["summary"]["physical_evaluations"], 12)

    def test_record_can_improve_on_last_query_without_committing_prefix(self):
        problem = {"n": 4, "weights": [1] * 4, "profits": [1, 2, 3, 4], "capacity": 4}
        masks = ["0000"] * 30
        scores = [score(problem, mask) for mask in masks]
        generators = make_rngs(17003, 0, 0)
        # Construct an explicit PCG64 software-test state with a nonempty first
        # mutation.  This checks a boundary branch, not a selected scientific seed.
        state = None
        for _ in range(64):
            candidate_state = deepcopy(generators["mutation"].bit_generator.state)
            flags = generators["mutation"].random(4) < 0.25
            if any(flags):
                state = candidate_state
                break
        self.assertIsNotNone(state)
        generators["mutation"].bit_generator.state = state
        log = knapsack.run_archive_search(problem, masks, scores, True, generators, budget=1)
        verify_archive_log(log)
        self.assertEqual(log["summary"]["best_call"], 1)
        self.assertGreater(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["final_population"], list(range(30)))
        self.assertEqual(log["summary"]["final_archive"], log["initial_archive"])

    def test_every_duplicate_still_invokes_raw_evaluator(self):
        with patch.object(knapsack, "_score", wraps=knapsack._score) as evaluator:
            log = small_log(True, budget=61)
            self.assertEqual(evaluator.call_count, 91)
        with patch.object(knapsack, "_score", side_effect=AssertionError("production evaluator used")):
            self.assertEqual(verify_archive_log(log)["verification_status"], "VERIFIED")

    def test_raw_integer_and_feasibility_corruptions_rejected(self):
        log = small_log()
        mutations = (
            ("weight", lambda value: value + 1),
            ("profit", lambda value: value + 1),
            ("feasible", lambda value: not value),
            ("mask", lambda value: ("1" if value[0] == "0" else "0") + value[1:]),
            ("duplicate", lambda value: not value),
            ("call", lambda value: True),
        )
        for field, change in mutations:
            with self.subTest(field=field):
                corrupted = deepcopy(log)
                corrupted["candidates"][0][field] = change(corrupted["candidates"][0][field])
                with self.assertRaises(ValueError):
                    verify_archive_log(corrupted)

    def test_normalization_and_parent_score_corruptions_rejected(self):
        log = small_log()
        changed_archive = deepcopy(log)
        changed_archive["initial_archive"][0]["objectives"][0] += 0.1
        changed_parent = deepcopy(log)
        changed_parent["candidates"][0]["parent_scores"][0]["profit"] += 1
        for corrupted in (changed_archive, changed_parent):
            with self.assertRaises(ValueError):
                verify_archive_log(corrupted)

    def test_partial_counter_commit_corruption_rejected(self):
        log = small_log(True, budget=12)
        log["generations"][-1]["archive_after"] = deepcopy(
            log["generations"][-1]["archive_after_selection"]
        )
        with self.assertRaises(ValueError):
            verify_archive_log(log)

    def test_rng_corruption_rejected(self):
        log = small_log()
        log["rng_final"]["mutation"]["state"]["state"] += 1
        with self.assertRaises(ValueError):
            verify_archive_log(log)

    def test_missing_candidate_and_extra_schema_field_rejected(self):
        log = small_log()
        missing = deepcopy(log)
        missing["candidates"].pop()
        extra = deepcopy(log)
        extra["generations"][0]["oracle"] = 100
        for corrupted in (missing, extra):
            with self.assertRaises(ValueError):
                verify_archive_log(corrupted)

    def test_mutation_and_crossover_probabilities_are_fixed(self):
        log = small_log()
        for field in ("p_m", "p_c"):
            corrupted = deepcopy(log)
            corrupted["generations"][0][field] = 0.125
            with self.assertRaises(ValueError):
                verify_archive_log(corrupted)

    def test_archive_contains_only_independently_validated_feasible_points(self):
        log = small_log()
        verify_archive_log(log)
        for generation in log["generations"]:
            for point in generation["archive_after"]:
                raw = score(log["problem"], point["id"])
                self.assertTrue(raw["feasible"])
                self.assertEqual(point["objectives"],
                                 [-raw["profit"] / sum(log["problem"]["profits"]),
                                  raw["weight"] / max(1, log["problem"]["capacity"])])

    def test_input_population_and_known_scores_are_not_mutated(self):
        problem = instructional_problem()
        masks, scores = initial_bank(problem)
        before = deepcopy((problem, masks, scores))
        knapsack.run_archive_search(problem, masks, scores, True, make_rngs(17004, 0, 0), budget=1)
        self.assertEqual((problem, masks, scores), before)

    def test_determinism_for_identical_profile_and_streams(self):
        self.assertEqual(small_log(True), small_log(True))

    def test_no_oracle_metadata_is_accepted(self):
        problem = instructional_problem()
        masks, scores = initial_bank(problem)
        for key in ("optimum", "optimal_mask", "certificate"):
            forbidden = {**problem, key: "external oracle"}
            with self.assertRaises(ValueError):
                knapsack.run_archive_search(
                    forbidden, masks, scores, True, make_rngs(17005, 0, 0), budget=1
                )
        log = small_log()
        log["problem"]["optimum"] = 100
        with self.assertRaises(ValueError):
            verify_archive_log(log)

    def test_initial_score_mismatch_and_no_feasible_start_rejected(self):
        problem = instructional_problem()
        masks, scores = initial_bank(problem)
        scores[0]["profit"] += 1
        with self.assertRaises(ValueError):
            knapsack.run_archive_search(problem, masks, scores, True, make_rngs(17006, 0, 0), budget=1)
        masks = ["1111"] * 30
        scores = [score(problem, mask) for mask in masks]
        with self.assertRaises(ValueError):
            knapsack.run_archive_search(problem, masks, scores, True, make_rngs(17006, 0, 0), budget=1)

    def test_resource_bounds_and_boolean_coefficients_rejected(self):
        problem = instructional_problem()
        masks, scores = initial_bank(problem)
        for changed in (
            {**problem, "capacity": 200001},
            {**problem, "weights": [200001, 2, 3, 4]},
            {**problem, "profits": [True, 4, 6, 8]},
        ):
            with self.assertRaises(ValueError):
                knapsack.run_archive_search(changed, masks, scores, True,
                                            make_rngs(17007, 0, 0), budget=1)

    def test_rng_channels_cannot_alias(self):
        problem = instructional_problem()
        masks, scores = initial_bank(problem)
        generators = make_rngs(17008, 0, 0)
        generators["branch"] = generators["selection"]
        with self.assertRaises(ValueError):
            knapsack.run_archive_search(problem, masks, scores, True, generators, budget=1)

    def test_search_refuses_local_execution(self):
        problem = instructional_problem()
        masks, scores = initial_bank(problem)
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                knapsack.run_archive_search(problem, masks, scores, True,
                                            make_rngs(17009, 0, 0), budget=1)

    def test_verifier_does_not_import_production_knapsack_or_operator(self):
        import studies.knapsack_parameters.bntga_selection.knapsack_verifier as verifier

        source = inspect.getsource(verifier)
        self.assertNotIn("from .knapsack import", source)
        self.assertNotIn("from .operator import", source)
        self.assertNotIn("mutation_only.engine import", source)

    def test_adaptive_historical_method_not_accepted_as_classical_control(self):
        problem = instructional_problem()
        masks, scores = initial_bank(problem)
        log = run_search(problem, masks, scores, "adaptive_mutation",
                         make_rngs(17010, 0, 0), budget=1)
        with self.assertRaises(ValueError):
            verify_log(log)


if __name__ == "__main__":
    unittest.main()

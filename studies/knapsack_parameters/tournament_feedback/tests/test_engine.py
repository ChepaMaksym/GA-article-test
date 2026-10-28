"""CI-only instructional fixtures; no KPLIB tuning or scientific series."""
from __future__ import annotations

import copy
from fractions import Fraction
import inspect
import os
import unittest

from studies.knapsack_parameters.tournament_feedback import engine, verifier
from studies.knapsack_parameters.parameter_dynamics import engine as historical


def problem(n=10, capacity=None):
    return {"n": n, "weights": [1] * n, "profits": list(range(1, n + 1)),
            "capacity": n if capacity is None else capacity}


def journal(profile="adaptive", *, p=None, masks=None, budget=61, seed=7, schedule=None):
    p = problem() if p is None else p
    masks = ["0" * p["n"]] * 30 if masks is None else masks
    scores = [engine.evaluate(p, mask) for mask in masks]
    return engine.run_search(p, masks, scores, profile, engine.make_rngs(seed, 0, 0),
                             budget=budget, schedule=schedule)


def instructional(predicate, **kwargs):
    # Bounded synthetic event fixtures; never use scientific tasks or seeds.
    for seed in range(128):
        log = journal(seed=seed, **kwargs)
        if predicate(log):
            return log
    raise AssertionError("No instructional event within the registered synthetic seed range 0..127")


def semantic(log):
    value = copy.deepcopy(log)
    for name in ("schema", "profile", "schedule", "timing_ns"):
        value.pop(name, None)
    return value


class TournamentFeedbackEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("These instructional checks may execute only in GitHub Actions")

    def test_registered_profiles_and_independent_defaults(self):
        for profile in engine.PROFILES:
            params = engine.default_parameters(profile)
            self.assertEqual(params["tournament_size"], int(profile[1:]) if profile.startswith("k") else 2)
            self.assertEqual({key: params[key] for key in ("p_m", "p_c", "target_mu", "elite_count")},
                             {"p_m": .01, "p_c": .9, "target_mu": 30, "elite_count": 1})
            params["target_mu"] = 99
            self.assertEqual(engine.default_parameters(profile)["target_mu"], 30)
        for profile in (0, 8, True, "k1", "k6", "donor", None):
            with self.assertRaises(ValueError):
                engine.default_parameters(profile)

    def test_only_registered_tournament_can_change(self):
        for name, value in (("p_m", .02), ("p_c", .8), ("target_mu", 10), ("elite_count", 2)):
            params = engine.default_parameters("adaptive")
            params[name] = value
            with self.assertRaises(ValueError):
                engine.update_parameters(params, 0, True, 29, Fraction(0), "adaptive")
        params = engine.default_parameters("k2")
        params["tournament_size"] = 3
        with self.assertRaises(ValueError):
            engine.update_parameters(params, 0, True, 29, Fraction(0), "k2")

    def test_five_failed_generations_and_boundary_event(self):
        params, failed = engine.default_parameters("adaptive"), 0
        for index in range(1, 6):
            change = engine.update_parameters(params, failed, False, 29, Fraction(0), "adaptive")
            failed = change["failed_queries_after"]
            self.assertEqual(failed, 29 * index if index < 5 else 0)
        self.assertEqual(change["event"], "STAGNATION")
        self.assertEqual(change["failed_queries_accumulated"], 145)
        self.assertEqual(change["stagnation_overshoot"], 0)
        self.assertEqual(change["parameters"]["tournament_size"], 2)
        self.assertTrue(change["parameter_events"][3]["at_boundary"])

    def test_success_has_priority_and_resets_counter(self):
        params = engine.default_parameters("adaptive")
        change = engine.update_parameters(params, 116, True, 29, Fraction(0), "adaptive")
        self.assertEqual(change["event"], "SUCCESS")
        self.assertEqual(change["failed_queries_accumulated"], 0)
        self.assertEqual(change["failed_queries_after"], 0)
        self.assertEqual(change["parameters"]["tournament_size"], 3)

    def test_upper_boundary_and_decrease(self):
        params = engine.default_parameters("adaptive")
        params["tournament_size"] = 5
        success = engine.update_parameters(params, 0, True, 29, Fraction(0), "adaptive")
        self.assertEqual(success["parameters"]["tournament_size"], 5)
        self.assertEqual(success["parameter_events"][3]["direction"], "unchanged")
        self.assertTrue(success["parameter_events"][3]["at_boundary"])
        failure = engine.update_parameters(params, 116, False, 29, Fraction(0), "adaptive")
        self.assertEqual(failure["parameters"]["tournament_size"], 4)

    def test_partial_update_is_not_accepted_by_controller(self):
        for count in (0, 12, 28, 30, True):
            with self.assertRaises(ValueError):
                engine.update_parameters(engine.default_parameters(), 0, False, count, Fraction(0), "k2")

    def test_static_and_replay_choices_do_not_depend_on_current_signals(self):
        for profile, schedule in (("k2", None), ("k3", None), ("k4", None), ("k5", None),
                                  ("replay", (2, 5, 3))):
            params = engine.default_parameters(profile)
            success = engine.update_parameters(params, 116, True, 29, Fraction(0), profile,
                                               schedule=schedule, completed_generation=1)
            failure = engine.update_parameters(params, 116, False, 29, Fraction(1), profile,
                                               schedule=schedule, completed_generation=1)
            self.assertEqual(success["parameters"], failure["parameters"])
        self.assertEqual(list(inspect.signature(engine.scheduled_k).parameters), ["schedule", "generation_index"])

    def test_policy_computation_consumes_no_operator_randomness(self):
        rngs = engine.make_rngs(7, 0, 0)
        before = engine._states(rngs)
        engine.update_parameters(engine.default_parameters("adaptive"), 116, False, 29, Fraction(1), "adaptive")
        engine.scheduled_k((2, 3, 5), 2)
        self.assertEqual(before, engine._states(rngs))

    def test_schedule_validation_rejects_wrong_shape_values_and_origin_payload(self):
        for schedule in (None, [], [2], [2, 3, 4, 5], [3, 2, 2], [2, True, 2],
                         [2, 2.0, 2], [2, 1, 2], [2, 6, 2], {"k": [2, 2, 2], "fitness": 5}):
            with self.assertRaises(ValueError):
                journal("replay", schedule=schedule)
        with self.assertRaises(ValueError):
            journal("adaptive", schedule=[2, 2, 2])

    def test_applied_schedule_and_exactly_completed_final_block(self):
        log = journal("replay", budget=58, schedule=[2, 5])
        self.assertEqual([g["parameters_before"]["tournament_size"] for g in log["generations"]], [2, 5])
        self.assertEqual(log["summary"]["final_parameters"]["tournament_size"], 5)
        self.assertEqual(verifier.verify(log)["verification_status"], "VERIFIED")

    def test_first_generation_matches_exactly_for_registered_pairs(self):
        logs = [journal(profile, schedule=[2, 5, 3] if profile == "replay" else None)
                for profile in ("k2", "adaptive", "replay")]
        for log in logs[1:]:
            self.assertEqual(log["candidates"][:29], logs[0]["candidates"][:29])
            self.assertEqual(log["generations"][0]["population_after"], logs[0]["generations"][0]["population_after"])
            self.assertEqual(log["generations"][0]["rng_after"], logs[0]["generations"][0]["rng_after"])

    def test_larger_static_tournaments_have_their_registered_initial_draw_count(self):
        for k in (2, 3, 4, 5):
            log = journal("k" + str(k), budget=1)
            self.assertEqual([len(entries) for entries in log["candidates"][0]["tournaments"]], [k, k])
        self.assertNotEqual(journal("k2", budget=1)["rng_final"]["selection"],
                            journal("k3", budget=1)["rng_final"]["selection"])

    def test_historical_full_operator_and_controller_trace_equivalence(self):
        p = problem(12)
        masks = ["0" * 12] + [format(index, "012b") for index in range(1, 30)]
        scores = [engine.evaluate(p, mask) for mask in masks]
        for profile, original in (("k2", 0), ("adaptive", 8)):
            for budget in (1, 29, 30, 87, 100):
                current = engine.run_search(p, masks, scores, profile, engine.make_rngs(7, 1, 1), budget)
                old = historical.run_search(p, masks, scores, original, historical.make_rngs(7, 1, 1), budget)
                self.assertEqual(semantic(current), semantic(old), (profile, budget))

    def test_repeating_own_schedule_is_determinism_fixture_only(self):
        original = journal("adaptive", budget=100)
        schedule = engine.extract_schedule(original)
        repeated = journal("replay", budget=100, schedule=schedule)
        self.assertEqual(semantic(original), semantic(repeated))
        self.assertTrue(all(type(value) is int for value in schedule))

    def test_different_donor_rng_is_not_affected_by_recipient_profile_names(self):
        first = engine._states(engine.make_rngs(110001, 0, 1))
        self.assertEqual(first, engine._states(engine.make_rngs(110001, 0, 1)))
        self.assertNotEqual(first, engine._states(engine.make_rngs(111001, 0, 1)))

    def test_5000_query_accounting_and_twelve_child_prefix(self):
        log = journal("adaptive", p=problem(100), budget=5000)
        check = verifier.verify(log)
        self.assertEqual(len(log["candidates"]), 5000)
        self.assertEqual(log["summary"]["new_calls"], 5000)
        self.assertEqual(log["summary"]["full_generations"], 172)
        self.assertEqual(log["summary"]["partial_children"], 12)
        self.assertEqual(log["summary"]["known_score_validation_evaluations"], 30)
        self.assertEqual(check["independent_score_checks"], 10030)

    def test_duplicate_and_infeasible_candidates_are_not_cached_or_removed(self):
        log = journal("k2", p=problem(2, 0), budget=61)
        self.assertGreaterEqual(log["summary"]["duplicate_calls"], 58)
        self.assertEqual(log["summary"]["physical_evaluations"], 61)
        self.assertEqual(log["summary"]["best_profit"], 0)
        verifier.verify(log)

    def test_nonelite_children_can_be_worse_and_record_is_monotone(self):
        p = problem(100)
        log = instructional(lambda value: any(not row["feasible"] or row["profit"] < sum(p["profits"])
                                               for row in value["candidates"]),
                            p=p, masks=["1" * 100] * 30, budget=29)
        self.assertEqual(log["summary"]["best_profit"], sum(p["profits"]))
        self.assertEqual(log["generations"][0]["population_after"][1:], list(range(30, 59)))
        self.assertTrue(any(log["candidates"][reference - 30]["profit"] < sum(p["profits"])
                            for reference in log["summary"]["final_population"][1:]))

    def test_final_prefix_record_does_not_commit_population_or_controller(self):
        log = instructional(lambda value: value["summary"]["best_call"] == 30,
                            p=problem(100), budget=30)
        prefix = log["generations"][-1]
        self.assertFalse(prefix["complete"])
        self.assertEqual(prefix["controller_event"], "PARTIAL_NO_UPDATE")
        self.assertEqual(prefix["population_before"], prefix["population_after"])
        self.assertEqual(prefix["parameters_before"], prefix["parameters_after"])
        self.assertEqual(prefix["failed_queries_before"], prefix["failed_queries_after"])
        self.assertEqual(verifier.verify(log)["record_call"], 30)

    def test_input_banks_and_schedule_are_not_mutated(self):
        p = problem()
        masks = ["0" * 10] * 30
        scores = [engine.evaluate(p, mask) for mask in masks]
        schedule = [2, 3, 4]
        saved = copy.deepcopy((p, masks, scores, schedule))
        log = engine.run_search(p, masks, scores, "replay", engine.make_rngs(7, 0, 0), 61, schedule)
        self.assertEqual((p, masks, scores, schedule), saved)
        schedule[-1] = 5
        self.assertEqual(log["schedule"], [2, 3, 4])

    def test_optimum_metadata_is_rejected_at_search_boundary(self):
        p = problem()
        p["optimum"] = 55
        with self.assertRaises(ValueError):
            journal(p=p)

    def test_known_score_and_rng_alias_validation(self):
        p = problem()
        masks = ["0" * 10] * 30
        scores = [engine.evaluate(p, mask) for mask in masks]
        scores[0]["profit"] = 1
        with self.assertRaises(ValueError):
            engine.run_search(p, masks, scores, "k2", engine.make_rngs(7, 0, 0), 1)
        scores[0]["profit"] = 0
        rngs = engine.make_rngs(7, 0, 0)
        rngs["selection"] = rngs["mutation"]
        with self.assertRaises(ValueError):
            engine.run_search(p, masks, scores, "k2", rngs, 1)


if __name__ == "__main__":
    unittest.main()

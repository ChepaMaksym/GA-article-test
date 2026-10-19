"""CI-only exact-equivalence checks; no local or scientific benchmark runs."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import inspect
import json
import os
import unittest
from unittest.mock import patch

from studies.adaptive_parameters.mutation_only.engine import make_rngs
from studies.knapsack_parameters.bntga_selection import knapsack as old
from studies.knapsack_parameters.bntga_selection import operator as operator_reference
from studies.knapsack_parameters.bntga_selection.knapsack_verifier import verify_archive_log
from studies.knapsack_parameters.final_study import fast_archive as fast


def points():
    return [
        {"id": "A", "objectives": [0, 6], "selected": 0},
        {"id": "B", "objectives": [2, 4], "selected": 0},
        {"id": "C", "objectives": [3, 3], "selected": 2},
        {"id": "D", "objectives": [6, 0], "selected": 0},
    ]


def fixture():
    problem = {"n": 6, "weights": [1, 2, 3, 4, 5, 6],
               "profits": [2, 4, 6, 8, 10, 12], "capacity": 12}
    masks = ["000000", "100000", "010000", "001000", "000100",
             "000010", "000001", "110000", "101000", "011000"] * 3
    scores = []
    for mask in masks:
        weight = sum(problem["weights"][i] for i, bit in enumerate(mask) if bit == "1")
        profit = sum(problem["profits"][i] for i, bit in enumerate(mask) if bit == "1")
        scores.append({"weight": weight, "profit": profit, "feasible": weight <= 12})
    return problem, masks, scores


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def neighbor(plan, draws):
    first = draws[0]
    for index in draws[1:]:
        if plan["priorities"][index] > plan["priorities"][first]:
            first = index
    return None if first in (0, len(plan["archive"]) - 1) else 0


class FastArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Equivalence fixtures run only in GitHub Actions")

    def test_compilation_preserves_entire_legacy_plan(self):
        for balanced in (False, True):
            for dimension in (0, 1):
                with self.subTest(balanced=balanced, dimension=dimension):
                    expected = operator_reference.freeze_selection(points(), dimension, balanced)
                    self.assertEqual(fast.compile_selection(points(), dimension, balanced).journal_plan(), expected)

    def test_session_and_its_descendants_are_immutable_and_do_not_alias_inputs(self):
        archive = points()
        session = fast.compile_selection(archive, 0)
        original = session.journal_plan()
        with self.assertRaises(FrozenInstanceError):
            session.dimension = 1
        with self.assertRaises(TypeError):
            session.entries[0][1][0] = 99
        archive[0]["objectives"][0] = -99
        archive[0]["selected"] = 99
        exported = session.journal_plan()
        exported["archive"][0]["objectives"][0] = 88
        exported["priorities"][0] = 0.0
        self.assertEqual(session.journal_plan(), original)

    def test_all_event_fields_equal_legacy_for_repeated_draws_and_both_dimensions(self):
        for balanced in (False, True):
            for dimension in (0, 1):
                plan = operator_reference.freeze_selection(points(), dimension, balanced)
                session = fast.compile_selection(points(), dimension, balanced)
                counts = {point["id"]: point["selected"] for point in plan["archive"]}
                for draws in ([0, 0], [1, 2], [2, 1], [3, 3], [1, 1], [2, 2], [3, 0]):
                    side = neighbor(plan, draws)
                    before = deepcopy(counts)
                    expected = operator_reference.select_pair(plan, counts, list(draws), side)
                    actual = fast.select_prevalidated_pair(session, counts, list(draws), side)
                    self.assertEqual(actual, expected)
                    self.assertEqual(counts, before)
                    counts = actual["counts_after"]

    def test_frozen_priority_does_not_follow_working_counts(self):
        session = fast.compile_selection(points(), 0)
        counts = {point["id"]: point["selected"] for point in session.journal_plan()["archive"]}
        first = fast.select_prevalidated_pair(session, counts, [1, 2], 0)
        self.assertEqual(first["first_id"], "B")
        changed = {key: value + 100 for key, value in first["counts_after"].items()}
        again = fast.select_prevalidated_pair(session, changed, [1, 2], 0)
        self.assertEqual(again["first_id"], "B")
        self.assertEqual(again["first_priority"], first["first_priority"])

    def test_coordinate_and_tournament_ties_preserve_explicit_stable_order(self):
        archive = [
            {"id": "b", "objectives": [0, 2, 3], "selected": 0},
            {"id": "a", "objectives": [0, 3, 2], "selected": 0},
            {"id": "c", "objectives": [1, 1, 4], "selected": 0},
            {"id": "d", "objectives": [2, 0, 5], "selected": 0},
        ]
        session = fast.compile_selection(archive, 0)
        plan = session.journal_plan()
        self.assertEqual([point["id"] for point in plan["archive"]], ["a", "b", "c", "d"])
        counts = {point["id"]: 0 for point in plan["archive"]}
        for draws in ([1, 2], [2, 1]):
            expected = operator_reference.select_pair(plan, counts, draws, 1)
            actual = fast.select_prevalidated_pair(session, counts, draws, 1)
            self.assertEqual(actual, expected)
            self.assertEqual(actual["first_index"], draws[0])

    def test_singleton_has_no_draws_or_counter_increment(self):
        archive = [{"id": "single", "objectives": [1.0], "selected": 42}]
        session = fast.compile_selection(archive, None)
        counts = {"single": 99}
        actual = fast.select_prevalidated_pair(session, counts, [])
        expected = operator_reference.select_pair(session.journal_plan(), counts, [])
        self.assertEqual(actual, expected)
        self.assertEqual(actual["counts_after"], {"single": 99})
        self.assertIsNone(actual["first_priority"])

    def test_large_counters_keep_exact_legacy_fraction_rounding(self):
        archive = points()
        for point in archive:
            point["selected"] = 10 ** 400
        session = fast.compile_selection(archive, 0)
        plan = operator_reference.freeze_selection(archive, 0)
        self.assertEqual(session.journal_plan(), plan)
        counts = {point["id"]: point["selected"] for point in archive}
        self.assertEqual(fast.select_prevalidated_pair(session, counts, [1, 2], 0),
                         operator_reference.select_pair(plan, counts, [1, 2], 0))

    def test_invalid_archives_still_fail_at_the_compile_boundary(self):
        for archive, dimension in (([], 0),
                                   ([{"id": "x", "objectives": [0, 0], "selected": 0},
                                     {"id": "y", "objectives": [1, 1], "selected": 0}], 0),
                                   ([{"id": "x", "objectives": [0], "selected": True}], None)):
            with self.subTest(archive=archive), self.assertRaises(ValueError):
                fast.compile_selection(archive, dimension)
        with self.assertRaises(ValueError):
            fast.compile_selection(points(), True)

    def test_invalid_counter_maps_draws_and_neighbors_still_rejected(self):
        session = fast.compile_selection(points(), 0)
        counts = {point["id"]: point["selected"] for point in points()}
        for changed in ({"A": 0}, {**counts, "B": True}, {**counts, "C": 1}):
            with self.subTest(counts=changed), self.assertRaises(ValueError):
                fast.select_prevalidated_pair(session, changed, [1, 2], 0)
        for draws, side in (([], None), ((1, 2), 0), ([True, 1], 0), ([4], None),
                            ([0], 0), ([1], None), ([1], True)):
            with self.subTest(draws=draws, side=side), self.assertRaises(ValueError):
                fast.select_prevalidated_pair(session, counts, draws, side)
        with self.assertRaises(ValueError):
            fast.select_prevalidated_pair(session.journal_plan(), counts, [1, 2], 0)

    def test_complete_raw_logs_and_rng_equal_old_executor_for_full_and_partial_budgets(self):
        problem, masks, scores = fixture()
        for balanced in (False, True):
            for seed in (41001, 41002):
                for budget in (1, 12, 28, 29, 30, 58, 61, 87):
                    with self.subTest(balanced=balanced, seed=seed, budget=budget):
                        previous = old.run_archive_search(problem, masks, scores, balanced,
                            make_rngs(seed, 0, 0), budget)
                        current = fast.run_archive_search(problem, masks, scores, balanced,
                            make_rngs(seed, 0, 0), budget)
                        self.assertEqual(canonical(current), canonical(previous))
                        self.assertEqual(current["rng_final"], previous["rng_final"])
                        self.assertEqual(verify_archive_log(current)["verification_status"], "VERIFIED")

    def test_plan_compilation_occurs_once_per_generation_not_per_child(self):
        problem, masks, scores = fixture()
        with patch.object(fast, "compile_selection", wraps=fast.compile_selection) as compile_spy, \
             patch.object(fast, "select_prevalidated_pair", wraps=fast.select_prevalidated_pair) as select_spy:
            log = fast.run_archive_search(problem, masks, scores, True, make_rngs(41003, 0, 0), budget=61)
        self.assertEqual(compile_spy.call_count, len(log["generations"]))
        self.assertEqual(compile_spy.call_count, 3)
        self.assertEqual(select_spy.call_count, 61)
        self.assertEqual(verify_archive_log(log)["verification_status"], "VERIFIED")

    def test_first_generation_is_equal_for_balanced_and_unbalanced(self):
        problem, masks, scores = fixture()
        logs = [fast.run_archive_search(problem, masks, scores, balanced,
                make_rngs(41004, 0, 0), budget=61) for balanced in (False, True)]
        self.assertEqual(logs[0]["candidates"][:29], logs[1]["candidates"][:29])
        self.assertEqual(logs[0]["generations"][0]["rng_after"], logs[1]["generations"][0]["rng_after"])

    def test_100_bit_5000_query_singleton_fixture_preserves_all_accounting(self):
        problem = {"n": 100, "weights": [1] * 100, "profits": [1] * 100, "capacity": 0}
        masks = ["0" * 100] * 30
        scores = [{"weight": 0, "profit": 0, "feasible": True} for _ in masks]
        previous = old.run_archive_search(problem, masks, scores, True, make_rngs(41005, 0, 0), 5000)
        current = fast.run_archive_search(problem, masks, scores, True, make_rngs(41005, 0, 0), 5000)
        self.assertEqual(canonical(current), canonical(previous))
        self.assertEqual(current["summary"]["full_generations"], 172)
        self.assertEqual(current["summary"]["partial_children"], 12)
        self.assertEqual(current["rng_initial"]["selection"], current["rng_final"]["selection"])
        self.assertEqual(current["summary"]["final_archive"][0]["selected"], 0)
        self.assertEqual(verify_archive_log(current)["independent_score_checks"], 5030)

    def test_success_on_last_prefix_query_keeps_record_without_state_commit(self):
        problem = {"n": 4, "weights": [1] * 4, "profits": [1, 2, 3, 4], "capacity": 4}
        masks = ["0000"] * 30
        scores = [{"weight": 0, "profit": 0, "feasible": True} for _ in masks]
        rngs = make_rngs(41006, 0, 0)
        explicit_state = None
        # Bounded construction of a software-test input, never scientific seed
        # selection: force a nonempty first mutation to exercise the last query.
        for _ in range(64):
            state = deepcopy(rngs["mutation"].bit_generator.state)
            if any(rngs["mutation"].random(4) < 0.25):
                explicit_state = state
                break
        self.assertIsNotNone(explicit_state)
        rngs["mutation"].bit_generator.state = explicit_state
        old_rngs = make_rngs(41006, 0, 0)
        old_rngs["mutation"].bit_generator.state = deepcopy(explicit_state)
        previous = old.run_archive_search(problem, masks, scores, True, old_rngs, 1)
        current = fast.run_archive_search(problem, masks, scores, True, rngs, 1)
        self.assertEqual(canonical(current), canonical(previous))
        self.assertEqual(current["summary"]["best_call"], 1)
        self.assertGreater(current["summary"]["best_profit"], 0)
        self.assertEqual(current["summary"]["final_population"], list(range(30)))
        self.assertEqual(current["summary"]["final_archive"], current["initial_archive"])

    def test_public_seed_adapter_matches_raw_executor_and_does_not_accept_oracles(self):
        problem, masks, scores = fixture()
        initial = {"initial_masks": masks, "initial_scores": scores}
        expected = fast.run_archive_search(problem, masks, scores, True, make_rngs(41007, 0, 1), 30)
        self.assertEqual(fast.run(problem, initial, "balanced_gap", 41007, 0, 1, 30), expected)
        for method in ("classical", "lambda_own", "unknown"):
            with self.assertRaises(ValueError):
                fast.run(problem, initial, method, 41007, 0, 1, 1)
        for corrupted in ({**problem, "optimum": 99}, {**problem, "certificate": {}}):
            with self.assertRaises(ValueError):
                fast.run(corrupted, initial, "balanced_gap", 41007, 0, 1, 1)
        with self.assertRaises(ValueError):
            fast.run(problem, {**initial, "optimal_mask": "111111"}, "balanced_gap", 41007, 0, 1, 1)

    def test_raw_executor_has_no_verifier_or_io_and_wrong_ci_scope_blocks(self):
        source = inspect.getsource(fast)
        self.assertNotIn("verify_archive_log", source)
        self.assertNotIn("knapsack_verifier import", source)
        self.assertNotIn(".write_bytes(", source)
        problem, masks, scores = fixture()
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), \
             patch.object(fast, "make_rngs", side_effect=AssertionError("No RNG before execution gate")):
            with self.assertRaises(ValueError):
                fast.run(problem, {"initial_masks": masks, "initial_scores": scores},
                         "balanced_gap", 41008, 0, 0, 1)
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "other/repository"}):
            with self.assertRaises(ValueError):
                fast.run_archive_search(problem, masks, scores, True, make_rngs(41008, 0, 0), 1)


if __name__ == "__main__":
    unittest.main()

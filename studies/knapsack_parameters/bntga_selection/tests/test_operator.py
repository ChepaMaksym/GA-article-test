"""CI-only, evaluator-free unit cases for the preregistered operator.

All vectors below are instructional fixtures, never knapsack search results.
"""
from copy import deepcopy
import inspect
import math
import os
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.bntga_selection import operator
from studies.knapsack_parameters.bntga_selection.comparison import (
    build_journal, teaching_comparison,
)
from studies.knapsack_parameters.bntga_selection.verifier import verify_journal


def point(identity, coordinates, selected=0):
    return {"id": identity, "objectives": list(coordinates), "selected": selected}


def example(counts=(0, 0, 0, 0)):
    return [point(identity, coordinates, count) for identity, coordinates, count in
            zip("ABCD", ((0, 6), (2, 4), (3, 3), (6, 0)), counts, strict=True)]


def current_counts(plan):
    return {item["id"]: item["selected"] for item in plan["archive"]}


class OperatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("The registered unit checks execute only in GitHub Actions")

    def test_archive_empty_and_selection_empty_rejected(self):
        self.assertEqual(operator.update_archive([]), [])
        with self.assertRaises(ValueError):
            operator.freeze_selection([], None)

    def test_archive_all_minimization_and_exact_dominance(self):
        result = operator.update_archive([
            point("bad", [9, 9]), point("A", [0, 6]), point("B", [2, 4]),
            point("C", [3, 3]), point("D", [6, 0]), point("equal_bad", [3, 4]),
        ])
        self.assertEqual([item["id"] for item in result], list("ABCD"))
        self.assertEqual(result[0]["objectives"], [0.0, 6.0])
        self.assertEqual(type(result[0]["objectives"][0]), float)

    def test_archive_old_vector_wins_and_keeps_counter(self):
        old = example((3, 7, 4, 8))
        result = operator.update_archive([point("copyB", [2, 4], 999)], old)
        self.assertEqual(result, old)
        self.assertEqual(result[1]["id"], "B")
        self.assertEqual(result[1]["selected"], 7)

    def test_archive_last_new_vector_wins_and_resets_counter(self):
        result = operator.update_archive([
            point("first", [2, 4], 10), point("other", [0, 6], 22),
            point("last", [2, 4], 53),
        ])
        self.assertEqual([item["id"] for item in result], ["other", "last"])
        self.assertEqual([item["selected"] for item in result], [0, 0])

    def test_archive_new_point_removes_dominated_old_without_reordering(self):
        result = operator.update_archive([point("E", [1, 3])], example((1, 2, 3, 4)))
        self.assertEqual([item["id"] for item in result], ["A", "D", "E"])
        self.assertEqual([item["selected"] for item in result], [1, 4, 0])

    def test_archive_no_input_mutation_or_output_aliases(self):
        old = example((1, 2, 3, 4))
        new = [point("E", [1, 5], 99)]
        original = deepcopy((old, new))
        result = operator.update_archive(new, old)
        self.assertEqual((old, new), original)
        result[0]["objectives"][0] = 999
        result[-1]["selected"] = 999
        self.assertEqual((old, new), original)

    def test_point_schema_and_numeric_edge_cases_rejected(self):
        malformed = [
            {"id": "A", "objectives": [0, 1], "selected": 0, "optimum": 5},
            point("", [0, 1]), point("  ", [0, 1]), point("A", []),
            point("A", [True, 1]), point("A", [math.nan, 1]),
            point("A", [math.inf, 1]), point("A", [-math.inf, 1]),
            point("A", ["1", 1]), point("A", [1, 2], -1),
            point("A", [1, 2], True), point("A", [1, 2], 1.0),
        ]
        for bad in malformed:
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError):
                    operator.update_archive([bad])

    def test_dimension_and_identity_conflicts_rejected_even_if_dominated(self):
        cases = [
            [point("A", [0, 1]), point("B", [1])],
            [point("A", [0, 1]), point("A", [2, 3])],
        ]
        for batch in cases:
            with self.assertRaises(ValueError):
                operator.update_archive(batch)
        with self.assertRaises(ValueError):
            operator.update_archive([point("A", [9, 9])], [point("A", [0, 0])])

    def test_existing_must_be_unique_and_nondominated(self):
        for invalid in (
            [point("A", [0, 1]), point("A", [0, 1])],
            [point("A", [0, 1]), point("B", [0, 1])],
            [point("A", [0, 0]), point("B", [1, 1])],
        ):
            with self.assertRaises(ValueError):
                operator.update_archive([], invalid)

    def test_same_id_same_vector_new_duplicate_is_allowed(self):
        result = operator.update_archive([point("A", [0, 1], 8), point("A", [0, 1], 3)])
        self.assertEqual(result, [point("A", [0.0, 1.0], 0)])

    def test_finite_edge_and_internal_max_neighbor_gap(self):
        plan = operator.freeze_selection(example(), 0, balanced=False)
        self.assertEqual(plan["gaps"], [operator.FLOAT32_MAX, 2.0, 3.0, operator.FLOAT32_MAX])
        self.assertTrue(all(math.isfinite(value) for value in plan["gaps"]))
        self.assertEqual(plan["priorities"], plan["gaps"])

    def test_balanced_snapshot_changes_only_priority_denominator(self):
        archive = example((0, 0, 2, 0))
        raw = operator.freeze_selection(archive, 0, balanced=False)
        balanced = operator.freeze_selection(archive, 0, balanced=True)
        self.assertEqual(raw["archive"], balanced["archive"])
        self.assertEqual(raw["gaps"], balanced["gaps"])
        self.assertEqual(raw["priorities"][1:3], [2.0, 3.0])
        self.assertEqual(balanced["priorities"][1:3], [2.0, 1.0])
        counts = current_counts(raw)
        self.assertEqual(operator.select_pair(raw, counts, [1, 2], 0)["first_id"], "C")
        self.assertEqual(operator.select_pair(balanced, counts, [1, 2], 0)["first_id"], "B")

    def test_all_zero_counts_have_identical_selection(self):
        plans = [operator.freeze_selection(example(), 0, balanced=value) for value in (False, True)]
        self.assertEqual(plans[0]["priorities"], plans[1]["priorities"])
        first = operator.select_pair(plans[0], current_counts(plans[0]), [1, 2], 0)
        second = operator.select_pair(plans[1], current_counts(plans[1]), [1, 2], 0)
        self.assertEqual(first, second)

    def test_priorities_frozen_while_counts_evolve(self):
        plan = operator.freeze_selection(example(), 0, balanced=True)
        original_plan = deepcopy(plan)
        first = operator.select_pair(plan, current_counts(plan), [2, 2], 0)
        second = operator.select_pair(plan, first["counts_after"], [1, 2], 0)
        self.assertEqual(second["first_id"], "C")
        self.assertEqual(second["first_priority"], 3.0)
        self.assertEqual(plan, original_plan)
        updated = [{**item, "selected": second["counts_after"][item["id"]]}
                   for item in plan["archive"]]
        refreshed = operator.freeze_selection(updated, 0, balanced=True)
        self.assertEqual(operator.select_pair(refreshed, current_counts(refreshed), [1, 2], 0)["first_id"], "B")

    def test_tournament_replacement_and_first_draw_ties(self):
        plan = operator.freeze_selection(example(), 0, balanced=False)
        event = operator.select_pair(plan, current_counts(plan), [3, 0, 3], None)
        self.assertEqual((event["first_id"], event["second_id"]), ("D", "C"))
        self.assertEqual(event["tournament_draws"], [3, 0, 3])
        self.assertEqual(event["counts_after"], {"A": 0, "B": 0, "C": 1, "D": 1})

    def test_adjacent_neighbor_directions_and_boundaries(self):
        plan = operator.freeze_selection(example(), 0)
        counts = current_counts(plan)
        self.assertEqual(operator.select_pair(plan, counts, [1], 0)["second_id"], "C")
        self.assertEqual(operator.select_pair(plan, counts, [1], 1)["second_id"], "A")
        self.assertEqual(operator.select_pair(plan, counts, [0], None)["second_id"], "B")
        self.assertEqual(operator.select_pair(plan, counts, [3], None)["second_id"], "C")
        for draws, side in (([0], 0), ([3], 1), ([1], None), ([1], True), ([1], 2)):
            with self.assertRaises(ValueError):
                operator.select_pair(plan, counts, draws, side)

    def test_singleton_no_random_draw_and_no_counter_change(self):
        plan = operator.freeze_selection([point("only", [4], 17)], None)
        self.assertEqual(plan["gaps"], [None])
        self.assertEqual(plan["priorities"], [None])
        event = operator.select_pair(plan, {"only": 19}, [], None)
        self.assertTrue(event["singleton"])
        self.assertEqual((event["first_id"], event["second_id"]), ("only", "only"))
        self.assertEqual(event["counts_before"], event["counts_after"])
        for dimension in (0, True):
            with self.assertRaises(ValueError):
                operator.freeze_selection([point("only", [4])], dimension)
        for draws, side in (([0], None), ([], 0)):
            with self.assertRaises(ValueError):
                operator.select_pair(plan, {"only": 19}, draws, side)

    def test_one_objective_archive_collapses_for_both_profiles(self):
        points = [point("worse", [9]), point("best1", [2]),
                  point("best2", [2]), point("other", [5])]
        blocks = [{"dimension": None, "requests": [
            {"tournament_draws": [], "neighbor_side": None}], "new_points": []}]
        journals = [build_journal(points, blocks, balanced) for balanced in (False, True)]
        for journal in journals:
            self.assertEqual(journal["final_archive"], [point("best2", [2.0], 0)])
            self.assertEqual(verify_journal(journal)["selection_pairs"], 1)
        self.assertEqual(journals[0]["blocks"][0]["events"], journals[1]["blocks"][0]["events"])

    def test_stable_coordinate_ties_use_case_sensitive_id_order(self):
        archive = [point("a", [0, 1, 3]), point("Z", [0, 2, 2]), point("C", [1, 0, 1])]
        plan = operator.freeze_selection(archive, 0)
        self.assertEqual([item["id"] for item in plan["archive"]], ["Z", "a", "C"])

    def test_zero_internal_gap_and_arbitrary_integer_counts(self):
        archive = [point("A", [1, 0, 2]), point("B", [1, 1, 1], 10**1000),
                   point("C", [1, 2, 0])]
        plan = operator.freeze_selection(archive, 0)
        self.assertEqual(plan["gaps"][1], 0.0)
        self.assertEqual(plan["priorities"][1], 0.0)
        large = operator.freeze_selection(example((10**1000, 0, 0, 0)), 0)
        self.assertEqual(large["priorities"][0], 0.0)

    def test_nonfinite_or_overlarge_gap_rejected_without_clipping(self):
        for magnitude in (operator.FLOAT32_MAX * 2, 1e308):
            archive = [point("A", [-magnitude, magnitude]), point("B", [magnitude, -magnitude])]
            with self.assertRaises(ValueError):
                operator.freeze_selection(archive, 0)

    def test_frozen_plan_and_invalid_counter_or_draw_tampering_rejected(self):
        plan = operator.freeze_selection(example((0, 1, 0, 0)), 0)
        for bad_counts in ({"A": 0}, {"A": 0, "B": 0, "C": 0, "D": 0},
                           {"A": 0, "B": True, "C": 0, "D": 0}):
            with self.assertRaises(ValueError):
                operator.select_pair(plan, bad_counts, [1], 0)
        for draws in ([], [True], [-1], [4], (1,)):
            with self.assertRaises(ValueError):
                operator.select_pair(plan, current_counts(plan), draws, 0)
        for field in ("gaps", "priorities"):
            corrupt = deepcopy(plan)
            corrupt[field][1] += 0.5
            with self.assertRaises(ValueError):
                operator.select_pair(corrupt, current_counts(plan), [1], 0)

    def test_operator_no_mutation_or_output_aliasing(self):
        points = example((0, 1, 2, 0))
        original = deepcopy(points)
        plan = operator.freeze_selection(points, 0)
        self.assertEqual(points, original)
        original_plan = deepcopy(plan)
        counts = current_counts(plan)
        original_counts = dict(counts)
        draws = [1, 2]
        event = operator.select_pair(plan, counts, draws, 0)
        event["counts_after"]["B"] = 1000
        event["tournament_draws"].append(0)
        self.assertEqual(plan, original_plan)
        self.assertEqual(counts, original_counts)
        self.assertEqual(draws, [1, 2])

    def test_teaching_pair_preconditioning_equal_then_choice_differs(self):
        result = teaching_comparison()
        raw = result["profiles"]["unbalanced_gap"]["journal"]
        balanced = result["profiles"]["balanced_gap"]["journal"]
        self.assertEqual(raw["initial_points"], balanced["initial_points"])
        self.assertEqual(raw["blocks"][0]["events"], balanced["blocks"][0]["events"])
        self.assertEqual(raw["blocks"][0]["events"][-1]["counts_after"],
                         {"A": 0, "B": 0, "C": 2, "D": 2})
        self.assertEqual(result["decisive_comparison"]["unbalanced_gap"]["first_parent"], "C")
        self.assertEqual(result["decisive_comparison"]["balanced_gap"]["first_parent"], "B")
        self.assertEqual(result["accounting"]["new_fitness_evaluations"], 0)

    def test_journal_archive_updates_count_carry_and_reset(self):
        blocks = [
            {"dimension": 0, "requests": [{"tournament_draws": [1, 1], "neighbor_side": 0}],
             "new_points": [point("E", [1, 5], 99), point("Bcopy", [2, 4], 98),
                            point("Ccopy", [3, 3], 97), point("bad", [9, 9], 96)]},
            {"dimension": 0, "requests": [{"tournament_draws": [2, 2], "neighbor_side": 1}],
             "new_points": []},
        ]
        journal = build_journal(example(), blocks, True)
        receipt = verify_journal(journal)
        self.assertEqual(receipt, {"status": "VERIFIED", "selection_pairs": 2,
                                  "objective_vectors_supplied": 8, "new_fitness_evaluations": 0})
        counts = {item["id"]: item["selected"] for item in journal["final_archive"]}
        self.assertEqual(counts, {"A": 0, "B": 2, "C": 1, "D": 0, "E": 1})

    def test_journal_is_deterministic_and_does_not_mutate_inputs(self):
        points = example((0, 8, 2, 4))
        blocks = [{"dimension": 0, "requests": [
            {"tournament_draws": [1, 2], "neighbor_side": 0}], "new_points": []}]
        original = deepcopy((points, blocks))
        first = build_journal(points, blocks, True)
        second = build_journal(points, blocks, True)
        self.assertEqual(first, second)
        self.assertEqual((points, blocks), original)
        self.assertTrue(all(item["selected"] == 0 for item in first["initial_archive"]))
        self.assertEqual(verify_journal(first)["status"], "VERIFIED")

    def test_verifier_has_no_production_import_and_runs_without_operator(self):
        journal = build_journal(example(), [], True)
        with patch.object(operator, "update_archive", side_effect=AssertionError("production archive used")), \
             patch.object(operator, "freeze_selection", side_effect=AssertionError("production gap used")), \
             patch.object(operator, "select_pair", side_effect=AssertionError("production selection used")):
            self.assertEqual(verify_journal(journal)["status"], "VERIFIED")
        source = inspect.getsource(inspect.getmodule(verify_journal))
        self.assertNotIn("from .operator import", source)
        self.assertNotIn("from .comparison import", source)

    def test_verifier_enforces_ci_identity(self):
        journal = build_journal(example(), [], True)
        for key, value in (("GITHUB_ACTIONS", "false"), ("GITHUB_REPOSITORY", "other/repo"),
                           ("GITHUB_REF", "refs/heads/main")):
            with patch.dict(os.environ, {key: value}):
                with self.assertRaises(ValueError):
                    verify_journal(journal)

    def test_verifier_rejects_corrupted_or_unregistered_journal_fields(self):
        pristine = teaching_comparison()["profiles"]["balanced_gap"]["journal"]
        modifications = [
            lambda data: data.update({"optimum": 1}),
            lambda data: data["accounting"].update({"new_fitness_evaluations": 1}),
            lambda data: data["accounting"].update({"selection_pairs": True}),
            lambda data: data["initial_archive"][0].update({"selected": True}),
            lambda data: data["blocks"][1]["plan"]["priorities"].__setitem__(1, 9.0),
            lambda data: data["blocks"][1]["events"][0].update({"first_id": "C"}),
            lambda data: data["blocks"][0]["events"][0]["counts_after"].update({"C": 20}),
            lambda data: data["blocks"][1]["requests"][0].update({"tournament_draws": [True, 2]}),
            lambda data: data["blocks"][1]["plan"].update({"balanced": False}),
            lambda data: data["blocks"][0]["plan"]["gaps"].__setitem__(0, math.inf),
            lambda data: data["blocks"][0]["events"].pop(),
            lambda data: data["final_archive"].pop(),
        ]
        for index, modify in enumerate(modifications):
            with self.subTest(corruption=index):
                damaged = deepcopy(pristine)
                modify(damaged)
                with self.assertRaises(ValueError):
                    verify_journal(damaged)

    def test_journal_builder_rejects_unknown_fields_and_never_accepts_evaluator(self):
        for blocks in (
            [{"dimension": 0, "requests": [], "new_points": [], "evaluator": None}],
            [{"dimension": 0, "requests": [{"tournament_draws": [1], "neighbor_side": 0,
                                            "fitness": 20}], "new_points": []}],
        ):
            with self.assertRaises(ValueError):
                build_journal(example(), blocks, True)
        self.assertEqual(build_journal([], [], True)["accounting"]["new_fitness_evaluations"], 0)


if __name__ == "__main__":
    unittest.main()

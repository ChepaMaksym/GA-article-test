"""Deterministic preparation fixtures; every execution is confined to CI."""

from dataclasses import replace
from itertools import combinations, product
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.feasibility import ascent, solvers
from studies.knapsack_parameters.feasibility.data_audit import Instance


def make_instance(profits, weights, capacity):
    return Instance(len(profits), capacity, tuple(profits), tuple(weights),
                    "fixture.kp", "UC", "s000", 0)


def independently_best_neighbor(instance, mask):
    """Test-only brute force: fresh full sums, not the ascent delta helper."""
    center_profit = sum(p for p, bit in zip(instance.profits, mask) if bit == "1")
    candidates = []
    for distance in (1, 2):
        for flips in combinations(range(instance.n), distance):
            bits = [int(bit) for bit in mask]
            for index in flips:
                bits[index] ^= 1
            weight = sum(w * bit for w, bit in zip(instance.weights, bits))
            profit = sum(p * bit for p, bit in zip(instance.profits, bits))
            if weight <= instance.capacity and profit > center_profit:
                candidates.append((profit, flips, weight))
    if not candidates:
        return None
    greatest = max(row[0] for row in candidates)
    return min((row for row in candidates if row[0] == greatest), key=lambda row: row[1])


class DeterministicAscentTests(unittest.TestCase):
    def test_registered_teaching_center_is_natural_but_not_certified(self):
        instance = make_instance((10, 8, 8), (6, 5, 5), 10)
        prepared = ascent.prepare_center(instance)
        self.assertEqual(prepared["greedy"]["mask"], "100")
        self.assertEqual(prepared["center"], {"mask": "100", "weight": 6, "profit": 10})
        self.assertTrue(prepared["natural_stop"])
        self.assertFalse(prepared["preparation_capped"])
        self.assertFalse(prepared["independent_certificate_issued"])
        self.assertEqual(prepared["passes_completed"], 1)
        self.assertEqual(prepared["neighbor_queries"], 6)
        self.assertIsNone(prepared["pass_trace"][0]["flipped_indices"])
        self.assertIsNone(independently_best_neighbor(instance, "100"))
        self.assertEqual(solvers.solve_capacity(instance)["optimum_profit"], 16)

    def test_greedy_exact_ratios_and_original_index_ties(self):
        instance = make_instance((2, 4, 3), (1, 2, 3), 2)
        self.assertEqual(ascent.greedy_start(instance)["item_order"], [0, 1, 2])
        self.assertEqual(ascent.greedy_start(instance)["mask"], "100")
        huge = 1 << 60
        near_equal = make_instance((huge + 2, huge + 1), (huge + 1, huge), huge)
        prepared = ascent.greedy_start(near_equal)
        self.assertEqual(prepared["item_order"], [1, 0])
        self.assertEqual(prepared["mask"], "01")

    def test_sorted_ratio_order_never_reorders_mask_bits(self):
        instance = make_instance((1, 8, 10), (1, 5, 6), 10)
        greedy = ascent.greedy_start(instance)
        self.assertEqual(greedy["item_order"], [2, 1, 0])
        self.assertEqual(greedy["mask"], "101")
        self.assertEqual(greedy["weight"], 7)
        self.assertEqual(greedy["profit"], 11)

    def test_best_neighbor_lex_tie_across_single_and_pair_moves(self):
        first = make_instance((2, 1, 1), (2, 1, 1), 2)
        second = make_instance((1, 1, 2), (1, 1, 2), 2)
        a = ascent._best_neighbor(first, [0, 0, 0], 0, 0, None)
        b = ascent._best_neighbor(second, [0, 0, 0], 0, 0, None)
        self.assertEqual(a["flipped_indices"], (0,))
        self.assertEqual(b["flipped_indices"], (0, 1))
        self.assertEqual(a["neighbor_queries"], 6)
        self.assertEqual(b["neighbor_queries"], 6)

    def test_all_small_neighbor_choices_match_independent_enumeration(self):
        for profits in product((1, 2), repeat=3):
            for weights in product((1, 2), repeat=3):
                for capacity in range(1, sum(weights) + 1):
                    instance = make_instance(profits, weights, capacity)
                    for bit_tuple in product((0, 1), repeat=3):
                        weight = sum(w * bit for w, bit in zip(weights, bit_tuple))
                        if weight > capacity:
                            continue
                        profit = sum(p * bit for p, bit in zip(profits, bit_tuple))
                        mask = "".join(str(bit) for bit in bit_tuple)
                        expected = independently_best_neighbor(instance, mask)
                        actual = ascent._best_neighbor(instance, list(bit_tuple), weight, profit, None)
                        with self.subTest(profits=profits, weights=weights, capacity=capacity, mask=mask):
                            self.assertEqual(actual["neighbor_queries"], 6)
                            self.assertEqual(actual["feasible_neighbors"] + actual["infeasible_neighbors"], 6)
                            if expected is None:
                                self.assertIsNone(actual["flipped_indices"])
                            else:
                                self.assertEqual((actual["profit"], actual["flipped_indices"], actual["weight"]), expected)

    def test_full_ascent_journal_replays_strict_feasible_best_moves(self):
        instance = make_instance((5, 6, 7), (3, 4, 5), 9)
        prepared = ascent.prepare_center(instance)
        self.assertEqual(prepared["greedy"]["mask"], "110")
        self.assertEqual(prepared["center"], {"mask": "011", "weight": 9, "profit": 13})
        self.assertTrue(prepared["natural_stop"])
        self.assertEqual(prepared["passes_completed"], 2)
        self.assertEqual(prepared["neighbor_queries"], 12)
        for row in prepared["pass_trace"]:
            expected = independently_best_neighbor(instance, row["center_before"]["mask"])
            if row["strict_improvement"]:
                self.assertEqual(row["flipped_indices"], list(expected[1]))
                self.assertEqual(row["center_after"]["profit"], expected[0])
                self.assertGreater(row["center_after"]["profit"], row["center_before"]["profit"])
                self.assertLessEqual(row["center_after"]["weight"], instance.capacity)
            else:
                self.assertIsNone(expected)
                self.assertEqual(row["center_after"], row["center_before"])

    def test_last_allowed_improvement_is_capped_even_if_global(self):
        instance = make_instance((5, 6, 7), (3, 4, 5), 9)
        prepared = ascent.prepare_center(instance, max_passes=1)
        self.assertEqual(prepared["center"]["profit"], 13)
        self.assertFalse(prepared["natural_stop"])
        self.assertTrue(prepared["preparation_capped"])
        self.assertEqual(prepared["status"], "EXCLUDED_PREPARATION_CAP")
        self.assertFalse(prepared["independent_certificate_issued"])
        self.assertEqual(solvers.solve_profit(instance)["optimum_profit"], 13)

    def test_nonimproving_last_allowed_pass_is_natural(self):
        instance = make_instance((10, 8, 8), (6, 5, 5), 10)
        prepared = ascent.prepare_center(instance, max_passes=1)
        self.assertTrue(prepared["natural_stop"])
        self.assertFalse(prepared["preparation_capped"])

    def test_exact_hundred_pass_cap_with_controlled_unit_start(self):
        # Injected starting mask is a unit fixture, not the registered greedy
        # preparation.  Real neighborhood scans make 100 strict two-bit moves.
        instance = make_instance((1,) * 201, (1,) * 201, 201)
        synthetic_start = {"mask": "0" * 201, "weight": 0, "profit": 0,
                           "item_order": list(range(201)), "items_considered": 201}
        with patch.object(ascent, "greedy_start", return_value=synthetic_start):
            prepared = ascent.prepare_center(instance)
        self.assertEqual(prepared["passes_completed"], 100)
        self.assertEqual(prepared["center"]["profit"], 200)
        self.assertTrue(prepared["preparation_capped"])
        self.assertFalse(prepared["independent_certificate_issued"])
        self.assertEqual(prepared["neighbor_queries"], 100 * (201 + 201 * 200 // 2))

    def test_plateau_and_global_center_are_not_ascent_admission_claims(self):
        plateau = make_instance((10, 8, 8, 10), (6, 5, 5, 6), 10)
        prepared = ascent.prepare_center(plateau)
        self.assertEqual(prepared["center"]["mask"], "1000")
        self.assertTrue(prepared["natural_stop"])
        self.assertFalse(prepared["independent_certificate_issued"])
        global_instance = make_instance((1, 2, 3), (1, 2, 3), 6)
        global_prepared = ascent.prepare_center(global_instance)
        self.assertEqual(global_prepared["center"]["mask"], "111")
        self.assertEqual(global_prepared["status"], "NATURAL_STOP_UNCERTIFIED")

    def test_preparation_is_deterministic_and_input_is_unchanged(self):
        instance = make_instance((5, 6, 7), (3, 4, 5), 9)
        self.assertEqual(ascent.prepare_center(instance), ascent.prepare_center(instance))
        self.assertEqual(instance.profits, (5, 6, 7))
        self.assertEqual(instance.weights, (3, 4, 5))

    def test_invalid_pass_limits_inputs_and_deadline(self):
        valid = make_instance((1, 2), (1, 2), 2)
        for passes in (0, 101, True, 1.0):
            with self.subTest(passes=passes), self.assertRaises(ValueError):
                ascent.prepare_center(valid, max_passes=passes)
        for invalid in (replace(valid, profits=(0, 2)), replace(valid, weights=(1,)),
                        replace(valid, capacity=True), replace(valid, n=0)):
            with self.assertRaises((ValueError, TypeError)):
                ascent.prepare_center(invalid)
        with patch.object(solvers.time, "monotonic", return_value=30):
            with self.assertRaises(solvers.PreparationDeadlineExceeded):
                ascent.prepare_center(valid, deadline=30)


if __name__ == "__main__":
    unittest.main()

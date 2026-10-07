"""Exact-method fixtures and exhaustive small cases, executed only in CI."""

from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.feasibility.data_audit import Instance
from studies.knapsack_parameters.feasibility import solvers


def make_instance(profits, weights, capacity):
    return Instance(len(profits), capacity, tuple(profits), tuple(weights),
                    "fixture.kp", "UC", "s000", 0)


def exhaustive_optimum(instance):
    best = 0
    for bits in product((0, 1), repeat=instance.n):
        weight = sum(instance.weights[i] for i in range(instance.n) if bits[i])
        profit = sum(instance.profits[i] for i in range(instance.n) if bits[i])
        if weight <= instance.capacity and profit > best:
            best = profit
    return best


class ExactSolverTests(unittest.TestCase):
    def assert_witness(self, instance, result, optimum):
        mask = result["witness_mask"]
        self.assertEqual(len(mask), instance.n)
        self.assertTrue(set(mask) <= {"0", "1"})
        weight = sum(w for w, bit in zip(instance.weights, mask) if bit == "1")
        profit = sum(p for p, bit in zip(instance.profits, mask) if bit == "1")
        self.assertLessEqual(weight, instance.capacity)
        self.assertEqual(profit, optimum)
        self.assertEqual(result["optimum_profit"], optimum)
        self.assertEqual(result["witness_weight"], weight)
        self.assertEqual(result["witness_profit"], profit)
        self.assertEqual(result["conceptual_cells"], (instance.n + 1) * (result["dimension"] + 1))

    def test_both_methods_exhaustive_all_small_positive_cases(self):
        # All item arrays with n=1..3 and p,w in1..3, at every positive
        # capacity through the total weight.  No stochastic test selection.
        for n in range(1, 4):
            for profits in product(range(1, 4), repeat=n):
                for weights in product(range(1, 4), repeat=n):
                    for capacity in range(1, sum(weights) + 1):
                        instance = make_instance(profits, weights, capacity)
                        optimum = exhaustive_optimum(instance)
                        with self.subTest(profits=profits, weights=weights, capacity=capacity):
                            self.assert_witness(instance, solvers.solve_capacity(instance), optimum)
                            self.assert_witness(instance, solvers.solve_profit(instance), optimum)

    def test_registered_teaching_fixture(self):
        instance = make_instance((10, 8, 8), (6, 5, 5), 10)
        for solver in (solvers.solve_capacity, solvers.solve_profit):
            with self.subTest(solver=solver.__name__):
                result = solver(instance)
                self.assert_witness(instance, result, 16)
                self.assertEqual(result["witness_mask"], "011")

    def test_equality_excludes_current_item_and_retains_original_order(self):
        instance = make_instance((5, 5, 5), (2, 2, 2), 2)
        for solver in (solvers.solve_capacity, solvers.solve_profit):
            result = solver(instance)
            self.assert_witness(instance, result, 5)
            self.assertEqual(result["witness_mask"], "100")

    def test_zero_one_not_unbounded_and_no_mutable_backpointer(self):
        fixtures = [
            make_instance((3, 1), (2, 100), 4),
            make_instance((3, 4), (2, 3), 5),
            make_instance((2, 2, 3), (1, 1, 2), 2),
        ]
        for instance in fixtures:
            expected = exhaustive_optimum(instance)
            for solver in (solvers.solve_capacity, solvers.solve_profit):
                with self.subTest(instance=instance, solver=solver.__name__):
                    self.assert_witness(instance, solver(instance), expected)
        self.assertEqual(solvers.solve_capacity(fixtures[0])["optimum_profit"], 3)
        self.assertEqual(solvers.solve_capacity(fixtures[1])["witness_mask"], "11")

    def test_empty_optimum_all_fit_and_exact_capacity(self):
        for instance, expected in [
            (make_instance((3, 7), (2, 5), 1), 0),
            (make_instance((3, 7), (2, 5), 100), 10),
            (make_instance((3, 7), (2, 5), 7), 10),
        ]:
            for solver in (solvers.solve_capacity, solvers.solve_profit):
                self.assert_witness(instance, solver(instance), expected)
        self.assertEqual(solvers.solve_capacity(make_instance((3, 7), (2, 5), 100))["dimension"], 7)

    def test_profit_dp_handles_gaps_and_exact_unbounded_integer_weights(self):
        huge = 1 << 100
        instance = make_instance((2, 5, 7), (3, huge, 4), 7)
        result = solvers.solve_profit(instance)
        self.assert_witness(instance, result, 9)
        self.assertEqual(result["witness_mask"], "101")
        self.assertEqual(result["minimum_weight_at_optimum"], 7)
        self.assertEqual(result["unreachable_sentinel"], huge + 8)
        self.assert_witness(instance, solvers.solve_capacity(instance), 9)

    def test_method_witnesses_need_not_be_identical(self):
        instance = make_instance((5, 5), (3, 2), 3)
        first, second = solvers.solve_capacity(instance), solvers.solve_profit(instance)
        self.assert_witness(instance, first, 5)
        self.assert_witness(instance, second, 5)
        self.assertEqual(first["witness_mask"], "10")
        self.assertEqual(second["witness_mask"], "01")

    def test_invalid_inputs_rejected_before_allocation(self):
        valid = make_instance((2, 3), (1, 2), 2)
        malformed = [replace(valid, n=0), replace(valid, n=True),
                     replace(valid, capacity=0), replace(valid, capacity=2.0),
                     replace(valid, profits=(True, 3)), replace(valid, weights=(1, -1)),
                     replace(valid, profits=(2.0, 3)), replace(valid, weights=(1,)),
                     replace(valid, profits=[2, 3])]
        for instance in malformed:
            for solver in (solvers.solve_capacity, solvers.solve_profit):
                with self.subTest(instance=instance, solver=solver.__name__):
                    with self.assertRaises((TypeError, ValueError)):
                        solver(instance)
        with self.assertRaises(TypeError):
            solvers.solve_capacity(None)

    def test_registered_dimension_and_cell_guards(self):
        for instance in [make_instance((200001,), (1,), 1),
                         make_instance((1,), (200001,), 200001),
                         make_instance((1,) * 101, (198020,) + (1,) * 100, 198020)]:
            for solver in (solvers.solve_capacity, solvers.solve_profit):
                with self.subTest(instance_n=instance.n, solver=solver.__name__):
                    with self.assertRaises(solvers.ResourceLimitExceeded):
                        solver(instance)
        # n+1 item-prefix rows, not n transitions, define the registered cell
        # count. Ninety-nine items make this exact 20,000,100-cell boundary.
        boundary = make_instance((2000,) * 98 + (4000,), (2000,) * 98 + (4000,), 200000)
        plan = solvers.resource_plan(boundary)
        self.assertEqual(plan["capacity_cells"], 20000100)
        self.assertEqual(plan["profit_cells"], 20000100)

    def test_deadline_and_memory_are_typed_resource_failures(self):
        instance = make_instance((2,), (1,), 1)
        for solver in (solvers.solve_capacity, solvers.solve_profit):
            with patch.object(solvers.time, "monotonic", return_value=10):
                with self.assertRaises(solvers.PreparationDeadlineExceeded):
                    solver(instance, deadline=10)
            for deadline in (True, float("nan"), float("inf"), "now"):
                with self.subTest(deadline=deadline), self.assertRaises((TypeError, ValueError)):
                    solver(instance, deadline=deadline)
        with patch.object(solvers, "array", side_effect=MemoryError):
            with self.assertRaises(solvers.ResourceLimitExceeded):
                solvers.solve_capacity(instance)

    def test_profit_transition_is_independent_of_capacity_implementation(self):
        instance = make_instance((10, 8, 8), (6, 5, 5), 10)
        with patch.object(solvers, "solve_capacity", side_effect=AssertionError("shared transition forbidden")):
            self.assert_witness(instance, solvers.solve_profit(instance), 16)


if __name__ == "__main__":
    unittest.main()

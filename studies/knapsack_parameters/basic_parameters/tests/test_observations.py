from copy import deepcopy
import unittest

import numpy as np

from studies.knapsack_parameters.basic_parameters.observations import record_history, verify_history


def fixture():
    return {"requests": {"profit": np.array([0, 10, 90, 12, 12, 99]),
                         "feasible": np.array([True, True, False, True, True, True])},
            "summary": {"logical_requests": 6, "best_request": 6, "best_profit": 99}}


class ObservationTests(unittest.TestCase):
    def test_final_prefix_and_invalid_are_handled(self):
        result = fixture()
        self.assertEqual(record_history(result), [
            {"request": 1, "profit": 0}, {"request": 2, "profit": 10},
            {"request": 4, "profit": 12}, {"request": 6, "profit": 99}])

    def test_missing_record_and_duplicate_record_are_rejected(self):
        result = fixture()
        expected = record_history(result)
        for bad in (expected[:2] + expected[3:], expected[:2] + [expected[1]] + expected[2:]):
            with self.assertRaises(ValueError):
                verify_history(result, bad)

    def test_wrong_first_request_or_value_rejected(self):
        result = fixture()
        expected = record_history(result)
        for key in ("request", "profit"):
            bad = deepcopy(expected)
            bad[1][key] += 1
            with self.assertRaises(ValueError):
                verify_history(result, bad)

    def test_no_improvement_and_initial_record(self):
        result = {"requests": {"profit": np.array([0, 10, 8, 10]), "feasible": np.ones(4, dtype=bool)},
                  "summary": {"logical_requests": 4, "best_request": 2, "best_profit": 10}}
        self.assertEqual(record_history(result), [{"request": 1, "profit": 0}, {"request": 2, "profit": 10}])

    def test_history_not_given_to_search(self):
        import inspect
        from studies.knapsack_parameters.ga_study.engine import run_search
        self.assertNotIn("record_history", inspect.signature(run_search).parameters)
        self.assertNotIn("optimum", inspect.signature(run_search).parameters)

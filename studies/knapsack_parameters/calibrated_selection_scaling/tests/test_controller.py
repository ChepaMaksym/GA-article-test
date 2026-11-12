"""Exact complete-generation threshold and calibrated immutable-state checks."""
from copy import deepcopy
from fractions import Fraction
import unittest

from studies.knapsack_parameters.calibrated_selection_scaling.program.ga_core.controllers import (
    update_calibrated_selection_parameters,
    validate_calibrated_initial_parameters,
)
from studies.knapsack_parameters.calibrated_selection_scaling.tests.helpers import configured, require_ci


def update(parameters, failed=0, success=False, *, initial=None, count=None,
           profile="adaptive", n=500, novelty=Fraction(1, 2)):
    require_ci()
    if initial is None:
        initial = configured(mu=parameters["target_mu"], n=n,
                             pc=parameters["p_c"], profile=profile)
    return update_calibrated_selection_parameters(
        parameters, failed, success, parameters["target_mu"] - 1 if count is None else count,
        novelty, n, profile, initial_parameters=initial)


class CalibratedControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_ci()

    def test_initial_validation_copies_each_calibrated_configuration(self):
        for n, mu, pc in ((100, 15, 1.), (500, 20, .9), (500, 25000, 0.)):
            for profile in ("k2", "k3", "adaptive"):
                parameters = configured(mu=mu, n=n, pc=pc, profile=profile)
                result = validate_calibrated_initial_parameters(parameters, n, profile)
                self.assertEqual(result, parameters)
                self.assertIsNot(result, parameters)

    def test_threshold_145_is_exact_and_success_has_priority(self):
        parameters = configured(mu=10, n=500, profile="adaptive")
        parameters["tournament_size"] = 3
        before = update(parameters, failed=135)
        self.assertEqual(before["event"], "NO_CHANGE")
        self.assertEqual(before["failed_queries_accumulated"], 144)
        self.assertEqual(before["failed_queries_after"], 144)
        self.assertEqual(before["parameters"]["tournament_size"], 3)
        at = update(parameters, failed=136)
        self.assertEqual(at["event"], "STAGNATION")
        self.assertEqual(at["failed_queries_accumulated"], 145)
        self.assertEqual(at["failed_queries_after"], 0)
        self.assertEqual(at["stagnation_overshoot"], 0)
        self.assertEqual(at["parameters"]["tournament_size"], 2)
        success = update(parameters, failed=144, success=True)
        self.assertEqual(success["event"], "SUCCESS")
        self.assertEqual(success["failed_queries_accumulated"], 0)
        self.assertEqual(success["failed_queries_after"], 0)
        self.assertEqual(success["stagnation_overshoot"], 0)
        self.assertEqual(success["parameters"]["tournament_size"], 4)

    def test_threshold_counts_full_generation_offspring_not_generations(self):
        initial = configured(mu=20, n=500, profile="adaptive")
        parameters = {**initial, "tournament_size": 4}
        failed = 0
        for generation in range(1, 9):
            result = update(parameters, failed=failed, initial=initial)
            if generation < 8:
                self.assertEqual(result["event"], "NO_CHANGE")
                self.assertEqual(result["failed_queries_after"], 19 * generation)
                self.assertEqual(result["parameters"]["tournament_size"], 4)
            else:
                self.assertEqual(result["event"], "STAGNATION")
                self.assertEqual(result["failed_queries_accumulated"], 152)
                self.assertEqual(result["stagnation_overshoot"], 7)
                self.assertEqual(result["failed_queries_after"], 0)
                self.assertEqual(result["parameters"]["tournament_size"], 3)
            parameters, failed = result["parameters"], result["failed_queries_after"]

    def test_large_generation_reports_overshoot_without_carrying_it(self):
        for mu in (146, 1000, 25000):
            with self.subTest(mu=mu):
                parameters = configured(mu=mu, n=500, profile="adaptive")
                parameters["tournament_size"] = 4
                result = update(parameters, failed=144)
                self.assertEqual(result["event"], "STAGNATION")
                self.assertEqual(result["failed_queries_accumulated"], 144 + mu - 1)
                self.assertEqual(result["stagnation_overshoot"], mu - 2)
                self.assertEqual(result["failed_queries_after"], 0)
                self.assertEqual(result["parameters"]["tournament_size"], 3)

    def test_only_adaptive_selection_changes_and_both_caps_are_closed(self):
        for k, success, expected, event_name in ((2, False, 2, "STAGNATION"),
                                                (3, False, 2, "STAGNATION"),
                                                (4, True, 5, "SUCCESS"),
                                                (5, True, 5, "SUCCESS")):
            parameters = configured(mu=20, n=500, pc=1., profile="adaptive")
            parameters["tournament_size"] = k
            result = update(parameters, failed=144, success=success)
            self.assertEqual(result["event"], event_name)
            self.assertEqual(result["parameters"]["tournament_size"], expected)
            self.assertEqual({name: value for name, value in result["parameters"].items()
                              if name != "tournament_size"},
                             {name: value for name, value in parameters.items()
                              if name != "tournament_size"})
            event = result["parameter_events"][3]
            self.assertEqual(event["enabled"], True)
            self.assertEqual(event["at_boundary"], expected in (2, 5))
            self.assertEqual(event["direction"], "increase" if expected > k else
                             "decrease" if expected < k else "unchanged")
        for profile in ("k2", "k3"):
            for success in (False, True):
                parameters = configured(mu=20, n=500, pc=1., profile=profile)
                result = update(parameters, failed=144, success=success, profile=profile)
                self.assertEqual(result["parameters"], parameters)
                self.assertTrue(all(not entry["enabled"] for entry in result["parameter_events"]))

    def test_event_bounds_retain_historical_monitoring_meaning(self):
        parameters = configured(mu=20, n=500, pc=1., profile="k3")
        result = update(parameters, profile="k3")
        expected_flags = {"p_m": False, "p_c": False, "target_mu": False,
                          "tournament_size": False, "elite_count": True}
        self.assertEqual({entry["field"]: entry["at_boundary"] for entry in result["parameter_events"]},
                         expected_flags)
        parameters = configured(mu=100, n=100, pc=.9, profile="k2")
        result = update(parameters, profile="k2", n=100)
        self.assertTrue(all(entry["at_boundary"] for entry in result["parameter_events"]))

    def test_disabled_parameters_must_match_original_configured_values(self):
        initial = configured(mu=20, n=500, pc=.9, profile="adaptive")
        for field, replacement in (("p_m", .01), ("p_c", 1.), ("target_mu", 30), ("elite_count", 2)):
            with self.subTest(field=field):
                parameters = {**initial, field: replacement}
                with self.assertRaises(ValueError):
                    update(parameters, initial=initial)
        result = update({**initial, "tournament_size": 5}, initial=initial)
        self.assertEqual(result["parameters"]["tournament_size"], 5)
        for profile in ("k2", "k3"):
            initial = configured(mu=20, n=500, profile=profile)
            with self.assertRaises(ValueError):
                update({**initial, "tournament_size": 4}, initial=initial, profile=profile)

    def test_controller_does_not_mutate_or_alias_caller_state(self):
        initial = configured(mu=20, n=500, profile="adaptive")
        parameters = {**initial, "tournament_size": 3}
        expected = deepcopy((initial, parameters))
        result = update(parameters, success=True, initial=initial)
        self.assertEqual((initial, parameters), expected)
        self.assertIsNot(result["parameters"], parameters)
        self.assertIsNot(result["parameters"], initial)
        result["parameters"]["p_c"] = 0
        self.assertEqual((initial, parameters), expected)

    def test_equal_numeric_values_with_changed_disabled_types_are_rejected(self):
        initial = configured(mu=20, n=500, pc=1., profile="adaptive")
        for field, replacement in (("p_c", 1), ("target_mu", 20.), ("elite_count", True)):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    update({**initial, field: replacement}, initial=initial)

    def test_invalid_signals_partial_counts_and_current_k_are_rejected(self):
        parameters = configured(mu=20, n=500, profile="adaptive")
        for kwargs in ({"failed": -1}, {"failed": 145}, {"failed": True},
                       {"success": 1}, {"count": 18}, {"count": 20}, {"count": 0},
                       {"count": 19.}, {"novelty": .5}, {"novelty": Fraction(-1)},
                       {"novelty": Fraction(2)}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    update(parameters, **kwargs)
        for k in (1, 6, True, 2.):
            with self.assertRaises(ValueError):
                update({**parameters, "tournament_size": k})


if __name__ == "__main__":
    require_ci()
    unittest.main()

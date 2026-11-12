"""Frozen identity counts, file boundaries and oracle-free entry points."""
from collections import Counter
import inspect
from pathlib import Path
import tempfile
import unittest

from studies.knapsack_parameters.calibrated_selection_scaling import configuration
from studies.knapsack_parameters.calibrated_selection_scaling.common import safe_relative
from studies.knapsack_parameters.calibrated_selection_scaling.program import ga_core
from studies.knapsack_parameters.calibrated_selection_scaling.search import execute_case
from studies.knapsack_parameters.calibrated_selection_scaling.tests.helpers import (
    CONTRACT, configured, fixture, require_ci, run_small,
)


class CalibratedContractBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_ci()

    def test_pilot_and_main_physical_identities_have_exact_coverage(self):
        pilot = configuration.technical_cases()
        main = configuration.main_cases()
        self.assertEqual(len(pilot), 21)
        self.assertEqual(len(main), 210)
        self.assertEqual(Counter(case["n"] for case in pilot), {100: 12, 500: 9})
        self.assertEqual(Counter(case["n"] for case in main), {100: 120, 500: 90})
        self.assertEqual({case["seed"] for case in pilot}, {180999})
        self.assertEqual({case["preparation_seed"] for case in pilot}, {180998})
        self.assertEqual({case["seed"] for case in main}, {181001})
        self.assertEqual({case["preparation_seed"] for case in main}, {181000})
        for cases, stage, expected_tasks in ((pilot, "technical", 6), (main, "main", 60)):
            self.assertEqual(len({case["case_id"] for case in cases}), len(cases))
            self.assertEqual(len({case["task_id"] for case in cases}), expected_tasks)
            self.assertTrue(all(case["stage"] == stage and case["configuration_contract"] == CONTRACT
                                and case["total_evaluations"] == 100000 for case in cases))
            groups = {}
            for case in cases:
                groups.setdefault((case["task_id"], case["seed"]), []).append(case)
            for values in groups.values():
                roles = {case["role"] for case in values}
                self.assertEqual(roles, {"k2", "k3", "adaptive", "common"}
                                 if values[0]["n"] == 100 else {"k2", "k3", "adaptive"})
                self.assertEqual(len(values), len(roles))
                self.assertEqual(len({case["task_index"] for case in values}), 1)

    def test_main_sources_are_pinned_and_families_do_not_overlap_pilots(self):
        main = configuration.task_descriptors("main")
        pilot = configuration.task_descriptors("technical")
        self.assertEqual(len(main), 60)
        self.assertEqual(len(pilot), 6)
        self.assertEqual(len({task["task_index"] for task in main + pilot}), 66)
        self.assertEqual({task["family"] for task in main}, {f"s{value:03d}" for value in range(70, 80)})
        self.assertEqual({task["family"] for task in pilot}, {"s000", "s001", "s005"})
        self.assertFalse({task["source_path"] for task in main} & {task["source_path"] for task in pilot})
        self.assertEqual(Counter(task["class_label"] for task in main), {"UC": 20, "WC": 20, "SC": 20})
        for task in main + pilot:
            self.assertEqual(task["url"], configuration.SOURCE_BASE + task["source_path"])
            self.assertIn("/" + configuration.SOURCE_COMMIT + "/", task["url"])
            self.assertIn(f"/n{task['n']:05d}/R01000/", task["source_path"])

    def test_compatibility_identities_preserve_six_legacy_new_query_budgets(self):
        cases = configuration.compatibility_cases()
        self.assertEqual(len(cases), 6)
        self.assertEqual(len({case["case_id"] for case in cases}), 6)
        self.assertEqual(len({case["reference_file"] for case in cases}), 6)
        self.assertEqual({(case["task_id"], case["profile"]) for case in cases},
                         {(task, profile) for task in ("UC-s040", "SC-s040")
                          for profile in ("k2", "k3", "adaptive")})
        for case in cases:
            self.assertEqual(case["seed"], 110001)
            self.assertEqual(case["new_evaluations"], 5000)
            self.assertNotIn("total_evaluations", case)
            self.assertEqual(case["initial_parameters"], configured(mu=30, n=100, profile=case["profile"]))

    def test_n100_common_control_is_distinct_and_n500_control_reuses_k2(self):
        tuned100 = configuration.baseline_parameters(100, "k2")
        common100 = configuration.baseline_parameters(100, "k2", common=True)
        self.assertEqual(tuned100, configured(mu=15, n=100, pc=1.))
        self.assertEqual(common100, configured(mu=20, n=100, pc=.9))
        self.assertEqual(configuration.baseline_parameters(500, "k2"), configured(mu=20, n=500, pc=.9))
        self.assertEqual(configuration.baseline_parameters(500, "k2", common=True),
                         configuration.baseline_parameters(500, "k2"))
        changed = configuration.baseline_parameters(100, "k2")
        changed["target_mu"] = 999
        self.assertEqual(configuration.baseline_parameters(100, "k2"), tuned100)

    def test_safe_relative_rejects_traversal_absolute_and_stream_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            accepted = safe_relative(root, "sources/n00100/UC-s070.kp")
            self.assertEqual(accepted, root / "sources/n00100/UC-s070.kp")
            for value in ("", ".", "..", "../outside", "a/../../outside", "/absolute", "//server/share",
                          "C:/outside", "C:relative", "a\\b", "a:stream", "https://example.com/file", None, 1):
                with self.subTest(relative=value):
                    with self.assertRaises(ValueError):
                        safe_relative(root, value)

    def test_safe_relative_rejects_symlink_escape_and_direct_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, outside = base / "root", base / "outside"
            root.mkdir()
            outside.mkdir()
            local_file = root / "local.json"
            local_file.write_text("{}", encoding="utf-8")
            try:
                (root / "escape").symlink_to(outside, target_is_directory=True)
                (root / "linked.json").symlink_to(local_file)
            except (OSError, NotImplementedError):
                self.skipTest("The CI filesystem does not support symbolic links")
            with self.assertRaises(ValueError):
                safe_relative(root, "escape/data.json")
            with self.assertRaises(ValueError):
                safe_relative(root, "linked.json")

    def test_search_api_excludes_optimum_and_certificate_arguments(self):
        for function in (ga_core.run_ga, execute_case):
            signature = inspect.signature(function)
            self.assertFalse(any(parameter.kind == inspect.Parameter.VAR_KEYWORD
                                 for parameter in signature.parameters.values()))
            self.assertFalse({"optimum", "OPT", "certificate", "reference_optimum"}
                             & set(signature.parameters))
        problem, initial = fixture()
        for name in ("optimum", "OPT", "certificate", "reference_optimum"):
            with self.subTest(oracle=name):
                with self.assertRaises(TypeError):
                    ga_core.run_ga(problem, initial, ga_core.tournament_controller("k2"),
                                   ga_core.create_random_generators(17, 4, 0), 1,
                                   initial_parameters=configured(), configuration_contract=CONTRACT,
                                   **{name: {"value": 100}})
                polluted = {**problem, name: {"value": 100}}
                with self.assertRaises(ValueError):
                    run_small(problem=polluted, initial=initial)
                case = configuration.technical_cases()[0]
                polluted_adapter = {"n": case["n"], "weights": [1] * case["n"],
                                    "profits": [1] * case["n"], "capacity": case["n"], name: 100}
                with self.assertRaises(ValueError):
                    execute_case(case, polluted_adapter, {})

    def test_missing_calibrated_contract_does_not_widen_historical_routes(self):
        for profile in ("k2", "k3", "adaptive"):
            with self.subTest(profile=profile):
                with self.assertRaises(ValueError):
                    run_small(profile=profile, contract=None)
        for field, value in (("p_c", 1.), ("tournament_size", 3), ("p_m", .01)):
            parameters = configured()
            parameters[field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    run_small(profile=0, parameters=parameters, contract=None)


if __name__ == "__main__":
    require_ci()
    unittest.main()

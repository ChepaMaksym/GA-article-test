"""CI-only checks for the 100-item validation wrapper.

These are synthetic programming fixtures, not registered study runs. Full
100000-evaluation pilot cases belong to the separate pilot command. Importing
the file does not run the GA; setUpClass requires the real CI environment.
Expected wrapper APIs are documented in README_TESTS.md.
"""
from copy import deepcopy
import hashlib
import inspect
import unittest

from .common import require_ci
from .preparation import make_bank, score, validate_source
from .pilot import make_log
from studies.knapsack_parameters.crossover_population.program.ga_core import (
    create_random_generators,
)
from studies.knapsack_parameters.crossover_population.observations import extract
from studies.knapsack_parameters.crossover_population.verification import verify_log


class ValidationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_ci()
        cls.problem = {"n": 100, "capacity": 100, "weights": [1] * 100, "profits": [1] * 100}
        cls.seed = 149999
        cls.task_index = 0
        cls.bank = make_bank(cls.problem, cls.task_index, cls.seed, 149998)

    def run_fixture(self, mu=20, total=80, *, bank=None, problem=None):
        return make_log(self.problem if problem is None else problem,
                        self.bank if bank is None else bank,
                        mu, self.seed, self.task_index, total=total)

    @staticmethod
    def scientific(log):
        # Execution time is observational; every scientific field remains bound.
        return {key: value for key, value in log.items() if key != "timing_ns"}

    @staticmethod
    def source_fixture():
        raw = b"100\n100\n" + b"1 1\n" * 100
        entry = {"source_path": "00Uncorrelated/n00100/R01000/s050.kp",
                 "bytes": len(raw),
                 "git_blob_sha1": hashlib.sha1(
                     b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()}
        return raw, entry

    def test_pinned_source_dimension_and_blob_are_checked(self):
        raw, entry = self.source_fixture()
        self.assertEqual(validate_source(raw, entry), self.problem)
        for bad_entry in ({**entry, "bytes": len(raw) + 1},
                          {**entry, "git_blob_sha1": "0" * 40},
                          {**entry, "source_sha256": "0" * 64},
                          {**entry, "source_path": "00Uncorrelated/n00500/R01000/s050.kp"}):
            with self.subTest(entry=bad_entry), self.assertRaises(ValueError):
                validate_source(raw, bad_entry)
        with self.assertRaises(ValueError):
            validate_source(raw.replace(b"100\n", b"101\n", 1), entry)

    def test_bank_has_empty_start_and_independent_scores(self):
        self.assertEqual((len(self.bank["masks"]), len(self.bank["scores"])), (30, 30))
        self.assertEqual(self.bank["masks"][0], "0" * 100)
        for mask, measured in zip(self.bank["masks"], self.bank["scores"], strict=True):
            self.assertEqual(len(mask), 100)
            self.assertLessEqual(set(mask), {"0", "1"})
            self.assertEqual(measured, {"weight": mask.count("1"),
                                       "profit": mask.count("1"), "feasible": True})
        expected_states = {name: generator.bit_generator.state for name, generator in
                           create_random_generators(self.seed, self.task_index, 0).items()}
        self.assertEqual(self.bank["rng_states"], expected_states)

    def test_bank_and_search_do_not_modify_the_known_prefix(self):
        before_bank, before_problem = deepcopy(self.bank), deepcopy(self.problem)
        for mu in (10, 20, 30):
            with self.subTest(mu=mu):
                log = self.run_fixture(mu)
                self.assertEqual(log["initial_masks"], self.bank["masks"][:mu])
                self.assertEqual(log["initial_scores"], self.bank["scores"][:mu])
                self.assertEqual(log["rng_initial"], self.bank["rng_states"])
        self.assertEqual(self.bank, before_bank)
        self.assertEqual(self.problem, before_problem)

    def test_same_inputs_reproduce_every_scientific_field(self):
        repeated_bank = make_bank(self.problem, self.task_index, self.seed, 149998)
        for field in ("masks", "scores", "rng_states"):
            self.assertEqual(repeated_bank[field], self.bank[field])
        first, second = self.run_fixture(), self.run_fixture(bank=repeated_bank)
        self.assertEqual(self.scientific(first), self.scientific(second))

    def test_fixed_parameters_and_total_accounting(self):
        for mu in (10, 20, 30):
            with self.subTest(mu=mu):
                log = self.run_fixture(mu)
                self.assertEqual(log["configuration_contract"], "population-crossover-v1")
                self.assertEqual(log["initial_population_size"], mu)
                self.assertEqual(log["budget"] + mu, 80)
                self.assertEqual(len(log["candidates"]), 80 - mu)
                expected = {"p_m": .01, "p_c": .9, "target_mu": mu,
                            "tournament_size": 2, "elite_count": 1}
                self.assertEqual(log["initial_parameters"], expected)
                for generation in log["generations"]:
                    self.assertEqual(generation["parameters_before"], expected)
                    self.assertEqual(generation["parameters_after"], expected)
                self.assertEqual(log["summary"]["new_calls"], 80 - mu)
                self.assertEqual(log["summary"]["known_score_validation_evaluations"], mu)
                checked = verify_log(log)
                self.assertEqual(checked["verification_status"], "VERIFIED")
                self.assertEqual(checked["new_calls"], 80 - mu)
                self.assertEqual(checked["independent_score_checks"], mu + 2 * (80 - mu))

    def test_arithmetic_of_registered_full_evaluation_limit(self):
        expected = {10: (11110, 0), 20: (5262, 2), 30: (3447, 7)}
        for mu, (complete, remainder) in expected.items():
            self.assertEqual(divmod(100000 - mu, mu - 1), (complete, remainder))
            self.assertEqual(mu + complete * (mu - 1) + remainder, 100000)

    def test_partial_generation_keeps_population_and_controller(self):
        for mu in (10, 20, 30):
            with self.subTest(mu=mu):
                log = self.run_fixture(mu)
                last = log["generations"][-1]
                self.assertFalse(last["complete"])
                self.assertEqual(last["end_call"], 80 - mu)
                self.assertEqual(last["controller_event"], "PARTIAL_NO_UPDATE")
                self.assertEqual(last["population_after"], last["population_before"])
                self.assertEqual(last["parameters_after"], last["parameters_before"])
                self.assertEqual(last["failed_queries_after"], last["failed_queries_before"])
                self.assertEqual(log["summary"]["partial_children"], (80 - mu) % (mu - 1))
                self.assertEqual(log["summary"]["best_profit"], log["candidates"][-1]["record_profit"])

    def test_exact_generation_boundary_has_no_extra_update(self):
        for mu, total in ((10, 100), (20, 96), (30, 117)):
            with self.subTest(mu=mu):
                log = self.run_fixture(mu, total)
                self.assertTrue(log["generations"][-1]["complete"])
                self.assertEqual(log["summary"]["partial_children"], 0)
                self.assertEqual(log["summary"]["full_generations"], (total - mu) // (mu - 1))
                self.assertEqual(log["candidates"][-1]["call"], total - mu)
                self.assertEqual(verify_log(log)["verification_status"], "VERIFIED")

    def test_independent_replay_rejects_candidate_population_and_rng_corruption(self):
        log = self.run_fixture(10, 100)
        self.assertEqual(verify_log(log)["verification_status"], "VERIFIED")
        bad_candidate = deepcopy(log)
        mask = bad_candidate["candidates"][0]["mask"]
        bad_candidate["candidates"][0]["mask"] = ("1" if mask[0] == "0" else "0") + mask[1:]
        bad_population = deepcopy(log)
        bad_population["generations"][0]["population_after"][-1] = 0
        bad_rng = deepcopy(log)
        bad_rng["rng_final"]["mutation"]["state"]["state"] ^= 1
        for name, corrupted in (("candidate", bad_candidate), ("population", bad_population), ("rng", bad_rng)):
            with self.subTest(corruption=name), self.assertRaises(ValueError):
                verify_log(corrupted)

    def test_feasibility_scores(self):
        problem = {"n": 100, "capacity": 1, "weights": [2] * 100, "profits": [3] * 100}
        self.assertEqual(score(problem, "0" * 100), {"weight": 0, "profit": 0, "feasible": True})
        self.assertEqual(score(problem, "1" + "0" * 99), {"weight": 2, "profit": 3, "feasible": False})

    def test_duplicate_initial_individuals_and_ties_keep_the_elite(self):
        bank = deepcopy(self.bank)
        bank["masks"] = ["0" * 100] + ["1" * 100 for _ in range(29)]
        bank["scores"] = [{"weight": 0, "profit": 0, "feasible": True}] + [
            {"weight": 100, "profit": 100, "feasible": True} for _ in range(29)]
        log = self.run_fixture(10, 100, bank=bank)
        self.assertEqual(len(set(log["initial_masks"])), 2)
        self.assertEqual(log["summary"]["best_profit"], 100)
        self.assertTrue(all(row["record_profit"] == 100 for row in log["candidates"]))
        self.assertTrue(any(row["profit"] < 100 for row in log["candidates"]))
        scores = log["initial_scores"] + [
            {name: row[name] for name in ("weight", "profit", "feasible")} for row in log["candidates"]]
        for generation in log["generations"]:
            self.assertEqual(max(scores[ref]["profit"] for ref in generation["population_after"]), 100)
        self.assertEqual(verify_log(log)["verification_status"], "VERIFIED")

    def test_external_optimum_is_not_an_input_to_the_search(self):
        self.assertNotIn("optimum", inspect.signature(make_log).parameters)
        self.assertNotIn("reference_optimum", inspect.signature(make_log).parameters)
        with self.assertRaises(ValueError):
            self.run_fixture(problem={**self.problem, "optimum": 100})
        bad_bank = deepcopy(self.bank)
        bad_bank["scores"][0]["profit"] = 1
        with self.assertRaises(ValueError):
            self.run_fixture(bank=bad_bank)

    def test_initial_prefix_exact_threshold_and_last_evaluation(self):
        # A deliberately synthetic observation fixture tests threshold arithmetic.
        # It is not a produced scientific journal and is never passed off as one.
        initial = {"weight": 0, "profit": 0, "feasible": True}
        log = {"schema": "ga-knapsack-population-crossover-log-v1",
               "configuration_contract": "population-crossover-v1", "profile": 0,
               "problem": self.problem,
               "initial_parameters": {"p_m": .01, "p_c": .9, "target_mu": 10,
                                      "tournament_size": 2, "elite_count": 1},
               "initial_population_size": 10, "initial_masks": ["0" * 100] * 10,
               "initial_scores": [deepcopy(initial) for _ in range(10)], "budget": 2,
               "candidates": [{"mask": "1" * 93 + "0" * 7, "weight": 93, "profit": 93, "feasible": True},
                              {"mask": "1" * 100, "weight": 100, "profit": 100, "feasible": True}],
               "generations": [{"generation": 1, "start_call": 1, "end_call": 2,
                                "complete": False, "requested_offspring": 9, "actual_parent_mu": 10}],
               "summary": {"partial_children": 2}}
        observed = extract(log, 12, 100, checkpoints=(0, 5, 10, 11, 12))
        points = {row["q"]: row for row in observed["checkpoints"]}
        self.assertIsNone(points[0]["record_profit"])
        self.assertEqual(points[5]["phase"], "initializing")
        self.assertIsNone(points[5]["completed_population"])
        self.assertEqual(points[11]["record_profit"], 93)
        self.assertEqual(points[12]["record_profit"], 100)
        self.assertEqual(points[12]["partial_offspring_count"], 2)
        self.assertEqual(observed["targets"]["93"]["first_total_evaluation"], 11)
        self.assertEqual(observed["targets"]["95"]["first_total_evaluation"], 12)
        self.assertEqual(observed["targets"]["99"]["first_total_evaluation"], 12)
        missed_log = deepcopy(log)
        missed_log["candidates"][-1] = {"mask": "1" * 98 + "0" * 2,
                                        "weight": 98, "profit": 98, "feasible": True}
        missed = extract(missed_log, 12, 100, checkpoints=(12,))
        self.assertFalse(missed["targets"]["99"]["attained"])
        self.assertEqual(missed["targets"]["99"]["restricted_evaluations"], 12)


if __name__ == "__main__":
    unittest.main()

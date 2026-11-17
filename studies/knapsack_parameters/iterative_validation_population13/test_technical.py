"""CI-only checks for the new contract, independent replay, and input admission.

These tests use small synthetic budgets. The six registered technical cases
provide the full-budget evidence; no local test or scientific run is admitted.
"""
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .common import HERE, descriptor, guard_technical, registered_cases, validate_plan
from .pilot import check_accounting, comparable_log
from .search import make_log
from studies.knapsack_parameters.population_validation_100.common import read_json


class TechnicalContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        guard_technical()

    def setUp(self):
        from studies.knapsack_parameters.population_validation_100.preparation import make_bank
        self.problem = {"n": 100, "weights": [1] * 100,
                        "profits": [1 + index % 11 for index in range(100)], "capacity": 50}
        self.bank = make_bank(self.problem, 0, 159999, 159998)

    def test_mu13_short_journal_replays_two_complete_and_three_partial_children(self):
        from studies.knapsack_parameters.crossover_population.verification import verify_log
        log = make_log(self.problem, self.bank, 13, 159999, 0, total=40)
        checked = verify_log(log)
        accounting = check_accounting(log, 13, 40)
        self.assertEqual(checked["verification_status"], "VERIFIED")
        self.assertEqual(accounting, {"initial_evaluations": 13, "new_evaluations": 27,
                                    "total_evaluations": 40, "completed_generations": 2,
                                    "terminal_partial_children": 3})
        self.assertEqual(log["initial_masks"], self.bank["masks"][:13])
        self.assertEqual(log["initial_scores"], self.bank["scores"][:13])
        self.assertEqual(log["rng_initial"], self.bank["rng_states"])
        last = log["generations"][-1]
        self.assertEqual(last["population_after"], last["population_before"])
        self.assertEqual(last["record_after"], log["summary"]["best_profit"])
        expected_record = max([score["profit"] for score in log["initial_scores"] if score["feasible"]]
                              + [child["profit"] for child in log["candidates"] if child["feasible"]])
        self.assertEqual(log["summary"]["best_profit"], expected_record)

    def test_replay_covers_registered_compatibility_population_sizes(self):
        from studies.knapsack_parameters.crossover_population.verification import verify_log
        for mu in (10, 15, 20):
            with self.subTest(mu=mu):
                total = mu + 2 * (mu - 1) + 3
                log = make_log(self.problem, self.bank, mu, 159999, 0, total)
                self.assertEqual(verify_log(log)["verification_status"], "VERIFIED")
                self.assertEqual(check_accounting(log, mu, total)["terminal_partial_children"], 3)
                self.assertEqual(log["initial_parameters"], {"p_m": .01, "p_c": .9,
                                 "target_mu": mu, "tournament_size": 2, "elite_count": 1})

    def test_exact_comparison_ignores_only_execution_timing(self):
        first = make_log(self.problem, self.bank, 13, 159999, 0, 40)
        second = make_log(self.problem, self.bank, 13, 159999, 0, 40)
        self.assertEqual(comparable_log(first), comparable_log(second))
        changed = deepcopy(second)
        changed["rng_final"]["mutation"]["state"]["state"] += 1
        self.assertNotEqual(comparable_log(first), comparable_log(changed))
        changed = deepcopy(second)
        changed["candidates"][-1]["mask"] = "0" * 100
        self.assertNotEqual(comparable_log(first), comparable_log(changed))

    def test_oracle_metadata_and_substituted_seed_or_stream_are_rejected(self):
        for field in ("optimum", "certificate", "witness_mask"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                make_log({**self.problem, field: 1}, self.bank, 13, 159999, 0, 40)
        for mu in (True, 12, 14, 30):
            with self.subTest(mu=mu), self.assertRaises(ValueError):
                make_log(self.problem, self.bank, mu, 159999, 0, 40)
        with self.assertRaises(ValueError):
            make_log(self.problem, self.bank, 13, 150001, 0, 40)
        changed = deepcopy(self.bank)
        changed["rng_states"]["ties"]["state"]["state"] += 1
        with self.assertRaises(ValueError):
            make_log(self.problem, changed, 13, 159999, 0, 40)

    def test_search_preserves_problem_and_original_bank(self):
        problem, bank = deepcopy(self.problem), deepcopy(self.bank)
        make_log(self.problem, self.bank, 13, 159999, 0, 40)
        self.assertEqual(self.problem, problem)
        self.assertEqual(self.bank, bank)

    def test_independent_verifier_rejects_partial_population_commit(self):
        from studies.knapsack_parameters.crossover_population.verification import verify_log
        log = make_log(self.problem, self.bank, 13, 159999, 0, 40)
        changed = deepcopy(log)
        changed["generations"][-1]["population_after"][-1] = 39
        with self.assertRaises(ValueError):
            verify_log(changed)

    def test_bank_duplicates_and_infeasible_children_still_count_as_queries(self):
        from studies.knapsack_parameters.crossover_population.verification import verify_log
        from studies.knapsack_parameters.population_validation_100.preparation import score
        bank = deepcopy(self.bank)
        bank["masks"] = ["0" * 100] * 30
        bank["scores"] = [score(self.problem, mask) for mask in bank["masks"]]
        log = make_log(self.problem, bank, 13, 159999, 0, 40)
        checked = verify_log(log)
        self.assertEqual(checked["new_calls"], 27)
        self.assertEqual(len(log["candidates"]), 27)
        self.assertEqual([row["call"] for row in log["candidates"]], list(range(1, 28)))


class TechnicalAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        guard_technical()

    def test_registered_six_case_inventory_and_full_mu13_budget(self):
        cases = registered_cases()
        self.assertEqual(len(cases), 6)
        self.assertEqual(len({row["case_id"] for row in cases}), 6)
        self.assertEqual(divmod(100000 - 13, 13 - 1), (8332, 3))
        self.assertEqual(sum(100000 - row["mu"] for row in cases), 599916)

    def test_source_plan_cannot_substitute_seed_bank_or_compact_reference(self):
        plan = read_json(HERE / "retained_input_plan.json")
        self.assertEqual(len(validate_plan(plan)), 6)
        for field, value in (("seed", 149999), ("mu", 15), ("task_index", 9)):
            changed = deepcopy(plan)
            changed["cases"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_plan(changed)
        changed = deepcopy(plan)
        changed["cases"][3]["reference_journal"] = None
        with self.assertRaises(ValueError):
            validate_plan(changed)
        changed = deepcopy(plan)
        changed["transport_status"] = "COMPACT_ONLY"
        with self.assertRaises(ValueError):
            validate_plan(changed)

    def test_legacy_certificate_without_optional_digests_preserves_witness_checks(self):
        from .preparation import validate_retained_certificate
        problem = {"n": 100, "weights": [1] * 100, "profits": [1] * 100, "capacity": 50}
        witness = {"witness_mask": "1" * 50 + "0" * 50, "witness_profit": 50,
                   "witness_weight": 50, "optimum_profit": 50}
        certificate = {"status": "CERTIFIED_TWO_INDEPENDENT_EXACT_ORACLES", "search_uses_optimum": False,
                       "optimum": 50,
                       "capacity_certificate": {**witness, "method": "capacity_max_profit_dp_packed_witness"},
                       "profit_certificate": {**witness, "method": "profit_min_weight_dp_independent_packed_witness"}}
        original = deepcopy(certificate)
        validate_retained_certificate(problem, certificate)
        self.assertEqual(certificate, original)
        changed = deepcopy(certificate)
        changed["profit_certificate"]["witness_profit"] = 49
        with self.assertRaises(ValueError):
            validate_retained_certificate(problem, changed)
        with self.assertRaises(ValueError):
            validate_retained_certificate(problem, {**certificate, "problem_sha256": "0" * 64})
        with self.assertRaises(ValueError):
            validate_retained_certificate(problem, certificate, require_input_hashes=True)

    def test_unknown_member_length_requires_a_bound_and_exact_hash(self):
        from hashlib import sha256
        content = b"retained-file-fixture"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "journal.json.gz").write_bytes(content)
            row = {"path": "journal.json.gz", "bytes": None, "max_bytes": len(content),
                   "sha256": sha256(content).hexdigest()}
            self.assertEqual(descriptor(root, row), root / "journal.json.gz")
            for change in ({"max_bytes": len(content) - 1}, {"sha256": "0" * 64}, {"max_bytes": None},
                           {"path": "../journal.json.gz"}, {"bytes": len(content) + 1}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    descriptor(root, {**row, **change})

    def test_guard_denies_local_event_and_old_analysis_authorization(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), self.assertRaises(ValueError):
            guard_technical()
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "push"}), self.assertRaises(ValueError):
            guard_technical()
        with self.assertRaises(ValueError):
            guard_technical("iterative-validation-first-analysis-old-grant")


if __name__ == "__main__":
    unittest.main()

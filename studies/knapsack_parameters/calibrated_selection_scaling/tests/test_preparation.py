"""CI-only provenance, prefix-bank and input-scope fixtures."""
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .. import configuration as config
from .. import preparation as prep


class PreparationFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Scientific fixtures execute only in GitHub Actions")

    def problem(self, n=100):
        return {"n": n, "capacity": n, "profits": list(range(1, n + 1)), "weights": [2] * n}

    def test_parser_preserves_profit_weight_order_and_rejects_extra_columns(self):
        raw = b"2\n7\n11 3\n13 5\n"
        self.assertEqual(prep.parse_kp_bytes(raw, 2),
                         {"n": 2, "capacity": 7, "profits": [11, 13], "weights": [3, 5]})
        for malformed in (b"2\n7\n11 3 0\n13 5\n", b"2\n7\n11 -3\n13 5\n",
                          b"2\n7\n11 0\n13 5\n", b"3\n7\n11 3\n13 5\n"):
            with self.subTest(raw=malformed), self.assertRaises(ValueError):
                prep.parse_kp_bytes(malformed, 2)

    def test_unordered_fingerprint_detects_permuted_items_but_includes_capacity(self):
        first = {"n": 3, "capacity": 7, "profits": [11, 13, 17], "weights": [3, 5, 2]}
        permuted = {"n": 3, "capacity": 7, "profits": [17, 11, 13], "weights": [2, 3, 5]}
        self.assertNotEqual(prep.problem_sha256(first), prep.problem_sha256(permuted))
        self.assertEqual(prep.unordered_problem_sha256(first), prep.unordered_problem_sha256(permuted))
        permuted["capacity"] += 1
        self.assertNotEqual(prep.unordered_problem_sha256(first), prep.unordered_problem_sha256(permuted))

    def test_registered_technical_preparation_includes_sixty_new_sources(self):
        _, sources, _ = prep._source_registry("technical")
        self.assertEqual(len(sources), 66)
        self.assertEqual({row["task_id"] for row in sources},
                         {row["task_id"] for row in config.task_descriptors("technical") + config.task_descriptors("main")})

    def test_generic_twenty_bank_has_matching_fifteen_prefix_and_six_untouched_states(self):
        from ..program.ga_core import create_random_generators
        task = config.task_descriptors("technical")[0]
        cases = [case for case in config.technical_cases() if case["task_id"] == task["task_id"]]
        problem = self.problem()
        bank = prep.make_bank(problem, 180998, task["task_index"], 180999)
        self.assertEqual(bank["masks"][0], "0" * 100)
        self.assertEqual(len(bank["masks"]), 20)
        self.assertEqual(bank["preparation_entropy"], [180998, task["task_index"], 180999, 1])
        generators = create_random_generators(180999, task["task_index"], 0)
        self.assertEqual(bank["rng_states"], {name: rng.bit_generator.state for name, rng in generators.items()})
        for case in cases:
            self.assertEqual(prep.validate_bank(problem, bank, case)["independent_score_checks"], 20)
        calibrated = [bank["masks"][:case["initial_parameters"]["target_mu"]]
                      for case in cases if case["role"] != "common"]
        self.assertTrue(all(prefix == bank["masks"][:15] for prefix in calibrated))

    def test_bank_builder_and_independent_validator_reject_score_seed_and_rng_tampering(self):
        problem = self.problem()
        case = config.technical_cases()[0]
        bank = prep.make_bank(problem, case["preparation_seed"], case["task_index"], case["seed"])
        for kind in ("score", "seed", "rng"):
            changed = deepcopy(bank)
            if kind == "score":
                changed["scores"][1]["profit"] += 1
            elif kind == "seed":
                changed["search_seed"] += 1
            else:
                changed["rng_states"]["selection"]["state"]["state"] += 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                prep.validate_bank(problem, changed, case)

    def test_retained_compressed_runs_and_input_groups_are_inspected_without_outcome_fields(self):
        problem = self.problem()
        document = {"runs": [{"task": "n00100-UC-s070", "best": 999999}],
                    "technical_cases": [{"task_id": "n00500-SC-s005"}],
                    "records": [{"task_id": "n00100-WC-s001", "problem": problem}],
                    "candidates": [{"task_id": "n00100-UC-s079", "problem": self.problem(500)}]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "compact.json.gz").write_bytes(gzip.compress(json.dumps(document).encode("utf-8")))
            scope = prep._retained_historical_inputs([root])
        self.assertEqual(scope["task_ids"], ["n00100-UC-s070", "n00100-WC-s001", "n00500-SC-s005"])
        self.assertEqual(len(scope["fingerprints"]), 1)
        self.assertTrue(scope["unavailable_external_evidence_excluded"])

    def test_source_path_traversal_and_symlink_escape_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            for path in ("../outside.kp", "/absolute.kp", "C:/outside.kp", "folder\\outside.kp"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    prep._safe(temporary, path, exists=False)

    def test_replay_failure_retains_candidate_and_recovery_performs_no_second_search(self):
        from .. import execution
        case = config.technical_cases()[0]
        expected = {"case": case, "source_manifest_sha256": "a" * 64}
        journal = {"budget": case["total_evaluations"] - case["initial_parameters"]["target_mu"]}
        observed = {"final_best_profit": 0, "targets": {}}
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(execution, "guard_stage"), patch.object(execution, "require_enclosure", return_value={}), \
                patch.object(execution, "load_case", return_value=({}, {})), \
                patch.object(execution, "_case_identity", return_value=expected), patch.object(execution, "_bind"), \
                patch.object(execution, "load_reference", return_value=1), \
                patch.object(execution, "extract", return_value=observed), \
                patch("studies.knapsack_parameters.calibrated_selection_scaling.search.execute_case", return_value=journal) as search, \
                patch("studies.knapsack_parameters.calibrated_selection_scaling.verification.verify_log") as replay:
            replay.side_effect = ValueError("fixture independent replay rejection")
            with self.assertRaisesRegex(ValueError, "replay rejection"):
                execution._run_one(case, temporary, temporary, 1024 ** 2)
            files = execution._files(temporary, case)
            self.assertTrue(files["candidate"].is_file())
            self.assertTrue(files["started"].is_file())
            self.assertFalse(files["log"].exists())
            self.assertFalse(files["receipt"].exists())
            replay.side_effect = None
            replay.return_value = {"verification_status": "VERIFIED"}
            receipt = execution._run_one(case, temporary, temporary, 1024 ** 2)
            self.assertEqual(search.call_count, 1)
            self.assertTrue(receipt["recovered_without_search"])
            self.assertEqual(receipt["new_search_runs"], 0)
            self.assertTrue(files["log"].is_file())
            self.assertTrue(files["receipt"].is_file())
            self.assertFalse(files["candidate"].exists())

    def test_started_identity_without_journal_cannot_silently_repeat_search(self):
        from .. import execution
        case = config.technical_cases()[0]
        expected = {"case": case, "source_manifest_sha256": "a" * 64}
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(execution, "guard_stage"), patch.object(execution, "require_enclosure", return_value={}), \
                patch.object(execution, "load_case", return_value=({}, {})), \
                patch.object(execution, "_case_identity", return_value=expected), \
                patch("studies.knapsack_parameters.calibrated_selection_scaling.search.execute_case") as search:
            execution._files(temporary, case)["started"].write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "recovery resource audit"):
                execution._run_one(case, temporary, temporary, 1024 ** 2)
            search.assert_not_called()


if __name__ == "__main__":
    unittest.main()

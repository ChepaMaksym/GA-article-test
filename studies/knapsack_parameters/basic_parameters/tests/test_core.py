"""Tiny CI fixtures for the fixed-grid wrapper and bank/seed provenance."""
from copy import deepcopy
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from studies.knapsack_parameters.feasibility.data_audit import Instance
from studies.knapsack_parameters.ga_study import engine
from studies.knapsack_parameters.ga_study.banks import create_bank as old_bank
from studies.knapsack_parameters.ga_study.oracle import verify_search
from studies.knapsack_parameters.basic_parameters import banks, core, execution
from studies.knapsack_parameters.basic_parameters.contract import PROTOCOL, canonical, read_json


def fixture():
    return Instance(100, 45, tuple(range(1, 101)), (1,) * 100,
                    "teaching.kp", "UC", "s000", 0)


def provenance():
    return {"protocol_id": PROTOCOL, "implementation_sha": "a" * 40,
            "run_id": 123, "run_attempt": 1,
            "source_manifest": {"sha256": "b" * 64, "files": []}}


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        core.ci_only()
        cls.instance = fixture()
        cls.bank, cls.metadata = banks.create_bank(cls.instance, 81001, provenance())

    def test_exact_125_grid_and_probability_units(self):
        values = core.grid()
        self.assertEqual(len(values), 125)
        self.assertEqual(len({c.configuration_id for c in values}), 125)
        self.assertEqual({c.mutation_numerator / 100 for c in values}, {0, .005, .01, .03, .08})
        self.assertEqual({c.crossover_probability for c in values}, {0, .25, .5, .9, 1})
        self.assertEqual({c.population_size for c in values}, {10, 20, 30, 50, 100})

    def test_all_old_configurations_remain_unmodified_subset(self):
        self.assertEqual(len(engine.configurations()), 27)
        self.assertTrue(set(engine.configurations()).issubset(set(core.grid())))
        self.assertEqual(core.grid().count(core.baseline()), 1)

    def test_pilot_is_exact_eight_corners_and_baseline(self):
        values = core.pilot_grid()
        self.assertEqual(len(set(values)), 9)
        self.assertEqual(set(values), {engine.Config(m, c, size)
            for m in (0, 8) for c in (0, 1) for size in (10, 100)} | {core.baseline()})

    def test_development_and_holdout_gate(self):
        self.assertEqual(len(core.task_ids()), 30)
        self.assertEqual(core.parse_task("SC-s009"), ("SC", 9))
        for task in ("UC-s010", "WC-s019", "SC-s099", "UC-s01", "other", "../UC-s000"):
            with self.assertRaises(ValueError):
                core.parse_task(task)

    def test_low_level_wrapper_cannot_release_holdout(self):
        instance = Instance(100, 45, self.instance.profits, self.instance.weights,
                            "holdout.kp", "UC", "s010", 10)
        with self.assertRaises(ValueError):
            core.run_checked(instance, core.baseline(), self.bank, self.metadata, 81001, budget=31)
        with self.assertRaises(ValueError):
            banks.create_bank(instance, 81001)

    def test_exact_303_bank_identities(self):
        ids = banks.bank_identities()
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 303)
        self.assertEqual(sum(seed == 83001 for _, seed in ids), 3)
        self.assertTrue(all(81001 <= seed <= 81010 or seed == 83001 for _, seed in ids))

    def test_bank100_known_scores_and_empty_first(self):
        self.assertTrue(banks.validate_bank(self.instance, 81001, self.bank, self.metadata))
        self.assertEqual(self.bank["masks"].shape, (100, 100))
        self.assertFalse(np.any(self.bank["masks"][0]))
        self.assertEqual(self.bank["profit"][0], 0)
        self.assertTrue(self.bank["feasible"][0])
        self.assertEqual(self.metadata["physical_evaluations"], 100)

    def test_bank_prefix_preserves_old50_sequence(self):
        previous, _ = old_bank(self.instance, 81001)
        for name in previous:
            np.testing.assert_array_equal(previous[name], self.bank[name][:50])

    def test_bank_seed_identity_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            banks.validate_bank(self.instance, 81002, self.bank, self.metadata)

    def test_self_consistent_mutated_bank_still_rejected_by_seed_replay(self):
        arrays = {k: v.copy() for k, v in self.bank.items()}
        metadata = deepcopy(self.metadata)
        arrays["masks"][1, 0] ^= 1
        arrays.update(engine.evaluate_masks(self.instance, arrays["masks"]))
        metadata["mask_sha256"] = hashlib.sha256(arrays["masks"].tobytes()).hexdigest()
        with self.assertRaises(ValueError):
            banks.validate_bank(self.instance, 81001, arrays, metadata)

    def test_wrong_bank_dtype_and_objective_rejected(self):
        for key in ("profit", "masks"):
            arrays = {k: v.copy() for k, v in self.bank.items()}
            arrays[key] = arrays[key].astype(np.float64)
            with self.assertRaises(ValueError):
                banks.validate_bank(self.instance, 81001, arrays, self.metadata)
        arrays = {k: v.copy() for k, v in self.bank.items()}
        arrays["weight"][0] = 1
        with self.assertRaises(ValueError):
            banks.validate_bank(self.instance, 81001, arrays, self.metadata)

    def test_wrong_rng_checkpoint_or_digest_rejected(self):
        for field in ("rng_after_sha256", "rng_before_sha256"):
            metadata = deepcopy(self.metadata)
            metadata[field] = "0" * 64
            with self.assertRaises(ValueError):
                banks.validate_bank(self.instance, 81001, self.bank, metadata)

    def test_every_configuration_replays_short_partial_fixture(self):
        for config in core.grid():
            with self.subTest(config=config.configuration_id):
                result, verdict = core.run_checked(self.instance, config, self.bank, self.metadata,
                                                  81001, budget=config.population_size + 1)
                self.assertEqual(verdict["status"], "PASS_REPLAY")
                self.assertEqual(result["summary"]["physical_evaluations"], 1)
                self.assertTrue(result["summary"]["terminal_partial"])

    def test_population100_known_initial_cost_and_last_prefix(self):
        result, verdict = core.run_checked(self.instance, engine.Config(1, .9, 100),
            self.bank, self.metadata, 81001, budget=201)
        self.assertEqual(result["summary"]["known_initial_requests"], 100)
        self.assertEqual(result["summary"]["physical_evaluations"], 101)
        self.assertEqual(result["summary"]["complete_generations"], 1)
        self.assertTrue(result["summary"]["terminal_partial"])
        self.assertEqual(result["generations"][-1]["population_before"],
                         result["generations"][-1]["population_after"])
        self.assertEqual(verdict["logical_requests"], 201)

    def test_initial_only_consumes_no_search_draws(self):
        result, _ = core.run_checked(self.instance, core.baseline(), self.bank, self.metadata, 81001, budget=30)
        self.assertEqual(result["summary"]["rng_states_start"], result["summary"]["rng_states_terminal"])
        self.assertEqual(result["summary"]["physical_evaluations"], 0)

    def test_no_crossover_no_mutation_cannot_create_genotypes(self):
        result, _ = core.run_checked(self.instance, engine.Config(0, 0, 10),
            self.bank, self.metadata, 81001, budget=31)
        initial = {row.tobytes() for row in result["requests"]["masks"][:10]}
        self.assertTrue(all(row.tobytes() in initial for row in result["requests"]["masks"][10:]))
        self.assertFalse(np.any(result["requests"]["crossover_applied"]))
        self.assertFalse(np.any(result["requests"]["mutation_bits"]))

    def test_crossover_one_always_applied_after_initialization(self):
        result, _ = core.run_checked(self.instance, engine.Config(8, 1, 10),
            self.bank, self.metadata, 81001, budget=21)
        self.assertTrue(np.all(result["requests"]["crossover_applied"][10:]))
        self.assertEqual(result["summary"]["p_m"], .08)

    def test_claimed_seed_cannot_be_replaced_by_self_consistent_rng_header(self):
        result, _ = core.run_checked(self.instance, core.baseline(), self.bank, self.metadata, 81001, budget=30)
        forged = deepcopy(result)
        expected = core.expected_rng_states(self.instance, 81002)
        forged["summary"]["rng_states_start"] = expected
        forged["generations"][0]["rng_states"] = expected
        digest = hashlib.sha256(canonical(expected)).hexdigest()
        forged["summary"]["rng_state_sha256_start"] = digest
        forged["generations"][0]["rng_state_sha256"] = digest
        with self.assertRaises(ValueError):
            core.verify_seed_binding(self.instance, 81001, self.metadata, forged)

    def test_oracle_rejects_corrupted_best_record(self):
        result, _ = core.run_checked(self.instance, core.baseline(), self.bank, self.metadata, 81001, budget=31)
        result["summary"]["best_profit"] += 1
        with self.assertRaises(ValueError):
            verify_search(self.instance, core.baseline(), result)

    def test_search_prefix_is_bound_to_bank_seed_not_only_rng_state(self):
        arrays = {k: v.copy() for k, v in self.bank.items()}
        arrays["masks"][1, 0] ^= 1
        arrays.update(engine.evaluate_masks(self.instance, arrays["masks"]))
        with self.assertRaisesRegex(ValueError, "initial masks"):
            core.run_checked(self.instance, core.baseline(), arrays, self.metadata, 81001, budget=30)

    def test_deterministic_and_external_bank_not_modified(self):
        frozen = {k: v.copy() for k, v in self.bank.items()}
        a, _ = core.run_checked(self.instance, core.baseline(), self.bank, self.metadata, 81001, budget=61)
        b, _ = core.run_checked(self.instance, core.baseline(), self.bank, self.metadata, 81001, budget=61)
        self.assertEqual(a["summary"], b["summary"])
        self.assertEqual(a["generations"], b["generations"])
        for key in self.bank:
            np.testing.assert_array_equal(self.bank[key], frozen[key])

    def test_kernel_has_no_exact_reference_argument(self):
        self.assertEqual(set(inspect.signature(engine.run_search).parameters),
                         {"instance", "config", "initial_masks", "initial_scores", "rngs", "budget"})
        self.assertFalse(hasattr(self.instance, "optimum"))

    def test_outer_summary_and_trace_separate_initial_record_and_population_mean(self):
        result, verdict = core.run_checked(self.instance, core.baseline(), self.bank, self.metadata, 81001, budget=61)
        row = execution.build_summary(self.instance, 81001, "main", result, verdict,
            self.bank, self.metadata, provenance(), 5050)
        self.assertEqual(row["known_initial_requests"], 30)
        self.assertEqual(row["physical_evaluations"], 31)
        self.assertLessEqual(row["initial_best_profit"], row["best_profit"])
        trace = execution.trajectory(self.instance, 81001, result)
        self.assertEqual(trace["points"][0]["request"], 30)
        self.assertEqual(trace["points"][-1]["request"], 61)
        self.assertEqual(trace["points"][-1]["record_profit"], row["best_profit"])
        self.assertFalse(trace["points"][-1]["complete"])

    def test_compatible_full_journal_roundtrip_without_pickle(self):
        result, verdict = core.run_checked(self.instance, core.baseline(), self.bank, self.metadata, 81001, budget=31)
        row = execution.build_summary(self.instance, 81001, "pilot", result, verdict,
            self.bank, self.metadata, provenance(), 5050)
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "run"
            self.assertGreater(execution.write_run(target, result, row), 0)
            with np.load(target / "requests.npz", allow_pickle=False) as archive:
                loaded = {key: archive[key] for key in archive.files}
            with gzip.open(target / "generations.jsonl.gz", "rt", encoding="utf-8") as source:
                events = [json.loads(line) for line in source]
            replay = verify_search(self.instance, core.baseline(),
                {"summary": read_json(target / "search_summary.json"), "requests": loaded, "generations": events})
            self.assertEqual(replay["status"], "PASS_REPLAY")
            with self.assertRaises(FileExistsError):
                execution.write_run(target, result, row)

    def test_task_preserves_incomplete_bank_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "checkout"
            target = Path(temporary) / "evidence"
            receipt = {"protocol_id": PROTOCOL, "source_manifest_sha256": "b" * 64,
                       "banks_manifest_sha256": "c" * 64}
            def fake_read(path):
                return receipt if Path(path).name == "frozen_banks.json" else {"provenance": provenance()}
            with patch.object(execution, "load_instance", return_value=self.instance), \
                 patch.object(execution, "verify_manifest"), \
                 patch.object(execution, "read_json", side_effect=fake_read), \
                 patch.object(execution, "load_bank", side_effect=ValueError("fixture corrupted bank")):
                with self.assertRaisesRegex(ValueError, "corrupted bank"):
                    execution.run_task(root, "UC-s000", "pilot", target, provenance())
            value = read_json(target / "manifest.json")
            self.assertEqual(value["status"], "INCOMPLETE")
            self.assertEqual(value["completed_runs"], 0)
            self.assertEqual(value["failure"]["type"], "ValueError")

    def test_resource_stop_does_not_shorten_budget_or_invent_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, target = Path(temporary) / "checkout", Path(temporary) / "evidence"
            receipt = {"protocol_id": PROTOCOL, "source_manifest_sha256": "b" * 64,
                       "banks_manifest_sha256": "c" * 64}
            def fake_read(path):
                return receipt if Path(path).name == "frozen_banks.json" else {"provenance": provenance()}
            with patch.object(execution, "load_instance", return_value=self.instance), \
                 patch.object(execution, "verify_manifest"), \
                 patch.object(execution, "read_json", side_effect=fake_read), \
                 patch.object(execution, "load_bank", return_value=(self.bank, self.metadata)), \
                 patch.object(execution, "MAX_SECONDS", 0), \
                 patch.object(execution, "run_checked") as search:
                with self.assertRaises(execution.StudyResourceError):
                    execution.run_task(root, "UC-s000", "pilot", target, provenance())
                search.assert_not_called()
            self.assertEqual(read_json(target / "manifest.json")["status"], "STOP_RESOURCE")
            self.assertEqual(read_json(target / "summaries.json"), [])


if __name__ == "__main__":
    unittest.main()

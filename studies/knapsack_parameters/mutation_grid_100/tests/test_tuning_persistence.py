"""Check that an interrupted synthetic block preserves completed receipts."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .. import run_tuning
from ..common import HERE, read_json, sha, write_json


class BlockPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Scientific tests require GitHub Actions")

    def test_interruption_retains_verified_cases_without_new_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs, raw, compact = root / "inputs", root / "raw", root / "compact"
            prepared = inputs / "prepared"
            task = "n00100-UC-s050"
            folder = prepared / task
            problem = {"n": 100, "weights": [1] * 100, "profits": [1] * 100, "capacity": 50}
            write_json(folder / "problem.json", problem)
            write_json(folder / "bank.json", {"synthetic": True})
            write_json(folder / "certificate.json", {"optimum": 100})
            tasks = [{"task": task, "family": "s050", "class_label": "UC", "task_index": 3,
                      "certificate_sha256": sha(folder / "certificate.json"),
                      "banks": [{"seed": 150001, "path": task + "/bank.json", "sha256": sha(folder / "bank.json")}]}]
            write_json(prepared / "manifest.json", {"tasks": tasks, "files": [{"path": "synthetic"}]})
            cases = [{"task": task, "family": "s050", "class_label": "UC", "task_index": 3,
                      "seed": 150001, "mu": 10 if i < 5 else 15, "pc_percentage": 100,
                      "mutation_basis_points": (25, 50, 75, 150, 200, 25)[i]} for i in range(6)]
            write_json(inputs / "schedule.json", {"shards": [{"shard_id": "000", "cases": cases}]})
            write_json(inputs / "retained_grid.json.gz", {"synthetic": True})
            write_json(inputs / "stage_manifest.json", {"schema": "mutation-grid-100-tuning-inputs-v1",
                       "status": "STAGE_INPUTS_PREPARED", "new_case_count": 1350, "retained_count": 1440,
                       "overlap_count": 270, "schedule_sha256": sha(inputs / "schedule.json"),
                       "retained_grid_sha256": sha(inputs / "retained_grid.json.gz"),
                       "prepared_manifest_sha256": sha(prepared / "manifest.json"),
                       "source_manifest_sha256": sha(HERE / "source_manifest.json")})
            calls = []

            def make_log(given_problem, bank, mu, rate, seed, index):
                self.assertNotIn("optimum", given_problem)
                calls.append((mu, rate))
                if len(calls) == 4:
                    raise RuntimeError("synthetic interruption")
                return {"mu": mu}

            def verify(log):
                return {"verification_status": "VERIFIED", "new_calls": 100000 - log["mu"],
                        "derived_metrics": {"operator_bins": {}}, "premutation_score_checks": 0,
                        "record_profit": 0, "duplicate_candidates": 0}

            observed = {"final_best_profit": 0, "record_events": [{"q": 1, "profit": 0}],
                        "checkpoints": [], "targets": {}, "completed_generations": 0}
            with patch.object(run_tuning, "guard_stage"), patch.object(run_tuning, "_verify_files"), \
                    patch.object(run_tuning, "make_log", side_effect=make_log), \
                    patch("studies.knapsack_parameters.mutation_grid_100.verification.verify_log", side_effect=verify), \
                    patch("studies.knapsack_parameters.mutation_grid_100.observations.extract", return_value=observed):
                with self.assertRaisesRegex(RuntimeError, "synthetic interruption"):
                    run_tuning.execute(inputs, "000", raw, compact)
            receipts = list((compact / "records").glob("*.json"))
            self.assertEqual(len(receipts), 3)
            self.assertEqual(len(calls), 4)
            self.assertEqual(read_json(compact / "failure-03.json")["completed_case_count"], 3)
            self.assertFalse((compact / "shard.json").exists())
            with self.assertRaises(ValueError):
                with patch.object(run_tuning, "guard_stage"):
                    run_tuning.execute(inputs, "000", raw, compact)


if __name__ == "__main__":
    unittest.main()

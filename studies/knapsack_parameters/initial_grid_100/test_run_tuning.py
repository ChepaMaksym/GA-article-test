"""CI-only synthetic checks of per-case persistence and interrupted blocks."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .common import guard_checks, guard_stage, sha
from . import run_tuning


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class TuningPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        if os.environ.get("GITHUB_REF") == "refs/heads/research/initial-grid100-checks-20261110":
            guard_checks()
        else:
            guard_stage("tuning")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs, self.raw, self.compact = (self.root / name for name in ("inputs", "raw", "compact"))
        task_name = "n00100-UC-s050"
        base = self.inputs / "prepared"
        bank_path = base / task_name / "banks/seed-150001.json"
        put(bank_path, {"marker": "synthetic"})
        put(base / task_name / "problem.json", {"n": 100, "weights": [1] * 100,
            "profits": [1] * 100, "capacity": 50})
        cert_path = base / task_name / "certificate.json"
        put(cert_path, {"optimum": 10})
        self.cases = [{"task": task_name, "task_index": 3, "family": "s050", "class_label": "UC",
                       "seed": 150001, "mu": mu, "pc_percentage": pc}
                      for mu, pc in ((15, 70), (15, 80), (15, 90), (15, 100), (25, 70), (25, 80))]
        task = {"task": task_name, "task_index": 3, "family": "s050", "class_label": "UC",
                "certificate_sha256": sha(cert_path),
                "banks": [{"seed": 150001, "path": bank_path.relative_to(base).as_posix(), "sha256": sha(bank_path)}]}
        put(base / "manifest.json", {"tasks": [task], "files": [{"path": bank_path.relative_to(base).as_posix(),
            "bytes": bank_path.stat().st_size, "sha256": sha(bank_path)}]})
        put(self.inputs / "schedule.json", {"shards": [{"shard_id": "000", "cases": self.cases}]})
        put(self.inputs / "reused.json", {"runs": []})
        put(self.inputs / "stage_manifest.json", {"schema": "initial-grid-100-stage-inputs-v1", "stage": "tuning",
            "status": "STAGE_INPUTS_PREPARED", "retained_count": 180, "new_case_count": 1260,
            "schedule_sha256": sha(self.inputs / "schedule.json"), "reused_sha256": sha(self.inputs / "reused.json"),
            "prepared_manifest_sha256": sha(base / "manifest.json")})

    @staticmethod
    def fake_search(problem, bank, mu, pc, seed, task_index):
        if "optimum" in problem:
            raise AssertionError("The search must not receive the optimum")
        return {"mu": mu, "pc": pc, "seed": seed}

    @staticmethod
    def fake_verification(log):
        return {"verification_status": "VERIFIED", "new_calls": 100000 - log["mu"], "record_profit": 5,
                "premutation_score_checks": 1, "duplicate_candidates": 0, "derived_metrics": {"operator_bins": {}}}

    @staticmethod
    def fake_observation(log, total, optimum, checkpoints):
        return {"final_best_profit": 5, "record_events": [{"q": 1, "profit": 0}, {"q": 100, "profit": 5}],
                "checkpoints": [{"q": q, "record_profit": 5, "population_metrics": {},
                                 "completed_generations": 0} for q in checkpoints],
                "targets": {}, "completed_generations": 0}

    def mocks(self, search):
        return patch.multiple(run_tuning, guard_stage=lambda stage: {"tuning": {"seeds": [150001, 150002, 150003]}},
                              make_log=search)

    def test_six_cases_write_verified_receipts_without_supplying_optimum(self):
        from studies.knapsack_parameters.crossover_population import verification, observations
        with self.mocks(self.fake_search), patch.object(verification, "verify_log", self.fake_verification), \
             patch.object(observations, "extract", self.fake_observation):
            run_tuning.execute(self.inputs, "000", self.raw, self.compact)
        data = json.loads((self.compact / "shard.json").read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "VERIFIED")
        self.assertEqual(len(data["runs"]), 6)
        self.assertEqual(len(list((self.compact / "records").glob("*.json"))), 6)
        self.assertTrue(all(r["best"] == 5 for r in data["runs"]))

    def test_interruption_preserves_receipt_and_refuses_full_rerun(self):
        from studies.knapsack_parameters.crossover_population import verification, observations
        calls = []
        def interrupted(*args):
            calls.append(args)
            if len(calls) == 2:
                raise RuntimeError("synthetic interruption")
            return self.fake_search(*args)
        with self.mocks(interrupted), patch.object(verification, "verify_log", self.fake_verification), \
             patch.object(observations, "extract", self.fake_observation):
            with self.assertRaisesRegex(RuntimeError, "synthetic interruption"):
                run_tuning.execute(self.inputs, "000", self.raw, self.compact)
            self.assertEqual(len(list((self.compact / "records").glob("*.json"))), 1)
            self.assertTrue((self.compact / "failure-01.json").is_file())
            with self.assertRaises(ValueError):
                run_tuning.execute(self.inputs, "000", self.raw, self.compact)
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()

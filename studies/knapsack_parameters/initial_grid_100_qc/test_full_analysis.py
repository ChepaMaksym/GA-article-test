"""Exercise the complete frozen grid aggregation with synthetic records only."""
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.initial_grid_100 import analyze_tuning as analysis
from studies.knapsack_parameters.initial_grid_100.common import HERE, read_json, require, require_ci, sha, verify_source
from studies.knapsack_parameters.initial_grid_100.prepare_tuning import tuning_schedule


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")


class FullSyntheticAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_ci()
        require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test"
                and os.environ.get("GITHUB_REF") == "refs/heads/research/initial-grid100-qc-20261110"
                and os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "Unregistered synthetic analysis check")
        authorization = read_json(HERE / "tuning_authorization.json")
        require(authorization.get("status") == "AUTHORIZED" and authorization.get("runner_minutes") == 1750
                and authorization.get("artifact_bytes") == 17179869184,
                "The separately approved tuning authority differs")
        verify_source()
        require(sha(HERE / "source_manifest.json") == "2ed212337b22706decd7123ab1111cbc4c62fbe357e29478c1c868acf3c2f44f",
                "The analysis under test differs from the running study")
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.inputs, cls.blocks = cls.root / "inputs", cls.root / "blocks"
        cls._build_synthetic_inputs()

    @classmethod
    def _build_synthetic_inputs(cls):
        tasks, banks = [], {}
        for family in range(50, 60):
            for index, kind in enumerate(("UC", "WC", "SC")):
                task = f"n00100-{kind}-s{family:03d}"
                task_index = 3 + (family - 50) * 3 + index
                cert = cls.inputs / "prepared" / task / "certificate.json"
                put(cert, {"optimum": 1000})
                descriptors = []
                for seed in (150001, 150002, 150003):
                    digest = sha256(f"synthetic:{task}:{seed}".encode()).hexdigest()
                    banks[(task, seed)] = digest
                    descriptors.append({"seed": seed, "sha256": digest})
                tasks.append({"task": task, "task_index": task_index, "family": f"s{family:03d}",
                              "class_label": kind, "certificate_sha256": sha(cert), "banks": descriptors})
        put(cls.inputs / "prepared/manifest.json", {"tasks": tasks})
        shards = tuning_schedule(tasks)
        put(cls.inputs / "schedule.json", {"physical_runs": 1260, "shards": shards})

        def row(task, seed, mu, pc, retained):
            best = 950 + mu // 5 + pc // 10
            metrics = {"population_size": mu, "unique_fraction": 1.0, "feasible_fraction": 1.0,
                       "mean_pairwise_hamming": 10.0}
            targets = {str(p): {"attained": p < 99, "first_total_evaluation": 100 if p < 99 else None,
                                "restricted_evaluations": 100 if p < 99 else 100000} for p in (93, 95, 99)}
            prefix = f'{task["task"]}/seed-{seed}' + ("" if retained else f"/mu{mu}-pc{pc}")
            return {**{key: task[key] for key in ("task", "task_index", "family", "class_label")},
                    "seed": seed, "mu": mu, "pc_percentage": pc, "optimum": 1000, "best": best,
                    "events": [[1, 0], [100, best]],
                    "checkpoints": [{"q": q, "record_profit": best, "population_metrics": metrics,
                                     "completed_generations": (q - mu) // (mu - 1)}
                                    for q in (5000, 10000, 20000, 50000, 100000)],
                    "targets": targets, "completed_generations": (100000 - mu) // (mu - 1), "duplicates": 0,
                    "artifact_hashes": {name: "a" * 64 for name in ("journal.json.gz", "verification.json",
                                          "operator_bins.json", "observations.json.gz", "record.json")},
                    "artifact_prefix": prefix, "bank_sha256": banks[(task["task"], seed)],
                    "certificate_sha256": task["certificate_sha256"],
                    "timing": {"search_seconds": 1, "log_write_seconds": 1, "verification_seconds": 1,
                               "observations_seconds": 1, "case_seconds": 5, "artifact_bytes": 1}}

        reused = [row(task, seed, mu, 90, True) for task in tasks for seed in (150001, 150002, 150003)
                  for mu in (10, 20)]
        put(cls.inputs / "reused.json", {"status": "VERIFIED_180_RETAINED", "original_run_id": 42813784277,
                                        "runs": reused, "provenance": []})
        put(cls.inputs / "stage_manifest.json", {"schema": "initial-grid-100-stage-inputs-v1", "stage": "tuning",
            "status": "STAGE_INPUTS_PREPARED", "new_case_count": 1260, "retained_count": 180,
            "schedule_sha256": sha(cls.inputs / "schedule.json"), "reused_sha256": sha(cls.inputs / "reused.json"),
            "prepared_manifest_sha256": sha(cls.inputs / "prepared/manifest.json")})
        by_task = {task["task"]: task for task in tasks}
        for shard in shards:
            block = cls.blocks / shard["shard_id"]
            rows = [row(by_task[c["task"]], c["seed"], c["mu"], c["pc_percentage"], False)
                    for c in shard["cases"]]
            for i, item in enumerate(rows):
                put(block / "records" / f"{i}.json", item)
            put(block / "shard.json", {"schema": "initial-grid-100-tuning-shard-v1", "status": "VERIFIED",
                "shard_id": shard["shard_id"], "runs": rows,
                "stage_manifest_sha256": sha(cls.inputs / "stage_manifest.json"),
                "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
                "source_manifest_sha256": sha(HERE / "source_manifest.json"),
                "raw_artifact_name": f'initial-grid100-tuning-raw-{shard["shard_id"]}-{os.environ["GITHUB_RUN_ID"]}'})

    def test_01_full_grid_selects_and_creates_both_heatmaps(self):
        output = self.root / "synthetic-results"
        with patch.object(analysis, "guard_stage", return_value={}), patch.object(sys, "argv", [
            "analysis", "--inputs", str(self.inputs), "--blocks", str(self.blocks), "--out", str(output)]):
            analysis.main()
        selected = read_json(output / "selection.json")
        self.assertEqual((selected["mu"], selected["pc_percentage"]), (25, 100))
        self.assertFalse(selected["independent_validation_started"])
        for q in (50000, 100000):
            for extension in ("png", "svg"):
                self.assertTrue((output / "figures" / f"grid-{q}.{extension}").is_file())

    def test_02_missing_receipt_blocks_selection(self):
        receipt = next((self.blocks / "000" / "records").glob("*.json"))
        receipt.unlink()
        with self.assertRaises(ValueError):
            analysis.collect(self.inputs, self.blocks)


if __name__ == "__main__":
    unittest.main()

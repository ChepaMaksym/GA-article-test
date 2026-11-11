"""Synthetic receipt integration only; all numerical checks run in CI."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .. import admit_tuning, analysis
from ..common import HERE, sha, write_json
from ..prepare_tuning import build_schedule
from .test_analysis import make_union


class TuningAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Scientific tests require GitHub Actions")

    def test_synthetic_receipts_allow_complete_grid_and_reject_missing_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs, blocks = root / "inputs", root / "blocks"
            inputs.mkdir()
            blocks.mkdir()
            prepared = inputs / "prepared"
            prepared.mkdir()
            rows = make_union()
            rows_by_id = {analysis.identity(row): row for row in rows}
            tasks = []
            for family in analysis.TUNING_FAMILIES:
                for offset, kind in enumerate(analysis.TYPES):
                    name = f"n00100-{kind}-{family}"
                    index = 3 + (int(family[1:]) - 50) * 3 + offset
                    tasks.append({"task": name, "family": family, "class_label": kind, "task_index": index,
                                  "certificate_sha256": "b" * 64,
                                  "banks": [{"seed": seed, "sha256": "a" * 64} for seed in analysis.TUNING_SEEDS]})
                    write_json(prepared / name / "certificate.json", {"optimum": 1000})
            write_json(prepared / "manifest.json", {"tasks": tasks, "files": [{"path": "synthetic"}]})
            schedule = {"physical_runs": 1350, "shards": build_schedule(tasks)}
            write_json(inputs / "schedule.json", schedule)
            retained = [row for row in rows if analysis.configuration(row) in analysis.OLD_CONFIGS]
            write_json(inputs / "retained_grid.json.gz", {"status": "VERIFIED_1440_RETAINED", "runs": retained})
            stage = {"schema": "mutation-grid-100-tuning-inputs-v1", "status": "STAGE_INPUTS_PREPARED",
                     "new_case_count": 1350, "retained_count": 1440, "overlap_count": 270,
                     "schedule_sha256": sha(inputs / "schedule.json"),
                     "retained_grid_sha256": sha(inputs / "retained_grid.json.gz"),
                     "prepared_manifest_sha256": sha(prepared / "manifest.json"),
                     "technical_manifest_sha256": "d" * 64,
                     "source_manifest_sha256": sha(HERE / "source_manifest.json")}
            write_json(inputs / "stage_manifest.json", stage)
            archive_map = {}
            first_receipt = None
            for block in schedule["shards"]:
                block_root = blocks / block["shard_id"]
                block_rows = [rows_by_id[analysis.identity(case)] for case in block["cases"]]
                raw_name = f'mutation-grid100-tuning-raw-{block["shard_id"]}-{os.environ["GITHUB_RUN_ID"]}'
                archive_map[raw_name] = {"id": int(block["shard_id"]) + 1, "sha256": "e" * 64, "bytes": 10}
                for index, row in enumerate(block_rows):
                    receipt = block_root / "records" / f"{index}.json"
                    write_json(receipt, row)
                    first_receipt = first_receipt or receipt
                write_json(block_root / "shard.json", {
                    "schema": "mutation-grid-100-tuning-shard-v1", "status": "VERIFIED",
                    "shard_id": block["shard_id"], "runs": block_rows,
                    "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
                    "stage_manifest_sha256": sha(inputs / "stage_manifest.json"),
                    "source_manifest_sha256": sha(HERE / "source_manifest.json"), "raw_artifact_name": raw_name})
            # Synthetic manifest checks are isolated from the real artifact audit.
            with patch.object(admit_tuning, "_verify_files"):
                accepted, provenance = admit_tuning.collect(inputs, blocks, archive_map)
                self.assertEqual(len(accepted), 2790)
                self.assertEqual(provenance["new_cases"], 1350)
                self.assertEqual(provenance["retained_cases"], 1440)
                selection = analysis.choose_recommendations(analysis.summarize(accepted))
                self.assertEqual(selection, {"quality": (10, 90, 100), "speed": (10, 90, 100)})
                first_receipt.unlink()
                with self.assertRaises(ValueError):
                    admit_tuning.collect(inputs, blocks, archive_map)


if __name__ == "__main__":
    unittest.main()

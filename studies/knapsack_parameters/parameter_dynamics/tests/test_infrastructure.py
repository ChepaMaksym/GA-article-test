"""Synthetic gate, storage, bank and resource fixtures; CI execution only."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.parameter_dynamics import authority as a, banks, driver


class InfrastructureTests(unittest.TestCase):
    def test_phase_is_exact_and_main_approval_is_separate(self):
        for phase in a.PHASES:
            self.assertEqual(a.phase(f"Run [parameter-dynamics:{phase}]"), phase)
        for message in ("none", "[parameter-dynamics:tests] [note]", "[parameter-dynamics:tests] [parameter-dynamics:pilot]",
                        "[parameter-dynamics:unknown]", "[other:tests]"):
            with self.subTest(message=message), self.assertRaises(ValueError):
                a.phase(message)
        for phase in ("prepare-main", "main"):
            with self.assertRaises(ValueError):
                a.grant_for(phase)

    def test_technical_resources_and_cumulative_allowance(self):
        grant = a.grant_for("pilot")
        self.assertEqual(grant["runner_minutes_ceiling"], 120)
        self.assertEqual(sum(grant["phase_reservations"].values()), 120)
        a.check_allowance("pilot", {"used_runner_minutes": 21}, grant)
        for used in (22, 120, -1, True, None):
            with self.subTest(used=used), self.assertRaises(ValueError):
                a.check_allowance("pilot", {"used_runner_minutes": used}, grant)
        self.assertEqual(a.journal_allowance("pilot", grant), 512 * 2 ** 20)
        for name, value in (("explicit_user_approval", False), ("runner_minutes_ceiling", 121),
                            ("main_search_authorized", True), ("max_parallel", 8), ("pilot_runs", 255)):
            changed = a.read_json(a.MODULE / "resource_authorization.json")
            changed["technical"][name] = value
            with patch.object(a, "read_json", return_value=changed), self.assertRaises(ValueError):
                a.grant_for("tests")

    def test_all_attempts_and_failed_jobs_count_rounded_up(self):
        runs = [{"id": 1, "run_attempt": 2, "status": "completed", "head_commit": {"message": "[parameter-dynamics:tests]"}},
                {"id": 9, "run_attempt": 1, "status": "in_progress", "head_commit": {"message": "[parameter-dynamics:pilot]"}}]
        def pages(endpoint, key):
            if key == "workflow_runs":
                return iter(runs)
            attempt = 1 if "/attempts/1/" in endpoint else 2
            return iter([{"id": attempt, "name": "fixture", "conclusion": "failure",
                          "started_at": "2026-01-01T00:00:00Z", "completed_at": "2026-01-01T00:01:01Z"}])
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "9", "GITHUB_RUN_ATTEMPT": "1"}), patch.object(a, "pages", side_effect=pages):
            result = a.runner_usage("pilot")
        self.assertEqual(result["used_runner_minutes"], 4)
        self.assertEqual(len(result["jobs"]), 2)
        with patch.object(a, "pages", side_effect=RuntimeError("unknown usage")), self.assertRaises(RuntimeError):
            a.runner_usage("tests")

    def test_manifest_preserves_exact_bytes_and_rejects_extras(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.txt").write_bytes(b"canonical\n")
            a.write_manifest(root)
            a.verify_manifest(root)
            (root / "extra.txt").write_bytes(b"extra")
            with self.assertRaises(ValueError):
                a.verify_manifest(root)
            for path in ("../a", "/a", "C:/a", "x\\y"):
                with self.assertRaises(ValueError):
                    a.safe_child(root, path)

    def test_registered_source_fingerprints_and_data_separation(self):
        registration = a.read_json(a.MODULE / "registration.json")
        for relative, expected in registration["immutable_documents"].items():
            self.assertEqual(a.identity(a.MODULE / relative)["sha256"], expected)
        for relative, expected in registration["historical_sources"].items():
            self.assertEqual(a.identity(a.ROOT / relative)["sha256"], expected)
        manifest = a.source_manifest()
        self.assertEqual(manifest["sha256"], hashlib.sha256(a.canonical(manifest["files"])).hexdigest())
        paths = {row["path"] for row in manifest["files"]}
        self.assertTrue({a.REL + name for name in ("engine.py", "driver.py", "verifier.py", "analysis.py", "plots.py", "banks.py")} <= paths)
        self.assertFalse(any("/evidence/" in p or "/inputs/" in p for p in paths))

    def test_rectangles_and_cyclic_execution_order(self):
        pilot, main = banks.expected_conditions("pilot"), banks.expected_conditions("main")
        self.assertEqual(len(pilot), 8)
        self.assertEqual(len(main), 900)
        self.assertEqual(len({row["worker"] for row in main}), 50)
        self.assertTrue(all(sum(row["worker"] == name for row in main) == 18 for name in a.MAIN_WORKERS))
        for stage, conditions in (("pilot", pilot), ("main", main)):
            for row in conditions:
                order = driver.balanced_order(row, stage)
                self.assertEqual(set(order), set(range(32)))
                self.assertEqual(len(order), 32)
        self.assertEqual(driver.balanced_order(main[0], "main"), tuple(range(32)))

    def test_bank_reconstruction_preserves_duplicates_and_rng(self):
        import numpy as np
        from copy import deepcopy
        p = {"n": 100, "weights": [1] * 100, "profits": [1] * 100, "capacity": 50}
        source = {"problem": p, "center_mask": "0" * 100}
        for start in ("cloned", "bank"):
            gen = np.random.Generator(np.random.PCG64(np.random.SeedSequence([97000, 0, 0, 96999])))
            before = deepcopy(gen.bit_generator.state)
            masks = (["0" * 100] * 30 if start == "cloned" else ["0" * 100] +
                     ["".join(map(str, gen.integers(0, 2, size=100).tolist())) for _ in range(29)])
            bank = {"stage": "pilot", "task_index": 0, "seed": 96999, "start": start,
                    "initialization_before": before, "initialization_after": deepcopy(gen.bit_generator.state),
                    "initial_masks": masks, "initial_scores": [banks.independent_score(p, mask) for mask in masks],
                    "physical_preparation_evaluations": len(set(masks)), "preparation_ns": 0,
                    "logical_initial_positions": 30, "new_search_calls": 0, "new_exact_solves": 0}
            banks.validate_bank(bank, source)
            wrong = deepcopy(bank)
            wrong["initial_scores"][0]["profit"] = 1
            with self.assertRaises(ValueError):
                banks.validate_bank(wrong, source)

    def test_source_parser_does_not_admit_truncated_or_wrong_n(self):
        for value in (b"99 50", b"100 50 1 2", b"100 -1" + b" 1 1" * 100):
            with self.assertRaises(ValueError):
                banks.parse_source(value)
        raw = b"100 50" + b" 1 1" * 100
        self.assertEqual(banks.parse_source(raw)["n"], 100)


if __name__ == "__main__":
    unittest.main()

"""CI-only provenance, scope, resource and evidence-corruption fixtures."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.tournament_feedback import authority as a, banks


class AuthorityFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Software checks are GitHub-Actions only")

    def test_unknown_and_mixed_phase_requests_stop(self):
        self.assertEqual(a.phase("Start [tournament-feedback:pilot-donors]"), "pilot-donors")
        for message in ("", "[tournament-feedback:pilot]", "[other:tests]",
                        "[tournament-feedback:tests] [tournament-feedback:prepare-pilot]",
                        "[tournament-feedback:tests] [other:run]"):
            with self.subTest(message=message), self.assertRaises(ValueError):
                a.phase(message)

    def test_numeric_grant_cannot_inherit_another_scope(self):
        grant = a.read_json(a.MODULE / "resource_authorization.json")
        for field, value in (("execution_authorized", False), ("explicit_user_numeric_approval", False),
                             ("runner_minutes_ceiling", 301), ("compressed_bytes_ceiling", 7 * 2**30),
                             ("historical_budgets_reassigned", True), ("protocol_id", "other")):
            invalid = copy.deepcopy(grant)
            invalid[field] = value
            with self.subTest(field=field), patch.object(a, "read_json", return_value=invalid), self.assertRaises(ValueError):
                a.grant_for("tests")
        with self.assertRaises(ValueError):
            a.grant_for("unregistered")

    def test_manifest_detects_missing_extra_and_changed_evidence(self):
        for change in ("missing", "extra", "changed", "duplicate", "escape"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                (directory / "known.json").write_bytes(b'{"answer":42}\n')
                a.write_manifest(directory)
                self.assertEqual(len(a.verify_manifest(directory)["files"]), 1)
                if change == "missing":
                    (directory / "known.json").unlink()
                elif change == "extra":
                    (directory / "unknown.txt").write_text("extra", encoding="utf-8")
                elif change == "changed":
                    (directory / "known.json").write_bytes(b'{"answer":43}\n')
                else:
                    value = a.read_json(directory / "file_manifest.json")
                    if change == "duplicate":
                        value["files"].append(copy.deepcopy(value["files"][0]))
                    else:
                        value["files"][0]["path"] = "../outside.json"
                    a.write_json(directory / "file_manifest.json", value)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    a.verify_manifest(directory)

    def test_path_traversal_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in ("../escape", "/absolute", "C:/drive", "a\\b", "a/../../escape"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    a.safe_child(tmp, path)

    def test_all_attempts_are_counted_with_per_job_upward_rounding(self):
        def job(identity, seconds):
            return {"id": identity, "name": "source", "conclusion": "success",
                    "started_at": "2026-10-28T10:00:00Z",
                    "completed_at": f"2026-10-28T10:{seconds // 60:02d}:{seconds % 60:02d}Z"}
        runs = [dict(id=100, run_attempt=2, head_commit={"message": "[tournament-feedback:tests]"}),
                dict(id=333, run_attempt=2, head_commit={"message": "[tournament-feedback:prepare-pilot]"})]
        def pages(endpoint, key):
            if key == "workflow_runs":
                return iter(runs)
            if "/100/attempts/1/" in endpoint:
                return iter([job(1, 61), {"id": 99, "conclusion": "skipped"}])
            if "/100/attempts/2/" in endpoint:
                return iter([job(2, 59)])
            if "/333/attempts/1/" in endpoint:
                return iter([job(3, 1)])
            raise AssertionError("Current attempt should be reserved, not recounted: " + endpoint)
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "333", "GITHUB_RUN_ATTEMPT": "2"}), patch.object(a, "pages", side_effect=pages):
            usage = a.runner_usage()
        self.assertEqual(usage["used_runner_minutes"], 4)
        self.assertEqual([row["runner_minutes"] for row in usage["jobs"]], [2, 1, 1])
        self.assertEqual({row["job_id"] for row in usage["jobs"]}, {1, 2, 3})

    def test_unknown_or_duplicate_allocated_time_blocks_execution(self):
        run = dict(id=100, run_attempt=1, head_commit={"message": "[tournament-feedback:tests]"})
        for entries in ([dict(id=1, name="bad", conclusion="failure", started_at=None, completed_at=None)],
                        [dict(id=1, name="a", conclusion="success", started_at="2026-10-28T10:00:00Z", completed_at="2026-10-28T10:00:10Z")] * 2):
            def pages(endpoint, key):
                return iter([run] if key == "workflow_runs" else entries)
            with patch.dict(os.environ, {"GITHUB_RUN_ID": "333", "GITHUB_RUN_ATTEMPT": "1"}), patch.object(a, "pages", side_effect=pages), self.assertRaises(ValueError):
                a.runner_usage()


class BankScopeFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Software checks are GitHub-Actions only")

    def test_frozen_rectangles_and_independent_donor_seeds(self):
        pilot = banks.expected_conditions("pilot")
        main = banks.expected_conditions("main")
        self.assertEqual(len(pilot), 8)
        self.assertEqual(len(main), 900)
        self.assertEqual(len({(row["task"], row["start"], row["seed"]) for row in main}), 900)
        self.assertEqual({row["seed"] for row in main}, set(range(110001, 110031)))
        self.assertEqual({row["donor_seed"] for row in main}, set(range(111001, 111031)))
        self.assertEqual({row["family"] for row in main}, {f"s{i:03d}" for i in range(40, 50)})
        self.assertTrue(all(row["seed"] != row["donor_seed"] for row in main + pilot))
        self.assertEqual({row["condition_index"] for row in main}, set(range(900)))
        self.assertEqual([sum(row["condition_index"] % 6 == i for row in main) for i in range(6)], [150] * 6)

    def test_independent_parser_preserves_profit_weight_order(self):
        pairs = [(10 + i, 101 + i) for i in range(100)]
        raw = ("100\n5000\n" + "\n".join(f"{profit} {weight}" for profit, weight in pairs) + "\n").encode()
        parsed = banks.independent_line_parse(raw)
        self.assertEqual(parsed["profits"], [p for p, _ in pairs])
        self.assertEqual(parsed["weights"], [w for _, w in pairs])
        self.assertEqual(parsed, banks.parse_source(raw))
        for malformed in (raw.replace(b"100\n", b"99\n", 1), raw + b"1 2\n"):
            with self.assertRaises(ValueError):
                banks.independent_line_parse(malformed)

    def test_known_beginning_is_independently_reconstructed(self):
        import numpy as np
        condition = dict(banks.expected_conditions("pilot")[1])
        source = {"problem": {"n": 100, "profits": list(range(1, 101)), "weights": [1] * 100, "capacity": 50},
                  "center_mask": "1" * 50 + "0" * 50}
        generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
            [109998, condition["task_index"], condition["seed"], condition["start_index"]])))
        before = copy.deepcopy(generator.bit_generator.state)
        masks = ["0" * 100] + ["".join(map(str, generator.integers(0, 2, size=100).tolist())) for _ in range(29)]
        bank = {**condition, "stage": "pilot", "problem": source["problem"], "initial_masks": masks,
                "initial_scores": [banks.independent_score(source["problem"], mask) for mask in masks],
                "initialization_before": before, "initialization_after": copy.deepcopy(generator.bit_generator.state),
                "physical_preparation_evaluations": len(set(masks)), "logical_initial_positions": 30, "new_search_calls": 0}
        banks.validate_bank(bank, source)
        for field in ("initial_masks", "initial_scores", "initialization_after", "new_search_calls"):
            changed = copy.deepcopy(bank)
            if field == "initial_masks":
                changed[field][1] = "0" * 100
            elif field == "initial_scores":
                changed[field][1]["profit"] += 1
            elif field == "initialization_after":
                changed[field] = copy.deepcopy(before)
            else:
                changed[field] = 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                banks.validate_bank(changed, source)

    def test_cloned_beginning_uses_one_physical_preparation_score(self):
        import numpy as np
        condition = dict(banks.expected_conditions("pilot")[0])
        source = {"problem": {"n": 100, "profits": [1] * 100, "weights": [1] * 100, "capacity": 50},
                  "center_mask": "1" * 50 + "0" * 50}
        state = np.random.PCG64(np.random.SeedSequence(
            [109998, condition["task_index"], condition["seed"], condition["start_index"]])).state
        masks = [source["center_mask"]] * 30
        bank = {**condition, "stage": "pilot", "problem": source["problem"], "initial_masks": masks,
                "initial_scores": [banks.independent_score(source["problem"], mask) for mask in masks],
                "initialization_before": copy.deepcopy(state), "initialization_after": copy.deepcopy(state),
                "physical_preparation_evaluations": 1, "logical_initial_positions": 30, "new_search_calls": 0}
        banks.validate_bank(bank, source)
        bank["physical_preparation_evaluations"] = 30
        with self.assertRaises(ValueError):
            banks.validate_bank(bank, source)

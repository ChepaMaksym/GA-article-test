"""CI-only fixtures for immutable starts, evidence identity and aggregation."""

import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from .. import banks, reporting, runner
from ..contract import canonical_bytes, file_identity, write_file_manifest, write_json
from ..engine import make_rngs
from ..verifier import independent_score


SHA = "a" * 40
SOURCE = {"schema_version": 1, "protocol_id": banks.PROTOCOL, "files": [], "sha256": "b" * 64}


def fixture_bank(task="OneMax", start="bank"):
    rng = make_rngs(banks.TASKS.index(task), banks.STARTS.index(start))["initialization"]
    before = copy.deepcopy(rng.bit_generator.state)
    center = "0" * 100
    if task.startswith("Jump"):
        k = int(task[4:])
        center = "1" * (100 - k) + "0" * k
        problem = {"kind": "jump", "n": 100, "k": k}
    else:
        problem = {"kind": "flat" if task == "Flat" else "onemax", "n": 100}
    masks = banks.generate_masks(task, center, rng, start=start)
    return {"schema_version": banks.BANK_SCHEMA, "protocol_id": banks.PROTOCOL,
            "preparation_sha": SHA, "task": task, "task_index": banks.TASKS.index(task),
            "start": start, "start_index": banks.STARTS.index(start), "seed": 70001, "n": 100, "mu": 30,
            "problem": problem, "masks": masks,
            "scores": [independent_score(problem, mask) for mask in masks],
            "initialization_before": before, "initialization_after": copy.deepcopy(rng.bit_generator.state),
            "physical_preparation_evaluations": len(set(masks)), "logical_initial_positions": 30,
            "independent_verification_evaluations": 30,
            "metadata": {"center_type": "FIXTURE", "escape_applicable": False}}


def fake_task(directory, task, *, sha=SHA):
    """Synthetic summaries test file handling only, never experimental endpoints."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    entries = []
    for start in banks.STARTS:
        for method in banks.METHODS:
            relative = f"runs/{task}-{start}-{method}"
            target = directory / relative
            target.mkdir(parents=True)
            search = {"new_calls": 5000, "physical_calls": 5000,
                      "record": {"score": {"value": 12}}}
            identity = {"schema_version": runner.RUN_SCHEMA, "protocol_id": banks.PROTOCOL,
                        "implementation_sha": sha, "task": task, "start": start,
                        "method": method, "seed": 70001,
                        "bank_manifest_sha256": "c" * 64, "preparation_sha": "d" * 40}
            with runner.JournalWriter(target / "journal.jsonl.gz") as sink:
                sink({"event": "FIXTURE_ONLY"})
            trace = [{"call": 0, "best_value": 10, "mean_feasible_value": 9, "diversity": 0.1},
                     {"call": 5000, "best_value": 12, "mean_feasible_value": 11, "diversity": 0.2}]
            runner.write_gzip_json(target / "trace.json.gz", trace)
            write_json(target / "verification.json", {"status": "VERIFIED", "summary": search})
            summary = dict(identity, status="COMPLETE", search=search, initial_value=10,
                           verification_calls=10, escape_applicable=False, escape=None,
                           journal_identity=file_identity(target / "journal.jsonl.gz"),
                           trace_identity=file_identity(target / "trace.json.gz"))
            write_json(target / "summary.json", summary)
            entries.append({"task": task, "start": start, "method": method,
                            "status": "COMPLETE", "path": relative})
    inventory = {"schema_version": runner.JOB_SCHEMA, "protocol_id": banks.PROTOCOL,
                 "implementation_sha": sha, "task": task, "task_index": banks.TASKS.index(task),
                 "seed": 70001, "expected_runs": 8, "complete_runs": 8, "runs": entries,
                 "compressed_bytes": 1024, "compressed_limit": 536870912,
                 "bank_manifest_sha256": "c" * 64, "preparation_sha": "d" * 40,
                 "bank_integrity_verification_calls": 480,
                 "initial_preparation_physical_calls_all_banks": 248}
    write_json(directory / "task_results.json", inventory)
    write_json(directory / "source_manifest.json", SOURCE)
    write_file_manifest(directory)


class BanksTests(unittest.TestCase):
    def test_clones_do_not_draw(self):
        rng = make_rngs(0, 0)["initialization"]
        before = canonical_bytes(rng.bit_generator.state)
        self.assertEqual(banks.generate_masks("Flat", "0" * 100, rng, start="cloned"), ["0" * 100] * 30)
        self.assertEqual(before, canonical_bytes(rng.bit_generator.state))

    def test_bank_first_empty_and_deterministic(self):
        a = make_rngs(1, 1)["initialization"]
        b = make_rngs(1, 1)["initialization"]
        masks = banks.generate_masks("OneMax", "0" * 100, a, start="bank")
        self.assertEqual(masks, banks.generate_masks("OneMax", "0" * 100, b, start="bank"))
        self.assertEqual(masks[0], "0" * 100)
        self.assertEqual(len(masks), 30)

    def test_jump_has_exact_k_zeros(self):
        for k in (4, 8):
            center = "1" * (100 - k) + "0" * k
            masks = banks.generate_masks(f"Jump{k}", center, make_rngs(2, 1)["initialization"], start="bank")
            self.assertEqual(masks[0], center)
            self.assertTrue(all(mask.count("0") == k for mask in masks))

    def test_duplicates_kept_small_jump(self):
        masks = banks.generate_masks("Jump1", "110", np.random.default_rng(4), start="bank", n=3, mu=30)
        self.assertEqual(len(masks), 30)
        self.assertLess(len(set(masks)), 30)

    def test_scores_and_oracle_isolation(self):
        bank = fixture_bank()
        self.assertEqual(banks.validate_bank(bank), bank)
        changed = copy.deepcopy(bank)
        changed["scores"][0]["value"] += 1
        with self.assertRaises(ValueError):
            banks.validate_bank(changed)
        changed = copy.deepcopy(bank)
        changed["problem"]["optimum"] = 100
        with self.assertRaises(ValueError):
            banks.validate_bank(changed)

    def test_accounting_bad_mask_and_identity(self):
        bank = fixture_bank(start="cloned")
        self.assertEqual(bank["physical_preparation_evaluations"], 1)
        for field, value in (("physical_preparation_evaluations", 30), ("seed", 70002), ("task_index", 9)):
            changed = copy.deepcopy(bank)
            changed[field] = value
            with self.assertRaises(ValueError):
                banks.validate_bank(changed)
        changed = copy.deepcopy(bank)
        changed["masks"][0] = "2" * 100
        with self.assertRaises(ValueError):
            banks.validate_bank(changed)

    def test_initialization_states_and_binary_mask_tampering(self):
        original = fixture_bank()
        for state_field in ("initialization_before", "initialization_after"):
            changed = copy.deepcopy(original)
            changed[state_field]["state"]["state"] += 1
            with self.subTest(state_field=state_field), self.assertRaises(ValueError):
                banks.validate_bank(changed)
        changed = copy.deepcopy(original)
        old = changed["masks"][5]
        changed["masks"][5] = ("1" if old[0] == "0" else "0") + old[1:]
        changed["scores"][5] = independent_score(changed["problem"], changed["masks"][5])
        changed["physical_preparation_evaluations"] = len(set(changed["masks"]))
        with self.assertRaises(ValueError):
            banks.validate_bank(changed)

    def test_independent_preparation_replay_avoids_production_generators(self):
        prepared = [fixture_bank(task=task, start=start)
                    for task in ("Flat", "OneMax", "Jump4", "Jump8") for start in banks.STARTS]
        with patch.object(banks, "make_rngs", side_effect=AssertionError("production RNG forbidden")), \
             patch.object(banks, "generate_masks", side_effect=AssertionError("production preparation forbidden")):
            for bank in prepared:
                with self.subTest(task=bank["task"], start=bank["start"]):
                    self.assertEqual(banks.validate_bank(bank), bank)


class FileTests(unittest.TestCase):
    def test_journal_deterministic_and_recoverable(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "a.gz", Path(directory) / "b.gz"
            for path in (first, second):
                sink = runner.JournalWriter(path)
                sink({"event": "candidate", "call": 1})
                sink.close()
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(list(runner.journal_records(first)), [{"event": "candidate", "call": 1}])

    def test_truncated_last_line_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "partial.gz"
            with gzip.open(path, "wb") as stream:
                stream.write(b'{"event":"candidate"}')
            with self.assertRaises(ValueError):
                list(runner.journal_records(path))


class AggregationTests(unittest.TestCase):
    def fixtures(self, directory, tasks=banks.TASKS):
        for task in tasks:
            fake_task(Path(directory) / task, task)

    def aggregate(self, source, output):
        receipts = {"artifacts": [{"status": "AVAILABLE", "task": task} for task in banks.TASKS]}
        with patch.object(reporting, "authenticate", return_value={"implementation_sha": SHA}), \
             patch.object(reporting, "source_manifest", return_value=SOURCE):
            return reporting.aggregate(source, output, SHA, receipts=receipts, make_plots=False)

    def test_full_64_summary_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixtures(root / "sources")
            report = self.aggregate(root / "sources", root / "output")
            self.assertEqual(report["status"], "COMPLETE_TECHNICAL_PILOT")
            self.assertEqual(report["complete_runs"], 64)
            self.assertEqual(report["completed_search_calls"], 320000)
            self.assertFalse(report["scientific_superiority_claim"])

    def test_missing_task_preserved_not_fabricated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixtures(root / "sources", banks.TASKS[:-1])
            report = self.aggregate(root / "sources", root / "output")
            self.assertEqual(report["status"], "INCOMPLETE_TECHNICAL")
            self.assertEqual(report["complete_runs"], 56)
            self.assertEqual(sum(r["status"] == "MISSING_RESULT" for r in report["runs"]), 8)

    def test_corrupted_member_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_task(root, "Flat")
            (root / "runs/Flat-cloned-baseline/summary.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                reporting.inspect_task(root, SHA, SOURCE)

    def test_mixed_sha_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_task(directory, "Flat", sha="e" * 40)
            with self.assertRaises(ValueError):
                reporting.inspect_task(directory, SHA, SOURCE)

    def test_duplicate_identity_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_task(root, "Flat")
            inventory = json.loads((root / "task_results.json").read_text(encoding="utf-8"))
            inventory["runs"][1] = copy.deepcopy(inventory["runs"][0])
            write_json(root / "task_results.json", inventory)
            write_file_manifest(root)
            with self.assertRaises(ValueError):
                reporting.inspect_task(root, SHA, SOURCE)


if __name__ == "__main__":
    unittest.main()

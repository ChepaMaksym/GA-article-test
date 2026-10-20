"""Main-series orchestration and provenance tests, executed only by CI."""

from copy import deepcopy
from dataclasses import fields
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from ...stagnation_diagnosis.banks import prepare_bank
from .. import runner


def identity():
    result = {name: "a" * 64 for name in runner.c.PROVENANCE_KEYS}
    result.update(protocol_id="GA-KNAPSACK-STAGNATION-DIAGNOSIS-MAIN-V1",
                  scientific_protocol_id=runner.SCIENTIFIC_PROTOCOL_ID,
                  technical_fingerprint=runner.TECHNICAL_FINGERPRINT,
                  bank_manifest_sha256=runner.BANK_REGISTRY_SHA256,
                  implementation_commit_sha="b" * 40,
                  registration_commit_sha="03c9433304856c884d962d5095feeed2397ddbaa",
                  run_id=123, run_attempt=1, phase="main")
    return result


class MainRunnerTests(unittest.TestCase):
    def test_search_interface_remains_the_exact_reference_free_dataclass(self):
        self.assertIs(runner.SearchProblem, runner.technical.SearchProblem)
        self.assertEqual({field.name for field in fields(runner.SearchProblem)},
                         {"n", "capacity", "weights", "profits"})

    def test_main_identity_does_not_relabel_historical_bank(self):
        main = identity()
        runner._check_identity(main)
        translated = runner._bank_identity(main)
        self.assertEqual(translated["protocol_id"], runner.SCIENTIFIC_PROTOCOL_ID)
        self.assertEqual(translated["implementation_fingerprint"], runner.TECHNICAL_FINGERPRINT)
        self.assertNotEqual(translated["protocol_id"], main["protocol_id"])
        self.assertNotEqual(translated["implementation_fingerprint"], main["implementation_fingerprint"])
        self.assertEqual(translated["bank_manifest_sha256"], main["bank_manifest_sha256"])

    def test_unknown_phase_protocol_or_bank_cannot_execute(self):
        for key, wrong in (("phase", "probe"), ("protocol_id", runner.SCIENTIFIC_PROTOCOL_ID),
                           ("scientific_protocol_id", "other"),
                           ("technical_fingerprint", "0" * 64),
                           ("bank_manifest_sha256", "0" * 64)):
            bad = {**identity(), key: wrong}
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner._check_identity(bad)

    def test_only_new_main_repeats_and_old_thirty_tasks_are_permitted(self):
        for seed in (92999, 93000, 93031, True, 93001.0):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                runner._select_instance("UC-s000", seed)
        for case in ("UC-s010", "UC-s999", "WC-s010", "other", "UC-s00x"):
            with self.subTest(case=case), self.assertRaises(ValueError):
                runner._select_instance(case, 93001)

    def test_committed_bank_rows_match_registered_seed_inventory(self):
        # This reads bytes and identities only; no regeneration or new search.
        row = runner._bank_record("UC-s000", 0, 93001)
        self.assertEqual(row["repeat_seed"], 93001)
        self.assertEqual(row["arrays_path"], "banks/UC-s000/93001/bank.npz")
        with self.assertRaises(ValueError):
            runner._bank_record("UC-s000", 1, 93001)

    def test_mixed_main_sha_or_old_bank_provenance_is_rejected(self):
        for key in runner.c.PROVENANCE_KEYS:
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner._same_identity({**identity(), key: "wrong"}, identity())

    def test_batch_retains_failure_and_does_not_retry_or_change_seeds(self):
        calls = []
        def fake_execute(case, seed, bank, output, provenance):
            calls.append(seed)
            if seed == 93003:
                raise RuntimeError("retained test failure")
            return {**provenance, "instance_id": case, "repeat_seed": seed,
                    "status": "COMPLETE", "verified": True}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "worker"
            with patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                    patch.object(runner, "_select_instance"), \
                    patch.object(runner, "execute_case", side_effect=fake_execute):
                result = runner.execute_batch("UC-s000", "unused", output, identity())
            self.assertEqual(calls, list(runner.SEEDS))
            self.assertEqual(result["completed_count"], 29)
            self.assertEqual(result["failed_count"], 1)
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertEqual(result["runs"][2]["failure"]["message"], "retained test failure")
            runner.c.verify_manifest(output)
            with self.assertRaises(ValueError):
                runner.verify_saved_batch(output, identity())

    def test_batch_byte_limit_stops_new_search_without_reducing_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "worker"
            with patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                    patch.object(runner, "_select_instance"), \
                    patch.object(runner.technical, "_bytes", return_value=runner.MAX_WORKER_BYTES - 1), \
                    patch.object(runner, "execute_case") as execute:
                result = runner.execute_batch("UC-s000", "unused", output, identity())
            execute.assert_not_called()
            self.assertEqual(result["completed_count"], 0)
            self.assertEqual(result["failed_count"], 30)
            self.assertEqual(len(result["runs"]), 30)

    def test_saved_worker_cannot_certify_duplicate_or_reordered_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [{"repeat_seed": seed, "instance_id": "UC-s000"} for seed in runner.SEEDS]
            rows[-1] = deepcopy(rows[0])
            runner.c.write_json(root / "worker_summary.json", {
                **identity(), "schema": "knapsack-stagnation-main-worker-v1",
                "status": "COMPLETE", "expected_seeds": list(runner.SEEDS),
                "completed_count": 30, "failed_count": 0, "runs": rows})
            runner.c.write_manifest(root)
            with self.assertRaises(ValueError):
                runner.verify_saved_batch(root, identity())

    def test_raw_journal_exists_before_replay_and_failure_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "studies/knapsack_parameters/inputs/source/fixture.txt"
            source.parent.mkdir(parents=True)
            source.write_text("fixture input", encoding="utf-8")
            instance = SimpleNamespace(n=100, capacity=50, weights=(1,) * 100,
                                       profits=(1,) * 100, instance_id="UC-s000",
                                       class_label="UC", family="s000", index=0,
                                       source_path="fixture.txt")
            bank, metadata = prepare_bank(instance, 0, 93001)
            fake_result = {"requests": {"masks": bank["masks"],
                                       **{key: bank[key] for key in ("weight", "profit", "feasible")}},
                           "generations": [], "summary": {"status": "fixture"}}
            output = root / "output"
            def reject_replay(*args, **kwargs):
                self.assertTrue((output / "raw/requests.npz").is_file())
                runner.c.verify_manifest(output / "raw")
                raise ValueError("independent rejection")
            with patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                    patch.object(runner.c, "ROOT", root), \
                    patch.object(runner, "_select_instance", return_value=(0, instance, {})), \
                    patch.object(runner, "_bank_record", return_value={"fixture": True}), \
                    patch.object(runner.technical, "_load_bank", return_value=(bank, metadata)), \
                    patch.object(runner, "run_search", return_value=fake_result) as search, \
                    patch.object(runner, "verify_search", side_effect=reject_replay), \
                    patch.object(runner, "analyze_run") as diagnosis:
                with self.assertRaisesRegex(ValueError, "independent rejection"):
                    runner.execute_case("UC-s000", 93001, "unused", output, identity())
                self.assertEqual(search.call_args.kwargs["budget"], 5030)
                self.assertFalse(hasattr(search.call_args.args[0], "optimum"))
                diagnosis.assert_not_called()
            saved = runner.c.read_json(output / "worker_summary.json")
            self.assertEqual(saved["status"], "INCOMPLETE")
            self.assertFalse(saved["verified"])
            self.assertEqual(saved["failure"]["message"], "independent rejection")
            runner.c.verify_manifest(output)

    def test_main_wrapper_saved_run_roundtrip_and_compact_corruption(self):
        # A tiny deterministic objective, but the registered 100-bit interface
        # and full 5030-request accounting exercise the actual unchanged kernel.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "studies/knapsack_parameters/inputs/source/fixture.txt"
            source.parent.mkdir(parents=True)
            source.write_text("independent fixture", encoding="utf-8")
            instance = SimpleNamespace(n=100, capacity=50, weights=(1,) * 100,
                                       profits=(1,) * 100, instance_id="UC-s000",
                                       class_label="UC", family="s000", index=0,
                                       source_path="fixture.txt")
            cases = {"UC-s000": {"payload": {"exact": {"confirmed_optimum": 50}}}}
            bank, metadata = prepare_bank(instance, 0, 93001)
            metadata_bytes = runner.c.canonical(metadata) + b"\n"
            reference = {"instance_id": "UC-s000", "case_ordinal": 0, "repeat_seed": 93001,
                         "metadata": {"bytes": len(metadata_bytes),
                                      "sha256": hashlib.sha256(metadata_bytes).hexdigest()}}
            output = root / "output"
            with patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                    patch.object(runner.c, "ROOT", root), \
                    patch.object(runner, "_select_instance", return_value=(0, instance, cases)), \
                    patch.object(runner, "_bank_record", return_value=reference), \
                    patch.object(runner.technical, "_load_bank", return_value=(bank, metadata)):
                saved = runner.execute_case("UC-s000", 93001, "unused", output, identity())
                verified = runner.verify_saved_case(output, identity())
                self.assertEqual(saved["status"], "COMPLETE")
                self.assertEqual(verified["new_evaluations"], 5000)
                self.assertEqual(len(verified["checkpoints"][-1]["pending_refs"]), 12)
                self.assertEqual(verified["checkpoints"], saved["checkpoints"])
                self.assertEqual(verified["aggregate_independent_verification"]["search"]["status"],
                                 "PASS_REPLAY")
                corrupted = deepcopy(saved)
                corrupted["accounting"]["search_new_evaluations"] -= 1
                runner.c.write_json(output / "worker_summary.json", corrupted)
                runner.c.write_manifest(output)
                with self.assertRaisesRegex(ValueError, "accounting differs"):
                    runner.verify_saved_case(output, identity())


if __name__ == "__main__":
    unittest.main()

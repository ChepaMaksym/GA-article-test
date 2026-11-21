"""CI-only pipeline checks using tiny synthetic searches, never main runs."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from . import runner
from .common import guard_main, registered_cases, registered_shards
from studies.knapsack_parameters.population_validation_100.common import read_json, sha


class MainRunnerChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A real fresh CI admission precedes all synthetic monkeypatches.
        cls.admitted_protocol, cls.admitted_authorization = guard_main()

    def setUp(self):
        from studies.knapsack_parameters.population_validation_100.preparation import make_bank

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        (self.inputs / "manifest.json").write_bytes(b'{"schema":"synthetic-runner-fixture"}\n')
        self.cases = registered_cases()[:3]
        self.shard = registered_shards()[0]
        self.authorization = deepcopy(self.admitted_authorization)
        self.protocol = deepcopy(self.admitted_protocol)
        self.protocol["checkpoints"] = [13, 25, 40]
        self.protocol["limits"].update(per_case_artifact_bytes=2 * 1024**2,
                                       shard_artifact_bytes=8 * 1024**2,
                                       shard_seconds=190, shard_reserve_seconds=45)
        self.problem = {"n": 100, "weights": [1] * 100,
                        "profits": [1] * 100, "capacity": 50}
        self.loaded = {}
        for fixed in self.cases:
            bank = make_bank(self.problem, fixed["task_index"], fixed["seed"], fixed["preparation_seed"])
            case = deepcopy(fixed)
            contents = {"problem": json.dumps(self.problem).encode("utf-8"),
                        "bank": json.dumps(bank).encode("utf-8"),
                        "certificate": b'{"optimum":50}', "source": b"synthetic source only"}
            for name, content in contents.items():
                path = self.inputs / fixed["case_id"] / (name + ".json")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                case[name] = {"path": path.relative_to(self.inputs).as_posix(),
                              "bytes": len(content), "sha256": sha(path)}
            self.loaded[fixed["case_id"]] = (case, deepcopy(self.problem), bank, {"optimum": 50})
        self.addCleanup(patch.stopall)
        patch.object(runner, "TOTAL", 40).start()
        patch.object(runner, "guard_main", return_value=(self.protocol, self.authorization)).start()
        patch.object(runner, "load_case", side_effect=self.load).start()

    def load(self, inputs, case_id, authorization):
        self.assertEqual(Path(inputs), self.inputs)
        self.assertEqual(authorization["source_manifest_sha256"], self.authorization["source_manifest_sha256"])
        return deepcopy(self.loaded[case_id])

    def case_folder(self, parent=None, index=0):
        parent = self.root / "output" if parent is None else parent
        return parent / self.cases[index]["case_id"]

    def produce(self, parent=None, index=0):
        folder = self.case_folder(parent, index)
        record = runner.run_case(self.inputs, self.cases[index]["case_id"], folder,
                                 self.authorization["authorization_id"])
        return folder, record

    def validate(self, folder, index=0):
        case = self.loaded[self.cases[index]["case_id"]][0]
        return runner.verify_saved_case(folder, case, sha(self.inputs / "manifest.json"), self.authorization)

    def save_record(self, folder, record):
        (folder / "record.json").write_bytes(json.dumps(record, sort_keys=True).encode("utf-8"))

    def test_tiny_case_replays_partial_generation_and_preserves_fixed_parameters(self):
        folder, record = self.produce()
        self.assertEqual(record["total_evaluations"], 40)
        self.assertEqual(record["initial_evaluations"], 13)
        self.assertEqual(record["new_evaluations"], 27)
        self.assertEqual(record["completed_generations"], 2)
        self.assertEqual(record["terminal_partial_children"], 3)
        self.assertEqual(self.validate(folder), record)
        verification = read_json(folder / "verification.json")
        self.assertEqual(verification["independent_score_checks"], 67)
        self.assertEqual(verification["final_parameters"], runner.PARAMETERS)
        journal = read_json(folder / "journal.json.gz")
        last = journal["generations"][-1]
        self.assertEqual(last["population_after"], last["population_before"])
        self.assertEqual(journal["initial_masks"], self.loaded[record["case_id"]][2]["masks"][:13])

    def test_changed_payload_is_rejected_before_reuse(self):
        folder, _ = self.produce()
        with (folder / "journal.json.gz").open("ab") as stream:
            stream.write(b"corrupt-payload")
        with self.assertRaises(ValueError):
            self.validate(folder)

    def test_modified_replay_counts_are_rejected_even_after_rehashing(self):
        folder, record = self.produce()
        path = folder / "verification.json"
        replay = read_json(path)
        replay["premutation_score_checks"] += 1
        path.write_bytes(json.dumps(replay).encode("utf-8"))
        record["artifact_hashes"]["verification.json"] = sha(path)
        record["artifact_bytes_before_receipt"] = sum((folder / name).stat().st_size
                                                     for name in runner.PAYLOAD_FILES)
        self.save_record(folder, record)
        with self.assertRaises(ValueError):
            self.validate(folder)

    def test_changed_manifest_or_initial_bank_cannot_be_reused(self):
        folder, record = self.produce()
        for key in ("inputs_manifest_sha256", "bank_sha256", "problem_sha256", "certificate_sha256"):
            changed = deepcopy(record)
            changed[key] = "0" * 64
            self.save_record(folder, changed)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(folder)
        self.save_record(folder, record)

    def test_saved_identity_and_integer_parameter_types_are_strict(self):
        folder, record = self.produce()
        for key, value in (("seed", 999999), ("mu", 15), ("elite_count", True), ("total_evaluations", 40.0),
                           ("search_seconds", -1), ("search_seconds", float("inf"))):
            changed = deepcopy(record)
            changed[key] = value
            self.save_record(folder, changed)
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.validate(folder)
        self.save_record(folder, record)

    def test_missing_payload_and_extra_failure_file_prevent_completed_status(self):
        folder, _ = self.produce()
        payload = folder / "operator_bins.json"
        original = payload.read_bytes()
        payload.unlink()
        with self.assertRaises(ValueError):
            self.validate(folder)
        payload.write_bytes(original)
        (folder / "failure.json").write_bytes(b'{"status":"failed"}')
        with self.assertRaises(ValueError):
            self.validate(folder)

    def test_partial_output_and_unknown_case_never_call_search(self):
        folder = self.case_folder()
        folder.mkdir(parents=True)
        original = b"retained incomplete evidence"
        pending = folder / "journal.json.gz.pending"
        pending.write_bytes(original)
        with patch.object(runner, "make_log") as search:
            with self.assertRaises(ValueError):
                runner.run_case(self.inputs, self.cases[0]["case_id"], folder)
            with self.assertRaises(ValueError):
                runner.run_case(self.inputs, "unregistered-case", self.root / "unknown")
            search.assert_not_called()
        self.assertEqual(pending.read_bytes(), original)

    def test_all_completed_current_cases_are_reused_without_new_search(self):
        output = self.root / "output"
        for index in range(3):
            self.produce(output, index)
        before = {p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob("*") if p.is_file()}
        with patch.object(runner, "make_log") as search:
            result = runner.run_shard(self.inputs, self.shard["shard_id"], output)
            search.assert_not_called()
        self.assertEqual(result["status"], "SHARD_VERIFIED")
        self.assertEqual(result["new_search_runs"], 0)
        self.assertEqual(result["retained_verified_runs"], 3)
        for name, content in before.items():
            self.assertEqual((output / name).read_bytes(), content)

    def test_corrupt_retained_case_is_failed_without_replacement_search(self):
        retained = self.root / "retained"
        for index in range(3):
            self.produce(retained, index)
        broken = self.case_folder(retained) / "journal.json.gz"
        broken.write_bytes(broken.read_bytes() + b"corruption")
        with patch.object(runner, "make_log") as search:
            result = runner.run_shard(self.inputs, self.shard["shard_id"],
                                      self.root / "resumed", retained_root=retained)
            search.assert_not_called()
        self.assertEqual(result["status"], "SHARD_INCOMPLETE")
        self.assertEqual(result["new_search_runs"], 0)
        self.assertEqual(result["retained_verified_runs"], 2)
        self.assertEqual([row["case_id"] for row in result["failed_cases"]], [self.cases[0]["case_id"]])
        self.assertTrue(broken.read_bytes().endswith(b"corruption"))

    def test_duplicate_retained_identity_is_rejected_before_search(self):
        retained = self.root / "retained"
        first, _ = self.produce(retained / "first")
        shutil.copytree(first, retained / "second" / first.name)
        with patch.object(runner, "make_log") as search, self.assertRaises(ValueError):
            runner.run_shard(self.inputs, self.shard["shard_id"], self.root / "duplicate-output",
                             retained_root=retained)
        search.assert_not_called()

    def test_failed_case_does_not_replace_seed_or_prevent_other_registered_cases(self):
        actual = runner.run_case
        called = []

        def one_failure(inputs, case_id, out, authorization_id=None):
            called.append(case_id)
            if case_id == self.cases[0]["case_id"]:
                raise ValueError("synthetic technical failure")
            return actual(inputs, case_id, out, authorization_id)

        with patch.object(runner, "run_case", side_effect=one_failure):
            result = runner.run_shard(self.inputs, self.shard["shard_id"], self.root / "failed-output")
        self.assertEqual(called, self.shard["case_ids"])
        self.assertEqual(result["newly_completed_case_ids"], self.shard["case_ids"][1:])
        self.assertEqual([row["case_id"] for row in result["failed_cases"]], [called[0]])
        self.assertEqual(result["status"], "SHARD_INCOMPLETE")

    def test_shard_resource_guard_defers_without_starting_a_case(self):
        readings = iter([0.0] + [200.0] * 20)
        with patch.object(runner.time, "perf_counter", side_effect=lambda: next(readings)), \
                patch.object(runner, "make_log") as search:
            result = runner.run_shard(self.inputs, self.shard["shard_id"], self.root / "deferred")
            search.assert_not_called()
        self.assertEqual(result["deferred_case_ids"], self.shard["case_ids"])
        self.assertEqual(result["new_search_runs"], 0)
        self.assertEqual(result["status"], "SHARD_INCOMPLETE")

    def test_full_search_is_counted_when_later_journal_retention_fails(self):
        actual_write = runner._write_bounded
        first = self.cases[0]["case_id"]

        def one_retention_failure(path, value, budget, **options):
            path = Path(path)
            if path.parent.name == first and path.name == "journal.json.gz":
                raise ValueError("synthetic postsearch retention failure")
            return actual_write(path, value, budget, **options)

        output = self.root / "postsearch-failure"
        with patch.object(runner, "_write_bounded", side_effect=one_retention_failure):
            result = runner.run_shard(self.inputs, self.shard["shard_id"], output)
        self.assertEqual(result["status"], "SHARD_INCOMPLETE")
        self.assertEqual(result["new_search_runs"], 3)
        self.assertEqual(len(result["newly_completed_case_ids"]), 2)
        failure = read_json(output / first / "failure.json")
        self.assertTrue(failure["search_call_started"])
        self.assertTrue(failure["search_call_completed"])
        self.assertEqual(failure["completed_search_evaluations_if_returned"], 40)


if __name__ == "__main__":
    unittest.main()

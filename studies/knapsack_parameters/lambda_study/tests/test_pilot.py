"""Independent small/fake fixtures; execution is restricted to GitHub Actions."""

import io
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from studies.knapsack_parameters.lambda_study import pilot


class OriginalObjective:
    jump_size = 2

    def __init__(self):
        self.seen = []

    def evaluate(self, query):
        self.seen.append(query)
        return query, False


class FakeAlgorithm:
    """A fixture that attempts queries; it implements no genetic operators."""

    def __init__(self, evaluator, *args):
        self.evaluator = evaluator
        self.solved = False
        self.generations = self.evaluations = 0
        self.offspring_size = 1
        self.parent = [evaluator.evaluate(0), 0]
        self.fit_gen, self.lambda_gen = [], []

    def __next__(self):
        # Updating only after both fixture queries reveals partial-generation caps.
        self.evaluator.evaluate(1)
        self.evaluator.evaluate(1)
        self.generations += 1
        self.evaluations += 2
        self.fit_gen.append(1)
        self.lambda_gen.append(1)


class PilotFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("These fixtures may run only in GitHub Actions")

    def test_exact_objective_cap_preserves_duplicate_queries_and_author_objective(self):
        original = OriginalObjective()
        evaluator = pilot.BoundedEvaluator(original, cap=4, clock=lambda: 0)
        result = pilot.bounded_iterations(evaluator, FakeAlgorithm, ())
        self.assertEqual(result["status"], "TECHNICAL_CALL_CAP")
        self.assertEqual(result["objective_calls"], 4)
        self.assertEqual(original.seen, [0, 1, 1, 1])
        self.assertEqual(result["author_state"]["generations"], 1)
        self.assertEqual(result["author_state"]["reported_evaluations"], 2)
        self.assertFalse(result["incomplete_generation_committed_as_result"])
        self.assertEqual(evaluator.jump_size, original.jump_size)
        self.assertEqual(result["full_gate"], "BLOCKED_NOT_AUTHORIZED")
        self.assertNotIn("PASS_FULL", json.dumps(result))

    def test_time_limit_blocks_next_query(self):
        moment = [0]
        original = OriginalObjective()
        evaluator = pilot.BoundedEvaluator(original, seconds=1, clock=lambda: moment[0])
        moment[0] = 1
        with self.assertRaisesRegex(pilot.TechnicalStop, "TECHNICAL_TIME_CAP"):
            evaluator.evaluate(10)
        self.assertEqual(original.seen, [])
        self.assertEqual(evaluator.calls, 0)

    def test_caps_cannot_be_raised(self):
        for values in ({"cap": 100001}, {"seconds": 31}, {"cap": 0}, {"seconds": 0}):
            with self.assertRaisesRegex(ValueError, "cannot increase"):
                pilot.BoundedEvaluator(OriginalObjective(), **values)

    def test_failure_preserves_stack_and_partial_call_count(self):
        def failing_factory(evaluator):
            evaluator.evaluate(9)
            raise TypeError("author dependency operation unsupported")
        evaluator = pilot.BoundedEvaluator(OriginalObjective())
        result = pilot.bounded_iterations(evaluator, failing_factory, ())
        self.assertEqual(result["status"], "TECHNICAL_FAILURE")
        self.assertEqual(result["objective_calls"], 1)
        self.assertIn("author dependency operation unsupported", result["failure"])
        self.assertNotIn("PASS_FULL", json.dumps(result))

    def test_fixed_profiles_have_same_seed_and_stable_identity(self):
        for case in pilot.CASES:
            first, second = pilot.profile(case), pilot.profile(case)
            self.assertEqual(first, second)
            self.assertEqual(first["seed"], 63001)
            self.assertEqual(first["max_objective_calls"], 100000)
            self.assertEqual(first["max_ga_seconds"], 30)
            self.assertEqual(first["compatibility_patches"], [])
            self.assertFalse(first["published_batch_rng_replay"])
            self.assertEqual(pilot.sha256_bytes(pilot.canonical_bytes(first)),
                             pilot.sha256_bytes(pilot.canonical_bytes(second)))
        with self.assertRaisesRegex(ValueError, "three registered"):
            pilot.profile("knapsack-main")

    def test_fresh_rng_seed_identity_repeats(self):
        import numpy
        random.seed(63001)
        numpy.random.seed(63001)
        first = pilot.rng_identity(numpy)
        random.random()
        numpy.random.random()
        self.assertNotEqual(first, pilot.rng_identity(numpy))
        random.seed(63001)
        numpy.random.seed(63001)
        self.assertEqual(first, pilot.rng_identity(numpy))

    def test_full_and_knapsack_cli_modes_are_unavailable(self):
        for operation in ("full", "knapsack", "calibrate", "main"):
            with self.assertRaises(SystemExit):
                pilot.main([operation, "--expected-sha", "a" * 40, "--output", "/tmp/forbidden"])

    def test_missing_frozen_descriptor_refuses_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(pilot, "MODULE_ROOT", Path(temporary)), patch.object(pilot, "api_get") as network:
                with self.assertRaisesRegex(ValueError, "committed frozen_sources"):
                    pilot.frozen_source(Path(temporary) / "source", {})
                network.assert_not_called()

    def test_process_exit_and_timeout_keep_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            failed = pilot.captured_process([sys.executable, "-c", "import sys; print('original stdout'); "
                       "print('original stderr', file=sys.stderr); sys.exit(7)"], directory, directory, "failure", timeout=2)
            self.assertEqual(failed["status"], "PROCESS_FAILED")
            self.assertEqual(failed["returncode"], 7)
            self.assertIn("original stdout", (directory / "failure.stdout.txt").read_text())
            self.assertIn("original stderr", (directory / "failure.stderr.txt").read_text())
            timed = pilot.captured_process([sys.executable, "-u", "-c", "import time; print('before timeout'); "
                       "time.sleep(10)"], directory, directory, "timeout", timeout=1)
            self.assertEqual(timed["status"], "PROCESS_TIMEOUT")
            self.assertIn("before timeout", (directory / "timeout.stdout.txt").read_text())

    def test_linux_colon_names_preserved_and_unsafe_paths_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            valid = "source/author/Raw/log_12:34:56"
            self.assertEqual(pilot.evidence_member(directory, valid), directory / valid)
            for relative in ("../escape", "/absolute", "source/C:drive/file", "source\\escape", ""):
                with self.assertRaises(ValueError):
                    pilot.evidence_member(directory, relative)

    def test_zip_manifest_checks_every_byte(self):
        with tempfile.TemporaryDirectory() as temporary:
            name, raw = "source/author/Raw/log_12:34:56", b"original author bytes\n"
            manifest = {"schema_version": "ga-knapsack-files-v1", "excludes_self": True,
                        "files": [{"path": name, "bytes": len(raw), "sha256": pilot.sha256_bytes(raw)}]}
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr(name, raw)
                archive.writestr("file_manifest.json", pilot.canonical_bytes(manifest))
            directory = pilot.extract_evidence(stream.getvalue(), Path(temporary) / "bundle")
            self.assertEqual((directory / name).read_bytes(), raw)
            (directory / name).write_bytes(raw + b"changed")
            with self.assertRaisesRegex(ValueError, "hash or length differs"):
                pilot.verify_evidence(directory)

    def test_completed_job_budget_never_claims_unfinished_duration(self):
        complete = {"id": 1, "name": "fixture", "status": "completed", "conclusion": "success",
                    "started_at": "2026-10-09T10:00:00Z", "completed_at": "2026-10-09T10:01:01Z"}
        running = {"id": 2, "name": "report", "status": "in_progress", "started_at": "2026-10-09T10:02:00Z"}
        self.assertEqual(pilot.completed_job_minutes([complete, running]),
                         (2, [{"job_id": 2, "name": "report", "status": "in_progress"}]))

    def test_unknown_throughput_cannot_become_full_projection(self):
        report = {"case": "maxsat-10", "status": "TECHNICAL_PREFIX", "probe": {"objective_calls": None}}
        projection = pilot.technical_projection([report], {"python_reported_evaluations_total": 10000})
        self.assertIsNone(projection["observations"][0]["observed_calls_per_second"])
        self.assertIsNone(projection["full_reproduction_runner_minutes"])
        self.assertFalse(projection["full_reproduction_authorized"])

    def test_compact_missing_counters_remain_unknown(self):
        compact = {"results_catalog": {"python_logs": [{"retained_runs": 2}], "cpp_batches": []}}
        self.assertIsNone(pilot.released_workload(compact)["python_reported_evaluations_total"])
        full = {"results_catalog": {"python_logs": [{"retained_runs": 2, "reported_evaluations_by_run": [7, 11]}], "cpp_batches": []}}
        self.assertEqual(pilot.released_workload(full)["python_reported_evaluations_total"], 18)

    def test_failed_cases_and_failed_fixtures_cannot_pass_aggregation(self):
        failures = pilot.technical_failures([{"case": "maxsat-10", "status": "TECHNICAL_BUILD_FAILURE"}], "failure")
        self.assertEqual(len(failures), 2)
        for status in pilot.VALID_TECHNICAL_STATUSES:
            self.assertEqual(pilot.technical_failures([{"case": "fixture", "status": status}], "success"), [])

    def test_failed_cli_preserves_report_then_raises(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "retained"
            with patch.object(pilot, "authenticate", return_value={}), \
                 patch.object(pilot, "frozen_source", side_effect=ValueError("source verification failed")):
                with self.assertRaisesRegex(ValueError, "archived evidence is retained"):
                    pilot.main(["run", "--case", "onemax-100", "--expected-sha", "a" * 40, "--output", str(output)])
            self.assertTrue((output / "file_manifest.json").is_file())
            report = pilot.read_json(output / "pilot-result.json")
            self.assertEqual(report["status"], "TECHNICAL_FAILURE")
            self.assertIn("source verification failed", report["failure"])
        with patch.object(pilot, "aggregate", return_value={"completion": "INCOMPLETE"}):
            with self.assertRaisesRegex(ValueError, "archived evidence is retained"):
                pilot.main(["aggregate", "--phase", "tests", "--expected-sha", "a" * 40, "--output", "/tmp/fixture"])

    def test_frozen_descriptor_binds_protocol_locks_and_attempt_name(self):
        identity = {field: f"identity-{field}" for field in pilot.FROZEN_IDENTITY_FIELDS}
        identity.update(full_reproduction_authorized=False, knapsack_execution_authorized=False)
        descriptor = {**identity, "run_id": 5, "run_attempt": 2, "artifact_name": "lambda-paper-audit-5-2"}
        pilot.validate_descriptor(descriptor, identity)
        for field in ("protocol_sha256", "runtime_lock_sha256", "author_requirements_sha256", "artifact_name"):
            changed = {**descriptor, field: "wrong-identity"}
            with self.assertRaises(ValueError):
                pilot.validate_descriptor(changed, identity)
        with patch.object(pilot, "committed_descriptor", return_value={**descriptor, "implementation_commit_sha": "a" * 40}), \
             patch.object(pilot, "api_get", return_value={"id": 5, "run_attempt": 1}) as api, \
             patch.object(pilot, "download_zip") as download:
            with self.assertRaises(ValueError):
                pilot.frozen_source(Path("/tmp/wrong-attempt"), identity)
            self.assertIn("/attempts/2", api.call_args.args[0])
            download.assert_not_called()

    def test_current_job_usage_queries_only_current_attempt(self):
        with patch.object(pilot, "api_get", return_value={"jobs": []}) as api:
            self.assertEqual(pilot.current_attempt_jobs({"run_id": 8, "run_attempt": 3})["jobs"], [])
            self.assertIn("/attempts/3/jobs?", api.call_args.args[0])
            self.assertNotIn("filter=all", api.call_args.args[0])


if __name__ == "__main__":
    unittest.main()

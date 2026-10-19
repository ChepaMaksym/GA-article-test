"""CI-only synthetic tests of authorization, transport and evidence ordering."""
from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.final_study import authority as a
from studies.knapsack_parameters.final_study import execution as e


class AuthorizationTests(unittest.TestCase):
    def test_current_final_gate_authenticates_and_historical_protected_bytes_are_unchanged(self):
        receipt = a.authenticate(runtime=True)
        self.assertEqual(receipt["registration_sha"], a.REGISTRATION_SHA)
        self.assertEqual(receipt["implementation_sha"], os.environ["GITHUB_SHA"])
        self.assertEqual(receipt["environment"]["python"], "3.12.14")
        registered = json.loads((a.MODULE / "registration.json").read_text(encoding="utf-8"))
        self.assertTrue(registered["protected_sha256"])
        for relative, expected in registered["protected_sha256"].items():
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256((a.ROOT / relative).read_bytes()).hexdigest(), expected)

    def test_historical_execution_gates_still_reject_this_later_protocol(self):
        from studies.knapsack_parameters.adaptation_analysis import authority as adaptation
        from studies.knapsack_parameters.adaptation_analysis import pilot_authority as pilot
        from studies.knapsack_parameters.bntga_selection import authority as archive
        for historical in (adaptation, pilot, archive):
            with self.subTest(protocol=historical.PROTOCOL), \
                 self.assertRaisesRegex(ValueError, "Historical files changed"):
                historical.authenticate(runtime=True)

    def test_regression_selection_excludes_exactly_three_old_context_checks_and_no_science(self):
        expected = {
            "studies.knapsack_parameters.adaptation_analysis.tests.test_authority.AuthorityTests.test_frozen_sources_and_runtime",
            "studies.knapsack_parameters.adaptation_analysis.tests.test_pilot_authority.PilotAuthorityTests.test_exact_registered_identity_and_frozen_environment",
            "studies.knapsack_parameters.bntga_selection.tests.test_authority.AuthorityTests.test_frozen_contract_and_runtime",
        }
        suite, selection = e.selected_regression_suite()
        excluded = {row["test_id"] for row in selection["excluded"]}
        self.assertEqual(excluded, expected)
        self.assertTrue(all(row["reason"] for row in selection["excluded"]))
        self.assertEqual(set(selection["selected_ids"]), set(selection["discovered_ids"]) - expected)
        self.assertEqual(selection["discovered_count"], selection["selected_count"] + 3)
        self.assertEqual(suite.countTestCases(), selection["selected_count"])
        self.assertFalse(selection["scientific_or_operator_checks_excluded"])
        self.assertFalse(selection["historical_authorization_code_modified"])

    def test_only_two_exact_markers_are_registered(self):
        self.assertEqual(a.phase("fix [knapsack-final:tests]"), "tests")
        self.assertEqual(a.phase("run [knapsack-final:probe]"), "probe")
        for message in ("", "[knapsack-final:main]", "[knapsack-final:prepare]",
                        "[knapsack-final:tests] [knapsack-final:probe]",
                        "[knapsack-final:tests] [skip ci]", "[knapsack-final:tests ]"):
            with self.subTest(message=message), self.assertRaises(ValueError):
                a.phase(message)

    def test_frozen_grant_is_ninety_minutes_without_main(self):
        grant = a.resource_grant()
        self.assertEqual(grant["runner_minutes_ceiling"], 90)
        self.assertEqual(grant["phase_reservation_minutes"], {"tests": 8, "probe": 76})
        for name in ("main_search_authorized", "holdout_search_authorized", "lambda_search_authorized",
                     "remaining_30_pilot_runs_authorized", "confirmatory_statistics_authorized"):
            self.assertIs(grant[name], False)

    def test_grant_checks_nested_types_and_every_semantic_constant(self):
        grant = a.resource_grant()
        for name, value in (("runner_minutes_ceiling", 91), ("probe_expected_runs", True),
                            ("probe_seed", 86002), ("new_evaluations_per_run", 5000.0),
                            ("main_search_authorized", 0), ("methods", list(reversed(a.METHODS))),
                            ("phase_reservation_minutes", {"tests": 8, "probe": 75})):
            changed = deepcopy(grant)
            changed[name] = value
            with self.subTest(name=name), patch.object(a, "read_json", return_value=changed), self.assertRaises(ValueError):
                a.resource_grant()

    def test_exact_phase_reservations_and_unknown_usage(self):
        grant = a.resource_grant()
        for phase, boundary in (("tests", 82), ("probe", 14)):
            a.check_allowance({"used_runner_minutes": boundary}, phase, grant)
            with self.assertRaises(ValueError):
                a.check_allowance({"used_runner_minutes": boundary + 1}, phase, grant)
        for value in (-1, True, 1.0, None, "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                a.check_allowance({"used_runner_minutes": value}, "probe", grant)
        with self.assertRaises(ValueError):
            a.check_allowance({"used_runner_minutes": 0}, "main", grant)

    @staticmethod
    def _job(identifier, seconds=61, conclusion="success"):
        return {"id": identifier, "conclusion": conclusion, "started_at": "2026-10-18T12:00:00Z",
                "completed_at": f"2026-10-18T12:{seconds // 60:02d}:{seconds % 60:02d}Z"}

    def test_resource_ledger_counts_all_prior_attempts_failure_and_cancellation(self):
        runs = [{"id": 4, "run_attempt": 2, "status": "completed"},
                {"id": 99, "run_attempt": 2, "status": "in_progress"}]
        def pages(path, key):
            if key == "workflow_runs":
                return runs
            if "/4/attempts/1/" in path:
                return [self._job(1, 61, "failure"), {"id": 7, "conclusion": "skipped"}]
            if "/4/attempts/2/" in path:
                return [self._job(2, 0, "cancelled")]
            if "/99/attempts/1/" in path:
                return [self._job(3, 121)]
            self.fail("Current attempt must be reserved, not scanned: " + path)
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "99", "GITHUB_RUN_ATTEMPT": "2"}), patch.object(a, "pages", side_effect=pages):
            usage = a.runner_usage()
        self.assertEqual(usage["used_runner_minutes"], 6)
        self.assertEqual(len(usage["prior_jobs"]), 3)

    def test_resource_ledger_rejects_concurrency_unknown_and_negative_durations(self):
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "99", "GITHUB_RUN_ATTEMPT": "1"}):
            with patch.object(a, "pages", return_value=[{"id": 4, "run_attempt": 1, "status": "in_progress"}]), self.assertRaises(ValueError):
                a.runner_usage()
            for job in ({"id": 1, "conclusion": "cancelled", "started_at": None, "completed_at": None},
                        {"id": 1, "conclusion": "success", "started_at": "2026-10-18T12:01:00Z",
                         "completed_at": "2026-10-18T12:00:00Z"}):
                def pages(path, key):
                    return ([{"id": 4, "run_attempt": 1, "status": "completed"}]
                            if key == "workflow_runs" else [job])
                with self.subTest(job=job), patch.object(a, "pages", side_effect=pages), self.assertRaises(ValueError):
                    a.runner_usage()

    def test_resource_ledger_rejects_duplicate_allocated_jobs(self):
        def pages(path, key):
            return ([{"id": 4, "run_attempt": 1, "status": "completed"}] if key == "workflow_runs"
                    else [self._job(1), self._job(1)])
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "99"}), patch.object(a, "pages", side_effect=pages), self.assertRaises(ValueError):
            a.runner_usage()

    @staticmethod
    def _provenance():
        return {"protocol_id": a.PROTOCOL, "registration_sha": a.REGISTRATION_SHA,
                "implementation_sha": "1" * 40, "source_manifest": {"files": [], "sha256": "f" * 64},
                "run_id": 99, "run_attempt": 1}

    def test_workers_reuse_central_permit_without_a_racing_api_budget_scan(self):
        provenance = self._provenance()
        grant = a.resource_grant()
        permit = {**provenance, "phase": "probe", "used_runner_minutes": 2,
                  "resource_grant": grant, "reserved_runner_minutes": 76,
                  "main_search_authorized": False, "holdout_search_authorized": False,
                  "lambda_search_authorized": False}
        with patch.object(a, "authenticate", return_value=provenance), patch.object(a, "verify_manifest"), \
             patch.object(a, "read_json", return_value=permit), patch.object(a, "resource_grant", return_value=grant), \
             patch.object(a, "runner_usage", side_effect=AssertionError("parallel re-scan")), \
             patch.dict(os.environ, {"COMMIT_MESSAGE": "[knapsack-final:probe]"}):
            self.assertEqual(a.check_permit("unused", "worker"), provenance)
            self.assertEqual(a.check_permit("unused", "aggregate"), provenance)
            for name, changed in (("run_id", 100), ("implementation_sha", "2" * 40),
                                  ("holdout_search_authorized", True), ("reserved_runner_minutes", 75)):
                invalid = deepcopy(permit)
                invalid[name] = changed
                with self.subTest(name=name), patch.object(a, "read_json", return_value=invalid), self.assertRaises(ValueError):
                    a.check_permit("unused", "worker")

    def test_manifest_detects_corruption_unlisted_and_unsafe_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a.write_json(root / "receipt.json", {"software_fixture": True})
            a.write_manifest(root)
            a.verify_manifest(root)
            (root / "extra.txt").write_text("extra", encoding="utf-8")
            with self.assertRaises(ValueError):
                a.verify_manifest(root)
            (root / "extra.txt").unlink()
            (root / "receipt.json").write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                a.verify_manifest(root)
            a.write_json(root / "file_manifest.json", {"protocol_id": a.PROTOCOL,
                "files": [{"path": "../outside.json", "bytes": 0, "sha256": "0" * 64}]})
            with self.assertRaises(ValueError):
                a.verify_manifest(root)

    def test_atomic_json_preserves_previous_bytes_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "receipt.json"
            a.write_json(path, {"previous": True})
            previous = path.read_bytes()
            with patch.object(a.os, "replace", side_effect=OSError("synthetic interrupted replacement")), \
                 self.assertRaisesRegex(OSError, "interrupted"):
                a.write_json(path, {"next": True})
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual(list(root.iterdir()), [path])

    def test_atomic_manifest_preserves_previous_manifest_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a.write_json(root / "receipt.json", {"previous": True})
            a.write_manifest(root)
            previous = (root / "file_manifest.json").read_bytes()
            with patch.object(a.os, "replace", side_effect=OSError("synthetic manifest interruption")), \
                 self.assertRaisesRegex(OSError, "interruption"):
                a.write_manifest(root)
            self.assertEqual((root / "file_manifest.json").read_bytes(), previous)
            a.verify_manifest(root)

    def test_green_receipt_path_cannot_escape_evidence(self):
        for name in ("../outside", "evidence/../outside", "evidence\\bad", "evidence/C:bad", "/tmp/evidence"):
            with self.subTest(name=name), patch.object(a, "read_json", return_value={
                    "protocol_id": a.PROTOCOL, "frozen": True, "receipt_directory": name}), self.assertRaises(ValueError):
                a.validated_tests()


class RawPersistenceTests(unittest.TestCase):
    def test_worker_transport_failure_is_recorded_for_incomplete_aggregation(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(a, "authenticate", return_value=AuthorizationTests._provenance()), \
             patch.object(a, "download_artifacts", side_effect=ValueError("synthetic corrupt artifact")), \
             patch("sys.argv", ["execution", "download", "--kind", "workers", "--output", directory]), \
             self.assertRaisesRegex(ValueError, "corrupt artifact"):
            try:
                e.main()
            finally:
                receipt = a.read_json(Path(directory) / "transport_errors.json")
                self.assertEqual(receipt["schema"], "ga-final-worker-transport-errors-v1")
                self.assertEqual(receipt["errors"], [{"type": "ValueError", "message": "synthetic corrupt artifact"}])

    def test_aggregation_cannot_claim_completion_after_worker_transport_error(self):
        from studies.knapsack_parameters.final_study import inputs
        provenance = AuthorizationTests._provenance()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(a, "check_permit", return_value=provenance), \
             patch.object(a, "validated_tests"), patch.object(inputs, "load_probe_bank", return_value={}), \
             patch.object(inputs, "validate_probe_freeze"):
            root = Path(directory)
            a.write_json(root / "workers" / "transport_errors.json", {**provenance,
                "schema": "ga-final-worker-transport-errors-v1", "errors": [{"message": "corrupt artifact"}]})
            result = e.aggregate(root / "summary", root / "workers", "unused")
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertEqual(result["errors"][0]["stage"], "worker_artifact_transport")
            self.assertEqual(result["missing_or_unverified_runs"], 10)
            a.verify_manifest(root / "summary")

    def test_gzip_is_atomic_roundtrips_and_refuses_overwrite(self):
        packet = {"schema": "software-fixture-only", "list": [1, 2, "українська"]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "worker" / "journal.json.gz"
            e.write_raw_atomic(path, packet)
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream), packet)
            self.assertFalse((path.parent.parent / ("." + path.name + ".partial")).exists())
            with self.assertRaises(ValueError):
                e.write_raw_atomic(path, packet)

    def test_capped_writer_refuses_oversize_without_silently_truncating(self):
        import io
        stream = io.BytesIO()
        bounded = e._CappedWriter(stream, 3)
        self.assertEqual(bounded.write(b"ab"), 2)
        with self.assertRaises(ValueError):
            bounded.write(b"cd")
        self.assertEqual(stream.getvalue(), b"ab")

    def test_lambda_or_unknown_profile_rejected_before_any_rng_creation(self):
        with self.assertRaises(ValueError):
            e.run_raw({}, "lambda_own")

    def test_registered_seed_binding_is_independent_of_logged_initial_state(self):
        import numpy as np
        bank = {"task_index": 2, "start_index": 1}
        channels = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
        states = {name: np.random.PCG64(np.random.SeedSequence([86001, 2, 1, i])).state
                  for i, name in enumerate(channels)}
        e._verify_seed_binding(bank, {"rng_initial": states})
        changed = deepcopy(states)
        changed["mutation"]["state"]["state"] += 1
        with self.assertRaises(ValueError):
            e._verify_seed_binding(bank, {"rng_initial": changed})

    def test_worker_saves_unverified_raw_before_independent_replay(self):
        from studies.knapsack_parameters.final_study import inputs
        provenance = AuthorizationTests._provenance()
        bank = {"task_index": 0, "start_index": 0, "source_identity": {"sha256": "fixture"}}
        raw = {"summary": {"best_profit": 1}, "software_fixture": True}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "worker"
            def verify(method, log):
                self.assertEqual(a.read_json(output / "worker_index.json")["status"], "RAW_SAVED_UNVERIFIED")
                a.verify_manifest(output)
                with gzip.open(output / "journal.json.gz", "rt", encoding="utf-8") as stream:
                    self.assertEqual(json.load(stream)["log"], raw)
                return {"verification_status": "VERIFIED"}
            with patch.object(a, "check_permit", return_value=provenance), patch.object(a, "validated_tests"), \
                 patch.object(inputs, "load_probe_bank", return_value=bank), patch.object(inputs, "validate_probe_freeze"), \
                 patch.object(e, "run_raw", return_value=raw), patch.object(e, "_verify_seed_binding"), \
                 patch.object(e, "verify_raw", side_effect=verify):
                result = e.worker(output, "UC-s000", "cloned", "classical", "unused")
            self.assertEqual(result["status"], "COMPLETE_VERIFIED_PROBE")
            self.assertTrue((output / "verification.json").is_file())

    def test_failed_replay_keeps_raw_and_does_not_claim_a_zero_result(self):
        from studies.knapsack_parameters.final_study import inputs
        bank = {"task_index": 0, "start_index": 0, "source_identity": {"sha256": "fixture"}}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(a, "check_permit", return_value=AuthorizationTests._provenance()), \
             patch.object(a, "validated_tests"), patch.object(inputs, "load_probe_bank", return_value=bank), \
             patch.object(inputs, "validate_probe_freeze"), patch.object(e, "_verify_seed_binding"), \
             patch.object(e, "run_raw", return_value={"summary": {"best_profit": 7}}), \
             patch.object(e, "verify_raw", side_effect=ValueError("synthetic replay failure")):
            output = Path(directory) / "worker"
            result = e.worker(output, "UC-s000", "cloned", "classical", "unused")
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertEqual(result["summary"]["best_profit"], 7)
            self.assertTrue((output / "journal.json.gz").is_file())
            self.assertIsNone(result["verification"])
            self.assertEqual(result["errors"][0]["stage"], "independent_replay")
            a.verify_manifest(output)

    def test_unregistered_condition_is_rejected_without_search(self):
        with patch.object(a, "check_permit", return_value=AuthorizationTests._provenance()), \
             patch.object(e, "run_raw", side_effect=AssertionError("search must not start")), self.assertRaises(ValueError):
            e.worker("unused", "UC-s010", "bank", "classical", "unused")

    def test_incomplete_aggregation_preserves_missing_as_missing(self):
        from studies.knapsack_parameters.final_study import inputs
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(a, "check_permit", return_value=AuthorizationTests._provenance()), \
             patch.object(a, "validated_tests"), patch.object(inputs, "load_probe_bank", return_value={}), \
             patch.object(inputs, "validate_probe_freeze"):
            root = Path(directory)
            (root / "workers").mkdir()
            result = e.aggregate(root / "summary", root / "workers", "unused")
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertEqual(result["verified_saved_runs"], 0)
            self.assertEqual(result["missing_or_unverified_runs"], 10)
            self.assertEqual(result["results"], [])
            self.assertFalse(result["confirmatory_statistics_performed"])
            self.assertFalse(result["superiority_claim_authorized"])
            a.verify_manifest(root / "summary")


if __name__ == "__main__":
    unittest.main()

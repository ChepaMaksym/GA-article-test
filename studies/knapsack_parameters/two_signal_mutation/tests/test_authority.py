"""CI-only gates and synthetic API fixtures; no scientific searches."""

from __future__ import annotations

import copy
import hashlib
import itertools
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.two_signal_mutation import authority as a
from studies.knapsack_parameters.two_signal_mutation import driver


def workflow_run(run_id, *, attempt=1, selected="tests", status="completed", message=None):
    return {"id": run_id, "run_attempt": attempt, "status": status,
            "head_commit": {"message": message if message is not None else f"[two-signal:{selected}]"}}


def allocated_job(job_id, seconds, *, conclusion="success"):
    # Fixed short fixtures are deliberately not real Actions records.
    minutes, remainder = divmod(seconds, 60)
    return {"id": job_id, "name": "fixture", "conclusion": conclusion,
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": f"2026-01-01T00:{minutes:02d}:{remainder:02d}Z"}


class AuthorityTests(unittest.TestCase):
    def test_one_exact_registered_marker_and_correct_scope(self):
        for selected in a.PHASES:
            self.assertEqual(a.phase(f"Execute [two-signal:{selected}]\nNo other marker"), selected)
            self.assertEqual(a.scope(selected), "main" if selected in ("prepare-main", "main") else "technical")

    def test_no_mixed_duplicate_unknown_or_unrelated_markers(self):
        for message in ("no marker", "[two-signal:tests] [two-signal:pilot]",
                        "[two-signal:tests] [two-signal:tests]", "[two-signal:unknown]",
                        "[other:tests]", "[two-signal:tests] [note]", "[two-signal:Tests]"):
            with self.subTest(message=message), self.assertRaises(ValueError):
                a.phase(message)
        with self.assertRaises(ValueError):
            a.scope("unregistered")

    def test_explicit_sixty_minute_technical_approval_with_all_reservations(self):
        for selected in ("tests", "prepare-pilot", "pilot"):
            grant = a.grant_for(selected)
            self.assertIs(grant["explicit_user_approval"], True)
            self.assertEqual(grant["runner_minutes_ceiling"], 60)
            self.assertEqual(grant["phase_reservations"], a.TECH_RESERVATIONS)
            self.assertEqual(grant["job_timeouts"], a.TECH_TIMEOUTS)
            self.assertEqual(sum(grant["phase_reservations"].values()), 59)
            self.assertEqual(grant["max_parallel"], 4)
            self.assertFalse(grant["main_search_authorized"])

    def test_main_and_main_banks_remain_blocked_without_separate_approval(self):
        original = a.read_json(a.MODULE / "resource_authorization.json")
        original["main"] = {"explicit_user_approval": False, "main_search_authorized": False}
        for selected in ("prepare-main", "main"):
            with self.subTest(selected=selected), patch.object(a, "read_json", return_value=original), self.assertRaises(ValueError):
                a.grant_for(selected)

    def test_measured_main_approval_has_disjoint_two_gib_journal_quotas(self):
        for selected in ("prepare-main", "main"):
            grant = a.grant_for(selected)
            self.assertTrue(grant["main_search_authorized"])
            self.assertEqual(grant["main_runs"], 2700)
            self.assertEqual(grant["runner_minutes_ceiling"], 240)
            self.assertEqual(grant["maximum_compressed_journal_bytes_total"], 2 ** 31)
            quota = a.journal_allowance(selected, grant)
            self.assertLessEqual(10 * quota, 2 ** 31)
            self.assertLessEqual(quota, grant["maximum_compressed_bytes_per_worker"])
        technical = a.grant_for("pilot")
        self.assertEqual(a.journal_allowance("pilot", technical), 536870912)

    def test_main_approval_cannot_omit_storage_or_resource_reservation(self):
        original = a.read_json(a.MODULE / "resource_authorization.json")
        mutations = (
            lambda grant: grant["main"].pop("maximum_compressed_journal_bytes_total"),
            lambda grant: grant["main"].__setitem__("maximum_compressed_journal_bytes_total", 3 * 2 ** 30),
            lambda grant: grant["main"]["phase_reservations"].__setitem__("main", 1),
            lambda grant: grant["main"].__setitem__("pilot_cost_receipt", {"pilot_runs": 23}),
        )
        for change in mutations:
            grant = copy.deepcopy(original)
            change(grant)
            with patch.object(a, "read_json", return_value=grant), self.assertRaises(ValueError):
                a.grant_for("main")

    def test_technical_approval_is_not_implicit_or_unbounded(self):
        original = a.read_json(a.MODULE / "resource_authorization.json")
        mutations = (
            lambda grant: grant["technical"].__setitem__("explicit_user_approval", False),
            lambda grant: grant["technical"].__setitem__("runner_minutes_ceiling", 61),
            lambda grant: grant["technical"].__setitem__("runner_minutes_ceiling", True),
            lambda grant: grant["technical"].__setitem__("main_search_authorized", True),
            lambda grant: grant["technical"].__setitem__("max_parallel", 8),
            lambda grant: grant["technical"].__setitem__("new_calls_per_run", 4999),
            lambda grant: grant["technical"]["phase_reservations"].__setitem__("pilot", 1),
            lambda grant: grant["technical"]["job_timeouts"].__setitem__("worker", 60),
        )
        for change in mutations:
            grant = copy.deepcopy(original)
            change(grant)
            with patch.object(a, "read_json", return_value=grant), self.assertRaises(ValueError):
                a.grant_for("tests")

    def test_allowance_uses_remaining_cumulative_budget_not_fresh_budget(self):
        grant = a.grant_for("pilot")
        a.check_allowance("pilot", {"used_runner_minutes": 17}, grant)
        for used in (18, 60, 61, -1, None, True, 0.5):
            with self.subTest(used=used), self.assertRaises(ValueError):
                a.check_allowance("pilot", {"used_runner_minutes": used}, grant)
        with self.assertRaises(ValueError):
            a.check_allowance("unknown", {"used_runner_minutes": 0}, grant)

    def test_api_pagination_preserves_query_and_reads_all_pages(self):
        calls = []

        def response(endpoint):
            calls.append(endpoint)
            return {"jobs": list(range(100)) if endpoint.endswith("page=1") else [100]}

        with patch.object(a, "api", side_effect=response):
            rows = list(a.pages("/fixture?filter=all", "jobs"))
        self.assertEqual(rows, list(range(101)))
        self.assertEqual(calls, ["/fixture?filter=all&per_page=100&page=1",
                                 "/fixture?filter=all&per_page=100&page=2"])

    def test_all_prior_attempts_cancelled_jobs_and_upward_rounding_count(self):
        runs = [workflow_run(30, attempt=2, status="in_progress"),
                workflow_run(10, attempt=2), workflow_run(20, selected="main")]
        payloads = {
            "/actions/runs/30/attempts/1/jobs": [allocated_job(31, 61, conclusion="cancelled")],
            "/actions/runs/10/attempts/1/jobs": [allocated_job(11, 0), allocated_job(12, 60),
                                                {"id": 13, "conclusion": "skipped"}],
            "/actions/runs/10/attempts/2/jobs": [allocated_job(14, 61)],
            "/actions/runs/20/attempts/1/jobs": [allocated_job(21, 10)],
        }
        requested = []

        def pages(endpoint, key):
            requested.append(endpoint)
            return iter(runs if key == "workflow_runs" else payloads[endpoint])

        with patch.dict(os.environ, {"GITHUB_RUN_ID": "30", "GITHUB_RUN_ATTEMPT": "2"}), \
                patch.object(a, "pages", side_effect=pages):
            receipt = a.runner_usage("tests")
        self.assertEqual(receipt["used_runner_minutes"], 6)
        self.assertEqual([row["runner_minutes"] for row in receipt["jobs"]], [2, 1, 1, 2])
        self.assertEqual({(row["run_id"], row["run_attempt"]) for row in receipt["jobs"]},
                         {(30, 1), (10, 1), (10, 2)})
        self.assertNotIn("/actions/runs/30/attempts/2/jobs", requested)

    def test_unknown_phase_or_incomplete_usage_blocks_instead_of_zero(self):
        bad_records = (
            (workflow_run(10, message="unknown execution"), [allocated_job(11, 1)]),
            (workflow_run(10, status="in_progress"), [allocated_job(11, 1)]),
            (workflow_run(10), [{"id": 11, "name": "fixture", "conclusion": "cancelled",
                                 "started_at": "2026-01-01T00:00:00Z", "completed_at": None}]),
            (workflow_run(10), [{**allocated_job(11, 1), "started_at": "2026-01-01T00:01:00Z"}]),
            (workflow_run(10), [allocated_job(11, 1), allocated_job(11, 2)]),
        )
        for run, jobs in bad_records:
            with self.subTest(run=run, jobs=jobs):
                def pages(endpoint, key):
                    return iter([run] if key == "workflow_runs" else jobs)
                with patch.dict(os.environ, {"GITHUB_RUN_ID": "30", "GITHUB_RUN_ATTEMPT": "1"}), \
                        patch.object(a, "pages", side_effect=pages), self.assertRaises(ValueError):
                    a.runner_usage("pilot")

    def test_api_failure_never_turns_into_zero_usage(self):
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "30", "GITHUB_RUN_ATTEMPT": "1"}), \
                patch.object(a, "pages", side_effect=RuntimeError("unknown API usage")), \
                self.assertRaises(RuntimeError):
            a.runner_usage("tests")

    def test_unknown_unallocated_run_does_not_consume_or_invent_minutes(self):
        run = workflow_run(10, message="unmarked documentation commit")

        def pages(endpoint, key):
            return iter([run] if key == "workflow_runs" else [{"id": 11, "conclusion": "skipped"}])

        with patch.dict(os.environ, {"GITHUB_RUN_ID": "30", "GITHUB_RUN_ATTEMPT": "1"}), \
                patch.object(a, "pages", side_effect=pages):
            usage = a.runner_usage("tests")
        self.assertEqual(usage["used_runner_minutes"], 0)
        self.assertEqual(usage["jobs"], [])

    def test_source_manifest_is_deterministic_and_covers_implementation(self):
        first, second = a.source_manifest(), a.source_manifest()
        self.assertEqual(first, second)
        paths = [row["path"] for row in first["files"]]
        self.assertEqual(paths, sorted(set(paths)))
        expected = {a.REL + name for name in
                    ("engine.py", "verifier.py", "analysis.py", "plots.py", "authority.py", "banks.py", "driver.py",
                     "PROTOCOL_UK.md", "protocol.json", "registration.json", "environment.json")}
        expected |= {a.WORKFLOW, "studies/adaptive_parameters/mutation_only/engine.py",
                     "studies/adaptive_parameters/mutation_only/verifier.py"}
        self.assertTrue(expected <= set(paths))
        self.assertFalse(any(path.startswith(a.REL + "inputs/") or path.startswith(a.REL + "evidence/")
                             or path == a.REL + "frozen_tests.json" for path in paths))
        self.assertEqual(first["sha256"], hashlib.sha256(a.canonical(first["files"])).hexdigest())
        for row in first["files"]:
            self.assertEqual(a.identity(a.ROOT / row["path"]),
                             {"bytes": row["bytes"], "sha256": row["sha256"]})

    def test_registration_hashes_still_match_frozen_existing_bytes(self):
        registration = a.read_json(a.MODULE / "registration.json")
        for relative, field in (("PROTOCOL_UK.md", "protocol_sha256"),
                                ("protocol.json", "machine_protocol_sha256")):
            self.assertEqual(a.identity(a.MODULE / relative)["sha256"], registration[field])
        for relative, field in (
                ("studies/adaptive_parameters/mutation_only/engine.py", "legacy_engine_sha256"),
                ("studies/adaptive_parameters/mutation_only/verifier.py", "legacy_verifier_sha256"),
                ("studies/knapsack_parameters/basic_parameters/inputs/frozen_holdout.json", "frozen_holdout_sha256"),
                ("studies/knapsack_parameters/basic_parameters/inputs/frozen_holdout_preparation.json",
                 "frozen_holdout_preparation_sha256")):
            self.assertEqual(a.identity(a.ROOT / relative)["sha256"], registration[field])

    def test_balanced_execution_order_uses_all_six_permutations(self):
        permutations = set(itertools.permutations(a.METHODS))
        pilot = [driver.balanced_order({"task_index": index // 2, "start_index": index % 2}, "pilot")
                 for index in range(6)]
        main = [driver.balanced_order({"seed": seed}, "main") for seed in range(94001, 94031)]
        self.assertEqual(set(pilot), permutations)
        self.assertEqual(set(main), permutations)
        self.assertTrue(all(main.count(order) == 5 for order in permutations))


if __name__ == "__main__":
    unittest.main()

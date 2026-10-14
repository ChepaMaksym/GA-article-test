"""CI-only, synthetic raw-API metadata fixtures; no searches or result analysis."""

from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import unittest

from .. import adapter
from ...main_study import contract


def job(job_id, name, attempt, *, conclusion="success"):
    return {"id": job_id, "name": name, "run_id": adapter.SOURCE_RUN, "run_attempt": attempt,
            "head_sha": adapter.SOURCE_SHA, "head_branch": adapter.SOURCE_BRANCH,
            "status": "completed", "conclusion": conclusion, "steps": [],
            "runner_id": None, "runner_name": None, "runner_group_id": None, "runner_group_name": None}


def metadata(auxiliary_first=0):
    run = {"id": adapter.SOURCE_RUN, "head_sha": adapter.SOURCE_SHA,
           "head_branch": adapter.SOURCE_BRANCH, "status": "completed", "conclusion": "failure", "run_attempt": 2}
    placeholder = job(adapter.PLACEHOLDER_ID, adapter.PLACEHOLDER_NAME, 1, conclusion="skipped")
    placeholder.update(started_at="2026-10-14T12:20:09Z", completed_at="2026-10-14T12:20:08Z")
    phase = job(adapter.PHASE_FAILURE_ID, "phase", 1, conclusion="failure")
    first = [phase, placeholder] + [job(3000000 + i, f"unused-service-{i}", 1, conclusion="skipped") for i in range(auxiliary_first)]
    second = [job(4000000 + i, name, 2) for i, name in enumerate(sorted(adapter.registered_names()))]
    return run, {1: first, 2: second}


class RawFixture:
    def __init__(self, run, attempts):
        self.run, self.attempts, self.calls = deepcopy(run), deepcopy(attempts), []

    def __call__(self, path):
        self.calls.append(path)
        parsed = urlsplit(path)
        if parsed.path == adapter.SOURCE_BASE:
            return deepcopy(self.run)
        if parsed.path in adapter.JOB_ENDPOINTS.values():
            attempt = next(a for a, endpoint in adapter.JOB_ENDPOINTS.items() if parsed.path == endpoint)
            query = parse_qs(parsed.query)
            page, size = int(query.get("page", [1])[0]), int(query.get("per_page", [100])[0])
            jobs = self.attempts[attempt]
            return {"total_count": len(jobs), "jobs": deepcopy(jobs[(page - 1) * size:page * size])}
        return {"unchanged": path, "token_or_headers_logged": False}


class FixedMetadataTests(unittest.TestCase):
    def validate(self, run, attempts, binding=None):
        return adapter.validate_source_metadata(binding or deepcopy(adapter.FIXED_BINDING), run, attempts, adapter.registered_names())

    def test_exact_skipped_placeholder_and_reversed_unused_timestamps_are_accepted(self):
        run, attempts = metadata()
        result = self.validate(run, attempts)
        self.assertEqual(result["excluded_count"], 1)
        self.assertEqual(result["source_job_count"], 104)
        self.assertEqual(result["excluded_job"]["id"], adapter.PLACEHOLDER_ID)
        self.assertEqual(result["excluded_job"]["started_at"], "2026-10-14T12:20:09Z")
        self.assertEqual(result["excluded_job"]["completed_at"], "2026-10-14T12:20:08Z")

    def test_same_name_with_execution_or_wrong_exact_id_is_never_filtered(self):
        for change in ({"steps": [{"name": "Search", "conclusion": "success"}]},
                       {"runner_id": 999}, {"runner_name": "executed-runner"},
                       {"conclusion": "failure"}, {"status": "in_progress"}, {"id": 9999999}):
            run, attempts = metadata()
            attempts[1][1].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(run, attempts)

    def test_real_failed_skipped_or_pending_source_job_is_not_discarded(self):
        for change in ({"conclusion": "failure"}, {"conclusion": "skipped"}, {"status": "in_progress"}):
            run, attempts = metadata()
            attempts[2][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(run, attempts)

    def test_missing_duplicate_or_unknown_concrete_names_fail_closed(self):
        for mutation in ("missing", "duplicate_id", "duplicate_name", "unknown"):
            run, attempts = metadata()
            if mutation == "missing":
                attempts[2].pop()
            elif mutation == "duplicate_id":
                attempts[2][-1]["id"] = attempts[2][0]["id"]
            elif mutation == "duplicate_name":
                attempts[2][-1]["name"] = attempts[2][0]["name"]
            else:
                attempts[2][-1]["name"] = "main (unregistered-task)"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.validate(run, attempts)

    def test_attempt_one_concrete_main_even_skipped_is_not_hidden(self):
        run, attempts = metadata()
        attempts[1].append(job(8888888, sorted(adapter.registered_names())[0], 1, conclusion="skipped"))
        with self.assertRaises(ValueError):
            self.validate(run, attempts)

    def test_source_and_job_sha_branch_run_and_attempt_are_required(self):
        for field, bad in (("head_sha", "a" * 40), ("head_branch", "main"), ("run_id", 1), ("run_attempt", 1)):
            run, attempts = metadata()
            attempts[2][0][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(run, attempts)
        run, attempts = metadata()
        run["head_sha"] = "a" * 40
        with self.assertRaises(ValueError):
            self.validate(run, attempts)
        run, attempts = metadata()
        del attempts[2][0]["run_id"]
        with self.assertRaises(ValueError):
            self.validate(run, attempts)

    def test_binding_is_not_a_generic_permission_for_another_run(self):
        run, attempts = metadata()
        binding = deepcopy(adapter.FIXED_BINDING)
        binding["source_run_id"] += 1
        with self.assertRaises(ValueError):
            self.validate(run, attempts, binding)

    def test_exact_infrastructure_failure_must_be_present(self):
        run, attempts = metadata()
        attempts[1][0]["conclusion"] = "success"
        with self.assertRaises(ValueError):
            self.validate(run, attempts)


class PaginationAndContextTests(unittest.TestCase):
    def test_repaging_after_removal_does_not_hide_the_next_raw_page(self):
        run, attempts = metadata(auxiliary_first=99)
        raw = RawFixture(run, attempts)
        cache = {attempt: adapter.collect_job_pages(raw, adapter.JOB_ENDPOINTS[attempt]) for attempt in (1, 2)}
        self.assertEqual(cache[1]["total_count"], 101)
        self.assertEqual(len(cache[1]["pages"]), 2)
        first = adapter.jobs_view(cache, 1, adapter.JOB_ENDPOINTS[1] + "?per_page=100&page=1")
        self.assertEqual(first["total_count"], 100)
        self.assertEqual(len(first["jobs"]), 100)
        self.assertNotIn(adapter.PLACEHOLDER_ID, [item["id"] for item in first["jobs"]])
        self.assertEqual(first["jobs"][-1]["id"], attempts[1][-1]["id"])
        second = adapter.jobs_view(cache, 1, adapter.JOB_ENDPOINTS[1] + "?per_page=100&page=2")
        self.assertEqual(second, {"total_count": 100, "jobs": []})
        unchanged = adapter.jobs_view(cache, 2, adapter.JOB_ENDPOINTS[2] + "?per_page=100&page=2")
        self.assertEqual(unchanged["total_count"], 104)
        self.assertEqual(unchanged["jobs"], attempts[2][100:])

    def test_raw_missing_page_and_duplicate_ids_are_rejected(self):
        run, attempts = metadata()
        raw = RawFixture(run, attempts)
        def truncated(path):
            response = raw(path)
            response["jobs"] = response["jobs"][:99]
            return response
        with self.assertRaises(ValueError):
            adapter.collect_job_pages(truncated, adapter.JOB_ENDPOINTS[2])
        attempts[2][-1]["id"] = attempts[2][0]["id"]
        with self.assertRaises(ValueError):
            adapter.collect_job_pages(RawFixture(run, attempts), adapter.JOB_ENDPOINTS[2])

    def test_unsupported_or_duplicate_pagination_is_rejected(self):
        run, attempts = metadata()
        raw = RawFixture(run, attempts)
        cache = {attempt: adapter.collect_job_pages(raw, adapter.JOB_ENDPOINTS[attempt]) for attempt in (1, 2)}
        for query in ("?per_page=101&page=1", "?page=0", "?page=1&page=2", "?filter=latest"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                adapter.jobs_view(cache, 1, adapter.JOB_ENDPOINTS[1] + query)

    def test_context_keeps_raw_budget_api_and_restores_aggregator_api_with_audit(self):
        run, attempts = metadata()
        raw = RawFixture(run, attempts)
        support = SimpleNamespace(api=raw)
        with tempfile.TemporaryDirectory() as directory, patch.object(contract, "api", raw):
            with adapter.filtered_source_api(support, raw_api=raw, binding=deepcopy(adapter.FIXED_BINDING),
                                            expected_names=adapter.registered_names(), audit_dir=directory):
                self.assertIs(contract.api, raw)
                raw_first = adapter.collect_job_pages(contract.api, adapter.JOB_ENDPOINTS[1])
                shown_first = adapter.collect_job_pages(support.api, adapter.JOB_ENDPOINTS[1])
                self.assertEqual(len(raw_first["jobs"]), 2)
                self.assertEqual(len(shown_first["jobs"]), 1)
                self.assertEqual(support.api("/actions/artifacts/123"), raw("/actions/artifacts/123"))
            self.assertIs(support.api, raw)
            audit = contract.read_json(Path(directory) / "adapter_audit.json")
            raw_audit = contract.read_json(Path(directory) / "raw_api_responses.json")
            self.assertEqual(audit["excluded_count"], 1)
            self.assertEqual(audit["status"], "AGGREGATION_RETURNED_SUCCESSFULLY")
            self.assertTrue(audit["aggregator_api_restored"])
            self.assertFalse(audit["contract_api_modified"])
            self.assertIn("sha256", audit["adapter_identity"])
            raw_ids = [entry["response"]["jobs"][1]["id"] for entry in raw_audit["responses"]
                       if entry["path"] == adapter.JOB_ENDPOINTS[1] + "?per_page=100&page=1"]
            self.assertEqual(raw_ids, [adapter.PLACEHOLDER_ID])

    def test_aggregation_exception_restores_api_and_preserves_failure_audit(self):
        run, attempts = metadata()
        raw = RawFixture(run, attempts)
        support = SimpleNamespace(api=raw)
        with tempfile.TemporaryDirectory() as directory, patch.object(contract, "api", raw):
            with self.assertRaisesRegex(RuntimeError, "synthetic body failure"):
                with adapter.filtered_source_api(support, raw_api=raw, binding=deepcopy(adapter.FIXED_BINDING),
                                                expected_names=adapter.registered_names(), audit_dir=directory):
                    raise RuntimeError("synthetic body failure")
            self.assertIs(support.api, raw)
            audit = contract.read_json(Path(directory) / "adapter_audit.json")
            self.assertEqual(audit["status"], "AGGREGATION_FAILED")
            self.assertTrue(audit["aggregator_api_restored"])


if __name__ == "__main__":
    unittest.main()

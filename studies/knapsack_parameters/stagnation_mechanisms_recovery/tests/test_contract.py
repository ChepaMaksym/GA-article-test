"""Recovery authority fixtures; no search or source analysis is performed."""

from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from .. import contract as c


class RecoveryAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Read frozen identities only. Feature values are not recalculated.
        cls.prior = c.prior_audit()
        cls.source_identity = deepcopy(cls.prior["source_identity"])
        cls.current = {"protocol_id": c.PROTOCOL_ID,
                       "registration_commit_sha": c.REGISTRATION_SHA,
                       "implementation_commit_sha": "a" * 40,
                       "implementation_fingerprint": "b" * 64,
                       "protocol_sha256": "c" * 64,
                       "scientific_implementation_fingerprint": cls.prior["implementation_fingerprint"],
                       "run_id": 70000000001, "run_attempt": 1}

    def usage(self, minutes=51, payload=0, zipped=0, workers=0):
        return {"used_runner_minutes": minutes,
                "previous_payload_upper_bound_bytes": payload,
                "previous_artifact_zip_bytes": zipped,
                "recovery_workers": workers, "both_workflows_included": True}

    def receipt(self, family):
        provenance = ({key: self.prior[key] for key in c.base.PROVENANCE_KEYS}
                      if family in c.REUSED_FAMILIES else deepcopy(self.current))
        rows = [{"instance_id": f"{label}-{family}", "repeat_seed": seed,
                 "family": family, "status": "PASS", "verified": True,
                 "source_identity": deepcopy(self.source_identity)}
                for label in ("UC", "WC", "SC") for seed in range(93001, 93031)]
        return {**provenance, "family": family, "source_identity": deepcopy(self.source_identity),
                "status": "COMPLETE", "completed_count": 90, "errors": [], "rows": rows}

    def validate(self, receipt, family):
        with patch.object(c, "prior_audit", return_value=self.prior), \
                patch.object(c.base, "source_summary", return_value={"provenance": self.source_identity}):
            return c.validate_producer(receipt, family, self.current)

    def test_only_three_missing_families_and_original_shared_ceiling(self):
        self.assertEqual(c.RECOVER_FAMILIES, ("s004", "s005", "s006"))
        self.assertEqual(c.REUSED_FAMILIES, ("s000", "s001", "s002", "s003", "s007", "s008", "s009"))
        self.assertEqual(set(c.RECOVER_FAMILIES) & set(c.REUSED_FAMILIES), set())
        self.assertEqual(set(c.RECOVER_FAMILIES) | set(c.REUSED_FAMILIES), {f"s{i:03d}" for i in range(10)})
        self.assertEqual(c.RESERVATIONS, {"tests": 4, "recover": 34})
        self.assertEqual(c.CEILING, 90)
        self.assertEqual(c.BYTE_CEILING, 1024 ** 3)
        self.assertEqual(self.prior["verified_rows"], 630)
        self.assertFalse(self.prior["complete"])

    def test_exact_single_recovery_phase_marker(self):
        for phase in ("tests", "recover"):
            self.assertEqual(c.phase(f"Finish technical recovery [knapsack-stagnation-recovery:{phase}]"), phase)
        for marker in ("", "[knapsack-stagnation-mechanisms:analyze]", "[knapsack-stagnation-recovery:main]",
                       "[knapsack-stagnation-recovery:recover] [skip ci]",
                       "[knapsack-stagnation-recovery:tests] [knapsack-stagnation-recovery:recover]",
                       "[knapsack-stagnation-recovery:recover] [knapsack-stagnation-recovery:recover]"):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                c.phase(marker)

    def test_shared_runner_reservation_includes_fifty_one_prior_minutes(self):
        c.check_allowance(self.usage(), "tests")
        c.check_allowance(self.usage(), "recover")
        c.check_allowance(self.usage(minutes=86), "tests")
        c.check_allowance(self.usage(minutes=56), "recover")
        for minutes, phase in ((87, "tests"), (57, "recover"), (90, "recover"), (50, "tests"), (0, "recover")):
            with self.subTest(minutes=minutes, phase=phase), self.assertRaises(ValueError):
                c.check_allowance(self.usage(minutes=minutes), phase)

    def test_unknown_negative_boolean_or_incomplete_accounting_blocks(self):
        invalid = [{}, self.usage(minutes=-1), self.usage(minutes=True), self.usage(minutes=51.0),
                   self.usage(payload=-1), self.usage(payload=False), self.usage(payload=None),
                   self.usage(zipped=-1), self.usage(zipped=True), self.usage(zipped=None),
                   {**self.usage(), "both_workflows_included": False},
                   {**self.usage(), "both_workflows_included": 1}]
        for field in ("used_runner_minutes", "previous_payload_upper_bound_bytes",
                      "previous_artifact_zip_bytes", "both_workflows_included"):
            missing = self.usage()
            missing.pop(field)
            invalid.append(missing)
        for usage in invalid:
            with self.subTest(usage=usage), self.assertRaises(ValueError):
                c.check_allowance(usage, "recover")
        with self.assertRaises(ValueError):
            c.check_allowance(self.usage(), "search")

    def test_unknown_or_previously_started_recovery_workers_block_matrix(self):
        for workers in (None, -1, True, False, 1, 3, 0.0):
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                c.check_allowance(self.usage(workers=workers), "recover")
        missing = self.usage()
        missing.pop("recovery_workers")
        with self.assertRaises(ValueError):
            c.check_allowance(missing, "recover")

    def test_shared_storage_reservation_counts_payload_not_only_small_zip(self):
        reserve = c.CAPS["permit"] + 3 * c.CAPS["worker"] + c.CAPS["summary"]
        c.check_allowance(self.usage(payload=c.BYTE_CEILING - reserve, zipped=1), "recover")
        for usage in (self.usage(payload=c.BYTE_CEILING - reserve + 1, zipped=1),
                      self.usage(payload=c.BYTE_CEILING, zipped=0),
                      self.usage(zipped=c.BYTE_CEILING + 1)):
            with self.subTest(usage=usage), self.assertRaises(ValueError):
                c.check_allowance(usage, "recover")
        test_reserve = c.CAPS["permit"] + c.CAPS["tests"]
        c.check_allowance(self.usage(payload=c.BYTE_CEILING - test_reserve), "tests")
        with self.assertRaises(ValueError):
            c.check_allowance(self.usage(payload=c.BYTE_CEILING - test_reserve + 1), "tests")

    def test_both_workflows_all_attempts_and_job_rounding_are_counted(self):
        current_id, old_id = 70000000001, 39551196713
        endpoints = []

        def pages(endpoint, field):
            endpoints.append((endpoint, field))
            if field == "workflow_runs":
                if "knapsack-stagnation-mechanisms.yml" in endpoint:
                    return [{"id": old_id, "run_attempt": 2, "status": "completed"}]
                if "knapsack-stagnation-recovery.yml" in endpoint:
                    return [{"id": current_id, "run_attempt": 1, "status": "in_progress"}]
            if endpoint == f"/actions/runs/{old_id}/attempts/1/jobs":
                return [{"id": 1, "name": "worker (s000)", "status": "completed", "conclusion": "success",
                         "started_at": "2026-10-20T10:00:00Z", "completed_at": "2026-10-20T10:50:01Z"}]
            if endpoint == f"/actions/runs/{old_id}/attempts/2/jobs":
                return [{"id": 2, "name": "gate", "status": "completed", "conclusion": "failure",
                         "started_at": "2026-10-20T11:00:00Z", "completed_at": "2026-10-20T11:00:01Z"}]
            if endpoint == f"/actions/runs/{current_id}/attempts/1/jobs":
                return [{"id": 3, "name": "gate", "status": "in_progress", "conclusion": None,
                         "started_at": "2026-10-21T00:00:00Z", "completed_at": None},
                        {"id": 4, "name": "tests", "status": "queued", "conclusion": None,
                         "started_at": None, "completed_at": None}]
            if endpoint == f"/actions/runs/{old_id}/artifacts":
                return [{"id": 101, "name": c.base.PREFIX + "worker-s000-39551196713-1", "size_in_bytes": 100,
                         "expired": False}]
            if endpoint == f"/actions/runs/{current_id}/artifacts":
                return [{"id": 102, "name": c.PREFIX + "permit-70000000001-1", "size_in_bytes": 80,
                         "expired": False}]
            raise AssertionError(f"Unexpected accounting endpoint: {endpoint}, {field}")

        with patch.dict(os.environ, {"GITHUB_RUN_ID": str(current_id), "GITHUB_RUN_ATTEMPT": "1"}), \
                patch.object(c, "pages", side_effect=pages):
            usage = c.resource_usage()
        self.assertEqual(usage["used_runner_minutes"], 52)
        self.assertTrue(usage["both_workflows_included"])
        self.assertEqual(usage["recovery_workers"], 0)
        self.assertEqual(usage["previous_payload_upper_bound_bytes"], c.CAPS["worker"] + c.CAPS["permit"])
        self.assertEqual(usage["previous_artifact_zip_bytes"], 180)
        self.assertEqual({row["workflow"] for row in usage["jobs"]}, {c.base.WORKFLOW})
        self.assertTrue(any("knapsack-stagnation-recovery.yml" in endpoint for endpoint, _ in endpoints))

    def test_exact_old_and_current_producers_are_admitted_without_relabeling(self):
        for family in c.REUSED_FAMILIES + c.RECOVER_FAMILIES:
            receipt = self.receipt(family)
            with self.subTest(family=family):
                rows = self.validate(receipt, family)
                self.assertEqual(len(rows), 90)
                if family in c.REUSED_FAMILIES:
                    self.assertEqual(receipt["run_id"], 39551196713)
                    self.assertEqual(receipt["implementation_commit_sha"], self.prior["implementation_commit_sha"])
                else:
                    self.assertEqual(receipt["run_id"], self.current["run_id"])

    def test_old_receipt_cannot_be_relabelled_as_current_or_the_reverse(self):
        old = {**self.receipt("s000"), **self.current}
        with self.assertRaises(ValueError):
            self.validate(old, "s000")
        new = {**self.receipt("s004"), **{key: self.prior[key] for key in c.base.PROVENANCE_KEYS}}
        with self.assertRaises(ValueError):
            self.validate(new, "s004")

    def test_every_execution_provenance_field_is_checked(self):
        for family, keys in (("s000", c.base.PROVENANCE_KEYS), ("s004", c.PROVENANCE_KEYS)):
            for key in keys:
                wrong = self.receipt(family)
                wrong[key] = "foreign"
                with self.subTest(family=family, key=key), self.assertRaises(ValueError):
                    self.validate(wrong, family)

    def test_missing_incomplete_duplicate_or_foreign_rows_are_rejected(self):
        for family in ("s000", "s004"):
            for corruption in ("status", "count", "error", "missing", "duplicate", "seed", "instance",
                               "family", "source", "row_source", "row_status", "row_verified"):
                wrong = self.receipt(family)
                if corruption == "status":
                    wrong["status"] = "INCOMPLETE"
                elif corruption == "count":
                    wrong["completed_count"] = 89
                elif corruption == "error":
                    wrong["errors"] = [{"type": "retained_failure"}]
                elif corruption == "missing":
                    wrong["rows"].pop()
                elif corruption == "duplicate":
                    wrong["rows"][1] = deepcopy(wrong["rows"][0])
                elif corruption == "seed":
                    wrong["rows"][0]["repeat_seed"] = 92999
                elif corruption == "instance":
                    wrong["rows"][0]["instance_id"] = "UC-s010"
                elif corruption == "family":
                    wrong["family"] = "s009" if family == "s004" else "s004"
                elif corruption == "source":
                    wrong["source_identity"]["run_id"] = 0
                elif corruption == "row_source":
                    wrong["rows"][0]["source_identity"]["run_id"] = 0
                elif corruption == "row_status":
                    wrong["rows"][0]["status"] = "INCOMPLETE"
                else:
                    wrong["rows"][0]["verified"] = False
                with self.subTest(family=family, corruption=corruption), self.assertRaises(ValueError):
                    self.validate(wrong, family)

    def test_unknown_families_and_foreign_recovery_attempt_are_rejected(self):
        for family in ("s010", "s999", "UC-s004", "", None):
            with self.subTest(family=family), self.assertRaises(ValueError):
                self.validate(self.receipt("s004"), family)
        wrong = self.receipt("s004")
        wrong["run_attempt"] += 1
        with self.assertRaises(ValueError):
            self.validate(wrong, "s004")


if __name__ == "__main__":
    unittest.main()

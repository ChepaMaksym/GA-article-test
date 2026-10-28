"""CI fixtures for conservative all-attempt compressed-journal accounting."""
import copy
import hashlib
import os
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.tournament_feedback import authority as a


class SearchResourceFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Software checks are GitHub-Actions only")

    def test_any_prior_source_allocation_blocks_repeating_its_search_phase(self):
        for phase in ("pilot-donors", "pilot-recipients", "main-donors", "main-recipients"):
            for conclusion in ("success", "failure", "cancelled"):
                usage = {"jobs": [{"phase": phase, "name": phase + " (UC-s000)",
                                   "run_id": 100, "attempt": 1, "conclusion": conclusion}]}
                with self.subTest(phase=phase, conclusion=conclusion), self.assertRaisesRegex(
                        ValueError, "REPEATED_SEARCH_PHASE_RESOURCE_AUDIT_REQUIRED"):
                    a.check_search_phase_once(phase, usage)

    def test_first_allocation_and_gate_only_failure_do_not_repeat_search(self):
        a.check_search_phase_once("pilot-donors", {"jobs": []})
        a.check_search_phase_once("pilot-donors", {"jobs": [{"phase": "pilot-donors", "name": "gate"}]})
        a.check_search_phase_once("pilot-recipients", {"jobs": [{"phase": "pilot-donors", "name": "pilot-donors (UC-s000)"}]})
        a.check_search_phase_once("main-donors", {"jobs": [{"phase": "pilot-donors", "name": "pilot-donors (UC-s000)"}]})

    def test_service_phases_can_repeat_without_new_search_journal_quota(self):
        for phase in ("tests", "prepare-pilot", "prepare-main", "aggregate"):
            a.check_search_phase_once(phase, {"jobs": [{"phase": phase, "name": phase + " (source)"}]})

    def test_disjoint_first_attempt_journal_quotas_never_exceed_six_gib(self):
        ceiling = (4 * a.journal_allowance("pilot-donors") + 4 * a.journal_allowance("pilot-recipients") +
                   10 * a.journal_allowance("main-donors") + 10 * a.journal_allowance("main-recipients"))
        self.assertLessEqual(ceiling, 6 * 2 ** 30)
        for phase in ("pilot-donors", "pilot-recipients", "main-donors", "main-recipients"):
            self.assertLessEqual(a.journal_allowance(phase), 512 * 2 ** 20)

    def test_extended_ceiling_needs_its_own_explicit_numeric_approval(self):
        grant = a.read_json(a.MODULE / "resource_authorization.json")
        changed = copy.deepcopy(grant)
        changed["runner_minutes_ceiling"] = 330
        changed.pop("resource_addendum", None)
        with patch.object(a, "read_json", return_value=changed), self.assertRaisesRegex(ValueError, "SEPARATE_330"):
            a.grant_for("tests")
        changed["resource_addendum"] = {"explicit_user_approval": True, "previous_runner_minutes_ceiling": 300,
             "runner_minutes_ceiling": 330, "compressed_bytes_ceiling": 6 * 2 ** 30,
             "user_reply": "Instructional fixture, not an actual permission record"}
        with patch.object(a, "read_json", return_value=changed):
            self.assertEqual(a.grant_for("tests")["runner_minutes_ceiling"], 330)
        changed["resource_addendum"]["explicit_user_approval"] = False
        with patch.object(a, "read_json", return_value=changed), self.assertRaises(ValueError):
            a.grant_for("tests")

    def test_exact_pilot_runtime_amendment_is_admitted_but_tests_stay_strict(self):
        audit = a.read_json(a.MODULE / "resource_compatibility.json")
        legacy, current = audit["legacy_source_manifest"], a.source_manifest()
        for phase, source_sha in audit["legacy_phase_shas"].items():
            a.compatible_source_manifest(legacy, current, phase, source_sha)
        for phase in ("tests", "prepare-main", "main-donors", "main-recipients", "aggregate"):
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                a.compatible_source_manifest(legacy, current, phase, "0" * 40)
        a.compatible_source_manifest(current, current, "tests", "0" * 40)

    def test_legacy_compatibility_rejects_scientific_runtime_and_inventory_changes(self):
        audit = a.read_json(a.MODULE / "resource_compatibility.json")
        legacy, current = audit["legacy_source_manifest"], a.source_manifest()
        phase, source_sha = "pilot-recipients", audit["legacy_phase_shas"]["pilot-recipients"]
        for relative in ("engine.py", "verifier.py", "analysis.py", "banks.py", "authority.py", "driver.py", "tests/test_resource_guard.py"):
            changed = copy.deepcopy(current)
            next(row for row in changed["files"] if row["path"] == a.REL + relative)["sha256"] = "0" * 64
            changed["sha256"] = hashlib.sha256(a.canonical(changed["files"])).hexdigest()
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                a.compatible_source_manifest(legacy, changed, phase, source_sha)
        changed = copy.deepcopy(current)
        changed["files"].append({"path": a.REL + "unexpected.py", "bytes": 1, "sha256": "0" * 64})
        changed["sha256"] = hashlib.sha256(a.canonical(changed["files"])).hexdigest()
        with self.assertRaises(ValueError):
            a.compatible_source_manifest(legacy, changed, phase, source_sha)
        with self.assertRaises(ValueError):
            a.compatible_source_manifest(legacy, current, phase, "0" * 40)

    def test_compatibility_allowlist_cannot_admit_an_extra_scientific_file(self):
        audit = a.read_json(a.MODULE / "resource_compatibility.json")
        legacy, current = audit["legacy_source_manifest"], a.source_manifest()
        changed = copy.deepcopy(audit)
        changed["file_transitions"][a.REL + "engine.py"] = {"before": {}, "after": {}}
        with patch.object(a, "read_json", return_value=changed), self.assertRaises(ValueError):
            a.compatible_source_manifest(legacy, current, "pilot-recipients", audit["legacy_phase_shas"]["pilot-recipients"])

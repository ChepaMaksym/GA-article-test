"""CI fixtures for conservative all-attempt compressed-journal accounting."""
import os
import unittest

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

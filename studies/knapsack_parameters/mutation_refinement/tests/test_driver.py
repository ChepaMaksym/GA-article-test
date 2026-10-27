"""Instructional accounting fixtures; no search or scoring is performed."""
from copy import deepcopy
import unittest

from ..driver import evaluation_accounting, validate_record_accounting


def replay_receipt():
    """The independent verifier's counter schema for one registered run."""
    return {"verification_status": "VERIFIED", "new_calls": 5000,
            "summary": {"new_calls": 5000, "physical_evaluations": 5000,
                        "known_score_validation_evaluations": 30},
            "independent_score_checks": 10030, "initial_score_checks": 30,
            "final_score_checks": 5000, "premutation_score_checks": 5000}


class DriverAccountingTests(unittest.TestCase):
    def test_search_has_no_premutation_scores_and_replay_subtotals_are_not_extra(self):
        receipt = replay_receipt()
        counts = evaluation_accounting(receipt)
        self.assertEqual(counts["new_search_evaluations"], 5000)
        self.assertEqual(counts["engine_initial_score_validation_evaluations"], 30)
        self.assertEqual(counts["engine_premutation_observational_evaluations"], 0)
        self.assertEqual(counts["independent_replay_score_checks"], 10030)
        self.assertEqual(counts["independent_replay_score_checks"],
                         counts["independent_replay_initial_score_checks"] +
                         counts["independent_replay_final_score_checks"] +
                         counts["independent_replay_premutation_score_checks"])
        validate_record_accounting({"summary": receipt["summary"], **counts})

    def test_corrupted_verifier_split_and_search_counters_are_rejected(self):
        for field, value in (("new_calls", True), ("new_calls", 0),
                             ("initial_score_checks", 0), ("final_score_checks", 4999),
                             ("premutation_score_checks", 0), ("premutation_score_checks", True),
                             ("independent_score_checks", 15030)):
            receipt = replay_receipt()
            receipt[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                evaluation_accounting(receipt)
        receipt = replay_receipt()
        receipt["summary"]["known_score_validation_evaluations"] = 0
        with self.assertRaises(ValueError):
            evaluation_accounting(receipt)

    def test_compact_record_cannot_claim_an_extra_engine_premutation_evaluation(self):
        receipt = replay_receipt()
        record = {"summary": receipt["summary"], **evaluation_accounting(receipt)}
        for field, value in (("engine_premutation_observational_evaluations", 5000),
                             ("engine_initial_score_validation_evaluations", 0),
                             ("independent_replay_premutation_score_checks", 0),
                             ("independent_replay_score_checks", 15030)):
            bad = deepcopy(record)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_record_accounting(bad)
        for field in ("engine_premutation_observational_evaluations",
                      "independent_replay_initial_score_checks",
                      "independent_replay_premutation_score_checks"):
            bad = deepcopy(record)
            del bad[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                validate_record_accounting(bad)

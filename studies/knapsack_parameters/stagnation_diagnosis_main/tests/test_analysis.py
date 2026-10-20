from copy import deepcopy
import unittest

from ...stagnation_diagnosis.tests.test_analysis import make_row as historical_row
from .. import analysis as a
from .. import contract as c


def row(instance="UC-s000", seed=93001, state="N2_NOT_LOCAL", stagnant=True):
    value = historical_row(instance, seed, state, stagnant=stagnant)
    for key in c.PROVENANCE_KEYS:
        value.setdefault(key, "a" * 64)
    value.update(protocol_id=c.PROTOCOL_ID, scientific_protocol_id=c.SCIENTIFIC_ID,
                 technical_fingerprint=c.TECHNICAL_FINGERPRINT, bank_manifest_sha256=c.BANK_SHA,
                 aggregate_independent_verification={"search": {"status": "PASS_REPLAY"},
                                                    "diagnosis": {"status": "PASS_DIAGNOSIS"}})
    return value


class MainAnalysisTests(unittest.TestCase):
    def test_adapter_copies_without_relabeling_saved_evidence(self):
        value = row()
        before = deepcopy(value)
        result = a.summarize_runs([value], expected={("UC-s000", 93001)})
        self.assertEqual(value, before)
        self.assertEqual(result["protocol_id"], c.PROTOCOL_ID)
        self.assertEqual(result["primary"]["value"], 1)
        self.assertEqual([item["q"] for item in result["checkpoint_counts"]], [0, 1000, 2500, 5000])
        self.assertEqual(result["checkpoint_counts"][0]["stagnant_state_counts"], {state: 0 for state in a.STATES})

    def test_unverified_transport_cannot_become_main_observation(self):
        value = row()
        value.pop("aggregate_independent_verification")
        with self.assertRaisesRegex(ValueError, "transported replay"):
            a.summarize_runs([value])

    def test_wrong_bank_probe_or_mixed_main_provenance_rejected(self):
        for key, wrong in (("bank_manifest_sha256", "0" * 64), ("phase", "probe"),
                           ("technical_fingerprint", "0" * 64), ("scientific_protocol_id", "other")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                a.summarize_runs([{**row(), key: wrong}])
        with self.assertRaises(ValueError):
            a.summarize_runs([row(), {**row(seed=93002), "run_id": "other"}])

    def test_missing_and_incomplete_not_counted_as_zero_successes(self):
        value = row()
        value.update(status="INCOMPLETE", verified=False)
        result = a.summarize_runs([value])
        self.assertEqual(result["completeness"]["verified_complete"], 0)
        self.assertEqual(len(result["completeness"]["missing"]), 899)
        self.assertEqual(len(result["completeness"]["incomplete"]), 1)
        self.assertIsNone(result["primary"]["value"])

    def test_ratio_preserves_family_weighting_and_all_zero_categories(self):
        rows = [row(), row(seed=93002, state="N2_STRICT_NONGLOBAL"),
                row("WC-s000", stagnant=False), row("UC-s001")]
        result = a.summarize_runs(rows, expected={(value["instance_id"], value["repeat_seed"]) for value in rows})
        self.assertAlmostEqual(result["primary"]["value"], 5 / 6)
        self.assertEqual(result["state_counts"]["GLOBAL_OPTIMUM"], 0)
        self.assertTrue(result["evaluation_accounting"]["initial_are_known_frozen_evaluations_not_new_search"])

    def test_zero_and_undefined_distinguished(self):
        for value, expected in ((row(stagnant=False), None), (row(state="GLOBAL_OPTIMUM"), 0)):
            result = a.summarize_runs([value], expected={("UC-s000", 93001)})
            self.assertEqual(result["primary"]["value"], expected)

    def test_full_grid_completeness_requires_exactly_900_identities(self):
        rows = [row(case, seed) for case, seed in sorted(a.expected_identities())]
        result = a.summarize_runs(rows)
        self.assertEqual(result["completeness"]["status"], "COMPLETE")
        self.assertEqual(result["evaluation_accounting"]["new_search"], 4500000)
        self.assertEqual(len(result["families"]), 10)
        self.assertEqual(result["inference_status"], "REGISTERED_DESCRIPTIVE_COMPLETE")


if __name__ == "__main__":
    unittest.main()

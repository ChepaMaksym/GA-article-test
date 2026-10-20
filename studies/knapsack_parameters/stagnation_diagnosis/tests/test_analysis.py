"""CI-only tests for the registered descriptive aggregation."""

import copy
import unittest

from studies.knapsack_parameters.stagnation_diagnosis.analysis import (
    PROTOCOL_ID,
    STATES,
    measured_main_quote,
    summarize_runs,
    write_report,
)


def make_row(instance="UC-s000", seed=93001, state="N2_NOT_LOCAL", *, stagnant=True, phase="main"):
    checkpoints = []
    for q in (0, 1000, 2500, 5000):
        last = 4501 if q == 5000 and not stagnant else 0
        checkpoints.append({
            "q": q, "mask": ("1" + "0" * 99) if last else "0" * 100,
            "best_profit": 10 if last else 9, "best_weight": 5,
            "last_improvement_q": last, "stagnation_age": q - last,
            "stagnant": q - last >= 1000, "state": state,
            "certificate_id": "a" * 64, "record_request_ref": 1,
            "population_refs": list(range(30)),
            "pending_refs": list(range(q % 29)),
            "unique_fraction": 1 / 30, "mean_pairwise_hamming": 0.0,
        })
    return {
        "protocol_id": PROTOCOL_ID, "phase": phase,
        "instance_id": instance, "class_label": instance[:2], "family": instance[3:],
        "repeat_seed": seed, "implementation_commit_sha": "a" * 40,
        "protocol_sha256": "b" * 64, "implementation_fingerprint": "c" * 64,
        "bank_manifest_sha256": "d" * 64, "source_sha256": "e" * 64,
        "logical_requests": 5030, "new_evaluations": 5000, "initial_evaluations": 30,
        "verified": True, "status": "COMPLETE", "checkpoints": checkpoints,
        "population_trajectory": [], "accounting": {},
        "timings": {"search_seconds": 1.0, "save_seconds": 2.0, "replay_seconds": 3.0,
                    "diagnosis_seconds": 4.0, "certification_verification_seconds": 5.0,
                    "total_seconds": 15.0},
        "output_bytes": 1024,
        "aggregation_replay_seconds": 5.0,
    }


def identities(rows):
    return {(row["instance_id"], row["repeat_seed"]) for row in rows}


class AnalysisTests(unittest.TestCase):
    def test_ratio_of_weighted_counts_not_mean_conditional_fractions(self):
        rows = [
            make_row(),
            make_row(seed=93002, state="N2_STRICT_NONGLOBAL"),
            make_row("WC-s000", stagnant=False),
            make_row("UC-s001"),
        ]
        result = summarize_runs(rows, expected_identities=identities(rows))
        self.assertAlmostEqual(result["primary"]["value"], 5 / 6)
        self.assertAlmostEqual(result["primary"]["weighted_numerator"], 0.625)
        self.assertAlmostEqual(result["primary"]["weighted_denominator"], 0.75)
        self.assertAlmostEqual(result["primary"]["pooled_fraction"], 2 / 3)
        self.assertEqual(result["primary"]["absolute_numerator"], 2)
        self.assertEqual(result["primary"]["absolute_denominator"], 3)
        self.assertEqual(result["completeness"]["status"], "COMPLETE")

    def test_balanced_family_weighting_matches_pooled_fraction(self):
        rows = [make_row("UC-s000"), make_row("WC-s000", state="N2_STRICT_NONGLOBAL"),
                make_row("UC-s001"), make_row("WC-s001", state="GLOBAL_OPTIMUM")]
        result = summarize_runs(rows, expected_identities=identities(rows))
        self.assertEqual(result["primary"]["value"], 0.5)
        self.assertEqual(result["state_counts"]["N2_NONSTRICT_NONGLOBAL"], 0)
        self.assertEqual(sum(result["state_counts"].values()), 4)

    def test_no_stagnation_is_undefined_not_zero(self):
        row = make_row(stagnant=False)
        result = summarize_runs([row], expected_identities=identities([row]))
        self.assertEqual(result["primary"]["status"], "UNDEFINED")
        self.assertIsNone(result["primary"]["value"])
        self.assertIsNone(result["primary"]["pooled_fraction"])

    def test_zero_numerator_with_stagnation_is_defined(self):
        row = make_row(state="GLOBAL_OPTIMUM")
        result = summarize_runs([row], expected_identities=identities([row]))
        self.assertEqual(result["primary"]["status"], "DEFINED")
        self.assertEqual(result["primary"]["value"], 0)

    def test_all_four_states_accounted_without_zero_filled_runs(self):
        rows = [make_row(seed=93001 + i, state=state) for i, state in enumerate(STATES)]
        result = summarize_runs(rows, expected_identities=identities(rows))
        self.assertEqual(result["stagnant_state_counts"], {state: 1 for state in STATES})
        self.assertEqual(len(result["terminal_observations"]), 4)
        self.assertEqual(result["evaluation_accounting"]["new_search"], 20_000)

    def test_incomplete_rows_and_missing_identities_retained_not_imputed(self):
        good = make_row()
        bad = make_row("WC-s000")
        bad.update(status="REPLAY_FAILED", verified=False, reason="corrupt log", checkpoints=[])
        expected = identities([good, bad]) | {("SC-s000", 93001)}
        result = summarize_runs([good, bad], expected_identities=expected)
        self.assertEqual(result["completeness"]["status"], "INCOMPLETE")
        self.assertEqual(result["completeness"]["verified_complete"], 1)
        self.assertEqual(len(result["completeness"]["incomplete"]), 1)
        self.assertEqual(len(result["completeness"]["missing"]), 1)
        self.assertEqual(result["primary"]["absolute_denominator"], 1)
        self.assertEqual(result["evaluation_accounting"]["new_search"], 5000)
        self.assertEqual(result["inference_status"], "PARTIAL_DESCRIPTIVE_ONLY")

    def test_unverified_complete_row_is_not_an_observation(self):
        row = make_row()
        row["verified"] = False
        result = summarize_runs([row], expected_identities=identities([row]))
        self.assertEqual(result["completeness"]["verified_complete"], 0)
        self.assertIsNone(result["primary"]["value"])

    def test_duplicate_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            summarize_runs([make_row(), make_row()])

    def test_mixed_common_provenance_rejected(self):
        for field, value in (
            ("implementation_commit_sha", "f" * 40),
            ("protocol_sha256", "f" * 64),
            ("implementation_fingerprint", "f" * 64),
            ("bank_manifest_sha256", "f" * 64),
        ):
            with self.subTest(field=field):
                rows = [make_row(), make_row(seed=93002)]
                rows[1][field] = value
                with self.assertRaisesRegex(ValueError, "Mixed"):
                    summarize_runs(rows)

    def test_source_hash_is_per_instance_not_global(self):
        rows = [make_row(), make_row("WC-s000")]
        rows[1]["source_sha256"] = "f" * 64
        summarize_runs(rows, expected_identities=identities(rows))
        rows = [make_row(), make_row(seed=93002)]
        rows[1]["source_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "source"):
            summarize_runs(rows)

    def test_invalid_identity_family_phase_or_seed_rejected(self):
        mutations = [
            {"family": "s001"}, {"class_label": "WC"}, {"repeat_seed": 81001},
            {"instance_id": "UC-s010"}, {"phase": "unknown"},
        ]
        for changes in mutations:
            with self.subTest(changes=changes):
                row = make_row()
                row.update(changes)
                with self.assertRaises(ValueError):
                    summarize_runs([row])

    def test_mixed_probe_and_main_rejected(self):
        with self.assertRaisesRegex(ValueError, "Mixed"):
            summarize_runs([make_row(), make_row("SC-s000", 92999, phase="probe")])

    def test_query_budgets_and_stagnation_flags_validated(self):
        for field, value in (("logical_requests", 5000), ("new_evaluations", 4999), ("initial_evaluations", 0)):
            row = make_row()
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize_runs([row])
        for field, value in (("stagnation_age", -1), ("stagnant", False), ("last_improvement_q", 5001)):
            row = make_row()
            row["checkpoints"][-1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize_runs([row])

    def test_checkpoints_masks_and_diversity_validated(self):
        row = make_row()
        row["checkpoints"].pop(1)
        with self.assertRaises(ValueError):
            summarize_runs([row])
        for field, value in (("mask", "001"), ("state", "PLATEAU"),
                             ("unique_fraction", 1.01), ("mean_pairwise_hamming", float("nan")),
                             ("best_profit", -1), ("certificate_id", "")):
            row = make_row()
            row["checkpoints"][-1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize_runs([row])

    def test_terminal_prefix_and_equal_record_witness_validated(self):
        row = make_row()
        row["checkpoints"][-1]["pending_refs"] = []
        with self.assertRaisesRegex(ValueError, "twelve"):
            summarize_runs([row])
        row = make_row()
        row["checkpoints"][-1]["mask"] = "1" * 100
        with self.assertRaisesRegex(ValueError, "first witness"):
            summarize_runs([row])

    def test_improvement_on_last_query_is_not_stagnation(self):
        row = make_row(stagnant=False)
        row["checkpoints"][-1].update(last_improvement_q=5000, stagnation_age=0)
        result = summarize_runs([row], expected_identities=identities([row]))
        self.assertIsNone(result["primary"]["value"])
        self.assertEqual(result["terminal_observations"][0]["stagnation_age"], 0)

    def test_probe_is_technical_only_and_quote_never_authorizes_main(self):
        rows = [make_row(case, 92999, phase="probe") for case in ("UC-s000", "SC-s005", "SC-s000")]
        result = summarize_runs(rows)
        self.assertEqual(result["completeness"]["status"], "COMPLETE")
        self.assertEqual(result["inference_status"], "TECHNICAL_ONLY")
        self.assertEqual(result["primary"]["interpretation"], "TECHNICAL_ONLY")
        quote = measured_main_quote(rows, result)
        self.assertFalse(quote["authorized"])
        self.assertEqual(quote["estimated_runner_minutes"], 520)
        self.assertEqual(quote["max_measured_aggregation_replay_seconds"], 5.0)
        self.assertEqual(quote["per_run_worker_plus_aggregation_bound_seconds"], 20.0)
        self.assertEqual(quote["estimated_bytes"], 1_152_000)
        partial = summarize_runs(rows[:1])
        self.assertEqual(measured_main_quote(rows[:1], partial)["status"], "UNAVAILABLE")

    def test_quote_requires_independently_measured_aggregation_cost(self):
        rows = [make_row(case, 92999, phase="probe") for case in ("UC-s000", "SC-s005", "SC-s000")]
        result = summarize_runs(rows)
        del rows[-1]["aggregation_replay_seconds"]
        quote = measured_main_quote(rows, result)
        self.assertEqual(quote["status"], "UNAVAILABLE")
        self.assertFalse(quote["authorized"])
        rows[-1]["aggregation_replay_seconds"] = -1
        with self.assertRaises(ValueError):
            measured_main_quote(rows, result)

    def test_report_cannot_write_inside_checkout(self):
        row = make_row()
        result = summarize_runs([row], expected_identities=identities([row]))
        from pathlib import Path
        with self.assertRaisesRegex(ValueError, "outside"):
            write_report(Path(__file__).resolve().parent / "forbidden", [row], result, phase="main")

    def test_expected_identity_set_is_enforced(self):
        row = make_row()
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            summarize_runs([row], expected_identities={("WC-s000", 93001)})


if __name__ == "__main__":
    unittest.main()

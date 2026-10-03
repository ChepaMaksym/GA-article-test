"""CI-only fixtures distinguish local maxima, plateaus and invalid evidence."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from local_optima_study.certification import prepare_case  # noqa: E402


def landscape(mask):
    if not any(mask):
        return (0.0, -1.0)
    if mask == (1, 1, 0, 0):
        quality = 0.8
    elif mask == (0, 1, 1, 0):
        quality = 0.9
    else:
        quality = 0.6
    return (quality, -sum(mask) / len(mask))


class CertificationTests(unittest.TestCase):
    def test_independent_complete_n1_certificate_and_first_n2_witness(self):
        objective = Mock(side_effect=landscape)
        result = prepare_case(objective, (1, 1, 0, 0), (0.8, -0.5))
        self.assertTrue(result["eligible"])
        self.assertEqual(result["status"], "eligible")
        self.assertEqual(result["one_bit_passes"], 1)
        self.assertFalse(result["pass_cap_hit"])
        certificate = result["certificate"]
        self.assertTrue(certificate["complete"])
        self.assertTrue(certificate["lexicographic_local_maximum"])
        self.assertTrue(certificate["wba_local_maximum"])
        self.assertTrue(certificate["strict_wba_local_maximum"])
        self.assertEqual([row["bit"] for row in certificate["neighbors"]], [0, 1, 2, 3])
        self.assertEqual(certificate["audit_calls_after"] - certificate["audit_calls_before"], 5)
        self.assertEqual(result["witness"]["changed_bits"], [0, 2])
        self.assertEqual(result["witness"]["mask"], [0, 1, 1, 0])
        self.assertEqual(result["witness_calls"], 2)
        self.assertEqual(result["diagnostic_calls"], 12)
        self.assertEqual(objective.call_count, result["diagnostic_calls"])
        self.assertEqual([row["call"] for row in result["evaluations"]], list(range(1, 13)))

    def test_smallest_changed_bit_breaks_complete_fitness_ties(self):
        scores = {
            (0, 0, 0, 1): (0.2, -0.25),
            (1, 0, 0, 1): (0.8, -0.5),
            (0, 1, 0, 1): (0.8, -0.5),
        }
        result = prepare_case(lambda mask: scores.get(mask, (0.1, -sum(mask) / 4)), (0, 0, 0, 1), (0.2, -0.25))
        self.assertEqual(result["ascent_trace"][0]["best_neighbor_bit"], 0)
        self.assertEqual(result["center_mask"], [1, 0, 0, 1])
        self.assertEqual(result["one_bit_passes"], 2)

    def test_equal_wba_neighbors_record_plateau_not_strict_quality_maximum(self):
        def objective(mask):
            if mask == (1, 1, 0, 0):
                return (0.8, -0.5)
            if mask == (0, 1, 1, 0):
                return (0.9, -0.5)
            if sum(mask) == 3:
                return (0.8, -0.75)
            return (0.6, -sum(mask) / 4) if any(mask) else (0.0, -1.0)
        result = prepare_case(objective, (1, 1, 0, 0), (0.8, -0.5))
        self.assertTrue(result["eligible"])
        self.assertTrue(result["certificate"]["wba_plateau"])
        self.assertFalse(result["certificate"]["strict_wba_local_maximum"])
        self.assertTrue(result["certificate"]["strict_lexicographic_local_maximum"])
        self.assertEqual(result["certificate"]["equal_wba_neighbors"], [2, 3])

    def test_neutral_complete_fitness_neighbors_do_not_trigger_ascent_walk(self):
        result = prepare_case(lambda _mask: (0.8, 0), (1, 1, 0, 0), (0.8, 0))
        self.assertFalse(result["ascent_trace"][0]["moved"])
        self.assertEqual(result["center_mask"], [1, 1, 0, 0])
        self.assertTrue(result["certificate"]["lexicographic_plateau"])
        self.assertFalse(result["certificate"]["strict_lexicographic_local_maximum"])
        self.assertEqual(result["certificate"]["equal_full_fitness_neighbors"], [0, 1, 2, 3])
        self.assertFalse(result["eligible"])

    def test_equal_quality_fewer_features_is_ascent_improvement(self):
        scores = {(1, 1, 0, 0): (0.8, -0.5), (0, 1, 0, 0): (0.8, -0.25)}
        result = prepare_case(lambda mask: scores.get(mask, (0.5, -sum(mask) / 4)), (1, 1, 0, 0), (0.8, -0.5))
        self.assertTrue(result["ascent_trace"][0]["moved"])
        self.assertEqual(result["ascent_trace"][0]["fitness_after"], [0.8, -0.25])
        self.assertEqual(result["center_mask"], [0, 1, 0, 0])

    def test_pass_cap_hit_may_qualify_only_after_independent_audit(self):
        scores = {
            (1, 1, 0, 0): (0.7, -0.5),
            (1, 1, 1, 0): (0.8, -0.75),
            (0, 1, 1, 1): (0.9, -0.75),
        }
        result = prepare_case(lambda mask: scores.get(mask, (0.5, -sum(mask) / 4)), (1, 1, 0, 0), (0.7, -0.5), max_passes=1)
        self.assertTrue(result["pass_cap_hit"])
        self.assertEqual(result["center_mask"], [1, 1, 1, 0])
        self.assertTrue(result["certificate"]["complete"])
        self.assertTrue(result["eligible"])
        self.assertEqual(result["witness"]["changed_bits"], [0, 3])

    def test_pass_cap_with_still_better_n1_neighbor_is_valid_ineligible(self):
        def quality(mask):
            return (sum(mask) / 4, -sum(mask) / 4) if any(mask) else (0, -1)
        result = prepare_case(quality, (0, 0, 0, 1), (0.25, -0.25), max_passes=1)
        self.assertTrue(result["pass_cap_hit"])
        self.assertFalse(result["eligible"])
        self.assertFalse(result["certificate"]["lexicographic_local_maximum"])
        self.assertFalse(result["certificate"]["wba_local_maximum"])
        self.assertEqual(result["status"], "ineligible_final_one_bit_not_local")
        self.assertEqual(result["witness_calls"], 0)
        self.assertEqual(result["diagnostic_calls"], 10)

    def test_no_two_bit_witness_does_not_claim_global_optimality(self):
        result = prepare_case(lambda mask: (sum(mask) / 4, -sum(mask) / 4), (1, 1, 1, 1), (1, -1))
        self.assertTrue(result["certificate"]["strict_wba_local_maximum"])
        self.assertFalse(result["eligible"])
        self.assertEqual(result["status"], "ineligible_no_two_bit_witness")
        self.assertEqual(result["witness_calls"], 6)
        self.assertIsNone(result["witness"])
        self.assertNotIn("global_optimum", result)

    def test_real_dimension_diagnostic_limit_is_1622_and_pairs_complete(self):
        n = 40
        result = prepare_case(lambda mask: (sum(mask) / n, -sum(mask) / n), (1,) * n, (1, -1))
        self.assertEqual(result["diagnostic_call_upper_bound"], 1622)
        self.assertEqual(result["witness_calls"], 780)
        self.assertEqual(result["diagnostic_calls"], 862)
        self.assertLessEqual(result["diagnostic_calls"], 1622)
        pairs = [row["changed_bits"] for row in result["evaluations"] if row["phase"] == "two_bit_witness"]
        self.assertEqual(pairs[0], [0, 1])
        self.assertEqual(pairs[-1], [38, 39])

    def test_empty_neighbor_special_score_and_call_are_retained(self):
        def objective(mask):
            return (0.8, -0.25) if mask == (0, 0, 0, 1) else (0.6, -sum(mask) / 4) if any(mask) else (0.0, -1.0)
        result = prepare_case(objective, (0, 0, 0, 1), (0.8, -0.25))
        empty = result["certificate"]["neighbors"][3]
        self.assertEqual(empty["mask"], [0, 0, 0, 0])
        self.assertEqual(empty["fitness"], [0.0, -1.0])
        self.assertEqual(len(result["evaluations"]), result["diagnostic_calls"])

    def test_source_score_mismatch_is_invalid_not_a_scientific_ineligible_case(self):
        objective = Mock(return_value=(0.7, -0.5))
        with self.assertRaisesRegex(ValueError, "did not reproduce"):
            prepare_case(objective, (1, 1, 0, 0), (0.8, -0.5))
        self.assertEqual(objective.call_count, 1)

    def test_independent_center_recheck_detects_nondeterminism(self):
        source = (1, 1, 0, 0)
        source_calls = 0
        def objective(mask):
            nonlocal source_calls
            if mask == source:
                source_calls += 1
                return (0.8 if source_calls == 1 else 0.81, -0.5)
            return landscape(mask)
        with self.assertRaisesRegex(ValueError, "did not reproduce"):
            prepare_case(objective, source, (0.8, -0.5))
        self.assertEqual(source_calls, 2)

    def test_independent_neighbor_recheck_detects_nondeterminism(self):
        target = (0, 1, 0, 0)
        target_calls = 0
        def objective(mask):
            nonlocal target_calls
            score = landscape(mask)
            if mask == target:
                target_calls += 1
                if target_calls > 1:
                    return (score[0] + 0.01, score[1])
            return score
        with self.assertRaisesRegex(ValueError, "did not reproduce"):
            prepare_case(objective, (1, 1, 0, 0), (0.8, -0.5))

    def test_interrupted_audit_cannot_return_a_partial_certificate(self):
        objective = Mock(side_effect=[(0.8, -0.5)] + [(0.6, -0.25)] * 4 + [RuntimeError("interrupted")])
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            prepare_case(objective, (1, 1, 0, 0), (0.8, -0.5))

    def test_invalid_static_inputs_fail_before_objective_invocation(self):
        for changes in (
            {"start_mask": (1, 0.5)}, {"start_mask": (True, 0)},
            {"expected_fitness": (0.8, float("nan"))}, {"expected_fitness": True},
            {"max_passes": 0}, {"max_passes": True}, {"max_passes": 21},
        ):
            with self.subTest(changes=changes):
                objective = Mock(return_value=(0.8, -0.5))
                args = {"start_mask": (1, 1, 0, 0), "expected_fitness": (0.8, -0.5)}
                args.update(changes)
                with self.assertRaises((TypeError, ValueError)):
                    prepare_case(objective, **args)
                objective.assert_not_called()

    def test_nonfinite_objective_fails_not_an_ineligible_result(self):
        with self.assertRaises(ValueError):
            prepare_case(lambda _mask: (float("inf"), 0), (1, 1, 0, 0), (0.8, -0.5))


if __name__ == "__main__":
    unittest.main()

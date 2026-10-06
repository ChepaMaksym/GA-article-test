"""Synthetic checks for the registered series; executed by CI, not locally."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lambda_initial_study.aggregate import (  # noqa: E402
    AUC_KEY, ALL_ARMS, analyse, make_plots, paired_bca, validate_lambda_journal,
)
from lambda_initial_study.contract import CASE_SEEDS  # noqa: E402
from lambda_initial_study.select_artifacts import select_artifacts  # noqa: E402
from local_optima_study.aggregate import validate_search_trace  # noqa: E402
from local_optima_study.search import run_lambda_search  # noqa: E402


def metadata(seed, identity, attempt=1):
    return {"id": identity, "name": f"eu26-21-lambda-case-{seed}-123-{attempt}",
            "expired": False, "size_in_bytes": 50, "digest": "sha256:" + "d" * 64,
            "workflow_run": {"id": 123, "head_sha": "a" * 40}}


def synthetic_cases():
    cases = []
    for i, seed in enumerate(CASE_SEEDS):
        arms, traces = {}, {}
        for j, arm in enumerate(ALL_ARMS):
            arms[arm] = {AUC_KEY: .70 + j * .001 + i * .00001,
                         "test_metrics": {"weighted": {"balanced_accuracy": .69 + j * .0002}}}
            traces[arm] = {"evaluations": [{"best_so_far_weighted_balanced_accuracy": .68 + j * .001 + k * .00001}
                                          for k in range(400)]}
        cases.append({"row": {"seed": seed, "arms": arms}, "traces": traces})
    return cases


class SelectionTests(unittest.TestCase):
    def test_all_30_and_latest_attempt_without_outcome(self):
        raw = {"artifacts": [metadata(seed, i + 1) for i, seed in enumerate(CASE_SEEDS)]}
        raw["artifacts"].append(metadata(43001, 100, 2))
        result = select_artifacts(raw, run_id=123, expected_sha="a" * 40)
        self.assertEqual(result["artifacts"][0]["id"], 100)
        self.assertEqual(len(result["attempts"]), 31)
        self.assertFalse(result["scientific_artifacts_opened"])

    def test_missing_duplicate_expired_wrong_sha_wrong_namespace(self):
        original = {"artifacts": [metadata(seed, i + 1) for i, seed in enumerate(CASE_SEEDS)]}
        invalid = []
        missing = deepcopy(original)
        missing["artifacts"].pop()
        invalid.append(missing)
        duplicate = deepcopy(original)
        duplicate["artifacts"].append(deepcopy(duplicate["artifacts"][0]))
        invalid.append(duplicate)
        for key, value in (("expired", True), ("digest", "bad"), ("name", "unscoped"), ("size_in_bytes", 0)):
            row = deepcopy(original)
            row["artifacts"][0][key] = value
            invalid.append(row)
        wrong = deepcopy(original)
        wrong["artifacts"][0]["workflow_run"]["head_sha"] = "b" * 40
        invalid.append(wrong)
        for row in invalid:
            with self.subTest(row=row["artifacts"][0]["name"]), self.assertRaises(ValueError):
                select_artifacts(row, run_id=123, expected_sha="a" * 40)


class AnalysisTests(unittest.TestCase):
    def test_bca_is_deterministic_and_mean_paired(self):
        values = [.001, -.002, .003, .007, -.001] * 6
        first = paired_bca(values, confidence=.9875, rng_seed=43031)
        second = paired_bca(values, confidence=.9875, rng_seed=43031)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first["estimate"], sum(values) / 30)
        self.assertEqual(first["bootstrap_resamples"], 50000)
        self.assertLess(first["interval"][0], first["interval"][1])

    def test_constant_no_fallback_or_quality_claim(self):
        fitted = paired_bca([.01] * 30, confidence=.995, rng_seed=43031)
        self.assertIsNone(fitted["interval"])
        self.assertEqual(fitted["unavailable_reason"], "constant_paired_differences")

    def test_prespecified_contrasts_and_joint_gate(self):
        calls = []
        def inference(differences, *, confidence, rng_seed):
            calls.append((confidence, rng_seed, len(differences)))
            # NI passes for only lambda1, AUC passes for all; no quality claim for other arms.
            index = len(calls) - 1
            interval = [-.002, .002] if 5 <= index <= 8 else [.0001, .003]
            return {"estimate": sum(differences) / len(differences), "interval": interval,
                    "confidence_level": confidence, "bootstrap_resamples": 50000,
                    "analysis_seed": rng_seed, "unit": "whole_seed_case", "case_count": 30,
                    "unavailable_reason": None}
        with patch("lambda_initial_study.aggregate.paired_bca", side_effect=inference):
            result = analyse(synthetic_cases())
        self.assertEqual(calls, [(.9875 if i < 4 else .995, 43031 + i, 30) for i in range(14)])
        self.assertEqual(len(result["primary_contrasts"]), 4)
        self.assertEqual(len(result["secondary_contrasts"]), 10)
        self.assertTrue(result["joint_search_advantage"]["lambda_initial_1"])
        self.assertFalse(any(result["joint_search_advantage"][f"lambda_initial_{n}"] for n in (5, 10, 20, 40)))

    def test_no_seed_exclusion_or_pooled_models(self):
        with self.assertRaises(ValueError):
            analyse(synthetic_cases()[:-1])

    def test_six_curve_and_contrast_plot_generated_in_ci(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            analysis = {"primary_contrasts": [{"arm": f"lambda_initial_{n}", "estimate": .002,
                        "interval": [-.001, .003]} for n in (5, 10, 20, 40)]}
            make_plots(synthetic_cases(), analysis, root)
            for name in ("initial-lambda-trajectories.png", "initial-lambda-primary-intervals.png"):
                self.assertTrue((root / name).read_bytes().startswith(b"\x89PNG"))


class JournalTests(unittest.TestCase):
    def test_all_initial_values_and_lambda40_duplicates(self):
        def objective(mask):
            return .5 + sum(mask) / 100, -sum(mask) / 40
        initial = [tuple([1] * 4 + [0] * 36)] * 50
        for value in (1, 5, 10, 20, 40):
            result = run_lambda_search(objective, seed=43001, initial_masks=initial,
                                       lambda_initial=value, mode="adaptive", budget=400)
            result["arm"] = f"lambda_initial_{value}"
            validate_search_trace(result)
            validate_lambda_journal(result, value)
            broken = deepcopy(result)
            broken["generation_trace"][0]["lambda_before"] = 2
            with self.assertRaises(ValueError):
                validate_lambda_journal(broken, value)
            if value == 40:
                mutants = result["evaluations"][50:90]
                self.assertEqual(len({json.dumps(r["mask"]) for r in mutants}), 1)
                self.assertEqual(result["generation_trace"][0]["mutation_strength"], 40)


if __name__ == "__main__":
    unittest.main()

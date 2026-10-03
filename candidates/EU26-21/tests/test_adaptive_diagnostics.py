"""Synthetic CI-only checks: no optimizer, classifier or real dataset execution."""
from __future__ import annotations

import copy
import csv
import math
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_bridge.aggregate import canonical_sha256  # noqa: E402
from evidence_audit import adaptive_diagnostics as report  # noqa: E402
import test_thesis_tables as fixtures  # noqa: E402


def records_with(changes=None):
    """Literal objective observations, not outputs of a search algorithm."""
    changes = changes or {}
    best = None
    rows = []
    for call in range(1, 401):
        score, count = changes.get(call, (0.7, 1))
        fitness = (score, -count / 40)
        update = best is None or fitness > best
        best = fitness if update else best
        rows.append({"call": call, "mask": [1] * count + [0] * (40 - count),
                     "selected_feature_count": count,
                     "validation_weighted_balanced_accuracy": score,
                     "negative_selected_feature_fraction": -count / 40,
                     "terminal_best_update": update,
                     "best_so_far_weighted_balanced_accuracy": best[0]})
    return rows


def constant_trace(arm, seed=41001):
    """Handcrafted constant-observation transcript for the two state contracts."""
    records = records_with()
    mask, fitness = records[0]["mask"], [0.7, -0.025]
    generations = []
    calls, lam, distance = 50, 1.0, 10
    while calls < 400:
        row = {"generation": len(generations) + 1, "calls_before": calls}
        if arm == "lambda_no_reset":
            planned = math.floor(lam + 0.5)
            count = min(planned, (400 - calls) // 2)
            after = min(40.0, lam * 1.5**0.25)
            row.update(lambda_before=lam, lambda_after=after,
                       planned_offspring_count_per_phase=planned,
                       evaluated_offspring_count_per_phase=count,
                       mutation_probability=lam / 40, crossover_probability=1 / lam,
                       mutation_strength=0, parent_before=mask, parent_fitness_before=fitness,
                       selected_mutant_index=0, candidate_mask=mask, candidate_fitness=fitness,
                       parent_after=mask, strict_success=False, accepted=True,
                       tail_truncated=count < planned)
            calls += 2 * count
            lam = after
        else:
            catastrophe = distance == 0
            row.update(distance_before=distance,
                       phase="cataclysmic_mutation" if catastrophe else "hux",
                       generated_fresh_offspring=50 if catastrophe else 0,
                       evaluated_fresh_offspring=50 if catastrophe else 0,
                       partial_population_update_skipped=False)
            distance = 10 if catastrophe else distance - 1
            row["distance_after"] = distance
            calls += 50 if catastrophe else 0
        row["calls_after"] = calls
        generations.append(row)
    state = {"generation_count": len(generations)}
    if arm == "lambda_no_reset":
        state.update(final_lambda=lam, parent_mask_sha256=canonical_sha256(mask),
                     parent_fitness=fitness, tail_truncated=generations[-1]["tail_truncated"])
    else:
        state.update(final_distance=distance, partial_population_update_skipped=False)
    return {"arm": arm, "seed": seed, "evaluations": records, "generation_trace": generations,
            "terminal_state": state, "reset": False, "reset_events": 0,
            "initial_population_calls": 50, "objective_calls": 400}


class EvaluationAgesTests(unittest.TestCase):
    def test_boundary_and_right_censored_terminal_interval(self):
        rows = report.evaluation_ages(records_with())
        self.assertEqual(len(rows), 351)
        self.assertEqual(rows[0]["call"], 50)
        self.assertTrue(rows[0]["boundary_only"])
        self.assertFalse(rows[0]["lexicographic_record_update"])
        self.assertEqual(rows[0]["lexicographic_record_age"], 0)
        self.assertEqual(rows[1]["lexicographic_record_age"], 1)
        self.assertEqual(rows[-1]["lexicographic_record_age"], 350)
        self.assertEqual(rows[-1]["quality_record_age"], 350)

    def test_feature_reduction_resets_only_lexicographic_age(self):
        changes = {call: (0.7, 4) for call in range(1, 401)}
        changes[53] = (0.7, 3)
        changes[54] = (0.7, 3)  # Exact tie must not reset either age.
        changes[56] = (0.8, 40)  # Higher quality wins despite more features.
        rows = {row["call"]: row for row in report.evaluation_ages(records_with(changes))}
        self.assertEqual(rows[53]["lexicographic_record_age"], 0)
        self.assertEqual(rows[53]["quality_record_age"], 3)
        self.assertTrue(rows[53]["lexicographic_record_update"])
        self.assertFalse(rows[53]["quality_record_update"])
        self.assertEqual(rows[54]["lexicographic_record_age"], 1)
        self.assertEqual(rows[55]["lexicographic_record_age"], 2)
        self.assertEqual(rows[56]["quality_record_age"], 0)
        self.assertEqual(rows[56]["lexicographic_record_age"], 0)
        self.assertEqual(rows[56]["best_selected_feature_count"], 40)

    def test_record_before_boundary_is_retained_and_empty_masks_are_valid(self):
        rows = report.evaluation_ages(records_with({49: (0.9, 0), 51: (0.8, 1)}))
        self.assertEqual(rows[0]["best_validation_wba"], 0.9)
        self.assertEqual(rows[0]["best_selected_feature_count"], 0)
        self.assertEqual(rows[1]["lexicographic_record_age"], 1)

    def test_tampered_record_flags_and_secondary_objective_rejected(self):
        for field, value in (("terminal_best_update", True),
                             ("negative_selected_feature_fraction", -0.5),
                             ("selected_feature_count", True),
                             ("best_so_far_weighted_balanced_accuracy", 0.8),
                             ("call", 400)):
            records = records_with()
            records[60][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                report.evaluation_ages(records)


class TraceDiagnosticsTests(unittest.TestCase):
    def test_handcrafted_transcripts_pass_independent_transition_validation(self):
        for arm in report.tables.ARMS:
            with self.subTest(arm=arm):
                trace = constant_trace(arm)
                before = copy.deepcopy(trace)
                calls, generations, summary = report.describe_trace(trace)
                self.assertEqual(trace, before)
                self.assertEqual(len(calls), 351)
                self.assertEqual(generations[-1]["calls_after"], 400)
                self.assertEqual(summary["maximum_lexicographic_record_age"], 350)
                self.assertEqual(summary["terminal_quality_record_age"], 350)
                self.assertEqual(summary["lexicographic_record_updates"], 0)
                self.assertTrue(summary["terminal_intervals_right_censored"])
                if arm == "lambda_no_reset":
                    self.assertEqual(summary["successful_generations"], 0)
                    self.assertEqual(summary["accepted_neutral_generations"], len(generations))
                    self.assertGreater(summary["lambda_final"], summary["lambda_maximum_used"])
                    self.assertTrue(summary["terminal_lambda_unused"])

    def test_transition_and_reset_corruption_fail_closed(self):
        for mutation in ("lambda", "success", "reset", "missing_generation"):
            trace = constant_trace("lambda_no_reset")
            if mutation == "lambda":
                trace["generation_trace"][0]["lambda_after"] = 40.0
            elif mutation == "success":
                trace["generation_trace"][0]["strict_success"] = True
            elif mutation == "reset":
                trace["reset_events"] = 1
            else:
                trace["generation_trace"].pop()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                report.describe_trace(trace)

    def test_authentication_failure_prevents_diagnostics(self):
        with mock.patch.object(report.tables, "load_pairs", side_effect=ValueError("byte/hash mismatch")), \
                mock.patch.object(report, "describe_trace") as describe:
            with self.assertRaisesRegex(ValueError, "byte/hash"):
                report.load_diagnostics(Path("rows"), Path("expected"), Path("verified"))
            describe.assert_not_called()


class FullReportTests(unittest.TestCase):
    def setUp(self):
        # Reuse the authenticated 30-pair fixture, upgrading only its trace content.
        self.fixture = fixtures.ThesisTablesTests("test_missing_and_duplicate_seeds_rejected")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        for entry in self.fixture.verification["artifacts"]:
            seed = entry["seed"]
            paths = {Path(item["path"]).name: self.fixture.rows / item["path"]
                     for item in entry["extracted_files"]}
            row_path = paths[f"seed-{seed}.json"]
            row = report.tables.source._load_json(row_path)
            for arm, suffix in zip(report.tables.ARMS, ("chc", "lambda")):
                path = paths[f"seed-{seed}-{suffix}-trace.json"]
                trace = report.tables.source._load_json(path)
                trace.update(constant_trace(arm, seed))
                self.fixture.write(path, trace)
                row["arms"][arm]["trace_sha256"] = report.tables.source._file_sha256(path)
            self.fixture.write(row_path, row)
            for item in entry["extracted_files"]:
                path = self.fixture.rows / item["path"]
                item.update(bytes=path.stat().st_size, sha256=report.tables.source._file_sha256(path))
        self.fixture.write(self.fixture.verified, self.fixture.verification)

    def test_all_pairs_outputs_sources_and_decisions_preserved(self):
        with mock.patch("joblib.load", side_effect=AssertionError("no deserialization")), \
                mock.patch("common_bridge.aggregate.analyze_rows", side_effect=AssertionError("no inference")), \
                mock.patch("common_bridge.aggregate._paired_median_bca", side_effect=AssertionError("no bootstrap")):
            calls, generations, summaries, provenance = report.load_diagnostics(
                self.fixture.rows, self.fixture.expected, self.fixture.verified)
            output = self.fixture.root / "diagnostics"
            report.write_report(calls, generations, summaries, provenance, output)
        self.assertEqual(len(summaries), 60)
        self.assertEqual(len(calls), 21060)
        self.assertEqual([item["seed"] for item in summaries[::2]],
                         list(report.tables.source.EXPECTED_SEEDS))
        with (output / "per-call-diagnostics.csv").open(encoding="utf-8", newline="") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 21060)
        manifest = report.tables.source._load_json(output / "diagnostics-manifest.json")
        self.assertEqual(manifest["plan_sha256"], report.tables.source._file_sha256(report.PLAN))
        self.assertEqual(manifest["source"]["source_run_id"], report.tables.RUN_ID)
        self.assertFalse(manifest["scientific_decisions_changed"])
        self.assertFalse(manifest["scientific_decisions_recomputed"])
        self.assertFalse(manifest["training_performed"])
        self.assertIn("FAIL_NONINFERIORITY", manifest["interpretation"])
        self.assertEqual(manifest["preserved_analysis"], report.tables.preserved_analysis(
            ROOT / "common_bridge" / "evidence"))
        summary = report.tables.source._load_json(output / "summary.json")
        self.assertEqual(summary["group_summaries"]["chc_harmonized"]["count"], 30)
        self.assertEqual(summary["group_summaries"]["lambda_no_reset"]["runs_using_lambda_upper_bound"], 0)
        self.assertEqual(summary["group_summaries"]["chc_harmonized"]["descriptive_statistics"]
                         ["maximum_lexicographic_record_age"],
                         {"minimum": 350, "median": 350, "maximum": 350})
        self.assertEqual(set(manifest["outputs"]), {
            "per-call-diagnostics.csv", "generation-diagnostics.csv", "summary.json",
            "lambda-response-41001.png", "stagnation-all-seeds.png", "report.md"})
        for name, entry in manifest["outputs"].items():
            self.assertEqual(report.tables.source._file_sha256(output / name), entry["sha256"])
        with self.assertRaises(FileExistsError):
            report.write_report(calls, generations, summaries, provenance, output)

    def test_missing_or_duplicate_pair_cannot_be_written(self):
        calls, generations, summaries, provenance = report.load_diagnostics(
            self.fixture.rows, self.fixture.expected, self.fixture.verified)
        for changed in (summaries[:-1], summaries[:-1] + summaries[:1]):
            output = self.fixture.root / "invalid"
            with self.assertRaisesRegex(ValueError, "30 ordered pairs"):
                report.write_report(calls, generations, changed, provenance, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()

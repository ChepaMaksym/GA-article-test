"""CI-only synthetic checks; fixtures are not retained study observations.

Importing these tests performs no numerical work. The manual workflow admits a
fresh first-analysis grant before executing this module. No GA is imported.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import gzip
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from . import admission, analysis


class CIOnlyChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Synthetic checks are permitted only in the authorized GitHub CI stage")


class AttainmentChecks(CIOnlyChecks):
    def test_initial_population_hits_keep_their_individual_evaluation(self):
        for population in (10, 15, 20, 25):
            for q in range(1, population + 1):
                events = [[1, 930]] if q == 1 else [[1, 0], [q, 930]]
                with self.subTest(population=population, q=q):
                    hit = analysis.first_attainment(events, 1000, 93)
                    self.assertEqual(hit, {"attained": True, "first_total_evaluation": q,
                                           "restricted_evaluations": q})

    def test_equality_is_a_hit_and_integer_comparison_preserves_large_values(self):
        optimum = 100 * (10 ** 18 + 7)
        below = 93 * (10 ** 18 + 7) - 1
        exact = below + 1
        hit = analysis.first_attainment([[1, 0], [17, below], [18, exact]], optimum, 93)
        self.assertTrue(hit["attained"])
        self.assertEqual(hit["first_total_evaluation"], 18)

    def test_last_evaluation_hit_and_nonattainment_have_different_indicators(self):
        hit = analysis.first_attainment([[1, 0], [100000, 950]], 1000, 95)
        missed = analysis.first_attainment([[1, 0], [100000, 949]], 1000, 95)
        self.assertEqual(hit["restricted_evaluations"], missed["restricted_evaluations"])
        self.assertTrue(hit["attained"])
        self.assertEqual(hit["first_total_evaluation"], 100000)
        self.assertFalse(missed["attained"])
        self.assertIsNone(missed["first_total_evaluation"])

    def test_higher_thresholds_cannot_be_hit_earlier(self):
        events = [[1, 0], [4, 900], [11, 930], [29, 950], [100000, 990]]
        self.assertEqual([analysis.first_attainment(events, 1000, target)["first_total_evaluation"]
                          for target in (90, 93, 95, 99)], [4, 11, 29, 100000])

    def test_event_history_rejects_invalid_order_types_and_impossible_profit(self):
        invalid = (
            [], [[2, 0]], [[0, 0]], [[1, 0], [1, 100]],
            [[1, 0], [3, 100], [2, 200]], [[1, 0], [2, 100], [3, 99]],
            [[1, 0], [2, 100], [3, 100]], [[1, -1]], [[1, 1001]],
            [[1, 0], [100001, 100]], [[True, 0]], [[1, False]],
            [[1.0, 0]], [[1, 0], [2, 10.5]], [[1, 0, 5]],
        )
        for events in invalid:
            with self.subTest(events=events), self.assertRaises(ValueError):
                analysis.validate_events(events, 1000)

    def test_terminal_record_must_match_the_last_improvement(self):
        self.assertEqual(analysis.validate_events([[1, 0], [7, 930]], 1000, best=930),
                         ((1, 0), (7, 930)))
        with self.assertRaises(ValueError):
            analysis.validate_events([[1, 0], [7, 930]], 1000, best=929)


def synthetic_row(config=(10, 90, 100), family="s050", kind="UC", seed=150001):
    """One invented trace; no retained scientific outcomes enter the tests."""
    mu, pc, bp = config
    task = f"n00100-{kind}-{family}"
    return {
        "mu": mu, "pc_percentage": pc, "mutation_basis_points": bp,
        "task": task, "task_index": 3 + (int(family[1:]) - 50) * 3 + analysis.TYPES.index(kind),
        "family": family, "class_label": kind, "seed": seed,
        "optimum": 1000, "best": 930, "events": [[1, 0], [7, 930]],
        "targets": {
            "93": {"attained": True, "first_total_evaluation": 7, "restricted_evaluations": 7},
            "95": {"attained": False, "first_total_evaluation": None, "restricted_evaluations": 100000},
            "99": {"attained": False, "first_total_evaluation": None, "restricted_evaluations": 100000},
        },
        "checkpoints": [{"q": q, "record_profit": 930,
                         "completed_generations": (q - mu) // (mu - 1),
                         "population_metrics": {"population_size": mu}} for q in analysis.CHECKPOINTS],
        "completed_generations": (100000 - mu) // (mu - 1), "duplicates": 0,
        "bank_sha256": "1" * 64, "certificate_sha256": "2" * 64,
        "artifact_hashes": {name: "3" * 64 for name in analysis.RAW_FILES},
        "artifact_prefix": f"{task}/seed-{seed}/synthetic", "timing": {"search_seconds": 0},
    }


class SourceIntegrityChecks(CIOnlyChecks):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document = {
            "schema": "mutation-grid-100-validated-union-v1", "status": "VERIFIED_2790",
            "provenance": {"status": "ALL_CASES_INDEPENDENTLY_VERIFIED",
                           "retained_cases": 1440, "new_cases": 1350},
            "runs": [synthetic_row(config, family, kind, seed)
                     for config in analysis.CONFIGS for family in analysis.FAMILIES
                     for kind in analysis.TYPES for seed in analysis.SEEDS],
        }

    def document_with_changed_first_row(self, change):
        document = {**self.document, "runs": list(self.document["runs"])}
        document["runs"][0] = deepcopy(document["runs"][0])
        change(document["runs"][0])
        return document

    def test_full_frozen_rectangle_is_admitted_without_synthesizing_missing_cases(self):
        rows = analysis.validate_source(self.document)
        self.assertEqual(len(rows), 2790)
        self.assertEqual(len({analysis.identity(row) for row in rows}), 2790)
        self.assertEqual(len(analysis.CONFIGS), 31)
        for config in analysis.SELECTED_CONFIGS:
            self.assertEqual(sum(analysis.configuration(row) == config for row in rows), 90)
        missing = {**self.document, "runs": self.document["runs"][:-1]}
        with self.assertRaises(ValueError):
            analysis.validate_source(missing)

    def test_duplicate_identity_cannot_replace_a_missing_paired_case(self):
        duplicate = {**self.document, "runs": list(self.document["runs"])}
        duplicate["runs"][-1] = duplicate["runs"][0]
        with self.assertRaises(ValueError):
            analysis.validate_source(duplicate)

    def test_stored_endpoint_and_checkpoint_must_be_recomputed_from_events(self):
        for change in (
            lambda row: row["targets"]["93"].update(first_total_evaluation=8, restricted_evaluations=8),
            lambda row: row["targets"]["95"].update(attained=True, first_total_evaluation=100000),
            lambda row: row["checkpoints"][0].update(record_profit=929),
            lambda row: row.update(best=931),
            lambda row: row.update(events=[[1, 930]]),
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                analysis.validate_source(self.document_with_changed_first_row(change))

    def test_pairing_requires_the_same_initial_bank_and_exact_reference(self):
        for field, value in (("bank_sha256", "f" * 64), ("certificate_sha256", "e" * 64),
                             ("optimum", 999)):
            changed = self.document_with_changed_first_row(lambda row: row.update({field: value}))
            with self.subTest(field=field), self.assertRaises(ValueError):
                analysis.validate_source(changed)

    def test_compressed_evidence_is_authenticated_before_parsing(self):
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "synthetic.json.gz"
            payload = gzip.compress(json.dumps({"synthetic": True}).encode("utf-8"), mtime=0)
            source.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            self.assertEqual(analysis.read_source(source, digest), {"synthetic": True})
            source.write_bytes(payload + b"corruption")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                analysis.read_source(source, digest)


class AggregationChecks(CIOnlyChecks):
    @staticmethod
    def metric_row(family, task, seed, value, attained):
        return {"mu": 10, "pc_percentage": 90, "mutation_basis_points": 100,
                "family": family, "task": task, "seed": seed,
                **{metric: Fraction(value) for metric in analysis.METRICS},
                "search_seconds": Fraction(value, 10),
                **{f"attained_{target}": attained for target in (93, 95, 99, 100)}}

    def test_repetitions_then_tasks_then_families_receive_equal_weights(self):
        # Unequal synthetic cell sizes expose accidental pooling. Task means are
        # 2 and 6 in family A, and 10 in family B; the expected grand mean is 7.
        rows = [self.metric_row("A", "A1", 1, 1, True),
                self.metric_row("A", "A1", 2, 3, False),
                self.metric_row("A", "A2", 1, 6, False),
                self.metric_row("B", "B1", 1, 10, True)]
        result = analysis.aggregate(rows)[0]
        self.assertEqual(result["mean_gap_100000_percent"], Fraction(7))
        self.assertEqual(result["worst_family_gap_100000_percent"], Fraction(10))
        self.assertEqual(result["mean_search_seconds"], Fraction(7, 10))
        self.assertEqual(result["attainment_93"], Fraction(5, 8))
        self.assertEqual(result["nonattainment_93"], Fraction(3, 8))
        self.assertEqual(result["not_attained_93"], 2)

    def test_duplicate_metric_identity_is_rejected(self):
        row = self.metric_row("A", "A1", 1, 1, True)
        with self.assertRaises(ValueError):
            analysis.aggregate([row, deepcopy(row)])

    def test_paired_signs_and_leave_one_family_out_use_b_minus_a(self):
        rows = []
        for index, config in enumerate(analysis.SELECTED_CONFIGS):
            for family_index, family in enumerate(analysis.FAMILIES):
                for kind in analysis.TYPES:
                    for seed in analysis.SEEDS:
                        task = f"n00100-{kind}-{family}"
                        row = self.metric_row(family, task, seed, index * (family_index + 1), True)
                        row.update(dict(zip(("mu", "pc_percentage", "mutation_basis_points"), config)))
                        row["class_label"] = kind
                        rows.append(row)
        paired, family_rows, summaries, loo = analysis._pair_analysis(rows)
        self.assertEqual(len(paired), 540)
        self.assertEqual(len(family_rows), 60)
        self.assertEqual(len(summaries), 6)
        self.assertEqual(len(loo), 60)
        primary = next(row for row in summaries if row["primary_diagnostic"])
        self.assertEqual(primary["mean_delta_gap_100000_percent"], Fraction(11, 2))
        self.assertEqual(primary["a_earlier_or_smaller_gap_100000_percent"], 90)
        self.assertEqual(primary["b_earlier_or_smaller_gap_100000_percent"], 0)
        omitted = next(row for row in loo if row["primary_diagnostic"] and row["omitted_family"] == "s059")
        self.assertEqual(omitted["mean_delta_gap_100000_percent"], Fraction(5))
        self.assertEqual(omitted["direction_gap_100000_percent"], "A")


class AdmissionChecks(CIOnlyChecks):
    @staticmethod
    def authorization():
        return {
            "schema": "iterative-validation-resource-authorization-v1",
            "status": "AUTHORIZED", "phase": "first_analysis",
            "repository": admission.REPOSITORY, "ref": admission.REF,
            "runner_minutes": 20, "artifact_bytes": 524288000,
            "source_sha256": admission.SOURCE_SHA256,
            "protocol_sha256": "a" * 64, "source_manifest_sha256": "b" * 64,
            "authorization_id": "synthetic-first-analysis-001",
            "fresh_approval": True, "new_search_evaluations": 0,
            "additional_dispatches_authorized": False,
        }

    def test_preparation_and_search_phases_do_not_admit_execution(self):
        valid = self.authorization()
        self.assertEqual(admission.validate_authorization(valid, valid["authorization_id"]), valid)
        for field, value in (("status", "PREPARED_NOT_AUTHORIZED"), ("fresh_approval", False),
                             ("phase", "main_search"), ("new_search_evaluations", 1),
                             ("runner_minutes", 700), ("artifact_bytes", 12 * 1024 ** 3),
                             ("source_sha256", "f" * 64), ("additional_dispatches_authorized", True)):
            changed = deepcopy(valid)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                admission.validate_authorization(changed, valid["authorization_id"])

    def test_grant_identity_and_numeric_boolean_types_are_not_interchangeable(self):
        valid = self.authorization()
        with self.assertRaises(ValueError):
            admission.validate_authorization(valid, "different-manual-dispatch-grant")
        for field, value in (("fresh_approval", 1), ("new_search_evaluations", False),
                             ("additional_dispatches_authorized", 0)):
            changed = deepcopy(valid)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                admission.validate_authorization(changed, valid["authorization_id"])

    def test_manual_registered_ci_identity_is_required(self):
        environment = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": admission.REPOSITORY,
                       "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": admission.REF,
                       "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123"}
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(admission.ci_identity()["workflow_run_id"], "123")
            for field, value in (("GITHUB_ACTIONS", "false"), ("GITHUB_EVENT_NAME", "push"),
                                 ("GITHUB_REPOSITORY", "another/repository"),
                                 ("GITHUB_REF", "refs/heads/main"), ("GITHUB_RUN_ATTEMPT", "2")):
                with self.subTest(field=field), patch.dict(os.environ, {field: value}), self.assertRaises(ValueError):
                    admission.ci_identity()

    def test_artifact_limit_counts_all_files_and_blocks_oversize_upload(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            (stage / "nested").mkdir(parents=True)
            (stage / "one.txt").write_bytes(b"1234")
            (stage / "nested/two.txt").write_bytes(b"56789")
            with patch.object(admission, "ci_identity", return_value={}), patch.object(admission, "ROOT", root):
                with patch.object(admission, "ARTIFACT_BYTES", 9):
                    self.assertEqual(admission.validate_artifacts(stage)["artifact_bytes"], 9)
                with patch.object(admission, "ARTIFACT_BYTES", 8), self.assertRaises(ValueError):
                    admission.validate_artifacts(stage)


if __name__ == "__main__":
    unittest.main()

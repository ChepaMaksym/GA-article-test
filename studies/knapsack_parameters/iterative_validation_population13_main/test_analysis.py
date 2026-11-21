"""Synthetic main-analysis checks admitted only by the real CI grant.

Fixtures are invented numerical examples. They are neither retained observations
nor extra full-budget GA executions. No test or research executes on import.
"""
from __future__ import annotations

from copy import deepcopy
import csv
from fractions import Fraction
import gzip
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from . import analysis


class CIOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        analysis.guard_main()


def fixture(best=990):
    case = deepcopy(analysis.registered_cases()[0])
    mu, total, new = 13, 100000, 99987
    events = [{"q": 1, "profit": 0, "mask": "0" * 100, "phase": "initializing"},
              {"q": 13, "profit": 930, "mask": "1" + "0" * 99, "phase": "initializing"},
              {"q": 6000, "profit": 950, "mask": "11" + "0" * 98, "phase": "search"},
              {"q": total, "profit": best, "mask": "111" + "0" * 97, "phase": "search"}]
    targets = {"93": {"attained": True, "first_total_evaluation": 13, "restricted_evaluations": 13},
               "95": {"attained": True, "first_total_evaluation": 6000, "restricted_evaluations": 6000},
               "99": {"attained": best >= 990, "first_total_evaluation": total if best >= 990 else None,
                      "restricted_evaluations": total}}
    points = []
    for q in analysis.CHECKPOINTS:
        profit = 930 if q < 6000 else 950 if q < total else best
        complete, partial = divmod(q - mu, mu - 1)
        points.append({"q": q, "record_profit": profit, "gap_percent": (1000 - profit) / 10,
                       "phase": "search", "initial_evaluations": mu, "offspring_evaluations": q - mu,
                       "completed_generations": complete, "partial_offspring_count": partial,
                       "population_total_q": mu + complete * (mu - 1),
                       "parameters": dict(analysis.FIXED_PARAMETERS),
                       "population_metrics": {"population_size": 13, "unique_count": 13, "unique_fraction": 1,
                                              "feasible_count": 13, "feasible_fraction": 1,
                                              "unordered_pairs": 78, "pairwise_hamming_sum": 780,
                                              "mean_pairwise_hamming": 10}})
    observed = {"schema": "population-crossover-observations-v1", "total_evaluations": total,
                "initial_evaluations": mu, "new_evaluations": new, "search_evaluations_performed": 0,
                "optimum": 1000, "final_best_profit": best, "final_gap_percent": (1000 - best) / 10,
                "record_events": events, "targets": targets, "checkpoints": points,
                "completed_generations": 8332, "terminal_partial_offspring": 3}
    record = {"schema": "population13-main-case-v1", "status": "VERIFIED", **case,
              "tournament_size": 2, "elite_count": 1, "initial_evaluations": mu,
              "new_evaluations": new, "total_evaluations": total, "completed_generations": 8332,
              "terminal_partial_children": 3, "search_seconds": 1.25,
              "bank_sha256": "1" * 64, "certificate_sha256": "2" * 64, "problem_sha256": "3" * 64,
              "source_manifest_sha256": "4" * 64,
              "workflow_run_id": "100", "workflow_commit": "a" * 40,
              "artifact_hashes": {name: "5" * 64 for name in analysis.PAYLOADS}}
    verified = {"verification_status": "VERIFIED", "new_calls": new, "initial_score_checks": mu,
                "final_score_checks": new, "premutation_score_checks": new,
                "independent_score_checks": 199987, "completed_generations": 8332,
                "partial_generations": 1, "record_profit": best,
                "duplicate_candidates": 17, "final_parameters": dict(analysis.FIXED_PARAMETERS),
                "summary": {"partial_children": 3}}
    bins = [{"distance": d, "total": new if d == 0 else 0, "crossed": 0,
             "novel_crossed": 0, "feasible_crossed": 0, "better_both_crossed": 0} for d in range(101)]
    operators = {"operator_bins": bins, "premutation_score_checks": new}
    return case, record, observed, verified, operators


def compact(values):
    return analysis.new_compact(*values, "6" * 64)


def metrics_rectangle():
    times = {(10, 90, 100): 750, (13, 90, 100): 600, (15, 90, 100): 650,
             (15, 100, 100): 900, (20, 90, 100): 800}
    bests = {(10, 90, 100): 970, (13, 90, 100): 980, (15, 90, 100): 975,
             (15, 100, 100): 990, (20, 90, 100): 965}
    rows = []
    for family in analysis.FAMILIES:
        for kind in analysis.TYPES:
            for seed in analysis.SEEDS:
                for config in analysis.DISPLAY_CONFIGURATIONS:
                    mu, pc, bp = config
                    row = {"mu": mu, "pc_percentage": pc, "mutation_basis_points": bp,
                           "task": f"n00100-{kind}-{family}", "family": family,
                           "class_label": kind, "seed": seed, "optimum": 1000, "best": bests[config],
                           "timing": {"search_seconds": 1},
                           "events": [[1, 0], [times[config], 930], [100000, bests[config]]]}
                    rows.append(analysis.historical._run_metrics(row))
    return rows


class ReceiptChecks(CIOnly):
    def test_initial_and_last_attainments_are_kept_on_total_scale(self):
        row = compact(fixture())
        metrics = analysis.historical._run_metrics(row)
        self.assertEqual(metrics["first_t93"], 13)
        self.assertEqual(metrics["first_t95"], 6000)
        self.assertEqual(metrics["first_t99"], 100000)
        self.assertEqual(row["initial_evaluations"] + row["new_evaluations"], 100000)
        self.assertEqual(row["duplicates"], 17)

    def test_nonattainment_and_last_hit_have_equal_restriction_but_distinct_flags(self):
        hit = compact(fixture(990))["targets"]["99"]
        miss = compact(fixture(989))["targets"]["99"]
        self.assertEqual(hit["restricted_evaluations"], miss["restricted_evaluations"])
        self.assertTrue(hit["attained"])
        self.assertFalse(miss["attained"])
        self.assertIsNone(miss["first_total_evaluation"])

    def test_integer_threshold_equality_and_q_zero_rejection(self):
        scale = 10 ** 18 + 7
        events = [[1, 0], [13, 93 * scale - 1], [14, 93 * scale]]
        value = analysis.historical.first_attainment(events, 100 * scale, 93)
        self.assertEqual(value["first_total_evaluation"], 14)
        for events in ([[0, 0], [2, 930]], [[True, 0], [2, 930]], [[1, 0], [2, 930], [2, 950]]):
            with self.subTest(events=events), self.assertRaises(ValueError):
                analysis.historical.first_attainment(events, 1000, 93)

    def test_checkpoint_partial_block_and_fixed_parameters_are_checked(self):
        for change in ("partial", "committed", "parameters", "phase"):
            values = fixture()
            point = values[2]["checkpoints"][-1]
            if change == "partial": point["partial_offspring_count"] = 0
            elif change == "committed": point["population_total_q"] = 100000
            elif change == "parameters": point["parameters"]["p_m"] = .02
            else: point["phase"] = "initializing"
            with self.subTest(change=change), self.assertRaises(ValueError):
                compact(values)

    def test_corrupt_events_target_types_and_replay_checks_are_rejected(self):
        for change in ("mask", "record", "target_bool", "restricted_bool", "replay", "new_calls"):
            values = fixture()
            if change == "mask": values[2]["record_events"][1]["mask"] = "x" * 100
            elif change == "record": values[2]["final_best_profit"] = 989
            elif change == "target_bool": values[2]["targets"]["93"]["attained"] = 1
            elif change == "restricted_bool": values[2]["targets"]["93"]["restricted_evaluations"] = True
            elif change == "replay": values[3]["independent_score_checks"] -= 1
            else: values[1]["new_evaluations"] += 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                compact(values)

    def test_operator_bin_coverage_subsets_and_distance_duplicates_are_rejected(self):
        for change in ("total", "subset", "distance", "checks"):
            values = fixture()
            if change == "total": values[4]["operator_bins"][0]["total"] -= 1
            elif change == "subset": values[4]["operator_bins"][0]["novel_crossed"] = 1
            elif change == "distance": values[4]["operator_bins"][1]["distance"] = 0
            else: values[4]["premutation_score_checks"] -= 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                compact(values)

    def test_historical_allowlist_is_not_expanded_by_new_configuration(self):
        self.assertNotIn(analysis.NEW_CONFIGURATION, analysis.historical.CONFIGS)
        row = compact(fixture())
        with self.assertRaises(ValueError):
            analysis.historical._validate_row(row)
        self.assertEqual(len(analysis.historical.CONFIGS), 31)


class AggregateChecks(CIOnly):
    def test_hierarchical_average_gives_equal_weight_to_families(self):
        rows = [{"family": "a", "task": "one", "value": 0}]
        rows += [{"family": "b", "task": "two", "value": 10} for _ in range(9)]
        value, families = analysis.historical._hierarchical(rows, "value")
        self.assertEqual(value, Fraction(5))
        self.assertEqual(families, {"a": Fraction(0), "b": Fraction(10)})

    def test_paired_effects_and_lofo_keep_control_minus_candidate_direction(self):
        paired, families, omitted, summaries = analysis.paired_diagnostics(metrics_rectangle())
        self.assertEqual((len(paired), len(families), len(omitted), len(summaries)), (360, 40, 40, 4))
        control10 = next(row for row in summaries if row["control_configuration"] == "mu10-pc90-pm100bp")
        self.assertEqual(control10["mean_delta_gap_100000_percent"], Fraction(1))
        self.assertEqual(control10["mean_delta_restricted_t93"], Fraction(150))
        self.assertEqual(control10["candidate_smaller_restricted_t93"], 90)
        self.assertTrue(all(row["remaining_pairs"] == 81 for row in omitted))

    def test_pair_rectangle_rejects_missing_and_duplicate_controls(self):
        values = metrics_rectangle()
        missing = next(index for index, row in enumerate(values) if analysis._configuration(row) == (10, 90, 100))
        with self.assertRaises(ValueError):
            analysis.paired_diagnostics(values[:missing] + values[missing + 1:])
        with self.assertRaises(ValueError):
            analysis.paired_diagnostics([*values, deepcopy(values[0])])

    def test_curves_retain_failed_runs_and_are_monotone_at_last_request(self):
        values = metrics_rectangle()
        rows = analysis.attainment_curves(values, 99)
        for config in analysis.DISPLAY_CONFIGURATIONS:
            curve = [row for row in rows if analysis._configuration(row) == config]
            self.assertEqual(curve[0]["q"], 0)
            self.assertEqual(curve[-1]["q"], 100000)
            self.assertTrue(all(row["denominator"] == 90 for row in curve))
            self.assertTrue(all(a["attainment_percent"] <= b["attainment_percent"] for a, b in zip(curve, curve[1:])))
            self.assertEqual(curve[-1]["attained"], 90 if config == (15, 100, 100) else 0)
        with self.assertRaises(ValueError):
            analysis.attainment_curves(values + [deepcopy(values[0])], 93)

    def test_attainment_nesting_is_preserved_at_common_query_points(self):
        metrics = metrics_rectangle()
        curves = {target: analysis.attainment_curves(metrics, target) for target in (93, 95, 99)}
        for config in analysis.DISPLAY_CONFIGURATIONS:
            for q in (0, 600, 750, 2500, 100000):
                successes = []
                for target in (93, 95, 99):
                    rows = [row for row in curves[target] if analysis._configuration(row) == config and row["q"] <= q]
                    successes.append(rows[-1]["attained"])
                self.assertGreaterEqual(successes[0], successes[1])
                self.assertGreaterEqual(successes[1], successes[2])

    def test_rational_exports_and_compressed_union_preserve_exact_values(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            analysis._write_json(root / "summary.json", {"metric": Fraction(1, 3)})
            result = json.loads((root / "summary.json").read_bytes())
            self.assertEqual(result["metric"]["numerator"], 1)
            self.assertEqual(result["metric"]["denominator"], 3)
            analysis._write_csv(root / "table.csv", [{"metric": Fraction(1, 3), "attained": True}])
            with (root / "table.csv").open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream, delimiter=";"))
            self.assertEqual((row["metric_numerator"], row["metric_denominator"], row["attained"]), ("1", "3", "true"))
            analysis._write_json_gz(root / "union.json.gz", {"metric": Fraction(2, 7)})
            with gzip.open(root / "union.json.gz", "rt", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream)["metric"]["denominator"], 7)


class FilesystemChecks(CIOnly):
    def test_missing_ninetieth_record_stops_before_reading_case_payloads(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            inputs, results = root / "inputs", root / "results"
            inputs.mkdir(); results.mkdir()
            cases = analysis.registered_cases()
            dummy = b"{}"
            input_files = []
            for name in ("problem", "certificate", "source", "bank"):
                path = inputs / (name + ".json")
                path.write_bytes(dummy)
                input_files.append({"path": path.name, "bytes": len(dummy), "sha256": analysis.sha(path)})
            descriptions = dict(zip(("problem", "certificate", "source", "bank"), input_files))
            manifest = {"schema": "population13-main-inputs-v1", "status": "NINETY_PAIRED_CASES_READY",
                        "new_bank_count": 0, "retained_bank_count": 90, "ga_runs": 0, "exact_solver_calls": 0,
                        "source_manifest_sha256": "8" * 64, "files": input_files,
                        "cases": [{**case, **deepcopy(descriptions)} for case in cases]}
            (inputs / "manifest.json").write_bytes(json.dumps(manifest).encode("utf-8"))
            for case in cases[:-1]:
                target = results / case["case_id"] / "record.json"
                target.parent.mkdir()
                target.write_bytes(b"{}")
            with patch.object(analysis, "new_compact") as conversion:
                with self.assertRaises(ValueError):
                    analysis.load_new_runs(results, inputs, {"source_manifest_sha256": "8" * 64})
                conversion.assert_not_called()

    def test_case_payload_hash_substitution_is_rejected_before_observation_use(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); inputs, results = root / "inputs", root / "results"
            inputs.mkdir(); results.mkdir(); cases = analysis.registered_cases()
            descriptions, files = {}, []
            for name in ("problem", "certificate", "source", "bank"):
                path = inputs / (name + ".json"); path.write_bytes(b"{}")
                item = {"path": path.name, "bytes": 2, "sha256": analysis.sha(path)}
                descriptions[name] = item; files.append(item)
            manifest = {"schema": "population13-main-inputs-v1", "status": "NINETY_PAIRED_CASES_READY",
                        "new_bank_count": 0, "retained_bank_count": 90, "ga_runs": 0, "exact_solver_calls": 0,
                        "source_manifest_sha256": "8" * 64, "files": files,
                        "cases": [{**case, **deepcopy(descriptions)} for case in cases]}
            path = inputs / "manifest.json"; path.write_bytes(json.dumps(manifest).encode("utf-8")); input_sha = analysis.sha(path)
            for case in cases:
                directory_case = results / case["case_id"]; directory_case.mkdir()
                hashes = {}
                for name in analysis.PAYLOADS:
                    payload = directory_case / name; payload.write_bytes(b"{}")
                    hashes[name] = analysis.sha(payload)
                # This deliberately corrupts every journal, so ordering cannot
                # accidentally reach a synthetic observation instead of the gate.
                (directory_case / "journal.json.gz").write_bytes(b"altered")
                record = {**case, "workflow_run_id": os.environ["GITHUB_RUN_ID"],
                          "source_manifest_sha256": "8" * 64, "inputs_manifest_sha256": input_sha,
                          "artifact_hashes": hashes,
                          **{key + "_sha256": descriptions[key]["sha256"] for key in ("bank", "certificate", "problem", "source")}}
                (directory_case / "record.json").write_bytes(json.dumps(record).encode("utf-8"))
            with patch.object(analysis, "validate_case_origin", return_value={}), patch.object(analysis, "new_compact") as conversion:
                with self.assertRaises(ValueError):
                    analysis.load_new_runs(results, inputs, {"source_manifest_sha256": "8" * 64})
                conversion.assert_not_called()

    def test_analysis_admission_precedes_source_or_results_access(self):
        with patch.object(analysis, "guard_main", side_effect=ValueError("not admitted")):
            with patch.object(analysis.historical, "read_source") as source:
                with self.assertRaises(ValueError):
                    analysis.analyze("absent", "absent-output", "unapproved", "absent-inputs")
                source.assert_not_called()

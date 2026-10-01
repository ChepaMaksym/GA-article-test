"""CI-only synthetic pipeline fixtures; no Census training or local execution."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import statistics
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from corrected_applied.data_protocol import TRANSFORMED_FEATURE_NAMES  # noqa: E402
from local_optima_study import aggregate, contract, run_case  # noqa: E402


def literal_trace(arm="lambda_adaptive", *, escape=False, exit_call=None):
    mask = [1] + [0] * 39
    fitness = [0.7, -0.025]
    initial = {"call": 0, "mask": mask, "fitness": fitness,
               "validation_weighted_balanced_accuracy": 0.7,
               "negative_selected_feature_fraction": -0.025, "selected_feature_count": 1}
    records = []
    for call in range(1, 401):
        new = exit_call is not None and call >= exit_call
        queried_mask = ([0, 1] + [0] * 38) if new else mask
        score = [0.8 if new else 0.7, -0.025]
        records.append({"call": call, "mask": queried_mask, "fitness": score,
                        "best_so_far_weighted_balanced_accuracy": score[0],
                        "terminal_best_update": call == exit_call if escape else call == 1 or call == exit_call})
    best_call = exit_call if exit_call else (0 if escape else 1)
    terminal = {**initial, "call": best_call,
                "mask": ([0, 1] + [0] * 38) if exit_call else mask,
                "fitness": [0.8 if exit_call else 0.7, -0.025],
                "validation_weighted_balanced_accuracy": 0.8 if exit_call else 0.7}
    return {"arm": arm, "objective_calls": 400, "initial_population_calls": 0 if escape else 50,
            "reset": False, "reset_events": 0, "initial": initial if escape else None,
            "terminal": terminal, "evaluations": records,
            "generation_trace": [] if not escape or exit_call is None else [{"calls_after": exit_call,
                "accepted": True, "eligible_count": 1, "parent_fitness_after": [0.8, -0.025]}],
            "terminal_state": {"final_lambda": 1}, "termination_phase": "complete_lambda_generation",
            "normalized_auc_best_so_far_validation_wba_1_400": statistics.fmean(row["fitness"][0] for row in records),
            "normalized_auc_best_so_far_validation_wba_51_400": None if escape else statistics.fmean(row["fitness"][0] for row in records[50:]),
            "escape": None if not escape else {"first_exit_call": exit_call, "first_accepted_exit_call": exit_call,
                         "censored": exit_call is None, "restricted_calls": 400 if exit_call is None else exit_call}}


def literal_preparation():
    center = [1] + [0] * 39
    fitness = [0.7, -0.025]
    records = []
    def append(mask, score, phase, one_bit_pass=None):
        records.append({"call": len(records) + 1, "mask": mask, "fitness": score,
                        "phase": phase, "changed_bits": [], "one_bit_pass": one_bit_pass})
    def neighbor(bit):
        mask = center.copy()
        mask[bit] = 1 - mask[bit]
        return mask, [0.6, -sum(mask) / 40] if sum(mask) else [0.0, -1.0]
    append(center, fitness, "source_center_recheck")
    for bit in range(40):
        append(*neighbor(bit), "ascent_one_bit", 1)
    append(center, fitness, "audit_center_recheck")
    neighbors = []
    for bit in range(40):
        mask, score = neighbor(bit)
        append(mask, score, "audit_one_bit")
        neighbors.append({"bit": bit, "mask": mask, "fitness": score, "call": len(records)})
    witness_mask = [0, 1] + [0] * 38
    witness_fitness = [0.8, -0.025]
    append(witness_mask, witness_fitness, "two_bit_witness")
    return {"schema": "eu26-21-local-optima-preparation-v1", "dimension": 40,
            "source_mask": center, "source_fitness": fitness, "center_mask": center, "center_fitness": fitness,
            "one_bit_passes": 1, "pass_cap_hit": False, "diagnostic_calls": 83,
            "eligible": True, "status": "eligible", "witness_calls": 1,
            "ascent_trace": [{"pass": 1, "calls_before": 1, "calls_after": 41,
                "center_before": center, "fitness_before": fitness, "best_neighbor_bit": 1,
                "best_neighbor_mask": neighbor(1)[0], "best_neighbor_fitness": neighbor(1)[1], "moved": False,
                "center_after": center, "fitness_after": fitness}],
            "certificate": {"complete": True, "center_recheck_fitness": fitness, "neighbors": neighbors,
                            "audit_calls_before": 41, "audit_calls_after": 82,
                            "lexicographic_local_maximum": True, "wba_local_maximum": True,
                            "strict_wba_local_maximum": True, "strict_lexicographic_local_maximum": True,
                            "equal_wba_neighbors": [], "equal_full_fitness_neighbors": [],
                            "wba_plateau": False, "lexicographic_plateau": False},
            "witness": {"mask": witness_mask, "fitness": witness_fitness, "changed_bits": [0, 1], "call": 83},
            "evaluations": records}


def escape_case(seed, outcomes):
    rows = []
    for repeat, (adaptive, fixed) in enumerate(outcomes, 1):
        rows.append({"seed": seed, "repeat": repeat, "arms": {
            arm: {"escape": {"first_exit_call": call, "restricted_calls": 400 if call is None else call}}
            for arm, call in (("lambda_adaptive", adaptive), ("lambda_fixed1", fixed))}})
    return rows


class MetricContractTests(unittest.TestCase):
    def test_both_class_denominators(self):
        metrics = contract.per_class_metrics([[80, 20], [30, 70]])
        self.assertAlmostEqual(metrics["0"]["precision"], 80 / 110)
        self.assertEqual(metrics["0"]["recall"], 0.8)
        self.assertAlmostEqual(metrics["1"]["precision"], 70 / 90)
        self.assertEqual(metrics["1"]["recall"], 0.7)
        self.assertEqual(metrics["0"]["support"], 100)

    def test_weight_sums_are_not_cast_to_record_counts(self):
        metrics = contract.per_class_metrics([[1.5, 0.25], [0.75, 2.5]])
        self.assertEqual(metrics["0"]["support"], 1.75)
        self.assertEqual(metrics["1"]["support"], 3.25)

    def test_zero_denominator_returns_zero(self):
        self.assertEqual(contract.per_class_metrics([[0, 0], [0, 0]])["1"]["f1"], 0)

    def test_invalid_matrix_rejected(self):
        for value in ([[1, 2]], [[1, -1], [0, 2]], [[1, float("nan")], [0, 2]]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                contract.per_class_metrics(value)

    def test_top_level_selection_metadata_retained(self):
        block = {"confusion_matrix": [[8, 2], [3, 7]]}
        result = contract.add_class_metrics({"selected_feature_count": 4,
                                             "weighted": block, "unweighted": block})
        self.assertEqual(result["selected_feature_count"], 4)
        self.assertIn("classes", result["weighted"])

    def test_empty_mask_special_fitness(self):
        contract.mask_fitness([0] * 40, [0, -1])
        with self.assertRaises(ValueError):
            contract.mask_fitness([0] * 40, [0, 0])

    def test_mask_coercions_rejected(self):
        for bit in (True, "1", 1.0):
            with self.subTest(bit=bit), self.assertRaises(ValueError):
                contract.mask_fitness([bit] + [0] * 39, [0.7, -0.025])

    def test_duplicate_json_fields_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "duplicate.json"
            path.write_text('{"seed":1,"seed":2}', encoding="utf-8")
            with self.assertRaises(ValueError):
                contract.read_json(path)

    def test_unregistered_protocol_rejected(self):
        with self.assertRaises(ValueError):
            contract.validate_protocol(ROOT / "local_optima_study/protocol.json", "0" * 64)


class TraceContractTests(unittest.TestCase):
    def test_comparison_400_complete(self):
        aggregate.validate_search_trace(literal_trace())

    def test_known_q0_is_best_on_nonexit(self):
        trace = literal_trace(escape=True)
        aggregate.validate_search_trace(trace, escape=True)
        self.assertEqual(trace["terminal"]["call"], 0)

    def test_q0_dropped_rejected(self):
        trace = literal_trace(escape=True)
        trace["terminal"]["call"] = 1
        with self.assertRaises(ValueError):
            aggregate.validate_search_trace(trace, escape=True)

    def test_duplicate_indices_rejected(self):
        trace = literal_trace()
        trace["evaluations"][1]["call"] = 1
        with self.assertRaises(ValueError):
            aggregate.validate_search_trace(trace)

    def test_queried_exit_and_censoring(self):
        aggregate.validate_search_trace(literal_trace(escape=True, exit_call=17), escape=True)
        trace = literal_trace(escape=True, exit_call=17)
        trace["escape"]["censored"] = True
        with self.assertRaises(ValueError):
            aggregate.validate_search_trace(trace, escape=True)

    def test_nonexit_not_removed_from_time_measure(self):
        trace = literal_trace(escape=True)
        trace["escape"]["restricted_calls"] = 0
        with self.assertRaises(ValueError):
            aggregate.validate_search_trace(trace, escape=True)

    def test_fixed_parameter_cannot_change(self):
        trace = literal_trace("lambda_fixed1")
        trace["terminal_state"]["final_lambda"] = 2
        with self.assertRaises(ValueError):
            aggregate.validate_search_trace(trace)


class CertificationContractTests(unittest.TestCase):
    def test_full_n1_and_n2_witness(self):
        aggregate.validate_preparation(literal_preparation())

    def test_missing_neighbor_rejected(self):
        prep = literal_preparation()
        prep["certificate"]["neighbors"].pop()
        with self.assertRaises(ValueError):
            aggregate.validate_preparation(prep)

    def test_false_eligibility_not_accepted(self):
        prep = literal_preparation()
        prep["eligible"] = False
        with self.assertRaises(ValueError):
            aggregate.validate_preparation(prep)

    def test_one_bit_witness_rejected(self):
        prep = literal_preparation()
        prep["witness"]["changed_bits"] = [1]
        with self.assertRaises(ValueError):
            aggregate.validate_preparation(prep)


class ClusterAnalysisTests(unittest.TestCase):
    def test_no_cases_is_scientific_status_not_exception(self):
        result = aggregate.case_cluster_analysis([])
        self.assertEqual(result["status"], "NO_CERTIFIED_CASES")
        self.assertFalse(result["advantage"])

    def test_one_case_descriptive_only(self):
        result = aggregate.case_cluster_analysis(escape_case(42001, [(20, None)] * 5))
        self.assertEqual(result["estimate"], 1)
        self.assertIsNone(result["interval"])
        self.assertEqual(result["unavailable_reason"], "fewer_than_two_eligible_cases")

    def test_constant_differences_no_false_certainty(self):
        result = aggregate.case_cluster_analysis(escape_case(42001, [(20, None)] * 5)
                                                + escape_case(42002, [(30, None)] * 5))
        self.assertEqual(result["unavailable_reason"], "constant_case_differences")
        self.assertFalse(result["advantage"])

    def test_missing_repeat_rejected(self):
        with self.assertRaises(ValueError):
            aggregate.case_cluster_analysis(escape_case(42001, [(20, None)] * 4))

    def test_bca_resamples_case_differences_not_150_pairs(self):
        rows = (escape_case(42001, [(20, None)] * 5)
                + escape_case(42002, [(20, 30)] * 5))
        fitted = SimpleNamespace(confidence_interval=SimpleNamespace(low=0.1, high=0.9),
                                  bootstrap_distribution=[0.2, 0.4, 0.8])
        with mock.patch.object(aggregate, "bootstrap", return_value=fitted) as call:
            result = aggregate.case_cluster_analysis(rows)
        self.assertEqual(call.call_args.args[0][0].tolist(), [1, 0])
        self.assertEqual(call.call_args.kwargs["n_resamples"], 50000)
        self.assertTrue(result["advantage"])
        self.assertEqual(result["cases"][0]["fixed1_restricted_mean_calls"], 400)

    def test_nonfinite_bca_no_fallback(self):
        rows = escape_case(42001, [(20, None)] * 5) + escape_case(42002, [(20, 30)] * 5)
        fitted = SimpleNamespace(confidence_interval=SimpleNamespace(low=float("nan"), high=1),
                                  bootstrap_distribution=[0.2, 0.4])
        with mock.patch.object(aggregate, "bootstrap", return_value=fitted):
            result = aggregate.case_cluster_analysis(rows)
        self.assertIsNone(result["interval"])
        self.assertFalse(result["advantage"])

    def test_actual_registered_bca_is_deterministic_in_ci(self):
        rows = (escape_case(42001, [(20, None)] * 5)
                + escape_case(42002, [(20, 30)] * 5)
                + escape_case(42003, [(None, 30)] * 5))
        first = aggregate.case_cluster_analysis(rows)
        second = aggregate.case_cluster_analysis(rows)
        self.assertEqual(first, second)
        self.assertEqual(first["estimate"], 0)
        self.assertIsNotNone(first["interval"])
        self.assertFalse(first["advantage"])


class ArtifactLedgerTests(unittest.TestCase):
    def test_wrong_source_run_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ledger.json"
            contract.write_json(path, {"artifacts": [{"id": 1, "name": "eu26-21-local-case-42001",
                "workflow_run": {"id": 2, "head_sha": "a" * 40}}]})
            with self.assertRaises(ValueError):
                aggregate._artifact_ledger(path, prefix="eu26-21-local-case-", expected_sha="a" * 40, source_run_id=3)

    def test_duplicate_artifact_id_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ledger.json"
            items = [{"id": 1, "name": f"eu26-21-local-case-{seed}",
                      "workflow_run": {"id": 2, "head_sha": "a" * 40}} for seed in (42001, 42002)]
            contract.write_json(path, {"artifacts": items})
            with self.assertRaises(ValueError):
                aggregate._artifact_ledger(path, prefix="eu26-21-local-case-", expected_sha="a" * 40, source_run_id=2)

    def test_incomplete_registry_rejected(self):
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(ValueError):
            aggregate.freeze_cases([], expected_sha="a" * 40, source_run_id=2, output_dir=Path(temp))

    def test_unlisted_artifact_member_rejected(self):
        protocol = contract.read_json(ROOT / "local_optima_study/protocol.json")
        provenance = {"implementation_sha": "a" * 40, "workflow_sha": "a" * 40,
                      "protocol_sha256": contract.PROTOCOL_SHA256,
                      "content_freeze_commit_sha": contract.CONTENT_FREEZE_SHA,
                      "protocol_id": contract.PROTOCOL_ID, "run_id": 2, "run_attempt": 1,
                      "data_sha256": {key: protocol["data"][f"{key}_sha256"] for key in ("archive", "train", "test")}}
        provenance["implementation_files"] = contract.implementation_inventory()
        provenance["implementation_files_sha256"] = contract.canonical_sha256(provenance["implementation_files"])
        # Isolate file-contract checks from unrelated runtime dependency checks.
        # Real numerical execution still authenticates the pinned environment.
        environment = {"python_implementation": "synthetic_test_fixture",
                       "python_version": "fixture", "packages": {}}
        provenance["environment"] = environment
        provenance["environment_sha256"] = contract.canonical_sha256(provenance["environment"])
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(contract, "runtime_environment", return_value=environment):
            directory = Path(temp)
            contract.write_json(directory / "case.json", {"schema": contract.CASE_SCHEMA})
            contract.write_manifest(directory, seed=42001, artifact_name="case", provenance=provenance, row_file="case.json")
            contract.verify_manifest(directory / "manifest.json", expected_sha="a" * 40)
            (directory / "unlisted.txt").write_text("not authenticated", encoding="utf-8")
            with self.assertRaises(ValueError):
                contract.verify_manifest(directory / "manifest.json", expected_sha="a" * 40)


class TerminalLeakageBarrierTests(unittest.TestCase):
    def test_all_four_masks_persist_before_any_official_test(self):
        kernel = literal_trace()
        masks = tuple(tuple(row["mask"]) for row in kernel["evaluations"][:50])
        records = tuple(SimpleNamespace(to_dict=lambda row=row: {
            "call": row["call"], "mask": row["mask"], "fitness": row["fitness"]}) for row in kernel["evaluations"])
        old = SimpleNamespace(objective_calls=400, initial_population_calls=50,
            terminal_payload=lambda: kernel["terminal"],
            normalized_auc_best_so_far_validation_wba_1_400=0.7,
            normalized_auc_best_so_far_validation_wba_51_400=0.7,
            terminal_state={}, termination_phase="complete", reset=False, reset_events=0,
            evaluations=records, generation_trace=())
        names = tuple(TRANSFORMED_FEATURE_NAMES)
        prepared = SimpleNamespace(feature_names=names)
        seen = []
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "case"
            def evaluate(_prepared, mask, *, path, seed, arm, provenance):
                self.assertTrue((output / "terminal-masks.json").is_file())
                self.assertTrue((output / "preparation.json").is_file())
                frozen = contract.read_json(output / "terminal-masks.json")
                self.assertEqual(set(frozen["arms"]), set(contract.ALL_ARMS))
                self.assertEqual(frozen["test_evaluations_so_far"], 0)
                self.assertEqual(mask, frozen["arms"][arm]["mask"])
                seen.append(arm)
                path.write_bytes(b"owned-model-fixture")
                block = {"confusion_matrix": [[8, 2], [3, 7]], "balanced_accuracy": 0.75}
                return {"weighted": block, "unweighted": block}, {"file": path.name}
            protocol = contract.read_json(ROOT / "local_optima_study/protocol.json")
            provenance = {"run_id": 3, "run_attempt": 1}
            with mock.patch.object(run_case, "authenticate", return_value=(protocol, provenance)), \
                 mock.patch.object(run_case, "prepare_data", return_value=prepared), \
                 mock.patch.object(run_case, "objective_for", return_value=lambda mask: (0.7, -sum(mask) / 40)), \
                 mock.patch.object(run_case, "source_density_population", return_value=masks), \
                 mock.patch.object(run_case, "pairing_for", return_value={}), \
                 mock.patch.object(run_case, "run_harmonized_chc", return_value=old), \
                 mock.patch.object(run_case, "run_lambda_search", side_effect=lambda *args, mode, **kwargs:
                                   {**copy.deepcopy(kernel), "arm": "lambda_adaptive" if mode == "adaptive" else "lambda_fixed1"}), \
                 mock.patch.object(run_case, "prepare_case", return_value=literal_preparation()), \
                 mock.patch.object(run_case, "evaluate_and_persist", side_effect=evaluate):
                result = run_case.run_case(protocol_path=ROOT / "local_optima_study/protocol.json",
                    upstream=Path(temp), official_train=Path(temp), official_test=Path(temp), seed=42001,
                    expected_sha="a" * 40, expected_protocol_sha256=contract.PROTOCOL_SHA256,
                    output_dir=output, artifact_name="case-fixture")
            self.assertEqual(seen, list(contract.ALL_ARMS))
            self.assertEqual(result["counts"]["test_evaluations"], 4)
            self.assertEqual(result["arms"]["full40"]["objective_calls"], 1)
            self.assertIsNone(result["arms"]["full40"]["normalized_auc_best_so_far_validation_wba_1_400"])


if __name__ == "__main__":
    unittest.main()

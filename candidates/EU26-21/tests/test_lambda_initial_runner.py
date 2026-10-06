"""Six-arm fixtures and persistence barriers; run only in CI."""
from __future__ import annotations

import copy
import csv
from pathlib import Path
import statistics
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from corrected_applied.data_protocol import TRANSFORMED_FEATURE_NAMES  # noqa: E402
from lambda_initial_study import contract, run_case  # noqa: E402


def score(mask):
    count = sum(mask)
    return (0.5 + count / 100, -count / 40) if count else (0.0, -1.0)


class RunnerTests(unittest.TestCase):
    def fixture(self, output, *, inspect_test_barrier=True):
        physical_masks, evaluated_arms = [], []
        prepared = SimpleNamespace(feature_names=tuple(TRANSFORMED_FEATURE_NAMES))
        initial = tuple(tuple([1] * (1 + index % 4) + [0] * (39 - index % 4)) for index in range(50))
        def objective(mask):
            physical_masks.append(tuple(mask))
            return score(mask)
        def terminal(_prepared, mask, *, path, seed, arm, provenance):
            if inspect_test_barrier:
                frozen = contract.read_json(output / "terminal-masks.json")
                self.assertEqual(set(frozen["arms"]), set(contract.ALL_ARMS))
                self.assertEqual(frozen["test_evaluations_so_far"], 0)
                self.assertEqual(mask, frozen["arms"][arm]["mask"])
                self.assertEqual(frozen["selected_by"], "validation_only")
                self.assertTrue(all((output / f"trace-{name}.json").is_file() for name in contract.ALL_ARMS))
                self.assertEqual(len(physical_masks), 2150)
            evaluated_arms.append(arm)
            path.write_bytes(b"owned-model-fixture")
            weighted = {"confusion_matrix": [[8, 2], [3, 7]], "balanced_accuracy": 0.75}
            matrix = [[80000, 10000], [3000, 6762]]
            classes = contract.per_class_metrics(matrix)
            unweighted = {"confusion_matrix": matrix,
                          "balanced_accuracy": statistics.fmean(classes[key]["recall"] for key in ("0", "1"))}
            model = {"file": path.name, "sha256": contract.file_sha256(path),
                     "bytes": path.stat().st_size, "mask": list(mask), "seed": seed, "arm": arm,
                     "selected_feature_names": [name for name, bit in zip(prepared.feature_names, mask) if bit],
                     "classifier": "DecisionTreeClassifier(random_state=0)",
                     "preprocessing_fit_partition": "internal_training_only",
                     "terminal_fit_partition": "internal_training_only",
                     "reload_verification": "PASS_EXACT_NON_TEST_PROBE",
                     "test_access_during_reload": False}
            return {"weighted": weighted, "unweighted": unweighted}, model
        protocol = contract.validate_protocol(ROOT / "lambda_initial_study/protocol.json")
        def pairing(_prepared, initial_masks, initial_records, seed):
            return {"seed": seed, "initial_masks_sha256": contract.canonical_sha256([list(mask) for mask in initial_masks]),
                    "first_50_evaluations_sha256": contract.canonical_sha256(initial_records)}
        provenance = {"run_id": 3, "run_attempt": 1, "implementation_sha": "a" * 40}
        with mock.patch.object(run_case, "authenticate", return_value=(protocol, provenance)), \
             mock.patch.object(run_case, "prepare_data", return_value=prepared), \
             mock.patch.object(run_case, "objective_for", return_value=objective), \
             mock.patch.object(run_case, "source_density_population", return_value=initial), \
             mock.patch.object(run_case, "pairing_for", side_effect=pairing), \
             mock.patch.object(run_case, "evaluate_and_persist", side_effect=terminal):
            row = run_case.run_case(protocol_path=ROOT / "lambda_initial_study/protocol.json",
                upstream=output.parent, official_train=output.parent, official_test=output.parent,
                seed=43001, expected_sha="a" * 40, expected_protocol_sha256=contract.PROTOCOL_SHA256,
                output_dir=output, artifact_name="eu26-21-lambda-case-43001-3-1")
        return row, physical_masks, evaluated_arms

    def test_all_six_mask_freezes_and_traces_precede_any_test(self):
        with tempfile.TemporaryDirectory() as temp:
            row, _, seen = self.fixture(Path(temp) / "case")
        self.assertEqual(seen, list(contract.ALL_ARMS))
        self.assertEqual(row["counts"], {"shared_initial_validation_calls": 50,
            "postinitial_validation_calls": 2100, "logical_validation_calls": 2400,
            "physical_validation_calls": 2150, "test_evaluations": 6})

    def test_each_registered_initial_lambda_and_adaptive_trace(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "case"
            row, physical, _ = self.fixture(output)
            self.assertEqual(len(physical), 2150)
            for value in contract.LAMBDA_INITIAL_VALUES:
                arm = f"lambda_initial_{value}"
                trace = contract.read_json(output / row["arms"][arm]["trace"]["file"])
                self.assertEqual(trace["lambda_initial"], value)
                self.assertEqual(trace["generation_trace"][0]["lambda_before"], value)
                self.assertEqual(trace["objective_calls"], 400)
                self.assertFalse(trace["reset"])
                self.assertEqual(trace["evaluation_ledger"]["post_initial_physical_calls"], 350)
                self.assertEqual([item["call"] for item in trace["evaluations"]], list(range(1, 401)))
                self.assertEqual(run_case._first_fifty(trace), row["initial_evaluations"])

    def test_lambda40_duplicates_remain_charged_and_first_strength40(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "case"
            row, _, _ = self.fixture(output)
            trace = contract.read_json(output / row["arms"]["lambda_initial_40"]["trace"]["file"])
            first = trace["generation_trace"][0]
            self.assertEqual(first["mutation_probability"], 1)
            self.assertEqual(first["mutation_strength"], 40)
            mutant_masks = [record["mask"] for record in trace["evaluations"][50:90]]
            self.assertEqual(len(mutant_masks), 40)
            self.assertTrue(all(mask == mutant_masks[0] for mask in mutant_masks))
            self.assertGreaterEqual(trace["evaluation_ledger"]["post_initial_duplicate_queries"], 39)

    def test_same_initial_parent_chosen_for_all_lambda_arms(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "case"
            row, _, _ = self.fixture(output)
            indices = [contract.read_json(output / row["arms"][arm]["trace"]["file"])
                       ["terminal_state"]["initial_parent_index"] for arm in contract.LAMBDA_ARMS]
            self.assertEqual(len(set(indices)), 1)

    def test_six_arm_fixture_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, queries1, _ = self.fixture(root / "first")
            second, queries2, _ = self.fixture(root / "second")
            self.assertEqual(first, second)
            self.assertEqual(queries1, queries2)

    def test_real_runner_fixture_passes_independent_case_and_journal_validator(self):
        from lambda_initial_study import aggregate
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "case"
            row, _, _ = self.fixture(output)
            manifest = contract.read_json(output / "manifest.json")
            # Contract-specific SHA/runtime checks have separate focused tests.
            # Retain all real six-arm trace, count, mask, model-hash and metric
            # checks in the independent aggregation path.
            with mock.patch.object(aggregate, "verify_manifest", return_value=manifest):
                result = aggregate.validate_case(output, expected_sha="a" * 40,
                    artifact={"name": "eu26-21-lambda-case-43001-3-1", "id": 3}, source_run=3)
            self.assertEqual(result["row"], row)
            self.assertEqual(set(result["traces"]), set(contract.ALL_ARMS))

    def test_complete_thirty_case_report_tables_preserve_all_arms_and_integer_masks(self):
        from lambda_initial_study import aggregate
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "case"
            row, _, _ = self.fixture(output)
            traces = {arm: contract.read_json(output / row["arms"][arm]["trace"]["file"])
                      for arm in contract.ALL_ARMS}
            cases = []
            for seed in contract.CASE_SEEDS:
                case_row = copy.deepcopy(row)
                case_row["seed"] = seed
                name = f"eu26-21-lambda-case-{seed}-3-1"
                cases.append({"row": case_row, "traces": traces,
                              "artifact": {"id": seed, "name": name},
                              "manifest_sha256": "a" * 64})
            sources = {"implementation_sha": "a" * 40, "source_run_id": 3}
            report_output = root / "report"
            with mock.patch.object(aggregate, "make_plots") as plots, \
                 mock.patch.object(aggregate, "bootstrap", side_effect=AssertionError("constant differences are descriptive")):
                result = aggregate.build_report(cases, sources, output=report_output, transport={"fixture": True})
            plots.assert_called_once()
            self.assertEqual(result["case_count"], 30)
            self.assertEqual(result["arm_count"], 6)
            self.assertEqual(result["counts"], {"logical_validation_calls": 72000,
                "physical_validation_calls": 64500, "test_evaluations": 180})
            with (report_output / "comparison.csv").open(encoding="utf-8", newline="") as stream:
                records = list(csv.DictReader(stream))
            self.assertEqual(len(records), 180)
            self.assertEqual({record["arm"] for record in records}, set(contract.ALL_ARMS))
            self.assertTrue(all(int(record["selected_features"]) == record["mask"].count("1") for record in records))
            with (report_output / "trajectories.csv").open(encoding="utf-8", newline="") as stream:
                self.assertEqual(sum(1 for _ in csv.DictReader(stream)), 72000)
            with (report_output / "contrasts.csv").open(encoding="utf-8", newline="") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 14)
            self.assertFalse(any(result["analysis"]["joint_search_advantage"].values()))

    def test_existing_output_not_overwritten_or_scientifically_evaluated(self):
        protocol = contract.validate_protocol(ROOT / "lambda_initial_study/protocol.json")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            original = output / "owned.txt"
            original.write_bytes(b"preserve")
            with mock.patch.object(run_case, "authenticate", return_value=(protocol, {})), \
                 mock.patch.object(run_case, "prepare_data") as prepare, self.assertRaises(ValueError):
                run_case.run_case(protocol_path=ROOT / "lambda_initial_study/protocol.json",
                    upstream=output, official_train=output, official_test=output,
                    seed=43001, expected_sha="a" * 40, expected_protocol_sha256=contract.PROTOCOL_SHA256,
                    output_dir=output, artifact_name="case-fixture")
            prepare.assert_not_called()
            self.assertEqual(original.read_bytes(), b"preserve")


if __name__ == "__main__":
    unittest.main()

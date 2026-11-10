"""Synthetic CI-only checks; none of these fixtures are study observations.

No test runs at import. Setup requires the authorized technical CI stage; test
data are synthetic and no actual main observations are read. The actual analysis
keeps exactly 50,000 BCa family resamples; a private numeric helper is exercised
with fewer draws only on deliberately synthetic vectors.
"""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from . import analysis
from .common import read_json
from studies.knapsack_parameters.population_validation_100.common import guard_technical


class AnalysisChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        guard_technical()
        cls.protocol = read_json(Path(analysis.__file__).resolve().parent / "protocol.json")

    def setUp(self):
        # Synthetic manifests carry synthetic provenance; the real CI guard is
        # still checked above, and no actual main observations are involved.
        self.execution = {"workflow_commit": "b" * 40, "workflow_run_id": "123",
                          "code_manifest_sha256": "c" * 64}
        stub = patch.object(analysis, "_execution_context", return_value=self.execution)
        stub.start()
        self.addCleanup(stub.stop)

    @staticmethod
    def fixture_row(family="s050", kind="UC", mu=10, seed=150001, best=None, first_q=25):
        best = {10: 900, 20: 920, 30: 910}[mu] if best is None else best
        optimum = 1000
        task = f"n00100-{kind}-{family}"
        events = [[1, 0], [first_q, best]]
        targets = {}
        for target in analysis.TARGETS:
            first = first_q if 100 * best >= target * optimum else None
            targets[str(target)] = {"attained": first is not None, "first_total_evaluation": first,
                                    "restricted_evaluations": first if first is not None else analysis.TOTAL}
        metrics = {"population_size": mu, "unique_fraction": .9, "feasible_fraction": .8,
                   "mean_pairwise_hamming": 5.0}
        checkpoints = [{"q": q, "record_profit": best if q >= first_q else 0,
                        "population_metrics": deepcopy(metrics), "completed_generations": (q - mu) // (mu - 1)}
                       for q in analysis.CHECKPOINTS]
        return {"task": task, "task_index": 3 + (int(family[1:]) - 50) * 3 + analysis.TYPES.index(kind),
                "family": family, "class_label": kind, "mu": mu, "seed": seed, "optimum": optimum,
                "best": best, "events": events, "checkpoints": checkpoints, "targets": targets,
                "completed_generations": (analysis.TOTAL - mu) // (mu - 1), "duplicates": 0,
                "artifact_hashes": {name: "0" * 64 for name in analysis.FILES},
                "bank_sha256": "1" * 64, "certificate_sha256": "2" * 64,
                "artifact_prefix": f"{task}/seed-{seed}",
                "timing": {"search_seconds": 1.0, "log_write_seconds": 1.0, "verification_seconds": 1.0,
                           "observations_seconds": 1.0, "case_seconds": 5.0, "artifact_bytes": 100}}

    def write_shards(self, root, skip=None):
        prepared_hash = "a" * 64
        for family in analysis.FAMILIES:
            for mu in analysis.POPS:
                if (family, mu) == skip:
                    continue
                rows = [self.fixture_row(family, kind, mu, seed) for kind in analysis.TYPES for seed in analysis.SEEDS]
                target = root / (family + "-mu" + str(mu)) / "compact.json"
                target.parent.mkdir(parents=True)
                target.write_text(json.dumps({"schema": "population-validation-100-main-shard-v1", "status": "VERIFIED",
                                  "family": family, "mu": mu, "runs": rows,
                                  "raw_artifact_name": f"population100-main-raw-{family}-mu{mu}-123",
                                  "source_manifest_sha256": prepared_hash,
                                  "technical_input_manifest_sha256": self.protocol["technical_input_manifest_sha256"],
                                  **self.execution}),
                                  encoding="utf-8")

    def test_equal_threshold_is_attained_and_missed_remains_in_denominator(self):
        row = self.fixture_row(best=930)
        checked = analysis.validate_row(row, "s050", 10)
        self.assertEqual(checked["targets"]["93"]["first_total_evaluation"], 25)
        self.assertFalse(checked["targets"]["95"]["attained"])
        self.assertEqual(checked["targets"]["95"]["restricted_evaluations"], 100000)
        damaged = deepcopy(row)
        damaged["targets"]["93"]["attained"] = False
        with self.assertRaises(ValueError):
            analysis.validate_row(damaged, "s050", 10)

    def test_last_evaluation_is_included(self):
        row = self.fixture_row(best=990, first_q=100000)
        analysis.validate_row(row, "s050", 10)
        self.assertEqual(row["targets"]["99"]["first_total_evaluation"], 100000)
        self.assertTrue(row["targets"]["99"]["attained"])
        self.assertEqual(row["checkpoints"][-1]["record_profit"], 990)

    def test_bca_degenerate_intervals_are_undefined_not_equal(self):
        result = analysis._bca_compute([[0.0, .4] for _ in range(10)], replicates=1000, seed=7, confidence=.975)
        for item in result["intervals"]:
            self.assertEqual(item["status"], "DESCRIPTIVE_UNDEFINED")
            self.assertIsNone(item["lower_pp"])
            self.assertIsNone(item["upper_pp"])
            self.assertFalse(item["positive_lower_bound"])

    def test_bca_variable_vectors_and_registered_draw_guard(self):
        vectors = [[(i - 4) / 10, (i - 3) / 10] for i in range(10)]
        first = analysis._bca_compute(vectors, replicates=1000, seed=7, confidence=.975)
        second = analysis._bca_compute(vectors, replicates=1000, seed=7, confidence=.975)
        self.assertEqual(first, second)
        self.assertEqual([r["status"] for r in first["intervals"]], ["NOMINAL_BCA", "NOMINAL_BCA"])
        with self.assertRaises(ValueError):
            analysis.bca(vectors, replicates=1000, seed=7, confidence=.975)

    def test_missing_shard_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_shards(root, skip=("s059", 30))
            with self.assertRaises(ValueError):
                analysis.load_shards(root, self.protocol)

    def test_duplicate_run_and_incompatible_input_provenance_are_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_shards(root)
            rows, _ = analysis.load_shards(root, self.protocol)
            self.assertEqual(len(rows), 900)
            path = root / "s050-mu10" / "compact.json"
            original = json.loads(path.read_text(encoding="utf-8"))
            duplicate = deepcopy(original)
            duplicate["runs"][1] = deepcopy(duplicate["runs"][0])
            path.write_text(json.dumps(duplicate), encoding="utf-8")
            with self.assertRaises(ValueError):
                analysis.load_shards(root, self.protocol)
            wrong_provenance = deepcopy(original)
            wrong_provenance["technical_input_manifest_sha256"] = "f" * 64
            path.write_text(json.dumps(wrong_provenance), encoding="utf-8")
            with self.assertRaises(ValueError):
                analysis.load_shards(root, self.protocol)
            wrong_bank = deepcopy(original)
            wrong_bank["runs"][0]["bank_sha256"] = "f" * 64
            path.write_text(json.dumps(wrong_bank), encoding="utf-8")
            with self.assertRaises(ValueError):
                analysis.load_shards(root, self.protocol)

    def test_primary_effect_direction_and_balanced_family_means(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_shards(root)
            records, _ = analysis.load_shards(root, self.protocol)
            # No scientific bootstrap is run on fixtures; only the direction and
            # weighted inputs to the numeric bootstrap helper are inspected.
            with patch.object(analysis, "bca", return_value={"intervals": []}) as bootstrap:
                profiles, _, families, loo, _, _ = analysis.summarize(records)
            self.assertEqual([r["mean_final_gap_percent"] for r in profiles], [10.0, 8.0, 9.0])
            self.assertTrue(all(r["population10_minus_population20_pp"] == 2.0 for r in families))
            self.assertTrue(all(r["population30_minus_population20_pp"] == 1.0 for r in families))
            self.assertTrue(all(r["population10_minus_population20_pp"] == 2.0 for r in loo))
            self.assertEqual(bootstrap.call_args.args[0], [[2.0, 1.0]] * 10)

    def test_mixed_ci_commit_run_and_code_seal_are_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_shards(root)
            path = root / "s050-mu10" / "compact.json"
            original = json.loads(path.read_text(encoding="utf-8"))
            for field, bad in (("workflow_commit", "f" * 40), ("workflow_run_id", "124"),
                               ("code_manifest_sha256", "e" * 64)):
                changed = deepcopy(original)
                changed[field] = bad
                path.write_text(json.dumps(changed), encoding="utf-8")
                with self.subTest(field=field), self.assertRaises(ValueError):
                    analysis.load_shards(root, self.protocol)


if __name__ == "__main__":
    unittest.main()

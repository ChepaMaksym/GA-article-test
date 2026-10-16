from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.basic_parameters import contract as c
from studies.knapsack_parameters.basic_parameters.data import duplicate_audit, source_path
from studies.knapsack_parameters.feasibility.data_audit import Instance, parse_instance
from studies.knapsack_parameters.feasibility.solvers import solve_capacity, solve_profit
from studies.knapsack_parameters.feasibility.ascent import prepare_center
from studies.knapsack_parameters.feasibility.certification import certify_center


class AuthorityDataTests(unittest.TestCase):
    def test_markers(self):
        self.assertEqual(c.phase("New [basic-parameters:tests]"), "tests")
        for message in ("none", "[basic-parameters:lambda]", "[basic-parameters:tests] [old:main]",
                        "[basic-parameters:main] [basic-parameters:pilot]"):
            with self.assertRaises(ValueError):
                c.phase(message)

    def test_manifest_roundtrip_corruption_extras(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            c.write_json(p / "one.json", {"x": 1})
            c.manifest(p)
            c.verify_manifest(p)
            original = (p / "one.json").read_bytes()
            (p / "one.json").write_bytes(b"broken")
            with self.assertRaises(ValueError):
                c.verify_manifest(p)
            (p / "one.json").write_bytes(original)
            (p / "extra.txt").write_text("extra")
            with self.assertRaises(ValueError):
                c.verify_manifest(p)

    def test_manifest_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            c.write_json(p / "file_manifest.json", {"protocol_id": c.PROTOCOL, "excludes_self": True,
                "files": [{"path": "../escape", "bytes": 0, "sha256": "0" * 64}]})
            with self.assertRaises(ValueError):
                c.verify_manifest(p)

    def test_holdout_source_paths(self):
        paths = {source_path(label, i) for label in ("UC", "WC", "SC") for i in range(10, 20)}
        self.assertEqual(len(paths), 30)
        self.assertIn("00Uncorrelated/n00100/R01000/s010.kp", paths)

    def test_pairwise_duplicates_not_independence(self):
        a = Instance(2, 3, (2, 3), (1, 2), "a", "UC", "s000", 0)
        b = Instance(2, 3, (2, 3), (1, 2), "b", "WC", "s000", 0)
        d = Instance(2, 3, (4, 3), (1, 2), "d", "SC", "s000", 0)
        report = duplicate_audit([a, b, d])
        self.assertEqual(report["pairs_checked"], 3)
        self.assertEqual(len(report["exact_duplicates"]), 1)
        self.assertEqual(len(report["same_family_comparisons"]), 3)
        with self.assertRaises(ValueError):
            duplicate_audit([a, a])

    def test_parse_original_profit_weight_and_invalid(self):
        i = parse_instance(b"2\n3\n7 1\n5 2\n", "test", class_label="UC", family="s010", index=10, expected_n=2)
        self.assertEqual(i.profits, (7, 5))
        self.assertEqual(i.weights, (1, 2))
        for bad in (b"2\n3\n7 1\n", b"2\n3\n7 0\n5 2\n", b"2\n3\n7 1 1\n5 2\n"):
            with self.assertRaises(ValueError):
                parse_instance(bad, "bad", class_label="UC", family="s010", index=10, expected_n=2)

    def test_two_exact_methods_against_enumeration(self):
        for weights, profits, capacity in (((6, 5, 5), (10, 8, 8), 10),
                ((2, 2, 1), (3, 3, 1), 2), ((1, 2, 3, 4), (2, 5, 6, 8), 5)):
            n = len(weights)
            instance = Instance(n, capacity, profits, weights, "test", "UC", "s010", 10)
            exact = max(sum(profits[j] for j in range(n) if bits >> j & 1)
                for bits in range(2**n) if sum(weights[j] for j in range(n) if bits >> j & 1) <= capacity)
            for result in (solve_capacity(instance), solve_profit(instance)):
                self.assertEqual(result["optimum_profit"], exact)
                mask = result["witness_mask"]
                self.assertEqual(sum(p * int(b) for p, b in zip(profits, mask)), exact)
                self.assertLessEqual(sum(w * int(b) for w, b in zip(weights, mask)), capacity)

    def test_non_global_n2_teaching_fixture(self):
        instance = Instance(3, 10, (10, 8, 8), (6, 5, 5), "test", "UC", "s010", 10)
        center = prepare_center(instance, max_passes=100)
        self.assertEqual(center["center"]["mask"], "100")
        certificate, rows = certify_center(instance, "100")
        self.assertTrue(certificate["strict"])
        self.assertTrue(certificate["local_maximum"])
        self.assertEqual(len(rows), 6)
        self.assertEqual(solve_capacity(instance)["optimum_profit"], 16)

    def test_missing_budget_token_fails(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            with self.assertRaises(ValueError):
                c.api("/actions/runs")

    def test_green_receipt_cannot_match_changed_sources(self):
        with patch.object(c, "read_json", return_value={"protocol_id": c.PROTOCOL, "success": True,
                "source_manifest_sha256": "a"}), patch.object(c, "source_manifest", return_value={"sha256": "b"}):
            with self.assertRaises(ValueError):
                c.validate_tests()

    def test_failed_job_rerun_without_new_gate_is_blocked(self):
        with patch.object(c, "pages", return_value=[]):
            with self.assertRaises(ValueError):
                c.require_current_gate({"run_id": 1, "run_attempt": 2}, "pilot")

    def test_gate_wrong_attempt_or_insufficient_budget_is_blocked(self):
        provenance = {"run_id": 1, "run_attempt": 2, "implementation_sha": "a" * 40,
                      "source_manifest": {"sha256": "b"}}
        valid = {**provenance, "phase": "pilot", "reserved_runner_minutes": 31,
                 "used_runner_minutes": 0, "technical_runner_minutes": 0}
        with patch.object(c, "pages", return_value=[{"name": "basic-gate-1-2"}]), \
                patch.object(c, "artifact_document", return_value=valid):
            c.require_current_gate(provenance, "pilot")
            valid["run_attempt"] = 1
            with self.assertRaises(ValueError):
                c.require_current_gate(provenance, "pilot")
            valid["run_attempt"] = 2
            valid["technical_runner_minutes"] = 30
            with self.assertRaises(ValueError):
                c.require_current_gate(provenance, "pilot")


if __name__ == "__main__":
    unittest.main()

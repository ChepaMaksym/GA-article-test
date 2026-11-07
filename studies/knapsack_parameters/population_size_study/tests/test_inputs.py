"""CI-only tests of strict inputs, reproducible banks and two independent oracles."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import tempfile
from time import monotonic
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.population_size_study import exact, inputs


TOY = {"n": 4, "capacity": 8, "profits": [8, 5, 7, 4], "weights": [5, 3, 4, 2]}


def brute_force_optimum(problem):
    best = 0
    for bits in product((0, 1), repeat=problem["n"]):
        weight = sum(bit * w for bit, w in zip(bits, problem["weights"], strict=True))
        value = sum(bit * v for bit, v in zip(bits, problem["profits"], strict=True))
        if weight <= problem["capacity"]:
            best = max(best, value)
    return best


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Input fixtures run only in GitHub Actions")
class InputParsingTests(unittest.TestCase):
    def test_source_order_and_raw_integer_format(self):
        raw = b"4\r\n8\r\n8 5\r\n5 3\r\n7 4\r\n4 2\r\n"
        self.assertEqual(inputs.parse_kp_bytes(raw, 4), TOY)
        self.assertEqual(inputs.parse_kp_bytes(raw.replace(b"\r\n", b"\n"), 4), TOY)

    def test_corrupted_source_bytes_rejected(self):
        invalid = (
            b"4\n8\n8 5\n5 3\n7 4\n",  # Missing item.
            b"4\n8\n8 5\n5 3\n7 4\n4 2\n1 1\n",  # Extra item.
            b"4\n8\n8 5\n5 3\n7 -4\n4 2\n",
            b"4\n8\n8 5\n5 3\n7 0\n4 2\n",
            b"4\n8\n8 5\n5 3\n7 4\n4.0 2\n",
            b"4 8\n8 5\n5 3\n7 4\n4 2\n",
            b"\xef\xbb\xbf4\n8\n8 5\n5 3\n7 4\n4 2\n",
            b"4\n8\n8 5\n5 3\n7 4\n4 \xff\n",
        )
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises((ValueError, UnicodeError)):
                inputs.parse_kp_bytes(raw, 4)

    def test_wrong_dimension_and_boolean_expected_dimension(self):
        raw = b"4\n8\n8 5\n5 3\n7 4\n4 2\n"
        for n in (3, True):
            with self.subTest(n=n), self.assertRaises(ValueError):
                inputs.parse_kp_bytes(raw, n)

    def test_problem_hash_preserves_order_and_detects_equivalent_permutation(self):
        permuted = {**TOY, "weights": list(reversed(TOY["weights"])), "profits": list(reversed(TOY["profits"]))}
        self.assertNotEqual(inputs.problem_sha256(TOY), inputs.problem_sha256(permuted))
        self.assertEqual(inputs.unordered_problem_sha256(TOY), inputs.unordered_problem_sha256(permuted))

    def test_task_sets_are_complete_and_holdout_is_disjoint(self):
        pilot, train, holdout = (inputs.task_specs(mode) for mode in ("pilot", "train", "holdout"))
        self.assertEqual([len(pilot), len(train), len(holdout)], [9, 90, 90])
        self.assertEqual({row["n"] for row in pilot}, {100, 200, 500})
        self.assertEqual(len({row["task_id"] for row in train}), 90)
        self.assertEqual(len({row["task_index"] for row in train + holdout}), 180)
        self.assertFalse({row["family"] for row in train} & {row["family"] for row in holdout})
        for row in train + holdout:
            self.assertIn(f"/n{row['n']:05d}/R01000/", row["source_path"])
            self.assertEqual(row["url"], inputs.SOURCE_BASE + row["source_path"])

    def test_kernel_problem_rejects_oracle_metadata(self):
        with self.assertRaises(ValueError):
            inputs.problem_sha256({**TOY, "optimum": 15})


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific checks run only in GitHub Actions")
class BankTests(unittest.TestCase):
    def test_preparation_prefixes_are_identical_for_different_requested_sizes(self):
        short, short_metadata = inputs.make_bank(TOY, 130001, 0, bank_size=5)
        long, long_metadata = inputs.make_bank(TOY, 130001, 0, bank_size=15)
        self.assertEqual(short["masks"], long["masks"][:5])
        self.assertEqual(short["scores"], long["scores"][:5])
        self.assertEqual(short_metadata["rng_before"], long_metadata["rng_before"])
        self.assertEqual(long["masks"][0], "0000")
        self.assertEqual(inputs.validate_bank(TOY, long, long_metadata)["independent_verification_evaluations"], 15)

    def test_determinism_and_bank_verification_leave_metadata_unchanged(self):
        first = inputs.make_bank(TOY, 130001, 0, bank_size=12)
        second = inputs.make_bank(TOY, 130001, 0, bank_size=12)
        self.assertEqual(first, second)
        saved = deepcopy(first)
        inputs.validate_bank(TOY, *first)
        self.assertEqual(first, saved)

    def test_corrupt_mask_score_and_generator_state_are_rejected(self):
        bank, metadata = inputs.make_bank(TOY, 130001, 0, bank_size=12)
        bad_bank = deepcopy(bank)
        bad_bank["masks"][1] = "2222"
        with self.assertRaises(ValueError):
            inputs.validate_bank(TOY, bad_bank, metadata)
        bad_bank = deepcopy(bank)
        bad_bank["scores"][0]["profit"] = True
        with self.assertRaises(ValueError):
            inputs.validate_bank(TOY, bad_bank, metadata)
        bad_metadata = deepcopy(metadata)
        bad_metadata["rng_after"]["state"]["state"] += 1
        with self.assertRaises(ValueError):
            inputs.validate_bank(TOY, bank, bad_metadata)

    def test_preparation_and_validation_are_rejected_outside_ci(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                inputs.make_bank(TOY, 130001, 0, bank_size=3)
            with self.assertRaises(ValueError):
                inputs.validate_bank(TOY, {}, {})


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific checks run only in GitHub Actions")
class ExactOracleTests(unittest.TestCase):
    def assert_exact(self, problem):
        certificate = exact.certify_problem(problem)
        wanted = brute_force_optimum(problem)
        self.assertEqual(certificate["optimum"], wanted)
        for name in ("capacity_certificate", "profit_certificate"):
            result = certificate[name]
            mask = result["witness_mask"]
            self.assertEqual(len(mask), problem["n"])
            self.assertFalse(set(mask) - {"0", "1"})
            self.assertEqual(sum(v for v, bit in zip(problem["profits"], mask, strict=True) if bit == "1"), wanted)
            self.assertLessEqual(sum(w for w, bit in zip(problem["weights"], mask, strict=True) if bit == "1"), problem["capacity"])
        return certificate

    def test_both_oracles_agree_with_complete_enumeration(self):
        self.assert_exact(TOY)
        self.assert_exact({"n": 5, "capacity": 11, "profits": [3, 8, 4, 9, 5], "weights": [2, 6, 3, 7, 4]})

    def test_empty_all_fit_and_exact_capacity(self):
        for capacity in (0, 100, 8):
            self.assert_exact({**TOY, "capacity": capacity})

    def test_unreachable_profit_gaps_and_oversized_items(self):
        self.assert_exact({"n": 4, "capacity": 7, "profits": [7, 19, 31, 43], "weights": [4, 8, 1000000, 3]})

    def test_duplicate_items_and_witness_cannot_reuse_one_item(self):
        self.assert_exact({"n": 4, "capacity": 8, "profits": [5, 5, 5, 13], "weights": [3, 3, 3, 8]})
        self.assert_exact({"n": 2, "capacity": 6, "profits": [5, 2], "weights": [3, 100]})

    def test_packed_witness_crosses_byte_boundaries(self):
        self.assert_exact({"n": 9, "capacity": 19, "profits": [3, 5, 7, 9, 11, 13, 17, 19, 23],
                           "weights": [2, 3, 5, 7, 11, 13, 2, 3, 4]})

    def test_memory_limit_and_deadline_stop_without_an_approximation(self):
        with self.assertRaises(exact.ExactResourceLimit):
            exact.certify_problem(TOY, memory_limit_bytes=1)
        with self.assertRaises(exact.ExactPreparationTimeout):
            exact.certify_problem(TOY, deadline=monotonic() - 1)
        for deadline in (True, float("inf"), float("nan")):
            with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                exact.certify_problem(TOY, deadline=deadline)

    def test_oracle_disagreement_is_not_admitted(self):
        with patch.object(exact, "solve_profit", return_value={"optimum_profit": -1}):
            with self.assertRaises(ArithmeticError):
                exact.certify_problem(TOY)

    def test_overflowing_source_sums_are_rejected_before_allocation(self):
        huge = {"n": 2, "capacity": 1, "profits": [2**63, 1], "weights": [1, 1]}
        with self.assertRaises(exact.ExactResourceLimit):
            exact.certify_problem(huge)

    def test_oracles_refuse_execution_outside_ci(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            for solver in (exact.solve_capacity, exact.solve_profit, exact.certify_problem):
                with self.subTest(solver=solver.__name__), self.assertRaises(ValueError):
                    solver(TOY)


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific checks run only in GitHub Actions")
class OfflineSourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.pinned = {}
        inventory_mock = patch.object(inputs, "_pinned_inventory", side_effect=lambda: deepcopy(self.pinned))
        inventory_mock.start()
        self.addCleanup(inventory_mock.stop)

    def snapshot(self, specs):
        files = []
        license_bytes = b"Creative Commons Attribution 4.0 International License\n"
        (self.root / "README.md").write_bytes(license_bytes)
        files.append({"source_path": "README.md", "url": inputs.SOURCE_BASE + "README.md",
                      "sha256": hashlib.sha256(license_bytes).hexdigest(), "bytes": len(license_bytes),
                      "git_blob_sha1": inputs._git_blob_sha1(license_bytes)})
        for index, spec in enumerate(specs):
            n = spec["n"]
            # Different capacities provide distinct tiny synthetic fixtures.
            raw = f"{n}\n{index + 1}\n".encode() + b"1 1\n" * n
            path = self.root / spec["source_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            files.append({"source_path": spec["source_path"], "url": spec["url"],
                          "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                          "git_blob_sha1": inputs._git_blob_sha1(raw)})
        value = {"source_commit": inputs.SOURCE_COMMIT, "files": files,
                 "fixture": "synthetic_transport_unit_test_not_KPLIB_evidence"}
        (self.root / "source_snapshot.json").write_text(json.dumps(value), encoding="utf-8")
        self.pinned = {row["source_path"]: {key: row[key] for key in ("source_path", "git_blob_sha1", "bytes")}
                       for row in files}
        return value

    def test_pilot_audit_freezes_all_nine_fixture_sources(self):
        self.snapshot(inputs.task_specs("pilot"))
        manifest = inputs.audit_corpus(self.root, "pilot")
        self.assertEqual(manifest["case_count"], 9)
        self.assertFalse(manifest["ga_search_performed"])
        self.assertEqual(len(manifest["source_files"]), 10)

    def test_modified_bytes_mixed_revision_and_missing_file_are_rejected(self):
        snapshot = self.snapshot(inputs.task_specs("pilot"))
        first = self.root / snapshot["files"][1]["source_path"]
        first.write_bytes(first.read_bytes() + b"\n")
        with self.assertRaises(ValueError):
            inputs.audit_corpus(self.root, "pilot")
        snapshot = self.snapshot(inputs.task_specs("pilot"))
        snapshot["source_commit"] = "0" * 40
        (self.root / "source_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
        with self.assertRaises(ValueError):
            inputs.audit_corpus(self.root, "pilot")
        self.snapshot(inputs.task_specs("pilot"))
        first.unlink()
        with self.assertRaises(ValueError):
            inputs.audit_corpus(self.root, "pilot")

    def test_duplicate_tasks_and_unsafe_paths_are_rejected(self):
        snapshot = self.snapshot(inputs.task_specs("pilot"))
        snapshot["files"].append(deepcopy(snapshot["files"][1]))
        (self.root / "source_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
        with self.assertRaises(ValueError):
            inputs.audit_corpus(self.root, "pilot")
        for relative in ("../README.md", "/README.md", "C:/README.md", "folder\\README.md"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                inputs._safe_file(self.root, relative)

    def test_recomputed_sha256_does_not_replace_the_registered_git_blob(self):
        snapshot = self.snapshot(inputs.task_specs("pilot"))
        first = snapshot["files"][1]
        path = self.root / first["source_path"]
        raw = path.read_bytes().replace(b"1 1\n", b"2 1\n", 1)
        path.write_bytes(raw)
        first["sha256"] = hashlib.sha256(raw).hexdigest()
        (self.root / "source_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
        with self.assertRaises(ValueError):
            inputs.audit_corpus(self.root, "pilot")

    def test_equal_problem_under_distinct_identities_is_not_admitted(self):
        snapshot = self.snapshot(inputs.task_specs("pilot"))
        first, second = snapshot["files"][1:3]
        raw = (self.root / first["source_path"]).read_bytes()
        # Both of these registered pilot fixtures have n=100.
        (self.root / second["source_path"]).write_bytes(raw)
        second.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), git_blob_sha1=inputs._git_blob_sha1(raw))
        self.pinned[second["source_path"]].update(bytes=len(raw), git_blob_sha1=inputs._git_blob_sha1(raw))
        (self.root / "source_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
        with self.assertRaises(ValueError):
            inputs.audit_corpus(self.root, "pilot")

    def test_holdout_cannot_be_audited_without_training_manifest(self):
        self.snapshot(inputs.task_specs("holdout"))
        with self.assertRaises(ValueError):
            inputs.audit_corpus(self.root, "holdout")


if __name__ == "__main__":
    unittest.main()

"""Offline provenance fixtures; run only by the bounded GitHub Actions workflow."""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.lambda_study.contract import AUTHOR_REPO, AUTHOR_SHA, INPUT_REPO, INPUT_SHA
from studies.knapsack_parameters.lambda_study.source_audit import (
    _download, audit_ising, catalog_results, cpp_seed_identity, extract_snapshot,
    git_blob_sha, parse_cpp_config, parse_cpp_dat, parse_python_log,
    validate_ising_bytes, validate_source_identity, verify_snapshot,
    write_compact_bundle, landscape_catalog,
)


def archive_bytes(members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        root = tarfile.TarInfo("repo-sha")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        for name, data, kind in members:
            member = tarfile.TarInfo(name)
            member.type = kind
            if kind == tarfile.REGTYPE:
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            else:
                member.linkname = "outside"
                archive.addfile(member)
    return buffer.getvalue()


def ising_fixture(n=16):
    side = 4
    edges = [(a, a // side * side + (a % side + 1) % side, 1) for a in range(n)]
    edges += [(a, (a + side) % n, 1) for a in range(n)]
    text = f"{-2*n} {'0'*n}\n{2*n}\n"
    return (text + "".join(f"{a} {b} {coupling}\n" for a, b, coupling in edges)).encode("ascii")


def python_log(seed=123, run_count=2):
    return (f"Experiment configurations\nSeed: {seed}\nProblem: Jump\nSize: 40\tk: 4\tExtra: None\n"
            f"Runs: {run_count}\nAlgorithm: JA.OnePlusLambdaCommaLambdaSA\n"
            "Initial offspring population size: 40\n"
            "Final results: Run: 1 Gens: 2 Evals: 4 λ: 1 p: 0.025 Solved: True\n"
            "Final results: Run: 2 Gens: 3 Evals: 6 λ: 1 p: 0.025 Solved: False\n")


class ArchiveTests(unittest.TestCase):
    def test_exact_bytes_and_normal_colon_filename(self):
        archive = archive_bytes([("repo-sha/Raw/results_12:34.txt", b"hello\r\n", tarfile.REGTYPE)])
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "source"
            extract_snapshot(archive, target, "repo-sha")
            self.assertEqual((target / "Raw" / "results_12:34.txt").read_bytes(), b"hello\r\n")

    def test_traversal_and_drive_and_absolute_are_rejected_before_writes(self):
        for name in ("repo-sha/../escape", "repo-sha/C:/escape", "/repo-sha/file", "repo-sha/a\\b"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / "source"
                archive = archive_bytes([(name, b"data", tarfile.REGTYPE)])
                with self.assertRaises(ValueError):
                    extract_snapshot(archive, target, "repo-sha")
                self.assertFalse(target.exists())

    def test_links_and_duplicates_rejected(self):
        cases = [
            [("repo-sha/link", b"", tarfile.SYMTYPE)],
            [("repo-sha/link", b"", tarfile.LNKTYPE)],
            [("repo-sha/file", b"a", tarfile.REGTYPE), ("repo-sha/file", b"b", tarfile.REGTYPE)],
        ]
        for members in cases:
            with tempfile.TemporaryDirectory() as temporary:
                with self.assertRaises(ValueError):
                    extract_snapshot(archive_bytes(members), Path(temporary) / "source", "repo-sha")

    def test_wrong_prefix_and_existing_target_rejected(self):
        archive = archive_bytes([("repo-sha/file", b"x", tarfile.REGTYPE)])
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "source"
            with self.assertRaises(ValueError):
                extract_snapshot(archive, target, "other-sha")
            target.mkdir()
            with self.assertRaises(ValueError):
                extract_snapshot(archive, target, "repo-sha")


class IdentityTests(unittest.TestCase):
    def test_known_git_blob_and_sha256(self):
        self.assertEqual(git_blob_sha(b"hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "file").write_bytes(b"hello\n")
            tree = {"truncated": False, "tree": [{"path": "file", "type": "blob", "mode": "100644",
                                                  "sha": "ce013625030ba8dba906f756967f9e9ca394464a", "size": 6}]}
            manifest = verify_snapshot(root, tree, AUTHOR_REPO, AUTHOR_SHA)
            self.assertEqual(manifest[0]["sha256"], hashlib.sha256(b"hello\n").hexdigest())
            tree["tree"][0]["sha"] = "0" * 40
            with self.assertRaisesRegex(ValueError, "Git blob mismatch"):
                verify_snapshot(root, tree, AUTHOR_REPO, AUTHOR_SHA)

    def test_missing_extra_and_truncated_tree_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tree = {"truncated": True, "tree": []}
            with self.assertRaises(ValueError):
                verify_snapshot(root, tree, AUTHOR_REPO, AUTHOR_SHA)
            tree["truncated"] = False
            (root / "unexpected").write_bytes(b"x")
            with self.assertRaises(ValueError):
                verify_snapshot(root, tree, AUTHOR_REPO, AUTHOR_SHA)

    def test_only_registered_source_identities(self):
        validate_source_identity(AUTHOR_REPO, AUTHOR_SHA, "author")
        validate_source_identity(INPUT_REPO, INPUT_SHA, "inputs")
        with self.assertRaises(ValueError):
            validate_source_identity(AUTHOR_REPO, "0" * 40, "author")
        with self.assertRaises(ValueError):
            validate_source_identity(AUTHOR_REPO, AUTHOR_SHA, "inputs")

    def test_network_is_guarded_outside_actions(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                _download("https://example.invalid")


class IsingTests(unittest.TestCase):
    def test_integer_witness_and_grid(self):
        result = validate_ising_bytes(ising_fixture(), 16)
        self.assertEqual(result["witness_energy"], -32)
        self.assertTrue(result["witness_verified"])
        self.assertFalse(result["optimality_independently_proven"])

    def test_truncated_bad_witness_and_energy_rejected(self):
        fixture = ising_fixture()
        variants = [fixture.rsplit(b"\n", 2)[0], fixture.replace(b"-32 ", b"-30 ", 1),
                    fixture.replace(b"0000000000000000", b"000000000000000x", 1),
                    fixture.replace(b"0 1 1", b"0 16 1", 1)]
        for data in variants:
            with self.subTest(data=data[:40]), self.assertRaises(ValueError):
                validate_ising_bytes(data, 16)

    def test_all_requested_files_are_required_and_analyzed_ids_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixtures = root / "problem_files"
            fixtures.mkdir()
            (fixtures / "IsingSpinGlass_pm_16_0.txt").write_bytes(ising_fixture())
            missing = audit_ising(root, (16,), (0, 100))
            self.assertFalse(missing["complete"])
            self.assertEqual(missing["prior_verified_files"], 1)
            self.assertEqual(len(missing["errors"]), 1)
            (fixtures / "IsingSpinGlass_pm_16_100.txt").write_bytes(ising_fixture())
            complete = audit_ising(root, (16,), (0, 100))
            self.assertTrue(complete["complete"])
            self.assertEqual(complete["analyzed_verified_files"], 1)


class LogTests(unittest.TestCase):
    def test_cpp_configuration_comments_overrides_and_declared_large_value(self):
        config = parse_cpp_config("seed -7 # recorded\neval_limit 100000000000\nruns 1\nruns 200\n")
        self.assertEqual(config["eval_limit"], "100000000000")
        self.assertEqual(config["runs"], "200")
        self.assertEqual(cpp_seed_identity(config)["mt19937_seed_uint32"], (1 << 32) - 7)
        self.assertFalse(cpp_seed_identity({"seed": "-1"})["actual_seed_available"])
        with self.assertRaises(ValueError):
            parse_cpp_config("seed")

    def test_python_actual_seed_mapping_and_truncated_log(self):
        result = parse_python_log(python_log())
        self.assertEqual([row["actual_python_seed"] for row in result["runs"]], [124, 125])
        self.assertEqual([row["actual_numpy_seed"] for row in result["runs"]], [124, 125])
        self.assertEqual(result["configuration"]["k"], "4")
        with self.assertRaises(ValueError):
            parse_python_log(python_log(run_count=3))
        with self.assertRaises(ValueError):
            parse_python_log(python_log(seed=(1 << 32) - 1))

    def test_cpp_dat_rejects_partial_and_nonfinite_rows(self):
        self.assertEqual(parse_cpp_dat("# summary\n1 12\n0.9 25\n"), [(1.0, 12), (0.9, 25)])
        for text in ("1", "nan 12", "1 -2"):
            with self.assertRaises(ValueError):
                parse_cpp_dat(text)

    def test_split_config_censor_is_analysis_not_effective_run_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Raw").mkdir()
            (root / "Raw" / "log.txt").write_text(python_log(), encoding="utf-8")
            results = root / "Goldman-modified" / "results"
            results.mkdir(parents=True)
            cfg = ("seed -42\nruns 2\nproblem IsingSpinGlass\nproblem_seed 100\nlength 16\n"
                   "optimizer LambdaLambda\neval_limit 100000000000\n")
            (results / "IsingSpinGlass.0016.LambdaLambda_2.cfg").write_text(cfg, encoding="utf-8")
            (results / "IsingSpinGlass.0016.LambdaLambda_2.dat").write_text(
                "# summary\n1 2100000000\n1 2099999999\n", encoding="utf-8")
            catalog = catalog_results(root)
            self.assertFalse(catalog["errors"])
            batch = catalog["cpp_batches"][0]
            self.assertEqual(batch["analysis_experiment_numbers"], [101, 102])
            self.assertEqual(batch["instance_ids_from_config"], [100, 101])
            self.assertEqual(batch["censored_rows"], 1)
            self.assertTrue(batch["declared_eval_limit_exceeds_int32"])
            self.assertIsNone(batch["effective_eval_limit"])
            self.assertTrue(batch["shared_rng_batch"])


class CompactTests(unittest.TestCase):
    def test_landscape_copy_is_not_a_new_raw_campaign(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "Graphs/Landscape_experiments"
            processed = root / "processed-results"
            nested.mkdir(parents=True)
            processed.mkdir()
            for directory in (nested, processed):
                (directory / "fixture").write_text("Number of runs: 1000\n", encoding="utf-8")
            rows = landscape_catalog(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["recorded_run_count_headers"], [1000])
            self.assertTrue(rows[0]["processed_counterpart_bytes_identical"])
            self.assertIn("UNRESOLVED", rows[0]["raw_seed_mapping"])

    def test_compact_excludes_large_vectors_upstream_paths_and_pdf(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("audit-report.json", "source_manifest.json", "SOURCE_AUDIT_UK.md"):
                (root / name).write_text("{}", encoding="utf-8")
            source = root / "source"
            source.mkdir()
            (source / "paper.pdf").write_bytes(b"%PDF-fixture")
            report = {
                "identity": {"protocol_id": "fixture"}, "availability": {}, "repositories": {},
                "results_catalog": {
                    "python_logs": [{"path": "Raw/result_12:34.txt", "base_seed": 12,
                                     "declared_runs": 2, "reported_evaluations_by_run": [10, 20],
                                     "recorded_generations_by_run": [2, 4]}],
                    "cpp_batches": [{"reported_evaluations_by_run": [30]}],
                },
            }
            write_compact_bundle(root, report)
            compact = root / "compact"
            reduced = json.loads((compact / "audit-report.json").read_text(encoding="utf-8"))
            log = reduced["results_catalog"]["python_logs"][0]
            self.assertNotIn("reported_evaluations_by_run", log)
            self.assertEqual(log["actual_seed_first"], 13)
            self.assertEqual(log["actual_seed_last"], 14)
            self.assertFalse((compact / "paper.pdf").exists())
            manifest = json.loads((compact / "file_manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("file_manifest.json", [row["path"] for row in manifest["files"]])
            self.assertEqual(reduced["full_evidence_reference"]["sha256"], hashlib.sha256(b"{}").hexdigest())


if __name__ == "__main__":
    unittest.main()

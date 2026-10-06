"""CI-only read-only checks of the retained QX study's exact output bytes.

These checks never refit a tree, rerun search, deserialize a model, regenerate
a plot, or perform inference. Denominators come from retained case coverage;
an excluded preparation or missing full winner remains explicitly excluded.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import unittest


ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "candidates/EU26-21/chc_qx_alignment_study"
EVIDENCE = STUDY / "evidence/2026-10-06"
REPORT = EVIDENCE / "report"
RUN = 37443128304
SHA = "405eba461fa3c945f8b132bba1343e38a84df5b1"
REGISTRATION = "b5c46e603838c5fbc7e35b121f757421c222046f"
PROTOCOL_SHA = "c51cbad33d2012b504312e70ff180f7f35cc58ffbd079882acf596b17710de40"
PROTOCOL_ID = "EU26-21-CHCQX-SOURCE-WBA-DIAG-V1"
SEEDS = tuple(range(44001, 44031))
ARMS = ("chc_qx", "lambda_adaptive_qx", "lambda_fixed1_qx")
LOCALITY = {(False, False): "neither_local", (True, False): "approximate_only_false_local",
            (True, True): "both_local", (False, True): "full_only_local"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     allow_nan=False, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_csv(filename):
    path = REPORT / filename
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def pair(row):
    return int(row["seed"]), row["arm"]


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "retained-evidence verification is CI-only")
class RetainedQxEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = read_json(EVIDENCE / "SOURCE.json")
        cls.summary = read_json(REPORT / "summary.json")
        cls.registry = read_json(EVIDENCE / "registry/registry.json")
        cls.cases = read_csv("cases.csv")
        cls.by_pair = {pair(row): row for row in cls.cases}
        cls.available = {key for key, row in cls.by_pair.items() if row["status"] != "NOT_EVALUABLE_SAMPLER"}
        cls.valid = {key for key, row in cls.by_pair.items() if row["status"] == "PASS_VALID_FINAL_MASK"}

    def assert_provenance(self, provenance):
        self.assertEqual(provenance["implementation_sha"], SHA)
        self.assertEqual(provenance["workflow_sha"], SHA)
        self.assertEqual(provenance["protocol_id"], PROTOCOL_ID)
        self.assertEqual(provenance["protocol_sha256"], PROTOCOL_SHA)
        self.assertEqual(provenance["run_id"], RUN)
        self.assertIs(type(provenance["run_attempt"]), int)
        self.assertGreater(provenance["run_attempt"], 0)

    def test_source_inventory_and_original_report_manifest_are_exact(self):
        source = self.source
        self.assertEqual(source["schema"], "eu26-21-qx-retained-source-v1")
        self.assertEqual(source["source_run_id"], RUN)
        self.assertIs(type(source["source_run_attempt"]), int)
        self.assertGreater(source["source_run_attempt"], 0)
        self.assertEqual(source["source_run_conclusion"], "success")
        self.assertEqual(source["implementation_sha"], SHA)
        self.assertEqual(source["protocol_sha256"], PROTOCOL_SHA)
        self.assertEqual(source["content_freeze_commit_sha"], REGISTRATION)
        self.assertEqual(source["historical_noninferiority_status"], "FAIL_NONINFERIORITY_UNCHANGED")
        for flag in ("all_30_case_jobs_completed_before_outcome_inspection",
                     "report_files_preserved_exactly", "original_preparation_bytes_preserved"):
            self.assertIs(source[flag], True)
        self.assertEqual(digest(STUDY / "protocol.json"), PROTOCOL_SHA)
        files = source["files"]
        actual = {path.relative_to(EVIDENCE).as_posix() for path in EVIDENCE.rglob("*") if path.is_file()}
        companions = {"SOURCE.json"}
        if (EVIDENCE / "README_UK.md").is_file():
            companions.add("README_UK.md")
        self.assertEqual(actual, set(files) | companions)
        for relative, identity in files.items():
            with self.subTest(file=relative):
                path = EVIDENCE / relative
                self.assertFalse(path.is_symlink())
                self.assertEqual(identity, {"sha256": digest(path), "bytes": path.stat().st_size})
        self.assertEqual(digest(REPORT / "report-manifest.json"), source["report_manifest_sha256"])
        self.assertRegex(source["report_manifest_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(digest(EVIDENCE / "registry/registry.json"), source["registry_sha256"])
        manifest = read_json(REPORT / "report-manifest.json")
        self.assertEqual(manifest["schema"], "eu26-21-qx-report-manifest-v1")
        self.assertEqual(manifest["source_run_id"], RUN)
        self.assertIs(manifest["manifest_self_hash_excluded"], True)
        self.assert_provenance(manifest["provenance"])
        self.assertEqual(manifest["provenance"]["run_attempt"], source["source_run_attempt"])
        self.assertEqual(manifest["provenance"]["content_freeze_commit_sha"], REGISTRATION)
        self.assertEqual(set(manifest["files"]), {path.name for path in REPORT.iterdir()} - {"report-manifest.json"})
        for filename, identity in manifest["files"].items():
            self.assertEqual(identity, files[f"report/{filename}"])
        self.assertEqual(self.summary["provenance"], manifest["provenance"])
        for filename in ("locality-types.png", "search-and-full-checkpoints.png", "adaptive-lambda.png"):
            self.assertTrue((REPORT / filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_retained_archive_identities_match_the_complete_raw_api_metadata(self):
        metadata = read_json(EVIDENCE / "artifact-api-metadata.json")
        rows = metadata["artifacts"]
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(len(by_id), len(rows))
        source = self.source
        report = by_id[source["report_artifact_id"]]
        self.assertEqual(report["name"], source["report_artifact_name"])
        self.assertEqual(report["name"], f"eu26-21-qx-report-{RUN}-{source['source_run_attempt']}")
        self.assertEqual(report["digest"], "sha256:" + source["report_artifact_sha256"])
        self.assertEqual(report["size_in_bytes"], source["report_artifact_bytes"])
        gates = source["source_gate_artifacts"]
        self.assertEqual({row["phase"] for row in gates}, {"fixture", "smoke"})
        self.assertEqual(len(gates), 2)
        for retained in gates:
            row = by_id[retained["artifact_id"]]
            self.assertEqual(row["name"], retained["artifact_name"])
            self.assertEqual(row["digest"], "sha256:" + retained["archive_sha256"])
            self.assertEqual(row["size_in_bytes"], retained["archive_bytes"])
            self.assertEqual(row["workflow_run"]["id"], RUN)
            self.assertEqual(row["workflow_run"]["head_sha"], SHA)
        self.assertEqual(report["workflow_run"]["id"], RUN)
        self.assertEqual(report["workflow_run"]["head_sha"], SHA)

    def test_preparation_and_case_source_ledgers_preserve_all_thirty_zip_proofs(self):
        for kind, directory in (("preparation", EVIDENCE / "registry"), ("case", EVIDENCE / "report-input")):
            with self.subTest(kind=kind):
                sources_path = directory / f"{kind}-sources.json"
                transport_path = directory / f"{kind}-transport.json"
                raw_path = directory / f"{kind}-api-metadata.json"
                sources, transport, raw = read_json(sources_path), read_json(transport_path), read_json(raw_path)
                self.assertEqual(sources["schema"], "eu26-21-qx-source-ledger-v1")
                self.assertEqual(sources["kind"], kind)
                self.assertEqual(sources["source_run_id"], RUN)
                self.assertEqual(sources["implementation_sha"], SHA)
                self.assertEqual(sources["protocol_id"], PROTOCOL_ID)
                self.assertEqual(sources["protocol_sha256"], PROTOCOL_SHA)
                self.assertEqual(sources["raw_metadata_sha256"], canonical_sha(raw))
                self.assertEqual(sources["raw_metadata_file_sha256"], digest(raw_path))
                self.assertEqual(sources["attempts"], raw["artifacts"])
                self.assertEqual(sources["selection_policy"], "highest_uploaded_attempt_per_seed_without_opening_results")
                selected = sources["artifacts"]
                self.assertEqual(len(selected), 30)
                self.assertEqual(len({row["id"] for row in selected}), 30)
                grouped = defaultdict(list)
                for row in sources["attempts"]:
                    match = re.fullmatch(rf"eu26-21-qx-{kind}-(\d+)-(\d+)-(\d+)", row["name"])
                    self.assertIsNotNone(match)
                    seed, run, attempt = map(int, match.groups())
                    self.assertIn(seed, SEEDS)
                    self.assertEqual(run, RUN)
                    self.assertGreater(attempt, 0)
                    grouped[seed].append((attempt, row))
                self.assertEqual(set(grouped), set(SEEDS))
                self.assertEqual(selected, [max(grouped[seed], key=lambda value: value[0])[1] for seed in SEEDS])
                self.assertIs(transport["complete"], True)
                self.assertEqual(transport["source_run_id"], RUN)
                self.assertEqual(transport["implementation_sha"], SHA)
                verified = {row["id"]: row for row in transport["artifacts"]}
                self.assertEqual(len(verified), 30)
                self.assertEqual(len(transport["artifacts"]), 30)
                self.assertEqual(set(verified), {row["id"] for row in selected})
                for row in selected:
                    self.assertEqual(row["workflow_run"]["head_sha"], SHA)
                    self.assertEqual(row["workflow_run"]["id"], RUN)
                    proof = verified[row["id"]]
                    self.assertEqual(proof["name"], row["name"])
                    self.assertEqual(proof["digest"], row["digest"])
                    self.assertEqual(proof["verified_zip_bytes"], row["size_in_bytes"])
                    self.assertEqual("sha256:" + proof["verified_zip_sha256"], row["digest"])
                    self.assertIs(proof["zip_verified_before_extraction"], True)
                if kind == "preparation":
                    self.assertEqual(self.registry["sources_sha256"], canonical_sha(sources))
                    self.assertEqual(self.registry["transport_sha256"], canonical_sha(transport))
                    self.assertEqual([row["source_artifact_id"] for row in self.registry["cases"]], [row["id"] for row in selected])
                    self.assertEqual([row["source_artifact_name"] for row in self.registry["cases"]], [row["name"] for row in selected])
                    self.assertEqual([row["source_artifact_digest"] for row in self.registry["cases"]], [row["digest"] for row in selected])
                else:
                    self.assertEqual(self.summary["case_sources_sha256"], digest(sources_path))
                    self.assertEqual(self.summary["case_transport_sha256"], digest(transport_path))

    def test_original_preparation_utf8_and_frozen_registry_are_preserved(self):
        registry = self.registry
        self.assertEqual(registry["schema"], "eu26-21-qx-frozen-preparation-registry-v1")
        self.assertEqual(registry["implementation_sha"], SHA)
        self.assertEqual(registry["source_run_id"], RUN)
        self.assertEqual(registry["protocol_id"], PROTOCOL_ID)
        self.assertEqual(registry["protocol_sha256"], PROTOCOL_SHA)
        self.assertIs(registry["all_30_accounted"], True)
        self.assertIs(registry["frozen_before_main_search"], True)
        self.assertEqual([row["seed"] for row in registry["cases"]], list(SEEDS))
        self.assertEqual(self.summary["registry_sha256"], self.source["registry_sha256"])
        packed = REPORT / "frozen-preparations.json.gz"
        self.assertEqual(registry["frozen_preparations"], {"file": packed.name, "sha256": digest(packed), "bytes": packed.stat().st_size})
        self.assertFalse((EVIDENCE / "registry/frozen-preparations.json.gz").exists())
        original = json.loads(gzip.decompress(packed.read_bytes()))
        self.assertEqual(original["schema"], "eu26-21-qx-original-preparations-v1")
        self.assertEqual([row["seed"] for row in original["records"]], list(SEEDS))
        for record, entry in zip(original["records"], registry["cases"]):
            with self.subTest(seed=record["seed"]):
                raw = record["original_utf8"].encode("utf-8")
                self.assertEqual(len(raw), record["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), record["original_sha256"])
                self.assertEqual(entry["preparation"], {"bytes": len(raw), "sha256": record["original_sha256"]})
                preparation = json.loads(raw)
                self.assertEqual(preparation["schema"], "eu26-21-qx-preparation-v1")
                self.assertEqual(preparation["seed"], entry["seed"])
                self.assertEqual(preparation["status"], entry["status"])
                self.assertIn(entry["status"], {"PASS_PREPARATION", "NOT_EVALUABLE_SAMPLER"})
                self.assert_provenance(preparation["provenance"])
                self.assertEqual(entry["source_run_id"], RUN)
                self.assertEqual(preparation["provenance"]["run_attempt"], int(entry["source_artifact_name"].rsplit("-", 1)[1]))
                self.assertIs(preparation["frozen_before_search"], True)
                self.assertIs(preparation["test_arrays_loaded"], False)
                self.assertIs(preparation["training_data"]["test_arrays_loaded"], False)
                masks = preparation["initial_masks"]
                self.assertEqual(len(masks), 50)
                self.assertEqual(preparation["initial_masks_sha256"], canonical_sha(masks))
                self.assertEqual(preparation["initial_scores_sha256"], canonical_sha(preparation["initial_scores"]))
                for mask in masks:
                    self.assertEqual(len(mask), 40)
                    self.assertTrue(all(type(bit) is int and bit in (0, 1) for bit in mask))
                if entry["status"] == "PASS_PREPARATION":
                    sampling = preparation["sampling"]
                    rows = sampling["selected_rows"]
                    self.assertEqual(len(rows), sampling["selected_row_count"])
                    self.assertGreater(len(rows), 5000)
                    self.assertEqual(len(set(rows)), len(rows))
                    self.assertTrue(all(type(index) is int and 0 <= index < preparation["training_data"]["train_partition_rows"] for index in rows))
                    header = f"<i8:({len(rows)},)".encode("ascii")
                    row_bytes = struct.pack(f"<{len(rows)}q", *rows)
                    self.assertEqual(hashlib.sha256(header + row_bytes).hexdigest(), sampling["selected_rows_sha256"])
                    self.assertEqual(len(sampling["selected_raw_row_ids"]), len(rows))
                    self.assertEqual(len(preparation["initial_scores"]), 50)
        feature_map = read_csv("bit-feature-map.csv")
        first = json.loads(original["records"][0]["original_utf8"])
        self.assertEqual(feature_map, [{"bit_index": str(index), "feature": name}
                                      for index, name in enumerate(first["training_data"]["feature_names"])])
        self.assertEqual(len(feature_map), 40)

    def test_all_registered_case_rows_keep_actual_evaluable_denominators(self):
        self.assertEqual(len(self.cases), 90)
        self.assertEqual(len(self.by_pair), 90)
        self.assertEqual(set(self.by_pair), {(seed, arm) for seed in SEEDS for arm in ARMS})
        summary = self.summary
        self.assertEqual(summary["schema"], "eu26-21-qx-descriptive-summary-v1")
        self.assertEqual(summary["protocol_id"], PROTOCOL_ID)
        self.assertEqual(summary["source_run_id"], RUN)
        self.assertEqual(summary["cases_accounted"], 30)
        self.assertEqual(set(summary["arms"]), set(ARMS))
        self.assertIs(summary["hypothesis_tests"], False)
        self.assertEqual(summary["claims"], {"speed_superiority": False, "escape_advantage": False,
                                             "global_optimality": False, "historical_results_reinterpreted": False})
        for entry in self.registry["cases"]:
            expected = entry["status"] == "PASS_PREPARATION"
            for arm in ARMS:
                self.assertEqual((entry["seed"], arm) in self.available, expected)
        for key, row in self.by_pair.items():
            self.assertIn(row["status"], {"NOT_EVALUABLE_SAMPLER", "NOT_EVALUABLE_NO_FULL_WINNER", "PASS_VALID_FINAL_MASK"})
            if key not in self.available:
                self.assertEqual(row.get("test_wba", ""), "")
                self.assertEqual(row.get("mask", ""), "")
                continue
            self.assertIn(row["locality"], set(LOCALITY.values()))
            self.assertEqual(int(row["diagnostic_calls"]), 82)
            self.assertEqual(int(row["active_logical_calls"]), int(row["active_physical_calls"]) + 50)
            self.assertIn(row["snapshot_reason"], {"first_whole_chunk_without_active_gain", "stagnation_not_observed"})
            self.assertIn(row["stop_reason"], {"full_no_change", "censored_safety_cap", "no_full_winner"})
            self.assertGreaterEqual(int(row["chunks"]), 1)
            self.assertLessEqual(int(row["chunks"]), 20)
            if key in self.valid:
                self.assertEqual(len(row["mask"]), 40)
                self.assertLessEqual(set(row["mask"]), {"0", "1"})
                self.assertEqual(int(row["features"]), row["mask"].count("1"))
                self.assertGreater(int(row["features"]), 0)
                self.assertEqual(int(row["test_evaluations"]), 1)
                self.assertTrue(0 <= float(row["test_wba"]) <= 1)
                self.assertTrue(0 < float(row["full_validation_wba"]) <= 1)
            else:
                self.assertEqual(row["mask"], "")
                self.assertEqual(row["test_wba"], "")
                self.assertEqual(int(row["test_evaluations"]), 0)
        for arm in ARMS:
            available = [row for key, row in self.by_pair.items() if key in self.available and key[1] == arm]
            valid = [row for key, row in self.by_pair.items() if key in self.valid and key[1] == arm]
            item = summary["arms"][arm]
            self.assertEqual(item["registered_cases"], 30)
            self.assertEqual(item["diagnostic_cases"], len(available))
            self.assertEqual(item["valid_test_cases"], len(valid))
            self.assertEqual(item["not_evaluable_cases"], 30 - len(valid))
            self.assertEqual(item["sampler_not_evaluable_cases"], 30 - len(available))
            self.assertEqual(item["no_full_winner_cases"], len(available) - len(valid))
            self.assertEqual(item["diagnostic_calls"], 82 * len(available))
            self.assertEqual(item["test_evaluations"], len(valid))
            self.assertEqual(item["observed_stagnation_snapshots"],
                             sum(row["snapshot_reason"] == "first_whole_chunk_without_active_gain" for row in available))
            self.assertEqual(item["stop_reasons"], dict(Counter(row["stop_reason"] for row in available)))
            for name in ("active_logical_calls", "active_physical_calls", "full_calls"):
                self.assertEqual(item[name], sum(int(row[name]) for row in available))
            if not valid:
                self.assertIsNone(item["median_test_wba"])
                self.assertIsNone(item["feature_count_range"])

    def test_all_ordered_one_bit_rows_reconstruct_locality_and_strict_plateau_counts(self):
        groups = defaultdict(list)
        for row in read_csv("one-bit-certificates.csv"):
            groups[(int(row["seed"]), row["arm"], row["scope"])].append(row)
        self.assertEqual(set(groups), {(seed, arm, scope) for seed, arm in self.available for scope in ("approximate", "full")})
        classifications, strict, plateau = defaultdict(Counter), Counter(), Counter()
        known_scores = {}
        for seed, arm in self.available:
            local = {}
            centers = []
            for scope in ("approximate", "full"):
                rows = groups[(seed, arm, scope)]
                self.assertEqual(len(rows), 41)
                self.assertEqual([int(row["call"]) for row in rows], list(range(1, 42)))
                self.assertEqual([row["bit"] for row in rows], [""] + [str(index) for index in range(40)])
                center_mask, center_wba = rows[0]["mask"], float(rows[0]["wba"])
                centers.append(center_mask)
                self.assertEqual(len(center_mask), 40)
                self.assertLessEqual(set(center_mask), {"0", "1"})
                relations = []
                for bit, row in enumerate(rows[1:]):
                    expected = center_mask[:bit] + str(1 - int(center_mask[bit])) + center_mask[bit + 1:]
                    self.assertEqual(row["mask"], expected)
                    wba = float(row["wba"])
                    self.assertTrue(math.isfinite(wba) and 0 <= wba <= 1)
                    relation = "higher" if wba > center_wba else "equal" if wba == center_wba else "lower"
                    self.assertEqual(row["relation"], relation)
                    self.assertEqual(float(row["difference_from_center"]), wba - center_wba)
                    relations.append(relation)
                self.assertTrue(math.isfinite(center_wba) and 0 <= center_wba <= 1)
                for row in rows:
                    key, wba = (seed, scope, row["mask"]), float(row["wba"])
                    if key in known_scores:
                        self.assertEqual(wba, known_scores[key])
                    known_scores[key] = wba
                local[scope] = "higher" not in relations
                strict[(arm, scope)] += local[scope] and "equal" not in relations
                plateau[(arm, scope)] += local[scope] and "equal" in relations
            self.assertEqual(centers[0], centers[1])
            classification = LOCALITY[(local["approximate"], local["full"])]
            self.assertEqual(self.by_pair[(seed, arm)]["locality"], classification)
            classifications[arm][classification] += 1
        for arm in ARMS:
            item = self.summary["arms"][arm]
            self.assertEqual(item["classifications"], dict(classifications[arm]))
            for scope in ("approximate", "full"):
                self.assertEqual(item[f"strict_{scope}_maxima"], strict[(arm, scope)])
                self.assertEqual(item[f"plateau_{scope}_maxima"], plateau[(arm, scope)])

    def test_checkpoint_tables_end_at_each_cases_actual_completed_chunk(self):
        groups = defaultdict(list)
        for row in read_csv("checkpoints.csv"):
            groups[pair(row)].append(row)
        self.assertEqual(set(groups), self.available)
        for key, rows in groups.items():
            case = self.by_pair[key]
            self.assertEqual(len(rows), int(case["chunks"]))
            previous_active, previous_full = 50, 0
            for chunk, row in enumerate(rows, 1):
                self.assertEqual(int(row["chunk"]), chunk)
                self.assertEqual(int(row["generation"]), chunk * 10)
                active, full = int(row["active_logical_calls"]), int(row["full_calls"])
                self.assertGreaterEqual(active, previous_active)
                self.assertGreaterEqual(full, previous_full)
                self.assertEqual(int(row["active_physical_calls"]), active - 50)
                self.assertEqual(int(row["new_full_calls"]), full - previous_full)
                self.assertEqual(int(row["checkpoint_visits"]), chunk * (50 if key[1] == "chc_qx" else 1))
                previous_active, previous_full = active, full
            self.assertEqual(previous_active, int(case["active_logical_calls"]))
            self.assertEqual(previous_full, int(case["full_calls"]))
            if case["stop_reason"] == "full_no_change":
                self.assertEqual(int(rows[-1]["no_change"]), 2)
            if case["stop_reason"] == "censored_safety_cap":
                self.assertEqual(len(rows), 20)
                self.assertLess(int(rows[-1]["no_change"]), 2)

    def test_class_tables_only_cover_valid_final_masks_and_keep_weighted_wba(self):
        groups = defaultdict(list)
        for row in read_csv("class-metrics.csv"):
            groups[(int(row["seed"]), row["arm"], row["scale"])].append(row)
        self.assertEqual(set(groups), {(seed, arm, scale) for seed, arm in self.valid for scale in ("weighted", "unweighted")})
        for (seed, arm, scale), rows in groups.items():
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["class"] for row in rows}, {"0", "1"})
            for row in rows:
                for name in ("precision", "recall", "f1"):
                    self.assertTrue(0 <= float(row[name]) <= 1)
                self.assertGreaterEqual(float(row["support"]), 0)
                precision, recall = float(row["precision"]), float(row["recall"])
                expected = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
                self.assertAlmostEqual(float(row["f1"]), expected, places=12)
            if scale == "unweighted":
                self.assertEqual(sum(float(row["support"]) for row in rows), 99762)
                self.assertTrue(all(float(row["support"]).is_integer() for row in rows))
            else:
                self.assertAlmostEqual(sum(float(row["recall"]) for row in rows) / 2,
                                       float(self.by_pair[(seed, arm)]["test_wba"]), places=12)

    def test_both_source_gates_are_bound_to_original_payloads_without_numeric_reinterpretation(self):
        fixture = read_json(EVIDENCE / "source-gates/fixture/source-gate-fixture.json")
        smoke = read_json(EVIDENCE / "source-gates/smoke/source-gate-smoke.json")
        self.assertEqual(fixture["schema"], "eu26-21-chc-qx-source-fixture-gate-v1")
        self.assertEqual(fixture["status"], "PASS_SOURCE_CONTROLLER_EQUIVALENCE")
        self.assertIs(fixture["classifier_training"], False)
        self.assertIs(fixture["historical_numeric_reproduction"], False)
        self.assertEqual(smoke["schema"], "eu26-21-chc-qx-source-integration-gate-v1")
        self.assertEqual(smoke["status"], "PASS_SOURCE_INTEGRATION_SMOKE")
        self.assertIs(smoke["historical_numeric_gate_changed"], False)
        self.assertIs(smoke["source_profile_known_limitations_retained"], True)
        self.assertEqual(smoke["result_sha256"], digest(EVIDENCE / "source-gates/smoke/source-integration-seed1.json"))
        self.assertEqual(smoke["environment_sha256"], canonical_sha(smoke["environment"]))
        self.assertTrue((EVIDENCE / "source-gates/smoke/source-integration-seed1.log").is_file())
        archives = {row["phase"]: row for row in self.source["source_gate_artifacts"]}
        for phase, gate in (("fixture", fixture), ("smoke", smoke)):
            self.assert_provenance(gate["provenance"])
            self.assertEqual(gate["provenance"]["registration_sha"], REGISTRATION)
            self.assertEqual(gate["provenance"]["upstream_sha"], "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6")
            self.assertEqual(archives[phase]["artifact_name"],
                             f"eu26-21-qx-source-{phase}-{RUN}-{gate['provenance']['run_attempt']}")


if __name__ == "__main__":
    unittest.main()

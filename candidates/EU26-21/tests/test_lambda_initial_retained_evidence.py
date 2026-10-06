"""Check frozen CI results without fitting models or repeating inference.

Executed by GitHub Actions only. The evidence SHA is the scientific launch
commit, not the later commit retaining its unchanged output bytes.
"""
import csv
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "candidates/EU26-21/lambda_initial_study"
EVIDENCE = STUDY / "evidence/2026-10-04"
REPORT = EVIDENCE / "report"
SHA = "ce7b9a24782ae3f97b0b3cb954eb7d8b989bfe32"
PROTOCOL_SHA = "8f96fbf91ae5e92b90409c3ba0492da2d13551bca0d49e273d299dd4ac1453b4"
MANIFEST_SHA = "ef67abc75e272197865410e98abf3b627ec2769c7af8fe058248e03eec197530"
RUN = 37218359309
SEEDS = set(range(43001, 43031))
ARMS = {"chc_harmonized", *(f"lambda_initial_{n}" for n in (1, 5, 10, 20, 40))}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class RetainedInitialLambdaEvidenceTests(unittest.TestCase):
    def test_exact_manifest_and_report_bytes(self):
        manifest_path = REPORT / "report-manifest.json"
        self.assertEqual(hashlib.sha256(manifest_path.read_bytes()).hexdigest(), MANIFEST_SHA)
        manifest = read_json(manifest_path)
        self.assertEqual(manifest["implementation_sha"], SHA)
        self.assertEqual(manifest["protocol_sha256"], PROTOCOL_SHA)
        self.assertEqual(manifest["source_run_id"], RUN)
        self.assertEqual(len(manifest["files"]), 11)
        self.assertEqual({p.name for p in REPORT.iterdir()},
                         set(manifest["files"]) | {"report-manifest.json"})
        for name, expected in manifest["files"].items():
            with self.subTest(name=name):
                raw = (REPORT / name).read_bytes()
                self.assertEqual(len(raw), expected["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["sha256"])

    def test_registration_and_transport_provenance(self):
        source = read_json(EVIDENCE / "SOURCE.json")
        self.assertEqual(source["implementation_sha"], SHA)
        self.assertEqual(source["source_run_id"], RUN)
        self.assertEqual(source["source_run_attempt"], 1)
        self.assertEqual(source["source_run_conclusion"], "success")
        self.assertEqual(source["report_artifact_id"], 11309451976)
        self.assertEqual(source["report_manifest_sha256"], MANIFEST_SHA)
        self.assertEqual(source["protocol_sha256"], PROTOCOL_SHA)
        self.assertEqual(hashlib.sha256((STUDY / "protocol.json").read_bytes()).hexdigest(),
                         PROTOCOL_SHA)
        raw_metadata = (EVIDENCE / "case-attempt-ledger.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw_metadata).hexdigest(),
                         source["case_attempt_ledger_sha256"])
        ledger = read_json(REPORT / "source-ledger.json")
        transport = read_json(REPORT / "transport-ledger.json")
        self.assertEqual(ledger["raw_metadata_file_sha256"], source["case_attempt_ledger_sha256"])
        self.assertEqual(len(ledger["artifacts"]), 30)
        self.assertEqual(len(ledger["attempts"]), 30)
        self.assertEqual(transport["source_run_id"], RUN)
        self.assertEqual(transport["implementation_sha"], SHA)
        self.assertIs(transport["complete"], True)
        selected = {row["id"]: row for row in ledger["artifacts"]}
        downloaded = {row["id"]: row for row in transport["artifacts"]}
        self.assertEqual(len(selected), 30)
        self.assertEqual(set(selected), set(downloaded))
        self.assertEqual({row["name"] for row in selected.values()},
                         {f"eu26-21-lambda-case-{seed}-{RUN}-1" for seed in SEEDS})
        for identity, row in selected.items():
            with self.subTest(identity=identity):
                self.assertEqual(row["workflow_run"]["head_sha"], SHA)
                self.assertEqual(row["workflow_run"]["id"], RUN)
                verified = downloaded[identity]
                self.assertEqual(verified["verified_zip_bytes"], row["size_in_bytes"])
                self.assertEqual("sha256:" + verified["verified_zip_sha256"], row["digest"])
                self.assertIs(verified["zip_verified_before_extraction"], True)

    def test_all_terminal_masks_and_call_counts(self):
        with (REPORT / "comparison.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 180)
        self.assertEqual({(int(r["seed"]), r["arm"]) for r in rows},
                         {(seed, arm) for seed in SEEDS for arm in ARMS})
        for row in rows:
            with self.subTest(seed=row["seed"], arm=row["arm"]):
                mask = row["mask"]
                self.assertEqual(len(mask), 40)
                self.assertLessEqual(set(mask), {"0", "1"})
                self.assertEqual(int(row["selected_features"]), mask.count("1"))
                self.assertEqual(int(row["logical_calls"]), 400)
                self.assertEqual(int(row["physical_postinitial_calls"]), 350)
                if row["arm"] == "chc_harmonized":
                    self.assertEqual(row["initial_lambda"], "")
                else:
                    self.assertEqual(int(row["initial_lambda"]), int(row["arm"].rsplit("_", 1)[1]))
        summary = read_json(REPORT / "summary.json")
        self.assertEqual(summary["case_count"], 30)
        self.assertEqual(summary["arm_count"], 6)
        self.assertEqual(summary["counts"], {"logical_validation_calls": 72000,
                                           "physical_validation_calls": 64500,
                                           "test_evaluations": 180})

    def test_complete_trajectories_have_the_same_initialization(self):
        trajectories = {}
        with (REPORT / "trajectories.csv").open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                key = (int(row["seed"]), row["arm"])
                points = trajectories.setdefault(key, [])
                self.assertEqual(int(row["call"]), len(points) + 1)
                value = float(row["best_so_far_validation_wba"])
                self.assertGreaterEqual(value, 0)
                self.assertLessEqual(value, 1)
                if points:
                    self.assertGreaterEqual(value, points[-1])
                points.append(value)
        self.assertEqual(set(trajectories), {(seed, arm) for seed in SEEDS for arm in ARMS})
        for (seed, arm), points in trajectories.items():
            with self.subTest(seed=seed, arm=arm):
                self.assertEqual(len(points), 400)
                self.assertEqual(points[:50], trajectories[(seed, "chc_harmonized")][:50])

    def test_recorded_inference_matches_registered_families_and_gates(self):
        summary = read_json(REPORT / "summary.json")
        analysis = summary["analysis"]
        primary, secondary = analysis["primary_contrasts"], analysis["secondary_contrasts"]
        self.assertEqual(len(primary), 4)
        self.assertEqual(len(secondary), 10)
        self.assertIs(analysis["global_14_contrast_95_coverage_claim"], False)
        self.assertIs(analysis["pooled_confusion_matrices"], False)
        for index, contrast in enumerate(primary + secondary):
            with self.subTest(index=index):
                self.assertEqual(contrast["analysis_seed"], 43031 + index)
                self.assertEqual(contrast["confidence_level"], .9875 if index < 4 else .995)
                self.assertEqual(contrast["bootstrap_resamples"], 50000)
                self.assertEqual(contrast["case_count"], 30)
                self.assertEqual(contrast["unit"], "whole_seed_case")
                self.assertIsNone(contrast["unavailable_reason"])
                lower, upper = contrast["interval"]
                self.assertLess(lower, upper)
                if index < 4:
                    self.assertEqual(contrast["reference"], "lambda_initial_1")
                    self.assertEqual(contrast["advantage"], lower > 0)
                    self.assertEqual(contrast["degradation"], upper < 0)
                else:
                    self.assertEqual(contrast["reference"], "chc_harmonized")
                    margin = -.001 if contrast["endpoint"] == "test_wba" else 0
                    self.assertEqual(contrast["gate_passed"], lower > margin)
                    if contrast["endpoint"] == "test_wba":
                        self.assertLess(lower, 0)
                        self.assertGreater(upper, 0)
        self.assertFalse(any(row["advantage"] for row in primary))
        self.assertEqual([row["arm"] for row in primary if row["degradation"]],
                         ["lambda_initial_40"])
        self.assertEqual({arm for arm, passed in analysis["joint_search_advantage"].items() if passed},
                         {"lambda_initial_5", "lambda_initial_20"})
        for arm, joint in analysis["joint_search_advantage"].items():
            self.assertEqual(joint, all(row["gate_passed"] for row in secondary if row["arm"] == arm))
        self.assertEqual(summary["historical_noninferiority_status"],
                         "FAIL_NONINFERIORITY_UNCHANGED")


if __name__ == "__main__":
    unittest.main()

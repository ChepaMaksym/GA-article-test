"""CI-only validation of original retained report bytes and all lambda events."""
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lambda_response_study import artifacts
from lambda_response_study.contract import PROTOCOL_ID,PROTOCOL_SHA256
from lambda_response_study.oracle import expected_lambda

ROOT=Path(__file__).resolve().parents[1]/"lambda_response_study/evidence/2026-10-06"

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def table(name):
    with (ROOT/"report"/name).open(encoding="utf-8",newline="") as stream:
        return list(csv.DictReader(stream))

class RetainedLambdaResponseTests(unittest.TestCase):
    def test_source_report_manifest_and_exact_members(self):
        source=read(ROOT/"SOURCE.json")
        self.assertEqual(source["protocol_id"],PROTOCOL_ID)
        self.assertEqual(source["protocol_sha256"],PROTOCOL_SHA256)
        self.assertEqual(source["source_run_id"],37466751636)
        self.assertEqual(source["source_run_attempt"],1)
        self.assertEqual(source["report_artifact"]["digest"],"sha256:"+source["verified_report_zip"]["sha256"])
        path=ROOT/"report/report-manifest.json"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),source["report_manifest_sha256"])
        manifest=read(path)
        self.assertEqual(manifest["provenance"]["implementation_sha"],source["scientific_sha"])
        self.assertEqual(manifest["source_run_id"],source["source_run_id"])
        self.assertEqual({p.name for p in path.parent.iterdir()},set(manifest["files"])|{"report-manifest.json"})
        for name, identity in manifest["files"].items():
            data=(path.parent/name).read_bytes()
            self.assertEqual(len(data),identity["bytes"],name)
            self.assertEqual(hashlib.sha256(data).hexdigest(),identity["sha256"],name)

    def test_canonical_registry_original_preparations_and_transport(self):
        source=read(ROOT/"SOURCE.json")
        registry_path=ROOT/source["canonical_registry"]
        self.assertEqual(hashlib.sha256(registry_path.read_bytes()).hexdigest(),source["registry_sha256"])
        self.assertFalse((ROOT/source["excluded_duplicate"]).exists())
        registry=read(registry_path)
        rows=artifacts.validate_registry(registry,expected_sha=source["scientific_sha"])
        self.assertEqual(set(rows),set(range(45001,45031)))
        for prefix,kind in (("registry/preparation","preparation"),("report-input/case","case")):
            selected=read(ROOT/(prefix+"-sources.json"))
            ledger=read(ROOT/(prefix+"-transport.json"))
            artifacts.validate_sources(selected,kind=kind,expected_sha=source["scientific_sha"])
            artifacts.validate_transport(selected,ledger)
            self.assertEqual(selected["source_run_id"],source["source_run_id"])

    def test_complete_cases_generations_and_no_statistical_claim(self):
        cases=table("cases.csv")
        events=table("events.csv")
        self.assertEqual(len(cases),120)
        self.assertEqual(len(events),2400)
        expected={(seed,problem,arm) for seed in range(45001,45031)
                  for problem in ("onemax","census") for arm in ("adaptive","fixed10")}
        self.assertEqual({(int(r["seed"]),r["problem"],r["arm"]) for r in cases},expected)
        self.assertTrue(all(r["status"]=="PASS_CASE" for r in cases))
        summary=read(ROOT/"report/summary.json")
        self.assertEqual(summary["cases_accounted"],30)
        self.assertEqual(summary["test_evaluations"],60)
        self.assertEqual(summary["preparation_calls"],1200)
        self.assertFalse(summary["hypothesis_tests"])
        self.assertFalse(summary["bootstrap"])
        self.assertFalse(summary["equal_objective_budget"])
        self.assertFalse(any(summary["claims"].values()))
        self.assertEqual(summary["example_seed"],45001)
        self.assertEqual(len(list((ROOT/"report").glob("*.png"))),8)

    def test_independent_formula_and_every_generation_budget_in_csv(self):
        groups={}
        for row in table("events.csv"):
            key=(int(row["seed"]),row["problem"],row["arm"])
            groups.setdefault(key,[]).append(row)
        for key,rows in groups.items():
            self.assertEqual([int(r["generation"]) for r in rows],list(range(1,21)))
            call,lam=0,10.0
            for row in rows:
                before=float(row["lambda_before"])
                candidate=float(row["candidate_score"])
                parent=float(row["parent_score_before"])
                success=candidate>parent
                expected=expected_lambda(before,strict_success=success,arm=key[2])
                applied=float(row["applied_lambda_after"])
                self.assertAlmostEqual(before,lam)
                self.assertTrue(math.isclose(applied,expected,rel_tol=1e-12,abs_tol=1e-12))
                self.assertEqual(row["strict_success"],str(success))
                self.assertEqual(int(row["calls_before"]),call)
                self.assertEqual(int(row["offspring_count"]),math.floor(before+.5))
                call+=2*int(row["offspring_count"])
                self.assertEqual(int(row["calls_after"]),call)
                self.assertAlmostEqual(float(row["score_delta_pp"]),100*(candidate-parent))
                self.assertAlmostEqual(float(row["lambda_delta_percent"]),100*(applied/before-1))
                lam=applied
            self.assertEqual(call,400 if key[2]=="fixed10" else call)
            self.assertLessEqual(call,1600)

    def test_bit_mapping_preparation_and_adverse_candidates_retained(self):
        from corrected_applied.data_protocol import TRANSFORMED_FEATURE_NAMES
        mapping=table("bit-feature-map.csv")
        self.assertEqual([r["feature_name"] for r in mapping],list(TRANSFORMED_FEATURE_NAMES))
        self.assertNotIn("instance_weight",[r["feature_name"] for r in mapping])
        self.assertEqual(len(table("preparation-scores.csv")),1200)
        rows=table("example-raw-evaluations.csv")
        self.assertEqual({int(r["seed"]) for r in rows},{45001})
        self.assertTrue(any(r["phase"]=="mutation" for r in rows))
        self.assertTrue(any(float(r["score"])<float(r["best_so_far_score"]) for r in rows))
        events=table("events.csv")
        self.assertTrue(any(r["outcome"]=="rejection" for r in events))
        self.assertTrue(any(r["outcome"]=="tie" for r in events))
        for r in rows:
            if r["kind"]=="empty_penalty":
                self.assertEqual(float(r["score"]),0)

if __name__=="__main__":
    unittest.main()

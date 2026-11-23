"""CI regression tests for shard, provenance, and resource decisions."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from .continuation import bound, case_jobs_missing_evidence, checked_compact
from .runner import SCHEMA


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.limits = {"runner_minutes":1600, "artifact_bytes":20*1024**3}
        self.probe = {"status":"FOUR_OLD_CASES_VERIFIED", "holdout_search_runs":0,
                      "forecast":{"physical_main_runs":1200, "slowest_case_seconds":30, "largest_case_bytes":9_000_000}}
        self.origin = {"run_id":202, "commit":"b"*40}
        self.binding = {"source_manifest_sha256":"5"*64,"inputs_manifest_sha256":"4"*64,"authorization_id":"study"}

    def fixture(self, root):
        (root/"records").mkdir()
        (root/"failures").mkdir()
        for case_id, producer in (("a",99),("b",202)):
            (root/"records"/(case_id+".json")).write_text(json.dumps({
                "schema":SCHEMA,"status":"VERIFIED","case_id":case_id,"workflow_run_id":str(producer),
                "workflow_commit":"b"*40,**self.binding}),encoding="utf-8")
        (root/"failures/c.json").write_text(json.dumps({
            "case_id":"c","workflow_run_id":"202","status":"FAILED_OR_INTERRUPTED"}),encoding="utf-8")
        (root/"shard.json").write_text(json.dumps({"schema":"independent-validation100-shard-v1",
            "shard_id":"005","requested":["a","b","c"],"new":["b"],"reused":["a"],"failures":["c"],
            "workflow_run_id":"202","workflow_commit":"b"*40,"status":"INCOMPLETE",**self.binding}),encoding="utf-8")

    def inspect(self, root, allowed=(99,202)):
        return checked_compact(root,["a","b","c"],5,self.binding,self.origin,allowed)

    def test_partial_and_transitively_reused_cases(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            self.fixture(root)
            self.assertEqual(set(self.inspect(root)),{"a","b"})
            with self.assertRaises(ValueError):
                self.inspect(root,(202,))

    def test_mixed_input_and_extra_case_are_rejected(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            self.fixture(root)
            path=root/"records/a.json"
            original=path.read_text(encoding="utf-8")
            row=json.loads(original)
            row["inputs_manifest_sha256"]="0"*64
            path.write_text(json.dumps(row),encoding="utf-8")
            with self.assertRaises(ValueError):
                self.inspect(root)
            path.write_text(original,encoding="utf-8")
            (root/"records/unregistered.json").write_text("{}")
            with self.assertRaises(ValueError):
                self.inspect(root)

    def test_exact_coverage_and_lost_failure_receipt(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            self.fixture(root)
            (root/"failures/c.json").unlink()
            with self.assertRaises(ValueError):
                self.inspect(root)

    def test_verified_rows_survive_interruption_before_shard_receipt(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            self.fixture(root)
            (root/"shard.json").unlink()
            self.assertEqual(set(self.inspect(root)),{"a","b"})

    def test_missing_artifact_after_possible_search(self):
        job={"name":"cases (5)","conclusion":"failure","steps":[{"name":"Execute cases","conclusion":"success"}]}
        with self.assertRaises(ValueError):
            case_jobs_missing_evidence([job],{})
        job["steps"][0]["conclusion"]="skipped"
        case_jobs_missing_evidence([job],{})
        case_jobs_missing_evidence([dict(name="prepare",conclusion="failure")],{})

    def test_forecast_and_hard_concurrent_wave_limits(self):
        result=bound(self.limits,self.probe,0,0,200,1200)
        self.assertGreater(result["worst_runner_minutes"],result["forecast_runner_minutes"])
        self.assertLess(result["worst_additional_artifact_bytes"],self.limits["artifact_bytes"])
        with self.assertRaises(ValueError):
            bound(self.limits,self.probe,200,0,200,1200)
        with self.assertRaises(ValueError):
            bound(self.limits,self.probe,0,2*1024**3,200,1200)
        self.probe["forecast"]["slowest_case_seconds"]=180
        with self.assertRaises(ValueError):
            bound(self.limits,self.probe,0,0,200,1200)

    def test_zero_missing_can_resume_analysis_only(self):
        result=bound(self.limits,self.probe,1470,14*1024**3,0,0)
        self.assertEqual(result["forecast_runner_minutes"],30)


if __name__ == "__main__":
    unittest.main()

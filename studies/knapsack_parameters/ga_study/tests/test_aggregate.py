"""CI-only adversarial evidence fixtures; no main result is fabricated by them."""

import copy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from studies.knapsack_parameters.ga_study.aggregate import (
    collect_verified_batches, expected_jobs, validate_sources, validate_summary,
)
from studies.knapsack_parameters.ga_study.contract import (
    DATA_SHA, PROTOCOL_ID, PROTOCOL_SHA, REGISTRATION_SHA, REGISTRY_SHA,
    file_identity, write_file_manifest, write_json,
)
from studies.knapsack_parameters.ga_study.engine import configurations


class SourceRegistryTests(unittest.TestCase):
    def setUp(self):
        self.cases={f"{c}-s{i:03d}":{"status":"ADMITTED_STRICT_LOCAL" if c=="UC" else "EXCLUDED_GLOBAL_CENTER"}
                    for c in ("UC","WC","SC") for i in range(10)}
        self.jobs=expected_jobs(self.cases)
        self.sha="a"*40
        self.sources={"schema_version":"ga-knapsack-sources-v1","phase":"main",
                      "implementation_commit_sha":self.sha,"sources":[
                          {"job_key":key,"instance_id":job["instance_id"],"seed_first":job["seed_first"],
                           "seed_last":job["seed_last"],"run_id":10,"run_attempt":1,"artifact_id":100+i,
                           "artifact_name":f"source-{i}","zip_sha256":"b"*64,"zip_bytes":123,
                           "job_manifest_sha256":"c"*64}
                          for i,(key,job) in enumerate(self.jobs.items())]}

    def test_all_ninety_matrix_sources_required(self):
        self.assertEqual(len(validate_sources(self.sources,self.jobs,self.sha,"main")),90)
        self.sources["sources"].pop()
        with self.assertRaisesRegex(ValueError,"missing or extra"):
            validate_sources(self.sources,self.jobs,self.sha,"main")

    def test_duplicate_artifact_rejected(self):
        self.sources["sources"][1]["artifact_id"]=self.sources["sources"][0]["artifact_id"]
        with self.assertRaisesRegex(ValueError,"artifact reused"):
            validate_sources(self.sources,self.jobs,self.sha,"main")

    def test_mixed_sha_rejected(self):
        self.sources["implementation_commit_sha"]="d"*40
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):
            validate_sources(self.sources,self.jobs,self.sha,"main")

    def test_duplicate_job_not_a_replacement_for_missing_job(self):
        self.sources["sources"][1]=copy.deepcopy(self.sources["sources"][0])
        with self.assertRaisesRegex(ValueError,"duplicate source job"):
            validate_sources(self.sources,self.jobs,self.sha,"main")


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.instance=SimpleNamespace(instance_id="UC-s000",n=3,capacity=10,weights=(6,5,5),
                                      profits=(10,8,8),source_path="fixture.kp")
        self.case={"status":"ADMITTED_STRICT_LOCAL","payload":{
            "exact":{"confirmed_optimum":16},"certificate":{"center":{"profit":10}},
            "source_identity":{"sha256":"d"*64}}}
        self.identity={"protocol_id":PROTOCOL_ID,"protocol_sha256":PROTOCOL_SHA,
                       "registration_commit_sha":REGISTRATION_SHA,"implementation_commit_sha":"a"*40,
                       "data_manifest_sha256":DATA_SHA,"registry_sha256":REGISTRY_SHA,
                       "runtime_lock_sha256":"b"*64,"banks_manifest_sha256":"c"*64}
        self.job={"seed_first":51001,"seed_last":51010,"profiles":("random","local")}
        config=configurations()[0]
        core={"best_mask":"011","best_profit":16,"best_weight":10,"best_request":5000,
              "duplicate_count":7,"invalid_request_count":12,"complete_generations":554,
              "terminal_partial":True,"logical_requests":5000,"physical_evaluations":4990,
              "escape_event":True,"first_escape_request":5000,"censored":False}
        self.row={**self.identity,**config.as_dict(),**core,"instance_id":"UC-s000", "repeat_seed":51001,
                  "start_profile":"local","status":"COMPLETE","verified":True,
                  "source_commit_sha":"c5bea0df8169749caaba5ce7dfcf21437aa1ca5c",
                  "source_path":"fixture.kp","source_sha256":"d"*64,"capacity":10,"bit_item_map":[1,2,3],
                  "run_directory":"runs/51001/local/m0p5-c0-n10",
                  "verification":{**core,"status":"PASS_REPLAY","exact_requests_verified":5000,
                                  "rng_and_operator_replay_verified":True}}

    def test_escape_at_last_request_is_not_censoring(self):
        result=validate_summary(self.row,self.instance,self.case,self.job,self.identity)
        self.assertEqual(result[:3],("UC-s000","local",51001))

    def test_nonevent_retained_with_null_first_escape(self):
        edits={"best_mask":"100","best_profit":10,"best_weight":6,"best_request":1,
               "escape_event":False,"first_escape_request":None,"censored":True}
        self.row.update(edits)
        self.row["verification"].update(edits)
        validate_summary(self.row,self.instance,self.case,self.job,self.identity)

    def test_null_censoring_not_accepted_for_local_run(self):
        self.row["censored"]=None
        self.row["verification"]["censored"]=None
        with self.assertRaisesRegex(ValueError,"censoring"):
            validate_summary(self.row,self.instance,self.case,self.job,self.identity)

    def test_corrupt_witness_rejected_independently(self):
        self.row["best_weight"]=9
        self.row["verification"]["best_weight"]=9
        with self.assertRaisesRegex(ValueError,"best-mask witness"):
            validate_summary(self.row,self.instance,self.case,self.job,self.identity)

    def test_unverified_requests_rejected(self):
        self.row["verification"]["exact_requests_verified"]=4999
        with self.assertRaisesRegex(ValueError,"full replay"):
            validate_summary(self.row,self.instance,self.case,self.job,self.identity)

    def test_last_partial_generation_flag_required(self):
        self.row["terminal_partial"]=False
        self.row["verification"]["terminal_partial"]=False
        with self.assertRaisesRegex(ValueError,"last-generation"):
            validate_summary(self.row,self.instance,self.case,self.job,self.identity)


class BatchIntegrityTests(unittest.TestCase):
    def test_corrupt_or_extra_internal_file_rejected(self):
        # Small static fixtures test byte inventories without executing a GA.
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/"payload.txt").write_bytes(b"original")
            write_file_manifest(root)
            from studies.knapsack_parameters.ga_study.contract import verify_file_manifest
            verify_file_manifest(root)
            (root/"payload.txt").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError,"hash/length mismatch"):
                verify_file_manifest(root)
            (root/"payload.txt").write_bytes(b"original")
            (root/"extra.txt").write_bytes(b"unregistered")
            with self.assertRaisesRegex(ValueError,"unexpected or missing"):
                verify_file_manifest(root)

    def test_missing_jobs_blocks_before_endpoint_analysis(self):
        cases={name:{"status":"ADMITTED_STRICT_LOCAL"} for name in ("UC-s000","WC-s001","SC-s005")}
        jobs=expected_jobs(cases,phase="pilot")
        self.assertEqual(set(jobs),{"UC-s000-52001-52001","WC-s001-52001-52001","SC-s005-52001-52001"})
        sources={"schema_version":"ga-knapsack-sources-v1","phase":"pilot",
                 "implementation_commit_sha":"a"*40,"sources":[]}
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError,"missing or extra source jobs"):
                collect_verified_batches(Path(temporary),sources,cases,{},
                                         {"implementation_commit_sha":"a"*40},phase="pilot")


if __name__ == "__main__":
    unittest.main()

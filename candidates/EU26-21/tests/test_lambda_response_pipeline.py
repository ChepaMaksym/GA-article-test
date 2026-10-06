"""CI fixture verifies chronology and counters without fitting Census models."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corrected_applied.data_protocol import TRANSFORMED_FEATURE_NAMES
from lambda_response_study import contract, prepare, run_case

SHA = "a"*40

def provenance():
    return {"protocol_id":contract.PROTOCOL_ID,"protocol_sha256":contract.PROTOCOL_SHA256,
            "registration_sha":contract.REGISTRATION_SHA,"implementation_sha":SHA,
            "workflow_sha":SHA,"run_id":1,"run_attempt":1}

def metadata():
    return {"feature_names":list(TRANSFORMED_FEATURE_NAMES),"test_arrays_loaded":False,
            "instance_weight_as_predictor":False,"instance_weight_as_sample_weight":True,
            "preprocessing_fit_scope":"internal_training_only","split_seed":2026081700+45001}

class LambdaResponsePipelineTests(unittest.TestCase):
    def test_forty_shared_initial_fits_minimum_and_exact_tie(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            train=root/"train.txt"
            train.write_bytes(b"CI_ONLY_SYNTHETIC_FIXTURE")
            protocol=contract.validate_protocol()
            protocol=deepcopy(protocol)
            protocol["data"]["train_sha256"]=contract.file_sha256(train)
            prepared=SimpleNamespace(metadata=metadata(),feature_names=TRANSFORMED_FEATURE_NAMES)
            calls=[]
            def objective(mask):
                calls.append(mask)
                bit=mask.index(1)
                return .5 if bit in (3,7) else .6
            with patch.object(prepare,"authenticate",return_value=(protocol,provenance())),\
                 patch.object(prepare,"prepare_training",return_value=prepared),\
                 patch.object(prepare,"objective_for",return_value=objective):
                result=prepare.prepare(train=train,seed=45001,expected_sha=SHA,output=root/"prep")
            self.assertEqual(len(calls),40)
            self.assertEqual(result["initial"]["bit_index"],3)
            self.assertEqual(result["initial"]["feature_name"],TRANSFORMED_FEATURE_NAMES[3])
            contract.verify_manifest(root/"prep/manifest.json",expected_sha=SHA)
            for change in ("score","mask"):
                bad=deepcopy(result)
                bad["initial"][change]=.99 if change=="score" else [1]*40
                with self.assertRaises(ValueError):
                    contract.validate_preparation(bad,seed=45001,expected_sha=SHA)

    def test_no_test_access_before_both_real_final_parents_frozen(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            train=root/"train.txt"
            train.write_bytes(b"SYNTHETIC_ONLY")
            protocol=deepcopy(contract.validate_protocol())
            protocol["data"]["train_sha256"]=contract.file_sha256(train)
            prepared=SimpleNamespace(metadata=metadata(),feature_names=TRANSFORMED_FEATURE_NAMES)
            initial={"mask":[1]+[0]*39,"score":.505,"bit_index":0,"feature_name":TRANSFORMED_FEATURE_NAMES[0]}
            frozen={"initial":initial,"training_data":metadata()}
            events=[]
            def objective(mask):
                events.append("validation")
                return .5+.2*sum(mask)/40 if sum(mask) else 0
            output=root/"case"
            def holdout(*args,**kwargs):
                parents=contract.read_json(output/"terminal-masks.json")
                self.assertEqual(set(parents["parents"]),set(contract.ARMS))
                self.assertEqual(parents["test_evaluations_so_far"],0)
                self.assertTrue(all((output/f"trace-census-{a}.json").is_file() for a in contract.ARMS))
                events.append("load_test")
                return SimpleNamespace()
            def evaluate(*args,**kwargs):
                self.assertEqual(events.count("load_test"),1)
                self.assertNotIn("validation",events[events.index("load_test")+1:])
                events.append("test")
                path=kwargs["path"]
                path.write_bytes(b"SYNTHETIC_MODEL_NOT_DESERIALIZED")
                return {"synthetic":True},{"file":path.name,"sha256":contract.file_sha256(path),"bytes":path.stat().st_size}
            with patch.object(run_case,"authenticate",return_value=(protocol,provenance())),\
                 patch.object(run_case,"load_preparation",return_value=(frozen,{"source_artifact_id":123})),\
                 patch.object(run_case,"prepare_training",return_value=prepared),\
                 patch.object(run_case,"objective_for",return_value=objective),\
                 patch.object(run_case,"load_terminal_holdout",side_effect=holdout),\
                 patch.object(run_case,"evaluate_and_persist",side_effect=evaluate),\
                 patch.object(run_case,"normalize_terminal_metrics",side_effect=lambda value:value):
                result=run_case.run_case(train=train,test=root/"unused_test.txt",seed=45001,
                    expected_sha=SHA,preparation=root/"unused-prep",registry=root/"unused-registry",output=output)
            self.assertEqual(events.count("test"),2)
            self.assertEqual(result["counts"]["test_evaluations"],2)
            self.assertEqual(len(result["problems"]),2)
            self.assertEqual(events.count("validation"),sum(
                t["counts"]["physical_calls"] for t in result["problems"]["census"]["arms"].values()))
            contract.verify_manifest(output/"manifest.json",expected_sha=SHA)

    def test_protocol_registration_and_training_only_profile(self):
        p=contract.validate_protocol()
        self.assertFalse(p["source"]["QX_used"])
        self.assertFalse(p["search"]["equal_objective_budget"])
        self.assertEqual(p["search"]["generations"],20)
        self.assertEqual(p["search"]["final_selection"],"accepted_parent_after_generation_20")
        with self.assertRaises(ValueError):
            contract.authenticate(SHA)

if __name__ == "__main__":
    unittest.main()

"""Static workflow contract, executed only in CI."""
from pathlib import Path
import re
import sys
import unittest

import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lambda_response_study.contract import CASE_SEEDS,PROTOCOL_SHA256,REGISTRATION_SHA

class LambdaResponseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.path=Path(__file__).resolve().parents[3]/".github/workflows/eu26-21-lambda-response-study.yml"
        self.text=self.path.read_text(encoding="utf-8")
        self.data=yaml.safe_load(self.text)

    def test_matrix_and_barriers(self):
        jobs=self.data["jobs"]
        self.assertEqual(set(jobs),{"preflight","dispatch","authorize","fixture","preparations","registry","cases","aggregate"})
        for name in ("preparations","cases"):
            strategy=jobs[name]["strategy"]
            self.assertFalse(strategy["fail-fast"])
            self.assertEqual(strategy["max-parallel"],10)
            self.assertEqual(strategy["matrix"]["seed"],list(CASE_SEEDS))
        self.assertIn("registry",jobs["cases"]["needs"])
        self.assertIn("cases",jobs["aggregate"]["needs"])

    def test_sha_pins_registration_and_exact_dispatch(self):
        self.assertEqual(self.data["env"]["PROTOCOL_SHA256"],PROTOCOL_SHA256)
        self.assertEqual(self.data["env"]["REGISTRATION_SHA"],REGISTRATION_SHA)
        for use in re.findall(r"uses:\s+([^\s]+)",self.text):
            self.assertRegex(use,r"@[0-9a-f]{40}$")
        self.assertIn("workflow_dispatch",self.text)
        self.assertIn("STUDY_WORKFLOW_SHA",self.text)
        self.assertIn("[launch-lambda-response]",self.text)

    def test_ci_only_transport(self):
        self.assertIn("--kind lr-preparation",self.text)
        self.assertIn("--transport-ledger",self.text)
        self.assertNotIn("python -m lambda_response_study.source_gate",self.text)
        self.assertIn("test -z",self.text)
        self.assertNotIn("pull-requests: write",self.text)

if __name__=="__main__":
    unittest.main()

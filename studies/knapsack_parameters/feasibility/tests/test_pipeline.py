"""CI-only frozen provenance, orchestration and safe transport fixtures."""

import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import zipfile

from studies.knapsack_parameters.feasibility.data_audit import parse_instance
from studies.knapsack_parameters.feasibility.download_cases import download_zip, extract_case
from studies.knapsack_parameters.feasibility.frozen_inputs import DEFAULT_INPUTS, verify_input_bundle
from studies.knapsack_parameters.feasibility.prepare_case import prepare_instance


class PipelineTests(unittest.TestCase):
    def test_frozen_originals_match_all_thirty_recorded_arrays(self):
        instances, manifest = verify_input_bundle()
        self.assertEqual(len(instances), 30)
        self.assertEqual([instances[index].instance_id for index in (0, 9, 10, 29)], ["UC-s000", "UC-s009", "WC-s000", "SC-s009"])
        self.assertEqual(manifest["status"], "PASS_AUDIT")

    def test_even_whitespace_changes_in_originals_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "inputs"
            shutil.copytree(DEFAULT_INPUTS, target)
            source = target / "source/00Uncorrelated/n00100/R01000/s000.kp"
            source.write_bytes(source.read_bytes() + b"\n")
            with self.assertRaises(ValueError):
                verify_input_bundle(target)

    def test_teaching_case_runs_two_methods_and_independent_complete_certificate(self):
        instance = parse_instance(b"3\n10\n10 6\n8 5\n8 5\n", "fixture.kp", class_label="UC", family="s000", index=0, expected_n=3)
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "case"
            case = prepare_instance(instance, {"fixture": True}, {"fixture": True}, target, deadline=None)
            self.assertEqual(case["status"], "ADMITTED_STRICT_LOCAL")
            self.assertEqual(case["exact"]["confirmed_optimum"], 16)
            self.assertEqual(case["certificate"]["center"]["mask"], "100")
            self.assertEqual(case["certificate"]["neighbor_count"], 6)
            self.assertTrue((target / "neighbors.csv").is_file())

    def test_zip_traversal_rejected_before_extraction(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../outside.json", "{}")
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(ValueError):
            extract_case(buffer.getvalue(), Path(temporary) / "case")

    def test_artifact_token_not_forwarded_to_signed_object_store(self):
        payload = b"fixture ZIP bytes"
        digest = hashlib.sha256(payload).hexdigest()
        metadata = {"id": 123, "digest": f"sha256:{digest}", "size_in_bytes": len(payload)}
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self):
                return payload
        error = urllib.error.HTTPError("https://api.github.com/fixture", 302, "redirect", {"Location": "https://objects.example.invalid/fixture?signature=fictitious"}, None)
        with patch.dict("os.environ", {"GITHUB_TOKEN": "FICTITIOUS_FIXTURE_TOKEN"}), patch("urllib.request.build_opener") as opener, patch("urllib.request.urlopen", return_value=Response()) as object_store:
            opener.return_value.open.side_effect = error
            self.assertEqual(download_zip(metadata, "ChepaMaksym/GA-article-test"), payload)
            redirected_request = object_store.call_args.args[0]
            self.assertIsNone(redirected_request.get_header("Authorization"))


if __name__ == "__main__":
    unittest.main()

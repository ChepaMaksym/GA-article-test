"""Check the holdout enrollment, pairing and evidence paths in CI."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from . import preparation as prep


def audit():
    return {"schema": "independent-validation100-history-v1", "cohort": "s060-s069",
            "status": "ELIGIBLE_WITHIN_PROJECT_EVIDENCE", "previous_holdout_search_runs": 0,
            "original_input_audit": prep.ORIGIN["run_id"], "registered_history_sha256": "a" * 64}


def manifest_fixture(case):
    task = case["task"]
    entry = {key: case[key] for key in ("task_index", "family", "class_label")}
    for key, filename in prep.FILE_NAMES.items():
        entry[key] = {"path": f"{task}/{filename}", "bytes": 1, "sha256": "f" * 64}
    entry["banks"] = {str(case["seed"]): {"path": f"{task}/banks/seed-{case['seed']}.json",
                                         "bytes": 1, "sha256": "b" * 64}}
    return {"schema": "independent-validation100-inputs-v1", "status": "PAIRED_HOLDOUT_BANKS_PREPARED",
            "source_archive_sha256": prep.ORIGIN["sha256"], "technical_manifest_sha256": prep.TECHNICAL_MANIFEST,
            "selection_sha256": prep.SELECTION_SHA, "source_records_sha256": prep.RECORDS_SHA, "tasks": {task: entry}}


class PreparationTests(unittest.TestCase):
    def test_four_paired_profiles_on_all_holdout_tasks(self):
        cases = prep.schedule_cases()
        self.assertEqual(len(cases), len({c["case_id"] for c in cases}))
        self.assertEqual(len(cases), 1200)
        pairs = {}
        for case in cases:
            pairs.setdefault((case["task"], case["seed"]), set()).add(
                (case["mu"], case["pc_percentage"], case["mutation_basis_points"]))
        self.assertEqual(len(pairs), 300)
        self.assertTrue(all(profiles == set(prep.PROFILES) for profiles in pairs.values()))
        self.assertEqual(cases[0]["case_id"], "n00100-UC-s060-seed-160001-mu10-pc90-pm100bp")
        self.assertEqual(cases[-1]["case_id"], "n00100-SC-s069-seed-160010-mu20-pc90-pm100bp")
        self.assertEqual(sorted(set(c["task_index"] for c in cases)), list(range(33, 63)))

    def test_original_frozen_choices_still_match(self):
        prep.verify_frozen_roles()

    def test_holdout_admission_rejects_incomplete_or_contaminated_scope(self):
        self.assertEqual(prep.checked_audit(audit())["previous_holdout_search_runs"], 0)
        for key, value in (("status", "PENDING"), ("previous_holdout_search_runs", 1),
                           ("previous_holdout_search_runs", False), ("cohort", "s050-s059"),
                           ("registered_history_sha256", "z" * 64), ("original_input_audit", 1)):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                prep.checked_audit({**audit(), key: value})

    def test_all_four_cases_share_the_same_bank_descriptor(self):
        cases = prep.schedule_cases()[:4]
        manifest = manifest_fixture(cases[0])
        expected = prep.input_descriptors(manifest, cases[0])
        self.assertEqual(set(expected), {"problem", "source", "bank", "certificate"})
        for case in cases[1:]:
            self.assertEqual(prep.input_descriptors(manifest, case), expected)

    def test_swapped_file_or_bank_and_mixed_seal_are_rejected(self):
        case = prep.schedule_cases()[0]
        for change in ("bank", "certificate", "source_archive_sha256", "selection_sha256", "task_index"):
            manifest = manifest_fixture(case)
            task = manifest["tasks"][case["task"]]
            if change == "bank":
                task["banks"][str(case["seed"])]["path"] = f"{case['task']}/banks/seed-160002.json"
            elif change == "certificate":
                task[change]["path"] = "../certificate.json"
            elif change == "task_index":
                task[change] = 0
            else:
                manifest[change] = "9" * 64
            with self.subTest(change=change), self.assertRaises(ValueError):
                prep.input_descriptors(manifest, case)

    def test_contents_and_traversal_fail_closed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "sample.json"
            path.write_bytes(b"original")
            entry = prep.descriptor(root, path)
            self.assertEqual(prep.checked_path(root, entry, "sample.json"), path)
            path.write_bytes(b"modified")
            with self.assertRaises(ValueError):
                prep.checked_path(root, entry, "sample.json")
            with self.assertRaises(ValueError):
                prep.checked_path(root, {**entry, "path": "../sample.json"}, "../sample.json")

    def test_modified_source_archive_is_rejected_before_opening_members(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "archive.zip"
            path.write_bytes(b"0" * prep.ORIGIN["bytes"])
            with self.assertRaises(ValueError):
                prep.read_certified_archive(path)


if __name__ == "__main__":
    unittest.main()

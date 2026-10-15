"""Synthetic outer-identity fixtures: no network, preparation, or GA search."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import unittest
import warnings
import zipfile

import numpy as np

from . import contract as c
from . import provenance as p


def metadata_fixture(phase="tests"):
    transport = {"protocol_id": c.PROTOCOL, "run_id": 101, "run_attempt": 1,
                 "artifact_id": 303, "implementation_sha": "ab" * 20,
                 "artifact_zip_sha256": "cd" * 32}
    run = {"id": 101, "run_attempt": 1, "conclusion": "success", "status": "completed",
           "head_sha": transport["implementation_sha"], "head_branch": c.BRANCH,
           "path": c.WORKFLOW, "head_commit": {"message": "Fixture [adaptive-mutation:" + phase + "]"}}
    prefix = "tests" if phase == "tests" else "inputs"
    artifact = {"id": 303, "expired": False,
                "workflow_run": {"id": 101, "head_sha": transport["implementation_sha"]},
                "name": f"adaptive-mutation-{prefix}-101-1",
                "digest": "sha256:" + transport["artifact_zip_sha256"]}
    return transport, run, artifact


def manifest_fixture(contents):
    return {"protocol_id": c.PROTOCOL, "excludes_self": True,
            "files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                      for name, data in contents]}


def archive_fixture(contents=None, manifest=None, extras=()):
    contents = [("receipt.json", b'{"fixture":"a"}\n'), ("tests.txt", b"synthetic fixtures only\n")] \
        if contents is None else contents
    manifest = manifest_fixture(contents) if manifest is None else manifest
    target = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in [*contents, *extras]:
                archive.writestr(name, data)
            archive.writestr("file_manifest.json", json.dumps(manifest).encode("utf-8"))
    raw = target.getvalue()
    return raw, hashlib.sha256(raw).hexdigest()


def initial_states(seed=76001, task=0, start=0):
    channels = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
    return {name: np.random.PCG64(np.random.SeedSequence([seed, task, start, channel])).state
            for channel, name in enumerate(channels)}


def identity_fixture():
    # An identity-only dictionary, deliberately not an executable search log.
    bank = {"task_index": 0, "start_index": 0,
            "problem": {"n": 2, "weights": [1, 2], "profits": [2, 3], "capacity": 2},
            "initial_masks": ["00"] * 30,
            "initial_scores": [{"weight": 0, "profit": 0, "feasible": True} for _ in range(30)]}
    log = {"method": "fixed", "budget": 5000, "problem": copy.deepcopy(bank["problem"]),
           "initial_masks": bank["initial_masks"][:],
           "initial_scores": copy.deepcopy(bank["initial_scores"]), "rng_initial": initial_states()}
    return log, bank


def complete_fixture():
    rows = []
    for task in ("UC-s000", "WC-s001", "SC-s005", "SC-s000"):
        for start in ("cloned", "bank"):
            for method in ("fixed", "adaptive_mutation"):
                initial = 35617 if (task, start) == ("SC-s000", "cloned") else 10
                rows.append({"task": task, "start": start, "method": method, "seed": 76001,
                             "summary": {"new_calls": 5000, "best_profit": initial},
                             "verification": {"verification_status": "VERIFIED"},
                             "initial_record": initial, "first_improvement_call": None})
    return rows


class ProvenanceTests(unittest.TestCase):
    def test_exact_tests_and_preparation_metadata(self):
        for phase in ("tests", "prepare"):
            with self.subTest(phase=phase):
                p.validate_metadata(*metadata_fixture(phase), phase)

    def test_wrong_phase_marker_or_api_run_identity_rejected(self):
        mutations = {
            "run": lambda t, r, a: r.__setitem__("id", 102),
            "attempt": lambda t, r, a: r.__setitem__("run_attempt", 2),
            "sha": lambda t, r, a: r.__setitem__("head_sha", "ef" * 20),
            "branch": lambda t, r, a: r.__setitem__("head_branch", "main"),
            "workflow": lambda t, r, a: r.__setitem__("path", ".github/workflows/other.yml"),
            "status": lambda t, r, a: r.__setitem__("status", "in_progress"),
            "failure": lambda t, r, a: r.__setitem__("conclusion", "failure"),
            "phase": lambda t, r, a: r["head_commit"].__setitem__("message", "[adaptive-mutation:prepare]"),
            "mixed_marker": lambda t, r, a: r["head_commit"].__setitem__(
                "message", "[adaptive-mutation:tests] [diversity-main:main]"),
            "transport_id": lambda t, r, a: t.__setitem__("run_id", True),
            "transport_hash": lambda t, r, a: t.__setitem__("implementation_sha", "not-a-sha"),
            "protocol": lambda t, r, a: t.__setitem__("protocol_id", "OTHER-PROTOCOL"),
        }
        for label, change in mutations.items():
            with self.subTest(label=label):
                values = metadata_fixture()
                change(*values)
                with self.assertRaises(ValueError):
                    p.validate_metadata(*values, "tests")
        with self.assertRaises(ValueError):
            p.validate_metadata(*metadata_fixture(), "pilot")

    def test_wrong_artifact_digest_run_attempt_name_and_expiration_rejected(self):
        mutations = {
            "artifact_id": lambda a: a.__setitem__("id", 304),
            "expired": lambda a: a.__setitem__("expired", True),
            "run_id": lambda a: a["workflow_run"].__setitem__("id", 102),
            "sha": lambda a: a["workflow_run"].__setitem__("head_sha", "ef" * 20),
            "attempt_name": lambda a: a.__setitem__("name", "adaptive-mutation-tests-101-2"),
            "wrong_phase_name": lambda a: a.__setitem__("name", "adaptive-mutation-inputs-101-1"),
            "digest": lambda a: a.__setitem__("digest", "sha256:" + "00" * 32),
        }
        for label, change in mutations.items():
            with self.subTest(label=label):
                transport, run, artifact = metadata_fixture()
                change(artifact)
                with self.assertRaises(ValueError):
                    p.validate_metadata(transport, run, artifact, "tests")

    def test_complete_archive_and_outer_zip_hash(self):
        raw, digest = archive_fixture()
        members = p.validate_archive(raw, digest)
        self.assertEqual(set(members), {"file_manifest.json", "receipt.json", "tests.txt"})
        self.assertEqual(members["receipt.json"], b'{"fixture":"a"}\n')
        for corrupted, expected in ((raw + b"corruption", digest), (raw, "00" * 32)):
            with self.assertRaises(ValueError):
                p.validate_archive(corrupted, expected)

    def test_unsafe_archive_paths_directories_and_links_rejected(self):
        for name in ("../escape.json", "/absolute.json", "C:drive.json", "a\\b.json", "a/../b.json", "folder/"):
            with self.subTest(name=name):
                raw, digest = archive_fixture(contents=[(name, b"fixture")])
                with self.assertRaises(ValueError):
                    p.validate_archive(raw, digest)
        link = zipfile.ZipInfo("link.json")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        raw, digest = archive_fixture(contents=[("target.json", b"target")], extras=[(link, b"target.json")])
        with self.assertRaises(ValueError):
            p.validate_archive(raw, digest)

    def test_incomplete_extra_repeated_and_mixed_internal_archive_rejected(self):
        original = [("receipt.json", b"original"), ("tests.txt", b"pass")]
        manifest = manifest_fixture(original)
        cases = {
            "missing": (original[:1], manifest, ()),
            "extra": (original, manifest, [("unexpected.json", b"extra")]),
            "repeated_zip_member": (original, manifest, [("tests.txt", b"pass")]),
            "mixed_artifacts": ([("receipt.json", b"replaced"), original[1]], manifest, ()),
        }
        for label, (contents, declared, extras) in cases.items():
            with self.subTest(label=label):
                raw, digest = archive_fixture(contents=contents, manifest=declared, extras=extras)
                with self.assertRaises(ValueError):
                    p.validate_archive(raw, digest)
        repeated = copy.deepcopy(manifest)
        repeated["files"].append(copy.deepcopy(repeated["files"][0]))
        raw, digest = archive_fixture(contents=original, manifest=repeated)
        with self.assertRaises(ValueError):
            p.validate_archive(raw, digest)

    def test_wrong_internal_size_checksum_and_protocol_rejected(self):
        contents = [("receipt.json", b"fixture")]
        for field in ("bytes", "sha256", "protocol_id", "excludes_self"):
            with self.subTest(field=field):
                manifest = manifest_fixture(contents)
                if field == "bytes":
                    manifest["files"][0][field] += 1
                elif field == "sha256":
                    manifest["files"][0][field] = "00" * 32
                else:
                    manifest[field] = "wrong" if field == "protocol_id" else False
                raw, digest = archive_fixture(contents=contents, manifest=manifest)
                with self.assertRaises(ValueError):
                    p.validate_archive(raw, digest)

    def test_log_identity_binds_all_six_registered_streams_without_search(self):
        log, bank = identity_fixture()
        p.validate_log_identity(log, bank, "fixed")
        for channel in log["rng_initial"]:
            with self.subTest(channel=channel):
                wrong = copy.deepcopy(log)
                wrong["rng_initial"][channel]["state"]["state"] ^= 1
                with self.assertRaises(ValueError):
                    p.validate_log_identity(wrong, bank, "fixed")

    def test_wrong_seed_task_start_method_budget_and_bank_mix_rejected(self):
        log, bank = identity_fixture()
        for label, wrong in (("seed", initial_states(seed=76002)),
                             ("task", initial_states(task=1)), ("start", initial_states(start=1))):
            with self.subTest(label=label):
                changed = copy.deepcopy(log)
                changed["rng_initial"] = wrong
                with self.assertRaises(ValueError):
                    p.validate_log_identity(changed, bank, "fixed")
        mutations = {
            "method": lambda x: x.__setitem__("method", "adaptive_mutation"),
            "budget": lambda x: x.__setitem__("budget", 4999),
            "problem": lambda x: x["problem"]["weights"].__setitem__(0, 9),
            "mask": lambda x: x["initial_masks"].__setitem__(0, "10"),
            "score": lambda x: x["initial_scores"][0].__setitem__("profit", 1),
        }
        for label, change in mutations.items():
            with self.subTest(label=label):
                wrong = copy.deepcopy(log)
                change(wrong)
                with self.assertRaises(ValueError):
                    p.validate_log_identity(wrong, bank, "fixed")
        wrong = copy.deepcopy(log)
        wrong["method"] = "unknown"
        with self.assertRaises(ValueError):
            p.validate_log_identity(wrong, bank, "unknown")

    def test_exact_sixteen_identities_not_just_total_budget(self):
        rows = complete_fixture()
        p.validate_complete_results(rows)
        for label in ("missing", "duplicate", "unknown_task"):
            with self.subTest(label=label):
                wrong = copy.deepcopy(rows)
                if label == "missing":
                    wrong.pop()
                elif label == "duplicate":
                    wrong[-1] = copy.deepcopy(wrong[0])  # Still sixteen and 80000 calls.
                else:
                    wrong[-1]["task"] = "UC-s999"
                with self.assertRaises(ValueError):
                    p.validate_complete_results(wrong)

    def test_incomplete_calls_wrong_seed_and_unverified_result_rejected(self):
        for label in ("calls", "seed", "verification"):
            with self.subTest(label=label):
                rows = complete_fixture()
                if label == "calls":
                    rows[0]["summary"]["new_calls"] = 4999
                elif label == "seed":
                    rows[0]["seed"] = 76002
                else:
                    rows[0]["verification"]["verification_status"] = "UNVERIFIED"
                with self.assertRaises(ValueError):
                    p.validate_complete_results(rows)

    def test_global_cloned_negative_control_for_both_methods(self):
        for method in ("fixed", "adaptive_mutation"):
            for field in ("first_improvement_call", "best_profit"):
                with self.subTest(method=method, field=field):
                    rows = complete_fixture()
                    target = next(row for row in rows if (row["task"], row["start"], row["method"]) ==
                                  ("SC-s000", "cloned", method))
                    if field == "first_improvement_call":
                        target[field] = 5000
                    else:
                        target["summary"][field] += 1
                    with self.assertRaises(ValueError):
                        p.validate_complete_results(rows)

    def test_global_task_random_bank_not_mislabelled_as_global_start(self):
        rows = complete_fixture()
        for row in rows:
            if (row["task"], row["start"]) == ("SC-s000", "bank"):
                row["summary"]["best_profit"] = 11
                row["first_improvement_call"] = 1
        p.validate_complete_results(rows)


if __name__ == "__main__":
    unittest.main()

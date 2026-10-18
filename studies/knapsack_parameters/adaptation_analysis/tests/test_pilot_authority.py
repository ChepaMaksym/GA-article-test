"""Prospective CI checks of the separately approved pilot resource contract.

No preparation or scientific search is executed by these software fixtures.
"""
from copy import deepcopy
from contextlib import ExitStack, contextmanager
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.adaptation_analysis import pilot_authority as p


def _grant():
    return {
        "protocol_id": "GA-KNAPSACK-ADAPTATION-ANALYSIS-PILOT-V1",
        "parent_protocol_id": "GA-KNAPSACK-ADAPTATION-ANALYSIS-V1",
        "explicit_user_approval": True,
        "allowed_phases": ["prepare", "pilot", "aggregate"],
        "runner_minutes_ceiling": 60,
        "phase_reservation_minutes": {"prepare": 5, "pilot": 49},
        "job_timeout_minutes": {"gate": 1, "prepare": 4, "pilot": 5, "aggregate": 8},
        "max_parallel": 4,
        "maximum_compressed_bytes_per_job": 536870912,
        "search_seed": 86001,
        "preparation_seed": 86000,
        "expected_initial_conditions": 8,
        "expected_search_runs": 40,
        "new_evaluations_per_run": 5000,
        "main_search_authorized": False,
        "lambda_search_authorized": False,
        "confirmatory_statistics_authorized": False,
    }


def _provenance():
    return {"protocol_id": p.a.PROTOCOL, "pilot_protocol_id": p.PROTOCOL,
            "pilot_registration_sha": p.REGISTRATION_SHA,
            "implementation_sha": "a" * 40, "source_manifest": {"files": [], "sha256": "b" * 64},
            "run_id": 999, "run_attempt": 1}


def _permit(phase="pilot"):
    return {**_provenance(), "used_runner_minutes": 2, "prior_jobs": [], "phase": phase,
            "resource_grant": _grant(), "reserved_runner_minutes": 5 if phase == "prepare" else 49,
            "green_tests_run": 101, "main_search_authorized": False, "lambda_search_authorized": False}


def _green():
    receipt = {"protocol_id": p.a.PROTOCOL, "tests_passed": True, "tests_run": 101,
               "failures": 0, "errors": 0, "skipped": 0,
               "scientific_KPLIB_search_performed": False, "lambda_search_performed": False,
               "run_id": 101, "run_attempt": 1, "implementation_sha": "c" * 40,
               "source_manifest": {"files": [], "sha256": "d" * 64}}
    frozen = {"pilot_protocol_id": p.PROTOCOL, "frozen": True,
              "receipt_directory": "evidence/software-fixture", "artifact_id": 201,
              "zip_sha256": "e" * 64}
    return receipt, frozen


def _bank_fixture():
    """Construct software-only metadata; never evaluate a scientific task."""
    import numpy as np

    problem = {"n": 100, "weights": [1] * 100, "profits": [1] * 100, "capacity": 100}
    case = {"certificate": {"center": {"mask": "0" * 100, "profit": 0, "weight": 0}}}
    source = {"path": "software-fixture-only", "bytes": 1, "sha256": "0" * 64}
    registry = {"schema": "ga-adaptation-pilot-banks-v1", "protocol_id": p.a.PROTOCOL,
                "pilot_protocol_id": p.PROTOCOL, "scope": "pilot", "initial_conditions": 8,
                "scientific_search_calls": 0, "implementation_sha": "c" * 40,
                "source_manifest": {"files": [], "sha256": "d" * 64},
                "run_id": 101, "run_attempt": 1, "banks": [],
                "physical_preparation_evaluations": 0, "independent_preparation_checks": 240}
    identity = {"bytes": 17, "sha256": "e" * 64}
    frozen = {"pilot_protocol_id": p.PROTOCOL, "frozen": True, "registry_identity": identity}
    banks = {}
    for ti, task in enumerate(p.TASKS):
        for si, start in enumerate(p.STARTS):
            rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([86000, 86001, ti, si, 0])))
            before = deepcopy(rng.bit_generator.state)
            masks = (["0" * 100] * 30 if start == "cloned" else ["0" * 100] +
                     ["".join("1" if bit else "0" for bit in rng.random(100) < 0.5)
                      for _ in range(29)])
            name = f"{task}-{start}-86001.json"
            bank = {key: deepcopy(registry[key]) for key in
                    ("protocol_id", "pilot_protocol_id", "implementation_sha", "source_manifest", "run_id", "run_attempt")}
            bank.update({"task": task, "start": start, "search_seed": 86001, "preparation_seed": 86000,
                         "task_index": ti, "start_index": si, "problem": deepcopy(problem),
                         "source_identity": deepcopy(source), "initial_masks": masks,
                         "initial_scores": [{"weight": mask.count("1"), "profit": mask.count("1"),
                                             "feasible": True} for mask in masks],
                         "initialization_before": before, "initialization_after": deepcopy(rng.bit_generator.state),
                         "physical_preparation_evaluations": len(set(masks)),
                         "independent_preparation_checks": 30, "logical_initial_positions": 30})
            banks[name] = bank
            registry["banks"].append({"task": task, "start": start, "seed": 86001,
                                      "path": "banks/" + name, "bytes": 23, "sha256": "f" * 64})
            registry["physical_preparation_evaluations"] += len(set(masks))
    return {"problem": problem, "case": case, "source": source, "registry": registry,
            "frozen": frozen, "banks": banks, "identity": identity,
            "freeze_sha": "f" * 40, "freeze_paths": [p.a.REL + "frozen_banks.json"]}


@contextmanager
def _mock_banks(fixture):
    def read(path):
        name = Path(path).name
        if name == "bank_registry.json":
            return fixture["registry"]
        if name == "frozen_banks.json":
            return fixture["frozen"]
        if name == "registry.json":
            return {"case_order": list(p.TASKS)}
        return fixture["banks"][name]

    def identity(path):
        return fixture["identity"] if Path(path).name == "bank_registry.json" else {"bytes": 23, "sha256": "f" * 64}

    def git(command, **kwargs):
        if command[1] == "log":
            return fixture["freeze_sha"] + "\n"
        if command[1] == "diff":
            return "\n".join(fixture["freeze_paths"]) + "\n"
        raise AssertionError("Unexpected Git operation in bank software fixture")

    with ExitStack() as stack:
        stack.enter_context(patch.object(p.a, "read_json", side_effect=read))
        stack.enter_context(patch.object(p.a, "identity", side_effect=identity))
        stack.enter_context(patch.object(p.a, "verify_manifest", return_value={}))
        stack.enter_context(patch.object(p.a, "api", return_value={"head_commit": {"message": "[adaptation-pilot:prepare]"}}))
        stack.enter_context(patch.object(p, "_successful_source", return_value={}))
        stack.enter_context(patch.object(p, "_artifact_identity", return_value={}))
        stack.enter_context(patch.object(p.subprocess, "check_output", side_effect=git))
        stack.enter_context(patch("studies.knapsack_parameters.mutation_population.driver.source_task",
                                  return_value=(fixture["problem"], fixture["case"], fixture["source"])))
        yield


class PilotAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Pilot authority checks execute only in GitHub Actions")

    def test_exact_registered_identity_and_frozen_environment(self):
        self.assertEqual(p.PROTOCOL, "GA-KNAPSACK-ADAPTATION-ANALYSIS-PILOT-V1")
        self.assertEqual(p.REGISTRATION_SHA, "c5922a34e8b97503324be27f19c7c09e4e039114")
        self.assertEqual(p.WORKFLOW, ".github/workflows/knapsack-adaptation-pilot.yml")
        receipt = p.authenticate(runtime=True)
        self.assertEqual(receipt["pilot_protocol_id"], p.PROTOCOL)
        self.assertEqual(receipt["implementation_sha"], os.environ["GITHUB_SHA"])
        self.assertEqual(receipt["environment"]["python"], "3.12.14")

    def test_only_two_exact_phase_markers(self):
        self.assertEqual(p.phase("Freeze [adaptation-pilot:prepare]"), "prepare")
        self.assertEqual(p.phase("Search [adaptation-pilot:pilot]"), "pilot")
        for message in ("", "[adaptation-pilot:main]", "[adaptation-pilot:aggregate]",
                        "[adaptation-pilot:lambda]", "[adaptation-pilot:prepare][other]",
                        "[adaptation-pilot:prepare] [adaptation-pilot:pilot]",
                        "[adaptation-pilot:pilot] [adaptation-analysis:tests]"):
            with self.subTest(message=message), self.assertRaises(ValueError):
                p.phase(message)

    def test_actual_grant_preserves_scientific_endpoints_and_limits(self):
        grant = p.resource_grant()
        for key, value in _grant().items():
            self.assertEqual(grant[key], value)
        self.assertEqual(sum((grant["phase_reservation_minutes"][phase]
                              for phase in ("prepare", "pilot"))), 54)
        self.assertEqual(grant["runner_minutes_ceiling"] - 54, 6)

    def test_grant_cannot_broaden_scope_or_change_resource_contract(self):
        mutations = (
            ("explicit_user_approval", False), ("runner_minutes_ceiling", 61),
            ("runner_minutes_ceiling", 60.0), ("max_parallel", 5),
            ("phase_reservation_minutes", {"prepare": 5, "pilot": 48}),
            ("job_timeout_minutes", {"gate": 1, "prepare": 4, "pilot": 5, "aggregate": 9}),
            ("expected_initial_conditions", 7), ("expected_search_runs", 39),
            ("new_evaluations_per_run", 4999), ("search_seed", 86002),
            ("preparation_seed", 86001), ("maximum_compressed_bytes_per_job", 536870913),
            ("main_search_authorized", True), ("lambda_search_authorized", True),
            ("confirmatory_statistics_authorized", True),
        )
        for key, value in mutations:
            invalid = {**_grant(), key: value}
            with self.subTest(key=key, value=value), \
                 patch.object(p.a, "read_json", return_value=invalid), self.assertRaises(ValueError):
                p.resource_grant()

    def test_phase_reservation_is_central_and_respects_total_ceiling(self):
        grant = _grant()
        p.check_allowance({"used_runner_minutes": 55}, "prepare", grant)
        p.check_allowance({"used_runner_minutes": 11}, "pilot", grant)
        for used, phase in ((56, "prepare"), (12, "pilot")):
            with self.subTest(used=used, phase=phase), self.assertRaises(ValueError):
                p.check_allowance({"used_runner_minutes": used}, phase, grant)

    def test_invalid_prior_usage_does_not_become_zero(self):
        for used in (None, True, -1, 1.0):
            with self.subTest(used=used), self.assertRaises(ValueError):
                p.check_allowance({"used_runner_minutes": used}, "pilot", _grant())
        with self.assertRaises(ValueError):
            p.check_allowance({"used_runner_minutes": 0}, "main", _grant())

    def test_all_attempts_and_each_job_round_up_including_failures(self):
        queried = []

        def pages(path, field):
            queried.append(path)
            if field == "workflow_runs":
                return [{"id": 41, "status": "completed", "run_attempt": 2}]
            attempt = 1 if "/attempts/1/" in path else 2
            return [{"id": 50 + attempt, "conclusion": "failure" if attempt == 1 else "success",
                     "started_at": "2026-10-18T00:00:00Z",
                     "completed_at": "2026-10-18T00:01:05Z" if attempt == 1 else "2026-10-18T00:00:05Z"},
                    {"id": 70 + attempt, "conclusion": "skipped"}]

        with patch.dict(os.environ, {"GITHUB_RUN_ID": "999", "GITHUB_RUN_ATTEMPT": "1"}), \
             patch.object(p.a, "pages", side_effect=pages):
            usage = p.runner_usage()
        self.assertEqual(usage["used_runner_minutes"], 3)
        self.assertEqual(len(usage["prior_jobs"]), 2)
        self.assertTrue(any("/attempts/1/" in path for path in queried))
        self.assertTrue(any("/attempts/2/" in path for path in queried))

    def test_current_attempt_not_charged_twice_but_earlier_attempts_are(self):
        queried = []

        def pages(path, field):
            queried.append(path)
            if field == "workflow_runs":
                return [{"id": 999, "status": "in_progress", "run_attempt": 3}]
            if "/attempts/3/" in path:
                raise AssertionError("The current central gate was charged before its own reservation")
            attempt = 1 if "/attempts/1/" in path else 2
            return [{"id": 80 + attempt, "conclusion": "cancelled", "started_at": "2026-10-18T00:00:00Z",
                     "completed_at": "2026-10-18T00:00:01Z"}]

        with patch.dict(os.environ, {"GITHUB_RUN_ID": "999", "GITHUB_RUN_ATTEMPT": "3"}), \
             patch.object(p.a, "pages", side_effect=pages):
            usage = p.runner_usage()
        self.assertEqual(usage["used_runner_minutes"], 2)
        self.assertFalse(any("/attempts/3/" in path for path in queried))

    def test_concurrent_other_run_blocks_reservation(self):
        def pages(path, field):
            if field == "workflow_runs":
                return [{"id": 41, "status": "in_progress", "run_attempt": 1}]
            raise AssertionError("An unknown concurrent run must block before job summation")

        with patch.dict(os.environ, {"GITHUB_RUN_ID": "999", "GITHUB_RUN_ATTEMPT": "1"}), \
             patch.object(p.a, "pages", side_effect=pages), self.assertRaises(ValueError):
            p.runner_usage()

    def test_unknown_or_negative_job_duration_blocks_reservation(self):
        invalid_jobs = (
            {"id": 51, "conclusion": "failure", "started_at": None, "completed_at": None},
            {"id": 51, "conclusion": "failure", "started_at": "2026-10-18T00:00:05Z",
             "completed_at": "2026-10-18T00:00:00Z"},
        )
        for job in invalid_jobs:
            def pages(path, field):
                return ([{"id": 41, "status": "completed", "run_attempt": 1}]
                        if field == "workflow_runs" else [job])
            with self.subTest(job=job), \
                 patch.dict(os.environ, {"GITHUB_RUN_ID": "999", "GITHUB_RUN_ATTEMPT": "1"}), \
                 patch.object(p.a, "pages", side_effect=pages), self.assertRaises(ValueError):
                p.runner_usage()

    def test_duplicate_allocated_job_is_not_silently_deduplicated(self):
        def pages(path, field):
            if field == "workflow_runs":
                return [{"id": 41, "status": "completed", "run_attempt": 1}]
            entry = {"id": 51, "conclusion": "success", "started_at": "2026-10-18T00:00:00Z",
                     "completed_at": "2026-10-18T00:00:01Z"}
            return [entry, deepcopy(entry)]

        with patch.dict(os.environ, {"GITHUB_RUN_ID": "999", "GITHUB_RUN_ATTEMPT": "1"}), \
             patch.object(p.a, "pages", side_effect=pages), self.assertRaises(ValueError):
            p.runner_usage()

    def test_worker_and_aggregator_reuse_one_central_reservation_without_api_rescan(self):
        for selected in ("prepare", "pilot", "aggregate"):
            phase = "pilot" if selected == "aggregate" else selected
            with self.subTest(selected=selected), \
                 patch.dict(os.environ, {"COMMIT_MESSAGE": f"Phase [adaptation-pilot:{phase}]"}), \
                 patch.object(p, "authenticate", return_value=_provenance()), \
                 patch.object(p, "resource_grant", return_value=_grant()), \
                 patch.object(p.a, "verify_manifest", return_value={}), \
                 patch.object(p.a, "read_json", return_value=_permit(phase)), \
                 patch.object(p, "runner_usage", side_effect=AssertionError("worker rescanned concurrent jobs")), \
                 patch.object(p, "validated_tests", side_effect=AssertionError("worker reserved a second phase")):
                receipt = p.check_permit("software-fixture-permit", selected)
                self.assertEqual(receipt["implementation_sha"], "a" * 40)

    def test_stale_wrong_phase_or_broadened_central_permit_is_rejected(self):
        mutations = (
            ("implementation_sha", "f" * 40), ("run_id", 1000), ("run_attempt", 2),
            ("pilot_protocol_id", "other-protocol"), ("pilot_registration_sha", "f" * 40),
            ("source_manifest", {"files": [], "sha256": "f" * 64}),
            ("phase", "prepare"), ("reserved_runner_minutes", 48),
            ("main_search_authorized", True), ("lambda_search_authorized", True),
            ("used_runner_minutes", 12),
        )
        for key, value in mutations:
            invalid = {**_permit(), key: value}
            with self.subTest(key=key), \
                 patch.dict(os.environ, {"COMMIT_MESSAGE": "Phase [adaptation-pilot:pilot]"}), \
                 patch.object(p, "authenticate", return_value=_provenance()), \
                 patch.object(p, "resource_grant", return_value=_grant()), \
                 patch.object(p.a, "verify_manifest", return_value={}), \
                 patch.object(p.a, "read_json", return_value=invalid), self.assertRaises(ValueError):
                p.check_permit("software-fixture-permit", "pilot")

    def test_wrong_worker_marker_or_unregistered_phase_is_rejected(self):
        for selected, marker in (("pilot", "prepare"), ("prepare", "pilot"),
                                 ("main", "pilot"), ("lambda", "pilot")):
            with self.subTest(selected=selected, marker=marker), \
                 patch.dict(os.environ, {"COMMIT_MESSAGE": f"Phase [adaptation-pilot:{marker}]"}), \
                 patch.object(p, "authenticate", return_value=_provenance()), self.assertRaises(ValueError):
                p.check_permit("software-fixture-permit", selected)

    def test_gate_reserves_whole_phase_once_and_requires_frozen_banks_for_pilot(self):
        for phase in ("prepare", "pilot"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory, \
                 patch.dict(os.environ, {"COMMIT_MESSAGE": f"Phase [adaptation-pilot:{phase}]"}), \
                 patch.object(p, "authenticate", return_value=_provenance()), \
                 patch.object(p, "resource_grant", return_value=_grant()), \
                 patch.object(p, "runner_usage", return_value={"used_runner_minutes": 2, "prior_jobs": []}) as usage, \
                 patch.object(p, "validated_tests", return_value={"run_id": 101}), \
                 patch.object(p, "load_banks", return_value=[{}] * 8) as banks:
                p.gate(directory, phase)
                permit = p.a.read_json(Path(directory) / "pilot_permit.json")
                self.assertEqual(permit["reserved_runner_minutes"], 5 if phase == "prepare" else 49)
                self.assertFalse(permit["main_search_authorized"])
                self.assertFalse(permit["lambda_search_authorized"])
                self.assertEqual(usage.call_count, 1)
                self.assertEqual(banks.call_count, int(phase == "pilot"))

    def test_gate_cannot_create_pilot_permit_before_frozen_banks(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {"COMMIT_MESSAGE": "Phase [adaptation-pilot:pilot]"}), \
             patch.object(p, "authenticate", return_value=_provenance()), \
             patch.object(p, "resource_grant", return_value=_grant()), \
             patch.object(p, "runner_usage", return_value={"used_runner_minutes": 2, "prior_jobs": []}), \
             patch.object(p, "validated_tests", return_value={"run_id": 101}), \
             patch.object(p, "load_banks", side_effect=ValueError("not frozen")), self.assertRaises(ValueError):
            p.gate(directory, "pilot")
        # No actual preparation or search is invoked by the mocked gate.

    def test_green_receipt_requires_real_tests_and_manifest_checks(self):
        receipt, frozen = _green()

        def read(path):
            return frozen if Path(path).name == "frozen_tests.json" else receipt

        with patch.object(p.a, "read_json", side_effect=read), \
             patch.object(p.a, "verify_manifest", return_value={}) as manifest, \
             patch.object(p, "_successful_source", return_value={}) as source, \
             patch.object(p, "_artifact_identity", return_value={}) as artifact:
            self.assertEqual(p.validated_tests(), receipt)
        self.assertEqual(manifest.call_count, 1)
        self.assertEqual(source.call_count, 1)
        self.assertEqual(artifact.call_count, 1)

    def test_green_receipt_invalid_tests_or_unsafe_path_is_rejected(self):
        original, frozen = _green()
        for key, value in (("tests_passed", False), ("tests_run", 0), ("tests_run", True),
                           ("failures", 1), ("errors", 1), ("skipped", 1),
                           ("scientific_KPLIB_search_performed", True), ("lambda_search_performed", True)):
            receipt = {**original, key: value}

            def read(path):
                return frozen if Path(path).name == "frozen_tests.json" else receipt

            with self.subTest(key=key), patch.object(p.a, "read_json", side_effect=read), \
                 patch.object(p.a, "verify_manifest", return_value={}), self.assertRaises(ValueError):
                p.validated_tests()
        for path in ("../outside", "/absolute", "evidence/../outside"):
            bad = {**frozen, "receipt_directory": path}
            with self.subTest(path=path), patch.object(p.a, "read_json", return_value=bad), self.assertRaises(ValueError):
                p.validated_tests()

    def test_successful_source_checks_workflow_branch_commit_and_fingerprint(self):
        receipt, _ = _green()
        correct_run = {"conclusion": "success", "head_sha": receipt["implementation_sha"],
                       "head_branch": p.a.BRANCH, "event": "push", "path": p.a.WORKFLOW}
        for key, value in (("conclusion", "failure"), ("head_sha", "f" * 40),
                           ("head_branch", "main"), ("event", "workflow_dispatch"), ("path", p.WORKFLOW)):
            run = {**correct_run, key: value}
            with self.subTest(key=key), patch.object(p.a, "api", return_value=run), self.assertRaises(ValueError):
                p._successful_source(receipt, p.a.WORKFLOW)
        with patch.object(p.a, "api", return_value=correct_run), \
             patch.object(p.subprocess, "run", return_value=None), \
             patch.object(p.a, "source_manifest", return_value={"files": [], "sha256": "f" * 64}), \
             patch.dict(os.environ, {"GITHUB_SHA": "a" * 40}), self.assertRaises(ValueError):
            p._successful_source(receipt, p.a.WORKFLOW)

    def test_successful_source_checks_git_bytes_not_only_a_declared_manifest(self):
        receipt, _ = _green()
        original = b"registered software fixture"
        manifest = {"files": [{"path": "fixture.py", "sha256": hashlib.sha256(original).hexdigest()}],
                    "sha256": "d" * 64}
        receipt["source_manifest"] = manifest
        run = {"conclusion": "success", "head_sha": receipt["implementation_sha"],
               "head_branch": p.a.BRANCH, "event": "push", "path": p.a.WORKFLOW}
        with patch.object(p.a, "api", return_value=run), patch.object(p.subprocess, "run", return_value=None), \
             patch.object(p.subprocess, "check_output", return_value=b"different bytes"), \
             patch.object(p.a, "source_manifest", return_value=manifest), \
             patch.dict(os.environ, {"GITHUB_SHA": "a" * 40}), self.assertRaises(ValueError):
            p._successful_source(receipt, p.a.WORKFLOW)

    def test_artifact_identity_binds_zip_digest_run_commit_and_availability(self):
        receipt, frozen = _green()
        valid = {"workflow_run": {"id": receipt["run_id"], "head_sha": receipt["implementation_sha"]},
                 "digest": "sha256:" + frozen["zip_sha256"], "expired": False}
        with patch.object(p.a, "api", return_value=valid):
            self.assertEqual(p._artifact_identity(frozen, receipt), valid)
        variants = []
        for key, value in (("digest", "sha256:" + "f" * 64), ("expired", True)):
            variants.append({**valid, key: value})
        variants.append({**valid, "workflow_run": {"id": 999, "head_sha": receipt["implementation_sha"]}})
        variants.append({**valid, "workflow_run": {"id": receipt["run_id"], "head_sha": "f" * 40}})
        for index, invalid in enumerate(variants):
            with self.subTest(corruption=index), patch.object(p.a, "api", return_value=invalid), self.assertRaises(ValueError):
                p._artifact_identity(frozen, receipt)

    def test_preparation_file_manifest_must_pass_before_using_bank_metadata(self):
        with patch.object(p.a, "verify_manifest", side_effect=ValueError("corrupt manifest")), \
             patch.object(p, "_successful_source", side_effect=AssertionError("invalid bank was used")), \
             self.assertRaises(ValueError):
            p.load_banks(validate_initial=False)

    def test_preparation_requires_explicit_freeze_and_exact_registry_identity(self):
        registry = {"schema": "ga-adaptation-pilot-banks-v1", "pilot_protocol_id": p.PROTOCOL, "scope": "pilot", "initial_conditions": 8,
                    "scientific_search_calls": 0}
        identity = {"bytes": 10, "sha256": "e" * 64}
        for frozen in ({"pilot_protocol_id": p.PROTOCOL, "frozen": False, "registry_identity": identity},
                       {"pilot_protocol_id": p.PROTOCOL, "frozen": True,
                        "registry_identity": {"bytes": 11, "sha256": "e" * 64}}):
            def read(path):
                return registry if Path(path).name == "bank_registry.json" else frozen

            with self.subTest(frozen=frozen), patch.object(p.a, "verify_manifest", return_value={}), \
                 patch.object(p.a, "read_json", side_effect=read), patch.object(p.a, "identity", return_value=identity), \
                 patch.object(p, "_successful_source", side_effect=AssertionError("unfrozen bank was used")), \
                 self.assertRaises(ValueError):
                p.load_banks(validate_initial=False)

    def test_preparation_is_not_allowed_to_include_search_calls_or_wrong_scope(self):
        valid = {"schema": "ga-adaptation-pilot-banks-v1", "pilot_protocol_id": p.PROTOCOL, "scope": "pilot", "initial_conditions": 8,
                 "scientific_search_calls": 0}
        identity = {"bytes": 10, "sha256": "e" * 64}
        frozen = {"pilot_protocol_id": p.PROTOCOL, "frozen": True, "registry_identity": identity}
        for key, value in (("scope", "main"), ("initial_conditions", 7), ("scientific_search_calls", 1)):
            registry = {**valid, key: value}

            def read(path):
                return registry if Path(path).name == "bank_registry.json" else frozen

            with self.subTest(key=key), patch.object(p.a, "verify_manifest", return_value={}), \
                 patch.object(p.a, "read_json", side_effect=read), patch.object(p.a, "identity", return_value=identity), \
                 patch.object(p, "_successful_source", side_effect=AssertionError("wrong scope was used")), \
                 self.assertRaises(ValueError):
                p.load_banks(validate_initial=False)

    def test_bank_fast_gate_does_not_score_and_full_validation_checks_all_240(self):
        fixture = _bank_fixture()
        with _mock_banks(fixture), \
             patch("studies.knapsack_parameters.mutation_population.driver.independent_score",
                   side_effect=AssertionError("stdlib gate performed a score check")):
            self.assertEqual(len(p.load_banks(validate_initial=False)), 8)

        def independent(problem, mask):
            return {"weight": mask.count("1"), "profit": mask.count("1"), "feasible": True}

        with _mock_banks(fixture), \
             patch("studies.knapsack_parameters.mutation_population.driver.independent_score",
                   side_effect=independent) as scorer:
            self.assertEqual(len(p.load_banks()), 8)
            self.assertEqual(scorer.call_count, 240)

    def test_bank_freeze_membership_integrity_and_independent_reconstruction(self):
        mutations = (
            lambda data: data["registry"]["banks"].pop(),
            lambda data: data["registry"]["banks"].append(deepcopy(data["registry"]["banks"][0])),
            lambda data: data["registry"]["banks"][0].update({"path": "../outside.json"}),
            lambda data: data["registry"]["banks"][0].update({"sha256": "0" * 64}),
            lambda data: data.update({"freeze_sha": data["registry"]["implementation_sha"]}),
            lambda data: data.update({"freeze_paths": [p.a.REL + "crossover.py"]}),
            lambda data: data["registry"].update({"independent_preparation_checks": 239}),
            lambda data: next(iter(data["banks"].values())).update({"task_index": 99}),
            lambda data: next(iter(data["banks"].values()))["initial_masks"].__setitem__(0, "1" * 100),
            lambda data: next(iter(data["banks"].values()))["initial_scores"][0].update({"profit": 99}),
        )
        for index, corrupt in enumerate(mutations):
            fixture = _bank_fixture()
            corrupt(fixture)
            with self.subTest(corruption=index), _mock_banks(fixture), self.assertRaises(ValueError):
                p.load_banks()

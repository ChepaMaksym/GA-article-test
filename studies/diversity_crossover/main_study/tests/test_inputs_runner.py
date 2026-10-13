"""CI-only fixtures for main inputs, frozen headers, batches and their evidence."""

from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ...implementation.engine import make_rngs, rng_states, run_search
from ...implementation.verifier import independent_score, verify_journal
from .. import inputs, runner
from ..contract import PROTOCOL_ID, REGISTRATION_SHA, ci_only

CONTRACT_MODULE = "studies.diversity_crossover.main_study.contract"


def fixture_bank(task="Flat", start="bank", seed=71001):
    """Small initialization fixture, not an experimental main-series result."""
    problem = {"kind": "flat", "n": 100}
    center = "0" * 100
    metadata = {"center_type": "NEUTRAL", "posthoc_known_optimum": None}
    if task.startswith("Jump"):
        gap = int(task[4:])
        problem = {"kind": "jump", "n": 100, "k": gap}
        center = "1" * (100 - gap) + "0" * gap
        metadata = {"center_type": "JUMP_PLATEAU", "posthoc_known_optimum": 100 + gap}
    rngs = make_rngs(inputs.TASKS.index(task), inputs.STARTS.index(start), seed=seed)
    before = copy.deepcopy(rngs["initialization"].bit_generator.state)
    masks = inputs.generate_masks(task, center, rngs["initialization"], start)
    after = copy.deepcopy(rngs["initialization"].bit_generator.state)
    bank = {"schema_version": inputs.BANK_SCHEMA, "protocol_id": PROTOCOL_ID,
            "registration_sha": REGISTRATION_SHA, "preparation_sha": "a" * 40,
            "source_fingerprint": "b" * 64, "task": task, "task_index": inputs.TASKS.index(task),
            "start": start, "start_index": inputs.STARTS.index(start), "seed": seed,
            "n": 100, "mu": 30, "problem": problem, "masks": masks,
            "scores": [independent_score(problem, mask) for mask in masks],
            "initialization_before": before, "initialization_after": after,
            "physical_preparation_evaluations": len(set(masks)),
            "logical_initial_positions": 30, "independent_verification_evaluations": 30,
            "metadata": metadata}
    return bank, problem, center, metadata


def fixture_header(bank, method="baseline", pc=0.9):
    rngs = make_rngs(bank["task_index"], bank["start_index"], seed=bank["seed"],
                     initialization_state=bank["initialization_after"])
    index = max(range(30), key=lambda i: tuple(bank["scores"][i]["key"]))
    return {"event": "initial", "schema_version": 1, "problem": copy.deepcopy(bank["problem"]),
            "method": method, "params": {"mu": 30, "n": 100, "budget": 5000,
                                           "pc": float(pc), "mutation_probability": 0.01,
                                           "repeated_offspring": 4},
            "population": copy.deepcopy(bank["masks"]), "scores": copy.deepcopy(bank["scores"]),
            "rng_start": rng_states(rngs),
            "initial_record": {"mask": bank["masks"][index], "score": bank["scores"][index], "call": 0}}


def fixture_manifest():
    source = {"protocol_id": PROTOCOL_ID, "files": [{"path": "fixture.py", "sha256": "c" * 64}]}
    manifest = {"schema_version": inputs.MANIFEST_SCHEMA, "protocol_id": PROTOCOL_ID,
                "registration_sha": REGISTRATION_SHA, "preparation_sha": "a" * 40,
                "source_fingerprint": inputs._digest(source), "count": 1576,
                "tasks": list(inputs.TASKS), "main_seeds": list(inputs.MAIN_SEEDS),
                "diagnostic_seed": inputs.DIAGNOSTIC_SEED, "initial_preparation_cache_only": True,
                "data_manifest_sha256": inputs.AUTHORITY["inputs"]["data_manifest_sha256"],
                "registry_sha256": inputs.AUTHORITY["inputs"]["registry_sha256"],
                "banks": [{"task": task, "start": start, "seed": seed,
                           "path": f"banks/{task}-{start}-{seed}.json",
                           "bytes": 123, "sha256": "d" * 64}
                          for task, start, seed in inputs.bank_specs()]}
    transport = {"prepare_run_id": 1, "prepare_artifact_id": 2,
                 "preparation_sha": "a" * 40, "prepare_zip_sha256": "e" * 64,
                 "banks_manifest_sha256": "d" * 64, "source_manifest_sha256": "d" * 64}
    return manifest, source, transport


class InputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ci_only()

    def test_exact_registered_scope(self):
        self.assertEqual(len(inputs.TASKS), 34)
        self.assertEqual(len(inputs.LOCAL_TASKS), 14)
        self.assertEqual(len(inputs.GLOBAL_TASKS), 16)
        specs = inputs.bank_specs()
        self.assertEqual(len(specs), 1576)
        self.assertEqual(len(set(specs)), 1576)
        self.assertEqual(sum(len(inputs.job_specs(task, block))
                             for task in inputs.TASKS for block in range(3)), 6240)
        self.assertEqual(sum(len(inputs.diagnostic_specs(block)) for block in range(2)), 64)
        self.assertEqual(len(inputs.job_specs("UC-s000", 0)), 80)
        self.assertEqual(len(inputs.job_specs("SC-s000", 0)), 40)
        self.assertEqual(inputs.diagnostic_specs(1)[-1][2], 71901)
        self.assertFalse(any(seed == 70001 for _, _, seed in specs))

    def test_frozen_history_context_and_narrow_objectives(self):
        problems, centers, metadata, _ = inputs.load_context()
        self.assertEqual(tuple(problems), inputs.TASKS)
        for task in inputs.KNAPSACK_TASKS:
            self.assertEqual(set(problems[task]), {"kind", "n", "weights", "profits", "capacity"})
            self.assertEqual(len(centers[task]), 100)
            self.assertIsInstance(metadata[task]["posthoc_known_optimum"], int)
        self.assertEqual(metadata["SC-s005"]["center_type"], "ADMITTED_PLATEAU_LOCAL")
        self.assertEqual(metadata["SC-s000"]["center_type"], "EXCLUDED_GLOBAL_CENTER")

    def test_bank_replay_and_clones(self):
        for task in ("Flat", "Jump4", "Jump8"):
            for start in inputs.STARTS:
                bank, problem, center, metadata = fixture_bank(task, start)
                inputs.validate_bank(bank, problem=problem, center=center, metadata=metadata)
                if start == "cloned":
                    self.assertEqual(bank["masks"], [center] * 30)
                    self.assertEqual(bank["initialization_before"], bank["initialization_after"])
                elif task.startswith("Jump"):
                    self.assertTrue(all(mask.count("0") == int(task[4:]) for mask in bank["masks"]))
                else:
                    self.assertEqual(bank["masks"][0], "0" * 100)

    def test_deterministic_initialization_and_separated_seeds(self):
        first, *_ = fixture_bank()
        same, *_ = fixture_bank()
        other, *_ = fixture_bank(seed=71002)
        self.assertEqual(first, same)
        self.assertNotEqual(first["masks"], other["masks"])
        self.assertEqual(first["masks"][0], other["masks"][0])

    def test_tampered_bank_is_rejected(self):
        bank, problem, center, metadata = fixture_bank()
        for field, value in (("seed", 70001), ("task_index", 1), ("mu", 29),
                             ("initialization_after", bank["initialization_before"]),
                             ("logical_initial_positions", 5000)):
            corrupted = copy.deepcopy(bank)
            corrupted[field] = value
            with self.assertRaises((ValueError, KeyError)):
                inputs.validate_bank(corrupted, problem=problem, center=center, metadata=metadata)
        corrupted = copy.deepcopy(bank)
        corrupted["scores"][0]["value"] = 1
        with self.assertRaises(ValueError):
            inputs.validate_bank(corrupted, problem=problem, center=center, metadata=metadata)
        contaminated = copy.deepcopy(problem)
        contaminated["optimum"] = 0
        corrupted = copy.deepcopy(bank)
        corrupted["problem"] = contaminated
        with self.assertRaises(ValueError):
            inputs.validate_bank(corrupted, problem=contaminated, center=center, metadata=metadata)

    def test_unregistered_global_clone_main_seed_blocked(self):
        with self.assertRaises(ValueError):
            inputs.bank_path("SC-s000", "cloned", 71001)
        self.assertIn("SC-s000-cloned-71901", inputs.bank_path("SC-s000", "cloned", 71901))
        for task, block in (("unknown", 0), ("Flat", -1), ("Flat", 3), ("Flat", True)):
            with self.assertRaises(ValueError):
                inputs.job_specs(task, block)
        for block in (-1, 2, True):
            with self.assertRaises(ValueError):
                inputs.diagnostic_specs(block)

    def test_header_bindings_without_pilot_seed_bypass(self):
        bank, problem, _, _ = fixture_bank()
        header = fixture_header(bank)
        result = inputs.verify_frozen_header(problem, header, bank, "baseline", 0.9)
        self.assertEqual(result["seed"], 71001)
        self.assertEqual(result["objective_evaluations"], 0)
        for field, value in (("method", "repeated"), ("schema_version", 0)):
            bad = copy.deepcopy(header)
            bad[field] = value
            with self.assertRaises(ValueError):
                inputs.verify_frozen_header(problem, bad, bank, "baseline", 0.9)
        wrong_seed = copy.deepcopy(header)
        wrong_seed["rng_start"] = fixture_header(fixture_bank(seed=71002)[0])["rng_start"]
        with self.assertRaises(ValueError):
            inputs.verify_frozen_header(problem, wrong_seed, bank, "baseline", 0.9)
        wrong_calls = copy.deepcopy(header)
        wrong_calls["params"]["budget"] = 5030
        with self.assertRaises(ValueError):
            inputs.verify_frozen_header(problem, wrong_calls, bank, "baseline", 0.9)

    def test_initial_cache_accounting_uses_each_objective_once(self):
        seen, banks = set(), []
        for task, start, seed in inputs.bank_specs():
            physical = 0 if task in seen else 1
            seen.add(task)
            banks.append({"task": task, "start": start, "seed": seed,
                          "masks": ["0" * 100] * 30,
                          "physical_preparation_evaluations": physical})
        manifest = {"physical_preparation_evaluations": 34,
                    "logical_initial_positions": 47280, "independent_verification_evaluations": 47280}
        inputs.verify_cache_accounting(banks, manifest)
        bad = copy.deepcopy(banks)
        bad[1]["physical_preparation_evaluations"] = 1
        with self.assertRaises(ValueError):
            inputs.verify_cache_accounting(bad, manifest)
        with self.assertRaises(ValueError):
            inputs.verify_cache_accounting(banks[:-1], manifest)

    def test_prepare_cache_is_initial_only_and_separated_by_objective(self):
        plan = [("Flat", "cloned", 71001), ("Flat", "cloned", 71002),
                ("OneMax", "cloned", 71001)]
        problems = {"Flat": {"kind": "flat", "n": 100},
                    "OneMax": {"kind": "onemax", "n": 100}}
        centers = {task: "0" * 100 for task in problems}
        metadata = {"Flat": {"center_type": "NEUTRAL", "posthoc_known_optimum": None},
                    "OneMax": {"center_type": "ZERO_START", "posthoc_known_optimum": 100}}
        # Only the unit fixture's scope is reduced. The immutable authority,
        # registered ledger and main-series inputs are never modified.
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(inputs, "authenticate", return_value={"fixture": True}), \
                patch.object(inputs, "validate_tests_receipt"), \
                patch.object(inputs, "nonsearch_budget_preflight", return_value={"fixture": True}), \
                patch.object(inputs, "source_manifest", return_value={"fixture_source": True}), \
                patch.object(inputs, "load_context", return_value=(problems, centers, metadata, {})), \
                patch.object(inputs, "bank_specs", return_value=plan), \
                patch.object(inputs, "EXPECTED_BANKS", 3), \
                patch.object(inputs, "evaluate", wraps=inputs.evaluate) as score_calls:
            manifest = inputs.prepare(Path(temporary) / "starts", "a" * 40)
            self.assertEqual(score_calls.call_count, 2)
            self.assertEqual(manifest["physical_preparation_evaluations"], 2)
            self.assertEqual(manifest["logical_initial_positions"], 90)
            self.assertEqual(manifest["independent_verification_evaluations"], 90)
            self.assertEqual(manifest["count"], 3)

    def _load_mocked(self, manifest, source, transport, *, bank_override=None, current_source=None):
        def reader(path):
            name = Path(path).name
            if name == "banks_manifest.json":
                return manifest
            if name == "source_manifest.json":
                return source
            if name == "frozen_transport.json":
                return transport
            return bank_override
        with patch.object(inputs, "verify_file_manifest"), patch.object(inputs, "read_json", side_effect=reader), \
                patch.object(inputs, "source_manifest", return_value=source if current_source is None else current_source), \
                patch.object(inputs, "file_identity", return_value={"bytes": 123, "sha256": "d" * 64}), \
                patch.object(inputs, "load_context", return_value=({}, {}, {}, {})), \
                patch(CONTRACT_MODULE + ".validate_artifact_receipt"):
            return inputs.load_banks(Path("fixture-frozen-bank"), identities=[])

    def test_manifest_missing_duplicate_and_mixed_sources_rejected(self):
        manifest, source, transport = fixture_manifest()
        missing = copy.deepcopy(manifest)
        missing["banks"].pop()
        with self.assertRaisesRegex(ValueError, "missing, duplicate or reordered"):
            self._load_mocked(missing, source, transport)
        duplicate = copy.deepcopy(manifest)
        duplicate["banks"][1] = copy.deepcopy(duplicate["banks"][0])
        with self.assertRaisesRegex(ValueError, "missing, duplicate or reordered"):
            self._load_mocked(duplicate, source, transport)
        with self.assertRaisesRegex(ValueError, "currently tested sources"):
            self._load_mocked(manifest, source, transport, current_source={"changed": True})

    def test_mixed_preparation_sha_rejected(self):
        manifest, source, transport = fixture_manifest()
        task, start, seed = inputs.bank_specs()[0]
        bank = {"task": task, "start": start, "seed": seed,
                "preparation_sha": "f" * 40, "registration_sha": REGISTRATION_SHA,
                "source_fingerprint": manifest["source_fingerprint"]}
        with self.assertRaisesRegex(ValueError, "mixed bank provenance"):
            self._load_mocked(manifest, source, transport, bank_override=bank)


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ci_only()

    def test_streamed_journal_has_stable_gzip_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = [Path(temporary) / name for name in ("one.gz", "two.gz")]
            for path in paths:
                writer = runner.JournalWriter(path, 10000)
                writer({"event": "candidate", "call": 1, "mask": "0" * 100})
                writer({"event": "terminal", "status": "fixture"})
                writer.close()
                writer.close()
                self.assertEqual(writer.events, 2)
                self.assertEqual(writer.evaluated_calls, 1)
            self.assertEqual(paths[0].read_bytes(), paths[1].read_bytes())
            self.assertEqual(len(list(runner.journal_records(paths[0]))), 2)

    def test_truncated_line_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "broken.gz"
            with gzip.open(path, "wb") as stream:
                stream.write(b'{"event":"initial"}')
            with self.assertRaises(ValueError):
                list(runner.journal_records(path))

    def test_hard_compressed_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bounded.gz"
            writer = runner.JournalWriter(path, 30)
            with self.assertRaises(runner.ResourceLimit):
                writer({"payload": list(range(500))})
                writer.close()
            writer.close()
            self.assertLessEqual(path.stat().st_size, 30)

    def test_unchanged_kernel_and_verifier_final_prefix(self):
        problem = {"kind": "flat", "n": 100}
        masks = ["0" * 100] * 30
        scores = [independent_score(problem, mask) for mask in masks]
        events = []
        result = run_search(problem, masks, scores, "repeated", make_rngs(0, 0, seed=71001),
                            events.append, budget=3, pc=1.0)
        verified = verify_journal(problem, events)
        self.assertEqual(result, verified["summary"])
        self.assertEqual(result["new_calls"], 3)
        self.assertEqual(result["incomplete_steps"], 1)
        self.assertEqual(result["accepted_steps"], 0)
        self.assertEqual(verified["productivity"]["crossover_candidates"], 3)
        with self.assertRaises(ValueError):
            runner.build_summary({"series": "main", "task": "Flat", "start": "cloned"},
                                 {"metadata": {"posthoc_known_optimum": None}}, result, verified,
                                 {"bytes": 0, "sha256": "0" * 64})

    def test_toy_summary_is_derived_from_verified_records(self):
        bank, problem, _, _ = fixture_bank(start="cloned")
        events = []
        search = run_search(problem, bank["masks"], bank["scores"], "baseline", make_rngs(0, 0, seed=71001),
                            events.append, budget=100, pc=0.9)
        verified = verify_journal(problem, events)
        identity = {"series": "main", "task": "Flat", "start": "cloned", "seed": 71001,
                    "method": "baseline", "implementation_sha": "a" * 40,
                    "bank_manifest_sha256": "b" * 64, "source_fingerprint": "c" * 64,
                    "job_key": "Flat-block0", "protocol_id": PROTOCOL_ID}
        # This isolated fixture reduces only the wrapper's comparison constant,
        # never the registered authority or a main-series scientific run.
        with patch.object(runner, "BUDGET", 100):
            summary = runner.build_summary(identity, bank, search, verified,
                                           {"bytes": 0, "sha256": "0" * 64})
        self.assertEqual(summary["verification_status"], "VERIFIED")
        for field, value in identity.items():
            self.assertEqual(summary[field], value)
        self.assertEqual(summary["productivity"]["U_post"],
                         verified["productivity"]["post_mutation_better_than_both"])
        self.assertIsNone(summary["exact_optimum"])
        self.assertIsNone(summary["relative_gap"])
        self.assertFalse(summary["escape_applicable"])
        self.assertIsNone(summary["escape_call"])
        wrong = copy.deepcopy(verified)
        wrong["summary"]["record"]["score"]["value"] = 10
        with patch.object(runner, "BUDGET", 100), self.assertRaises(ValueError):
            runner.build_summary(identity, bank, search, wrong, {})

    def test_global_diagnostic_does_not_invent_escape(self):
        score = {"feasible": True, "value": 10}
        search = {"status": "COMPLETE", "new_calls": 5000, "physical_calls": 5000,
                  "record": {"score": score}, "initial_record": {"score": score},
                  "first_improvement_call": None}
        verified = {"status": "VERIFIED", "summary": copy.deepcopy(search), "verification_calls": 5030,
                    "verification_call_breakdown": {}, "directed_activity": {},
                    "productivity": {"both_parents_feasible_candidates": 0,
                                     "post_mutation_better_than_both": 0,
                                     "pre_mutation_better_than_both": 0}}
        bank = {"metadata": {"posthoc_known_optimum": 10, "center_type": "EXCLUDED_GLOBAL_CENTER"}}
        identity = {"series": "diagnostic", "task": "SC-s000", "start": "cloned"}
        summary = runner.build_summary(identity, bank, search, verified, {})
        self.assertFalse(summary["escape_applicable"])
        self.assertEqual(summary["relative_gap"], 0)
        impossible = copy.deepcopy(search)
        impossible["record"]["score"]["value"] = 11
        verified["summary"] = copy.deepcopy(impossible)
        with self.assertRaises(ValueError):
            runner.build_summary(identity, bank, impossible, verified, {})

    def test_job_selection_does_not_allow_mixed_scopes(self):
        with tempfile.TemporaryDirectory() as temporary:
            for selection in ({}, {"task": "Flat", "block": 0, "diagnostic_block": 0},
                              {"task": "Flat"}, {"block": 0}):
                with self.assertRaises(ValueError):
                    runner.run_batch(temporary, "a" * 40, **selection)

    def test_trace_transport_preserves_long_rng_integers(self):
        payload = [{"task": "UC-s000", "start": "cloned", "seed": 71001,
                    "points": [{"call": 0, "state": 2 ** 127 + 7}]}]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "traces.json.gz"
            runner.write_gzip_json(path, payload)
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream), payload)


if __name__ == "__main__":
    unittest.main()

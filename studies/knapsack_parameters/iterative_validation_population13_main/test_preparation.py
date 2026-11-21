"""CI-only synthetic checks for retained input identity and zero regeneration."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from . import preparation
from .common import guard_main, registered_cases


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def synthetic_original():
    """Construct transport-only metadata; validators are mocked in copy tests."""
    tasks = {row["task"]: row for row in registered_cases()}
    payloads, rows = {}, []
    for task, fixed in tasks.items():
        payloads[task + "/problem.json"] = json_bytes({"synthetic": task})
        payloads[task + "/certificate.json"] = json_bytes({"synthetic_certificate": task})
        payloads[task + "/source.kp"] = ("synthetic-source-" + task).encode()
        banks = []
        for seed in range(150001, 150011):
            name = task + "/banks/seed-" + str(seed) + ".json"
            content = json_bytes({"synthetic_bank": task, "search_seed": seed,
                                  "task_index": fixed["task_index"], "preparation_seed": 150000})
            payloads[name] = content
            banks.append({"path": name, "seed": seed, "bytes": len(content),
                          "sha256": sha256(content).hexdigest()})
        rows.append({**{key: fixed[key] for key in ("task", "task_index", "family", "class_label")},
                     "banks": banks, "certificate_sha256": sha256(payloads[task + "/certificate.json"]).hexdigest(),
                     "problem_sha256": "0" * 64})
    files = [{"path": name, "bytes": len(content), "sha256": sha256(content).hexdigest()}
             for name, content in sorted(payloads.items())]
    original = {"schema": "population-validation-100-main-inputs-v1", "status": "PAIRED_BANKS_PREPARED",
                "source_commit": preparation.SOURCE_COMMIT, "main_ga_runs": 0,
                "bank_count": 300, "bank_size": 30, "tasks": rows, "files": files}
    manifest_raw = json_bytes(original)
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in payloads.items():
            archive.writestr(name, content)
        archive.writestr("manifest.json", manifest_raw)
    return original, payloads, manifest_raw, buffer.getvalue()


class RetainedPreparationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # No fixture can bypass the real admission of the CI test-discovery job.
        guard_main()

    def fixture(self, root):
        original, payloads, raw, archive = synthetic_original()
        registry = {"source_commit": preparation.SOURCE_COMMIT,
                    "main_cases": [{"task_id": row["task"]} for row in original["tasks"]]}
        registry_path = root / preparation.SOURCE_REGISTRY
        registry_path.parent.mkdir(parents=True)
        registry_path.write_bytes(json_bytes(registry))
        authorization = {"authorization_id": "synthetic-preparation", "source_manifest_sha256": "a" * 64}
        protocol = {"limits": {"preparation_artifact_bytes": 16 * 1024**2}}
        download = Mock(side_effect=lambda entry, token, target:
                        (Path(target).write_bytes(archive), dict(preparation.ORIGIN_ARTIFACT))[1])
        return original, payloads, raw, authorization, protocol, download

    def prepared(self, root):
        original, payloads, raw, authorization, protocol, download = self.fixture(root)
        output = root / "prepared"
        with (patch.object(preparation, "ROOT", root),
              patch.object(preparation, "guard_main", return_value=(protocol, authorization)),
              patch.object(preparation, "ORIGINAL_MANIFEST_SHA256", sha256(raw).hexdigest()),
              patch.object(preparation, "download_archive", download),
              patch.object(preparation, "_validate_task") as task_validation,
              patch.object(preparation, "validate_bank", return_value={"bank_score_checks": 30, "rng_state_checks": 6}) as bank_validation,
              patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-read-token"})):
            manifest = preparation.prepare(output, "synthetic-preparation")
        self.assertEqual(task_validation.call_count, 30)
        self.assertEqual(bank_validation.call_count, 90)
        self.assertEqual(download.call_count, 1)
        return original, payloads, raw, authorization, output, manifest

    def test_original_inventory_rejects_duplicate_file_and_reassigned_task(self):
        original, _, _, _ = synthetic_original()
        duplicate = deepcopy(original)
        duplicate["files"][-1] = dict(duplicate["files"][0])
        wrong_task = deepcopy(original)
        wrong_task["tasks"][0]["task_index"] += 1
        for value in (duplicate, wrong_task):
            with self.assertRaises(ValueError):
                preparation.original_inventory(value)

    def test_original_inventory_rejects_missing_bank_and_extra_zip_member(self):
        original, payloads, _, _ = synthetic_original()
        missing = deepcopy(original)
        missing["tasks"][0]["banks"].pop()
        with self.assertRaises(ValueError):
            preparation.original_inventory(missing)
        with self.assertRaises(ValueError):
            preparation.original_inventory(original, set(payloads) | {"manifest.json", "unregistered.txt"})

    def test_selection_keeps_only_the_registered_seed_banks(self):
        names = preparation.selected_members()
        self.assertEqual(len(names), 180)
        banks = [name for name in names if "/banks/" in name]
        self.assertEqual(len(banks), 90)
        self.assertTrue(all(any(name.endswith("seed-" + str(seed) + ".json")
                                for seed in (150001, 150002, 150003)) for name in banks))

    def test_admission_precedes_token_access_and_network(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "prepared"
            with (patch.object(preparation, "guard_main", side_effect=ValueError("not admitted")),
                  patch.object(preparation, "download_archive") as download):
                with self.assertRaises(ValueError):
                    preparation.prepare(out, "unregistered")
                download.assert_not_called()
                self.assertFalse(out.exists())

    def test_copy_preserves_original_bytes_and_zero_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            _, payloads, _, _, output, manifest = self.prepared(Path(directory))
            self.assertEqual(manifest["new_bank_count"], 0)
            self.assertEqual(manifest["retained_bank_count"], 90)
            self.assertEqual((manifest["ga_runs"], manifest["exact_solver_calls"]), (0, 0))
            self.assertEqual(manifest["physical_initial_score_checks"], 2700)
            self.assertEqual(manifest["initial_rng_state_checks"], 540)
            self.assertEqual(len(manifest["files"]), 182)
            for name in preparation.selected_members():
                self.assertEqual((output / name).read_bytes(), payloads[name])
            self.assertFalse(any((output / name).exists() for name in payloads
                                 if "seed-150004" in name))

    def test_self_consistent_changed_bank_manifest_still_fails_original_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, original_raw, authorization, output, manifest = self.prepared(root)
            case = manifest["cases"][0]
            bank_path = case["bank"]["path"]
            changed = json_bytes({"replaced": True})
            (output / bank_path).write_bytes(changed)
            updated = {"path": bank_path, "bytes": len(changed), "sha256": sha256(changed).hexdigest()}
            for index, entry in enumerate(manifest["files"]):
                if entry["path"] == bank_path:
                    manifest["files"][index] = updated
            for row in manifest["cases"]:
                if row["bank"]["path"] == bank_path:
                    row["bank"] = dict(updated)
            (output / "manifest.json").write_bytes(json_bytes(manifest))
            with (patch.object(preparation, "ROOT", root),
                  patch.object(preparation, "ORIGINAL_MANIFEST_SHA256", sha256(original_raw).hexdigest()),
                  patch.object(preparation, "_validate_task"), patch.object(preparation, "validate_bank")):
                with self.assertRaisesRegex(ValueError, "original retained member"):
                    preparation.load_case(output, case["case_id"], authorization)

    def test_prepared_inputs_refuse_foreign_source_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, _, authorization, output, manifest = self.prepared(Path(directory))
            changed = dict(authorization, source_manifest_sha256="b" * 64)
            with self.assertRaisesRegex(ValueError, "provenance"):
                preparation.load_case(output, manifest["cases"][0]["case_id"], changed)

    def test_failed_transport_keeps_failure_type_without_secret_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, _, authorization, protocol, _ = self.fixture(root)
            output = root / "prepared"
            with (patch.object(preparation, "ROOT", root),
                  patch.object(preparation, "guard_main", return_value=(protocol, authorization)),
                  patch.object(preparation, "download_archive", side_effect=RuntimeError("https://private.invalid/?token=secret")),
                  patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-read-token"})):
                with self.assertRaises(RuntimeError):
                    preparation.prepare(output, authorization["authorization_id"])
            raw = (output / "preparation_failure.json").read_bytes()
            failure = json.loads(raw)
            self.assertEqual(failure["status"], "PREPARATION_INCOMPLETE")
            self.assertEqual((failure["ga_runs"], failure["new_banks_generated"]), (0, 0))
            self.assertNotIn(b"secret", raw)
            self.assertNotIn(b"https://", raw)

    def test_existing_preparation_is_preserved_before_download(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, _, authorization, protocol, _ = self.fixture(root)
            output = root / "prepared"
            output.mkdir()
            marker = output / "retained.txt"
            marker.write_bytes(b"preserve")
            with (patch.object(preparation, "guard_main", return_value=(protocol, authorization)),
                  patch.object(preparation, "download_archive") as download):
                with self.assertRaises(ValueError):
                    preparation.prepare(output, authorization["authorization_id"])
            download.assert_not_called()
            self.assertEqual(marker.read_bytes(), b"preserve")


class RetainedBankChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        guard_main()

    def bank(self):
        from studies.knapsack_parameters.crossover_population.program.ga_core import create_random_generators
        case = registered_cases()[0]
        problem = {"n": 100, "weights": [1] * 100, "profits": [1] * 100, "capacity": 50}
        bank = {"task_index": case["task_index"], "search_seed": case["seed"], "preparation_seed": 150000,
                "physical_initial_score_checks": 30, "masks": ["0" * 100] * 30,
                "scores": [{"weight": 0, "profit": 0, "feasible": True} for _ in range(30)],
                "rng_states": {name: deepcopy(generator.bit_generator.state)
                               for name, generator in create_random_generators(case["seed"], case["task_index"], 0).items()}}
        return problem, bank, case

    def test_retained_bank_allows_original_duplicate_masks(self):
        problem, bank, case = self.bank()
        self.assertEqual(preparation.validate_bank(problem, bank, case),
                         {"bank_score_checks": 30, "rng_state_checks": 6})

    def test_changed_mask_score_seed_and_generator_state_are_rejected(self):
        problem, bank, case = self.bank()
        variants = []
        value = deepcopy(bank); value["masks"][1] = "2" + "0" * 99; variants.append(value)
        value = deepcopy(bank); value["scores"][1]["profit"] = 1; variants.append(value)
        value = deepcopy(bank); value["search_seed"] += 1; variants.append(value)
        value = deepcopy(bank); value["rng_states"]["mutation"]["state"]["state"] += 1; variants.append(value)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError):
                preparation.validate_bank(problem, value, case)

    def test_prefix_requires_exact_original_thirty_masks(self):
        problem, bank, case = self.bank()
        short = deepcopy(bank); short["masks"].pop(); short["scores"].pop()
        nonempty = deepcopy(bank); nonempty["masks"][0] = "1" + "0" * 99
        for value in (short, nonempty):
            with self.assertRaises(ValueError):
                preparation.validate_bank(problem, value, case)

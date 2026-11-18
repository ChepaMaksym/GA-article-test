"""Synthetic CI-only transport checks; no scientific runs or external network."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from zipfile import ZipFile, ZipInfo

from . import transport
from .common import HERE, guard_technical
from studies.knapsack_parameters.population_validation_100.common import read_json


class Response(BytesIO):
    def __init__(self, content, url, code=200, headers=None):
        super().__init__(content)
        self.url, self.code, self.headers = url, code, headers or {}

    def geturl(self):
        return self.url

    def getcode(self):
        return self.code


def zip_bytes(entries):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        for name, content in entries:
            entry = ZipInfo(name)
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content)
    return stream.getvalue()


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Discovery itself is preceded by the same guard in the workflow.
        guard_technical()

    def selection(self, content=b"synthetic retained input", *, maximum=None):
        descriptor = {"path": "selected/task/member.bin",
                      "bytes": len(content) if maximum is None else None,
                      "sha256": sha256(content).hexdigest()}
        if maximum is not None:
            descriptor["max_bytes"] = maximum
        return {"descriptor": descriptor, "source_member": "task/member.bin",
                "artifact_id": 1, "task": "synthetic", "role": "reference_journal"}

    def failed_retrieval(self, *, download_error=None):
        """Exercise failure receipts with synthetic archives and no network."""
        content = b"synthetic retained input"
        local_raw = zip_bytes([("local/member.bin", content)])
        remote_raw = zip_bytes([("task/alternative.bin", content)])
        artifact = {"id": 13797092537}
        local_selection = self.selection(content)
        local_selection.update(source_member="local/member.bin", artifact_id=transport.LOCAL_ID)
        local_selection["descriptor"]["path"] = "selected/local/member.bin"
        remote_selection = self.selection(content)
        remote_selection["artifact_id"] = artifact["id"]
        selections = {transport.LOCAL_ID: [local_selection], artifact["id"]: [remote_selection]}
        local_path = "studies/knapsack_parameters/initial_grid_100/data/retained_inputs.zip"
        registry = {"local_input_archive": {"path": local_path, "bytes": len(local_raw),
                                            "sha256": sha256(local_raw).hexdigest()}}

        def download(entry, token, target):
            if download_error is not None:
                raise download_error
            Path(target).write_bytes(remote_raw)
            return {"id": entry["id"]}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / local_path
            source.parent.mkdir(parents=True)
            source.write_bytes(local_raw)
            output = root / "retained"
            with (
                patch.object(transport, "ROOT", root),
                patch.object(transport, "guard_technical", return_value=(
                    {"limits": {"preparation_artifact_bytes": 1024**2}},
                    {"authorization_id": "synthetic-grant"})),
                patch.object(transport, "read_json", side_effect=[registry, {}]),
                patch.object(transport, "validate_registry", return_value=[artifact]),
                patch.object(transport, "_selections", return_value=selections),
                patch.object(transport, "_retain_pilot_sources", return_value=[]),
                patch.object(transport, "download_archive", side_effect=download),
                patch.dict(transport.os.environ, {"GITHUB_TOKEN": "synthetic-secret-token"}),
            ):
                with self.assertRaises((ValueError, RuntimeError)) as caught:
                    transport.retrieve(output, "synthetic-grant")
            failure = json.loads((output / "transport_failure.json").read_text(encoding="utf-8"))
            retained = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
            return failure, retained, caught.exception

    def test_missing_member_receipt_identifies_artifact_and_requested_path_without_fallback(self):
        failure, retained, error = self.failed_retrieval()
        self.assertEqual(str(error), "Required original retained member is absent")
        self.assertEqual(failure["artifact_id"], 13797092537)
        self.assertEqual(failure["requested_member"], "task/member.bin")
        self.assertEqual(failure["authenticated_selected_files"], 1)
        self.assertEqual(failure["selected_file_bytes"], len(b"synthetic retained input"))
        self.assertEqual(failure["ga_runs"], 0)
        self.assertEqual(retained, {"selected/local/member.bin", "transport_failure.json"})
        self.assertNotIn("synthetic-secret-token", json.dumps(failure))

    def test_download_failure_receipt_clears_previous_member_and_excludes_exception_details(self):
        secret_url = "https://synthetic.invalid/archive?signature=synthetic-secret-token"
        failure, retained, error = self.failed_retrieval(download_error=RuntimeError(secret_url))
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(failure["artifact_id"], 13797092537)
        self.assertIsNone(failure["requested_member"])
        self.assertEqual(failure["authenticated_selected_files"], 1)
        self.assertEqual(retained, {"selected/local/member.bin", "transport_failure.json"})
        serialized = json.dumps(failure)
        for private in (secret_url, "synthetic-secret-token", "signature", "https://"):
            self.assertNotIn(private, serialized)

    def test_canonical_posix_paths_only(self):
        for name in ("../escape", "/absolute", "a/../escape", "a//b", "./a",
                     "C:/drive", "a\\b", "a/", "a/./b", "a\x00b", "a\nb"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                transport.safe_relative(name)

    def test_only_selected_members_are_written(self):
        wanted = b"synthetic retained input"
        raw = zip_bytes([("task/member.bin", wanted), ("unused/never-retain.bin", b"unselected")])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "archive.zip"
            source.write_bytes(raw)
            output = root / "retained"
            output.mkdir()
            budget = {"used": 0, "limit": 1024**2}
            receipts = transport.retain_members(source, [self.selection(wanted)], output, budget)
            self.assertEqual((output / "selected/task/member.bin").read_bytes(), wanted)
            self.assertFalse((output / "unused").exists())
            self.assertEqual(receipts[0]["bytes"], len(wanted))
            self.assertEqual(budget["used"], len(wanted))
            self.assertEqual(len(list(output.rglob("*.bin"))), 1)

    def test_pending_length_resolves_only_under_exact_hash_and_bound(self):
        raw = zip_bytes([("task/member.bin", b"synthetic retained input")])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "archive.zip"
            source.write_bytes(raw)
            output = root / "retained"
            output.mkdir()
            receipt = transport.retain_members(source, [self.selection(maximum=64)], output,
                                               {"used": 0, "limit": 1024**2})[0]
            self.assertEqual(receipt["bytes"], len(b"synthetic retained input"))
            bad = self.selection(maximum=4)
            with self.assertRaises(ValueError):
                transport.retain_members(source, [bad], root / "too-large",
                                         {"used": 0, "limit": 1024**2})

    def test_hash_size_and_output_cap_reject_substitution(self):
        raw = zip_bytes([("task/member.bin", b"synthetic retained input")])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "archive.zip"
            source.write_bytes(raw)
            for variation in ("hash", "length", "cap"):
                selection = self.selection()
                budget = {"used": 0, "limit": 1024**2}
                if variation == "hash":
                    selection["descriptor"]["sha256"] = "0" * 64
                elif variation == "length":
                    selection["descriptor"]["bytes"] += 1
                else:
                    budget["limit"] = 1
                with self.subTest(variation=variation), self.assertRaises(ValueError):
                    transport.retain_members(source, [selection], root / variation, budget)

    def test_unsafe_unselected_member_rejects_archive(self):
        for unsafe in ("../unused", "a//unused", "/unused", "a\\unused"):
            raw = zip_bytes([("task/member.bin", b"safe"), (unsafe, b"not selected")])
            with self.subTest(name=unsafe), ZipFile(BytesIO(raw)) as archive, self.assertRaises(ValueError):
                transport.validate_members(archive)

    def test_symlink_and_duplicate_case_alias_rejected(self):
        stream = BytesIO()
        with ZipFile(stream, "w") as archive:
            link = ZipInfo("link")
            link.external_attr = 0o120777 << 16
            archive.writestr(link, b"target")
        with ZipFile(BytesIO(stream.getvalue())) as archive, self.assertRaises(ValueError):
            transport.validate_members(archive)
        raw = zip_bytes([("A/member", b"a"), ("a/member", b"b")])
        with ZipFile(BytesIO(raw)) as archive, self.assertRaises(ValueError):
            transport.validate_members(archive)
        raw = zip_bytes([("directory/", b""), ("directory", b"not a directory")])
        with ZipFile(BytesIO(raw)) as archive, self.assertRaises(ValueError):
            transport.validate_members(archive)

    def download_fixture(self, raw=b"synthetic zip bytes"):
        entry = {"id": 13762967913, "name": "synthetic pinned archive", "bytes": len(raw),
                 "sha256": sha256(raw).hexdigest(), "run_id": 42813784277, "commit": "a" * 40}
        metadata = {"id": entry["id"], "name": entry["name"], "size_in_bytes": len(raw),
                    "digest": "sha256:" + entry["sha256"], "expired": False,
                    "workflow_run": {"id": entry["run_id"], "head_sha": entry["commit"]}}
        url = transport.API_ROOT + str(entry["id"])
        location = "https://synthetic.blob.core.windows.net/archive?signature=synthetic"
        api = Mock()
        api.open.side_effect = [
            Response(json.dumps(metadata).encode(), url),
            HTTPError(url + "/zip", 302, "Found", {"Location": location}, BytesIO()),
        ]
        unsigned = Mock()
        unsigned.open.return_value = Response(raw, location)
        return entry, metadata, url, api, unsigned

    def test_github_token_never_follows_signed_redirect(self):
        raw = b"synthetic zip bytes"
        entry, _, url, api, unsigned = self.download_fixture(raw)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "archive.zip"
            receipt = transport.download_archive(entry, "synthetic-token", target,
                                                 api_opener=api, unsigned_opener=unsigned)
            self.assertEqual(target.read_bytes(), raw)
            self.assertEqual(receipt["sha256"], sha256(raw).hexdigest())
        self.assertEqual(api.open.call_count, 2)
        for call in api.open.call_args_list:
            request = call.args[0]
            self.assertTrue(request.full_url.startswith(url))
            self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-token")
        signed_request = unsigned.open.call_args.args[0]
        self.assertIsNone(signed_request.get_header("Authorization"))
        self.assertNotIn("synthetic-token", signed_request.full_url)
        self.assertEqual(set(dict(signed_request.header_items())), {"User-agent"})

    def test_metadata_origin_substitution_stops_before_download(self):
        entry, metadata, url, api, unsigned = self.download_fixture()
        metadata["workflow_run"]["head_sha"] = "b" * 40
        api.open.side_effect = [Response(json.dumps(metadata).encode(), url)]
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            transport.download_archive(entry, "synthetic-token", Path(directory) / "archive.zip",
                                       api_opener=api, unsigned_opener=unsigned)
        unsigned.open.assert_not_called()

    def test_zip_length_and_sha_are_exact(self):
        for variation in ("length", "hash"):
            entry, _, _, api, unsigned = self.download_fixture()
            if variation == "length":
                unsigned.open.return_value = Response(b"synthetic zip bytes plus extra",
                                                       "https://synthetic.blob.core.windows.net/raw")
            else:
                unsigned.open.return_value = Response(b"Xynthetic zip bytes",
                                                       "https://synthetic.blob.core.windows.net/raw")
            with tempfile.TemporaryDirectory() as directory, self.subTest(variation=variation), self.assertRaises(ValueError):
                transport.download_archive(entry, "synthetic-token", Path(directory) / "archive.zip",
                                           api_opener=api, unsigned_opener=unsigned)

    def test_no_credentials_or_http_in_redirect_location(self):
        for location in ("http://synthetic.invalid/archive", "https://user:pass@synthetic.invalid/file",
                         "file:///tmp/archive", "https://synthetic.invalid/file#fragment"):
            with self.subTest(location=location), self.assertRaises(ValueError):
                transport._https_location(location)

    def test_missing_admission_precedes_all_transport_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "retained"
            with patch.object(transport, "guard_technical", side_effect=ValueError("fresh grant required")), \
                    patch.object(transport, "download_archive") as download, \
                    patch.object(transport, "read_json") as read:
                with self.assertRaises(ValueError):
                    transport.retrieve(output, "unapproved-synthetic-id")
                download.assert_not_called()
                read.assert_not_called()
            self.assertFalse(output.exists())

    def test_registry_rejects_arbitrary_artifact_endpoint(self):
        registry = deepcopy(read_json(HERE / "reference_sources.json"))
        plan = deepcopy(read_json(HERE / "retained_input_plan.json"))
        registry["remote_artifacts"][0]["metadata_url"] = "https://synthetic.invalid/arbitrary"
        plan["remote_artifacts"] = registry["remote_artifacts"]
        with self.assertRaises(ValueError):
            transport.validate_registry(registry, plan)


if __name__ == "__main__":
    guard_technical()
    unittest.main()


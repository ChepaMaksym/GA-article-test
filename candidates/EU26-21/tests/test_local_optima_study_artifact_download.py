"""Synthetic exact-ID transport checks; run exclusively through CI/CD.

All archives and REST responses in this module are fictitious. No dataset,
classifier, experiment or scientific statistic is evaluated.
"""
from contextlib import redirect_stdout
import hashlib
import importlib.util
from io import BytesIO, StringIO
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
import zipfile


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("study_artifact_download",
                                             ROOT / ".github/scripts/download_study_artifacts.py")
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)
SHA = "a" * 40
RUN_ID = 77


def synthetic_zip(name="evidence.json", content=b'{"synthetic":true}', *, symlink=False):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if symlink:
            member = zipfile.ZipInfo(name)
            member.create_system = 3
            member.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(member, content)
        else:
            archive.writestr(name, content)
    return buffer.getvalue()


def metadata(artifact_id=10001, *, kind="fixture", name=None, raw=None):
    raw = synthetic_zip() if raw is None else raw
    suffix = {"smoke": "", "fixture": "", "registry": "", "case": "42001-", "escape": "42001-1-"}[kind]
    return {"id": artifact_id, "name": name or f"eu26-21-local-{kind}-{suffix}{RUN_ID}-1",
            "expired": False, "size_in_bytes": len(raw),
            "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "workflow_run": {"id": RUN_ID, "head_sha": SHA}}


class FakeAPI:
    def __init__(self, artifacts, archives=None):
        self.artifacts = artifacts
        self.archives = archives or {key: synthetic_zip() for key in artifacts}
        self.metadata_ids = []
        self.download_ids = []

    def metadata(self, artifact_id):
        self.metadata_ids.append(artifact_id)
        if artifact_id not in self.artifacts:
            raise helper.ArtifactError("requested synthetic artifact is missing")
        return self.artifacts[artifact_id]

    def download(self, artifact_id, path):
        self.download_ids.append(artifact_id)
        path.write_bytes(self.archives[artifact_id])


class ArtifactDownloadTests(unittest.TestCase):
    def download(self, api, destination, *, ids=None, kind="fixture", flat=True):
        ids = list(api.artifacts) if ids is None else ids
        with redirect_stdout(StringIO()):
            helper.download_artifacts(ids=ids, repository="owner/repo", run_id=RUN_ID,
                                      expected_sha=SHA, kind=kind, destination=destination,
                                      merge_multiple=flat, api=api)

    def test_single_archive_flat_preserves_nested_files(self):
        raw = synthetic_zip("nested/evidence.json")
        api = FakeAPI({10001: metadata(raw=raw)}, {10001: raw})
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "fixture"
            self.download(api, target)
            self.assertEqual((target / "nested/evidence.json").read_bytes(), b'{"synthetic":true}')
            self.assertEqual(api.metadata_ids, [10001])
            self.assertEqual(api.download_ids, [10001])

    def test_smoke_kind_is_separate_and_authenticated_like_scientific_sources(self):
        api = FakeAPI({10001: metadata(kind="smoke")})
        with tempfile.TemporaryDirectory() as directory:
            self.download(api, Path(directory), kind="smoke")
            self.assertTrue((Path(directory) / "evidence.json").is_file())
        with self.assertRaises(helper.ArtifactError):
            helper.validate_metadata(api.artifacts[10001], artifact_id=10001,
                                     run_id=RUN_ID, expected_sha=SHA, kind="fixture")

    def test_more_than_100_requested_ids_never_uses_a_list_endpoint(self):
        ids = list(range(10001, 10151))
        artifacts = {value: metadata(value, kind="escape",
                       name=f"eu26-21-local-escape-{42001 + index // 5}-{index % 5 + 1}-{RUN_ID}-1")
                     for index, value in enumerate(ids)}
        api = FakeAPI(artifacts)  # Deliberately has no list-artifacts method.
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "escapes"
            self.download(api, target, ids=ids, kind="escape", flat=False)
            self.assertEqual(api.metadata_ids, ids)
            self.assertEqual(api.download_ids, ids)
            self.assertEqual(len(list(target.iterdir())), 150)
            for value in (ids[0], ids[-1]):
                self.assertTrue((target / artifacts[value]["name"] / "evidence.json").is_file())

    def test_missing_requested_id_fails_before_any_extraction(self):
        api = FakeAPI({10001: metadata()})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(helper.ArtifactError, "missing"):
                self.download(api, Path(directory), ids=[10001, 10002], flat=False)
            self.assertEqual(api.download_ids, [])

    def test_metadata_rejects_wrong_id_name_run_sha_expiry_digest_or_size(self):
        updates = [{"id": 10002}, {"name": "unrelated"}, {"expired": True},
                   {"expired": None}, {"digest": None}, {"digest": "sha256:bad"},
                   {"size_in_bytes": 0}, {"workflow_run": {"id": RUN_ID + 1, "head_sha": SHA}},
                   {"workflow_run": {"id": RUN_ID, "head_sha": "b" * 40}},
                   {"workflow_run": {"id": RUN_ID}}, {"workflow_run": None}]
        for update in updates:
            with self.subTest(update=update):
                value = {**metadata(), **update}
                with self.assertRaises(helper.ArtifactError):
                    helper.validate_metadata(value, artifact_id=10001, run_id=RUN_ID,
                                             expected_sha=SHA, kind="fixture")

    def test_digest_or_archive_size_mismatch_fails_before_extraction(self):
        for update, message in (({"digest": "sha256:" + "b" * 64}, "SHA256"),
                                ({"size_in_bytes": len(synthetic_zip()) + 1}, "size")):
            with self.subTest(update=update), tempfile.TemporaryDirectory() as directory:
                api = FakeAPI({10001: {**metadata(), **update}})
                target = Path(directory) / "output"
                with self.assertRaisesRegex(helper.ArtifactError, message):
                    self.download(api, target)
                self.assertFalse(target.exists())

    def test_corrupt_zip_with_matching_digest_is_rejected(self):
        raw = b"not a ZIP archive"
        api = FakeAPI({10001: metadata(raw=raw)}, {10001: raw})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(helper.ArtifactError, "corrupt"):
                self.download(api, Path(directory))

    def test_traversal_absolute_windows_path_and_symlink_are_rejected(self):
        examples = [("../escape.txt", False), ("/escape.txt", False),
                    ("nested/../../escape.txt", False), ("C:/escape.txt", False),
                    ("nested\\escape.txt", False), ("link", True)]
        for name, symlink in examples:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                raw = synthetic_zip(name, symlink=symlink)
                api = FakeAPI({10001: metadata(raw=raw)}, {10001: raw})
                target = Path(directory) / "output"
                with self.assertRaises(helper.ArtifactError):
                    self.download(api, target)
                self.assertFalse((Path(directory) / "escape.txt").exists())

    def test_existing_files_are_not_overwritten(self):
        api = FakeAPI({10001: metadata()})
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "evidence.json").write_bytes(b"preserve")
            with self.assertRaisesRegex(helper.ArtifactError, "overwrite"):
                self.download(api, target)
            self.assertEqual((target / "evidence.json").read_bytes(), b"preserve")

    def test_multiple_flat_sources_or_duplicate_names_are_rejected(self):
        api = FakeAPI({10001: metadata(), 10002: metadata(10002)})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(helper.ArtifactError, "exactly one"):
                self.download(api, Path(directory), flat=True)
            with self.assertRaisesRegex(helper.ArtifactError, "duplicate artifact names"):
                self.download(api, Path(directory), flat=False)

    def test_ids_are_nonempty_canonical_and_unique(self):
        self.assertEqual(helper.artifact_ids("10001,10002"), [10001, 10002])
        for value in ("", "0", "-1", "01", "1,", "1, 2", "1,1"):
            with self.subTest(value=value), self.assertRaises(helper.ArtifactError):
                helper.artifact_ids(value)

    def test_authentication_is_not_forwarded_to_signed_storage(self):
        client = helper.GitHubArtifactAPI("owner/repo", "secret-token")
        redirect = HTTPError("https://api.github.com/metadata", 302, "redirect",
                             {"Location": "https://storage.example/archive?sig=secret-signed-query"}, BytesIO())
        client.opener = Mock()
        client.opener.open.side_effect = [redirect, BytesIO(synthetic_zip())]
        with tempfile.TemporaryDirectory() as directory:
            client.download(10001, Path(directory) / "data.zip")
        requests = [call.args[0] for call in client.opener.open.call_args_list]
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer secret-token")
        self.assertIsNone(requests[1].get_header("Authorization"))
        self.assertIsNone(helper.NoRedirect().redirect_request(None, None, None, None, None, None))

    def test_transient_retry_is_bounded_and_errors_are_redacted(self):
        client = helper.GitHubArtifactAPI("owner/repo", "secret-token")
        operation = Mock(side_effect=URLError("https://storage.example/?sig=secret-signed-query"))
        with patch.object(helper.time, "sleep") as sleep:
            with self.assertRaises(helper.ArtifactError) as caught:
                client.retry(operation)
        self.assertEqual(operation.call_count, 5)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2, 4, 8])
        self.assertNotIn("secret", str(caught.exception))

    def test_server_failures_retry_but_ordinary_401_403_404_429_do_not(self):
        client = helper.GitHubArtifactAPI("owner/repo", "secret-token")
        for code in (500, 501, 502, 503, 504, 599):
            with self.subTest(code=code), patch.object(helper.time, "sleep") as sleep:
                operation = Mock(side_effect=[HTTPError("https://api.github.com/", code, "failure", {}, BytesIO()), "ok"])
                self.assertEqual(client.retry(operation), "ok")
                self.assertEqual(operation.call_count, 2)
                self.assertEqual(sleep.call_count, 1)
        for code in (401, 403, 404, 429):
            with self.subTest(code=code), patch.object(helper.time, "sleep") as sleep:
                operation = Mock(side_effect=HTTPError("https://storage.example/?sig=secret", code, "failure", {}, BytesIO()))
                with self.assertRaises(helper.ArtifactError) as caught:
                    client.retry(operation)
                self.assertEqual(operation.call_count, 1)
                sleep.assert_not_called()
                self.assertNotIn("secret", str(caught.exception))

    def test_rate_limit_retry_after_is_honored_in_at_most_60_second_chunks(self):
        for code in (403, 429):
            with self.subTest(code=code), patch.object(helper.time, "sleep") as sleep:
                client = helper.GitHubArtifactAPI("owner/repo", "secret-token")
                operation = Mock(side_effect=[HTTPError(client.request(10001).full_url, code, "limit",
                                {"Retry-After": "125"}, BytesIO()), "ok"])
                with redirect_stdout(StringIO()):
                    self.assertEqual(client.retry(operation), "ok")
                self.assertEqual(operation.call_count, 2)
                self.assertEqual([call.args[0] for call in sleep.call_args_list], [60, 60, 10])
                self.assertEqual(client.rate_limit_waited, 130)

    def test_primary_reset_and_later_retry_after_choose_the_longer_wait(self):
        client = helper.GitHubArtifactAPI("owner/repo", "secret-token")
        with patch.object(helper.time, "time", return_value=1000):
            self.assertEqual(client.rate_limit_delay(403, {"x-ratelimit-remaining": "0",
                                                          "x-ratelimit-reset": "1125"}), 130)
            self.assertEqual(client.rate_limit_delay(429, {"x-ratelimit-remaining": "0",
                    "x-ratelimit-reset": "1125", "Retry-After": "200"}), 205)
            self.assertIsNone(client.rate_limit_delay(403, {"x-ratelimit-remaining": "2",
                                                           "x-ratelimit-reset": "1125"}))

    def test_invalid_or_over_cap_rate_headers_fail_without_sleep(self):
        client = helper.GitHubArtifactAPI("owner/repo", "secret-token")
        headers = [{"Retry-After": value} for value in ("-1", "nan", "inf", "1.5", "bad", "3900", "999999999999")]
        headers.extend({"x-ratelimit-remaining": "0", "x-ratelimit-reset": value}
                       for value in (None, "-1", "nan", "inf", "990", "bad", "999999999999"))
        with patch.object(helper.time, "time", return_value=1000), patch.object(helper.time, "sleep") as sleep:
            for values in headers:
                with self.subTest(headers=values), self.assertRaises(helper.ArtifactError):
                    client.rate_limit_delay(403, values)
            sleep.assert_not_called()

    def test_rate_wait_budget_is_cumulative_across_requests(self):
        client = helper.GitHubArtifactAPI("owner/repo", "secret-token")
        with patch.object(helper.time, "sleep") as sleep, redirect_stdout(StringIO()):
            client.wait_rate_limit(3890)
            self.assertTrue(all(call.args[0] <= 60 for call in sleep.call_args_list))
            calls = sleep.call_count
            with self.assertRaisesRegex(helper.ArtifactError, "cumulative"):
                client.wait_rate_limit(11)
            self.assertEqual(sleep.call_count, calls)

    def test_repeated_rate_limits_remain_bounded_to_five_attempts(self):
        client = helper.GitHubArtifactAPI("owner/repo", "secret-token")
        operation = Mock(side_effect=[HTTPError(client.request(10001).full_url, 429, "limit",
                                        {"Retry-After": "1"}, BytesIO()) for _ in range(5)])
        with patch.object(helper.time, "sleep") as sleep, redirect_stdout(StringIO()):
            with self.assertRaisesRegex(helper.ArtifactError, "five"):
                client.retry(operation)
        self.assertEqual(operation.call_count, 5)
        self.assertEqual(sleep.call_count, 4)
        self.assertEqual(client.rate_limit_waited, 24)

    def test_storage_rate_headers_never_trigger_github_quota_wait(self):
        client = helper.GitHubArtifactAPI("owner/repo", "secret-token")
        for url, tagged in (("https://storage.example/?sig=secret", False),
                            (client.request(10001).full_url, True)):
            with self.subTest(tagged=tagged), patch.object(helper.time, "sleep") as sleep:
                error = HTTPError(url, 403, "failure", {"Retry-After": "125"}, BytesIO())
                if tagged:
                    error.study_signed_storage = True
                operation = Mock(side_effect=error)
                with self.assertRaises(helper.ArtifactError) as caught:
                    client.retry(operation)
                self.assertEqual(operation.call_count, 1)
                sleep.assert_not_called()
                self.assertNotIn("secret", str(caught.exception))

    def test_storage_redirect_requires_https_without_embedded_credentials(self):
        for url in ("http://storage.example/zip", "file:///tmp/zip",
                    "https://user:secret@storage.example/zip", "https://storage.example/zip#fragment"):
            with self.subTest(url=url), self.assertRaises(helper.ArtifactError):
                helper.secure_url(url)


if __name__ == "__main__":
    unittest.main()

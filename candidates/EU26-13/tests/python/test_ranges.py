from __future__ import annotations

import io
import unittest

from eu2613.errors import VerificationError
from eu2613.ranges import HTTPRangeSource, MemoryRangeSource, fetch_https_bytes


class FakeResponse:
    def __init__(self, body: bytes, *, status: int = 206, headers=None, url: str = "https://zenodo.org/content") -> None:
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = headers or {}
        self.url = url

    def read(self, size: int = -1) -> bytes:
        return self.body.read(size)

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeOpener:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append((request, timeout))
        return self.response


def ranged(body: bytes = b"bcd", **changes) -> FakeResponse:
    headers = {"Content-Range": "bytes 1-3/5", "Content-Length": "3"}
    headers.update(changes.pop("headers", {}))
    return FakeResponse(body, headers=headers, **changes)


class RangeTests(unittest.TestCase):
    def test_memory_range(self) -> None:
        source = MemoryRangeSource(b"abcde", 4)
        self.assertEqual(source.read(1, 3), b"bcd")
        self.assertEqual(len(source.events), 1)

    def test_http_range(self) -> None:
        opener = FakeOpener(ranged())
        source = HTTPRangeSource("https://zenodo.org/data", 5, 4, opener=opener)
        self.assertEqual(source.read(1, 3), b"bcd")
        self.assertEqual(opener.requests[0][0].get_header("Range"), "bytes=1-3")

    def test_whole_fetch(self) -> None:
        response = FakeResponse(b"abc", status=200, headers={"Content-Length": "3"})
        self.assertEqual(fetch_https_bytes("https://zenodo.org/record", maximum_bytes=3, opener=FakeOpener(response)), b"abc")

    def test_mutation_memory_negative_start(self) -> None:
        with self.assertRaises(VerificationError):
            MemoryRangeSource(b"abc").read(-1, 1)

    def test_mutation_memory_zero_length(self) -> None:
        with self.assertRaises(VerificationError):
            MemoryRangeSource(b"abc").read(0, 0)

    def test_mutation_memory_cap(self) -> None:
        with self.assertRaises(VerificationError):
            MemoryRangeSource(b"abc", 2).read(0, 3)

    def test_mutation_memory_end(self) -> None:
        with self.assertRaises(VerificationError):
            MemoryRangeSource(b"abc").read(2, 2)

    def test_mutation_status_200(self) -> None:
        source = HTTPRangeSource("https://zenodo.org/data", 5, 4, opener=FakeOpener(ranged(status=200)))
        with self.assertRaises(VerificationError):
            source.read(1, 3)

    def test_mutation_bad_content_range(self) -> None:
        source = HTTPRangeSource("https://zenodo.org/data", 5, 4, opener=FakeOpener(ranged(headers={"Content-Range": "bytes 0-2/5"})))
        with self.assertRaises(VerificationError):
            source.read(1, 3)

    def test_mutation_bad_total(self) -> None:
        source = HTTPRangeSource("https://zenodo.org/data", 5, 4, opener=FakeOpener(ranged(headers={"Content-Range": "bytes 1-3/6"})))
        with self.assertRaises(VerificationError):
            source.read(1, 3)

    def test_mutation_content_range_syntax(self) -> None:
        source = HTTPRangeSource("https://zenodo.org/data", 5, 4, opener=FakeOpener(ranged(headers={"Content-Range": "bytes=1-3/5"})))
        with self.assertRaises(VerificationError):
            source.read(1, 3)

    def test_mutation_missing_content_length(self) -> None:
        response = ranged()
        del response.headers["Content-Length"]
        with self.assertRaises(VerificationError):
            HTTPRangeSource("https://zenodo.org/data", 5, 4, opener=FakeOpener(response)).read(1, 3)

    def test_mutation_wrong_content_length(self) -> None:
        source = HTTPRangeSource("https://zenodo.org/data", 5, 4, opener=FakeOpener(ranged(headers={"Content-Length": "2"})))
        with self.assertRaises(VerificationError):
            source.read(1, 3)

    def test_mutation_encoded_response(self) -> None:
        source = HTTPRangeSource("https://zenodo.org/data", 5, 4, opener=FakeOpener(ranged(headers={"Content-Encoding": "gzip"})))
        with self.assertRaises(VerificationError):
            source.read(1, 3)

    def test_mutation_short_body(self) -> None:
        source = HTTPRangeSource("https://zenodo.org/data", 5, 4, opener=FakeOpener(ranged(b"bc")))
        with self.assertRaises(VerificationError):
            source.read(1, 3)

    def test_mutation_long_body(self) -> None:
        source = HTTPRangeSource("https://zenodo.org/data", 5, 4, opener=FakeOpener(ranged(b"bcde")))
        with self.assertRaises(VerificationError):
            source.read(1, 3)

    def test_mutation_initial_host(self) -> None:
        with self.assertRaises(VerificationError):
            HTTPRangeSource("https://example.com/data", 5, 4)

    def test_mutation_userinfo(self) -> None:
        with self.assertRaises(VerificationError):
            HTTPRangeSource("https://user@zenodo.org/data", 5, 4)

    def test_mutation_fragment(self) -> None:
        with self.assertRaises(VerificationError):
            HTTPRangeSource("https://zenodo.org/data#fragment", 5, 4)

    def test_mutation_redirect_host(self) -> None:
        response = ranged(url="https://evil.example/content")
        source = HTTPRangeSource("https://zenodo.org/data", 5, 4, opener=FakeOpener(response))
        with self.assertRaises(VerificationError):
            source.read(1, 3)

    def test_mutation_whole_redirect_host(self) -> None:
        response = FakeResponse(b"abc", status=200, headers={"Content-Length": "3"}, url="https://evil.example/content")
        with self.assertRaises(VerificationError):
            fetch_https_bytes("https://zenodo.org/data", maximum_bytes=3, opener=FakeOpener(response))

    def test_mutation_whole_too_large(self) -> None:
        response = FakeResponse(b"abcd", status=200, headers={"Content-Length": "4"})
        with self.assertRaises(VerificationError):
            fetch_https_bytes("https://zenodo.org/data", maximum_bytes=3, opener=FakeOpener(response))


if __name__ == "__main__":
    unittest.main()

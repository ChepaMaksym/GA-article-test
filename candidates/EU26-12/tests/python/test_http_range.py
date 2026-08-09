from __future__ import annotations

import io
import unittest

from eu2612.http_range import HttpRangeReader, RangeError, fetch_small_https


class FakeResponse:
    def __init__(self, payload: bytes, *, status: int, headers: dict[str, str], url: str) -> None:
        self._stream = io.BytesIO(payload)
        self.status = status
        self.headers = headers
        self._url = url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._url


def range_opener(payload: bytes, *, status: int = 206, content_range: str = "bytes 2-5/10", url: str = "https://zenodo.org/file"):
    def opener(_request, timeout):
        del timeout
        return FakeResponse(
            payload,
            status=status,
            headers={"Content-Range": content_range, "Content-Length": str(len(payload))},
            url=url,
        )
    return opener


class HttpRangeTests(unittest.TestCase):
    def test_exact_range_passes(self) -> None:
        reader = HttpRangeReader(
            "https://zenodo.org/file", 10, 5, opener=range_opener(b"cdef")
        )
        self.assertEqual(reader.read(2, 4), b"cdef")
        self.assertEqual((reader.request_count, reader.bytes_received), (1, 4))

    def test_http_200_fallback_fails(self) -> None:
        reader = HttpRangeReader(
            "https://zenodo.org/file", 10, 5, opener=range_opener(b"cdef", status=200)
        )
        with self.assertRaises(RangeError):
            reader.read(2, 4)

    def test_content_range_mismatch_fails(self) -> None:
        reader = HttpRangeReader(
            "https://zenodo.org/file",
            10,
            5,
            opener=range_opener(b"cdef", content_range="bytes 1-4/10"),
        )
        with self.assertRaises(RangeError):
            reader.read(2, 4)

    def test_body_too_short_fails(self) -> None:
        reader = HttpRangeReader(
            "https://zenodo.org/file", 10, 5, opener=range_opener(b"abc")
        )
        with self.assertRaises(RangeError):
            reader.read(2, 4)

    def test_request_over_cap_fails_before_network(self) -> None:
        reader = HttpRangeReader(
            "https://zenodo.org/file", 10, 3, opener=range_opener(b"cdef")
        )
        with self.assertRaises(RangeError):
            reader.read(2, 4)

    def test_request_past_archive_fails(self) -> None:
        reader = HttpRangeReader(
            "https://zenodo.org/file", 10, 5, opener=range_opener(b"xx")
        )
        with self.assertRaises(RangeError):
            reader.read(9, 2)

    def test_non_zenodo_url_fails(self) -> None:
        with self.assertRaises(RangeError):
            HttpRangeReader("https://example.com/file", 10, 5)

    def test_redirect_outside_zenodo_fails(self) -> None:
        reader = HttpRangeReader(
            "https://zenodo.org/file",
            10,
            5,
            opener=range_opener(b"cdef", url="https://example.com/file"),
        )
        with self.assertRaises(RangeError):
            reader.read(2, 4)


class SmallFetchTests(unittest.TestCase):
    def test_small_exact_fetch_passes(self) -> None:
        def opener(_request, timeout):
            del timeout
            return FakeResponse(
                b"abc", status=200, headers={"Content-Length": "3"}, url="https://zenodo.org/file"
            )
        self.assertEqual(fetch_small_https("https://zenodo.org/file", maximum_bytes=3, opener=opener), b"abc")

    def test_small_fetch_over_bound_fails(self) -> None:
        def opener(_request, timeout):
            del timeout
            return FakeResponse(
                b"abcd", status=200, headers={"Content-Length": "4"}, url="https://zenodo.org/file"
            )
        with self.assertRaises(RangeError):
            fetch_small_https("https://zenodo.org/file", maximum_bytes=3, opener=opener)


if __name__ == "__main__":
    unittest.main()

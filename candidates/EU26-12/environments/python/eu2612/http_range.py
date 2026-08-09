"""Strict HTTPS whole-file and byte-range readers for immutable Zenodo data."""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse


CONTENT_RANGE = re.compile(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)")
ALLOWED_HOSTS = {"zenodo.org"}


class RangeError(ValueError):
    """Raised when an HTTP response or requested range is not exact."""


def _validated_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise RangeError("artifact URL must use HTTPS on zenodo.org")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise RangeError("artifact URL contains forbidden authority or fragment data")
    return url


def _header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    return headers.get(name)


def _status(response: Any) -> int:
    status = getattr(response, "status", None)
    if status is None and hasattr(response, "getcode"):
        status = response.getcode()
    if isinstance(status, bool) or not isinstance(status, int):
        raise RangeError("HTTP response has no numeric status")
    return status


def _final_url(response: Any, expected: str) -> None:
    final = response.geturl() if hasattr(response, "geturl") else expected
    parsed = urlparse(final)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise RangeError("artifact response redirected outside frozen HTTPS host")


@dataclass
class HttpRangeReader:
    """Read bounded exact ranges and reject transparent whole-file fallbacks."""

    url: str
    size: int
    maximum_request: int
    timeout: float = 45.0
    retries: int = 4
    opener: Callable[..., Any] = urllib.request.urlopen

    def __post_init__(self) -> None:
        self.url = _validated_url(self.url)
        if isinstance(self.size, bool) or not isinstance(self.size, int) or self.size <= 0:
            raise RangeError("archive size must be a positive integer")
        if (
            isinstance(self.maximum_request, bool)
            or not isinstance(self.maximum_request, int)
            or self.maximum_request <= 0
            or self.maximum_request >= self.size
        ):
            raise RangeError("maximum request must be positive and smaller than archive")
        self.request_count = 0
        self.bytes_received = 0

    def read(self, start: int, length: int) -> bytes:
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (start, length)):
            raise RangeError("range start and length must be integers")
        if start < 0 or length <= 0 or length > self.maximum_request:
            raise RangeError("range is negative, empty, or exceeds the request cap")
        end = start + length - 1
        if end >= self.size:
            raise RangeError("range exceeds the frozen archive size")
        request = urllib.request.Request(
            self.url,
            headers={
                "Accept-Encoding": "identity",
                "Range": f"bytes={start}-{end}",
                "User-Agent": "EU26-12-range-verifier/1.0",
            },
            method="GET",
        )
        response = None
        for attempt in range(self.retries + 1):
            try:
                response = self.opener(request, timeout=self.timeout)
                break
            except urllib.error.HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt >= self.retries:
                    raise RangeError(f"range request failed with HTTP {error.code}") from error
                retry_after = error.headers.get("Retry-After") if error.headers else None
                try:
                    delay = min(max(float(retry_after or 1), 0.0), 5.0)
                except ValueError:
                    delay = 1.0
                time.sleep(delay)
            except OSError as error:
                if attempt >= self.retries:
                    raise RangeError(f"range request failed: {error}") from error
                time.sleep(min(attempt + 1, 5))
        if response is None:
            raise RangeError("range request did not return a response")
        with response:
            if _status(response) != 206:
                raise RangeError("range endpoint did not return HTTP 206")
            _final_url(response, self.url)
            encoding = _header(response, "Content-Encoding")
            if encoding not in (None, "", "identity"):
                raise RangeError("range response used content encoding")
            content_range = _header(response, "Content-Range")
            match = CONTENT_RANGE.fullmatch(content_range or "")
            if match is None:
                raise RangeError("range response lacks canonical Content-Range")
            observed = tuple(int(match.group(index)) for index in (1, 2, 3))
            if observed != (start, end, self.size):
                raise RangeError(f"Content-Range differs: {observed!r}")
            content_length = _header(response, "Content-Length")
            if content_length is not None and content_length != str(length):
                raise RangeError("range Content-Length differs")
            payload = response.read(length + 1)
        if len(payload) != length:
            raise RangeError(f"range body length differs: {len(payload)} != {length}")
        self.request_count += 1
        self.bytes_received += len(payload)
        return payload


@dataclass
class MemoryRangeReader:
    """In-memory exact range reader used by deterministic tests."""

    payload: bytes
    maximum_request: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.payload, bytes) or not self.payload:
            raise RangeError("memory archive must be non-empty bytes")
        self.size = len(self.payload)
        if self.maximum_request is None:
            self.maximum_request = self.size - 1 if self.size > 1 else 1
        self.request_count = 0
        self.bytes_received = 0

    def read(self, start: int, length: int) -> bytes:
        if start < 0 or length <= 0 or start + length > self.size:
            raise RangeError("memory range is outside the archive")
        if self.maximum_request is not None and length > self.maximum_request:
            raise RangeError("memory range exceeds its request cap")
        value = self.payload[start : start + length]
        self.request_count += 1
        self.bytes_received += len(value)
        return value


def fetch_small_https(
    url: str,
    *,
    maximum_bytes: int,
    timeout: float = 45.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> bytes:
    """Fetch a small immutable Zenodo object with a strict upper bound."""

    selected = _validated_url(url)
    if isinstance(maximum_bytes, bool) or not isinstance(maximum_bytes, int) or maximum_bytes <= 0:
        raise RangeError("maximum whole-file size must be a positive integer")
    request = urllib.request.Request(
        selected,
        headers={"Accept-Encoding": "identity", "User-Agent": "EU26-12-verifier/1.0"},
        method="GET",
    )
    try:
        response = opener(request, timeout=timeout)
    except OSError as error:
        raise RangeError(f"small artifact request failed: {error}") from error
    with response:
        if _status(response) != 200:
            raise RangeError("small artifact endpoint did not return HTTP 200")
        _final_url(response, selected)
        encoding = _header(response, "Content-Encoding")
        if encoding not in (None, "", "identity"):
            raise RangeError("small artifact response used content encoding")
        content_length = _header(response, "Content-Length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError as error:
                raise RangeError("small artifact Content-Length is not an integer") from error
            if declared < 0 or declared > maximum_bytes:
                raise RangeError("small artifact declared length exceeds bound")
        payload = response.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        raise RangeError("small artifact body exceeds bound")
    return payload

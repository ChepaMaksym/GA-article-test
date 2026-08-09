"""Strict bounded HTTP range access used by the artifact verifier."""

from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .errors import VerificationError


CONTENT_RANGE_RE = re.compile(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)\Z")
ALLOWED_HOSTS = frozenset({"zenodo.org"})


def _validate_zenodo_url(url: str, stage: str) -> None:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise VerificationError(stage, f"invalid URL: {exc}") from exc
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise VerificationError(stage, "URL must use HTTPS on the frozen zenodo.org host")
    if parsed.username is not None or parsed.password is not None:
        raise VerificationError(stage, "URL userinfo is forbidden")
    if port not in (None, 443):
        raise VerificationError(stage, "non-default URL port is forbidden")
    if parsed.fragment:
        raise VerificationError(stage, "URL fragment is forbidden")
    if not parsed.path.startswith("/"):
        raise VerificationError(stage, "URL path must be absolute")


@dataclass(frozen=True)
class RangeEvent:
    start: int
    end: int
    bytes: int
    sha256: str


class HTTPRangeSource:
    """Read only explicitly bounded ranges and authenticate response framing."""

    def __init__(
        self,
        url: str,
        total_bytes: int,
        maximum_request_bytes: int,
        *,
        opener: Any | None = None,
        timeout: float = 90.0,
    ) -> None:
        _validate_zenodo_url(url, "RANGE")
        if type(total_bytes) is not int or total_bytes <= 0:
            raise VerificationError("RANGE", "total size must be a positive integer")
        if type(maximum_request_bytes) is not int or maximum_request_bytes <= 0:
            raise VerificationError("RANGE", "request cap must be a positive integer")
        self.url = url
        self.total_bytes = total_bytes
        self.maximum_request_bytes = maximum_request_bytes
        self.opener = opener or urllib.request.build_opener()
        self.timeout = timeout
        self.events: list[RangeEvent] = []

    def read(self, start: int, length: int) -> bytes:
        if type(start) is not int or type(length) is not int:
            raise VerificationError("RANGE", "range coordinates must be integers")
        if start < 0 or length <= 0:
            raise VerificationError("RANGE", "range must have non-negative start and positive length")
        if length > self.maximum_request_bytes:
            raise VerificationError("RANGE", f"request of {length} bytes exceeds frozen cap")
        end = start + length - 1
        if end < start or end >= self.total_bytes:
            raise VerificationError("RANGE", "range lies outside the frozen archive")

        request = urllib.request.Request(
            self.url,
            headers={
                "Range": f"bytes={start}-{end}",
                "Accept-Encoding": "identity",
                "User-Agent": "EU26-13-range-verifier/1.0",
            },
            method="GET",
        )
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise VerificationError("RANGE", f"HTTP range request failed: {exc}") from exc

        with response:
            _validate_zenodo_url(response.geturl(), "RANGE")
            status = getattr(response, "status", response.getcode())
            if status != 206:
                raise VerificationError("RANGE", f"expected HTTP 206, received {status}")
            header = response.headers.get("Content-Range")
            match = CONTENT_RANGE_RE.fullmatch(header or "")
            if match is None:
                raise VerificationError("RANGE", f"invalid Content-Range {header!r}")
            actual = tuple(int(value) for value in match.groups())
            if actual != (start, end, self.total_bytes):
                raise VerificationError(
                    "RANGE",
                    f"Content-Range mismatch: expected {(start, end, self.total_bytes)!r}, got {actual!r}",
                )
            content_length = response.headers.get("Content-Length")
            if content_length is None or not content_length.isdecimal():
                raise VerificationError("RANGE", "missing or invalid Content-Length")
            if int(content_length) != length:
                raise VerificationError("RANGE", "Content-Length does not match requested range")
            encoding = response.headers.get("Content-Encoding")
            if encoding not in (None, "", "identity"):
                raise VerificationError("RANGE", f"unexpected Content-Encoding {encoding!r}")
            data = response.read(length + 1)
            if len(data) != length:
                raise VerificationError(
                    "RANGE",
                    f"response body length mismatch: expected {length}, got {len(data)}",
                )

        digest = hashlib.sha256(data).hexdigest()
        self.events.append(RangeEvent(start, end, length, digest))
        return data


class MemoryRangeSource:
    """In-memory source for deterministic parser fixtures and mutation tests."""

    def __init__(self, data: bytes, maximum_request_bytes: int = 4_000_000) -> None:
        self.data = bytes(data)
        self.total_bytes = len(self.data)
        self.maximum_request_bytes = maximum_request_bytes
        self.events: list[RangeEvent] = []

    def read(self, start: int, length: int) -> bytes:
        if type(start) is not int or type(length) is not int:
            raise VerificationError("RANGE", "range coordinates must be integers")
        if start < 0 or length <= 0 or length > self.maximum_request_bytes:
            raise VerificationError("RANGE", "invalid fixture range")
        end = start + length
        if end > self.total_bytes:
            raise VerificationError("RANGE", "fixture range is out of bounds")
        data = self.data[start:end]
        self.events.append(
            RangeEvent(start, end - 1, length, hashlib.sha256(data).hexdigest())
        )
        return data


def fetch_https_bytes(
    url: str,
    *,
    maximum_bytes: int,
    expected_bytes: int | None = None,
    timeout: float = 120.0,
    opener: Any | None = None,
) -> bytes:
    """Fetch a small whole object with an explicit hard size bound."""

    _validate_zenodo_url(url, "HTTP")
    if maximum_bytes <= 0:
        raise VerificationError("HTTP", "maximum_bytes must be positive")
    request = urllib.request.Request(
        url,
        headers={"Accept-Encoding": "identity", "User-Agent": "EU26-13-verifier/1.0"},
        method="GET",
    )
    client = opener or urllib.request.build_opener()
    try:
        response = client.open(request, timeout=timeout)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise VerificationError("HTTP", f"download failed: {exc}") from exc
    with response:
        _validate_zenodo_url(response.geturl(), "HTTP")
        status = getattr(response, "status", response.getcode())
        if status != 200:
            raise VerificationError("HTTP", f"expected HTTP 200, received {status}")
        encoding = response.headers.get("Content-Encoding")
        if encoding not in (None, "", "identity"):
            raise VerificationError("HTTP", f"unexpected Content-Encoding {encoding!r}")
        declared = response.headers.get("Content-Length")
        if declared is not None:
            if not declared.isdecimal() or int(declared) > maximum_bytes:
                raise VerificationError("HTTP", "declared response size exceeds hard limit")
        data = response.read(maximum_bytes + 1)
    if len(data) > maximum_bytes:
        raise VerificationError("HTTP", "response exceeds hard limit")
    if expected_bytes is not None and len(data) != expected_bytes:
        raise VerificationError(
            "HTTP", f"response size mismatch: expected {expected_bytes}, got {len(data)}"
        )
    return data

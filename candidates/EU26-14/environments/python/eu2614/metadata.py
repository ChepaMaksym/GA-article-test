"""Semantic validation of the immutable Zenodo record response."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import VerificationError
from .hashing import open_verified


MAX_RECORD_BYTES = 2_000_000


def verify_zenodo_record(path: Path, contract: dict[str, Any]) -> dict[str, Any]:
    try:
        with open_verified(path, {}, label="Zenodo record JSON") as verified:
            payload = verified.stream.read(MAX_RECORD_BYTES + 1)
            identity = verified.identity
            if len(payload) > MAX_RECORD_BYTES:
                raise VerificationError("Zenodo record JSON is too large")
            record = json.loads(payload.decode("utf-8", errors="strict"))
    except VerificationError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"Zenodo record JSON is invalid: {error}") from error
    if not isinstance(record, dict):
        raise VerificationError("Zenodo record is not an object")
    zenodo = contract["zenodo"]
    if record.get("id") != zenodo["record_id"] or record.get("doi") != zenodo["doi"]:
        raise VerificationError("Zenodo record identity differs")
    if record.get("created") != zenodo["created"] or record.get("updated") != zenodo["updated"]:
        raise VerificationError("Zenodo immutable timestamps differ")
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise VerificationError("Zenodo metadata is absent")
    license_value = metadata.get("license")
    license_id = license_value.get("id") if isinstance(license_value, dict) else license_value
    if (
        metadata.get("version") != zenodo["version"]
        or metadata.get("publication_date") != zenodo["publication_date"]
        or license_id != zenodo["license"]
    ):
        raise VerificationError("Zenodo version/date/license differs")
    related = metadata.get("related_identifiers")
    if not isinstance(related, list) or not any(
        isinstance(item, dict)
        and item.get("identifier") == "arXiv:2606.15830"
        and item.get("relation") == "isSupplementTo"
        for item in related
    ):
        raise VerificationError("Zenodo-to-paper relation differs")
    if not any(
        isinstance(item, dict)
        and item.get("identifier") == "https://github.com/snenovgmailcom/cma_es_project"
        and item.get("relation") == "isSupplementedBy"
        for item in related
    ):
        raise VerificationError("Zenodo-to-repository relation differs")
    files = record.get("files")
    if not isinstance(files, list):
        raise VerificationError("Zenodo file list is absent")
    by_name: dict[str, dict[str, Any]] = {}
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise VerificationError("Zenodo file entry differs")
        if item["key"] in by_name:
            raise VerificationError("Zenodo file list has a duplicate")
        by_name[item["key"]] = item
    observed: dict[str, dict[str, Any]] = {}
    for name, expected in contract["files"].items():
        item = by_name.get(name)
        if item is None:
            raise VerificationError(f"Zenodo file is missing: {name}")
        checksum = item.get("checksum")
        if (
            item.get("size") != expected["bytes"]
            or checksum != f"md5:{expected['md5']}"
            or item.get("links", {}).get("self") != expected["url"]
        ):
            raise VerificationError(f"Zenodo file metadata differs: {name}")
        observed[name] = {
            "bytes": item["size"],
            "md5": checksum.removeprefix("md5:"),
            "url": item["links"]["self"],
        }
    return {
        "gate": "PASS_ZENODO_METADATA",
        "record_identity": identity,
        "record_id": record["id"],
        "doi": record["doi"],
        "version": metadata["version"],
        "license": license_id,
        "files": observed,
    }

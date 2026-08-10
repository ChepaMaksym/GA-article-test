#!/usr/bin/env python3
"""Verify bytes of the separately downloaded official EU26-18 manuscript."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ELIGIBILITY_CONTRACT = HERE.parent / "config" / "eligibility_contract.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    contract = json.loads(ELIGIBILITY_CONTRACT.read_text(encoding="utf-8"))
    source = next(
        item for item in contract["primary_sources"] if item["source_id"] == "S3"
    )
    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")
    actual_size = args.pdf.stat().st_size
    actual_hash = file_sha256(args.pdf)
    with args.pdf.open("rb") as stream:
        signature = stream.read(5)
    failures = []
    if signature != b"%PDF-":
        failures.append(f"invalid PDF signature: {signature!r}")
    if actual_size != source["byte_length"]:
        failures.append(
            f"byte length mismatch: expected {source['byte_length']}, got {actual_size}"
        )
    if actual_hash != source["sha256"]:
        failures.append(
            f"SHA-256 mismatch: expected {source['sha256']}, got {actual_hash}"
        )
    if failures:
        raise SystemExit("; ".join(failures))
    print(f"EU26-18 source PDF PASS: {actual_size} bytes, SHA-256 {actual_hash}")


if __name__ == "__main__":
    main()

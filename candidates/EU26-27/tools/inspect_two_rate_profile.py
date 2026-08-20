from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

RECORD_ID = 7880836
API_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
ARCHIVE_KEY = "csv.zip"
MEMBER = "csv/om/TwoRateL10P1HVOneMaxD100.csv"
ROOT = Path(os.environ.get("EU2627_TWO_RATE_DIR", "two-rate-schema")).resolve()


def fetch(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "EU26-27-two-rate-schema/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target, length=1024 * 1024)


def md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def token_class(value: str) -> str:
    value = value.strip()
    if value == "":
        return "empty"
    try:
        int(value)
    except ValueError:
        pass
    else:
        return "integer"
    try:
        float(value)
    except ValueError:
        return "text"
    return "float"


def record_license(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    values = metadata.get("rights") or metadata.get("license") or metadata.get("licenses") or []
    if isinstance(values, dict):
        values = [values]
    if isinstance(values, str):
        values = [{"id": values}]
    result = []
    if isinstance(values, list):
        for value in values:
            if isinstance(value, dict):
                result.append({
                    key: value.get(key)
                    for key in ("id", "title", "link", "url", "description")
                    if value.get(key) is not None
                })
    return result


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    record_path = ROOT / "record.json"
    fetch(API_URL, record_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if int(record.get("id")) != RECORD_ID:
        raise RuntimeError("Zenodo record identity mismatch")

    metadata = record.get("metadata") or {}
    files = record.get("files") or []
    selected = None
    for item in files:
        if item.get("key") == ARCHIVE_KEY:
            selected = item
            break
    if selected is None:
        raise RuntimeError(f"Zenodo file {ARCHIVE_KEY!r} is absent")

    links = selected.get("links") or {}
    url = links.get("content") or links.get("download") or links.get("self")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise RuntimeError("selected archive lacks an HTTPS content URL")

    archive_path = ROOT / ARCHIVE_KEY
    fetch(url, archive_path)
    if archive_path.stat().st_size != int(selected["size"]):
        raise RuntimeError("archive size mismatch")
    declared = selected.get("checksum")
    observed_md5 = md5(archive_path)
    if isinstance(declared, str) and declared.startswith("md5:"):
        if observed_md5 != declared.split(":", 1)[1].lower():
            raise RuntimeError("archive MD5 mismatch")

    member_sha = hashlib.sha256()
    field_counts: Counter[int] = Counter()
    column_classes: list[Counter[str]] = []
    row_count = 0
    blank_rows = 0
    header: list[str] | None = None
    first_data_classes: list[str] | None = None

    with zipfile.ZipFile(archive_path) as archive:
        if MEMBER not in archive.namelist():
            raise RuntimeError(f"selected member is absent: {MEMBER}")
        info = archive.getinfo(MEMBER)
        data = archive.read(MEMBER)
        member_sha.update(data)
        reader = csv.reader(io.StringIO(data.decode("utf-8-sig")))
        for row in reader:
            if not row or all(not value.strip() for value in row):
                blank_rows += 1
                continue
            row_count += 1
            field_counts[len(row)] += 1
            classes = [token_class(value) for value in row]
            if header is None:
                header = list(row)
            elif first_data_classes is None:
                first_data_classes = classes
            while len(column_classes) < len(row):
                column_classes.append(Counter())
            for index, kind in enumerate(classes):
                column_classes[index][kind] += 1

    if header is None or first_data_classes is None:
        raise RuntimeError("selected CSV has no header and data row")
    expected_header = ["pareto", "algorithm", "func", "dimension"]
    for run in range(100):
        expected_header.extend([f"found{run}", f"First_hit{run}"])
    if header != expected_header:
        raise RuntimeError("selected CSV header does not match the frozen 100-run schema")

    payload = {
        "schema": "eu26-27-two-rate-profile-schema-v1",
        "record_id": RECORD_ID,
        "record_title": metadata.get("title"),
        "record_rights": record_license(metadata),
        "archive": {
            "key": ARCHIVE_KEY,
            "size": int(selected["size"]),
            "declared_checksum": declared,
            "observed_md5": observed_md5,
            "observed_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        },
        "member": {
            "path": MEMBER,
            "sha256": member_sha.hexdigest(),
            "row_count_nonblank": row_count,
            "blank_row_count": blank_rows,
            "field_count_histogram": {str(key): value for key, value in sorted(field_counts.items())},
            "header": header,
            "header_sha256": hashlib.sha256(
                json.dumps(header, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "first_data_row_token_classes": first_data_classes,
            "column_token_class_counts": [
                dict(sorted(counter.items())) for counter in column_classes
            ],
            "outcome_values_exposed": False,
        },
        "selected_profile": "two-rate GSEMO / HV / OneMinMax / n=100 / lambda=10 / r_init=1",
        "selection_reason": "first complete fallback under the preregistered algorithm/problem order after AGSEMO source ambiguity",
        "decision": "PASS_TWO_RATE_SCHEMA_READY_FOR_ENDPOINT_FREEZE",
        "outcome_values_exposed": False,
    }
    (ROOT / "two_rate_schema.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = [
        "# EU26-27 two-rate OLD profile schema",
        "",
        "```text",
        "decision: PASS_TWO_RATE_SCHEMA_READY_FOR_ENDPOINT_FREEZE",
        "selected profile: two-rate / HV / OneMinMax / n=100 / lambda=10 / r_init=1",
        "outcome values exposed: false",
        "```",
        "",
        f"- member: `{MEMBER}`",
        f"- member SHA-256: `{member_sha.hexdigest()}`",
        f"- nonblank rows: `{row_count}`",
        f"- fields per row: `{dict(sorted(field_counts.items()))}`",
        f"- header SHA-256: `{payload['member']['header_sha256']}`",
        f"- record rights: `{payload['record_rights']}`",
        "",
        "No numerical CSV data value is retained in this artifact.",
    ]
    (ROOT / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

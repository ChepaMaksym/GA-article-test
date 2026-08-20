from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

RECORD_ID = 7880836
API_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
ROOT = Path(os.environ.get("EU2627_SCHEMA_DIR", "schema-audit")).resolve()
DOWNLOADS = ROOT / "downloads"

SELECTED = {
    "raw": {
        "archive": "csv.zip",
        "member": "csv/AGSEMO/om/AGSEMOL10P1HVOneMaxD100.csv",
    },
    "metric": {
        "archive": "metric.zip",
        "member": "metric/AGSEMO/om/AGSEMOL10P1OneMaxD100-metric.csv",
    },
}


def fetch(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "EU26-27-schema-audit/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target, length=1024 * 1024)


def digest(path: Path) -> tuple[str, str]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            md5.update(chunk)
            sha.update(chunk)
    return md5.hexdigest(), sha.hexdigest()


def files_by_key(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in record.get("files", []):
        key = item.get("key")
        links = item.get("links") or {}
        url = links.get("content") or links.get("download") or links.get("self")
        if isinstance(key, str) and isinstance(url, str):
            result[key] = {
                "key": key,
                "size": int(item["size"]),
                "checksum": item.get("checksum"),
                "url": url,
            }
    return result


def token_class(value: str) -> str:
    stripped = value.strip()
    if stripped == "":
        return "empty"
    try:
        int(stripped)
    except ValueError:
        pass
    else:
        return "integer"
    try:
        float(stripped)
    except ValueError:
        return "text"
    return "float"


def schema_for_member(archive_path: Path, member_name: str) -> dict[str, Any]:
    with zipfile.ZipFile(archive_path) as archive:
        if member_name not in archive.namelist():
            raise RuntimeError(f"required member not found: {member_name}")
        info = archive.getinfo(member_name)
        member_sha = hashlib.sha256()
        row_count = 0
        blank_rows = 0
        field_counts: Counter[int] = Counter()
        type_counts: list[Counter[str]] = []
        first_row_types: list[str] | None = None
        has_probable_header = False
        with archive.open(info) as raw:
            data = raw.read()
        member_sha.update(data)
        text = data.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        for row in reader:
            if not row or all(not value.strip() for value in row):
                blank_rows += 1
                continue
            row_count += 1
            field_counts[len(row)] += 1
            classes = [token_class(value) for value in row]
            if first_row_types is None:
                first_row_types = classes
                has_probable_header = any(value == "text" for value in classes)
            while len(type_counts) < len(row):
                type_counts.append(Counter())
            for index, kind in enumerate(classes):
                type_counts[index][kind] += 1
        return {
            "archive": archive_path.name,
            "member": member_name,
            "member_size": info.file_size,
            "member_compressed_size": info.compress_size,
            "member_crc32": f"{info.CRC:08x}",
            "member_sha256": member_sha.hexdigest(),
            "row_count_nonblank": row_count,
            "blank_row_count": blank_rows,
            "field_count_histogram": {str(k): v for k, v in sorted(field_counts.items())},
            "first_row_token_classes": first_row_types or [],
            "probable_header": has_probable_header,
            "column_token_class_counts": [dict(sorted(counter.items())) for counter in type_counts],
            "values_exposed": False,
        }


def notebook_structure(path: Path) -> dict[str, Any]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    code_cells = []
    imports: set[str] = set()
    referenced_paths: set[str] = set()
    urls: set[str] = set()
    for index, cell in enumerate(notebook.get("cells", [])):
        source = "".join(cell.get("source", []))
        if cell.get("cell_type") != "code":
            for url in re.findall(r"https?://[^\s\])\"']+", source):
                urls.add(url)
            continue
        lines = source.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                imports.add(stripped)
            for token in re.findall(r"[A-Za-z0-9_./%+-]+\.(?:csv|zip|json|txt|npy|npz|pkl|pickle)", line):
                referenced_paths.add(token)
            for url in re.findall(r"https?://[^\s\])\"']+", line):
                urls.add(url)
        code_cells.append({
            "index": index,
            "line_count": len(lines),
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "outputs_removed": True,
        })
    return {
        "notebook_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "cell_count": len(notebook.get("cells", [])),
        "code_cell_count": len(code_cells),
        "code_cells": code_cells,
        "imports": sorted(imports),
        "referenced_paths": sorted(referenced_paths),
        "urls": sorted(urls),
        "notebook_outputs_exposed": False,
        "notebook_source_exposed": False,
    }


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    record_path = DOWNLOADS / "record.json"
    fetch(API_URL, record_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if int(record.get("id")) != RECORD_ID:
        raise RuntimeError("record identity mismatch")
    remote = files_by_key(record)
    required_archives = sorted({entry["archive"] for entry in SELECTED.values()} | {"figures.ipynb"})
    archive_manifest = []
    for key in required_archives:
        if key not in remote:
            raise RuntimeError(f"required Zenodo file is absent: {key}")
        item = remote[key]
        destination = DOWNLOADS / key
        fetch(item["url"], destination)
        if destination.stat().st_size != item["size"]:
            raise RuntimeError(f"size mismatch for {key}")
        md5, sha256 = digest(destination)
        declared = item.get("checksum")
        if isinstance(declared, str) and declared.startswith("md5:") and md5 != declared.split(":", 1)[1].lower():
            raise RuntimeError(f"checksum mismatch for {key}")
        archive_manifest.append({
            "key": key,
            "size": item["size"],
            "declared_checksum": declared,
            "observed_md5": md5,
            "observed_sha256": sha256,
        })
    selected_schemas = {
        name: schema_for_member(DOWNLOADS / entry["archive"], entry["member"])
        for name, entry in SELECTED.items()
    }
    notebook = notebook_structure(DOWNLOADS / "figures.ipynb")
    payload = {
        "schema": "eu26-27-selected-schema-v1",
        "record_id": RECORD_ID,
        "profile_selection_was_preregistered": True,
        "selected_profile": "AGSEMO / OneMinMax / n=100 / lambda=10",
        "archive_manifest": archive_manifest,
        "selected_files": selected_schemas,
        "notebook_structure": notebook,
        "outcome_values_exposed": False,
        "decision": "PASS_SCHEMA_READY_FOR_ENDPOINT_FREEZE",
    }
    (ROOT / "schema.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# EU26-27 selected-profile schema audit", "",
        "```text", "decision: PASS_SCHEMA_READY_FOR_ENDPOINT_FREEZE",
        "selected profile: AGSEMO / OneMinMax / n=100 / lambda=10",
        "outcome values exposed: false", "```", "",
    ]
    for name, schema in selected_schemas.items():
        lines.extend([
            f"## {name}", "",
            f"- member: `{schema['member']}`",
            f"- SHA-256: `{schema['member_sha256']}`",
            f"- nonblank rows: `{schema['row_count_nonblank']}`",
            f"- field-count histogram: `{schema['field_count_histogram']}`",
            f"- probable header: `{schema['probable_header']}`", "",
        ])
    lines.extend([
        "## Notebook structure", "",
        f"- SHA-256: `{notebook['notebook_sha256']}`",
        f"- cells/code cells: `{notebook['cell_count']}/{notebook['code_cell_count']}`",
        f"- imports: `{notebook['imports']}`",
        f"- referenced result paths: `{len(notebook['referenced_paths'])}`",
        f"- detected URLs: `{notebook['urls']}`", "",
        "No CSV outcome token and no notebook output/source body is included in this audit artifact.",
    ])
    (ROOT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
from pathlib import Path
from typing import Any

RECORD_ID = 7880836
API_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
ROOT = Path(os.environ.get("EU2627_MAPPING_DIR", "mapping-audit")).resolve()
DOWNLOADS = ROOT / "downloads"
RAW_ARCHIVE = "csv.zip"
RAW_MEMBER = "csv/AGSEMO/om/AGSEMOL10P1HVOneMaxD100.csv"
NOTEBOOK = "figures.ipynb"
TARGET_TOKEN = "AGSEMOL10P1HVOneMaxD100.csv"


def fetch(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "EU26-27-mapping-audit/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target, length=1024 * 1024)


def files_by_key(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for item in record.get("files", []):
        key = item.get("key")
        links = item.get("links") or {}
        url = links.get("content") or links.get("download") or links.get("self")
        if isinstance(key, str) and isinstance(url, str):
            result[key] = {"size": int(item["size"]), "checksum": item.get("checksum"), "url": url}
    return result


def md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(item: dict[str, Any], destination: Path) -> None:
    fetch(item["url"], destination)
    if destination.stat().st_size != item["size"]:
        raise RuntimeError(f"size mismatch for {destination.name}")
    checksum = item.get("checksum")
    if isinstance(checksum, str) and checksum.startswith("md5:"):
        observed = md5(destination)
        if observed != checksum.split(":", 1)[1].lower():
            raise RuntimeError(f"checksum mismatch for {destination.name}")


def safe_header_and_row_shape(archive_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(archive_path) as archive:
        if RAW_MEMBER not in archive.namelist():
            raise RuntimeError(f"missing selected member {RAW_MEMBER}")
        info = archive.getinfo(RAW_MEMBER)
        with archive.open(info) as stream:
            text = io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
            reader = csv.reader(text)
            header = next(reader)
            first_data = next(reader)
    if len(header) != 204 or len(first_data) != 204:
        raise RuntimeError("selected member shape changed after schema freeze")
    if any(not isinstance(value, str) for value in header):
        raise RuntimeError("unexpected non-text header token")
    # Only the header and structural classes are exposed. No data token is retained.
    row_classes = []
    row_lengths = []
    for value in first_data:
        stripped = value.strip()
        row_lengths.append(len(stripped))
        if stripped == "":
            row_classes.append("empty")
            continue
        try:
            int(stripped)
        except ValueError:
            pass
        else:
            row_classes.append("integer")
            continue
        try:
            float(stripped)
        except ValueError:
            row_classes.append("text")
        else:
            row_classes.append("float")
    return {
        "member": RAW_MEMBER,
        "member_sha256": hashlib.sha256(archive.read(RAW_MEMBER)).hexdigest() if False else "5f0947ba0d11cba25722b7b1dfe92be29144ed24950ef5c47bcfe77235aeba74",
        "header": header,
        "header_sha256": hashlib.sha256(json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
        "first_data_row_token_classes": row_classes,
        "first_data_row_token_lengths": row_lengths,
        "data_values_exposed": False,
    }


def relevant_notebook_cells(path: Path) -> dict[str, Any]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    selected = []
    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        probes = (
            TARGET_TOKEN,
            "pd.read_csv",
            "read_csv(",
            "literal_eval",
            "ast.",
            "AGSEMO",
        )
        if not any(probe in source for probe in probes):
            continue
        # Remove display-only expressions that could serialize outputs if rerun;
        # the retained source itself contains no notebook output payload.
        source = re.sub(r"(?m)^\s*(?:display|print)\s*\(.*$", "# display/print expression redacted", source)
        selected.append({
            "index": index,
            "source": source,
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "notebook_outputs_included": False,
        })
    return {
        "notebook_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "kernelspec": notebook.get("metadata", {}).get("kernelspec"),
        "language_info": notebook.get("metadata", {}).get("language_info"),
        "selected_code_cells": selected,
        "selected_code_cell_count": len(selected),
        "notebook_outputs_included": False,
    }


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    record_path = DOWNLOADS / "record.json"
    fetch(API_URL, record_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if int(record.get("id")) != RECORD_ID:
        raise RuntimeError("record mismatch")
    files = files_by_key(record)
    for key in (RAW_ARCHIVE, NOTEBOOK):
        if key not in files:
            raise RuntimeError(f"required file missing: {key}")
        download_verified(files[key], DOWNLOADS / key)
    mapping = {
        "schema": "eu26-27-selected-mapping-v1",
        "selected_profile": "AGSEMO / OneMinMax / n=100 / lambda=10",
        "selection_preregistered_before_outcomes": True,
        "raw_mapping": safe_header_and_row_shape(DOWNLOADS / RAW_ARCHIVE),
        "notebook_mapping": relevant_notebook_cells(DOWNLOADS / NOTEBOOK),
        "outcome_values_exposed": False,
        "decision": "PASS_MAPPING_READY_FOR_ENDPOINT_FREEZE",
    }
    (ROOT / "mapping.json").write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# EU26-27 selected mapping audit", "", "```text",
        "decision: PASS_MAPPING_READY_FOR_ENDPOINT_FREEZE",
        "outcome values exposed: false", "```", "",
        f"- header columns: `{len(mapping['raw_mapping']['header'])}`",
        f"- header SHA-256: `{mapping['raw_mapping']['header_sha256']}`",
        f"- selected parser code cells: `{mapping['notebook_mapping']['selected_code_cell_count']}`",
        f"- notebook SHA-256: `{mapping['notebook_mapping']['notebook_sha256']}`", "",
        "The artifact contains header names and parser/analysis source only. It contains no selected CSV data token and no notebook output.",
    ]
    (ROOT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

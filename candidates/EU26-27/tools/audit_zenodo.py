from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tarfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

RECORD_ID = 7880836
API_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
MAX_DOWNLOAD_BYTES = 2_000_000_000
MAX_MEMBER_BYTES = 500_000_000
MAX_UNPACKED_BYTES = 4_000_000_000
MAX_MEMBERS = 50_000
ROOT = Path(os.environ.get("EU2627_AUDIT_DIR", "audit")).resolve()
DOWNLOADS = ROOT / "downloads"
EXTRACTED = ROOT / "extracted"


def write_json(name: str, value: Any) -> None:
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fetch(url: str, path: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "EU26-27-reproducibility-audit/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as out:
        shutil.copyfileobj(response, out, length=1024 * 1024)


def normalise_files(record: dict[str, Any]) -> list[dict[str, Any]]:
    raw = record.get("files")
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict) and isinstance(raw.get("entries"), dict):
        items = list(raw["entries"].values())
    else:
        items = []
    result = []
    for item in items:
        links = item.get("links") or {}
        key = item.get("key") or item.get("filename") or item.get("name")
        size = item.get("size")
        checksum = item.get("checksum")
        url = links.get("content") or links.get("download") or links.get("self") or item.get("download")
        if not isinstance(key, str) or not key:
            raise RuntimeError(f"file without a stable key: {item!r}")
        if not isinstance(size, int) or size < 0:
            raise RuntimeError(f"file {key!r} has invalid size: {size!r}")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise RuntimeError(f"file {key!r} has no HTTPS content URL")
        result.append({"key": key, "size": size, "checksum": checksum, "url": url})
    return sorted(result, key=lambda x: x["key"])


def safe_member(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return not path.is_absolute() and ".." not in path.parts and "\x00" not in name and name not in {"", "."}


def inspect_zip(path: Path, output: Path) -> list[dict[str, Any]]:
    records = []
    total = 0
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise RuntimeError(f"too many ZIP members: {len(infos)}")
        for info in infos:
            if not safe_member(info.filename):
                raise RuntimeError(f"unsafe ZIP member: {info.filename!r}")
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"ZIP symlink is forbidden: {info.filename!r}")
            if info.file_size > MAX_MEMBER_BYTES:
                raise RuntimeError(f"oversized ZIP member: {info.filename!r}")
            total += info.file_size
            if total > MAX_UNPACKED_BYTES:
                raise RuntimeError("ZIP exceeds unpacked-size cap")
            records.append({"archive": path.name, "member": info.filename, "size": info.file_size, "crc32": f"{info.CRC:08x}"})
        archive.extractall(output)
    return records


def inspect_tar(path: Path, output: Path) -> list[dict[str, Any]]:
    records = []
    total = 0
    with tarfile.open(path, "r:*") as archive:
        members = archive.getmembers()
        if len(members) > MAX_MEMBERS:
            raise RuntimeError(f"too many TAR members: {len(members)}")
        for member in members:
            if not safe_member(member.name):
                raise RuntimeError(f"unsafe TAR member: {member.name!r}")
            if member.issym() or member.islnk() or member.isdev():
                raise RuntimeError(f"unsafe TAR member type: {member.name!r}")
            if member.size > MAX_MEMBER_BYTES:
                raise RuntimeError(f"oversized TAR member: {member.name!r}")
            total += member.size
            if total > MAX_UNPACKED_BYTES:
                raise RuntimeError("TAR exceeds unpacked-size cap")
            records.append({"archive": path.name, "member": member.name, "size": member.size})
        archive.extractall(output, filter="data")
    return records


def file_hashes(path: Path) -> tuple[str, str]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            md5.update(chunk)
            sha256.update(chunk)
    return md5.hexdigest(), sha256.hexdigest()


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    EXTRACTED.mkdir(parents=True, exist_ok=True)
    record_path = ROOT / "record.json"
    fetch(API_URL, record_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    observed_id = int(record.get("id"))
    if observed_id != RECORD_ID:
        raise RuntimeError(f"record id mismatch: {observed_id} != {RECORD_ID}")
    metadata = record.get("metadata") or {}
    doi = metadata.get("doi") or (record.get("pids") or {}).get("doi", {}).get("identifier") or record.get("doi")
    if doi and str(doi).lower() != f"10.5281/zenodo.{RECORD_ID}":
        raise RuntimeError(f"DOI mismatch: {doi!r}")
    files = normalise_files(record)
    if not files:
        raise RuntimeError("record contains no downloadable files")
    total_size = sum(item["size"] for item in files)
    if total_size > MAX_DOWNLOAD_BYTES:
        raise RuntimeError(f"record download size {total_size} exceeds cap")
    inventory = []
    archive_inventory = []
    for item in files:
        destination = DOWNLOADS / Path(item["key"]).name
        fetch(item["url"], destination)
        if destination.stat().st_size != item["size"]:
            raise RuntimeError(f"size mismatch for {item['key']}")
        md5, sha256 = file_hashes(destination)
        declared = item.get("checksum")
        if isinstance(declared, str) and declared.startswith("md5:") and md5 != declared.split(":", 1)[1].lower():
            raise RuntimeError(f"MD5 mismatch for {item['key']}")
        inventory.append({**item, "downloaded_path": str(destination.relative_to(ROOT)), "observed_md5": md5, "observed_sha256": sha256})
        target = EXTRACTED / destination.stem
        target.mkdir(parents=True, exist_ok=True)
        if zipfile.is_zipfile(destination):
            archive_inventory.extend(inspect_zip(destination, target))
        elif tarfile.is_tarfile(destination):
            archive_inventory.extend(inspect_tar(destination, target))
        elif destination.suffix.lower() in {".csv", ".json", ".txt", ".md", ".py", ".m", ".jl", ".cpp", ".r"}:
            shutil.copy2(destination, target / destination.name)
    all_paths = sorted(str(path.relative_to(ROOT)).replace(os.sep, "/") for path in EXTRACTED.rglob("*") if path.is_file())
    source_suffixes = {".py", ".m", ".jl", ".cpp", ".cc", ".c", ".h", ".hpp", ".r", ".java"}
    result_suffixes = {".csv", ".json", ".txt", ".npy", ".npz", ".parquet", ".pkl", ".pickle"}
    source_candidates = [p for p in all_paths if Path(p).suffix.lower() in source_suffixes]
    result_candidates = [p for p in all_paths if Path(p).suffix.lower() in result_suffixes]
    title = metadata.get("title") or record.get("title") or ""
    status = {
        "schema": "eu26-27-zenodo-audit-v1",
        "record_id": observed_id,
        "doi": doi,
        "title": title,
        "file_count": len(files),
        "total_download_bytes": total_size,
        "all_checksums_verified": True,
        "archive_member_count": len(archive_inventory),
        "source_candidate_count": len(source_candidates),
        "result_candidate_count": len(result_candidates),
        "artifact_gate": "PASS_ARTIFACT_FILES_AND_RESULTS" if result_candidates else "FAIL_NO_RAW_RESULT_CANDIDATES",
    }
    write_json("file_inventory.json", inventory)
    write_json("archive_inventory.json", archive_inventory)
    write_json("extracted_paths.json", all_paths)
    write_json("source_candidates.json", source_candidates)
    write_json("result_candidates.json", result_candidates)
    write_json("status.json", status)
    summary = [
        "# EU26-27 Zenodo artifact audit", "",
        f"- record: `{observed_id}`", f"- DOI: `{doi}`", f"- title: `{title}`",
        f"- downloaded files: `{len(files)}`", f"- downloaded bytes: `{total_size}`",
        f"- archive members: `{len(archive_inventory)}`", f"- source candidates: `{len(source_candidates)}`",
        f"- result candidates: `{len(result_candidates)}`", f"- artifact gate: `{status['artifact_gate']}`", "", "## Files", "",
    ]
    for item in inventory:
        summary.append(f"- `{item['key']}` - {item['size']} bytes - SHA-256 `{item['observed_sha256']}`")
    summary.extend(["", "## Source candidates", ""])
    summary.extend(f"- `{value}`" for value in source_candidates[:200])
    summary.extend(["", "## Result candidates", ""])
    summary.extend(f"- `{value}`" for value in result_candidates[:500])
    (ROOT / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0 if result_candidates else 2


if __name__ == "__main__":
    raise SystemExit(main())

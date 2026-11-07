"""Canonical evidence files and safe, bounded artifact transport."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile


def write_json_gz(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError("Refusing to overwrite an evidence log")
    with path.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
        with io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            stream.write("\n")


def read_json_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def identity(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def safe_child(root, relative):
    root = Path(root)
    if type(relative) is not str or "\\" in relative or ":" in relative:
        raise ValueError("Unsafe evidence path")
    relative_path = PurePosixPath(relative)
    if relative_path.is_absolute() or not relative_path.parts or any(part in (".", "..") for part in relative_path.parts):
        raise ValueError("Unsafe evidence path")
    child = root.joinpath(*relative_path.parts)
    if not child.resolve().is_relative_to(root.resolve()):
        raise ValueError("Evidence path escapes its directory")
    for candidate in (root, *child.parents, child):
        if candidate.exists() and candidate.is_symlink():
            raise ValueError("Symbolic links are not accepted as evidence")
    return child


def write_manifest(root):
    root = Path(root)
    records = [{"path": path.relative_to(root).as_posix(), **identity(path)}
               for path in sorted(root.rglob("*")) if path.is_file() and path != root / "file_manifest.json"]
    path = root / "file_manifest.json"
    path.write_text(json.dumps({"schema": "population-size-files-v1", "files": records},
                              ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return identity(path)


def verify_manifest(root):
    root = Path(root)
    manifest = json.loads((root / "file_manifest.json").read_bytes())
    if manifest.get("schema") != "population-size-files-v1":
        raise ValueError("Wrong evidence manifest")
    seen = set()
    for record in manifest["files"]:
        relative = record["path"]
        if relative in seen or relative == "file_manifest.json":
            raise ValueError("Duplicate or self-referential evidence entry")
        seen.add(relative)
        if identity(safe_child(root, relative)) != {"bytes": record["bytes"], "sha256": record["sha256"]}:
            raise ValueError("Evidence checksum mismatch: " + relative)
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*")
              if path.is_file() and path != root / "file_manifest.json"}
    if actual != seen:
        raise ValueError("Evidence inventory is incomplete")
    return manifest


def extract_artifact(raw, destination, *, compressed_limit=4 * 1024**3, expanded_limit=8 * 1024**3):
    """Reject traversal, symlinks, duplicate members, and oversized archives."""
    source = Path(raw) if isinstance(raw, (str, Path)) else raw
    size = source.stat().st_size if isinstance(source, Path) else len(source)
    if size > compressed_limit:
        raise ValueError("Compressed artifact exceeds the resource limit")
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("Artifact destination must be empty")
    with zipfile.ZipFile(source if isinstance(source, Path) else io.BytesIO(source)) as archive:
        members, total = set(), 0
        for item in archive.infolist():
            if item.filename in members or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Duplicate member or symbolic link in artifact")
            members.add(item.filename)
            safe_child(root, item.filename.rstrip("/"))
            total += item.file_size
            if total > expanded_limit:
                raise ValueError("Expanded artifact exceeds the resource limit")
        for item in archive.infolist():
            target = safe_child(root, item.filename.rstrip("/"))
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, target.open("xb") as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(chunk)
    return root

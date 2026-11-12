"""Small I/O utilities and fail-closed authorization for this study only."""
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile

ROOT = HERE = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
BRANCHES = {stage: f"refs/heads/research/calibrated-selection-{stage}-20261112"
            for stage in ("technical", "main")}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ci_only():
    require(os.environ.get("GITHUB_ACTIONS") == "true", "This study executes only in GitHub Actions")


require_ci = ci_only


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def canonical_sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


sha = sha256


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _atomic(path, raw):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".pending-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
            # Docker writes as root; artifact upload must remain readable by the host runner.
            os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_json(path, value, *, max_bytes=None):
    raw = canonical_bytes(value) + b"\n"
    require(max_bytes is None or (type(max_bytes) is int and 0 <= len(raw) <= max_bytes),
            "JSON evidence exceeds its disjoint phase allowance")
    _atomic(path, raw)


def read_log(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def write_log(path, value, *, max_bytes=None):
    raw = gzip.compress(canonical_bytes(value), compresslevel=6, mtime=0)
    require(max_bytes is None or (type(max_bytes) is int and 0 <= len(raw) <= max_bytes),
            "Compressed evidence exceeds its disjoint phase allowance")
    _atomic(path, raw)


def safe_relative(root, relative):
    require(type(relative) is str and "\\" not in relative and ":" not in relative,
            "Unsafe source path")
    parts = PurePosixPath(relative)
    require(not parts.is_absolute() and ".." not in parts.parts and parts.parts,
            "Unsafe source path")
    target = Path(root).joinpath(*parts.parts)
    require(target.resolve().is_relative_to(Path(root).resolve()) and not target.is_symlink(),
            "Source path leaves its registered root")
    return target


def verify_source():
    """Check frozen bytes and forbid unregistered executable module additions."""
    manifest = read_json(ROOT / "source_manifest.json")
    require(manifest.get("schema") == "calibrated-selection-source-v1", "Missing source seal")
    seen = set()
    for row in manifest["files"]:
        relative = row["path"]
        require(relative not in seen, "Duplicate frozen source path")
        seen.add(relative)
        path = safe_relative(REPOSITORY, relative)
        require(path.is_file() and path.stat().st_size == row["bytes"]
                and sha256(path) == row["sha256"], "Frozen source differs: " + relative)
    prefix = ROOT.relative_to(REPOSITORY).as_posix() + "/"
    active_python = {path.relative_to(REPOSITORY).as_posix() for path in ROOT.rglob("*.py")}
    require(active_python == {p for p in seen if p.startswith(prefix) and p.endswith(".py")},
            "Executable module inventory differs from its seal")
    return manifest


def guard_stage(stage):
    """Past permissions do not authorize either stage of this experiment."""
    ci_only()
    require(stage in BRANCHES and os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test"
            and os.environ.get("GITHUB_REF") == BRANCHES[stage], "Unregistered repository or branch")
    require(os.environ.get("GITHUB_RUN_ATTEMPT") == "1",
            "Recovery needs a new ledger of missing identities, not a blind rerun")
    import numpy as np
    require(sys.version_info[:3] == (3, 12, 14) and np.__version__ == "2.2.6",
            "Frozen Python or NumPy version differs")
    authority = read_json(ROOT / f"{stage}_authorization.json")
    require(authority.get("status") == "AUTHORIZED" and authority.get("stage") == stage
            and authority.get("historical_budgets_inherited") is False,
            "A separate stage resource permission is required")
    require(type(authority.get("runner_minutes")) is int and authority["runner_minutes"] > 0
            and type(authority.get("artifact_bytes")) is int and authority["artifact_bytes"] > 0,
            "Missing resource ceilings")
    if stage == "technical":
        require(authority["runner_minutes"] == 60 and authority["artifact_bytes"] == 2 * 1024 ** 3
                and authority.get("main_authorized") is False,
                "Technical permission cannot enable the main series")
    verify_source()
    protocol = read_json(ROOT / "protocol.json")
    require(protocol.get("execution_policy") == "READY_FOR_TECHNICAL_RUN",
            "Execution is deferred: prepare the requested documents before any experiment")
    return protocol

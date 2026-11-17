"""Small evidence helpers; no search or exact solving occurs on import."""
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def require_ci():
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Calculations are allowed only in GitHub Actions")


def sha(path):
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig") as stream:
        return json.load(stream)


def write_json(path, value):
    path = Path(path)
    require(not path.exists(), "Existing evidence must not be overwritten: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    opener = gzip.open if path.suffix == ".gz" else open
    options = {"compresslevel": 3} if path.suffix == ".gz" else {}
    with opener(pending, "wt", encoding="utf-8", **options) as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    pending.replace(path)


def guard_technical():
    """Require a new, explicit technical authorization and the sealed source."""
    require_ci()
    require(os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "Preserve completed cases; register a new remaining-case ledger before retrying")
    import numpy as np
    require(sys.version_info[:3] == (3, 12, 14) and np.__version__ == "2.2.6", "Frozen Python/NumPy versions differ")
    authorization = read_json(HERE / "resource_authorization.json")
    require(authorization.get("status") == "AUTHORIZED" and authorization.get("stage") == "technical",
            "No explicit resource authorization for this new technical stage")
    require(authorization.get("runner_minutes") == 30 and authorization.get("artifact_bytes") == 1073741824,
            "Technical authorization differs from the registered ceiling")
    require(authorization.get("main_stage_authorized") is False and authorization.get("historical_budgets_inherited") is False,
            "Technical authorization cannot enable the main series or inherit old budgets")
    manifest = read_json(HERE / "source_manifest.json")
    require(manifest.get("schema") == "population-validation-100-source-v1", "Source seal missing")
    for row in manifest["files"]:
        source = (REPOSITORY / row["path"]).resolve()
        require(source.is_relative_to(REPOSITORY.resolve()) and source.is_file(), "Unsafe source dependency")
        require(source.stat().st_size == row["bytes"] and sha(source) == row["sha256"], "Frozen source differs: " + row["path"])
    return read_json(HERE / "protocol.json")

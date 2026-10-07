"""CI-only pinned-source audit. No optimization, population or statistics."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_PATH = REPO_ROOT / "studies/knapsack_parameters/feasibility_protocol.json"
PROTOCOL_ID = "GA-KNAPSACK-FEASIBILITY-V1"
PROTOCOL_SHA256 = "d60db58531f76f3068a9fe16d92b2978c284d206e4f840b07ece318a7d08252f"
REGISTRATION_SHA = "d08d3b17af959df2e2379094d3f5dcdd71efe3b2"
SOURCE_SHA = "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c"
BRANCH = "refs/heads/research/masters-ga-knapsack-parameters"
CLASSES = (("UC", "00Uncorrelated"), ("WC", "01WeaklyCorrelated"), ("SC", "02StronglyCorrelated"))
RAW_BASE = f"https://raw.githubusercontent.com/likr/kplib/{SOURCE_SHA}/"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


@dataclass(frozen=True)
class Instance:
    n: int
    capacity: int
    profits: tuple[int, ...]
    weights: tuple[int, ...]
    source_path: str
    class_label: str
    family: str
    index: int

    @property
    def instance_id(self) -> str:
        return f"{self.class_label}-{self.family}"


def parse_instance(raw: bytes, source_path: str, *, class_label: str, family: str,
                   index: int, expected_n: int = 100) -> Instance:
    """Strictly parse original rows; never sort, repair or alter source bytes."""
    text = raw.decode("utf-8", errors="strict")
    rows = [line.split() for line in text.splitlines() if line.strip()]
    require(len(rows) == expected_n + 2, "unexpected number of nonempty source rows")
    require(len(rows[0]) == len(rows[1]) == 1, "n and capacity must have one integer each")
    require(all(len(row) == 2 for row in rows[2:]), "each item row must contain profit and weight")
    require(all(re.fullmatch(r"[0-9]+", token) is not None for row in rows for token in row), "source must contain unsigned decimal integers only")
    n, capacity = int(rows[0][0]), int(rows[1][0])
    require(n == expected_n and n > 0, "source dimension differs from the registered dimension")
    items = tuple((int(row[0]), int(row[1])) for row in rows[2:])
    require(capacity > 0 and all(p > 0 and w > 0 for p, w in items), "profits, weights and capacity must be positive")
    return Instance(n, capacity, tuple(p for p, _ in items), tuple(w for _, w in items), source_path, class_label, family, index)


def check_license(raw: bytes) -> dict:
    text = raw.decode("utf-8", errors="strict")
    phrase = "Creative Commons Attribution 4.0 International License"
    require(phrase in text, "pinned README does not declare the expected CC BY 4.0 license")
    return {"identifier": "CC-BY-4.0", "declaration": phrase,
            "scope": "KPLIB source data; README declaration, not a legal guarantee",
            "attribution_url": f"https://github.com/likr/kplib/tree/{SOURCE_SHA}"}


def source_specs() -> list[dict]:
    specs = [{"path": "README.md", "kind": "readme"}]
    for label, directory in CLASSES:
        for index in range(10):
            specs.append({"path": f"{directory}/n00100/R01000/s{index:03d}.kp", "kind": "instance",
                          "class_label": label, "family": f"s{index:03d}", "index": index})
    return specs


class DownloadFailure(OSError):
    def __init__(self, message: str, attempts: list[dict]):
        super().__init__(message)
        self.attempts = attempts


def download_source(source_path: str) -> tuple[bytes, list[dict]]:
    """At most three infrastructural attempts; identical pinned URL each time."""
    url = RAW_BASE + source_path
    attempts = []
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "knapsack-feasibility-source-audit/1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                require(response.geturl() == url, "unexpected source redirect")
                raw = response.read()
            attempts.append({"attempt": attempt, "status": "DOWNLOADED", "bytes": len(raw)})
            return raw, attempts
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            attempts.append({"attempt": attempt, "status": "DOWNLOAD_ERROR", "type": type(error).__name__, "message": str(error)})
            retriable = not isinstance(error, urllib.error.HTTPError) or error.code in (408, 429) or 500 <= error.code <= 599
            if not retriable or attempt == 3:
                raise DownloadFailure(str(error), attempts) from error
            time.sleep(attempt)
    raise AssertionError("unreachable")


def authenticate(expected_sha: str) -> dict:
    require(re.fullmatch(r"[0-9a-f]{40}", expected_sha) is not None, "expected SHA must be exact")
    require(os.environ.get("GITHUB_ACTIONS") == "true", "scientific source audit is permitted only in GitHub Actions")
    require(os.environ.get("GITHUB_EVENT_NAME") == "push" and os.environ.get("GITHUB_REF") == BRANCH, "unexpected event or branch")
    require(os.environ.get("GITHUB_SHA") == os.environ.get("STUDY_WORKFLOW_SHA") == expected_sha, "workflow and implementation SHA mismatch")
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT)
    require(git("rev-parse", "HEAD").decode().strip() == expected_sha, "checkout is not the exact expected SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, expected_sha], cwd=REPO_ROOT, check=True)
    registered = git("show", f"{REGISTRATION_SHA}:studies/knapsack_parameters/feasibility_protocol.json")
    require(sha256_bytes(registered) == sha256_bytes(PROTOCOL_PATH.read_bytes()) == PROTOCOL_SHA256, "registered preparation protocol bytes changed")
    require(not git("status", "--porcelain=v1", "--untracked-files=all").strip(), "scientific checkout must be pristine")
    require(sys.version_info[:2] == (3, 12), "registered Python 3.12 is required")
    run_id, run_attempt = int(os.environ["GITHUB_RUN_ID"]), int(os.environ["GITHUB_RUN_ATTEMPT"])
    require(run_id > 0 and run_attempt > 0, "missing workflow run identity")
    return {"protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
            "registration_commit_sha": REGISTRATION_SHA, "implementation_sha": expected_sha,
            "workflow_sha": os.environ["STUDY_WORKFLOW_SHA"], "source_commit_sha": SOURCE_SHA,
            "run_id": run_id, "run_attempt": run_attempt,
            "artifact_name": f"knapsack-feasibility-audit-{run_id}-{run_attempt}"}


def compare_families(instances: list[Instance]) -> list[dict]:
    grouped = {(instance.family, instance.class_label): instance for instance in instances}
    comparisons = []
    for index in range(10):
        family = f"s{index:03d}"
        for first, second in itertools.combinations([label for label, _ in CLASSES], 2):
            a, b = grouped.get((family, first)), grouped.get((family, second))
            row = {"family": family, "classes": [first, second], "complete": a is not None and b is not None}
            if row["complete"]:
                row.update(weights_equal=a.weights == b.weights, profits_equal=a.profits == b.profits, capacity_equal=a.capacity == b.capacity)
            comparisons.append(row)
    return comparisons


def audit_sources(output: Path, provenance: dict, *, fetcher=download_source) -> dict:
    output = Path(output).resolve()
    require(not output.exists() or not any(output.iterdir()), "audit output must be empty; existing evidence is not overwritten")
    output.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    write_json(output / "execution-start.json", {"started_at": started, "provenance": provenance, "phase": "SOURCE_AUDIT_ONLY"})
    instances, files = [], []
    license_info = None
    for spec in source_specs():
        row = {"path": f"source/{spec['path']}", "source_path": spec["path"], "url": RAW_BASE + spec["path"], "status": "PENDING"}
        try:
            raw, attempts = fetcher(spec["path"])
            row.update(attempts=attempts, bytes=len(raw), sha256=sha256_bytes(raw))
            target = output / "source" / PurePosixPath(spec["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            if spec["kind"] == "readme":
                license_info = check_license(raw)
            else:
                instance = parse_instance(raw, spec["path"], class_label=spec["class_label"], family=spec["family"], index=spec["index"])
                instances.append(instance)
            row["status"] = "PASS_SOURCE"
        except (OSError, ValueError, UnicodeError) as error:
            row.update(status="INVALID_SOURCE", error_type=type(error).__name__, error=str(error))
            if isinstance(error, DownloadFailure):
                row["attempts"] = error.attempts
        files.append(row)
        write_json(output / "execution-progress.json", {"files_completed": len(files), "files_expected": 31, "last_file": row})
    complete = len(instances) == 30 and license_info is not None and all(row["status"] == "PASS_SOURCE" for row in files)
    parsed = []
    for instance in instances:
        row = asdict(instance)
        row.update(instance_id=instance.instance_id, original_positions=list(range(instance.n)),
                   documentation_positions=list(range(1, instance.n + 1)),
                   profits_sha256=sha256_bytes(canonical_bytes(instance.profits)),
                   weights_sha256=sha256_bytes(canonical_bytes(instance.weights)))
        parsed.append(row)
    manifest = {"schema_version": "knapsack-feasibility-data-manifest-v1",
                "protocol_id": PROTOCOL_ID, "status": "PASS_AUDIT" if complete else "INCOMPLETE_AUDIT",
                "provenance": provenance, "source_repository": "likr/kplib", "source_commit_sha": SOURCE_SHA,
                "source_files": files, "license": license_info, "instances": parsed,
                "instance_count": len(instances), "expected_instance_count": 30,
                "family_comparisons": compare_families(instances), "family_key": "sNNN",
                "family_comparison_scope": "exact array/capacity equality only; independence and statistical correlation are not assessed",
                "bit_order": "original item row order, zero-based internal and one-based documentation positions",
                "runtime": {"python_version": platform.python_version(), "python_full": sys.version,
                            "implementation": platform.python_implementation(), "platform": platform.platform(), "byteorder": sys.byteorder},
                "scientific_python_patch_frozen": False, "forbidden_computations_performed": False,
                "source_originals_retained": True}
    write_json(output / "data_manifest.json", manifest)
    write_json(output / "execution-status.json", {"status": manifest["status"], "finished_at": datetime.now(timezone.utc).isoformat(), "provenance": provenance})
    members = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "file_manifest.json":
            raw = path.read_bytes()
            members.append({"path": path.relative_to(output).as_posix(), "bytes": len(raw), "sha256": sha256_bytes(raw)})
    write_json(output / "file_manifest.json", {"schema_version": "knapsack-feasibility-files-v1", "provenance": provenance,
                                             "excludes_self": True, "files": members})
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    provenance = authenticate(args.expected_sha)
    output = args.output.resolve()
    require(not output.is_relative_to(REPO_ROOT), "audit outputs must be isolated outside the scientific checkout")
    manifest = audit_sources(output, provenance)
    print(json.dumps({"status": manifest["status"], "instances": manifest["instance_count"], "python": manifest["runtime"]["python_version"]}))
    return 0 if manifest["status"] == "PASS_AUDIT" else 1


if __name__ == "__main__":
    raise SystemExit(main())

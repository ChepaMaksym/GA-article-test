"""Audit retained ZIPs without importing any search implementation.

This module never extracts archive paths, evaluates an optimum or launches GA.
The archive inventory is the previously recorded provenance, not an external
signature or proof of long-term public availability.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from . import verifier_snapshot

PROFILES = ("adaptive", "replay", "k2", "k3", "k4", "k5")
INVENTORY = Path(__file__).with_name("archive_inventory.json")


def safe_path(name):
    p = PurePosixPath(name)
    return bool(name and not name.startswith("/") and "\\" not in name
                and all(x not in (".", "..") for x in p.parts)
                and ":" not in p.parts[0])


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def expected(scope):
    if scope == "smoke":
        return {("main", "recipients", "UC-s040", "bank", 110001, p) for p in PROFILES} | {
            ("main", "donors", "UC-s040", "bank", 110001, "adaptive")}
    result = set()
    for task in ("UC-s000", "WC-s001", "SC-s005", "SC-s000"):
        for start in ("bank", "cloned"):
            result.add(("pilot", "donors", task, start, 109999, "adaptive"))
            result.update(("pilot", "recipients", task, start, 109999, p) for p in PROFILES)
    for i in range(40, 50):
        for kind in ("UC", "WC", "SC"):
            task = f"{kind}-s{i:03}"
            for seed in range(110001, 110031):
                result.add(("main", "donors", task, "bank", seed, "adaptive"))
                result.update(("main", "recipients", task, "bank", seed, p) for p in PROFILES)
    return result


def run(bundle, scope):
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8-sig"))
    valid_archives = {x["zip_sha256"]: x for x in inventory["canonical_archives"]}
    source_sha = {(x["run_id"], x["attempt"]): x["sha"] for x in inventory["attempts"]}
    wanted, seen, errors, archive_hashes = expected(scope), {}, [], set()
    archives = list(Path(bundle).rglob("*.zip"))
    for archive in archives:
        try:
            digest = sha256(archive)
            if digest not in valid_archives:
                raise ValueError("archive not in frozen inventory")
            if digest in archive_hashes:
                raise ValueError("duplicate canonical archive")
            archive_hashes.add(digest)
            with zipfile.ZipFile(archive) as z:
                names = z.namelist()
                if len(names) != len(set(names)) or not all(safe_path(n) for n in names):
                    raise ValueError("duplicate or unsafe archive path")
                for name in names:
                    if not name.startswith("metadata/") or not name.endswith(".json"):
                        continue
                    m = json.loads(z.read(name))
                    key = tuple(m[x] for x in ("stage", "role", "task", "start", "seed", "profile"))
                    if key not in wanted:
                        continue
                    if key in seen:
                        raise ValueError("duplicate journal identity: " + str(key))
                    path = m["log_path"]
                    if not safe_path(path) or path not in names:
                        raise ValueError("missing or unsafe journal path")
                    raw = z.read(path)
                    if len(raw) != m["log_identity"]["bytes"] or hashlib.sha256(raw).hexdigest() != m["log_identity"]["sha256"]:
                        raise ValueError("journal checksum mismatch")
                    frozen = valid_archives[digest]
                    frozen_sha = source_sha[(frozen["run_id"], frozen["run_attempt"])]
                    if m["implementation_sha"] != frozen_sha:
                        raise ValueError("implementation SHA differs from its frozen source job")
                    log = json.loads(gzip.decompress(raw))
                    if log["profile"] != m["profile"] or log["budget"] != 5000:
                        raise ValueError("journal and metadata identity mismatch")
                    result = verifier_snapshot.verify_log(log)
                    seen[key] = {"archive_sha256": digest, "journal_sha256": m["log_identity"]["sha256"],
                                 "record_profit": result["record_profit"], "new_calls": result["new_calls"]}
        except Exception as exc:
            errors.append({"archive": str(archive), "error": str(exc)})
    missing = sorted(wanted - seen.keys())
    status = "INVALID" if errors else "INCOMPLETE" if missing else "VERIFIED"
    return {"status": status, "scope": scope, "expected": len(wanted), "verified": len(seen),
            "missing": [list(x) for x in missing], "errors": errors,
            "records": [{"identity": list(k), **v} for k, v in sorted(seen.items())],
            "bootstrap_recomputed": False,
            "limitations": ["Transport hashes and journal replay do not establish statistical coverage or public availability.",
                            "Cross-run bank, seed and compact-summary provenance require a separate independent reconciliation."]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audit", choices=["audit"])
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--scope", choices=["smoke", "full"], required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run(args.bundle, args.scope)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{report['status']}: {report['verified']}/{report['expected']}; bootstrap_recomputed=false")
    if report["status"] != "VERIFIED":
        raise SystemExit(1)

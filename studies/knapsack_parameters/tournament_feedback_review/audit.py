"""Audit retained ZIPs without importing any search implementation.

This module never extracts archive paths, evaluates an optimum or launches GA.
The archive inventory is the previously recorded provenance, not an external
signature or proof of long-term public availability.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

from . import verifier_snapshot
import numpy as np

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


def expected_rng(key, search_seed):
    stage, _role, task, start, seed, _profile = key
    if stage == "pilot":
        task_index = ("UC-s000", "WC-s001", "SC-s005", "SC-s000").index(task)
        start_index = ("cloned", "bank").index(start)
    else:
        task_index = 3 * (int(task[-3:]) - 40) + ("UC", "WC", "SC").index(task[:2])
        start_index = 1
    return {name: np.random.PCG64(np.random.SeedSequence([search_seed, task_index, start_index, channel])).state
            for channel, name in enumerate(verifier_snapshot.CHANNELS)}


def run(bundle, scope):
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8-sig"))
    valid_archives = {x["zip_sha256"]: x for x in inventory["canonical_archives"]}
    source_sha = {(x["run_id"], x["attempt"]): x["sha"] for x in inventory["attempts"]}
    wanted, seen, errors, archive_hashes = expected(scope), {}, [], set()
    banks, donor_schedules, recipient_schedules, missing_compact = {}, {}, {}, []
    compact = {}
    compact_names = {"main": ("main_compact_records.json.gz", "1105e6aab6fcc3c9efb0244b603c27c49ce748df8606640a3a9581628e71bd93")}
    if scope == "full":
        compact_names["pilot"] = ("pilot_compact_records.json.gz", "72271178ba07975e4f0899142c8411b665771fd891eccaef3ff5699724b81669")
    for stage, (filename, digest) in compact_names.items():
        path = Path(bundle) / filename
        if not path.is_file():
            missing_compact.append(filename)
            continue
        if sha256(path) != digest:
            errors.append({"file": filename, "error": "compact summary hash mismatch"})
            continue
        for row in json.loads(gzip.decompress(path.read_bytes())):
            identity = (stage, "recipients", row["task"], row["start"], row["seed"], row["profile"])
            if identity in compact:
                errors.append({"file": filename, "error": "duplicate compact identity"})
            compact[identity] = row
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
                if any(((x.external_attr >> 16) & 0o170000) == 0o120000 for x in z.infolist()):
                    raise ValueError("symbolic-link archive entry")
                for name in names:
                    if not name.startswith("metadata/") or not name.endswith(".json"):
                        continue
                    if z.getinfo(name).file_size > 1024 * 1024:
                        raise ValueError("oversized metadata")
                    m = json.loads(z.read(name))
                    key = tuple(m[x] for x in ("stage", "role", "task", "start", "seed", "profile"))
                    if key not in wanted:
                        continue
                    if key in seen:
                        raise ValueError("duplicate journal identity: " + str(key))
                    exp_seed = (109997 if key[0] == "pilot" else key[4] + 1000) if key[1] == "donors" else key[4]
                    if m["search_seed"] != exp_seed:
                        raise ValueError("unexpected search seed")
                    path = m["log_path"]
                    basename = f"{key[2]}-{key[3]}-{key[4]}-{key[5]}"
                    if name != f"metadata/{basename}.json" or path != f"logs/{basename}.json.gz" or not safe_path(path) or path not in names:
                        raise ValueError("missing or unsafe journal path")
                    raw = z.read(path)
                    if len(raw) != m["log_identity"]["bytes"] or hashlib.sha256(raw).hexdigest() != m["log_identity"]["sha256"]:
                        raise ValueError("journal checksum mismatch")
                    frozen = valid_archives[digest]
                    frozen_sha = source_sha[(frozen["run_id"], frozen["run_attempt"])]
                    if m["implementation_sha"] != frozen_sha:
                        raise ValueError("implementation SHA differs from its frozen source job")
                    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
                        decoded = compressed.read(64 * 1024 * 1024 + 1)
                    if len(decoded) > 64 * 1024 * 1024:
                        raise ValueError("oversized journal")
                    log = json.loads(decoded)
                    if log["profile"] != m["profile"] or log["budget"] != 5000:
                        raise ValueError("journal and metadata identity mismatch")
                    if log["rng_initial"] != expected_rng(key, exp_seed):
                        raise ValueError("seed-derived RNG state mismatch")
                    result = verifier_snapshot.verify_log(log)
                    if key[1] == "recipients":
                        row = compact.get(key)
                        if row is None:
                            raise ValueError("missing compact recipient")
                        encoded = json.dumps(log, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
                        if (row["journal_sha256"] != hashlib.sha256(encoded).hexdigest()
                                or row["log_identity"]["sha256"] != m["log_identity"]["sha256"]
                                or row["final_best_profit"] != result["record_profit"]
                                or row["record_events"] != result["derived_metrics"]["record_events"]):
                            raise ValueError("compact record differs from independent replay")
                    condition = (key[0], key[2], key[3], key[4])
                    bank = json.dumps({"problem": log["problem"], "masks": log["initial_masks"],
                                       "scores": log["initial_scores"], "identity": m["bank_identity"]}, sort_keys=True)
                    if condition in banks and banks[condition] != bank:
                        raise ValueError("beginning differs across donor and recipients")
                    banks[condition] = bank
                    if key[1] == "donors":
                        donor_schedules[condition] = [x["parameters_before"]["tournament_size"] for x in log["generations"]]
                    elif key[5] == "replay":
                        recipient_schedules[condition] = log["schedule"]
                    seen[key] = {"archive_sha256": digest, "journal_sha256": m["log_identity"]["sha256"],
                                 "record_profit": result["record_profit"], "new_calls": result["new_calls"]}
        except Exception as exc:
            errors.append({"archive": str(archive), "error": str(exc)})
    for condition in donor_schedules.keys() & recipient_schedules.keys():
        if donor_schedules[condition] != recipient_schedules[condition]:
            errors.append({"condition": list(condition), "error": "donor schedule mismatch"})
    missing = sorted(wanted - seen.keys())
    status = "INVALID" if errors else "INCOMPLETE" if missing or missing_compact else "VERIFIED"
    return {"status": status, "scope": scope, "expected": len(wanted), "verified": len(seen),
            "missing": [list(x) for x in missing], "missing_compact": missing_compact, "errors": errors,
            "records": [{"identity": list(k), **v} for k, v in sorted(seen.items())],
            "bootstrap_recomputed": False,
            "compact_reconciliation": "journal digests, final records and record events; not all summary metrics",
            "limitations": ["Transport hashes and journal replay do not establish statistical coverage or public availability.",
                            "Other compact statistics and BCa intervals are not recomputed."]}


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

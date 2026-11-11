"""Prepare authenticated technical inputs without running search or exact solvers."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import time

from .common import HERE, guard_stage
from .retained import OUTPUT_LIMIT, REGISTRY, retrieve, validate_registry
from studies.knapsack_parameters.population_validation_100.common import read_json, require, require_ci, sha, write_json
from studies.knapsack_parameters.population_validation_100.preparation import make_bank
from studies.knapsack_parameters.initial_grid_100.preparation import verify_certificate
from studies.knapsack_parameters.initial_grid_100.analyze_tuning import verify_row
from studies.knapsack_parameters.population_validation_100_main.runner import _safe_file, _verify_files
from studies.knapsack_parameters.population_size_study.inputs import parse_kp_bytes, problem_sha256
from studies.knapsack_parameters.population_size_study.io_utils import extract_artifact

TECHNICAL = (("n00100-UC-s000", 0), ("n00100-WC-s001", 1), ("n00100-SC-s005", 2))


def authenticate_downloads(root):
    """Recheck the downloader's pinned registry and selected-file hashes."""
    root = Path(root)
    registry = read_json(REGISTRY)
    descriptors = validate_registry(registry)
    origin = read_json(root / "origin.json")
    require(origin.get("schema") == "mutation-grid-100-retained-origin-v1"
            and origin.get("status") == "AUTHENTICATED_SELECTED_EVIDENCE"
            and origin.get("registry_sha256") == sha(REGISTRY) and origin.get("archives") == descriptors,
            "Retained downloader origin differs")
    _verify_files(root, origin.get("files"))
    return origin


def validate_retained_records(document, prepared):
    """Audit all 1440 rows against their paired banks and exact certificates."""
    require(document.get("schema") == "initial-grid-100-validated-tuning-v1"
            and document.get("status") == "VERIFIED_1440", "Retained grid is not complete and verified")
    rows = document.get("runs")
    require(type(rows) is list and len(rows) == 1440, "Exactly 1440 retained grid rows are required")
    manifest = read_json(prepared / "manifest.json")
    require(manifest.get("schema") == "population-validation-100-main-inputs-v1"
            and manifest.get("status") == "PAIRED_BANKS_PREPARED" and manifest.get("main_ga_runs") == 0
            and manifest.get("source_commit") == "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c",
            "Original tuning bank provenance differs")
    _verify_files(prepared, manifest["files"])
    tasks = {t["task"]: t for t in manifest["tasks"]}
    expected_tasks = {f"n00100-{kind}-s{family:03d}" for family in range(50, 60) for kind in ("UC", "WC", "SC")}
    require(len(tasks) == 30 and set(tasks) == expected_tasks, "Original tuning task inventory differs")
    expected = {(task, seed, mu, pc) for task in tasks for seed in (150001, 150002, 150003)
                for mu in (10, 15, 20, 25) for pc in (70, 80, 90, 100)}
    seen, normalized = set(), []
    for row in rows:
        identity = row["task"], row["seed"], row["mu"], row["pc_percentage"]
        require(identity in expected and identity not in seen, "Missing, substituted or duplicate retained grid identity")
        seen.add(identity)
        task = tasks[row["task"]]
        verify_row(row, task["family"], row["mu"], row["pc_percentage"],
                   retained=(row["mu"], row["pc_percentage"]) in ((10, 90), (20, 90)))
        bank = next(b for b in task["banks"] if b["seed"] == row["seed"])
        certificate = prepared / row["task"] / "certificate.json"
        require(row["task_index"] == task["task_index"] and row["bank_sha256"] == bank["sha256"]
                and row["certificate_sha256"] == task["certificate_sha256"] == sha(certificate)
                and row["optimum"] == read_json(certificate)["optimum"],
                "Retained record differs from the paired input or exact reference")
        item = dict(row)
        item["mutation_basis_points"] = 100
        item["retained_origin"] = {"run_id": 42886706730,
                                   "commit": "3dc54a652a54c851653f16ce55507ac5c708bc8f",
                                   "artifact_id": 13810740328,
                                   "artifact_sha256": "4de51008ac16a045475183af019fe309adb1b19fa9e9659887ccc734f77ecbb0"}
        normalized.append(item)
    require(seen == expected, "Retained grid is incomplete")
    return normalized, tasks


def authenticate_reference(reference, expected, task, mu):
    """Bind an authenticated raw journal to its retained compact source row."""
    require(expected["task"] == task and expected["mu"] == mu and expected["seed"] == 150001
            and expected["pc_percentage"] == 100 and expected["mutation_basis_points"] == 100,
            "Reference identity differs")
    require(sha(reference / "journal.json.gz") == expected["artifact_hashes"]["journal.json.gz"]
            and sha(reference / "record.json") == expected["artifact_hashes"]["record.json"]
            and sha(reference / "verification.json") == expected["artifact_hashes"]["verification.json"],
            "Reference member hash differs from the authenticated compact row")
    receipt = read_json(reference / "record.json")
    require(receipt.get("status") == "VERIFIED" and receipt.get("task") == task
            and receipt.get("mu") == mu and receipt.get("seed") == 150001
            and receipt.get("pc_percentage") == 100 and receipt.get("workflow_run_id") == "42886706730"
            and receipt.get("workflow_commit") == "3dc54a652a54c851653f16ce55507ac5c708bc8f"
            and receipt.get("code_manifest_sha256") == "2ed212337b22706decd7123ab1111cbc4c62fbe357e29478c1c868acf3c2f44f"
            and receipt.get("bank_sha256") == expected["bank_sha256"]
            and receipt.get("certificate_sha256") == expected["certificate_sha256"],
            "Raw retained receipt provenance differs")


def _copy(source, destination):
    require(source.is_file() and not source.is_symlink() and not destination.exists(),
            "Missing source or existing output file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def prepare(out, retained=None):
    protocol = guard_stage("technical")
    require_ci()
    destination = Path(out)
    require(not destination.exists(), "Preserve prior or partial technical preparation")
    destination.mkdir(parents=True)
    begin = time.perf_counter()
    retained_root = Path(retained) if retained is not None else retrieve(destination / "retained")
    origin = authenticate_downloads(retained_root)
    source = destination / "source"
    extract_artifact(retained_root / "technical_inputs.zip", source / "technical", compressed_limit=1024**2,
                     expanded_limit=16 * 1024**2)
    extract_artifact(retained_root / "tuning_inputs.zip", source / "tuning", compressed_limit=4 * 1024**2,
                     expanded_limit=64 * 1024**2)
    extract_artifact(retained_root / "results.zip", source / "results", compressed_limit=2 * 1024**2,
                     expanded_limit=32 * 1024**2)
    technical = source / "technical"
    previous = read_json(technical / "manifest.json")
    require(previous.get("schema") == "initial-grid-100-inputs-v1"
            and previous.get("status") == "INPUTS_AUDITED_AND_CERTIFIED"
            and previous.get("technical_tasks") == 3 and previous.get("validation_ga_runs") == 0,
            "Prior certified technical input origin differs")
    _verify_files(technical, previous["files"])
    paired = source / "tuning" / "prepared"
    rows, paired_tasks = validate_retained_records(read_json(source / "results" / "validated_records.json.gz"), paired)
    tasks = []
    for task, index in TECHNICAL:
        folder = destination / task
        folder.mkdir()
        problem = read_json(technical / task / "problem.json")
        raw = (technical / task / "source.kp").read_bytes()
        require(problem == parse_kp_bytes(raw, 100), "Retained technical source and parsed problem differ")
        verify_certificate(problem, read_json(technical / task / "certificate.json"), raw)
        for name in ("problem.json", "certificate.json", "source.kp"):
            _copy(technical / task / name, folder / name)
        bank = make_bank(problem, index, 169999, 169998)
        write_json(folder / "bank.json", bank)
        tasks.append({"task": task, "task_index": index, "phase": "technical",
                      "problem_sha256": problem_sha256(problem), "bank_path": f"{task}/bank.json",
                      "bank_sha256": sha(folder / "bank.json"),
                      "certificate_sha256": sha(folder / "certificate.json")})
    by_identity = {(r["task"], r["mu"], r["seed"], r["pc_percentage"]): r for r in rows}
    for kind in ("UC", "WC", "SC"):
        task = f"n00100-{kind}-s050"
        descriptor = paired_tasks[task]
        folder = destination / task
        folder.mkdir()
        for name in ("problem.json", "certificate.json", "source.kp"):
            # Historical prepared inputs retain the canonical source under source.kp.
            _copy(paired / task / name, folder / name)
        problem = read_json(folder / "problem.json")
        require(problem == parse_kp_bytes((folder / "source.kp").read_bytes(), 100),
                "Compatibility source and parsed problem differ")
        verify_certificate(problem, read_json(folder / "certificate.json"), (folder / "source.kp").read_bytes())
        bank_descriptor = next(b for b in descriptor["banks"] if b["seed"] == 150001)
        bank_path = _safe_file(paired, bank_descriptor["path"])
        bank = read_json(bank_path)
        require(bank == make_bank(problem, descriptor["task_index"], 150001, 150000),
                "Retained bank prefixes or six RNG states differ on independent preparation")
        _copy(bank_path, folder / "compatibility_bank.json")
        references = []
        for mu in (10, 15, 20):
            reference = retained_root / "references" / task / f"mu{mu}"
            expected = by_identity[(task, mu, 150001, 100)]
            authenticate_reference(reference, expected, task, mu)
            for name in ("journal.json.gz", "record.json", "verification.json"):
                _copy(reference / name, destination / "references" / task / f"mu{mu}" / name)
            references.append({"mu": mu, "path": f"references/{task}/mu{mu}/journal.json.gz",
                               "sha256": expected["artifact_hashes"]["journal.json.gz"]})
        tasks.append({"task": task, "task_index": descriptor["task_index"], "phase": "compatibility",
                      "bank_path": f"{task}/compatibility_bank.json", "bank_sha256": sha(folder / "compatibility_bank.json"),
                      "certificate_sha256": sha(folder / "certificate.json"), "references": references})
    overlap = [r for r in rows if r["mu"] in (10, 15, 20) and r["pc_percentage"] == 100]
    require(len(overlap) == 270 and len(tasks) == 6, "Retained mutation overlap or technical corpus differs")
    write_json(destination / "retained_grid.json.gz", {"schema": "mutation-grid-100-retained-grid-v1",
               "status": "VERIFIED_1440_RETAINED", "runs": rows,
               "source_result_zip_sha256": "4de51008ac16a045475183af019fe309adb1b19fa9e9659887ccc734f77ecbb0"})
    write_json(destination / "reused_mutation.json.gz", {"schema": "mutation-grid-100-reused-v1",
               "status": "VERIFIED_270_RETAINED", "runs": overlap})
    files = [{"path": p.relative_to(destination).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)}
             for p in sorted(destination.rglob("*")) if p.is_file()]
    require(sum(p["bytes"] for p in files) < OUTPUT_LIMIT, "Prepared technical payload exceeds 256 MiB")
    write_json(destination / "manifest.json", {"schema": "mutation-grid-100-technical-inputs-v1",
               "status": "TECHNICAL_INPUTS_PREPARED", "tasks": tasks, "files": files,
               "protocol_sha256": sha(HERE / "protocol.json"), "retained_registry_sha256": sha(REGISTRY),
               "retained_grid_count": 1440, "reused_mutation_count": 270, "compatibility_references": 9,
               "preparation_seconds": time.perf_counter() - begin,
               "physical_initial_score_checks": 180, "validation_ga_runs": 0,
               "exact_solvers_rerun": False, "historical_source_modified": False})
    print("Prepared 18 pilot identities and nine exact compatibility references; retained 1440 rows authenticated.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--retained", type=Path)
    args = parser.parse_args()
    prepare(args.out, args.retained)


if __name__ == "__main__":
    main()

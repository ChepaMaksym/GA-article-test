"""CI-only complete-case evidence revalidation and Ukrainian feasibility report."""

from __future__ import annotations

import argparse
import csv
from fractions import Fraction
import hashlib
import io
import itertools
import json
from pathlib import Path, PurePosixPath
import re
import shutil

from .certification import evaluate_mask, validate_certificate, validate_witness
from .data_audit import CLASSES, PROTOCOL_ID, PROTOCOL_SHA256, REGISTRATION_SHA, SOURCE_SHA
from .frozen_inputs import DEFAULT_INPUTS, load_frozen_inputs, verify_input_bundle


FREEZE_SHA = "58487fa3a541f194aeec5045f64a7d1641ae96be"
COMPLETE_STATUSES = {"ADMITTED_STRICT_LOCAL", "ADMITTED_PLATEAU_LOCAL", "EXCLUDED_GLOBAL_CENTER",
                     "EXCLUDED_PREPARATION_CAP"}
INCOMPLETE_STATUSES = {"RESOURCE_NOT_EVALUATED", "INVALID_SOURCE", "EXACT_METHOD_DISAGREEMENT",
                       "INCOMPLETE_CERTIFICATE", "PREPARATION_ERROR"}
ALL_STATUSES = COMPLETE_STATUSES | INCOMPLETE_STATUSES
STATUS_UK = {"ADMITTED_STRICT_LOCAL": "Допущено: строгий максимум",
             "ADMITTED_PLATEAU_LOCAL": "Допущено: плато",
             "EXCLUDED_GLOBAL_CENTER": "Не допущено: глобальний центр",
             "EXCLUDED_PREPARATION_CAP": "Не допущено: межа підготовки",
             "RESOURCE_NOT_EVALUATED": "Не оцінено: ресурсна межа",
             "INVALID_SOURCE": "Некоректне джерело",
             "EXACT_METHOD_DISAGREEMENT": "Розбіжність точних методів",
             "INCOMPLETE_CERTIFICATE": "Неповний сертифікат",
             "PREPARATION_ERROR": "Помилка підготовки"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path):
    def invalid_constant(value):
        raise ValueError(f"nonfinite JSON value: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_object,
                      parse_constant=invalid_constant)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _identity(path: Path, root: Path) -> dict:
    raw = path.read_bytes()
    return {"path": path.relative_to(root).as_posix(), "sha256": _sha(raw), "bytes": len(raw)}


def _safe_file(root: Path, relative: str) -> Path:
    require(type(relative) is str and "\\" not in relative and ":" not in relative,
            "invalid evidence path")
    value = PurePosixPath(relative)
    require(not value.is_absolute() and value.parts and all(part not in (".", "..") for part in value.parts),
            "evidence path escapes its case")
    path = root.joinpath(*value.parts)
    require(path.resolve().is_relative_to(root.resolve()), "evidence path resolves outside its case")
    current = root
    for part in value.parts:
        current /= part
        require(not current.is_symlink(), "symlink evidence is not allowed")
    require(path.is_file(), "missing retained evidence file")
    return path


def _verify_files(folder: Path, provenance: dict) -> dict:
    require(not folder.is_symlink(), "case folder must not be a symlink")
    manifest = read_json(folder / "file_manifest.json")
    require(manifest.get("schema_version") == "knapsack-feasibility-files-v1" and
            manifest.get("excludes_self") is True, "unknown case file inventory")
    require(manifest.get("provenance") == provenance, "file inventory provenance mismatch")
    members = manifest.get("files")
    require(isinstance(members, list) and members, "empty case file inventory")
    require(all(isinstance(row, dict) and type(row.get("path")) is str for row in members), "invalid inventory rows")
    paths = [row.get("path") for row in members]
    require(len(set(paths)) == len(paths) and paths == sorted(paths), "duplicate or unordered inventory paths")
    actual = {path.relative_to(folder).as_posix() for path in folder.rglob("*")
              if path.is_file() and path.relative_to(folder).as_posix() != "file_manifest.json"}
    require(set(paths) == actual and "case.json" in actual, "unlisted or missing case evidence")
    for row in members:
        path = _safe_file(folder, row["path"])
        require(type(row.get("bytes")) is int and row["bytes"] >= 0 and
                re.fullmatch(r"[0-9a-f]{64}", row.get("sha256", "")) is not None,
                "invalid member byte identity")
        require(_identity(path, folder) == row, f"corrupt evidence bytes: {row['path']}")
    return manifest


def _provenance(value: dict, expected_sha: str, data_sha: str) -> None:
    require(isinstance(value, dict), "missing provenance")
    expected = {"protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
                "registration_commit_sha": REGISTRATION_SHA, "source_commit_sha": SOURCE_SHA,
                "implementation_sha": expected_sha, "workflow_sha": expected_sha,
                "data_freeze_commit_sha": FREEZE_SHA, "data_manifest_sha256": data_sha}
    require(all(value.get(key) == field for key, field in expected.items()), "mixed scientific provenance")
    for key in ("run_id", "run_attempt"):
        require(type(value.get(key)) is int and value[key] > 0, f"invalid {key}")


def _transport(sources: dict, ledger: dict, expected_ids: list[str], expected_sha: str, api_metadata: dict) -> dict:
    require(sources.get("schema_version") == "knapsack-feasibility-case-sources-v1" and
            ledger.get("schema_version") == "knapsack-feasibility-case-transport-v1", "unknown transport schema")
    for value in (sources, ledger):
        require(value.get("protocol_id") == PROTOCOL_ID and value.get("implementation_sha") == expected_sha,
                "transport protocol or implementation mismatch")
        for field in ("source_run_id", "run_attempt"):
            require(type(value.get(field)) is int and value[field] > 0, "missing top-level transport run identity")
    require(all(sources[field] == ledger[field] for field in ("source_run_id", "run_attempt")),
            "transport source metadata and ledger mix runs")
    artifacts, downloads = sources.get("artifacts"), ledger.get("downloads")
    require(isinstance(artifacts, list) and isinstance(downloads, list), "missing exact-ID transport records")
    require(all(isinstance(row, dict) for row in artifacts + downloads), "invalid transport record")
    require(len(artifacts) == len(downloads) == 30, "transport must account for exactly 30 case artifacts")
    ids = [item.get("id") for item in artifacts]
    require(all(type(value) is int and value > 0 for value in ids) and len(set(ids)) == 30,
            "duplicate or invalid source artifact IDs")
    ledger_ids = [item.get("artifact_id") for item in downloads]
    require(len(set(ledger_ids)) == 30 and set(ledger_ids) == set(ids), "transport ledger IDs differ")
    mapped = {item["artifact_id"]: item for item in downloads}
    metadata_rows = api_metadata.get("artifacts")
    require(isinstance(metadata_rows, list) and api_metadata.get("source_run_id") == sources["source_run_id"] and
            api_metadata.get("run_attempt") == sources["run_attempt"], "API listing provenance mismatch")
    instances = [item.get("instance_id") for item in artifacts]
    require(len(set(instances)) == 30 and set(instances) == set(expected_ids), "incomplete case source coverage")
    result = {}
    run_ids = set()
    for source in artifacts:
        receipt = mapped[source["id"]]
        digest = source.get("digest", "")
        require(type(digest) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is not None,
                "source API digest is not a SHA-256 identity")
        require(source.get("implementation_sha") == expected_sha, "source artifact SHA mismatch")
        for field in ("source_run_id", "run_attempt"):
            require(type(source.get(field)) is int and source[field] > 0, "invalid source run identity")
            require(receipt.get(field) == source[field] == sources[field], "transport source run mismatch")
        require(receipt.get("name") == source.get("name") and receipt.get("sha256") == digest[7:] and
                type(receipt.get("bytes")) is int and receipt["bytes"] > 0 and
                receipt.get("instance_id") == source["instance_id"] and
                receipt.get("implementation_sha") == expected_sha, "transport ZIP identity mismatch")
        expected_name = f"knapsack-feasibility-case-{source['instance_id']}-{source['source_run_id']}-{source['run_attempt']}"
        require(source.get("name") == expected_name, "unrecognized case artifact name")
        matches = [item for item in metadata_rows if item.get("id") == source["id"]]
        require(len(matches) == 1, "source ID is missing or duplicated in retained API metadata")
        metadata = matches[0]
        require(metadata.get("name") == source["name"] and metadata.get("digest") == digest and
                metadata.get("expired") is False and metadata.get("size_in_bytes") == receipt["bytes"],
                "API artifact identity differs from retained transport")
        workflow = metadata.get("workflow_run", {})
        require(workflow.get("id") == source["source_run_id"] and workflow.get("head_sha") == expected_sha and
                workflow.get("head_branch") == "research/masters-ga-knapsack-parameters", "API artifact belongs to another workflow")
        run_ids.add(source["source_run_id"])
        result[source["instance_id"]] = source
    require(len(run_ids) == 1, "case sources mix distinct workflow runs")
    return result


def _score3(instance, mask: str) -> dict:
    return {key: value for key, value in evaluate_mask(instance, mask).items() if key != "feasible"}


def _valid_score3(record: dict) -> bool:
    return (isinstance(record, dict) and set(record) == {"mask", "weight", "profit"} and
            type(record.get("mask")) is str and type(record.get("weight")) is int and type(record.get("profit")) is int)


def _verify_preparation(instance, preparation: dict) -> None:
    """Replay the declared deterministic preparation without the ascent module."""
    require(isinstance(preparation, dict) and preparation.get("schema_version") == "knapsack-feasibility-ascent-v1",
            "unknown center preparation schema")
    order = sorted(range(instance.n), key=lambda i: (-Fraction(instance.profits[i], instance.weights[i]), i))
    bits = ["0"] * instance.n
    weight = 0
    for index in order:
        if weight + instance.weights[index] <= instance.capacity:
            bits[index] = "1"
            weight += instance.weights[index]
    current = _score3(instance, "".join(bits))
    greedy = preparation.get("greedy", {})
    require(isinstance(greedy, dict) and type(greedy.get("weight")) is int and type(greedy.get("profit")) is int and
            type(greedy.get("items_considered")) is int and
            all(greedy.get(key) == value for key, value in current.items()) and
            greedy.get("item_order") == order and greedy.get("items_considered") == instance.n and
            greedy.get("ratio_comparison") == "exact_integer_cross_products" and
            greedy.get("ratio_tie_break") == "smaller_original_zero_based_index", "incorrect greedy preparation")
    trace = preparation.get("pass_trace")
    require(isinstance(trace, list) and 1 <= len(trace) <= 100 and
            type(preparation.get("max_passes")) is int and type(preparation.get("passes_completed")) is int and
            preparation.get("max_passes") == 100 and preparation.get("passes_completed") == len(trace),
            "incomplete preparation passes")
    expected_count = instance.n + instance.n * (instance.n - 1) // 2
    stopped = False
    for pass_index, row in enumerate(trace, 1):
        require(isinstance(row, dict) and type(row.get("pass")) is int and
                all(type(row.get(field)) is int for field in ("neighbor_queries", "feasible_neighbors",
                                                             "infeasible_neighbors", "strictly_improving_neighbors")) and
                _valid_score3(row.get("center_before")) and _valid_score3(row.get("center_after")), "invalid ascent record types")
        require(not stopped and row.get("pass") == pass_index and row.get("center_before") == current,
                "broken ascent state continuation")
        candidates = itertools.chain(((i,) for i in range(instance.n)), itertools.combinations(range(instance.n), 2))
        best_profit, best_flips = current["profit"], None
        feasible, improving = 0, 0
        # Exact source-based deltas replay selection; accepted masks use fresh sums.
        for flips in candidates:
            changed_weight = current["weight"]
            changed_profit = current["profit"]
            for index in flips:
                sign = -1 if current["mask"][index] == "1" else 1
                changed_weight += sign * instance.weights[index]
                changed_profit += sign * instance.profits[index]
            if changed_weight > instance.capacity:
                continue
            feasible += 1
            if changed_profit <= current["profit"]:
                continue
            improving += 1
            if changed_profit > best_profit or (changed_profit == best_profit and (best_flips is None or flips < best_flips)):
                best_profit, best_flips = changed_profit, flips
        require(row.get("flipped_indices") == (list(best_flips) if best_flips is not None else None) and
                type(row.get("strict_improvement")) is bool and row["strict_improvement"] == (best_flips is not None),
                "ascent did not choose the registered best strictly improving neighbor")
        mask = list(current["mask"])
        for index in best_flips or ():
            mask[index] = "0" if mask[index] == "1" else "1"
        current = _score3(instance, "".join(mask))
        require(row.get("center_after") == current and row.get("neighbor_queries") == expected_count and
                row.get("feasible_neighbors") == feasible and row.get("infeasible_neighbors") == expected_count - feasible and
                row.get("strictly_improving_neighbors") == improving, "inconsistent ascent pass proof")
        stopped = best_flips is None
    require(_valid_score3(preparation.get("center")) and preparation.get("center") == current and
            type(preparation.get("neighbor_queries")) is int and type(preparation.get("index_base")) is int and
            preparation.get("natural_stop") is stopped and
            preparation.get("preparation_capped") is (not stopped) and
            preparation.get("neighbor_queries") == len(trace) * expected_count and
            preparation.get("index_base") == 0 and preparation.get("rng_used") is False and
            preparation.get("independent_certificate_issued") is False, "inconsistent preparation summary")
    require(stopped or len(trace) == 100, "premature cap before the registered hundredth pass")
    require(preparation.get("status") == ("NATURAL_STOP_UNCERTIFIED" if stopped else "EXCLUDED_PREPARATION_CAP"),
            "preparation status mismatch")


def _validate_case(folder: Path, instance, source_file: dict, source: dict,
                   expected_sha: str, frozen_provenance: dict) -> tuple[dict, bool]:
    case = read_json(folder / "case.json")
    require(case.get("schema_version") == "knapsack-feasibility-case-v1", "unknown case schema")
    expected_identity = {"instance_id": instance.instance_id, "class_label": instance.class_label,
                         "family": instance.family, "index": instance.index, "n": instance.n,
                         "capacity": instance.capacity}
    require(all(case.get(key) == value for key, value in expected_identity.items()) and
            all(type(case.get(key)) is int for key in ("index", "n", "capacity")), "case source identity mismatch")
    data_sha = frozen_provenance["data_manifest_sha256"]
    provenance = case.get("provenance")
    _provenance(provenance, expected_sha, data_sha)
    require(provenance["run_id"] == source["source_run_id"] and provenance["run_attempt"] == source["run_attempt"] and
            provenance.get("artifact_name") == source["name"], "case is not from its pinned source artifact")
    for field in ("input_file_manifest_sha256", "runtime_lock_sha256", "audit_transport_sha256",
                  "python_version", "source_audit_run_id", "source_audit_artifact_id"):
        require(provenance.get(field) == frozen_provenance.get(field) and field in frozen_provenance,
                f"frozen audit/runtime anchor differs: {field}")
    identity = {"source_path": instance.source_path, "sha256": source_file["sha256"], "bytes": source_file["bytes"],
                "data_manifest_sha256": data_sha, "source_commit_sha": SOURCE_SHA}
    require(case.get("source_identity") == identity, "case data bytes do not match frozen input manifest")
    _verify_files(folder, provenance)
    status = case.get("status")
    require(status in ALL_STATUSES, "unknown or unfinished case status")
    terminal = read_json(folder / "execution-status.json")
    require(terminal.get("instance_id") == instance.instance_id and terminal.get("status") == status and
            terminal.get("provenance") == provenance, "terminal case identity/status mismatch")
    if status in INCOMPLETE_STATUSES:
        failure = case.get("failure")
        require(isinstance(failure, dict) and type(failure.get("type")) is str and type(failure.get("message")) is str,
                "technically incomplete case has no retained failure reason")
        return case, False
    require(case.get("failure") is None, "complete case has an unexplained failure")
    exact = case.get("exact", {})
    verified = {}
    for method in ("capacity", "profit"):
        result = exact.get(method)
        verified[method] = validate_witness(instance, result)
        dimension = min(instance.capacity, sum(instance.weights)) if method == "capacity" else sum(instance.profits)
        expected_method = ("capacity_max_profit_dp_with_witness_exclude_current_item_on_equal" if method == "capacity"
                           else "profit_min_weight_dp_independent_transition_core")
        require(result.get("method") == expected_method and type(result.get("dimension")) is int and
                result["dimension"] == dimension and type(result.get("conceptual_cells")) is int and
                result["conceptual_cells"] == (instance.n + 1) * (dimension + 1) and
                dimension <= 200000 and result["conceptual_cells"] <= 20000100, "exact method resource identity mismatch")
    optimum = exact.get("confirmed_optimum")
    require(type(optimum) is int and optimum == exact["capacity"]["optimum_profit"] == exact["profit"]["optimum_profit"] and
            exact.get("witness_verified") is True and exact.get("witness_verification") == verified,
            "exact methods and independently verified witnesses disagree")
    preparation = case.get("preparation")
    _verify_preparation(instance, preparation)
    center = evaluate_mask(instance, preparation["center"]["mask"])
    require(center["feasible"] and center["profit"] <= optimum, "prepared center is infeasible or exceeds exact optimum")
    if status == "EXCLUDED_PREPARATION_CAP":
        require(preparation["preparation_capped"] is True and case.get("certificate") is None and
                case.get("neighbors_file") is None and not (folder / "neighbors.csv").exists(), "cap case has a forbidden certificate")
    else:
        require(preparation["natural_stop"] is True, "uncapped case lacks natural completion")
        neighbor_file = case.get("neighbors_file")
        require(isinstance(neighbor_file, dict) and neighbor_file.get("file") == "neighbors.csv", "missing neighbor file identity")
        path = _safe_file(folder, neighbor_file["file"])
        require(neighbor_file == {"file": path.name, "bytes": path.stat().st_size, "sha256": _sha(path.read_bytes())},
                "neighbor bytes differ from case identity")
        certificate = validate_certificate(instance, case.get("certificate"), path)
        require(certificate["center"] == center and certificate["local_maximum"] is True, "independent local certificate failed")
        expected_status = ("EXCLUDED_GLOBAL_CENTER" if center["profit"] == optimum else
                           "ADMITTED_STRICT_LOCAL" if certificate["strict"] else "ADMITTED_PLATEAU_LOCAL")
        require(status == expected_status, "local/global admission status differs from independent proof")
    return case, True


def _write_json(path: Path, value) -> None:
    path.write_bytes((json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))


def _csv_bytes(rows: list[dict], columns: tuple[str, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _decision(entries: list[dict]) -> dict:
    admitted = [row for row in entries if row["status"] in {"ADMITTED_STRICT_LOCAL", "ADMITTED_PLATEAU_LOCAL"}]
    families = sorted({row["family"] for row in admitted})
    complete = all(row["technically_complete"] for row in entries)
    decision = ("TECHNICALLY_INCOMPLETE" if not complete else
                "MINIMUM_FEASIBILITY_MET" if len(families) >= 5 else "LOCAL_SERIES_NOT_READY")
    return {"decision": decision, "technically_complete": complete,
            "admitted_center_count": len(admitted), "nonempty_admitted_family_count": len(families),
            "nonempty_admitted_families": families,
            "minimum_family_count": 5,
            "full_GA_series_authorized": False,
            "statistical_power_established": False}


def _table_row(entry: dict) -> dict:
    case = entry["payload"]
    complete = entry["technically_complete"]
    preparation = case.get("preparation") or {}
    certificate = case.get("certificate") or {}
    return {"instance_id": entry["instance_id"], "class": entry["class_label"], "family": entry["family"],
            "capacity": case["capacity"], "greedy_profit": preparation.get("greedy", {}).get("profit") if complete else None,
            "center_profit": preparation.get("center", {}).get("profit") if complete else None,
            "center_weight": preparation.get("center", {}).get("weight") if complete else None,
            "exact_optimum": case.get("exact", {}).get("confirmed_optimum") if complete else None,
            "locality": "strict" if certificate.get("strict") else "plateau" if certificate.get("plateau") else "uncertified",
            "neighbor_count": certificate.get("neighbor_count") if complete else None,
            "status": entry["status"], "technically_complete": complete}


def build_registry(root: Path, expected_sha: str, sources_path: Path, ledger_path: Path,
                   output: Path, *, inputs: Path = DEFAULT_INPUTS) -> dict:
    require(re.fullmatch(r"[0-9a-f]{40}", expected_sha) is not None, "implementation SHA must be exact")
    require(not Path(root).is_symlink(), "case collection cannot be a symlink")
    root, output, inputs = Path(root).resolve(), Path(output).resolve(), Path(inputs)
    require(root.is_dir(), "missing complete case collection")
    require(not output.exists() or not any(output.iterdir()), "retained registry evidence cannot be overwritten")
    require(not output.is_relative_to(Path(__file__).resolve().parents[3]) and
            not output.is_relative_to(root) and not root.is_relative_to(output), "registry output must be isolated")
    instances, provenance = load_frozen_inputs(expected_sha, inputs=inputs)
    verified_instances, manifest = verify_input_bundle(inputs)
    require(instances == verified_instances and len(instances) == 30 and
            manifest.get("instance_count") == manifest.get("expected_instance_count") == 30,
            "incomplete frozen input registry")
    expected_ids = [f"{label}-s{index:03d}" for label, _ in CLASSES for index in range(10)]
    require([instance.instance_id for instance in instances] == expected_ids and
            all(instance.n == 100 for instance in instances), "frozen input order/dimension differs")
    data_raw = (inputs / "data_manifest.json").read_bytes()
    require(_sha(data_raw) == provenance["data_manifest_sha256"], "frozen manifest byte identity differs")
    _provenance(provenance, expected_sha, provenance["data_manifest_sha256"])
    provenance["artifact_name"] = f"knapsack-feasibility-report-{provenance['run_id']}-{provenance['run_attempt']}"
    sources_path, ledger_path = Path(sources_path), Path(ledger_path)
    api_path = sources_path.parent / "artifact-api-metadata.json"
    sources, ledger, api_metadata = read_json(sources_path), read_json(ledger_path), read_json(api_path)
    selected = _transport(sources, ledger, expected_ids, expected_sha, api_metadata)
    require(sources["source_run_id"] == provenance["run_id"] and sources["run_attempt"] == provenance["run_attempt"],
            "aggregation does not belong to the pinned source run/attempt")
    case_paths = list(root.rglob("case.json"))
    require(len(case_paths) == 30 and {path.parent for path in case_paths} == {root / value for value in expected_ids},
            "missing, duplicate or nested case identities")
    source_rows = {row["source_path"]: row for row in manifest["source_files"]}
    entries = []
    for instance in instances:
        source = selected[instance.instance_id]
        folder = root / instance.instance_id
        case, complete = _validate_case(folder, instance, source_rows[instance.source_path], source, expected_sha, provenance)
        entries.append({"instance_id": instance.instance_id, "class_label": instance.class_label,
                        "family": instance.family, "index": instance.index, "status": case["status"],
                        "technically_complete": complete, "file_integrity_verified": True,
                        "scientific_proofs_verified": complete,
                        "source_artifact_id": source["id"], "source_artifact_name": source["name"],
                        "source_artifact_digest": source["digest"], "source_run_id": source["source_run_id"],
                        "source_run_attempt": source["run_attempt"],
                        "retained_case_path": f"cases/{instance.instance_id}/case.json", "payload": case})
    decision = _decision(entries)
    selected_case = next((row["instance_id"] for row in entries if row["status"].startswith("ADMITTED_")), expected_ids[0])
    registry = {"schema_version": "knapsack-feasibility-registry-v1", "protocol_id": PROTOCOL_ID,
                "protocol_sha256": PROTOCOL_SHA256, "registration_commit_sha": REGISTRATION_SHA,
                "implementation_sha": expected_sha, "data_freeze_commit_sha": FREEZE_SHA,
                "data_manifest_sha256": provenance["data_manifest_sha256"], "provenance": provenance,
                "source_run_id": sources["source_run_id"], "source_run_attempt": sources["run_attempt"],
                "all_30_accounted": True, "case_count": 30, "case_order": expected_ids, "cases": entries,
                "family_comparisons": manifest["family_comparisons"], "selected_document_case": selected_case,
                "status_counts": {status: sum(row["status"] == status for row in entries) for status in sorted(ALL_STATUSES)},
                **decision}
    output.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        shutil.copytree(root / entry["instance_id"], output / "cases" / entry["instance_id"])
    for path, name in ((sources_path, "sources.json"), (ledger_path, "transport-ledger.json"), (api_path, "artifact-api-metadata.json")):
        shutil.copyfile(path, output / name)
    (output / "data_manifest.json").write_bytes(data_raw)
    _write_json(output / "registry.json", registry)
    rows = [_table_row(entry) for entry in entries]
    (output / "cases.csv").write_bytes(_csv_bytes(rows, tuple(rows[0])))
    (output / "report_UK.md").write_text(_report(registry, rows, {instance.instance_id: instance for instance in instances}),
                                       encoding="utf-8", newline="\n")
    members = [_identity(path, output) for path in sorted(output.rglob("*"))
               if path.is_file() and path.relative_to(output).as_posix() != "file_manifest.json"]
    _write_json(output / "file_manifest.json", {"schema_version": "knapsack-feasibility-files-v1", "excludes_self": True,
                                               "provenance": provenance, "files": members})
    return registry


def _report(registry: dict, rows: list[dict], instances: dict) -> str:
    decisions = {"TECHNICALLY_INCOMPLETE": "Технічно неповно",
                 "LOCAL_SERIES_NOT_READY": "Локальна серія не готова",
                 "MINIMUM_FEASIBILITY_MET": "Мінімальний критерій здійсненності виконано"}
    lines = ["# 5. ФАКТИЧНІ РЕЗУЛЬТАТИ ПІДГОТОВКИ", "",
             f"У реєстрі враховано {registry['case_count']} задач. Рішення: {decisions[registry['decision']]}. "
             f"Допущено {registry['admitted_center_count']} центрів у {registry['nonempty_admitted_family_count']} сімействах.", "",
             "Позначення класів: UC означає некорельовані задачі, WC слабко корельовані, SC сильно корельовані. "
             "Символ C позначає місткість. Цінності наведено в умовних одиницях. Строгий максимум і плато визначено щодо допустимого сусідства у радіусі два.", "",
             "Таблиця 5.1. Повний реєстр підготовки тридцяти задач", "",
             "| Задача | C | Жадібна цінність | Цінність центра | Оптимум | Тип | Допуск |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        locality = {"strict": "Строгий", "plateau": "Плато", "uncertified": "Не підтверджено"}[row["locality"]]
        status = "Так" if row["status"].startswith("ADMITTED_") else STATUS_UK[row["status"]]
        values = [row["instance_id"], row["capacity"], row["greedy_profit"], row["center_profit"], row["exact_optimum"], locality, status]
        lines.append("| " + " | ".join("Не оцінено" if value is None else str(value) for value in values) + " |")
    lines.extend(["", "*Недопущені задачі залишено в реєстрі без заміни. Глобальний підготовлений центр не доводить відсутності інших неглобальних локальних максимумів у цій задачі.*", "",
                  "## 5.1 Спільність вихідних масивів", ""])
    for first, second in itertools.combinations(("UC", "WC", "SC"), 2):
        comparisons = [row for row in registry["family_comparisons"] if row["classes"] == [first, second]]
        counts = {field: sum(row.get(field) is True for row in comparisons) for field in ("weights_equal", "profits_equal", "capacity_equal")}
        lines.append(f"Для пари класів {first} і {second} точний збіг ваг виявлено у {counts['weights_equal']} з 10 сімейств, "
                     f"цінностей у {counts['profits_equal']}, місткостей у {counts['capacity_equal']}.\n")
    lines.extend(["*Ці числа описують точні збіги вихідних даних, а не коефіцієнти кореляції чи доказ незалежності сімейств.*", "",
                  "## 5.2 Наперед визначений приклад центра", ""])
    selected = next(entry for entry in registry["cases"] if entry["instance_id"] == registry["selected_document_case"])
    case, instance = selected["payload"], instances[selected["instance_id"]]
    lines.append(f"Обрано {selected['instance_id']}: {STATUS_UK[selected['status']]}. "
                 "Це перший допущений випадок у погодженому порядку; якщо допущених немає, використовується UC-s000.")
    preparation = case.get("preparation")
    if preparation:
        center = preparation["center"]
        positions = [i + 1 for i, bit in enumerate(center["mask"]) if bit == "1"]
        lines.extend(["", f"Жадібна цінність: {preparation['greedy']['profit']}. Цінність центра: {center['profit']}; "
                      f"вага: {center['weight']} за місткості {instance.capacity}. Обрано {len(positions)} предметів. "
                      f"Підйом завершив {preparation['passes_completed']} проходів.", "",
                      "Маска центра; позиції бітів зліва направо відповідають предметам 1–100:", "", "```", center["mask"], "```", "",
                      "Індекси обраних предметів: " + ", ".join(map(str, positions)) + "."])
        certificate = case.get("certificate")
        if certificate:
            lines.extend(["", f"Незалежно перевірено {certificate['neighbor_count']} сусідів. Допустимих кращих: {certificate['higher_feasible']}; "
                          f"рівноцінних: {certificate['equal_feasible']}; гірших: {certificate['lower_feasible']}; недопустимих: {certificate['invalid_count']}."])
        exact = case.get("exact", {})
        if exact.get("witness_verified"):
            witness = exact["capacity"]["witness_mask"]
            distance = sum(a != b for a, b in zip(center["mask"], witness))
            lines.extend(["", f"Обидва точні методи підтвердили оптимум {exact['confirmed_optimum']}. "
                          f"Наведений оптимальний свідок відрізняється від центра у {distance} позиціях:", "", "```", witness, "```"])
    if case.get("failure"):
        lines.extend(["", "Причина неповної підготовки: " + case["failure"]["type"] + ". " + case["failure"]["message"]])
    lines.extend(["", "*Приклад не є запуском генетичного алгоритму. Відстань до наведеного оптимального свідка не визначає найменшу відстань до будь-якого кращого набору та не доводить необхідності прямого стрибка для популяційного пошуку.*", "",
                  "# 6. РІШЕННЯ ТА МЕЖІ ВИСНОВКІВ", "", decisions[registry["decision"]] + ".",
                  "Перехід до повної серії цим етапом не дозволений. Вихідні дані, точні свідки, журнали підйому й усі сусіди збережено для перевірки. "
                  "Мінімальний критерій у п'ять сімейств не встановлює статистичної потужності або наукової новизни.", "",
                  "*Не досліджено взаємодії параметрів GA, частоту виходу з максимумів, різноманітність популяцій чи перевагу над точним розв'язанням. "
                  "Погані результати не замінено повтореннями; дані й пороги не змінено за отриманими підсумками.*", "",
                  "# ДОДАТОК А. ПОХОДЖЕННЯ РЕЗУЛЬТАТІВ", "",
                  f"Протокол: {PROTOCOL_ID}. SHA реалізації: {registry['implementation_sha']}.",
                  f"Запуск: https://github.com/ChepaMaksym/GA-article-test/actions/runs/{registry['source_run_id']}; спроба {registry['source_run_attempt']}.",
                  "Реєстр джерел містить усі тридцять artifact ID, окремі хеші транспортних ZIP та внутрішніх файлів. Великі DP-таблиці не включено.", ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--transport-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, default=DEFAULT_INPUTS)
    args = parser.parse_args(argv)
    result = build_registry(args.root, args.expected_sha, args.sources, args.transport_ledger, args.output, inputs=args.inputs)
    print(json.dumps({key: result[key] for key in ("case_count", "decision", "admitted_center_count", "nonempty_admitted_family_count")}))
    return 0 if result["technically_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

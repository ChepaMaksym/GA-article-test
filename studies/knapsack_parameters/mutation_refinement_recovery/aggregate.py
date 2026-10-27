"""Aggregate authenticated saved pilot workers without invoking search or API.

The recovery authority must authenticate original source, artifact identities
and completed source jobs before calling this function. Original search and
recovery execution retain separate provenance. Historical code is unchanged.
"""
from pathlib import Path

from ..mutation_refinement import authority as a
from ..mutation_refinement.driver import cost_review, validate_record_accounting


SOURCE_FIELDS = ("protocol_id", "registration_sha", "implementation_sha",
                 "source_manifest", "run_id", "run_attempt")


def _registry(source_provenance):
    registry = a.read_json(a.MODULE / "inputs/pilot/bank_registry.json")
    a.require(registry.get("schema") == "mutation-refinement-bank-registry-v1" and
              registry.get("stage") == "pilot" and registry.get("conditions") == 8 and
              registry.get("pilot_runs") == 40 and registry.get("new_search_calls") == 0 and
              registry.get("new_exact_solves") == 0, "Wrong frozen preparation registry")
    for name in ("protocol_id", "registration_sha", "source_manifest"):
        a.require(registry.get(name) == source_provenance[name], "Mixed preparation provenance: " + name)
    a.require(type(registry.get("physical_preparation_evaluations")) is int and
              registry["physical_preparation_evaluations"] == 124 and
              type(registry.get("logical_initial_positions")) is int and
              registry["logical_initial_positions"] == 240 and
              type(registry.get("existing_center_validation_score_checks")) is int and
              registry["existing_center_validation_score_checks"] == 4,
              "Wrong frozen preparation accounting")
    return registry


def aggregate_saved(workers, output, source_provenance, recovery_provenance):
    """Validate the unchanged forty-run rectangle, then aggregate saved data.

    No permit checks, network requests, GA calls, scoring or replay occur here.
    Root recovery authority supplies provenance only after authenticating the
    original artifacts and successful completion of all four producer jobs.
    """
    a.require(type(source_provenance) is dict and all(k in source_provenance for k in SOURCE_FIELDS),
              "Missing authenticated source provenance")
    a.require(type(recovery_provenance) is dict and bool(recovery_provenance),
              "Missing separate recovery provenance")
    output, workers = Path(output), Path(workers)
    output.mkdir(parents=True, exist_ok=True)
    a.require(not any((output / name).exists() for name in
                      ("pilot_summary.json", "cost_review.json", "audit_status.json")),
              "Existing recovery outputs must be preserved")
    seen, records, errors, receipts = set(), [], [], []
    expected_keys = {(task, start, 97999, method) for task in a.PILOT_TASKS
                     for start in a.STARTS for method in a.METHODS}
    seen_keys = set()
    for path in sorted(workers.rglob("worker_summary.json")):
        try:
            a.verify_manifest(path.parent)
            row = a.read_json(path)
            a.require(row.get("schema") == "mutation-refinement-worker-v1" and row.get("stage") == "pilot" and
                      row.get("worker") in set(a.PILOT_TASKS) - seen, "Foreign or duplicate producer")
            seen.add(row["worker"])
            for field in SOURCE_FIELDS:
                a.require(row.get(field) == source_provenance[field], "Mixed producer provenance: " + field)
            a.require(row.get("complete") is True and not row.get("errors") and
                      row.get("expected_runs") == row.get("verified_runs") == len(row["records"]) == 10,
                      "Incomplete producer")
            checked_bytes = 0
            for record in row["records"]:
                key = record["task"], record["start"], record["seed"], record["method"]
                a.require(key in expected_keys - seen_keys and key[0] == row["worker"],
                          "Foreign/duplicate search condition")
                seen_keys.add(key)
                log_path = a.safe_child(path.parent, record["log_path"])
                a.require(a.identity(log_path) == record["log_identity"], "Full gzip journal identity differs")
                basename = log_path.name.removesuffix(".json.gz")
                metadata = a.read_json(path.parent / "metadata" / (basename + ".json"))
                a.require(metadata.get("verification_status") == "VERIFIED" and metadata.get("record") == record,
                          "Compact record does not match replay receipt")
                for field in SOURCE_FIELDS:
                    a.require(metadata.get(field) == source_provenance[field], "Mixed replay receipt: " + field)
                a.require(record["new_search_evaluations"] == record["summary"]["physical_evaluations"] == 5000 and
                          record["independent_replay_score_checks"] == 10030,
                          "Wrong independent evaluation accounting")
                validate_record_accounting(record)
                checked_bytes += record["log_identity"]["bytes"]
                records.append(record)
            a.require(checked_bytes == row["compressed_journal_bytes"], "Wrong worker log byte accounting")
            receipts.append({k: row[k] for k in
                             ("worker", "verified_runs", "compressed_journal_bytes", "worker_ns",
                              "bank_validation_ns", "bank_validation_initial_score_checks",
                              "existing_center_validation_score_checks")})
        except Exception as exc:
            errors.append({"path": path.relative_to(workers).as_posix(), "error": str(exc)})
    registry = None
    try:
        registry = _registry(source_provenance)
    except Exception as exc:
        errors.append({"path": "frozen preparation registry", "error": str(exc)})
    complete = seen == set(a.PILOT_TASKS) and seen_keys == expected_keys and len(records) == 40 and not errors
    status = {**source_provenance, "recovery_provenance": recovery_provenance, "stage": "pilot",
              "complete": complete, "expected_runs": 40, "verified_runs": len(records),
              "workers": receipts, "errors": errors, "new_search_performed_during_aggregation": False}
    a.write_json(output / "audit_status.json", status)
    a.write_manifest(output)
    a.require(complete, "Incomplete saved pilot retained; cost forecast blocked")
    costs = {"new_search_evaluations": sum(r["new_search_evaluations"] for r in records),
             "initial_preparation_physical_evaluations": registry["physical_preparation_evaluations"],
             "initial_preparation_logical_positions": registry["logical_initial_positions"],
             "preparation_existing_center_score_checks": registry["existing_center_validation_score_checks"],
             "worker_existing_center_score_checks": sum(w["existing_center_validation_score_checks"] for w in receipts),
             "bank_validation_initial_score_checks": sum(w["bank_validation_initial_score_checks"] for w in receipts),
             "engine_initial_validation_evaluations": sum(r["engine_initial_score_validation_evaluations"] for r in records),
             "engine_premutation_observational_evaluations": sum(r["engine_premutation_observational_evaluations"] for r in records),
             "independent_replay_score_checks": sum(r["independent_replay_score_checks"] for r in records),
             "independent_replay_initial_score_checks": sum(r["independent_replay_initial_score_checks"] for r in records),
             "independent_replay_final_score_checks": sum(r["independent_replay_final_score_checks"] for r in records),
             "independent_replay_premutation_score_checks": sum(r["independent_replay_premutation_score_checks"] for r in records),
             "independent_replay_split_is_breakdown_of_total": True,
             "compressed_journal_bytes": sum(w["compressed_journal_bytes"] for w in receipts), "new_exact_solves": 0}
    summary = {**status, "costs": costs, "records": records, "statistical_bootstrap_performed": False,
               "scientific_superiority_established": False, "calibration_authorized": False, "main_authorized": False}
    a.write_json(output / "pilot_summary.json", summary)
    forecast = cost_review(records, receipts)
    forecast.update({"source_provenance": source_provenance, "recovery_provenance": recovery_provenance,
                     "new_search_performed_during_aggregation": False})
    a.write_json(output / "cost_review.json", forecast)
    (output / "REPORT_UK.md").write_text(
        "# Технічний пілот уточнення мутації\n\n"
        "Перевірено 40/40 збережених запусків на чотирьох старих задачах із двома початками й п'ятьма правилами. "
        "На кожний запуск припадає 5000 нових пошукових оцінювань; повні журнали залишаються в початкових worker-артефактах.\n\n"
        "Відновлено лише зведення після технічної помилки перевірки стану jobs. Пошук не повторювали. "
        "Походження початкових результатів і виконання відновлення записано окремо.\n\n"
        "Підготовку, перевірки початків і незалежне відновлення обліковано окремо. Проміжні оцінки до мутації "
        "є частиною незалежної перевірки, а не додатковими пошуковими оцінюваннями.\n\n"
        "Це технічна перевірка й вимірювання ресурсів. Наукову перевагу або новизну не встановлено; "
        "калібрування, нові точні еталони та основну серію не дозволено. Прогноз не є повним кошторисом або дозволом.\n",
        encoding="utf-8")
    a.write_manifest(output)
    return summary

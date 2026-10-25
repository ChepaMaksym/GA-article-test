"""Explicit, bounded CI phases. Search is never dispatched by import."""
from __future__ import annotations

import argparse
import gzip
import math
import os
from pathlib import Path
import sys
from time import perf_counter_ns
import traceback
import unittest

from . import authority as a


def run_tests(output, permit):
    provenance = a.check_permit(permit, "tests")
    suite = unittest.defaultTestLoader.discover(str(a.MODULE / "tests"), pattern="test_*.py", top_level_dir=str(a.ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    a.write_json(Path(output) / "tests_receipt.json", {**provenance, "tests_passed": result.wasSuccessful(),
                 "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                 "skipped": len(result.skipped), "scientific_search_performed": False,
                 "heldout_search_performed": False, "scientific_bootstrap_performed": False,
                 "instructional_fixtures_only": True, "new_exact_solves": 0})
    a.write_manifest(output)
    a.require(result.wasSuccessful() and not result.skipped and result.testsRun > 0, "Checks not fully green")


def balanced_order(condition, stage):
    a.require(stage in ("pilot", "main"), "Unknown execution stage")
    index = (2 * condition["task_index"] + condition["start_index"] if stage == "pilot" else
             30 * condition["task_index"] + condition["seed"] - 97001)
    return tuple((index + offset) % 32 for offset in range(32))


def run_worker(stage, worker, output, permit):
    from . import analysis, banks, engine
    started_worker = perf_counter_ns()
    provenance = a.check_permit(permit, stage)
    started = perf_counter_ns()
    beginnings = banks.load_frozen_banks(stage, check_scores=True, selected_worker=worker)
    bank_validation_ns = perf_counter_ns() - started
    expected = [row for row in banks.expected_conditions(stage) if row["worker"] == worker]
    count = 64 if stage == "pilot" else 576
    a.require(expected and len(beginnings) == len(expected) and len(beginnings) * 32 == count, "Wrong worker rectangle")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records, errors, compressed_bytes = [], [], 0
    grant = a.grant_for(stage)
    try:
        sources = {bank["task"]: banks.source_case(bank["task"], stage) for bank in beginnings}
        for bank in beginnings:
            source = sources[bank["task"]]
            for order_index, profile in enumerate(balanced_order(bank, stage)):
                started = perf_counter_ns()
                log = engine.run_search(bank["problem"], bank["initial_masks"], bank["initial_scores"], profile,
                                        engine.make_rngs(bank["seed"], bank["task_index"], bank["start_index"]), budget=5000)
                search_wall_ns = perf_counter_ns() - started
                basename = f"{bank['task']}-{bank['start']}-{bank['seed']}-p{profile:02d}"
                log_relative = f"logs/{basename}.json.gz"
                started = perf_counter_ns()
                raw = gzip.compress(a.canonical(log), mtime=0)
                path = output / log_relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                serialization_ns = perf_counter_ns() - started
                compressed_bytes += len(raw)
                metadata = {**provenance, "stage": stage, "task": bank["task"], "start": bank["start"],
                            "seed": bank["seed"], "profile": profile, "order_index": order_index,
                            "log_path": log_relative, "log_identity": a.identity(path),
                            "verification_status": "PENDING_INDEPENDENT_REPLAY",
                            "bank_identity": a.identity(a.MODULE / "inputs" / stage / "banks" /
                                                        f"{bank['task']}-{bank['start']}-{bank['seed']}.json"),
                            "source_identity": source["source_identity"]}
                # Retain the journal even if independent replay fails. Never
                # substitute another seed for a failed or negative result.
                a.write_json(output / "metadata" / (basename + ".json"), metadata)
                envelope = {"task": bank["task"], "family": bank["family"], "start": bank["start"],
                            "seed": bank["seed"], "profile": profile, "stage": stage,
                            "implementation_sha": provenance["implementation_sha"], "optimum": source["optimum"], "log": log,
                            "timings": {"search_wall_ns": search_wall_ns, "serialization_ns": serialization_ns,
                                        "verification_ns": None, "preparation_ns": bank["preparation_ns"]}}
                started = perf_counter_ns()
                row = analysis.extract_run(envelope)
                row["timings"]["verification_ns"] = perf_counter_ns() - started
                records.append(row)
                metadata.update({"verification_status": "VERIFIED", "timings": row["timings"]})
                a.write_json(output / "metadata" / (basename + ".json"), metadata)
                a.require(compressed_bytes <= a.journal_allowance(stage, grant), "Compressed journal quota exceeded")
                print(f"VERIFIED {basename}: 5000 new calls", flush=True)
                del log, envelope, raw
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        a.write_json(output / "worker_summary.json", {**provenance, "schema": "parameter-dynamics-worker-v1",
                     "stage": stage, "worker": worker, "expected_runs": count, "verified_runs": len(records),
                     "complete": len(records) == count and not errors, "records": records, "errors": errors,
                     "compressed_journal_bytes": compressed_bytes, "worker_ns": perf_counter_ns() - started_worker,
                     "bank_validation_ns": bank_validation_ns, "bank_validation_initial_score_checks": 30 * len(beginnings),
                     "known_bank_conditions": len(beginnings)})
        a.write_manifest(output)


def cost_review(records, receipts):
    """Conservative prospective cost; this function cannot authorize a run."""
    a.require(len(records) == 256 and len(receipts) == 4, "Complete registered pilot required")
    seconds = [sum(row["timings"][key] for key in ("search_wall_ns", "verification_ns", "serialization_ns")) / 1e9
               for row in records]
    maximum = max(max(seconds), max(row["worker_ns"] / row["verified_runs"] / 1e9 for row in receipts))
    timeout = max(2, math.ceil(1.5 * maximum * 576 / 60) + 2)
    compressed = sum(row["compressed_journal_bytes"] for row in receipts)
    return {"pilot_runs": 256, "per_run_seconds_maximum": maximum, "per_run_seconds_mean": sum(seconds) / 256,
            "future_main_runs": 28800, "future_new_search_calls": 144000000, "forecast_main_jobs": 50,
            "forecast_worker_timeout_minutes": timeout,
            "forecast_main_runner_minutes_with_reservations": 50 * (timeout + 1) + 35,
            "pilot_compressed_journal_bytes": compressed,
            "forecast_main_compressed_journal_bytes_with_50pct_reserve": math.ceil(compressed * 28800 / 256 * 1.5),
            "future_source_exact_solves": 60, "source_preparation_measured": False,
            "main_authorized": False,
            "interpretation": "Measured search/replay forecast with 50% reserve; fresh-source preparation remains unmeasured."}


def write_report(summary, rendering, output, forecast):
    lines = ["# Еволюція параметрів генетичного алгоритму", "",
             "## Питання та метод", "",
             "Як керування мутацією, схрещуванням, популяцією, турнірним відбором та елітизмом змінює пошук розв’язку задачі рюкзака?", "",
             "Алгоритм формує нове покоління з елітних особин і нащадків. Параметри змінюються лише після завершеного покоління. "
             "Новий розмір популяції реалізується звичайним створенням нащадків наступного покоління; усі оцінювання враховано.", "",
             "## Перевірені результати", "",
             f"Незалежно перевірено {summary['runs']} запусків і {summary['new_search_evaluations']} нових оцінювань.", "",
             "| Початок | Варіант | Запуски | Відставання від оптимуму, % | Досягли 95% | Досягли 99% |", "|---|---|---:|---:|---:|---:|"]
    labels = {0: "Сталі параметри", 1: "Мутація", 2: "Схрещування", 4: "Популяція", 8: "Турнір", 16: "Елітизм", 31: "Усі п’ять правил"}
    for cell in summary["profile_cells"]:
        if cell["profile"] in labels:
            lines.append(f"| {cell['start']} | {labels[cell['profile']]} | {cell['runs']} | {cell['mean_final_gap_percent']:.4f} | "
                         f"{cell['targets']['95']['attained']} | {cell['targets']['99']['attained']} |")
    lines += ["", "## Активність правил", "", "| Початок | Варіант | Параметр | Зміни у запусках | Збільшення | Зменшення |", "|---|---|---|---:|---:|---:|"]
    for cell in summary["activity_cells"]:
        if cell["profile"] == 31:
            lines.append(f"| {cell['start']} | Усі правила | {cell['field']} | {cell['changed_runs']}/{cell['runs']} | {cell['increases']} | {cell['decreases']} |")
    lines += ["", "## Динаміка та якість", ""]
    for item in rendering["figures"]:
        lines += [f"![{item['caption']}](figures/{item['file']})", "", f"Рисунок {item['number']}. {item['caption']}", ""]
    lines += ["## Межі висновків", ""]
    if summary["scope"] == "pilot":
        lines += ["Один технічний повтор перевіряє правильність реалізації, активність правил і ресурси. "
                  "Він не встановлює переваги, статистичної стійкості чи наукової новизни. Підтверджувальні інтервали не обчислювалися."]
    else:
        lines += ["Шість первинних ефектів порівнюють окремі адаптації та спільне керування зі сталим контролем. "
                  "Взаємодії решти поєднань мають описовий характер."]
    lines += ["", "Власні правила є наперед визначеними евристиками. Нова маска, більша різноманітність і довгий застій самі по собі не доводять покращення або локальної оптимальності. "
              "Час пошуку, запису та незалежної перевірки вимірюється окремо; внутрішні складові часу не додаються повторно."]
    if forecast:
        lines += ["", "## Наступний етап", "",
                  f"Прогноз основної серії становить {forecast['forecast_main_runner_minutes_with_reservations']} runner-хвилин із резервуванням. "
                  "Обробку нових джерельних задач ще не виміряно. Кошторис не є дозволом основної серії."]
    (Path(output) / "REPORT_UK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def aggregate(stage, workers, output, permit):
    from . import analysis, plots
    provenance = a.check_permit(permit, stage)
    expected = set(a.PILOT_TASKS if stage == "pilot" else a.MAIN_WORKERS)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    seen, records, errors, receipts = set(), [], [], []
    for path in sorted(Path(workers).rglob("worker_summary.json")):
        try:
            a.verify_manifest(path.parent)
            row = a.read_json(path)
            a.require(row.get("worker") in expected - seen and row.get("stage") == stage and
                      row.get("schema") == "parameter-dynamics-worker-v1", "Foreign or duplicate producer")
            seen.add(row["worker"])
            for key in ("implementation_sha", "source_manifest", "run_id", "run_attempt", "protocol_id"):
                a.require(row.get(key) == provenance[key], "Mixed producer provenance: " + key)
            count = 64 if stage == "pilot" else 576
            a.require(row.get("complete") is True and not row.get("errors") and
                      row.get("expected_runs") == row.get("verified_runs") == len(row["records"]) == count, "Incomplete producer")
            records.extend(row["records"])
            receipts.append({key: row[key] for key in ("worker", "verified_runs", "compressed_journal_bytes", "worker_ns", "bank_validation_ns")})
            receipts[-1]["manifest_identity"] = a.identity(path.parent / "file_manifest.json")
        except Exception as exc:
            errors.append({"path": path.relative_to(Path(workers)).as_posix(), "error": str(exc)})
    jobs = [job for job in a.pages(f"/actions/runs/{provenance['run_id']}/attempts/{provenance['run_attempt']}/jobs", "jobs")
            if job["name"].startswith(stage + " (")]
    if {job["name"] for job in jobs} != {f"{stage} ({name})" for name in expected} or len(jobs) != len(expected) or any(job.get("conclusion") != "success" for job in jobs):
        errors.append({"error": "Not all exact source jobs completed successfully"})
    count = 256 if stage == "pilot" else 28800
    if stage == "main" and sum(row["compressed_journal_bytes"] for row in receipts) > a.grant_for(stage)["maximum_compressed_journal_bytes_total"]:
        errors.append({"error": "Total compressed journal quota exceeded"})
    audit = {**provenance, "stage": stage, "expected_runs": count, "verified_runs": len(records), "errors": errors,
             "complete": seen == expected and len(records) == count and not errors, "workers": receipts,
             "new_search_performed_during_aggregation": False}
    a.write_json(output / "audit_status.json", audit)
    a.write_manifest(output)
    a.require(audit["complete"], "Incomplete series retained; full analysis blocked")
    summary = analysis.aggregate(records, scope=stage, expected_sha=provenance["implementation_sha"])
    rendering = plots.render_report(summary, output / "figures")
    forecast = cost_review(records, receipts) if stage == "pilot" else None
    if forecast:
        a.write_json(output / "cost_review.json", forecast)
    a.write_json(output / "series_summary.json", summary)
    (output / "compact_records.json.gz").write_bytes(gzip.compress(a.canonical(records), mtime=0))
    a.write_json(output / "rendering_receipt.json", rendering)
    write_report(summary, rendering, output, forecast)
    a.write_manifest(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "tests", "prepare", "worker", "aggregate"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--permit")
    parser.add_argument("--stage", choices=("pilot", "main"))
    parser.add_argument("--worker")
    parser.add_argument("--workers")
    args = parser.parse_args()
    try:
        selected = a.phase(os.environ.get("COMMIT_MESSAGE", ""))
        if args.command == "preflight":
            a.preflight(selected, args.output)
        elif args.command == "tests":
            a.require(selected == "tests" and args.permit, "Wrong tests phase")
            run_tests(args.output, args.permit)
        elif args.command == "prepare":
            from . import banks
            a.require(selected == "prepare-" + str(args.stage) and args.permit, "Wrong preparation phase")
            banks.prepare(args.stage, args.output, a.check_permit(args.permit, selected))
        elif args.command == "worker":
            a.require(selected == args.stage and args.permit and args.worker, "Wrong worker phase")
            run_worker(args.stage, args.worker, args.output, args.permit)
        else:
            a.require(selected == args.stage and args.permit and args.workers, "Wrong aggregation phase")
            aggregate(args.stage, args.workers, args.output, args.permit)
    except Exception as exc:
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        a.write_json(output / "failure.json", {"type": type(exc).__name__, "message": str(exc), "command": args.command})
        a.write_manifest(output)
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

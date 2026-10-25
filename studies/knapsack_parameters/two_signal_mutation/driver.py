"""Explicit CI phase dispatcher; no implicit search and no local execution."""
from __future__ import annotations

import argparse
import gzip
import itertools
import math
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
    receipt = {**provenance, "tests_passed": result.wasSuccessful(), "tests_run": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
               "scientific_search_performed": False, "heldout_search_performed": False,
               "scientific_bootstrap_performed": False, "instructional_fixtures_only": True, "new_exact_solves": 0}
    a.write_json(Path(output) / "tests_receipt.json", receipt)
    a.write_manifest(output)
    a.require(result.wasSuccessful() and not result.skipped and result.testsRun > 0, "Program checks not fully green")


def balanced_order(condition, stage):
    permutations = tuple(sorted(itertools.permutations(a.METHODS)))
    index = condition["task_index"] * 2 + condition["start_index"] if stage == "pilot" else condition["seed"] - 94001
    return permutations[index % 6]


def run_worker(stage, worker, output, permit):
    from . import analysis, banks, engine
    started_worker = perf_counter_ns()
    provenance = a.check_permit(permit, stage)
    validation_started = perf_counter_ns()
    beginnings = banks.load_frozen_banks(stage, check_scores=True, selected_worker=worker)
    bank_validation_ns = perf_counter_ns() - validation_started
    expected = banks.expected_conditions(stage)
    if stage == "pilot":
        a.require(worker in banks.PILOT_TASKS, "Unknown pilot worker")
        chosen = [bank for bank in beginnings if bank["task"] == worker]
        expected_count = 6
    else:
        a.require(worker in {f"s{i:03d}" for i in range(10, 20)}, "Unknown main family worker")
        chosen = [bank for bank in beginnings if bank["family"] == worker]
        expected_count = 270
    a.require(len(chosen) * 3 == expected_count, "Wrong worker beginning count")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records, errors, compressed_bytes = [], [], 0
    grant = a.grant_for(stage)
    try:
        for bank in chosen:
            source = banks.source_case(bank["task"], stage)
            for order_index, method in enumerate(balanced_order(bank, stage)):
                started = perf_counter_ns()
                log = engine.run_search(bank["problem"], bank["initial_masks"], bank["initial_scores"], method,
                                        engine.make_rngs(bank["seed"], bank["task_index"], bank["start_index"]), budget=5000)
                search_wall_ns = perf_counter_ns() - started
                basename = f"{bank['task']}-{bank['start']}-{bank['seed']}-{method}"
                log_relative = f"logs/{basename}.json.gz"
                serialization_started = perf_counter_ns()
                raw = gzip.compress(a.canonical(log), mtime=0)
                path = output / log_relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                serialization_ns = perf_counter_ns() - serialization_started
                compressed_bytes += len(raw)
                metadata = {**provenance, "stage": stage, "task": bank["task"], "start": bank["start"],
                            "seed": bank["seed"], "method": method, "order_index": order_index,
                            "log_path": log_relative, "log_identity": a.identity(path),
                            "verification_status": "PENDING_INDEPENDENT_REPLAY",
                            "bank_identity": a.identity(a.MODULE / "inputs" / stage / "banks" /
                                                        f"{bank['task']}-{bank['start']}-{bank['seed']}.json"),
                            "source_identity": source["source_identity"]}
                # Persist the candidate journal BEFORE replay: a verifier failure
                # must never erase the run or permit replacement by a new seed.
                a.write_json(output / "metadata" / (basename + ".json"), metadata)
                envelope = {"task": bank["task"], "family": bank["family"], "start": bank["start"],
                            "seed": bank["seed"], "method": method, "implementation_sha": provenance["implementation_sha"],
                            "optimum": source["optimum"], "log": log,
                            "timings": {"search_wall_ns": search_wall_ns, "serialization_ns": serialization_ns,
                                        "verification_ns": None, "preparation_ns": bank["preparation_ns"]}}
                verification_started = perf_counter_ns()
                row = analysis.extract_run(envelope)
                verification_ns = perf_counter_ns() - verification_started
                row["timings"]["verification_ns"] = verification_ns
                records.append(row)
                metadata.update({"verification_status": "VERIFIED", "timings": row["timings"]})
                a.write_json(output / "metadata" / (basename + ".json"), metadata)
                a.require(compressed_bytes <= grant["maximum_compressed_bytes_per_worker"], "Compressed journal cap exceeded")
                print(f"VERIFIED {basename}: 5000 new calls", flush=True)
                del envelope, log, raw
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        a.write_json(output / "worker_summary.json", {**provenance, "schema": "two-signal-worker-v1", "stage": stage,
                     "worker": worker, "expected_runs": expected_count, "verified_runs": len(records),
                     "complete": len(records) == expected_count and not errors, "records": records, "errors": errors,
                     "compressed_journal_bytes": compressed_bytes, "worker_ns": perf_counter_ns() - started_worker,
                     "bank_validation_ns": bank_validation_ns,
                     "bank_validation_initial_score_checks": 30 * len(chosen),
                     "source_center_validation_checks": 2 * len(chosen),
                     "known_bank_conditions": len(expected)})
        a.write_manifest(output)


def cost_review(records, stage, worker_receipts):
    """Resource forecast only; scientific settings are never selected here."""
    a.require(stage == "pilot" and len(records) == 24, "Full fixed pilot required for a cost forecast")
    values = [sum(row["timings"][key] for key in ("search_wall_ns", "verification_ns", "serialization_ns")) / 1e9
              for row in records]
    maximum = max(max(values), max(row["worker_ns"] / row["verified_runs"] / 1e9 for row in worker_receipts))
    worker_timeout = max(2, math.ceil(1.5 * maximum * 270 / 60) + 2)
    projected_ceiling = 2 + 10 * (worker_timeout + 1) + 9 + 13
    return {"pilot_runs": 24, "per_run_seconds_maximum": maximum, "per_run_seconds_mean": sum(values) / 24,
            "future_main_runs": 2700, "future_new_search_calls": 13500000,
            "forecast_worker_timeout_minutes": worker_timeout,
            "forecast_main_jobs": 10, "forecast_main_runner_minutes_with_reservations": projected_ceiling,
            "main_authorized": False,
            "interpretation": "Conservative measured runtime forecast; separate approval and journal-size forecast required."}


def write_report(summary, rendering, output, forecast=None):
    output = Path(output)
    pilot = summary["scope"] == "pilot"
    lines = ["# Два сигнали для керування мутацією", "",
             "## Перевірені матеріали", "",
             f"Незалежно перевірено {summary['runs']} запусків і {summary['new_search_evaluations']} нових оцінювань.", "",
             "Технічний пілот перевіряє реалізацію та ресурси, не доводить переваги." if pilot else
             "Нова серія порівнює три способи керування одним поколіннєвим генетичним алгоритмом.", "",
             "## Кінцева якість і час до цілі", "",
             "| Початок | Керування | Запуски | Відставання від OPT, % | Досягли 95% | Досягли 99% |",
             "|---|---|---:|---:|---:|---:|"]
    labels = {"fixed": "Стала мутація", "adaptive_mutation": "Сигнал застою", "two_signal": "Два сигнали"}
    for row in summary["method_summaries"]:
        lines.append(f"| {row['start']} | {labels[row['method']]} | {row['runs']} | {row['mean_final_gap_percent']:.4f} | "
                     f"{row['targets']['95']['attained']}/{row['runs']} | {row['targets']['99']['attained']}/{row['runs']} |")
    lines += ["", "Недосягнення цілі збережено. Відомий початок є точкою 0; кінцевий бюджет становить 5000 нових оцінювань.",
              "", "## Два первинні порівняння", ""]
    if pilot:
        lines += ["Підтверджувальні інтервали й кореляції не обчислювалися: один технічний seed не є основною серією."]
    else:
        lines += ["Додатний ефект означає менше відставання нового варіанта.", "",
                  "| Контроль мінус два сигнали | Ефект, в.п. | Нижня межа 97,5% | Верхня межа 97,5% | Статус |",
                  "|---|---:|---:|---:|---|"]
        for interval in summary["primary_analysis"]["intervals"]:
            lo = "н/в" if interval["lower"] is None else f"{interval['lower']:.4f}"
            hi = "н/в" if interval["upper"] is None else f"{interval['upper']:.4f}"
            lines.append(f"| {interval['contrast_id']} | {interval['estimate_gap_points']:.4f} | {lo} | {hi} | {interval['status']} |")
        lines += ["", "Мінімального практично важливого ефекту не задано; статистичний результат не оголошується практичною перевагою автоматично."]
    lines += ["", "## Пояснення рисунків", ""]
    captions = ["Досягнення однакової якості за кількістю нових оцінювань.",
                "Рекорд, середня допустима якість та різноманітність популяції у визначеному прикладі.",
                "Фактична мутація, схожість батьків і рішення контролера у визначеному прикладі.",
                "Новизна, допустимість і корисність проміжного схрещування за відстанню між батьками.",
                "Кінцева якість, заповнення місткості та недопустимі спроби за типом задачі."]
    for index, filename in enumerate(rendering["files"]):
        caption_index = int(filename[:2]) - 1
        lines += [f"![{captions[caption_index]}](figures/{filename})", "", f"Рисунок {index + 1}. {captions[caption_index]}", ""]
    lines += ["## Витрати й обмеження", "",
              "Окремо збережено час пошуку, обчислення сигналу, контролера, запису та незалежної перевірки. "
              "Спостереження сигналу у сталому контролі є витратою дослідження, не обов'язковою частиною алгоритму.", "",
              "Нова маска не обов'язково допустима або краща. Застій та значення сигналу не сертифікують локальний максимум. "
              "Повне сусідство в кожному поколінні не перевіряється. Проміжні оцінки схрещування отримано тільки після пошуку."]
    lines += ["", "| Керування | Складова часу | Відомі вимірювання | Середнє, с |", "|---|---|---:|---:|"]
    for cell in summary["costs"]["profile_metrics"]:
        if cell["metric"] not in ("search_wall_ns", "serialization_ns", "verification_ns", "signal", "controller"):
            continue
        seconds = "н/в" if cell["mean_ns"] is None else f"{cell['mean_ns'] / 1e9:.6f}"
        lines.append(f"| {labels[cell['method']]} | {cell['metric']} | {cell['known_observations']} | {seconds} |")
    lines += ["", "Складові часу мають вкладені області й не додаються механічно. Підготовка спільного початку враховується один раз на умову."]
    if forecast:
        lines += ["", "## Наступний ресурсний етап", "",
                  f"Прогноз основної серії: {forecast['forecast_main_runner_minutes_with_reservations']} runner-хвилин із резервуванням; "
                  "це виміряний кошторис, не дозвіл виконання. Потрібне окреме погодження та перевірка обсягу журналів."]
    (output / "REPORT_UK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def aggregate(stage, workers, output, permit):
    from . import analysis, plots
    provenance = a.check_permit(permit, stage)
    roots = sorted(Path(workers).rglob("worker_summary.json"))
    expected_workers = {"UC-s000", "WC-s001", "SC-s005", "SC-s000"} if stage == "pilot" else {f"s{i:03d}" for i in range(10, 20)}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    seen, records, errors, worker_receipts = set(), [], [], []
    for path in roots:
        try:
            a.verify_manifest(path.parent)
            receipt = a.read_json(path)
            a.require(receipt.get("worker") in expected_workers - seen and receipt.get("stage") == stage and
                      receipt.get("schema") == "two-signal-worker-v1", "Foreign or duplicate worker")
            seen.add(receipt["worker"])
            for key in ("implementation_sha", "source_manifest", "run_id", "run_attempt", "protocol_id"):
                a.require(receipt.get(key) == provenance[key], "Mixed worker execution: " + key)
            a.require(receipt.get("complete") is True and not receipt.get("errors"), "Incomplete worker")
            records.extend(receipt["records"])
            worker_receipts.append({"worker": receipt["worker"], "verified_runs": receipt["verified_runs"],
                                    "compressed_journal_bytes": receipt["compressed_journal_bytes"],
                                    "worker_ns": receipt["worker_ns"], "manifest_identity": a.identity(path.parent / "file_manifest.json")})
        except Exception as exc:
            errors.append({"path": path.relative_to(Path(workers)).as_posix(), "error": str(exc)})
    job_prefix = "pilot (" if stage == "pilot" else "main ("
    jobs = [job for job in a.pages(f"/actions/runs/{provenance['run_id']}/attempts/{provenance['run_attempt']}/jobs", "jobs")
            if job["name"].startswith(job_prefix)]
    if len(jobs) != len(expected_workers) or any(job.get("conclusion") != "success" for job in jobs):
        errors.append({"error": "Not all source worker jobs completed successfully"})
    expected_runs = 24 if stage == "pilot" else 2700
    audit = {**provenance, "stage": stage, "verified_runs": len(records), "expected_runs": expected_runs,
             "complete": seen == expected_workers and len(records) == expected_runs and not errors,
             "errors": errors, "workers": worker_receipts, "new_search_performed_during_aggregation": False}
    a.write_json(output / "audit_status.json", audit)
    if not audit["complete"]:
        a.write_manifest(output)
        raise ValueError("Incomplete series retained; no full analysis or plots produced")
    summary = analysis.aggregate(records, scope=stage, expected_sha=provenance["implementation_sha"])
    rendering = plots.render_report(summary, output / "figures")
    forecast = cost_review(records, stage, worker_receipts) if stage == "pilot" else None
    if forecast:
        compressed = sum(row["compressed_journal_bytes"] for row in worker_receipts)
        forecast["pilot_compressed_journal_bytes"] = compressed
        forecast["forecast_main_compressed_journal_bytes_with_50pct_reserve"] = math.ceil(compressed / 24 * 2700 * 1.5)
        a.write_json(output / "cost_review.json", forecast)
    a.write_json(output / "series_summary.json", summary)
    a.write_json(output / "compact_records.json", records)
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
        selected = a.phase(__import__("os").environ.get("COMMIT_MESSAGE", ""))
        if args.command == "preflight":
            a.preflight(selected, args.output)
        elif args.command == "tests":
            a.require(selected == "tests" and args.permit, "Wrong tests phase")
            run_tests(args.output, args.permit)
        elif args.command == "prepare":
            from . import banks
            a.require(selected == "prepare-" + str(args.stage) and args.permit, "Wrong preparation phase")
            provenance = a.check_permit(args.permit, selected)
            banks.prepare(args.stage, args.output, provenance)
        elif args.command == "worker":
            a.require(selected == args.stage and args.permit and args.worker, "Wrong worker phase")
            run_worker(args.stage, args.worker, args.output, args.permit)
        else:
            a.require(selected == args.stage and args.permit and args.workers, "Wrong aggregation phase")
            aggregate(args.stage, args.workers, args.output, args.permit)
    except Exception as exc:
        directory = Path(args.output)
        directory.mkdir(parents=True, exist_ok=True)
        a.write_json(directory / "failure.json", {"type": type(exc).__name__, "message": str(exc), "command": args.command})
        a.write_manifest(directory)
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

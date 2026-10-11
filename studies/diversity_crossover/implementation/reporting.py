"""Post-matrix descriptive aggregation; no inferential statistics or new search."""

from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path

from .banks import METHODS, PROTOCOL, SEED, STARTS, TASKS
from .contract import (api, authenticate, canonical_bytes, ci_only, file_identity,
                       require, source_manifest, verify_file_manifest,
                       write_file_manifest, write_json)
from .runner import JOB_SCHEMA, RUN_SCHEMA

LABELS = {"baseline": "Базовий", "directed": "Спрямований добір",
          "repeated": "Чотири нащадки", "mutation_control": "Без схрещування"}


def inspect_task(directory, expected_sha, expected_source):
    """Reject incomplete inventories, duplicate identities and mixed source revisions."""
    directory = Path(directory)
    verify_file_manifest(directory)
    task = json.loads((directory / "task_results.json").read_text(encoding="utf-8"))
    require(task["schema_version"] == JOB_SCHEMA and task["protocol_id"] == PROTOCOL and
            task["implementation_sha"] == expected_sha and task["seed"] == SEED,
            "wrong task protocol/source/seed")
    require(task["task"] in TASKS and task["task_index"] == TASKS.index(task["task"]), "wrong task identity")
    actual_source = json.loads((directory / "source_manifest.json").read_text(encoding="utf-8"))
    require(canonical_bytes(actual_source) == canonical_bytes(expected_source), "mixed implementation fingerprints")
    require(len(task["runs"]) == task["expected_runs"] == 8, "task run inventory is incomplete")
    require(task["compressed_bytes"] <= task["compressed_limit"] == 536870912, "compressed output ceiling exceeded")
    rows, seen = [], set()
    for row in task["runs"]:
        identity = (row["task"], row["start"], row["method"])
        require(identity[0] == task["task"] and identity[1] in STARTS and identity[2] in METHODS and
                identity not in seen, "duplicate or unregistered run identity")
        seen.add(identity)
        expected = f"runs/{identity[0]}-{identity[1]}-{identity[2]}"
        require(row["path"] == expected, "unsafe run path")
        summary = json.loads((directory / expected / "summary.json").read_text(encoding="utf-8"))
        require(summary["schema_version"] == RUN_SCHEMA and summary["protocol_id"] == PROTOCOL and
                summary["implementation_sha"] == expected_sha and summary["seed"] == SEED and
                tuple(summary[k] for k in ("task", "start", "method")) == identity,
                "run summary identity/source mismatch")
        require(summary["status"] == row["status"] and summary["bank_manifest_sha256"] ==
                task["bank_manifest_sha256"] and summary["preparation_sha"] == task["preparation_sha"],
                "run status/bank identity mismatch")
        require(summary.get("run_id") == task.get("run_id") and
                summary.get("run_attempt") == task.get("run_attempt"), "mixed source run/attempt")
        if summary["status"] == "COMPLETE":
            require(summary["search"]["new_calls"] == summary["search"]["physical_calls"] == 5000,
                    "registered search call count is not complete")
            verification = json.loads((directory / expected / "verification.json").read_text(encoding="utf-8"))
            require(verification["status"] == "VERIFIED" and canonical_bytes(verification["summary"]) ==
                    canonical_bytes(summary["search"]), "independent reconstruction mismatch")
            require(file_identity(directory / expected / "journal.jsonl.gz") == summary["journal_identity"] and
                    file_identity(directory / expected / "trace.json.gz") == summary["trace_identity"],
                    "journal/trace identity mismatch")
            with gzip.open(directory / expected / "trace.json.gz", "rt", encoding="utf-8") as stream:
                trace = json.load(stream)
            require(trace and trace[0]["call"] == 0 and trace[-1]["call"] == 5000,
                    "trace lacks initial/final state")
            summary["trace"] = trace
        rows.append(summary)
    require(seen == {(task["task"], s, m) for s in STARTS for m in METHODS}, "missing method/start")
    require(task["complete_runs"] == sum(r["status"] == "COMPLETE" for r in rows), "task completion count mismatch")
    return task, rows


def source_receipts():
    """Verify completion and pin actual source artifacts of this exact run/attempt."""
    run_id, attempt = int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    run = api(f"/actions/runs/{run_id}")
    require(run["head_sha"] == os.environ["GITHUB_SHA"], "source run SHA mismatch")
    jobs, page = [], 1
    while True:
        batch = api(f"/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100&page={page}")["jobs"]
        jobs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    # The aggregate job is still active; all eight source jobs must already have ended.
    source_jobs = [j for j in jobs if any(t in j["name"] for t in TASKS) and "pilot" in j["name"].lower()]
    require(len(source_jobs) == 8 and all(j["status"] == "completed" for j in source_jobs),
            "aggregation started before all source matrix jobs ended")
    artifacts, page = [], 1
    while True:
        batch = api(f"/actions/runs/{run_id}/artifacts?per_page=100&page={page}")["artifacts"]
        artifacts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    records = []
    for task in TASKS:
        expected_name = f"diversity-pilot-{task}-{run_id}-{attempt}"
        found = [a for a in artifacts if a["name"] == expected_name]
        if len(found) == 1:
            artifact = found[0]
            require(not artifact["expired"] and artifact.get("workflow_run", {}).get("head_sha") == run["head_sha"],
                    "artifact is expired or belongs to another source SHA")
            digest = artifact.get("digest")
            require(isinstance(digest, str) and digest.startswith("sha256:") and len(digest) == 71,
                    "artifact lacks a trustworthy ZIP digest")
            records.append({"task": task, "status": "AVAILABLE", "artifact_id": artifact["id"],
                            "artifact_name": expected_name, "zip_sha256": digest[7:],
                            "size_in_bytes": artifact["size_in_bytes"], "expires_at": artifact["expires_at"]})
        else:
            require(len(found) == 0, "duplicate artifact identity")
            records.append({"task": task, "status": "MISSING_ARTIFACT", "artifact_name": expected_name})
    return {"run_id": run_id, "run_attempt": attempt, "head_sha": run["head_sha"],
            "run_url": run["html_url"], "source_jobs": [{k: j.get(k) for k in
              ("id", "name", "status", "conclusion", "started_at", "completed_at")} for j in source_jobs],
            "artifacts": records}


def plot_examples(rows, output):
    """Fixed examples only; separate record, population mean and diversity axes."""
    ci_only()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    styles = {"baseline": ("#171717", "-"), "directed": ("#155e9b", "--"),
              "repeated": ("#a34a18", "-."), "mutation_control": ("#777777", ":")}
    figure_dir = Path(output) / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for task in ("UC-s000", "Jump4"):
        for start in STARTS:
            selected = {r["method"]: r for r in rows if r["task"] == task and r["start"] == start and
                        r["status"] == "COMPLETE"}
            fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
            for method in METHODS:
                if method not in selected:
                    continue
                trace = selected[method]["trace"]
                xs = [p["call"] for p in trace]
                color, line = styles[method]
                for axis, field in zip(axes, ("best_value", "mean_feasible_value", "diversity"), strict=True):
                    axis.plot(xs, [p[field] for p in trace], color=color, linestyle=line,
                              linewidth=1.4, label=LABELS[method])
            for axis, label in zip(axes, ("Найкраща оцінка", "Середня оцінка\nдопустимих особин", "Відстань Геммінга D"), strict=True):
                axis.set_ylabel(label)
                axis.grid(alpha=0.2)
            ds = [p["diversity"] for r in selected.values() for p in r["trace"]]
            # Shared scale within each comparison, not a full 0..1 axis that hides small changes.
            axes[2].set_ylim(0, min(1.0, max(0.05, max(ds, default=0.0) * 1.1)))
            axes[2].set_xlabel("Нові пошукові оцінювання")
            axes[0].legend(fontsize=9, ncol=2)
            start_label = "копії центра" if start == "cloned" else "спільний банк"
            fig.suptitle(f"{task}, {start_label}; технічний seed 70001")
            fig.text(0.5, 0.005, "Один технічний запуск. Лінії не є довірчими інтервалами або доказом переваги.",
                     ha="center", fontsize=8)
            fig.tight_layout(rect=(0, 0.025, 1, 0.96))
            if not selected:
                axes[0].text(0.5, 0.5, "Немає повного перевіреного запуску", transform=axes[0].transAxes, ha="center")
            for extension in ("png", "pdf"):
                filename = f"figures/{task}-{start}.{extension}"
                fig.savefig(Path(output) / filename, dpi=180)
                files.append(filename)
            plt.close(fig)
    return files


def render_report(report):
    complete = report["complete_runs"]
    lines = ["# Технічний пілот різноманітності та схрещування", "",
             f"Протокол: {PROTOCOL}. Статус: {report['status']}.", "",
             f"Завершено й незалежно перевірено {complete} із 64 запусків. "
             f"Нові пошукові оцінювання завершених запусків: {report['completed_search_calls']}.", "",
             "Це технічний пілот з одним seed 70001. Він перевіряє реалізацію й доказові журнали, "
             "а не статистичну перевагу, новизну або універсальність методу.", "",
             "## Повнота і фактичні результати", "",
             "| Задача | Початок | Метод | Рекорд на початку → наприкінці | Вихід | Нові запити | Статус |",
             "| --- | --- | --- | --- | --- | ---: | --- |"]
    for row in report["runs"]:
        if row["status"] == "COMPLETE":
            search = row["search"]
            record = f"{row['initial_value']} → {search['record']['score']['value']}"
            escape = ("так" if row["escape"] else "ні") if row["escape_applicable"] else "не застосовується"
            calls = search["new_calls"]
        else:
            record, escape, calls = "неповні докази", "не встановлено", "—"
        lines.append(f"| {row['task']} | {row['start']} | {LABELS[row['method']]} | {record} | {escape} | {calls} | {row['status']} |")
    lines += ["", "## Облік і незалежна перевірка", "",
              f"Підготовчі фізичні оцінювання (одноразово): {report.get('preparation_physical_calls', 'невідомо')}. "
              f"Перевірні оцінювання в повних журналах: {report['independent_journal_verification_calls']}. "
              f"Повторна перевірка цілісності банків у jobs: {report['bank_integrity_verification_calls']}.", "",
              "Початкові відомі оцінки не зараховано як новий пошук. Повторні пошукові запити, "
              "дублікати та недопустимі маски зараховано. Не змішано рекорд, середню оцінку популяції та різноманітність.", "",
              "## Наперед визначені рисунки", "",
              "Для UC-s000 та Jump4 обидва початки показано окремо. Верхня панель відповідає питанню "
              "«який найкращий результат оцінено?», середня «яка середня оцінка допустимої популяції?», "
              "нижня «наскільки відрізняються її хромосоми?». Оцінки неповного завершального пакета "
              "входять до рекорду, але не змінюють популяцію.", "",
              "## Межі висновків і наступний етап", "",
              "*Плоска траєкторія, невихід або неактивний спрямований добір не є технічним провалом. "
              "Середня оцінка різних початків не ізолює лише різноманітність. Пілот не встановлює рівноваги "
              "та не доводить, що адаптивний алгоритм кращий: адаптації λ у ньому немає. Для повної серії "
              "потрібні окреме погодження повторень, статистичної точності й кошторису.*", ""]
    if report["issues"]:
        lines += ["## Неповні випадки", ""] + [f"- {r['task']}: {r['reason']}" for r in report["issues"]] + [""]
    receipts = report.get("source_receipts", {})
    if receipts.get("run_url"):
        lines += ["## Походження", "", f"[Зафіксований CI-запуск]({receipts['run_url']}). "
                  "SHA, artifact IDs, ZIP та внутрішні контрольні суми наведено в report-data.json і файловому реєстрі.", ""]
    return "\n".join(lines)


def aggregate(source, output, expected_sha, *, receipts=None, make_plots=True):
    ci_only()
    provenance = authenticate(expected_sha)
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()), "aggregate output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    sources = source_manifest()
    receipts = receipts if receipts is not None else source_receipts()
    transport_path = Path(source) / "transport_receipts.json"
    if transport_path.exists():
        transported = json.loads(transport_path.read_text(encoding="utf-8"))
        require(transported["run_id"] == receipts["run_id"] and transported["head_sha"] == expected_sha,
                "ZIP transport belongs to a different run")
        for original, downloaded in zip(receipts["artifacts"], transported["artifacts"], strict=True):
            require(original["task"] == downloaded["task"] and original["status"] == downloaded["status"],
                    "ZIP transport inventory differs")
            if original["status"] == "AVAILABLE":
                require(downloaded.get("transport_verified") is True and
                        downloaded["downloaded_zip_sha256"] == original["zip_sha256"], "Unverified source ZIP")
        receipts = transported
    directories = sorted({p.parent for p in Path(source).rglob("task_results.json")})
    rows, issues, seen, manifests, observed_tasks = [], [], set(), [], set()
    preparation_hashes, preparation_shas = set(), set()
    bank_checks, preparation_calls = 0, set()
    for directory in directories:
        task_hint = directory.name
        try:
            task, entries = inspect_task(directory, expected_sha, sources)
            task_hint = task["task"]
            if "run_id" in receipts:
                require(int(task["run_id"]) == receipts["run_id"] and int(task["run_attempt"]) == receipts["run_attempt"],
                        "source output belongs to another run/attempt")
            require(task_hint not in observed_tasks, "duplicate source task")
            observed_tasks.add(task_hint)
            preparation_hashes.add(task["bank_manifest_sha256"])
            preparation_shas.add(task["preparation_sha"])
            bank_checks += task["bank_integrity_verification_calls"]
            preparation_calls.add(task["initial_preparation_physical_calls_all_banks"])
            manifests.append({"task": task_hint, "file_manifest_identity": file_identity(directory / "file_manifest.json"),
                              "task_results_identity": file_identity(directory / "task_results.json")})
            for entry in entries:
                key = (entry["task"], entry["start"], entry["method"])
                require(key not in seen, "duplicate physical run")
                seen.add(key)
                rows.append(entry)
        except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
            issues.append({"task": task_hint, "reason": str(exc)})
    require(len(preparation_hashes) <= 1 and len(preparation_shas) <= 1 and len(preparation_calls) <= 1,
            "mixed prepared banks across source jobs")
    for task in TASKS:
        for start in STARTS:
            for method in METHODS:
                if (task, start, method) not in seen:
                    rows.append({"task": task, "start": start, "method": method,
                                 "status": "MISSING_RESULT", "reason": "source job absent or invalid"})
    rows.sort(key=lambda r: (TASKS.index(r["task"]), STARTS.index(r["start"]), METHODS.index(r["method"])))
    completed = [r for r in rows if r["status"] == "COMPLETE"]
    receipt_rows = receipts.get("artifacts", [])
    sources_valid = (len(receipt_rows) == 8 and {a["task"] for a in receipt_rows} == set(TASKS) and
                     all(a["status"] == "AVAILABLE" for a in receipt_rows))
    if not sources_valid:
        issues.append({"task": "SOURCE_ARTIFACTS", "reason": "not all eight exact source artifacts are available"})
    complete = len(completed) == 64 and not issues and sources_valid
    report = {"schema_version": "diversity-pilot-report-v1", "protocol_id": PROTOCOL,
              "implementation_sha": expected_sha, "status": "COMPLETE_TECHNICAL_PILOT" if complete else "INCOMPLETE_TECHNICAL",
              "expected_runs": 64, "complete_runs": len(completed), "expected_search_calls": 320000,
              "completed_search_calls": sum(r["search"]["new_calls"] for r in completed),
              "independent_journal_verification_calls": sum(r["verification_calls"] for r in completed),
              "bank_integrity_verification_calls": bank_checks,
              "preparation_physical_calls": next(iter(preparation_calls)) if preparation_calls else None,
              "source_receipts": receipts, "source_member_manifests": manifests,
              "bank_manifest_sha256": next(iter(preparation_hashes)) if preparation_hashes else None,
              "preparation_sha": next(iter(preparation_shas)) if preparation_shas else None,
              "issues": issues, "runs": rows,
              "inferential_statistics_performed": False, "scientific_superiority_claim": False}
    if complete:
        require(report["completed_search_calls"] == 320000, "complete pilot call count mismatch")
    report["figures"] = plot_examples(rows, output) if make_plots else []
    # Keep full reconstructed trajectories in compressed source artifacts, not the compact registry.
    compact_rows = [{k: v for k, v in row.items() if k != "trace"} for row in rows]
    report["runs"] = compact_rows
    write_json(output / "report-data.json", report)
    (output / "RESULTS_UK.md").write_text(render_report(report), encoding="utf-8")
    write_json(output / "provenance.json", provenance)
    write_json(output / "source_manifest.json", sources)
    write_file_manifest(output)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = aggregate(args.source, args.output, args.expected_sha)
    if result["status"] != "COMPLETE_TECHNICAL_PILOT":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Fail-closed main-series evidence aggregation, invoked exclusively in CI.

All 90 frozen transport sources and all 35,640 run identities are validated
before endpoint aggregation or plotting. A pilot produces resource/evidence
checks only and cannot enter the primary scientific series.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import gzip
import json
import math
from pathlib import Path
import re

import numpy as np

from .contract import (
    DATA_SHA, MODULE_ROOT, PROTOCOL_ID, PROTOCOL_SHA, REGISTRATION_SHA,
    REGISTRY_SHA, STUDY_ROOT, file_identity, load_context, output_directory,
    read_json, require, safe_member, verify_file_manifest, write_file_manifest,
    write_json,
)
from .engine import configurations
from .statistics import (
    CROSSOVER_PROBABILITIES, MUTATION_NUMERATORS, POPULATION_SIZES,
    bca_family_intervals, descriptive, grouped_family_contrasts,
)


SUMMARY_SCHEMA = "ga-knapsack-main-report-v1"
SOURCES_SCHEMA = "ga-knapsack-sources-v1"
LIMIT = 5000
EXPECTED_RUNS = 35640
EXPECTED_LOGICAL_REQUESTS = 178200000


def expected_jobs(cases: dict, *, phase: str = "main") -> dict:
    """Enumerate identities from frozen cases, never from observed successes."""
    if phase == "main":
        seeds = ((51001, 51010), (51011, 51020), (51021, 51030))
        instance_ids = list(cases)
    elif phase == "pilot":
        seeds = ((52001, 52001),)
        instance_ids = ("UC-s000", "WC-s001", "SC-s005")
    else:
        raise ValueError("phase must be main or pilot")
    output = {}
    for instance_id in instance_ids:
        require(instance_id in cases, "expected instance missing from frozen registry")
        admitted = cases[instance_id]["status"].startswith("ADMITTED_")
        if phase == "pilot":
            require(admitted, "a prespecified pilot center is not admitted")
        for first, last in seeds:
            key = f"{instance_id}-{first}-{last}"
            output[key] = {
                "instance_id": instance_id, "seed_first": first, "seed_last": last,
                "profiles": ("random", "local") if admitted else ("random",),
                "run_count": (last-first+1)*27*(2 if admitted else 1),
            }
    return output


def validate_sources(sources: dict, jobs: dict, expected_sha: str, phase: str) -> list[dict]:
    require(sources.get("schema_version") == SOURCES_SCHEMA, "wrong transport registry schema")
    require(sources.get("phase") == phase and sources.get("implementation_commit_sha") == expected_sha,
            "transport phase/SHA mismatch")
    rows = sources.get("sources")
    require(isinstance(rows, list) and len(rows) == len(jobs), "missing or extra source jobs")
    seen_keys, seen_artifacts = set(), set()
    for source in rows:
        key = source["job_key"]
        require(key in jobs and key not in seen_keys, "unknown or duplicate source job")
        seen_keys.add(key)
        for field in ("instance_id", "seed_first", "seed_last"):
            require(source[field] == jobs[key][field], "source matrix identity mismatch")
        for field in ("run_id", "run_attempt", "artifact_id", "zip_bytes"):
            require(type(source.get(field)) is int and source[field] > 0, "invalid source numeric ID/length")
        require(source["artifact_id"] not in seen_artifacts, "artifact reused for multiple jobs")
        seen_artifacts.add(source["artifact_id"])
        require(isinstance(source.get("artifact_name"), str) and source["artifact_name"], "missing artifact name")
        for field in ("zip_sha256", "job_manifest_sha256"):
            require(re.fullmatch("[0-9a-f]{64}", str(source.get(field))) is not None, "invalid source checksum")
    require(seen_keys == set(jobs), "incomplete source matrix")
    return rows


def validate_summary(row: dict, instance, case: dict, job: dict, identity: dict) -> tuple:
    """Validate independently replayed metrics plus the retained best witness."""
    for field in ("protocol_id", "protocol_sha256", "registration_commit_sha",
                  "implementation_commit_sha", "data_manifest_sha256", "registry_sha256",
                  "runtime_lock_sha256", "banks_manifest_sha256"):
        require(row.get(field) == identity[field], f"run {field} mismatch")
    require(row.get("instance_id") == instance.instance_id, "run instance mismatch")
    require(row.get("source_commit_sha") == "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c" and
            row.get("source_path") == instance.source_path and
            row.get("source_sha256") == case["payload"]["source_identity"]["sha256"] and
            row.get("capacity") == instance.capacity and row.get("bit_item_map") == list(range(1,instance.n+1)),
            "source data/order identity mismatch")
    seed = row.get("repeat_seed")
    require(type(seed) is int and job["seed_first"] <= seed <= job["seed_last"], "seed outside frozen batch")
    profile = row.get("start_profile")
    require(profile in job["profiles"], "unexpected start profile")
    expected_configs = {config.configuration_id: config for config in configurations()}
    config_id = row.get("configuration_id")
    require(config_id in expected_configs, "unknown configuration")
    config = expected_configs[config_id]
    for field, value in config.as_dict().items():
        require(row.get(field) == value, "run parameter mismatch")
    require(row.get("status") == "COMPLETE" and row.get("verified") is True, "incomplete or unverified run")
    require(row.get("logical_requests") == LIMIT and row.get("physical_evaluations") == LIMIT-config.population_size,
            "logical/physical objective-call mismatch")
    verification = row.get("verification", {})
    require(verification.get("status") == "PASS_REPLAY" and
            verification.get("exact_requests_verified") == LIMIT and
            verification.get("rng_and_operator_replay_verified") is True, "missing independent full replay")
    for field in ("best_mask", "best_profit", "best_weight", "best_request", "duplicate_count",
                  "invalid_request_count", "complete_generations", "terminal_partial", "logical_requests",
                  "physical_evaluations", "escape_event", "first_escape_request", "censored"):
        require(row.get(field) == verification.get(field), f"summary/replay mismatch: {field}")
    mask = row.get("best_mask")
    require(isinstance(mask, str) and len(mask) == instance.n and set(mask) <= {"0", "1"}, "invalid best mask")
    weight = sum(int(bit)*value for bit, value in zip(mask, instance.weights, strict=True))
    profit = sum(int(bit)*value for bit, value in zip(mask, instance.profits, strict=True))
    require(weight == row["best_weight"] and profit == row["best_profit"] and weight <= instance.capacity,
            "independent best-mask witness mismatch")
    optimum = case["payload"]["exact"]["confirmed_optimum"]
    require(0 <= profit <= optimum, "observed profit outside confirmed optimum")
    require(type(row["best_request"]) is int and 1 <= row["best_request"] <= LIMIT, "invalid best request index")
    completed, remainder = divmod(LIMIT-config.population_size, config.population_size-1)
    require(row["complete_generations"] == completed and row["terminal_partial"] is bool(remainder),
            "last-generation accounting mismatch")
    for field in ("duplicate_count", "invalid_request_count"):
        require(type(row[field]) is int and 0 <= row[field] <= LIMIT, "invalid request counter")
    if profile == "local":
        center = case["payload"]["certificate"]["center"]["profit"]
        require(type(row.get("escape_event")) is bool and type(row.get("censored")) is bool
                and row["censored"] is not row["escape_event"],
                "escape event/censoring flags mismatch")
        if row["escape_event"]:
            require(type(row.get("first_escape_request")) is int and
                    config.population_size < row["first_escape_request"] <= LIMIT and profit > center,
                    "invalid first evaluated escape")
        else:
            require(row.get("first_escape_request") is None and profit == center, "nonevent changed record")
    else:
        require(row.get("escape_event") is None and row.get("first_escape_request") is None and
                row.get("censored") is None, "random-start result has a local escape endpoint")
    require(isinstance(row.get("run_directory"), str), "missing request/generation log path")
    return instance.instance_id, profile, seed, config_id


def collect_verified_batches(root: Path, sources: dict, cases: dict, instances: dict,
                             identity: dict, *, phase: str = "main") -> tuple[list[dict], list[dict]]:
    jobs = expected_jobs(cases, phase=phase)
    source_rows = validate_sources(sources, jobs, identity["implementation_commit_sha"], phase)
    require(root.is_dir(), "missing extracted job directory")
    require({p.name for p in root.iterdir()} == set(jobs), "unexpected or missing extracted job directories")
    all_rows, seen_runs, resources = [], set(), []
    for source in sorted(source_rows, key=lambda row: row["job_key"]):
        key, job = source["job_key"], jobs[source["job_key"]]
        directory = safe_member(root, key)
        require(directory.is_dir(), "source job is not a directory")
        require(file_identity(directory/"manifest.json")["sha256"] == source["job_manifest_sha256"],
                "job manifest differs from frozen source")
        verify_file_manifest(directory)
        manifest = read_json(directory/"manifest.json")
        for field in ("protocol_id", "protocol_sha256", "registration_commit_sha",
                      "implementation_commit_sha", "data_manifest_sha256", "registry_sha256",
                      "runtime_lock_sha256", "banks_manifest_sha256"):
            require(manifest.get(field) == identity[field], f"batch {field} mismatch")
        for field in ("instance_id", "seed_first", "seed_last"):
            require(manifest.get(field) == job[field], "batch matrix identity mismatch")
        for field in ("run_id", "run_attempt"):
            require(manifest.get(field) == source[field], "batch/source run mismatch")
        require(manifest.get("phase") == phase and manifest.get("job_key") == key and
                manifest.get("python_version") == identity["python_version"] and
                manifest.get("numpy_version") == identity["numpy_version"] and
                manifest.get("matplotlib_version") == identity["matplotlib_version"] and
                manifest.get("requirements_lock_sha256") == identity["requirements_lock_sha256"] and
                manifest.get("implementation_fingerprint") == identity["implementation_fingerprint"],
                "batch phase/implementation/runtime mismatch")
        require(manifest.get("status") == "COMPLETE" and manifest.get("verified") is True,
                "batch is incomplete or not independently verified")
        require(manifest.get("run_count") == job["run_count"] and
                manifest.get("logical_requests") == job["run_count"]*LIMIT, "batch result/call total mismatch")
        declared, names = manifest.get("files"), set()
        require(isinstance(declared, list), "missing batch file inventory")
        for entry in declared:
            relative = entry["path"]
            require(relative not in names and relative not in ("manifest.json", "file_manifest.json"),
                    "duplicate or self-declared batch member")
            names.add(relative)
            require(file_identity(safe_member(directory, relative)) ==
                    {"bytes": entry["bytes"], "sha256": entry["sha256"]}, "batch member changed")
        actual_files = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
        require(actual_files == names | {"manifest.json", "file_manifest.json"}, "unexpected batch payload")
        require("summaries.json" in names, "batch summary absent from hashed inventory")
        rows = read_json(directory/"summaries.json")
        require(isinstance(rows, list) and len(rows) == job["run_count"], "missing run summaries")
        instance = instances[job["instance_id"]]
        expected_ids = {(instance.instance_id, profile, seed, config.configuration_id)
                        for profile in job["profiles"] for seed in range(job["seed_first"],job["seed_last"]+1)
                        for config in configurations()}
        found = set()
        for row in rows:
            run_key = validate_summary(row, instance, cases[instance.instance_id], job, identity)
            require(run_key in expected_ids and run_key not in found and run_key not in seen_runs,
                    "unexpected or duplicate run identity")
            found.add(run_key)
            seen_runs.add(run_key)
            log_directory = safe_member(directory, row["run_directory"])
            for name in ("requests.npz", "generations.jsonl.gz", "summary.json", "search_summary.json", "manifest.json"):
                require((log_directory/name).relative_to(directory).as_posix() in names,
                        "run evidence missing from checksum inventory")
            require(read_json(log_directory/"summary.json") == row, "flat/file run summaries disagree")
            kernel_summary=read_json(log_directory/"search_summary.json")
            require(all(row.get(field)==value for field,value in kernel_summary.items()),
                    "kernel and verified run summary disagree")
            run_manifest=read_json(log_directory/"manifest.json")
            require(run_manifest.get("schema_version")=="ga-knapsack-run-manifest-v1" and
                    run_manifest.get("verified") is True and
                    run_manifest.get("identity")=={field:row[field] for field in
                        ("instance_id","start_profile","repeat_seed","configuration_id","implementation_commit_sha")},
                    "individual run manifest identity mismatch")
            for entry in run_manifest["files"]:
                require(file_identity(safe_member(log_directory,entry["path"]))==
                        {"bytes":entry["bytes"],"sha256":entry["sha256"]},
                        "individual run payload changed")
            # Only retain small summaries and the predefined example's paths.
            result = dict(row)
            result["_job_key"] = key
            result["_job_directory"] = str(directory)
            all_rows.append(result)
        require(found == expected_ids, "incomplete configuration/seed/profile rectangle")
        elapsed = manifest.get("elapsed_seconds")
        require(isinstance(elapsed, (float,int)) and math.isfinite(elapsed) and elapsed > 0,
                "missing or invalid batch resource measurement")
        output_bytes = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
        require(elapsed <= 7200 and output_bytes <= 8*1024**3, "batch resource guard exceeded")
        require(manifest.get("output_bytes")==sum(entry["bytes"] for entry in declared),
                "batch payload length counter mismatch")
        multiplier = 10 if phase == "pilot" else 1
        resources.append({"job_key": key, "elapsed_seconds": elapsed, "output_bytes": output_bytes,
                          "projected_ten_seed_seconds": elapsed*multiplier,
                          "projected_ten_seed_bytes": output_bytes*multiplier,
                          "resource_feasible": elapsed*multiplier <= 7200 and output_bytes*multiplier <= 8*1024**3})
    expected_count = sum(job["run_count"] for job in jobs.values())
    require(len(all_rows) == expected_count and len(seen_runs) == expected_count, "final run completeness mismatch")
    if phase == "main":
        require(expected_count == EXPECTED_RUNS and sum(row["logical_requests"] for row in all_rows)
                == EXPECTED_LOGICAL_REQUESTS, "main series run/call count mismatch")
    return all_rows, resources


def _family_mean(rows: list[dict], cases: dict, extractor) -> float:
    families = defaultdict(lambda: defaultdict(list))
    for row in rows:
        families[cases[row["instance_id"]]["family"]][row["instance_id"]].append(extractor(row))
    return float(np.mean([np.mean([np.mean(repetitions) for repetitions in instances.values()])
                          for instances in families.values()]))


def configuration_summaries(rows: list[dict], cases: dict) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["start_profile"],row["configuration_id"])].append(row)
    output = []
    baseline_id = next(c.configuration_id for c in configurations()
                       if (c.mutation_numerator,c.crossover_probability,c.population_size) == (1.,.9,30))
    baseline = {(r["instance_id"],r["start_profile"],r["repeat_seed"]): r
                for r in rows if r["configuration_id"] == baseline_id}
    def gap(row):
        optimum = cases[row["instance_id"]]["payload"]["exact"]["confirmed_optimum"]
        return (optimum-row["best_profit"])/optimum
    for profile in ("random", "local"):
        for config in configurations():
            runs = grouped[(profile,config.configuration_id)]
            require(bool(runs), "missing profile/configuration summary")
            value = {"start_profile": profile, **config.as_dict(),
                     "baseline": config.configuration_id == baseline_id,
                     "run_count": len(runs), "instance_count": len({r["instance_id"] for r in runs}),
                     "family_count": len({cases[r["instance_id"]]["family"] for r in runs}),
                     "mean_final_relative_gap_equal_family": _family_mean(runs,cases,gap),
                     "final_relative_gap_run_distribution": descriptive([gap(r) for r in runs]),
                     "mean_invalid_request_fraction_equal_family": _family_mean(runs,cases,lambda r:r["invalid_request_count"]/LIMIT),
                     "mean_duplicate_count_equal_family": _family_mean(runs,cases,lambda r:r["duplicate_count"]),
                     "mean_gap_difference_from_baseline_equal_family": _family_mean(
                         runs,cases,lambda r:gap(r)-gap(baseline[(r["instance_id"],profile,r["repeat_seed"])])),
                     "baseline_comparison": "descriptive only; no unregistered superiority test",
                     "logical_requests": len(runs)*LIMIT,
                     "physical_search_evaluations": sum(r["physical_evaluations"] for r in runs)}
            if profile == "local":
                times = [r["first_escape_request"] if r["escape_event"] else LIMIT for r in runs]
                value.update(
                    escape_rate_equal_family=_family_mean(runs,cases,lambda r:int(r["escape_event"])),
                    escape_events=sum(r["escape_event"] for r in runs),
                    censored_nonevents=sum(r["censored"] for r in runs),
                    events_at_limit=sum(r["escape_event"] and r["first_escape_request"] == LIMIT for r in runs),
                    restricted_escape_time_all_runs=descriptive(times),
                    mean_restricted_escape_time_equal_family=_family_mean(
                        runs,cases,lambda r:r["first_escape_request"] if r["escape_event"] else LIMIT),
                )
            output.append(value)
    return output


def preparation_rows(cases: dict) -> list[dict]:
    rows = []
    for instance_id, case in cases.items():
        payload = case["payload"]
        center = payload["preparation"]["center"]
        rows.append({"instance_id":instance_id,"class_label":case["class_label"],"family":case["family"],
                     "capacity":payload["capacity"],"greedy_profit":payload["preparation"]["greedy"]["profit"],
                     "center_profit":center["profit"],"center_weight":center["weight"],"center_mask":center["mask"],
                     "optimum_profit":payload["exact"]["confirmed_optimum"],
                     "status":case["status"],"admitted":case["status"].startswith("ADMITTED_"),
                     "locality":"strict" if payload["certificate"]["strict"] else "plateau",
                     "neighbor_count":payload["certificate"]["neighbor_count"],
                     "reason":None if case["status"].startswith("ADMITTED_") else "center_is_global_optimum"})
    return rows


def primary_statistics(rows: list[dict], cases: dict) -> tuple[list[dict], dict]:
    local = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["start_profile"] == "local":
            key = (row["mutation_numerator"],row["crossover_probability"],row["population_size"])
            local[row["instance_id"]][key].append(int(row["escape_event"]))
    instance_rates = {}
    for instance_id, config_rows in local.items():
        rates = np.empty((3,3,3), dtype=float)
        for m,mutation in enumerate(MUTATION_NUMERATORS):
            for c,crossover in enumerate(CROSSOVER_PROBABILITIES):
                for p,population in enumerate(POPULATION_SIZES):
                    values = config_rows[(mutation,crossover,population)]
                    require(len(values) == 30, "primary endpoint missing seed repetitions")
                    rates[m,c,p] = np.mean(values)
        instance_rates[instance_id] = rates
    metadata = {name:{"family":case["family"],"class_label":case["class_label"]} for name,case in cases.items()}
    memberships, values = grouped_family_contrasts(instance_rates,metadata)
    return memberships,bca_family_intervals(values)


def example_trajectories(rows: list[dict]) -> list[dict]:
    """Read only the three registered configurations of one registered case."""
    output=[]
    for row in rows:
        if (row["instance_id"] != "UC-s000" or row["repeat_seed"] != 51001 or
                row["crossover_probability"] != .9 or row["population_size"] != 30):
            continue
        directory = safe_member(Path(row["_job_directory"]),row["run_directory"])
        with np.load(directory/"requests.npz",allow_pickle=False) as archive:
            requests=archive["request"].astype(int).tolist()
            feasible=archive["feasible"]
            profit=archive["profit"]
            record=np.maximum.accumulate(np.where(feasible,profit,0)).astype(int).tolist()
        generations=[]
        with gzip.open(directory/"generations.jsonl.gz","rt",encoding="utf-8") as stream:
            for line in stream:
                event=json.loads(line)
                if event["generation"] == 0 or event["complete"]:
                    generations.append({"request":event["last_request"],**event["metrics_after"]})
        output.append({"instance_id":row["instance_id"],"repeat_seed":row["repeat_seed"],
                       "start_profile":row["start_profile"],"configuration_id":row["configuration_id"],
                       "mutation_numerator":row["mutation_numerator"],"crossover_probability":.9,
                       "population_size":30,"requests":requests,"best_feasible_profit":record,
                       "population_metrics":generations})
    require(len(output)==6,"registered example trajectories incomplete")
    return sorted(output,key=lambda r:(r["start_profile"],r["mutation_numerator"]))


def write_report_markdown(path: Path, report: dict) -> None:
    def number(value):
        return f"{value:.4f}".replace(".",",")
    lines=["# Результати дослідження параметрів генетичного алгоритму", "",
           "## 1. Постановка й дані", "",
           "Досліджено один поколіннєвий бінарний генетичний алгоритм зі сталими параметрами. "
           "Теоретичною основою є огляд Whitley; пріоритет допустимості відповідає принципу "
           "порівняння за обмеженнями Deb [@whitley1994; @deb2000]. "
           "Це не новий алгоритм і не буквальне числове відтворення авторської реалізації.","",
           "Використано 30 згенерованих задач KPLIB зі 100 предметами. До локальної серії допущено "
           "14 неглобальних центрів у 10 сімействах: 13 строгих максимумів та одне плато. "
           "Ще 16 центрів є глобальними й залишаються в реєстрі без заміни [@kplib; @kellerer2004].", "",
           "Процедура жадібного добору й локального підйому знаходить центри; незалежна перевірка "
           "всіх 5050 одно- й двобітних сусідів підтверджує їхню локальність. Генетичний алгоритм "
           "центрів підготовки не створював.","",
           "*Локальність обмежена допустимим сусідством радіуса два. Початки відрізняються також "
           "початковою якістю та різноманітністю; порівняння не ізолює причинний ефект локальності.*", "",
           "## 2. Метод і простежуваність", "",
           "Два турніри розміру два з поверненням обирають батьків. Рівномірне схрещування "
           "та незалежна побітова мутація створюють одного нащадка; одна елітна особина "
           "переноситься без оцінювання. Недопустимі кандидати не виправляються.","",
           "| Джерело | Компонент | Наша реалізація | Перевірка | Результат |",
           "|---|---|---|---|---|",
           "| Whitley, 1994 | Популяційний генетичний пошук | Точний профіль турніру, схрещування, мутації та елітизму | Незалежне відтворення випадкових рішень | PASS_REPLAY для всіх запусків |",
           "| Deb, 2000 | Перевага допустимості | Без штрафового коефіцієнта й автоматичного виправлення | Точні цілі порівняння | Перевірено всі журнали |",
           "| KPLIB | Вага, цінність і місткість | Початковий порядок предметів збережено | SHA256 вихідних байтів | 30 зафіксованих задач |",
           "| Kellerer та ін., 2004 | Точний еталон | Два незалежні динамічні програмування | Однаковий оптимум і допустимі маски-свідки | 30 точних еталонів |",
           "| Efron, 1987 | BCa | Перевибір цілих сімейств | Спільні індекси й сімейний jackknife | Чотири наперед визначені інтервали |", "",
           "Опорна конфігурація: мутація 1/n, схрещування 0,9, популяція 30. "
           "Вона вже входить до 27 комбінацій і не запускалася вдруге. Аналіз параметрів "
           "рюкзака існував до цієї роботи [@anagun_sarac2006].", "",
           "## 3. Обсяг і первинний показник", "",
           "Повна серія містить 35 640 запусків: 24 300 із випадковим та 11 340 із локальним "
           "початком. Кожний виконав 5000 логічних оцінювань; загалом 178 200 000. "
           "Дублікати й недопустимі кандидати враховано, останні неповні покоління збережено.", "",
           "Вихід означає першу оцінену допустиму маску з цінністю строго більшою за центр, "
           "навіть якщо вона ще не ввійшла до нової популяції. Невиходи не вилучено: їхній "
           "час обмежено 5000 з ознакою цензурування.","",
           "## 4. Чотири первинні контрасти", "",
           "Частки виходу спочатку усереднено за 30 повтореннями, потім за налаштуваннями, "
           "допущеними класами сімейства й рівновагово за сімействами. BCa використовує "
           "50 000 перевибірок цілих сімейств із seed 51031. Для чотирьох порівнянь "
           "застосовано інтервали 98,75% з поправкою Бонферроні [@efron1987].", "",
           "| Контраст | Оцінка, в.п. | Інтервал 98,75%, в.п. | Статус |",
           "|---|---:|---|---|"]
    labels={"mutation_3_over_1":"Мутація 3/n мінус 1/n", "crossover_09_over_0":"Схрещування 0,9 мінус 0",
            "population_50_over_10":"Популяція 50 мінус 10", "mutation_crossover_interaction":"Взаємодія мутації зі схрещуванням"}
    for item in report["primary_statistics"]["intervals"]:
        interval=(f"[{number(item['lower']*100)}; {number(item['upper']*100)}]"
                  if item["lower"] is not None else f"не визначено: {item['reason']}")
        status=("Додатний ефект підтверджено" if item["positive_effect_supported"] else
                "Від'ємний ефект підтверджено" if item["negative_effect_supported"] else
                "Лише описово" if item["status"] == "DESCRIPTIVE_ONLY" else "Напрям ефекту не підтверджено")
        lines.append(f"| {labels[item['contrast_id']]} | {number(item['estimate']*100)} | {interval} | {status} |")
    lines.extend(["", "*BCa для десяти обраних сімейств є наближенням. Вироджений інтервал "
                  "не замінено іншим методом. Відсутність підтвердженого ефекту не доводить рівності.*", "",
                  "## 5. Описові результати конфігурацій", "",
                  "| Початок | Мутація | Схрещування | Популяція | Частота виходу, % | Середній розрив, % |",
                  "|---|---:|---:|---:|---:|---:|"])
    for item in report["configuration_summaries"]:
        escape=number(item["escape_rate_equal_family"]*100) if item["start_profile"] == "local" else "не застосовується"
        label="локальний" if item["start_profile"] == "local" else "випадковий"
        star=" (опорна)" if item["baseline"] else ""
        lines.append(f"| {label}{star} | {number(item['mutation_numerator'])}/n | "
                     f"{number(item['crossover_probability'])} | {item['population_size']} | {escape} | "
                     f"{number(item['mean_final_relative_gap_equal_family']*100)} |")
    lines.extend(["", "*Кінцевий розрив і порівняння з опорною конфігурацією є описовими. "
                  "Додаткових перевірок переваги окремих конфігурацій не виконано. "
                  "Вища частота виходу не означає кращої кінцевої якості або швидшого точного розв'язання.*", "",
                  "## 6. Реєстр підготовки", "",
                  "| Задача | Місткість | Жадібна цінність | Центр | Оптимум | Статус |",
                  "|---|---:|---:|---:|---:|---|"])
    for item in report["preparation_cases"]:
        lines.append(f"| {item['instance_id']} | {item['capacity']} | {item['greedy_profit']} | "
                     f"{item['center_profit']} | {item['optimum_profit']} | {item['status']} |")
    lines.extend(["", "## 7. Рисунки та наперед визначений приклад", "",
                  "Приклад UC-s000, seed 51001 показує три значення мутації за схрещування "
                  "0,9 і популяції 30. Рекорд, середню цінність допустимих особин і частку "
                  "унікальних масок наведено окремо, у шкалі фактичних логічних оцінювань.", ""])
    for name in report.get("example_figures",[]):
        lines.append(f"![{name['caption']}]({name['path']})")
        lines.append("")
    lines.extend(["*Рекорд є монотонним за означенням; середня якість популяції може знижуватися. "
                  "Неповне покоління змінює рекорд, але не оновлює популяцію. Штучного продовження "
                  "популяційних траєкторій до ліміту не додано.*", "",
                  "## 8. Походження й межі висновків", "",
                  "Усі журнали пройшли незалежний перерахунок оцінок і відтворення операторів. "
                  "Маніфест джерел фіксує run/artifact IDs, SHA реалізації, контрольні суми ZIP "
                  "та внутрішніх файлів. Політика прийняття не використовує 'останній' або 'найкращий' запуск.", "",
                  f"SHA реалізації: `{report['implementation_commit_sha']}`. "
                  f"Коміт реєстрації: `{REGISTRATION_SHA}`. Реєстр джерел: `sources.json`.", "",
                  "Висновки обмежені 100-бітними задачами KPLIB, визначеною сіткою сталих параметрів "
                  "і лімітом 5000 оцінювань. Адаптацію λ не досліджено; нового алгоритму, світового "
                  "пріоритету та універсально найкращих параметрів не встановлено.", "",
                  "## Джерела", "",
                  "Повні бібліографічні записи: `../SOURCES.json`; ключі @whitley1994, @deb2000, "
                  "@kplib, @kellerer2004, @anagun_sarac2006, @efron1987."])
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")


def aggregate(root: Path, source_path: Path, expected_sha: str, output: Path, *, pilot=False) -> dict:
    instances, cases, _, identity=load_context(expected_sha)
    descriptor=read_json(MODULE_ROOT/"frozen_banks.json")
    identity["banks_manifest_sha256"]=descriptor["banks_manifest_sha256"]
    phase="pilot" if pilot else "main"
    sources=read_json(source_path)
    rows,resources=collect_verified_batches(Path(root),sources,cases,
                                           {instance.instance_id:instance for instance in instances},identity,phase=phase)
    output=output_directory(output)
    write_json(output/"sources.json",sources)
    if pilot:
        feasible=all(row["resource_feasible"] for row in resources)
        result={"schema_version":"ga-knapsack-pilot-gate-v1","protocol_id":PROTOCOL_ID,
                "implementation_commit_sha":expected_sha,"phase":"pilot","run_count":len(rows),
                "logical_requests":sum(row["logical_requests"] for row in rows),"resources":resources,
                "all_evidence_verified":True,"resource_feasible":feasible,
                "projected_job_seconds":max(row["projected_ten_seed_seconds"] for row in resources),
                "projected_job_bytes":max(row["projected_ten_seed_bytes"] for row in resources),
                "implementation_fingerprint":identity["implementation_fingerprint"],
                "runtime_lock_sha256":identity["runtime_lock_sha256"],
                "banks_manifest_sha256":identity["banks_manifest_sha256"],
                "provenance":sources,
                "technical_status":"PASS_TECHNICAL" if feasible else "BLOCK_MAIN_RESOURCE_LIMIT",
                "status":"PASS_TECHNICAL" if feasible else "BLOCK_MAIN_RESOURCE_LIMIT",
                "scientific_statistics_computed":False}
        write_json(output/"technical_result.json",result)
        write_file_manifest(output)
        return result
    memberships,statistics=primary_statistics(rows,cases)
    result={"schema_version":SUMMARY_SCHEMA,"protocol_id":PROTOCOL_ID,
            "protocol_sha256":PROTOCOL_SHA,"registration_commit_sha":REGISTRATION_SHA,
            "implementation_commit_sha":expected_sha,"data_manifest_sha256":DATA_SHA,
            "registry_sha256":REGISTRY_SHA,"runtime_lock_sha256":identity["runtime_lock_sha256"],
            "banks_manifest_sha256":identity["banks_manifest_sha256"],"status":"COMPLETE_VERIFIED_MAIN",
            "runs":len(rows),"random_runs":sum(row["start_profile"]=="random" for row in rows),
            "local_runs":sum(row["start_profile"]=="local" for row in rows),
            "logical_requests":EXPECTED_LOGICAL_REQUESTS,"source_job_count":len(sources["sources"]),
            "preparation_cases":preparation_rows(cases),"configuration_summaries":configuration_summaries(rows,cases),
            "family_memberships":memberships,"primary_statistics":statistics,
            "baseline":{"mutation_numerator":1.,"crossover_probability":.9,"population_size":30,
                        "role":"prespecified descriptive control, already in 27 configurations"},
            "example_trajectories":example_trajectories(rows),"resources":resources,"provenance":sources}
    from .plots import create_plots
    result["example_figures"]=create_plots(result,output/"figures")
    write_json(output/"report-data.json",result)
    write_report_markdown(output/"RESULTS_UK.md",result)
    # Compact scalar evidence is retained without duplicating RNG journals.
    compact_fields=("instance_id","start_profile","repeat_seed","configuration_id","mutation_numerator",
                    "crossover_probability","population_size","best_mask","best_profit","best_weight","best_request",
                    "escape_event","first_escape_request","censored","logical_requests","physical_evaluations",
                    "invalid_request_count","duplicate_count","complete_generations","terminal_partial")
    compact=[{field:row[field] for field in compact_fields} for row in rows]
    with (output/"run-summaries.jsonl.gz").open("wb") as target:
        with gzip.GzipFile(fileobj=target,mode="wb",mtime=0,filename="") as stream:
            for row in compact:
                stream.write(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()+b"\n")
    with (output/"preparation-cases.csv").open("w",encoding="utf-8",newline="") as target:
        fields=[key for key in result["preparation_cases"][0] if key != "center_mask"]
        writer=csv.DictWriter(target,fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["preparation_cases"])
    write_file_manifest(output)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--sources",type=Path,required=True)
    parser.add_argument("--expected-sha",required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--pilot",action="store_true")
    args=parser.parse_args(argv)
    result=aggregate(args.root,args.sources,args.expected_sha,args.output,pilot=args.pilot)
    print(result["status"])


if __name__ == "__main__":
    main()

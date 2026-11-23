"""CI entry points for paired comparisons of selection rules."""
import argparse
from copy import deepcopy
import gc
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
from time import monotonic

from ..calibrated_selection_scaling import preparation as inputs
from ..calibrated_selection_scaling.common import read_json, require, write_json
from ..calibrated_selection_scaling.program.ga_core import create_random_generators
from .engine import run_search
from .verification import verify_log

TOTAL = 100_000
ROLES = ("donor", "k2", "k3", "adaptive", "replay")
TASKS = tuple(f"n00100-{kind}-s{family:03}" for family in range(70, 80) for kind in ("UC", "WC", "SC"))
STAGE = Path("stage")


def check_ci():
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
            os.environ.get("GITHUB_REF") == "refs/heads/research/selection-two-bases", "Unexpected execution context")


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def prepare():
    check_ci()
    corpus = inputs.audit_corpus("main", (STAGE / "audit").resolve(), source_root=Path("kplib"))
    cases = {r["task_id"]: r for r in corpus["cases"] if r["n"] == 100}
    require(set(cases) == set(TASKS), "Incomplete 100-item cohort")
    for index, task in enumerate(TASKS, 63):
        row = cases[task]
        problem = row["problem"]
        certificate = inputs._certificate(problem, deadline=monotonic()+60, memory_limit_bytes=1024**3)
        bank = inputs.make_bank(problem, 192000, index, 192001)
        write_json(STAGE/"inputs"/f"{task}.json", {"problem":problem, "bank":bank, "certificate":certificate,
                   "source_sha256":row["source_sha256"], "source_path":row["source_path"], "index":index})
    write_json(STAGE/"inputs"/"origin.json", {"source_commit":corpus["source_commit"],
               "license":corpus["license"], "attribution":corpus["attribution_url"],
               "duplicates":corpus["duplicates"], "input_checksums":{t:inputs.identity(STAGE/"inputs"/f"{t}.json")["sha256"] for t in TASKS}})


def run_ga(problem, bank, role, pc, schedule=None, total=TOTAL):
    require(set(problem) == {"n","weights","profits","capacity"} and problem["n"] == 100, "Invalid search inputs")
    require(pc in (90, 100) and role in ROLES and ((role == "replay") == (schedule is not None)), "Unknown profile")
    mu = 15
    seed = 193001 if role == "donor" else 192001
    generators = create_random_generators(seed, bank["task_index"], 0)
    if role != "donor":
        require({k: r.bit_generator.state for k,r in generators.items()} == bank["rng_states"], "Recipient streams differ")
    parameters = {"p_m":0.01, "p_c":pc/100, "target_mu":mu, "elite_count":1,
                  "tournament_size":3 if role == "k3" else 2}
    return run_search(problem, bank["masks"][:mu], bank["scores"][:mu], "adaptive" if role == "donor" else role,
                      generators, total-mu, tournament_schedule=schedule, initial_parameters=parameters,
                      configuration_contract="paired-selection-v1")


def endpoints(log, optimum):
    mu = log["initial_population_size"]
    hits = {}
    for target in (93,95,99):
        first = next((i for i,s in enumerate(log["initial_scores"], 1)
                      if s["feasible"] and 100*s["profit"] >= target*optimum), None)
        if first is None:
            first = next((mu+c["call"] for c in log["candidates"] if 100*c["record_profit"] >= target*optimum), None)
        hits[str(target)] = first
    return hits


def execute(index, pc):
    check_ci()
    require(0 <= index < len(TASKS) and pc in (90,100), "Unexpected shard")
    task = TASKS[index]
    source = STAGE/"inputs"/f"{task}.json"
    require(inputs.identity(source)["sha256"] == read_json(STAGE/"inputs"/"origin.json")["input_checksums"][task],
            "Prepared input checksum differs")
    item = read_json(source)
    problem, bank = item["problem"], item["bank"]
    require(item["index"] == bank["task_index"] == index+63, "Task identity differs")
    optimum = item["certificate"]["optimum"]
    root = STAGE/"evidence"/f"{index:02d}-{pc}"
    root.mkdir(parents=True, exist_ok=False)
    schedule = None
    for role in ROLES:
        log = run_ga(problem, bank, role, pc, schedule if role == "replay" else None)
        verified = verify_log(log)
        require(verified["verification_status"] == "VERIFIED" and verified["new_calls"] == TOTAL-15 and
                log["initial_masks"] == bank["masks"][:15], "Replay or start differs")
        sizes = [g["parameters_before"]["tournament_size"] for g in log["generations"]]
        if role == "donor":
            schedule = sizes
            write_json(root/"donor-schedule.json", schedule)
        if role == "replay":
            require(sizes == schedule and log["schedule"] == schedule, "Receiver diverged from donor")
        best = verified["record_profit"]
        require(0 <= best <= optimum, "Best value exceeds exact optimum")
        raw_path = root/f"{role}.json.gz"
        raw = gzip.compress(json.dumps(log,separators=(",",":"), allow_nan=False).encode(), compresslevel=3, mtime=0)
        require(len(raw) <= 20*1024**2, "Single log exceeds the study storage allowance")
        raw_path.write_bytes(raw)
        del raw
        row = {"task":task, "pc":pc, "role":role, "optimum":optimum, "best":best, "hits":endpoints(log,optimum),
               "bank_sha256":digest(log["initial_masks"]), "rng_initial":digest(log["rng_initial"]),
               "search_seconds":log["timing_ns"]["total"]/1e9, "evaluations":TOTAL,
               "schedule_sha256":digest(sizes), "source_sha256":item["source_sha256"],
               "log_sha256":inputs.identity(raw_path)["sha256"], "log_bytes":raw_path.stat().st_size,
               "commit":os.environ["GITHUB_SHA"], "verified":True}
        write_json(root/f"{role}.receipt.json", row)
        print(task, pc, role, "verified", flush=True)
        del log, verified
        gc.collect()


def test():
    check_ci()
    p = {"n":100,"weights":[1]*100,"profits":list(range(1,101)), "capacity":49}
    b = inputs.make_bank(p,192000,63,192001)
    for pc in (90,100):
        schedule = [2,5,3]
        log = run_ga(p,b,"replay",pc,schedule, total=44)
        require(verify_log(log)["new_calls"] == 29, "Last partial evaluation missing")
        require([g["parameters_before"]["tournament_size"] for g in log["generations"]] == schedule,
                "Schedule indexed at the wrong generation")
        require(log["generations"][-1]["complete"] is False, "Wrong final phase")
        broken = deepcopy(log)
        broken["schedule"][1] = 4
        try:
            verify_log(broken)
        except ValueError:
            pass
        else:
            raise AssertionError("Corrupted schedule accepted")
        for role in ("k2", "k3", "adaptive", "donor"):
            verify_log(run_ga(p,b,role,pc,total=44))


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("mode", choices=("prepare","run","test"))
    cli.add_argument("--index",type=int)
    cli.add_argument("--pc",type=int)
    args = cli.parse_args()
    if args.mode == "run":
        execute(args.index, args.pc)
    elif args.mode == "prepare":
        prepare()
    else:
        test()

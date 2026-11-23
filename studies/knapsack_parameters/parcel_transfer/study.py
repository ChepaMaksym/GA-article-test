import argparse
import gc
import gzip
import json
import os
from pathlib import Path
from time import monotonic

import numpy as np
from ..selection_two_bases.study import (ROLES, TOTAL, digest, endpoints, inputs, read_json,
                                        require, run_ga, verify_log, write_json)

ROOT = Path("stage")
BASE_SCORES = {"стандартний": 10, "пріоритетний": 25, "терміновий": 50}


def guard():
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
            os.environ.get("GITHUB_REF") == "refs/heads/research/parcel-transfer", "Unexpected CI context")


def manifest(trip):
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([20261123, trip])))
    parcels = []
    for number in range(1, 101):
        mass = int(rng.integers(1, 201))
        draw = int(rng.integers(100))
        service = "стандартний" if draw < 60 else "пріоритетний" if draw < 90 else "терміновий"
        days = int(rng.integers(7))
        parcels.append({"id": f"R{trip:02}-P{number:03}", "mass_100g": mass, "service": service,
                        "waiting_days": days, "points": BASE_SCORES[service]+2*days})
    return parcels


def prepare():
    seen = set()
    for trip in range(1,7):
        parcels = manifest(trip)
        require(len({p["id"] for p in parcels}) == len(parcels) == 100 and all(
            1 <= p["mass_100g"] <= 200 and 0 <= p["waiting_days"] <= 6 and
            p["points"] == BASE_SCORES[p["service"]]+2*p["waiting_days"] for p in parcels
        ), "Invalid parcel manifest")
        problem = {"n":100,"capacity":5000,"weights":[p["mass_100g"] for p in parcels],
                   "profits":[p["points"] for p in parcels]}
        key = digest(sorted(zip(problem["weights"],problem["profits"])))
        require(key not in seen and sum(problem["weights"]) > problem["capacity"], "Duplicate or unconstrained trip")
        seen.add(key)
        certificate = inputs._certificate(problem, deadline=monotonic()+60, memory_limit_bytes=1024**3)
        bank = inputs.make_bank(problem,20261123,300+trip,192001)
        write_json(ROOT/"inputs"/f"trip-{trip}.json", {"parcels":parcels,"problem":problem,"bank":bank,
                   "certificate":certificate,"manifest_sha":digest(parcels)})
    write_json(ROOT/"inputs"/"hashes.json",{str(i):inputs.identity(ROOT/"inputs"/f"trip-{i}.json")["sha256"]
                                           for i in range(1,7)})


def execute(trip, pc):
    source = ROOT/"inputs"/f"trip-{trip}.json"
    require(inputs.identity(source)["sha256"] == read_json(source.parent/"hashes.json")[str(trip)], "Changed input")
    item = read_json(source)
    parcels, problem, bank = item["parcels"], item["problem"], item["bank"]
    require(digest(parcels) == digest(manifest(trip)) == item["manifest_sha"], "Unexpected manifest")
    optimum = item["certificate"]["optimum"]
    out = ROOT/"evidence"/f"{trip}-{pc}"
    out.mkdir(parents=True, exist_ok=False)
    schedule = None
    for role in ROLES:
        log = run_ga(problem,bank,role,pc,schedule if role=="replay" else None)
        check = verify_log(log)
        require(check["verification_status"]=="VERIFIED" and check["new_calls"]+15 == TOTAL, "Replay incomplete")
        applied = [g["parameters_before"]["tournament_size"] for g in log["generations"]]
        if role=="donor":
            schedule = applied
            write_json(out/"donor-schedule.json",schedule)
        if role=="replay":
            require(applied == schedule, "Receiver diverged from donor")
        chosen = [p for p,b in zip(parcels,log["summary"]["best_mask"],strict=True) if b=="1"]
        score = sum(p["points"] for p in chosen)
        mass = sum(p["mass_100g"] for p in chosen)
        require(mass <= problem["capacity"] and score == check["record_profit"] <= optimum,"Invalid loaded cargo")
        data = gzip.compress(json.dumps(log,separators=(",",":"),allow_nan=False).encode(),compresslevel=3,mtime=0)
        require(len(data)<=20*1024**2,"Unexpected log size")
        path = out/f"{role}.json.gz"
        path.write_bytes(data)
        write_json(out/f"{role}.receipt.json", {"trip":trip,"pc":pc,"role":role,"manifest_sha":item["manifest_sha"],
                   "ids":[p["id"] for p in chosen],"mass_100g":mass,"points":score,"optimum":optimum,
                   "hits":endpoints(log,optimum),"bank_sha":digest(log["initial_masks"]),
                   "rng_sha":digest(log["rng_initial"]),"schedule_sha":digest(applied),
                   "log_sha":inputs.identity(path)["sha256"],"commit":os.environ["GITHUB_SHA"],"verified":True})
        del data, log, check
        gc.collect()


if __name__=="__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("operation",choices=("prepare","run"))
    cli.add_argument("--trip",type=int,choices=range(1,7))
    cli.add_argument("--pc",type=int,choices=(90,100))
    args = cli.parse_args()
    guard()
    if args.operation=="prepare":
        prepare()
    else:
        execute(args.trip,args.pc)

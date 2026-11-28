"""Transfer of frozen finalist policies to 30 synthetic single-trip manifests."""
import argparse
import csv
import json
import os
from pathlib import Path
from statistics import mean
from time import perf_counter_ns

from ..parcel_transfer.study import manifest
from ..population_size_study.exact import certify_problem, solve_capacity
from ..population_validation_100.preparation import make_bank
from .analysis import endpoint
from .confirmatory import compare
from .holdout import inventory, key, run_case
from .study import require

TRIPS=tuple(range(7,37))
SEEDS=tuple(range(197001,197011))
HISTORICAL=key([90,"fixed",30,2,1,145,None])

def load_cargo(parcels,mask):
    require(len(mask)==100 and set(mask)<={"0","1"},"Invalid cargo mask")
    chosen=[p for p,b in zip(parcels,mask,strict=True) if b=="1"]
    mass=sum(p["mass_100g"] for p in chosen)
    require(mass<=5000,"Overloaded vehicle")
    return dict(ids=[p["id"] for p in chosen],mass_100g=mass,points=sum(p["points"] for p in chosen))

def problem_of(parcels):
    return dict(n=100,capacity=5000,weights=[p["mass_100g"] for p in parcels],profits=[p["points"] for p in parcels])

def prepare():
    root=Path("manifests")
    root.mkdir()
    seen=set()
    for trip in range(1,37):
        parcels=manifest(trip)
        p=problem_of(parcels)
        fingerprint=tuple(sorted(zip(p["weights"],p["profits"])))
        require(fingerprint not in seen and sum(p["weights"])>5000,"Duplicate or trivial manifest")
        seen.add(fingerprint)
        if trip in TRIPS:
            cert=certify_problem(p)
            (root/f"{trip}.json").write_text(json.dumps(dict(parcels=parcels,certificate=cert)),encoding="utf8")

def shard(block):
    _,policies=inventory()
    physical=sorted([*policies,HISTORICAL])
    trip=TRIPS[block//5]
    task=f"trip-{trip:02}"
    item=json.loads((Path("manifests")/f"{trip}.json").read_bytes())
    parcels,cert=item["parcels"],item["certificate"]
    require(parcels==manifest(trip),"Manifest differs")
    p=problem_of(parcels)
    for seed in SEEDS[2*(block%5):2*(block%5)+2]:
        bank=make_bank(p,300+trip,seed,197000)
        start=perf_counter_ns()
        exact=solve_capacity(p)
        answer=load_cargo(parcels,exact["witness_mask"])
        elapsed=perf_counter_ns()-start
        require(answer["points"]==cert["optimum"]==exact["optimum_profit"],"Exact cargo mismatch")
        compact=Path("compact")
        compact.mkdir(exist_ok=True)
        (compact/f"{task}-{seed}-exact.json").write_text(json.dumps(dict(task=task,seed=seed,exact=True,
            solution_ns=elapsed,**answer)),encoding="utf8")
        for cfg in physical:
            args=(task,seed,cfg,bank,p,cert["optimum"],physical)
            schedule=None
            if json.loads(cfg)[0]=="donor":
                schedule=run_case(*args,donor=True,parcels=parcels)
            run_case(*args,schedule=schedule,parcels=parcels)

def summarize():
    roles,_=inventory()
    rows=[json.loads(p.read_bytes()) for p in Path("collected").rglob("*.json")]
    exact={(r["task"],r["seed"]):r for r in rows if r.get("exact")}
    ga=[r for r in rows if not r.get("exact")]
    donors={(r["task"],r["seed"],r["configuration"]):r for r in ga if r["donor_source"]}
    rec=[r for r in ga if not r["donor_source"]]
    starts={(f"trip-{t:02}",s) for t in TRIPS for s in SEEDS}
    require(set(exact)==starts and len(rows)==6000 and len(donors)==1200 and len(rec)==4500,"Incomplete series")
    require(all(r["commit"]==os.environ["GITHUB_SHA"] and r["points"]==r["best"]<=r["optimum"] and
                exact[r["task"],r["seed"]]["points"]==r["optimum"] and r["mass_100g"]<=5000 and r["solution_ns"]>0
                for r in ga),"Unverified cargo or runtime")
    for r in rec:
        if json.loads(r["configuration"])[0]=="donor":
            require(r["schedule_sha256"]==donors[r["task"],r["seed"],r["configuration"]]["schedule_sha256"],"Donor mismatch")
    require({(r["task"],r["seed"]) for r in rec if r["configuration"]==HISTORICAL}==starts,"Historical control missing")
    clusters={task:[task] for task,_ in starts}
    results=compare([r for r in rec if r["configuration"]!=HISTORICAL],roles,clusters,SEEDS,parcels=True)
    Path("parcel-comparisons.json").write_text(json.dumps(results,indent=2),encoding="utf8")
    with Path("cargo-summary.csv").open("w",newline="",encoding="utf-8-sig") as stream:
        w=csv.writer(stream,delimiter=";")
        w.writerow(("configuration","runs","mean_gap_pct","mean_T93","misses93","mean_seconds_to_load","mean_donor_seconds_extra"))
        for cfg in sorted({r["configuration"] for r in rec}):
            group=[r for r in rec if r["configuration"]==cfg]
            extra=[r["solution_ns"]/1e9 for k,r in donors.items() if k[2]==cfg]
            w.writerow((cfg,len(group),*(float(mean(endpoint(r,m) for r in group)) for m in ("gap","t93")),
                        sum(r["hits"]["93"] is None for r in group),mean(r["solution_ns"]/1e9 for r in group),mean(extra) if extra else 0))
        w.writerow(("exact_capacity_dp",300,0,"","",mean(r["solution_ns"]/1e9 for r in exact.values()),0))

if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("mode",choices=("prepare","run","summarize"))
    cli.add_argument("--shard",type=int,choices=range(150))
    args=cli.parse_args()
    if args.mode=="prepare":prepare()
    elif args.mode=="run":shard(args.shard)
    else:summarize()

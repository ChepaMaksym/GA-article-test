"""Follow-up comparisons on the original paired tuning starts, conditional on Stage A."""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
from statistics import mean
from time import perf_counter

from . import design, engine, verification
from .analysis import endpoint, select_screen
from .study import input_case, require, thresholds

DIGEST = "6caf185ec8884137ae459717bd3fc05bd7ccffa1b679ee4bb0a0022002a5f377"
SEEDS = range(150001, 150004)


def configurations():
    # Existing absolute thresholds 70, 145, 280, k2 and k3 come from Stage A.
    for pc, role in [(90, "A4"), (100, "A5")]:
        for threshold in (28, 140, 700):
            yield (pc, role, 15, 2, 1, threshold, None)
    for k in (4, 5):
        yield (90, "fixed", 15, k, 1, 145, None)
    for elites in range(2, 6):
        yield (100, "fixed", 15, 2, elites, 145, None)
    for h in (2, 5, 10, 20, 50):
        yield (100, "A5", 15, 2, 1, 14*h, h)
    for threshold in (70, 145):
        yield (90, "A4", 30, 2, 1, threshold, None)


def gate():
    src = Path("prior/verified.jsonl").read_bytes()
    require(hashlib.sha256(src).hexdigest() == DIGEST, "Screen digest differs")
    rows = [json.loads(line) for line in src.splitlines()]
    winners = select_screen(rows)
    require([(w["pc"], w["metric"], w["role"], w["threshold"]) for w in winners] ==
            [(90,"gap","A4",145),(90,"t93","A4",70),(100,"gap","A5",70),(100,"t93","A5",70)],
            "Previously registered finalist selection differs")
    require(any(r["pc"] == 100 and r["role"] == "A5" and r["changes"].get("elite_count",0)
                for r in rows), "Dynamic quota was never observed")


def run(shard):
    task = design.tasks()[shard // 3]
    seed = SEEDS[shard % 3]
    problem, bank, optimum = input_case(task, seed)
    for i, cfg in enumerate(configurations()):
        pc, role, mu, k, elites, threshold, dynamic = cfg
        identity = f"{task}-{seed}-{i:02d}"
        receipt_path = Path("compact",identity+".json")
        raw_path = Path("raw",identity+".json.gz")
        previous = list(Path("restored").rglob(identity+".json"))
        if previous:
            receipt = json.loads(previous[0].read_bytes())
            archive = previous[0].with_suffix(".json.gz")
            require(receipt["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
                    and receipt["config"] == list(cfg) and receipt["commit"] == os.environ["GITHUB_SHA"]
                    and receipt["task"] == task and receipt["seed"] == seed, "Invalid restored case")
        else:
            initial = dict(target_mu=mu,p_c=pc/100,p_m=.01,tournament_size=k,elite_count=elites)
            rng = engine.make_rngs(seed,bank["task_index"],0)
            require({k:r.bit_generator.state for k,r in rng.items()} == bank["rng_states"],"RNG bank mismatch")
            args = dict(initial=initial,threshold=threshold,dynamic_h=dynamic)
            start = perf_counter()
            log = engine.run_search(problem,bank["masks"][:mu],bank["scores"][:mu],
                                    design.BITS.get(role,0),rng,design.TOTAL-mu,**args)
            elapsed = perf_counter()-start
            check = verification.verify_log(log,**args)
            require(check["new_calls"]+mu == design.TOTAL and check["verification_status"]=="VERIFIED"
                    and 0 <= check["record_profit"] <= optimum,"Replay mismatch")
            raw_path.parent.mkdir(exist_ok=True)
            with gzip.open(raw_path,"wt",encoding="utf8",compresslevel=1) as f:
                json.dump(log,f,separators=(",",":"),allow_nan=False)
            receipt = dict(task=task,seed=seed,config=cfg,best=check["record_profit"],optimum=optimum,
                           hits=thresholds(log,optimum),search_seconds=elapsed,total=design.TOTAL,
                           sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),commit=os.environ["GITHUB_SHA"])
            raw_path.with_suffix("").write_text(json.dumps(receipt),encoding="utf8")
            del log
        receipt_path.parent.mkdir(exist_ok=True)
        receipt_path.write_text(json.dumps(receipt),encoding="utf8")


def summarize():
    configs = list(configurations())
    expected = {(t,s,c) for t in design.tasks() for s in SEEDS for c in configs}
    groups = {cfg:[] for cfg in configs}
    for f in Path("collected").rglob("*.json"):
        row = json.loads(f.read_bytes())
        cfg = tuple(row["config"])
        expected.remove((row["task"],row["seed"],cfg))
        require(row["commit"]==os.environ["GITHUB_SHA"] and row["total"]==design.TOTAL,"Unexpected provenance")
        groups[cfg].append(row)
    require(not expected,"Incomplete collection")
    with Path("followup.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        out = csv.writer(stream)
        out.writerow(("pc","role","population","tournament","elite","threshold","dynamic_h","runs","mean_gap_pct","mean_T93"))
        for cfg,rows in groups.items():
            out.writerow((*cfg,len(rows),*(float(mean(endpoint(r,m) for r in rows)) for m in design.METRICS)))


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("mode",choices=("gate","run","summarize"))
    cli.add_argument("--shard",type=int,choices=range(90))
    args=cli.parse_args()
    if args.mode=="gate":
        gate()
    elif args.mode=="run":
        run(args.shard)
    else:
        summarize()

"""Execute and independently replay one registered case before publishing its measurements."""
import argparse
from collections import Counter
from hashlib import sha256
import gzip
import json
import os
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

from ..population_validation_100.preparation import make_bank
from . import design, engine, verification

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parent / "initial_grid_100/data/retained_inputs.zip"
ARCHIVE_SHA = "1feb6f74fd0929f4e690a6a352f0c76e8ed41022c81df1109feab8f340a06ee5"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def input_case(task, seed):
    require(sha256(ARCHIVE.read_bytes()).hexdigest()==ARCHIVE_SHA,"Changed certified inputs")
    with ZipFile(ARCHIVE) as z:
        manifest=json.loads(z.read("manifest.json"))
        entry=next(t for t in manifest["tasks"] if t["task"]==task)
        problem=json.loads(z.read(task+"/problem.json"))
        certificate=json.loads(z.read(task+"/certificate.json"))
    bank=make_bank(problem,entry["task_index"],seed,150000)
    return problem,bank,certificate["optimum"]


def thresholds(log, optimum):
    hits=dict.fromkeys((93,95,99))
    size=len(log["initial_scores"])
    for i,s in enumerate(log["initial_scores"],1):
        for q in hits:
            if hits[q] is None and s["feasible"] and 100*s["profit"]>=q*optimum:
                hits[q]=i
    for c in log["candidates"]:
        if all(x is not None for x in hits.values()):
            break
        for q in hits:
            if hits[q] is None and 100*c["record_profit"]>=q*optimum:
                hits[q]=size+c["call"]
    return hits


def execute(task, seed, configuration, output, *, total=design.TOTAL):
    pc,role,h=configuration
    require(configuration in set(design.screening()),"Unregistered screening configuration")
    problem,bank,optimum=input_case(task,seed)
    initial=dict(p_m=.01,p_c=pc/100,target_mu=15,tournament_size=3 if role=="k3" else 2,elite_count=1)
    streams=engine.make_rngs(seed,bank["task_index"],0)
    require({k:r.bit_generator.state for k,r in streams.items()}==bank["rng_states"],"Unpaired RNG start")
    since=perf_counter()
    log=engine.run_search(problem,bank["masks"][:15],bank["scores"][:15],design.BITS[role],streams,
                          total-15,initial=initial,threshold=h or 145)
    verified=verification.verify_log(log,initial=initial,threshold=h or 145)
    require(verified["new_calls"]+15==total and verified["verification_status"]=="VERIFIED","Incomplete replay")
    best=verified["record_profit"]
    require(0<=best<=optimum,"Invalid record")
    hits=thresholds(log,optimum)
    name=f"{task}-{seed}-pc{pc}-{role}-H{h or 'na'}"
    output.mkdir(parents=True,exist_ok=True)
    dest=output/(name+".json.gz")
    # Stream the representation; the raw record may be several hundred MB.
    with dest.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=1,mtime=0) as stream:
        import io
        with io.TextIOWrapper(stream,encoding="utf8") as text:
            json.dump(log,text,separators=(",",":"),allow_nan=False)
    changed=Counter(e["field"] for g in log["generations"] for e in g["parameter_events"]
                    if e["before"]!=e["after"])
    receipt=dict(case_id=name,task=task,seed=seed,pc=pc,role=role,threshold=h,total=total,
                 optimum=optimum,best=best,hits=hits,commit=os.environ["GITHUB_SHA"],verified=True,
                 generations=verified["completed_generations"],changes=dict(changed),
                 stagnations=sum(g["controller_event"]=="STAGNATION" for g in log["generations"]),
                 seconds=perf_counter()-since,bytes=dest.stat().st_size,sha256=sha256(dest.read_bytes()).hexdigest())
    with (output/(name+".receipt.json")).open("x",encoding="utf8") as f:
        json.dump(receipt,f,sort_keys=True)
    print(name,best,hits,round(receipt["seconds"],2),flush=True)
    return receipt


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("operation",choices=("pilot","screen","freeze"))
    parser.add_argument("--pc",type=int,choices=design.BASES)
    parser.add_argument("--shard",type=int)
    args=parser.parse_args()
    if args.operation=="freeze":
        manifest=dict(stage_a=list(design.screening()),count=sum(1 for _ in design.cases()),
                      a7={p:design.static_grid(p,"A7") for p in design.BASES},
                      comparisons=design.contrasts(),confidence=.9975,bca_resamples=50000)
        print(json.dumps(manifest,indent=2))
        return
    require(os.environ.get("GITHUB_ACTIONS")=="true","GitHub Actions required")
    output=Path("evidence")
    if args.operation=="pilot":
        require(args.pc in design.BASES,"Missing pilot base")
        # Exercise all rules on both bases; time full-size fixed and combined cases.
        for i,role in enumerate(design.BITS):
            task=("n00100-UC-s000","n00100-WC-s001","n00100-SC-s005")[i%3]
            h=None if role in ("k2","k3","A2") else (70,145,280)[i%3]
            execute(task,196999,(args.pc,role,h),output,total=design.TOTAL if role in ("k2","A7") else 2500)
    else:
        require(args.shard is not None and 0<=args.shard<180,"Invalid shard")
        # One common task, seed and base per shard.
        task,seed,pc=list(__import__("itertools").product(design.tasks(),range(150001,150004),design.BASES))[args.shard]
        for config in design.screening():
            if config[0]==pc:
                execute(task,seed,config,output)


if __name__=="__main__":
    main()

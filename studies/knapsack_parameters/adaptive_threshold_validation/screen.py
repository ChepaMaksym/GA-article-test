"""Run paired screening blocks and reconcile their compact verified receipts."""
import argparse
import csv
from collections import defaultdict
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
from statistics import mean

from . import design
from .analysis import endpoint, select_screen
from .study import execute, require


def case_name(task, seed, pc, role, h):
    return f"{task}-{seed}-pc{pc}-{role}-H{h or 'na'}"


def validate(row, expected_commit):
    require(row["commit"] in (expected_commit, "d3e5ce0dcff688974317779ff20de362d6430b43") and row["verified"] is True, "Foreign/unverified receipt")
    require(row["total"] == design.TOTAL and 0 <= row["best"] <= row["optimum"] and row["optimum"] > 0,
            "Invalid case accounting")
    require(row["case_id"] == case_name(row["task"],row["seed"],row["pc"],row["role"],row["threshold"]),
            "Case identity differs")
    require(set(row["hits"]) == {"93","95","99"}, "Threshold inventory")
    previous = 0
    for target in (93,95,99):
        hit = row["hits"][str(target)]
        require((hit is not None) == (100*row["best"] >= target*row["optimum"]), "Hit contradicts final score")
        q = design.TOTAL+1 if hit is None else hit
        require(type(q) is int and previous <= q and 1 <= q <= design.TOTAL+(hit is None), "Invalid first hit")
        previous = q


def run_block(shard, output, restored):
    rows = list(product(design.tasks(),range(150001,150004),design.BASES))
    require(0 <= shard < len(rows),"Unregistered block")
    task,seed,pc = rows[shard]
    output.mkdir(parents=True,exist_ok=True)
    for cfg in design.screening():
        if cfg[0]!=pc:
            continue
        identity = case_name(task,seed,*cfg)
        saved = list(restored.rglob(identity+".receipt.json")) if restored.exists() else []
        if saved:
            receipt = json.loads(saved[0].read_bytes())
            validate(receipt,os.environ["GITHUB_SHA"])
            raw = saved[0].with_name(identity+".json.gz")
            require(raw.stat().st_size == receipt["bytes"] and sha256(raw.read_bytes()).hexdigest()==receipt["sha256"],
                    "Restored evidence differs")
            require(all(p.read_bytes()==saved[0].read_bytes() for p in saved), "Previous attempts disagree")
            print("Restored",identity,flush=True)
        else:
            execute(task,seed,cfg,output)
            receipt = json.loads((output/(identity+".receipt.json")).read_bytes())
        validate(receipt,os.environ["GITHUB_SHA"])
        compact = Path("compact")
        compact.mkdir(exist_ok=True)
        (compact/(identity+".receipt.json")).write_text(json.dumps(receipt,sort_keys=True),encoding="utf8")


def summarize(root, out, commit):
    unique = {}
    for path in sorted(root.rglob("*.receipt.json")):
        r=json.loads(path.read_bytes())
        validate(r,commit)
        prior=unique.setdefault(r["case_id"],r)
        require(prior==r,"Conflicting duplicate across attempts")
    rows=list(unique.values())
    winners=select_screen(rows)
    out.mkdir(parents=True,exist_ok=True)
    groups=defaultdict(list)
    for r in rows:
        groups[r["pc"],r["role"],r["threshold"]].append(r)
    with (out/"screening.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.writer(stream,delimiter=";")
        writer.writerow(("pc","mechanism","threshold","runs","mean_gap_pct","restricted_mean_T93",
                         "missed_93","missed_95","missed_99"))
        for config in design.screening():
            group=groups[config]
            writer.writerow((*config,len(group),*(float(mean(endpoint(r,m) for r in group)) for m in design.METRICS),
                             *(sum(r["hits"][q] is None for r in group) for q in ("93","95","99"))))
    evidence=out/"verified.jsonl"
    with evidence.open("w",encoding="utf8",newline="\n") as f:
        for k in sorted(unique):
            f.write(json.dumps(unique[k],sort_keys=True)+"\n")
    frozen=dict(source_commit=commit,verified=len(rows),sha256=sha256(evidence.read_bytes()).hexdigest(),
                winners=winners)
    (out/"selection.json").write_text(json.dumps(frozen,indent=2)+"\n",encoding="utf8")
    print(json.dumps(frozen,indent=2))


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("mode",choices=("run","summarize"))
    cli.add_argument("--shard",type=int)
    args=cli.parse_args()
    if args.mode=="run":
        run_block(args.shard,Path("evidence"),Path("restored"))
    else:
        summarize(Path("collected"),Path("report"),os.environ["GITHUB_SHA"])

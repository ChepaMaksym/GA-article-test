"""Run the frozen 100-item holdout in paired blocks; the exact reference stays outside the GA."""
import argparse
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path

from ..population_size_study.inputs import problem_sha256
from ..population_validation_100.preparation import make_bank
from .confirmatory import compare
from .donor_replay import evaluate
from .study import require, thresholds

TOTAL = 100000
SEEDS = tuple(range(196001,196011))
TASKS = [f"n00100-{kind}-s{family:03}" for family in range(80,90) for kind in ("UC","WC","SC")]
def key(config):
    return json.dumps(config,separators=(",",":"))

def pinned(path,digest):
    raw=Path(path).read_bytes()
    require(sha256(raw).hexdigest()==digest,"Frozen artifact digest mismatch")
    return json.loads(raw)

def inventory():
    frozen=pinned("roles/frozen-roles.json","7321d3f29568967ffac1be9180d6a506a3de2b41bd48eb913cb6b91adae8b826")
    roles={}
    for item in frozen["roles"]:
        for role,cfg in dict(candidate=item["candidate"],**item["controls"]).items():
            roles[item["pc"],item["metric"],role]=key(cfg)
    physical=sorted(set(roles.values()))
    require(len(physical)==14,"Role inventory differs")
    return roles,physical

def run_case(task,seed,config_id,bank,problem,optimum,physical,*,donor=False,schedule=None):
    item=json.loads(config_id)
    cfg=item[1:] if item[0]=="donor" else item
    idx=physical.index(config_id)
    ident=f"{task}-{seed}-{idx:02d}"+("-source" if donor else "")
    dest=Path("raw")/ident
    dest.mkdir(parents=True,exist_ok=True)
    compact=Path("compact")
    compact.mkdir(exist_ok=True)
    restored=list(Path("restored").glob("**/"+ident+"/receipt.json"))
    if restored:
        row=json.loads(restored[0].read_bytes())
        require(row["commit"]==os.environ["GITHUB_SHA"] and row["configuration"]==config_id and
                row["task"]==task and row["seed"]==seed and row["total"]==TOTAL and row["verified"] and
                row["donor_source"]==donor,"Restored identity disagrees")
        require(sha256(restored[0].with_name("log.json.gz").read_bytes()).hexdigest()==row["sha256"],"Restored log changed")
        if donor:
            raw=restored[0].with_name("schedule.json").read_bytes()
            require(sha256(raw).hexdigest()==row["schedule_sha256"],"Restored donor changed")
            schedule=json.loads(raw)
    else:
        log,checked=evaluate(problem,bank,cfg,stream_group=int(donor),schedule=schedule)
        if donor:
            schedule=[g["parameters_before"] for g in log["generations"]]
        raw=key(schedule).encode()
        if donor:
            (dest/"schedule.json").write_bytes(raw)
        with gzip.open(dest/"log.json.gz","wt",encoding="utf8",compresslevel=1) as stream:
            json.dump(log,stream,separators=(",",":"),allow_nan=False)
        row=dict(task=task,seed=seed,configuration=config_id,verified=True,total=TOTAL,optimum=optimum,
                 best=checked["record_profit"],hits=thresholds(log,optimum),donor_source=donor,
                 schedule_sha256=sha256(raw).hexdigest() if schedule is not None else None,
                 commit=os.environ["GITHUB_SHA"],sha256=sha256((dest/"log.json.gz").read_bytes()).hexdigest())
        (dest/"receipt.json").write_text(json.dumps(row),encoding="utf8")
    if schedule is not None:
        require(sha256(key(schedule).encode()).hexdigest()==row["schedule_sha256"],"Recipient schedule differs")
    (compact/(ident+".json")).write_text(json.dumps(row),encoding="utf8")
    return schedule

def shard(number):
    _,physical=inventory()
    manifest=pinned("inputs/manifest.json","d9438b12d243ce9ed1449ddfdef6007dc98847cf9f31bc387f12b45696f6e89f")
    task=TASKS[number//5]
    source=next(r for r in manifest["tasks"] if r["task"]==task)
    problem=json.loads((Path("inputs")/task/"problem.json").read_bytes())
    require(problem_sha256(problem)==source["problem_sha256"],"Changed search input")
    for seed in SEEDS[2*(number%5):2*(number%5)+2]:
        bank=make_bank(problem,90+number//5,seed,196000)
        for cfg in physical:
            args=(task,seed,cfg,bank,problem,source["optimum"],physical)
            schedule=None
            if json.loads(cfg)[0]=="donor":
                schedule=run_case(*args,donor=True)
            run_case(*args,schedule=schedule)

def summarize():
    roles,physical=inventory()
    rows=[json.loads(f.read_bytes()) for f in Path("collected").rglob("*.json")]
    require(all(r["commit"]==os.environ["GITHUB_SHA"] for r in rows),"Foreign run")
    sources={(r["task"],r["seed"],r["configuration"]):r for r in rows if r["donor_source"]}
    recipients=[r for r in rows if not r["donor_source"]]
    require(len(rows)==5400 and len(sources)==1200 and len(recipients)==4200,"Incomplete independent series")
    for r in recipients:
        if json.loads(r["configuration"])[0]=="donor":
            source=sources[r["task"],r["seed"],r["configuration"]]
            require(source["schedule_sha256"]==r["schedule_sha256"],"Unmatched donor")
    clusters={t[-4:]:[x for x in TASKS if x[-4:]==t[-4:]] for t in TASKS}
    result=compare(recipients,roles,clusters,SEEDS)
    Path("independent-comparisons.json").write_text(json.dumps(result,indent=2),encoding="utf8")

if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("mode",choices=("run","summarize"))
    cli.add_argument("--shard",type=int,choices=range(150))
    args=cli.parse_args()
    if args.mode=="run": shard(args.shard)
    else: summarize()

"""Freeze adaptive candidates and paired controls from complete tuning series only."""
import hashlib
import json
from pathlib import Path
from statistics import mean

from .analysis import endpoint
from .design import METRICS, TOTAL, tasks
from .followup import configurations, gate, SEEDS
from .study import require

FOLLOW_COMMIT = "8d763b123554f81a63c81206c10eda0fe3fcdb4d"


def freeze():
    gate()
    starts = {(task, seed) for task in tasks() for seed in SEEDS}
    groups = {}
    optima = {}

    def add(cfg, row):
        start = (row["task"], row["seed"])
        group = groups.setdefault(cfg, {})
        require(start in starts and start not in group and row["total"] == TOTAL, "Unpaired input")
        opt = optima.setdefault(start[0], row["optimum"])
        require(opt == row["optimum"] and 0 <= row["best"] <= opt and opt > 0, "Invalid endpoint")
        group[start] = row

    for line in Path("prior/verified.jsonl").read_bytes().splitlines():
        row = json.loads(line)
        pc, role = row["pc"], row["role"]
        if role in ("k2", "k3"):
            add((pc,"fixed",15,3 if role=="k3" else 2,1,145,None),row)
        elif (pc,role) in ((90,"A4"),(100,"A5")):
            add((pc,role,15,2,1,row["threshold"],None),row)

    follow = set(configurations())
    digest = hashlib.sha256()
    files = sorted(Path("follow/collected").rglob("*.json"))
    require(len(files) == len(follow)*len(starts), "Incomplete follow-up artifact")
    for path in files:
        data = path.read_bytes()
        digest.update(hashlib.sha256(data).digest())
        row = json.loads(data)
        cfg = tuple(row["config"])
        require(row["commit"] == FOLLOW_COMMIT and cfg in follow, "Unexpected follow-up case")
        add(cfg,row)
    require(follow <= groups.keys() and all(g.keys()==starts for g in groups.values()), "Incomplete groups")

    def score(cfg, metric):
        per_task = {task:mean(endpoint(groups[cfg][task,seed],metric) for seed in SEEDS) for task in tasks()}
        return mean(mean(per_task[t] for t in per_task if t.endswith(f"s{s:03}")) for s in range(50,60))

    estimates = {cfg:{metric:score(cfg,metric) for metric in METRICS} for cfg in groups}
    roles = []
    physical = set()
    for pc, mechanism in ((90,"A4"),(100,"A5")):
        k2 = (pc,"fixed",15,2,1,145,None)
        k3 = (pc,"fixed",15,3,1,145,None)
        adaptive = [c for c in groups if c[:3] == (pc,mechanism,15)]
        # A5 changes only elite count. Fixed k3 is its separate registered control.
        static = [c for c in groups if c[:3]==(pc,"fixed",15) and
                  (c[4]==1 if mechanism=="A4" else c[3]==2)]
        for metric, secondary in (METRICS,METRICS[::-1]):
            def rank(c):
                return (estimates[c][metric],estimates[c][secondary],c[-1] is not None,
                        c[3:6],c[-1] or 0)
            candidate = min(adaptive,key=rank)
            controls = dict(k2=k2,k3=k3,tuned_static=min(static,key=rank),
                            same_mechanism_H145=(pc,mechanism,15,2,1,145,None),
                            donor_schedule=("donor",*candidate))
            physical.update((candidate,*controls.values()))
            roles.append(dict(pc=pc,metric=metric,candidate=candidate,controls=controls))
    result = dict(roles=roles,followup_digest=digest.hexdigest(),
                  independent_recipient_runs=len(physical)*300,
                  independent_donor_runs=len({r["candidate"] for r in roles})*300)
    Path("frozen-roles.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")


if __name__=="__main__":
    freeze()

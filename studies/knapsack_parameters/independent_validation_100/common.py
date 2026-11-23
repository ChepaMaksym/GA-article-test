"""Bind each execution to the registered source, run identity and previous resource ledger."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPO = "ChepaMaksym/GA-article-test"
BRANCH = "research/independent-validation-100"
WORKFLOW = ".github/workflows/independent-validation-100.yml"

def require(ok, message):
    if not ok:
        raise ValueError(message)

def read(path):
    return json.loads(path.read_bytes())

def require_ci():
    env=os.environ
    require(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_REPOSITORY")==REPO
            and env.get("GITHUB_REF")=="refs/heads/"+BRANCH and env.get("GITHUB_EVENT_NAME")=="workflow_dispatch"
            and env.get("GITHUB_RUN_ATTEMPT")=="1" and re.fullmatch(r"[1-9]\d*",env.get("GITHUB_RUN_ID",""))
            and re.fullmatch(r"[0-9a-f]{40}",env.get("GITHUB_SHA","")), "Unexpected CI identity")
    import numpy
    require(sys.version_info[:3]==(3,12,14) and numpy.__version__=="2.2.6","Unregistered execution environment")

def check_seal(grant):
    p=HERE/"source_manifest.json"
    require(sha256(p.read_bytes()).hexdigest()==grant["source_manifest_sha256"],"Source manifest checksum differs")
    rows=read(p)["files"]
    require(len({r["path"] for r in rows})==len(rows),"Repeated sealed path")
    for row in rows:
        path=ROOT/row["path"]
        require(path.resolve().is_relative_to(ROOT) and path.is_file()
                and path.stat().st_size==row["bytes"] and sha256(path.read_bytes()).hexdigest()==row["sha256"],
                "Unmatched registered file: "+row["path"])

def guard(stage, authorization_id=None):
    require_ci()
    require(stage in ("main","benchmark"),"Unknown study stage")
    a=read(HERE/"resource_authorization.json")
    require(a["status"]=="AUTHORIZED" and a["fresh_approval"] and a["public_release_approved"] and
            a["authorization_id"]==(authorization_id or os.environ["IV_AUTH"]) and
            a["repository"]==REPO and a["ref"]=="refs/heads/"+BRANCH,"Inactive or different study registration")
    p=read(HERE/"protocol.json")
    require((a["runner_minutes"],a["artifact_bytes"])==(p["limits"]["runner_minutes"],p["limits"]["artifact_bytes"]),
            "Resource ceilings differ")
    ids=json.loads(os.environ.get("IV_PRIOR_RUN_IDS","[]"))
    require(type(ids) is list and all(type(i) is int and 0<i<int(os.environ["GITHUB_RUN_ID"]) for i in ids)
            and len(set(ids))==len(ids),"Invalid prior run identities")
    a["prior_run_ids"]=ids
    check_seal(a)
    return p,a

def validate_origin(row, auth):
    allowed={str(i) for i in auth["prior_run_ids"]}|{os.environ["GITHUB_RUN_ID"]}
    require(row["workflow_run_id"] in allowed and row["workflow_commit"]==os.environ["GITHUB_SHA"] and
            row["source_manifest_sha256"]==auth["source_manifest_sha256"] and
            row["authorization_id"]==auth["authorization_id"] and
            re.fullmatch(r"[0-9a-f]{64}",row["inputs_manifest_sha256"]), "Different run, source or input provenance")

def enroll(resume):
    from .history import api,list_all
    guard("benchmark")
    runs=list_all(api,"/actions/workflows/independent-validation-100.yml/runs","workflow_runs",branch=BRANCH,event="workflow_dispatch")
    rid=int(os.environ["GITHUB_RUN_ID"])
    need_current=[r for r in runs if r["id"]==rid and r["head_sha"]==os.environ["GITHUB_SHA"]]
    require(len(need_current)==1,"Study run is missing")
    past=sorted((r for r in runs if r["id"]!=rid),key=lambda r:r["id"])
    require(all(r["id"]<rid and r["status"]=="completed" and r["conclusion"]!="success" and r["run_attempt"]==1 and
                r["path"]==WORKFLOW and r["head_branch"]==BRANCH for r in past), "Existing active or successful study")
    require((not past and not resume) or (past and str(past[-1]["id"])==resume),"Resume must name most recent prior attempt")
    ids=json.dumps([r["id"] for r in past],separators=(",",":"))
    with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as f: print("prior="+ids,file=f)
    with open(os.environ["GITHUB_ENV"],"a",encoding="utf-8") as f: print("IV_PRIOR_RUN_IDS="+ids,file=f)

if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("--resume-run-id",default="")
    args=cli.parse_args()
    enroll(args.resume_run_id)

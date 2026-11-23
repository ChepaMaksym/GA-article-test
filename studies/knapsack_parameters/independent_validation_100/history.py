"""Classify workflow identities without opening search outcomes from the holdout."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

HERE = Path(__file__).resolve().parent
REPO = "ChepaMaksym/GA-article-test"
SINCE = "2026-11-10"
CATEGORIES = {
    "population-validation-100": "pilot on s000,s001,s005; input audit of s050-s059",
    "population-validation-100-main-tests": "software checks for s050-s059",
    "population-validation-100-main": "population comparison s050-s059",
    "population-validation-100-completion": "completion of population comparison s050-s059",
    "initial-grid-100-technical": "old pilot and compatibility; certified s060-s069 inputs without GA",
    "initial-grid-100-checks": "retained-input/compact audit",
    "initial-grid-100-tuning": "initial-parameter grid s050-s059",
    "initial-grid-100-qc": "post-processing of the initial grid",
    "mutation-grid-100-technical": "pilot on old tasks, tuning on s050-s059 or checks and retained-data preparation",
    "mutation-grid-100-report": "tuning report only",
    "calibrated-selection-technical": "technical workflow on old tasks; separate registered cohort s070-s079",
    "iterative-validation": "retrospective existing data s050-s059",
    "iterative-validation-population13-technical": "old pilot tasks and s050 controls",
    "iterative-validation-population13-main": "90 paired searches on s050-s059",
}
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def need(ok, msg):
    if not ok:
        raise ValueError(msg)

def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def api(path):
    need(path.startswith("/actions/") and "://" not in path, "Invalid metadata endpoint")
    headers = {"Accept":"application/vnd.github+json", "User-Agent":"knapsack-holdout-history"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with build_opener(NoRedirect()).open(Request("https://api.github.com/repos/"+REPO+path,headers=headers), timeout=45) as r:
        return json.load(r)

def list_all(request, path, key, **filters):
    rows = []
    for page in range(1, 101):
        response = request(path+"?"+urlencode(dict(filters, per_page=100, page=page)))
        batch = response[key]
        rows.extend(batch)
        if len(rows) >= response["total_count"] or len(batch) < 100:
            need(len(rows)==response["total_count"]==len({r["id"] for r in rows}), "Incomplete Actions metadata: "+path)
            return rows
    raise ValueError("Excessive result count: "+path)

def pin(run):
    return {k:run[k] for k in ("id", "run_attempt", "head_sha", "head_branch", "path", "event", "conclusion")}

def job_identities(request,run_id):
    jobs=list_all(request, f"/actions/runs/{run_id}/jobs", "jobs")
    return sorted((j["id"], j["name"], j["conclusion"]) for j in jobs)

def check(registry, request, current=None, prior=()):
    known={r["id"]:r for r in registry["runs"]}
    live=list_all(request,"/actions/runs","workflow_runs",created=">="+SINCE)
    seen=set()
    new=[]
    for run in live:
        rid=run["id"]
        if rid in known:
            saved=known[rid]
            need(run["status"]=="completed" and pin(run)=={k:saved[k] for k in pin(run)},f"Changed historical run {rid}")
            need(digest(job_identities(request,rid))==saved["jobs_sha256"],f"Changed job identities {rid}")
            need(saved["scope"]==CATEGORIES[Path(saved["path"]).stem],"Unknown search scope")
            seen.add(rid)
        elif rid==current or rid in prior:
            need(run["event"]=="workflow_dispatch" and run["path"]==".github/workflows/independent-validation-100.yml" and
                 run["head_branch"]=="research/independent-validation-100" and run["run_attempt"]==1, "Unexpected stage execution")
            if rid==current:
                need(run["head_sha"]==os.environ["GITHUB_SHA"], "Current study commit differs")
            new.append(rid)
        else:
            raise ValueError(f"Unclassified workflow run {rid}: inspect its immutable inputs before searching")
    need(seen==set(known) and current in new and set(new)=={current,*prior}, "Missing historical or study metadata")
    local=json.loads((HERE/"local_history.json").read_bytes())
    need(local["status"]=="ELIGIBLE_WITHIN_PROJECT_EVIDENCE","Local holdout identity review is incomplete")
    return {"schema":"independent-validation100-history-v1","cohort":"s060-s069","previous_holdout_search_runs":0,
            "additional_searched_problem_keys":local["additional_searched_problem_keys"],
            "status":"ELIGIBLE_WITHIN_PROJECT_EVIDENCE","historical_workflow_runs":len(known),
            "prior_enrolled_study_runs":list(prior),"registered_history_sha256":digest(registry),
            "original_input_audit":42876556319,"coverage":"Initial project audit and reviewed subsequent local records and repository workflows up to enrollment"}

if __name__=="__main__":
    from .common import guard
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    _,auth=guard("benchmark")
    receipt=check(json.loads((HERE/"history_registry.json").read_bytes()),api,int(os.environ["GITHUB_RUN_ID"]),auth.get("prior_run_ids",[]))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open("x",encoding="utf-8") as f:
        json.dump(receipt,f,indent=2)

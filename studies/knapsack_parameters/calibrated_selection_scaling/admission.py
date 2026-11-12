"""One CI dispatch per explicit grant; no token enters the worker container."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .common import BRANCHES, ROOT, ci_only, read_json, require, verify_source, write_json


def admit(output):
    ci_only()
    require(read_json(ROOT / "protocol.json").get("execution_policy") == "READY_FOR_TECHNICAL_RUN",
            "Execution is deferred while preparing the requested documents")
    authorization = read_json(ROOT / "technical_authorization.json")
    require(authorization.get("status") == "AUTHORIZED"
            and authorization.get("stage") == "technical"
            and authorization.get("runner_minutes") == 60
            and authorization.get("artifact_bytes") == 2 * 1024 ** 3
            and authorization.get("historical_budgets_inherited") is False
            and authorization.get("main_authorized") is False,
            "A separate technical permission is required")
    require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test"
            and os.environ.get("GITHUB_REF") == BRANCHES["technical"]
            and os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "Unregistered dispatch identity")
    verify_source()
    branch = BRANCHES["technical"].removeprefix("refs/heads/")
    run_id = int(os.environ["GITHUB_RUN_ID"])
    token = os.environ.get("GITHUB_TOKEN")
    require(token, "The standard CI read token is required for grant reuse detection")
    query = urlencode({"branch": branch, "per_page": 100})
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    run_url = "https://api.github.com/repos/ChepaMaksym/GA-article-test/actions/runs/" + str(run_id)
    with urlopen(Request(run_url, headers=headers), timeout=30) as response:
        current = json.load(response)
    require(current.get("id") == run_id and type(current.get("workflow_id")) is int,
            "The current workflow identity is unavailable")
    endpoint = ("https://api.github.com/repos/ChepaMaksym/GA-article-test/actions/workflows/"
                + str(current["workflow_id"]) + "/runs?" + query)
    with urlopen(Request(endpoint, headers=headers), timeout=30) as response:
        require(response.geturl().startswith("https://api.github.com/"), "Untrusted run-history redirect")
        history = json.load(response)
    rows = history.get("workflow_runs")
    require(type(rows) is list and history.get("total_count") == 1 and len(rows) == 1
            and rows[0].get("id") == run_id,
            "This grant cannot be reused: another dispatch exists; retain usage and request a recovery allocation")
    write_json(output, {"status": "ADMITTED_SINGLE_DISPATCH", "run_id": run_id,
                        "branch": branch, "runner_minutes": 60, "artifact_bytes": 2 * 1024 ** 3,
                        "sum_workflow_timeout_minutes": 55,
                        "retries_or_additional_dispatches_authorized": False,
                        "previous_dispatch_count": 0,
                        "main_authorized": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    admit(parser.parse_args().output)

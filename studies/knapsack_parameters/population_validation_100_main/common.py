"""Authority, fixed-input verification, and I/O for the 100-item main stage."""
from pathlib import Path
import os
import sys

from studies.knapsack_parameters.population_validation_100.common import read_json, write_json, sha, require, require_ci

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]


def verify_source():
    """Verify the prospective code seal without admitting the main search."""
    require_ci()
    manifest = read_json(HERE / "source_manifest.json")
    require(manifest.get("schema") == "population-validation-100-main-source-v1", "Main source seal missing")
    for row in manifest["files"]:
        path = (REPOSITORY / row["path"]).resolve()
        require(path.is_relative_to(REPOSITORY.resolve()) and path.is_file(), "Unsafe source dependency")
        require(path.stat().st_size == row["bytes"] and sha(path) == row["sha256"], "Frozen source differs: " + row["path"])
    return manifest


def guard_main():
    """Fail closed until a separately authorized, sealed main run is available."""
    require_ci()
    require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test"
            and os.environ.get("GITHUB_REF") == "refs/heads/research/population100-main-20261110",
            "Main study runs only in the registered repository and branch")
    require(os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "Preserve completed results and register a remaining-case ledger before any retry")
    import numpy as np
    require(sys.version_info[:3] == (3, 12, 14) and np.__version__ == "2.2.6", "Frozen Python/NumPy versions differ")
    auth = read_json(HERE / "resource_authorization.json")
    require(auth.get("stage") == "main" and auth.get("status") == "AUTHORIZED", "Separate authorization for the 900-run series is required")
    require(auth.get("runner_minutes") == 700 and auth.get("artifact_bytes") == 12884901888,
            "Main resource limit differs from the approved 700 runner-minutes and 12 GiB")
    require(auth.get("historical_budgets_inherited") is False and auth.get("technical_run_id") == 42780269269,
            "Technical resource use cannot be charged to the main budget")
    verify_source()
    p = read_json(HERE / "protocol.json")
    require(p["schema"] == "population-validation-100-main-v1" and p["item_count"] == 100
            and p["populations"] == [10, 20, 30] and p["candidate_population"] == 20
            and p["total_evaluations"] == 100000 and p["main_runs"] == 900, "Main study settings differ")
    require((p["p_m"], p["p_c"], p["tournament_size"], p["elite_count"]) == (0.01, 0.9, 2, 1),
            "Fixed genetic operators differ")
    require(p["fixed_parameters"] == {"p_m": 0.01, "p_c": 0.9, "tournament_size": 2, "elite_count": 1}
            and p["source_commit"] == "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c", "Fixed parameters or source revision differ")
    require(p["families"] == list(range(50, 60)) and p["types"] == ["UC", "WC", "SC"]
            and p["search_seeds"] == list(range(150001, 150011)), "Task or seed inventory differs")
    require(p["technical_input_manifest_sha256"] == "ceb0b1bb021e46eee316ca1422342053b2df3307311dea86e203599aa7173552",
            "Technical input manifest differs")
    require(sha(HERE / "data" / "certified_inputs_42780269269.zip") == p["certified_inputs_zip_sha256"],
            "Certified-input ZIP differs from the completed technical stage")
    return p

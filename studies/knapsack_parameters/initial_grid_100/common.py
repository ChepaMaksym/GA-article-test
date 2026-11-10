"""Stage authority, immutable sources and small I/O for the registered grid."""
from pathlib import Path
import os
import sys

from studies.knapsack_parameters.population_validation_100.common import (
    read_json, write_json, sha, require, require_ci,
)
from studies.knapsack_parameters.population_validation_100_main.common import verify_source as verify_historical_source

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
BRANCHES = {stage: f"refs/heads/research/initial-grid100-{stage}-20261110"
            for stage in ("technical", "tuning", "validation")}


def verify_source():
    """Check the registered wrapper and the unchanged historical dependencies."""
    verify_historical_source()
    original = REPOSITORY / "studies/knapsack_parameters/population_validation_100_main/source_manifest.json"
    require(sha(original) == "ce799ba032c1178a988e8a608daaf1b44ee074c47e9e88f10671924e3565798a",
            "Historical main source seal differs")
    manifest = read_json(HERE / "source_manifest.json")
    require(manifest.get("schema") == "initial-grid-100-source-v1", "New grid source seal missing")
    seen = set()
    for row in manifest["files"]:
        relative = row["path"]
        require(relative not in seen and not Path(relative).is_absolute() and ".." not in Path(relative).parts,
                "Duplicate or unsafe source path")
        seen.add(relative)
        path = (REPOSITORY / relative).resolve()
        require(path.is_relative_to(REPOSITORY.resolve()) and path.is_file()
                and path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
                "Frozen source differs: " + relative)
    return manifest


def guard_stage(stage):
    """Require the distinct resource permission for the requested experimental stage."""
    require_ci()
    require(stage in BRANCHES, "Unknown experimental stage")
    require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test"
            and os.environ.get("GITHUB_REF") == BRANCHES[stage], "Unregistered study repository or branch")
    require(os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "Preserve completed evidence and register missing identities before retry")
    import numpy as np
    require(sys.version_info[:3] == (3, 12, 14) and np.__version__ == "2.2.6", "Frozen Python/NumPy versions differ")
    path = HERE / ("resource_authorization.json" if stage == "technical" else stage + "_authorization.json")
    require(path.is_file(), "Separate resource permission for this stage is absent")
    authorization = read_json(path)
    require(authorization.get("status") == "AUTHORIZED" and authorization.get("stage") == stage
            and authorization.get("historical_budgets_inherited") is False,
            "No distinct authorization for this experimental stage")
    require(type(authorization.get("runner_minutes")) is int and authorization["runner_minutes"] > 0
            and type(authorization.get("artifact_bytes")) is int and authorization["artifact_bytes"] > 0,
            "Authorized resource ceiling is absent")
    if stage == "technical":
        require(authorization["runner_minutes"] == 45 and authorization["artifact_bytes"] == 1073741824
                and authorization.get("tuning_authorized") is False
                and authorization.get("validation_authorized") is False,
                "Technical authority must not enable tuning or validation")
    if stage == "tuning":
        require(authorization["runner_minutes"] == 1750 and authorization["artifact_bytes"] == 17179869184
                and authorization.get("validation_authorized") is False,
                "Tuning authority must match its separate cap and leave validation disabled")
    verify_source()
    protocol = read_json(HERE / "protocol.json")
    require(protocol.get("schema") == "initial-grid-100-protocol-v1"
            and protocol.get("item_count") == 100 and protocol.get("populations") == [10, 15, 20, 25]
            and protocol.get("crossover_percentages") == [70, 80, 90, 100]
            and protocol.get("total_evaluations_including_initial") == 100000,
            "Registered grid or dimension differs")
    require(protocol.get("fixed") == {"p_m": 0.01, "tournament_size": 2, "elite_count": 1,
                                      "bit_inheritance_probability": 0.5}, "Fixed genetic operators differ")
    require(protocol["tuning"]["seeds"] == [150001, 150002, 150003]
            and protocol["tuning"]["results"] == 1440 and protocol["tuning"]["new_runs"] == 1260
            and protocol["validation"]["seeds"] == list(range(160001, 160011)), "Registered repetition inventory differs")
    require(protocol.get("resources", {}).get(stage + "_authorized") is True,
            "The protocol has not recorded authorization for this stage")
    return protocol


def guard_checks():
    """Permit only prospective tests and retained-input audit within the technical cap."""
    require_ci()
    require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test"
            and os.environ.get("GITHUB_REF") == "refs/heads/research/initial-grid100-checks-20261110"
            and os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "Unregistered checks-only execution")
    import numpy as np
    require(sys.version_info[:3] == (3, 12, 14) and np.__version__ == "2.2.6", "Frozen Python/NumPy versions differ")
    technical = read_json(HERE / "resource_authorization.json")
    tuning = read_json(HERE / "tuning_authorization.json")
    require(technical.get("status") == "AUTHORIZED" and technical.get("runner_minutes") == 45
            and technical.get("artifact_bytes") == 1073741824 and technical.get("historical_budgets_inherited") is False,
            "The original technical-stage authority differs")
    require(tuning.get("status") == "PENDING_USER_APPROVAL" and tuning.get("runner_minutes") == 0
            and tuning.get("artifact_bytes") == 0, "Checks-only execution cannot enable the tuning search")
    ledger = read_json(HERE / "data/technical_checks_budget.json")
    require(ledger.get("previous_rounded_runner_minutes") == 20 and ledger.get("checks_timeout_minutes") == 10
            and ledger.get("previous_artifact_bytes") == 137803074 and ledger.get("checks_artifact_cap") == 536870912
            and 20 + 10 <= technical["runner_minutes"]
            and 137803074 + 536870912 <= technical["artifact_bytes"],
            "Prospective checks would exceed the approved technical resource ceiling")
    verify_source()
    protocol = read_json(HERE / "protocol.json")
    require(protocol.get("resources", {}).get("tuning_authorized") is False,
            "Checks-only execution cannot admit tuning")
    return protocol

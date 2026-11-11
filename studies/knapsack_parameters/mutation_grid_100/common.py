"""Separate source seals and resource authorization for the mutation study."""
import os
from pathlib import Path
import sys

from studies.knapsack_parameters.population_validation_100.common import (
    read_json, write_json, sha, require, require_ci,
)

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
BRANCHES = {stage: f"refs/heads/research/mutation-grid100-{stage}-20261111"
            for stage in ("technical", "tuning", "validation")}


def verify_source():
    """Verify prospective sources and the immutable historical source inventory."""
    old = REPOSITORY / "studies/knapsack_parameters/initial_grid_100/source_manifest.json"
    require(sha(old) == "2ed212337b22706decd7123ab1111cbc4c62fbe357e29478c1c868acf3c2f44f",
            "Retained tuning source seal differs")
    from studies.knapsack_parameters.initial_grid_100.common import verify_source as verify_retained
    verify_retained()
    manifest = read_json(HERE / "source_manifest.json")
    require(manifest.get("schema") == "mutation-grid-100-source-v1", "Mutation source seal is absent")
    seen = set()
    for row in manifest["files"]:
        relative = row["path"]
        require(relative not in seen and not Path(relative).is_absolute()
                and ".." not in Path(relative).parts, "Duplicate or unsafe frozen path")
        seen.add(relative)
        path = REPOSITORY / relative
        require(path.resolve().is_relative_to(REPOSITORY.resolve()) and path.is_file()
                and not path.is_symlink() and path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"], "Frozen mutation source differs: " + relative)
    return manifest


def guard_stage(stage):
    """Fail closed until that stage has a distinct recorded resource permission."""
    require_ci()
    require(stage in BRANCHES and os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test"
            and os.environ.get("GITHUB_REF") == BRANCHES[stage], "Unregistered study repository or branch")
    require(os.environ.get("GITHUB_RUN_ATTEMPT") == "1",
            "Retain completed cases and register only missing identities before recovery")
    import numpy as np
    require(sys.version_info[:3] == (3, 12, 14) and np.__version__ == "2.2.6",
            "Registered Python or NumPy version differs")
    path = HERE / ("resource_authorization.json" if stage == "technical" else stage + "_authorization.json")
    require(path.is_file(), "Separate authorization for this stage is absent")
    authority = read_json(path)
    require(authority.get("stage") == stage and authority.get("status") == "AUTHORIZED"
            and authority.get("historical_budgets_inherited") is False,
            "Resource permission has not been granted for this stage")
    require(type(authority.get("runner_minutes")) is int and authority["runner_minutes"] > 0
            and type(authority.get("artifact_bytes")) is int and authority["artifact_bytes"] > 0,
            "Separate resource ceilings are absent")
    if stage == "technical":
        require(authority["runner_minutes"] == 60 and authority["artifact_bytes"] == 1073741824
                and authority.get("tuning_authorized") is False
                and authority.get("validation_authorized") is False,
                "Technical permission cannot enable main stages")
    if stage == "tuning":
        require(authority["runner_minutes"] == 2000 and authority["artifact_bytes"] == 21474836480
                and authority.get("validation_authorized") is False,
                "Tuning permission must match its cap and must not enable validation")
    verify_source()
    protocol = read_json(HERE / "protocol.json")
    require(protocol.get("schema") == "mutation-grid-100-protocol-v1"
            and protocol.get("resources", {}).get(stage + "_authorized") is True,
            "The protocol has no authorization for this stage")
    require(protocol["item_count"] == 100 and protocol["populations"] == [10, 15, 20]
            and protocol["mutation_basis_points"] == [25, 50, 75, 100, 150, 200]
            and protocol["total_evaluations_including_initial"] == 100000
            and protocol["fixed"] == {"p_c": 1.0, "tournament_size": 2,
                                      "elite_count": 1, "bit_inheritance_probability": 0.5},
            "Registered grid or fixed operators differ")
    return protocol

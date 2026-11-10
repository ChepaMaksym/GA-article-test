"""Authority and immutable evidence checks for completing fourteen missing runs."""
from pathlib import Path
import os
import sys

from studies.knapsack_parameters.population_validation_100.common import (
    read_json, write_json, sha, require, require_ci,
)
from studies.knapsack_parameters.population_validation_100_main.common import verify_source as verify_original_source

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
ORIGINAL_RUN = 42813784277
ORIGINAL_COMMIT = "653b7a3f9c5e66d31ec8ca93fb4e710bd0078ff8"
ORIGINAL_SEAL = "ce799ba032c1178a988e8a608daaf1b44ee074c47e9e88f10671924e3565798a"
TECHNICAL_INPUT_SEAL = "ceb0b1bb021e46eee316ca1422342053b2df3307311dea86e203599aa7173552"


def verify_source():
    """Verify both the historical algorithm seal and the completion wrapper seal."""
    verify_original_source()
    original = REPOSITORY / "studies/knapsack_parameters/population_validation_100_main/source_manifest.json"
    require(sha(original) == ORIGINAL_SEAL, "Original main-stage source seal differs")
    manifest = read_json(HERE / "source_manifest.json")
    require(manifest.get("schema") == "population-validation-100-completion-source-v1",
            "Completion source seal differs")
    seen = set()
    for row in manifest["files"]:
        relative = row["path"]
        require(relative not in seen and not Path(relative).is_absolute() and ".." not in Path(relative).parts,
                "Unsafe or duplicate sealed path")
        seen.add(relative)
        path = (REPOSITORY / relative).resolve()
        require(path.is_relative_to(REPOSITORY.resolve()) and path.is_file()
                and path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
                "Completion source differs: " + relative)
    return manifest


def guard_completion():
    """Admit only the registered completion branch inside the original aggregate cap."""
    require_ci()
    require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test"
            and os.environ.get("GITHUB_REF") == "refs/heads/research/population100-completion-20261110",
            "Completion runs only in the registered repository and branch")
    require(os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "Retain evidence and register only missing identities before retry")
    import numpy as np
    require(sys.version_info[:3] == (3, 12, 14) and np.__version__ == "2.2.6", "Frozen Python/NumPy versions differ")
    authorization = read_json(HERE / "resource_authorization.json")
    require(authorization.get("status") == "AUTHORIZED" and authorization.get("stage") == "completion",
            "Completion authority missing")
    require(authorization.get("parent_main_runner_minutes") == 700
            and authorization.get("parent_main_artifact_bytes") == 12884901888,
            "Original main-stage authorization differs")
    require(authorization.get("runner_minutes") == 60 and authorization.get("artifact_bytes") == 322122547,
            "Completion sub-allocation differs")
    verify_source()
    protocol = read_json(HERE / "protocol.json")
    require(protocol.get("original_run_id") == ORIGINAL_RUN and protocol.get("original_commit") == ORIGINAL_COMMIT
            and protocol.get("original_code_manifest_sha256") == ORIGINAL_SEAL,
            "Original experiment identity differs")
    require(protocol.get("completed") == 886 and protocol.get("missing") == 14,
            "Completion identity counts differ")
    require(protocol.get("recovery_runner_minutes") == 60
            and protocol.get("recovery_artifact_bytes") == 322122547,
            "Completion allocation differs from the frozen protocol")
    require(protocol.get("original_runner_minutes_rounded") == 436
            and 436 + 60 <= 700 and protocol.get("original_artifact_bytes") == 6917596921
            and 6917596921 + 322122547 <= 12884901888,
            "Cumulative completion allocation exceeds the original approved cap")
    return protocol

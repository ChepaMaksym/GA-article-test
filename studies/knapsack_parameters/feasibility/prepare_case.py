"""Prepare one frozen knapsack instance in CI; no genetic algorithm."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from .ascent import prepare_center
from .certification import certify_center, validate_witness, write_certificate_csv
from .data_audit import REPO_ROOT, require, sha256_bytes, write_json
from .frozen_inputs import DATA_MANIFEST_SHA256, DEFAULT_INPUTS, load_frozen_inputs, read_json
from .solvers import (PreparationDeadlineExceeded, ResourceLimitExceeded,
                      solve_capacity, solve_profit)


def member_manifest(output, provenance):
    rows = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.relative_to(output).as_posix() != "file_manifest.json":
            raw = path.read_bytes()
            rows.append({"path": path.relative_to(output).as_posix(), "bytes": len(raw), "sha256": sha256_bytes(raw)})
    write_json(output / "file_manifest.json", {"schema_version": "knapsack-feasibility-files-v1", "excludes_self": True, "provenance": provenance, "files": rows})


def prepare_instance(instance, provenance, source_identity, output, *, deadline):
    """Unit fixtures may supply small instances; production uses frozen inputs."""
    output = Path(output).resolve()
    require(not output.exists() or not any(output.iterdir()), "existing preparation evidence is not overwritten")
    require(not output.is_relative_to(REPO_ROOT), "preparation output must be isolated outside the scientific checkout")
    output.mkdir(parents=True, exist_ok=True)
    record = {"schema_version": "knapsack-feasibility-case-v1", "status": "RUNNING",
              "instance_id": instance.instance_id, "class_label": instance.class_label,
              "family": instance.family, "index": instance.index, "n": instance.n,
              "capacity": instance.capacity, "source_identity": source_identity,
              "provenance": provenance, "exact": {}, "preparation": None,
              "certificate": None, "neighbors_file": None, "failure": None}
    write_json(output / "execution-start.json", {"started_at": datetime.now(timezone.utc).isoformat(), "provenance": provenance, "instance_id": instance.instance_id})

    def checkpoint(phase):
        write_json(output / "case.json", record)
        write_json(output / "execution-progress.json", {"phase": phase, "status": record["status"], "instance_id": instance.instance_id})

    checkpoint("AUTHENTICATED_FROZEN_INPUT")
    try:
        capacity = solve_capacity(instance, deadline=deadline)
        record["exact"]["capacity"] = capacity
        checkpoint("CAPACITY_DP_COMPLETE")
        profit = solve_profit(instance, deadline=deadline)
        record["exact"]["profit"] = profit
        checkpoint("PROFIT_DP_COMPLETE")
        if capacity["optimum_profit"] != profit["optimum_profit"]:
            record["status"] = "EXACT_METHOD_DISAGREEMENT"
            record["failure"] = {"type": "ExactMethodDisagreement", "message": "Independent exact methods returned different optima"}
        else:
            optimum = capacity["optimum_profit"]
            witnesses = {"capacity": validate_witness(instance, capacity), "profit": validate_witness(instance, profit)}
            require(all(row["feasible"] and row["profit"] == optimum for row in witnesses.values()), "exact witness verification failed")
            record["exact"].update(confirmed_optimum=optimum, witness_verified=True, witness_verification=witnesses)
            preparation = prepare_center(instance, max_passes=100, deadline=deadline)
            record["preparation"] = preparation
            checkpoint("CENTER_PREPARATION_COMPLETE")
            if preparation["preparation_capped"]:
                record["status"] = "EXCLUDED_PREPARATION_CAP"
            else:
                require(preparation["natural_stop"], "center did not complete naturally or reach the registered cap")
                certificate, rows = certify_center(instance, preparation["center"]["mask"], deadline=deadline)
                record["certificate"] = certificate
                record["neighbors_file"] = write_certificate_csv(output / "neighbors.csv", rows)
                if not certificate["local_maximum"]:
                    record["status"] = "INCOMPLETE_CERTIFICATE"
                    record["failure"] = {"type": "LocalityDisagreement", "message": "Independent certificate found a better neighbor"}
                elif certificate["center"]["profit"] > optimum:
                    record["status"] = "EXACT_METHOD_DISAGREEMENT"
                    record["failure"] = {"type": "ImpossibleProfit", "message": "Certified center exceeds the exact optimum"}
                elif certificate["center"]["profit"] == optimum:
                    record["status"] = "EXCLUDED_GLOBAL_CENTER"
                else:
                    record["status"] = "ADMITTED_STRICT_LOCAL" if certificate["strict"] else "ADMITTED_PLATEAU_LOCAL"
    except (ResourceLimitExceeded, PreparationDeadlineExceeded) as error:
        record.update(status="RESOURCE_NOT_EVALUATED", failure={"type": type(error).__name__, "message": str(error)})
    except Exception as error:
        record.update(status="PREPARATION_ERROR", failure={"type": type(error).__name__, "message": str(error)})
    checkpoint("FINISHED")
    write_json(output / "execution-status.json", {"status": record["status"], "finished_at": datetime.now(timezone.utc).isoformat(), "instance_id": instance.instance_id, "provenance": provenance})
    member_manifest(output, provenance)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class", dest="class_label", required=True, choices=["UC", "WC", "SC"])
    parser.add_argument("--index", type=int, required=True, choices=range(10))
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    instances, provenance = load_frozen_inputs(args.expected_sha)
    instance = next(item for item in instances if item.class_label == args.class_label and item.index == args.index)
    source = next(row for row in read_json(DEFAULT_INPUTS / "data_manifest.json")["source_files"] if row["source_path"] == instance.source_path)
    identity = {"source_path": source["source_path"], "sha256": source["sha256"], "bytes": source["bytes"],
                "data_manifest_sha256": DATA_MANIFEST_SHA256, "source_commit_sha": provenance["source_commit_sha"]}
    provenance["artifact_name"] = f"knapsack-feasibility-case-{instance.instance_id}-{provenance['run_id']}-{provenance['run_attempt']}"
    record = prepare_instance(instance, provenance, identity, args.output, deadline=time.monotonic() + 1740)
    print(json.dumps({"instance_id": instance.instance_id, "status": record["status"]}))
    return 0 if record["status"] in {"ADMITTED_STRICT_LOCAL", "ADMITTED_PLATEAU_LOCAL", "EXCLUDED_GLOBAL_CENTER", "EXCLUDED_PREPARATION_CAP"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

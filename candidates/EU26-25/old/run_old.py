from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
import platform
from pathlib import Path
from time import perf_counter


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--max-iterations", type=int, required=True)
    parser.add_argument("--bks", type=int, default=27591)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--expected-instance-blob", required=True)
    parser.add_argument("--expected-penalty-blob", required=True)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    try:
        from pyvrp import PenaltyManager
        from pyvrp.cli import solve

        version = importlib.metadata.version("pyvrp")
        if version != "0.5.0":
            raise RuntimeError(f"expected pyvrp 0.5.0, found {version}")

        instance_bytes = args.instance.read_bytes()
        instance_blob = git_blob_sha(instance_bytes)
        if instance_blob != args.expected_instance_blob:
            raise RuntimeError(
                f"instance blob mismatch: {instance_blob} != {args.expected_instance_blob}"
            )

        penalty_path = Path(inspect.getsourcefile(PenaltyManager) or "")
        if not penalty_path.is_file():
            raise RuntimeError("cannot locate installed PenaltyManager source")
        penalty_blob = git_blob_sha(penalty_path.read_bytes())
        if penalty_blob != args.expected_penalty_blob:
            raise RuntimeError(
                f"PenaltyManager blob mismatch: {penalty_blob} != {args.expected_penalty_blob}"
            )

        result = solve(
            instance=args.instance,
            seed=args.seed,
            is_rounded=True,
            config_loc=args.config,
            instance_format="vrplib",
            round_func="dimacs",
            max_iterations=args.max_iterations,
        )

        feasible_costs = [float(item.best_cost) for item in result.stats.feas_stats]
        if len(feasible_costs) != result.num_iterations:
            raise RuntimeError(
                f"statistics length mismatch: {len(feasible_costs)} != {result.num_iterations}"
            )

        targets = {
            "bks_1_01": 1.01 * args.bks,
            "bks_1_005": 1.005 * args.bks,
            "bks": float(args.bks),
        }
        first_hit: dict[str, int | None] = {}
        for name, target in targets.items():
            first_hit[name] = next(
                (idx for idx, value in enumerate(feasible_costs, start=1) if value <= target),
                None,
            )

        best = result.best
        best_text = str(best)
        canonical = {
            "candidate_id": "EU26-25",
            "profile": "old_iteration_120k",
            "algorithm": "PYVRP_0_5_0_OLD",
            "source_commit": args.source_commit,
            "source_version": version,
            "instance_git_blob": instance_blob,
            "config_sha256": file_sha256(args.config),
            "penalty_manager_git_blob": penalty_blob,
            "seed": args.seed,
            "max_iterations": args.max_iterations,
            "completed_iterations": int(result.num_iterations),
            "final_cost": int(result.cost()),
            "feasible": bool(best.is_feasible()),
            "num_clients": int(best.num_clients()),
            "num_routes": int(best.num_routes()),
            "first_hit": first_hit,
            "solution_sha256": hashlib.sha256(best_text.encode()).hexdigest(),
        }
        scientific_digest = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        row = {
            **canonical,
            "scientific_digest": scientific_digest,
            "runtime_seconds": perf_counter() - started,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "pid": os.getpid(),
            "complete": True,
            "error": None,
        }
        args.output.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
        print(json.dumps(row, sort_keys=True))
        return 0
    except Exception as exc:
        failure = {
            "candidate_id": "EU26-25",
            "profile": "old_iteration_120k",
            "seed": args.seed,
            "max_iterations": args.max_iterations,
            "complete": False,
            "error": f"{type(exc).__name__}: {exc}",
            "runtime_seconds": perf_counter() - started,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pid": os.getpid(),
        }
        args.output.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
        print(json.dumps(failure, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

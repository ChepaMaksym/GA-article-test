from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2, 4), required=True)
    parser.add_argument("--max-iterations", type=int, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--expected-instance-blob", required=True)
    parser.add_argument("--expected-penalty-blob", required=True)
    parser.add_argument("--bks", type=int, default=27591)
    args = parser.parse_args()

    seeds = [int(token) for token in args.seeds.split(",") if token.strip()]
    if not seeds or len(set(seeds)) != len(seeds):
        raise SystemExit("seeds must be a non-empty unique comma-separated ledger")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    runner = Path(__file__).with_name("run_old.py")

    def run(seed: int) -> dict:
        output = args.output_dir / f"seed_{seed}.json"
        cmd = [
            sys.executable,
            str(runner),
            "--instance",
            str(args.instance),
            "--config",
            str(args.config),
            "--seed",
            str(seed),
            "--max-iterations",
            str(args.max_iterations),
            "--bks",
            str(args.bks),
            "--profile",
            args.profile,
            "--output",
            str(output),
            "--source-commit",
            args.source_commit,
            "--expected-instance-blob",
            args.expected_instance_blob,
            "--expected-penalty-blob",
            args.expected_penalty_blob,
        ]
        completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if not output.is_file():
            failure = {
                "candidate_id": "EU26-25",
                "profile": args.profile,
                "seed": seed,
                "complete": False,
                "error": "runner produced no JSON",
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
            output.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
        row = json.loads(output.read_text())
        row["batch_worker_count"] = args.workers
        row["runner_returncode"] = completed.returncode
        output.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
        return row

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run, seed): seed for seed in seeds}
        for future in as_completed(futures):
            rows.append(future.result())

    rows.sort(key=lambda row: int(row["seed"]))
    ledger = [int(row["seed"]) for row in rows]
    report = {
        "candidate_id": "EU26-25",
        "profile": args.profile,
        "workers": args.workers,
        "expected_seeds": seeds,
        "actual_seeds": ledger,
        "complete": ledger == seeds and all(row.get("complete") is True for row in rows),
        "scientific_digests": [row.get("scientific_digest") for row in rows],
        "costs": [row.get("final_cost") for row in rows],
    }
    (args.output_dir / "batch_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

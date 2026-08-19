from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

from old.moea_isa_kernel import FormulaCase

CASES = [
    FormulaCase((1, 0, 1, 0), (1, 1, 0, 0), 1),
    FormulaCase((1, 1, 1, 0), (0, 1, 0, 1), 5),
    FormulaCase((1, 0, 0, 1), (0, 1, 1, 0), 10),
]


def run(case: FormulaCase):
    return case.canonical()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, choices=(1, 2, 4), required=True)
    args = parser.parse_args()
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=ctx) as pool:
        rows = list(pool.map(run, CASES))
    payload = json.dumps(rows, separators=(",", ":"))
    print(json.dumps({
        "workers": args.workers,
        "rows": rows,
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

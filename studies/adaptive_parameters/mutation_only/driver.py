"""CI entry points. No work is executed by importing the module."""
from __future__ import annotations

import argparse
import copy
import gzip
import io
from pathlib import Path
import sys
import unittest
import urllib.error
import urllib.request
import zipfile

from . import contract as c


def require_phase(expected):
    c.require(c.phase(c.os.environ.get("COMMIT_MESSAGE", "")) == expected, "Wrong execution phase")


def validated_tests():
    transport = c.read_json(c.MODULE / "validated_tests.json")
    run_id, attempt = transport["run_id"], transport["run_attempt"]
    run = c.api(f"/actions/runs/{run_id}/attempts/{attempt}")
    c.require(run["conclusion"] == "success" and run["status"] == "completed" and
              run["head_sha"] == transport["implementation_sha"] and
              run["head_branch"] == c.BRANCH and run["path"] == c.WORKFLOW and
              c.phase(run["head_commit"]["message"]) == "tests", "Source checks not successful tests")
    artifact = c.api(f"/actions/artifacts/{transport['artifact_id']}")
    c.require(not artifact["expired"] and artifact["workflow_run"]["id"] == run_id and
              artifact["workflow_run"]["head_sha"] == run["head_sha"] and
              artifact["name"] == f"adaptive-mutation-tests-{run_id}-{attempt}" and
              artifact.get("digest") == "sha256:" + transport["artifact_zip_sha256"], "Wrong tests artifact")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, message, headers, new_url):
            return None
    request = urllib.request.Request(
        f"https://api.github.com/repos/{c.REPOSITORY}/actions/artifacts/{transport['artifact_id']}/zip",
        headers={"Authorization": "Bearer " + c.os.environ["GITHUB_TOKEN"], "User-Agent": "mutation-tests-receipt"})
    try:
        urllib.request.build_opener(NoRedirect).open(request, timeout=25)
    except urllib.error.HTTPError as exc:
        c.require(exc.code == 302, "Expected signed artifact redirect")
        location = exc.headers["Location"]
    else:
        raise ValueError("Missing signed artifact redirect")
    c.require(location.startswith("https://"), "Unsafe artifact storage protocol")
    # No API credential accompanies the signed storage request.
    with urllib.request.urlopen(location, timeout=25) as response:
        raw = response.read(16*1024*1024 + 1)
    c.require(len(raw) <= 16*1024*1024 and len(raw) == artifact["size_in_bytes"] and
              c.hashlib.sha256(raw).hexdigest() == transport["artifact_zip_sha256"], "Tests ZIP mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        c.require(len(names) == len(set(names)) and sum(v.file_size for v in archive.infolist()) < 16*1024*1024,
                  "Oversized or repeated test members")
        manifest = c.json.loads(archive.read("file_manifest.json"))
        c.require(manifest.get("protocol_id") == c.PROTOCOL and manifest.get("excludes_self") is True,
                  "Wrong tests manifest")
        members = manifest["files"]
        c.require(len({r["path"] for r in members}) == len(members) and
                  {r["path"] for r in members} | {"file_manifest.json"} == set(names), "Incomplete tests ZIP")
        for member in members:
            content = archive.read(member["path"])
            c.require(len(content) == member["bytes"] and c.hashlib.sha256(content).hexdigest() == member["sha256"],
                      "Wrong tests internal checksum")
        receipt = c.json.loads(archive.read("tests_receipt.json"))
    c.require(receipt.get("tests_passed") is True and receipt.get("tests_run", 0) > 0 and
              receipt.get("phase") == "tests" and receipt.get("protocol_id") == c.PROTOCOL and
              receipt.get("run_id") == run_id and receipt.get("run_attempt") == attempt and
              receipt.get("implementation_sha") == run["head_sha"] and
              receipt.get("source_manifest") == c.source_manifest(), "Missing or stale green checks")
    return receipt


def run_tests(output):
    require_phase("tests")
    provenance = c.authenticate(runtime=True)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in (
        "studies.adaptive_parameters.mutation_only.test_mutation_only",
        "studies.adaptive_parameters.mutation_only.test_contract"))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = stream.getvalue()
    print(report)
    (output / "tests.txt").write_text(report, encoding="utf-8")
    c.write_json(output / "tests_receipt.json", {**provenance,
        "phase": "tests", "tests_run": result.testsRun, "tests_passed": result.wasSuccessful(),
        "failures": len(result.failures), "errors": len(result.errors),
        "scientific_pilot_runs": 0})
    c.write_manifest(output)
    c.require(result.wasSuccessful(), "Independent CI checks failed")


def source_task(task):
    registration = c.read_json(c.MODULE / "registration.json")
    suffix = {"UC-s000": "00Uncorrelated/n00100/R01000/s000.kp",
              "WC-s001": "01WeaklyCorrelated/n00100/R01000/s001.kp",
              "SC-s005": "02StronglyCorrelated/n00100/R01000/s005.kp",
              "SC-s000": "02StronglyCorrelated/n00100/R01000/s000.kp"}[task]
    relative = "studies/knapsack_parameters/inputs/source/" + suffix
    c.require(c.identity(c.ROOT / relative)["sha256"] == registration["input_sha256"][relative], "Wrong data")
    raw = [int(v) for v in (c.ROOT / relative).read_text(encoding="utf-8").split()]
    n, capacity = raw[:2]
    c.require(n == 100 and len(raw) == 2 + 2*n and capacity > 0 and
              all(v > 0 for v in raw[2:]), "Malformed source data")
    problem = {"n": n, "capacity": capacity, "profits": raw[2::2], "weights": raw[3::2]}
    case = c.read_json(c.ROOT / f"studies/knapsack_parameters/evidence/run-37637475385/cases/{task}/case.json")
    return problem, case, relative


def initial_independent_score(problem, mask):
    c.require(len(mask) == problem["n"] and set(mask) <= {"0", "1"}, "Bad initial mask")
    weight = sum(problem["weights"][i] for i in range(problem["n"]) if mask[i] == "1")
    profit = sum(problem["profits"][i] for i in range(problem["n"]) if mask[i] == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def prepare(output):
    require_phase("prepare")
    provenance = c.authenticate(runtime=True)
    validated_tests()
    from .engine import evaluate, make_rngs
    registration = c.read_json(c.MODULE / "registration.json")
    banks = []
    for ti, task in enumerate(registration["tasks"]):
        problem, case, source = source_task(task)
        for si, start in enumerate(registration["starts"]):
            rngs = make_rngs(76000, ti, si)
            before = copy.deepcopy(rngs["initialization"].bit_generator.state)
            if start == "cloned":
                masks = [case["certificate"]["center"]["mask"]] * 30
            else:
                masks = ["0" * 100] + ["".join("1" if v < 0.5 else "0"
                    for v in rngs["initialization"].random(100)) for _ in range(29)]
            cache = {mask: evaluate(problem, mask) for mask in sorted(set(masks))}
            scores = [cache[mask] for mask in masks]
            c.require(scores == [initial_independent_score(problem, mask) for mask in masks], "Initial score mismatch")
            bank = {"schema": "mutation-only-bank-v1", "protocol_id": c.PROTOCOL,
                "task": task, "task_index": ti, "start": start, "start_index": si,
                "preparation_seed": 76000, "problem": problem, "initial_masks": masks,
                "initial_scores": scores, "initialization_before": before,
                "initialization_after": copy.deepcopy(rngs["initialization"].bit_generator.state),
                "logical_initial_positions": 30, "physical_preparation_evaluations": len(cache),
                "independent_preparation_checks": 30, "source_path": source,
                "source_identity": c.identity(c.ROOT / source), "provenance": provenance}
            name = f"banks/{task}-{start}.json"
            c.write_json(output / name, bank)
            banks.append({"task": task, "start": start, "path": name, **c.identity(output / name)})
    c.require(len(banks) == 8, "Incomplete preparation")
    c.write_json(output / "bank_registry.json", {**provenance, "schema": "mutation-only-registry-v1",
        "banks": banks, "initial_conditions": 8, "pilot_search_seed": 76001,
        "physical_preparation_evaluations": sum(c.read_json(output / b["path"])["physical_preparation_evaluations"] for b in banks),
        "independent_preparation_checks": 240, "scientific_search_calls": 0})
    c.write_manifest(output)


def load_banks():
    root = c.MODULE / "inputs"
    registry = c.read_json(root / "bank_registry.json")
    c.require(registry.get("protocol_id") == c.PROTOCOL and
              registry.get("source_manifest") == c.source_manifest() and
              registry.get("schema") == "mutation-only-registry-v1" and
              registry.get("initial_conditions") == 8 and registry.get("pilot_search_seed") == 76001,
              "Wrong preparation identity")
    preparation = c.api(f"/actions/runs/{registry['run_id']}/attempts/{registry['run_attempt']}")
    c.require(preparation["status"] == "completed" and preparation["conclusion"] == "success" and
              preparation["path"] == c.WORKFLOW and preparation["head_branch"] == c.BRANCH and
              preparation["head_sha"] == registry["implementation_sha"] and
              c.phase(preparation["head_commit"]["message"]) == "prepare", "Unverified preparation run")
    registration = c.read_json(c.MODULE / "registration.json")
    expected = {(task, start) for task in registration["tasks"] for start in registration["starts"]}
    seen, result = set(), []
    for row in registry["banks"]:
        task, start = row["task"], row["start"]
        c.require((task, start) in expected - seen and row["path"] == f"banks/{task}-{start}.json", "Duplicate or unsafe bank")
        seen.add((task, start))
        path = root / row["path"]
        c.require(c.identity(path) == {"sha256": row["sha256"], "bytes": row["bytes"]}, "Corrupted bank")
        bank = c.read_json(path)
        ti, si = registration["tasks"].index(task), registration["starts"].index(start)
        problem, case, source = source_task(task)
        c.require(bank.get("protocol_id") == c.PROTOCOL and bank.get("schema") == "mutation-only-bank-v1" and
                  bank.get("task") == task and bank.get("start") == start and bank.get("preparation_seed") == 76000 and
                  bank.get("source_path") == source and
                  all(bank["provenance"].get(k) == registry.get(k) for k in
                      ("protocol_id", "implementation_sha", "run_id", "run_attempt", "source_manifest")) and
                  bank["problem"] == problem and bank["task_index"] == ti and bank["start_index"] == si and
                  bank["source_identity"] == c.identity(c.ROOT / source) and
                  len(bank["initial_masks"]) == len(bank["initial_scores"]) == 30, "Wrong bank identity")
        from .engine import make_rngs
        rng = make_rngs(76000, ti, si)["initialization"]
        replay = ([case["certificate"]["center"]["mask"]] * 30 if start == "cloned" else
                  ["0" * 100] + ["".join("1" if v < 0.5 else "0" for v in rng.random(100)) for _ in range(29)])
        c.require(bank["initial_masks"] == replay and bank["initial_scores"] ==
                  [initial_independent_score(problem, m) for m in replay], "Initial reconstruction mismatch")
        result.append(bank)
    c.require(seen == expected, "Missing initial condition")
    return result


def pilot(output):
    require_phase("pilot")
    provenance = c.authenticate(runtime=True)
    validated_tests()
    from .engine import make_rngs, run_search
    from .verifier import verify_log
    results = []
    for bank in load_banks():
        first = None
        for method in ("fixed", "adaptive_mutation"):
            log = run_search(bank["problem"], bank["initial_masks"], bank["initial_scores"], method,
                make_rngs(76001, bank["task_index"], bank["start_index"]), budget=5000)
            verification = verify_log(log)
            c.require(verification["verification_status"] == "VERIFIED", "Log replay failed")
            candidates = [row for row in log["candidates"] if row["generation"] == 1]
            if first is None:
                first = candidates
            else:
                c.require(first == candidates, "First paired generation differs")
            name = f"{bank['task']}-{bank['start']}-{method}"
            journal = output / "journals" / (name + ".json.gz")
            journal.parent.mkdir(parents=True, exist_ok=True)
            raw = c.canonical({"provenance": provenance, "task": bank["task"], "start": bank["start"],
                               "seed": 76001, "log": log, "verification": verification})
            journal.write_bytes(gzip.compress(raw, mtime=0))
            c.require(journal.stat().st_size <= 64*1024*1024, "Oversized journal")
            initial = max(s["profit"] for s in bank["initial_scores"] if s["feasible"])
            exits = [r["call"] for r in log["candidates"] if r["feasible"] and r["profit"] > initial]
            results.append({"task": bank["task"], "start": bank["start"], "method": method,
                "seed": 76001, "summary": log["summary"], "verification": verification,
                "initial_record": initial, "first_improvement_call": min(exits) if exits else None,
                "calls_to_improvement_capped": min(exits) if exits else 5000,
                "journal": journal.relative_to(output).as_posix(), "journal_identity": c.identity(journal)})
    c.require(len(results) == 16 and sum(r["summary"]["new_calls"] for r in results) == 80000, "Incomplete pilot")
    c.write_json(output / "pilot_summary.json", {**provenance, "status": "COMPLETE_TECHNICAL_PILOT",
        "runs": 16, "new_calls": 80000, "results": results, "technical_seed": 76001,
        "superiority_tested": False, "bootstrap_performed": False})
    draw_pilot(output)
    c.write_manifest(output)


def draw_pilot(output):
    """Only CI: transparent record and mutation plots; not a superiority chart."""
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(output / "Прості_графіки_мутації.pdf") as pdf:
        for start, label in (("cloned", "копії локального центра"), ("bank", "випадковий початок")):
            fig, axes = plt.subplots(2, 1, figsize=(10, 7), layout="constrained")
            for method, title in (("fixed", "стала мутація"), ("adaptive_mutation", "адаптивна мутація")):
                raw = c.json.loads(gzip.decompress((output / "journals" / f"UC-s000-{start}-{method}.json.gz").read_bytes()))
                log = raw["log"]
                axes[0].plot([r["call"] for r in log["candidates"]], [r["record_profit"] for r in log["candidates"]], label=title)
                axes[1].step([g["start_call"] for g in log["generations"]], [100*g["p_m"] for g in log["generations"]], where="post", label=title)
            axes[0].set_title(f"UC-s000, {label}: чи знайдено кращий набір?")
            axes[0].set_ylabel("Найкраща допустима цінність")
            axes[1].set_title("Коли змінювалася ймовірність мутації?")
            axes[1].set_ylabel("Мутація одного біта, %")
            for ax in axes:
                ax.set_xlabel("Нові оцінювання")
                ax.legend()
                ax.grid(alpha=0.25)
            fig.suptitle("Один технічний seed 76001; не доказ переваги")
            fig.savefig(output / f"UC-s000-{start}.png", dpi=160)
            pdf.savefig(fig)
            plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "tests", "prepare", "pilot"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase == "preflight":
        c.preflight(args.output)
    else:
        # Work must have a same-SHA preflight from this very job, not a copied permit.
        previous = c.read_json(args.output / "preflight.json")
        c.require(previous["implementation_sha"] == c.os.environ.get("GITHUB_SHA") and
                  previous["run_id"] == int(c.os.environ["GITHUB_RUN_ID"]) and
                  previous["run_attempt"] == int(c.os.environ.get("GITHUB_RUN_ATTEMPT", "1")) and
                  previous["phase"] == args.phase, "No matching phase preflight")
        {"tests": run_tests, "prepare": prepare, "pilot": pilot}[args.phase](args.output)


if __name__ == "__main__":
    main()

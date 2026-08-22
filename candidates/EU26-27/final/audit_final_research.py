from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT / "candidates" / "EU26-27"
FINAL = CANDIDATE / "final"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def seeds(path: Path) -> list[int]:
    rows = list(csv.DictReader(path.read_text().splitlines()))
    return [int(row["seed"]) for row in rows]


def assert_text(path: Path, required: tuple[str, ...], forbidden: tuple[str, ...] = ()) -> None:
    text = path.read_text()
    for token in required:
        require(token in text, f"{path}: missing required token {token!r}")
    for token in forbidden:
        require(token not in text, f"{path}: forbidden token present {token!r}")


def main() -> int:
    evidence = json.loads((FINAL / "FINAL_EVIDENCE.json").read_text())
    lock = json.loads((CANDIDATE / "source_native" / "UPSTREAM_LOCK.json").read_text())

    require(evidence["schema"] == "eu26-27-final-research-evidence-v1", "unexpected final evidence schema")
    require(lock["verified_result"]["decision"] == "PASS_SOURCE_NATIVE_OLD", "OLD lock is not PASS_SOURCE_NATIVE_OLD")
    require(lock["gsemo"]["commit"] == "fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380", "GSEMO SHA drift")
    require(lock["iohexperimenter"]["commit"] == "f223c682dff0749067d00b870f83ad754f7d96f5", "IOH SHA drift")
    require(lock["reference"]["published_mean_fe"] == 61624.0, "paper anchor drift")
    require(lock["reference"]["authenticated_raw_mean_fe"] == 61623.78, "raw mean drift")
    require(lock["verified_result"]["matrix_mismatches"] == 0, "OLD matrix is not exact")
    require(lock["verified_result"]["endpoint_mismatches"] == 0, "OLD endpoints are not exact")

    old = evidence["old"]
    require(old["status"] == "PASS_EXACT_REPRODUCTION", "final OLD status drift")
    require(old["complete_runs"] == 100, "OLD run-count drift")
    require(old["matrix_shape"] == [101, 100], "OLD matrix-shape drift")
    require(old["matrix_mismatches"] == 0 and old["endpoint_mismatches"] == 0, "OLD exact evidence drift")
    require(old["source_mean_fe"] == old["authenticated_mean_fe"] == 61623.78, "OLD mean mismatch")
    require(old["maximum_endpoint_fe"] == 131875, "OLD endpoint maximum drift")

    v1 = seeds(CANDIDATE / "hybrid" / "seeds.csv")
    v2 = seeds(CANDIDATE / "hybrid_v2" / "seeds.csv")
    v3 = seeds(CANDIDATE / "hybrid_v3" / "holdout_seeds.csv")
    require(v1 == list(range(27001, 27031)), "v1 seed ledger drift")
    require(v2 == list(range(28001, 28031)), "v2 seed ledger drift")
    require(v3 == list(range(29001, 29031)), "v3 seed ledger drift")
    require(set(v1).isdisjoint(v2) and set(v1).isdisjoint(v3) and set(v2).isdisjoint(v3), "confirmatory seed overlap")

    require(evidence["hybrid_v1"]["status"] == "FAIL", "v1 verdict was relabeled")
    require(evidence["hybrid_v2"]["status"] == "FAIL", "v2 verdict was relabeled")
    require(evidence["hybrid_v3"]["status"] == "FAIL", "v3 verdict was relabeled")
    require(evidence["hybrid_v3"]["selected_cap"] == 20, "v3 selected-cap drift")
    require(evidence["seed_policy"]["future_confirmatory_reuse_forbidden"] is True, "seed retirement policy removed")

    assert_text(
        CANDIDATE / "hybrid" / "RESULTS.md",
        ("H1: FAIL", "H2: NO_CLEAR_EFFECT", "32571460043", "9475506328"),
    )
    assert_text(
        CANDIDATE / "hybrid_v2" / "RESULTS.md",
        ("H1: FAIL", "H2: NO_CLEAR_EFFECT", "32572161500", "9475683444"),
    )
    assert_text(
        CANDIDATE / "hybrid_v3" / "RESULTS.md",
        ("T3_H1_FAIL", "H1: FAIL", "32573546704", "9476099058"),
    )

    v3_test = (CANDIDATE / "hybrid_v3" / "test_hybrid_v3.py").read_text()
    require("import analyze_holdout as holdout" in v3_test, "v3 tests do not exercise the real holdout analyzer")
    require("import select_cap as selector" in v3_test, "v3 tests do not exercise the real selector")
    require("patcher.patch_gsemo" in v3_test, "v3 tests lack wrong-preimage fail-closed coverage")

    v3_patch = (CANDIDATE / "hybrid_v3" / "patch_upstream.py").read_text()
    for token in ("CAPS = (15, 20, 30, 40, 60, 100)", "HybridCapped", "lambda_floor = 10.0", "update_factor = 1.5"):
        require(token in v3_patch, f"v3 implementation drift: {token}")
    require("TwoRate<SolutionType>::adapt(pareto_front, new_population);" in v3_patch, "TwoRate mutation adaptation no longer preserved")

    workflow_dir = ROOT / ".github" / "workflows"
    relevant = sorted(workflow_dir.glob("eu26-27-*.yml"))
    require(relevant, "no EU26-27 workflows found")
    unpinned = []
    for workflow in relevant:
        for line in workflow.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("uses:"):
                value = stripped.split("uses:", 1)[1].strip()
                if not re.search(r"@[0-9a-f]{40}$", value):
                    unpinned.append(f"{workflow.name}: {value}")
    require(not unpinned, "unpinned GitHub Action uses: " + "; ".join(unpinned))

    report = {
        "decision": "PASS_FINAL_RESEARCH_INTEGRITY_AUDIT",
        "old": "PASS_EXACT_REPRODUCTION",
        "hybrid_v1": "FAIL",
        "hybrid_v2": "FAIL",
        "hybrid_v3": "FAIL",
        "seed_ledgers": {"v1": v1, "v2": v2, "v3": v3},
        "workflows_checked": [p.name for p in relevant],
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

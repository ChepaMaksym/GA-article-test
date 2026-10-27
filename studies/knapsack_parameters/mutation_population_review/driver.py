"""Explicit authority -> fixtures -> historical replay -> descriptive figures."""
import argparse
from pathlib import Path
import tempfile
import time
import unittest

from . import authority as a


def run(permit, output):
    receipt, grant = a.validate_permit(permit)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    suite = unittest.defaultTestLoader.discover(str(a.MODULE / "tests"), top_level_dir=str(a.ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    a.write(output / "tests.json", {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                                  "success": result.wasSuccessful(), "fixtures_only": True})
    a.require(result.wasSuccessful(), "secondary review fixtures failed")
    from .review import execute
    from .plots import render
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "source-worker.zip"
        artifact = a.download_archive(archive)
        summary, examples = execute(archive, output)
    rendering = render(summary, examples, output / "figures")
    a.write(output / "rendering_receipt.json", rendering)
    a.write(output / "audit_status.json", {**receipt, "status": "COMPLETE_VERIFIED_SECONDARY_REVIEW",
        "reviewed_compact_runs": 3600, "replayed_raw_journals": 4, "new_search_runs": 0, "new_search_evaluations": 0,
        "descriptive_only": True, "historical_primary_analysis_modified": False, "artifact": artifact,
        "permit": grant, "duration_seconds": time.perf_counter() - started})
    write_report(summary, rendering, output)
    manifest = [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": a.sha(p.read_bytes())}
                for p in sorted(output.rglob("*")) if p.is_file()]
    a.write(output / "file_manifest.json", {"schema": "mutation-population-review-files-v1", "files": manifest})
    print("COMPLETE_VERIFIED_SECONDARY_REVIEW: 3600 saved endpoints, 4 replayed journals, 0 new GA runs")


def write_report(summary, rendering, output):
    lines = ["# Мутація та популяція: вторинний описовий аналіз", "",
        "Новий пошук ГА не виконувався. Перераховано 3600 збережених результатів, незалежно відновлено чотири журнали прикладу.",
        "Результати були переглянуті до постановки цього доповнення. Нових первинних перевірок переваги немає.", "",
        "| Варіант | Відставання, % | Досягли 95% | Досягли 99% |", "|---|---:|---:|---:|"]
    for c in summary["cells"]:
        gap = f"{c['mean_final_gap_percent']:.4f}".replace(".", ",")
        lines.append(f"| {c['name']} | {gap} | {c['targets']['95']['attained']}/900 | {c['targets']['99']['attained']}/900 |")
    lines.extend(["", "Спільна адаптація описово краща за адаптацію лише мутації. Сталий контроль має найменше середнє відставання серед чотирьох варіантів.",
        "Окремий приклад не замінює підсумків усіх запусків. Висновок обмежений заданими правилами, задачами й бюджетом.", ""])
    for fig in rendering["figures"]:
        lines.extend([f"![{fig['caption']}](figures/{fig['file']})", ""])
    (output / "REPORT_UK.md").write_text("\n".join(lines), encoding="utf-8")


def render_saved(permit, output):
    receipt, grant = a.validate_permit(permit)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    suite = unittest.defaultTestLoader.discover(str(a.MODULE / "tests"), top_level_dir=str(a.ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    a.write(output / "tests.json", {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                                  "success": result.wasSuccessful(), "fixtures_only": True})
    a.require(result.wasSuccessful(), "figure revision fixtures failed")
    source = a.MODULE / "evidence/review-40478517966-1"
    raw = (source / "review_summary.json").read_bytes()
    a.require(a.sha(raw) == "525e6c6489f929dadf12d2fb4d81d257d2a2b22305c3b66ef20ec565c0814dab", "saved values changed")
    a.require(a.sha((source / "file_manifest.json").read_bytes()) ==
              "07ba3a0b25c1cd7895c8ad1198c012de032e196d3425ffc80612c7bc5c6afc0e", "saved evidence manifest changed")
    import json
    summary = json.loads(raw)
    from .plots import render_quality
    rendering = render_quality(summary, output / "figures")
    a.write(output / "rendering_receipt.json", rendering)
    a.write(output / "audit_status.json", {**receipt, "status": "COMPLETE_VERIFIED_FIGURE_REVISION",
        "source_run_id": 40478517966, "source_summary_sha256": a.sha(raw), "source_saved_runs": 3600,
        "data_values_changed": False, "new_search_runs": 0, "new_search_evaluations": 0,
        "new_statistical_analysis": False, "journals_replayed_again": 0, "permit": grant})
    manifest = [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": a.sha(p.read_bytes())}
                for p in sorted(output.rglob("*")) if p.is_file()]
    a.write(output / "file_manifest.json", {"schema": "mutation-population-figure-files-v1", "files": manifest})
    print("COMPLETE_VERIFIED_FIGURE_REVISION: saved values unchanged, zero new search/analysis")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "review", "render-saved", "target93"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--permit")
    args = parser.parse_args()
    if args.phase == "preflight":
        a.preflight(args.output)
    else:
        a.require(bool(args.permit), "missing exact-source permit")
        {"render-saved": render_saved, "review": run, "target93": target93}[args.phase](args.permit, args.output)


def target93(permit, output):
    receipt, grant = a.validate_permit(permit)
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    suite=unittest.defaultTestLoader.discover(str(a.MODULE/"tests"),top_level_dir=str(a.ROOT))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    a.write(output/"tests.json",{"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"success":result.wasSuccessful()})
    a.require(result.wasSuccessful(),"target93 fixtures failed")
    from .targets93 import execute, render
    summary=execute(output)
    rendering=render(summary,output/"figures")
    a.write(output/"rendering_receipt.json",rendering)
    a.write(output/"audit_status.json",{**receipt,"status":"COMPLETE_VERIFIED_TARGET93_REVIEW","post_hoc_descriptive":True,
        "reviewed_saved_runs":3600,"new_search_runs":0,"new_search_evaluations":0,"new_primary_tests":0,"permit":grant})
    manifest=[{"path":p.relative_to(output).as_posix(),"bytes":p.stat().st_size,"sha256":a.sha(p.read_bytes())}
              for p in sorted(output.rglob("*")) if p.is_file()]
    a.write(output/"file_manifest.json",{"schema":"mutation-population-target93-files-v1","files":manifest})
    print("COMPLETE_VERIFIED_TARGET93_REVIEW: 3600 saved runs; 95/99 endpoints preserved; zero new GA search")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ZENODO_RECORD = 7880836
REFERENCE_MEMBER = "csv/om/TwoRateL10P1HVOneMaxD100.csv"
PUBLISHED_MEAN_FE = 61618.0
PUBLISHED_MEAN_TOL = 1.0
DIMENSION = 100
RUNS = 100


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "EU26-27-source-native-old/1.0"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url: str, destination: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "EU26-27-source-native-old/1.0"})
    with urllib.request.urlopen(req, timeout=120) as response, destination.open("wb") as out:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            out.write(block)


def download_reference(work: Path) -> tuple[Path, str]:
    record = fetch_json(f"https://zenodo.org/api/records/{ZENODO_RECORD}")
    if int(record.get("id", -1)) != ZENODO_RECORD:
        raise RuntimeError("Zenodo record identity mismatch")
    csv_item = None
    for item in record.get("files", []):
        if item.get("key") == "csv.zip":
            csv_item = item
            break
    if csv_item is None:
        raise RuntimeError("Zenodo csv.zip is absent")
    url = (csv_item.get("links") or {}).get("content") or (csv_item.get("links") or {}).get("download")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise RuntimeError("Zenodo csv.zip has no HTTPS download URL")
    archive = work / "zenodo-csv.zip"
    download(url, archive)
    expected_size = int(csv_item["size"])
    if archive.stat().st_size != expected_size:
        raise RuntimeError("Zenodo csv.zip size mismatch")
    checksum = csv_item.get("checksum")
    if isinstance(checksum, str) and checksum.startswith("md5:"):
        md5 = hashlib.md5(usedforsecurity=False)
        with archive.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                md5.update(chunk)
        if md5.hexdigest() != checksum.split(":", 1)[1].lower():
            raise RuntimeError("Zenodo csv.zip MD5 mismatch")
    return archive, sha256_file(archive)


def read_reference(archive: Path) -> tuple[list[list[int]], list[int], str]:
    with zipfile.ZipFile(archive) as zf:
        if REFERENCE_MEMBER not in zf.namelist():
            raise RuntimeError(f"reference member absent: {REFERENCE_MEMBER}")
        payload = zf.read(REFERENCE_MEMBER)
    rows = list(csv.DictReader(payload.decode("utf-8-sig").splitlines()))
    if len(rows) != DIMENSION + 1:
        raise RuntimeError(f"reference front row count {len(rows)} != {DIMENSION + 1}")
    matrix: list[list[int]] = [[-1 for _ in range(RUNS)] for _ in range(DIMENSION + 1)]
    for point_index, row in enumerate(rows):
        for run in range(RUNS):
            key = f"First_hit{run}"
            if key not in row:
                raise RuntimeError(f"reference column missing: {key}")
            matrix[point_index][run] = int(float(row[key]))
    endpoints = []
    for run in range(RUNS):
        values = [matrix[i][run] for i in range(DIMENSION + 1)]
        if any(value < 0 for value in values):
            raise RuntimeError(f"reference run {run} is incomplete")
        endpoints.append(max(values))
    return matrix, endpoints, sha256_bytes(payload)


def locate_ioh_scenario(root: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    candidates = sorted(root.rglob("*.json"))
    matched: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    for path in candidates:
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        algorithm = (meta.get("algorithm") or {}).get("name") or ""
        function_name = meta.get("function_name") or ""
        for scenario in meta.get("scenarios", []):
            if int(scenario.get("dimension", -1)) != DIMENSION:
                continue
            text = f"{algorithm} {function_name} {path}".lower()
            if "tworate" in text and ("onemax" in text or "oneminmax" in text):
                matched.append((path, meta, scenario))
    if len(matched) != 1:
        summary = [str(item[0]) for item in matched]
        raise RuntimeError(f"expected exactly one TwoRate/OneMinMax scenario, found {len(matched)}: {summary}")
    return matched[0]


def parse_author_runs(root: Path) -> tuple[list[list[tuple[int, int, int]]], dict[str, Any]]:
    json_path, meta, scenario = locate_ioh_scenario(root)
    data_path = json_path.parent / scenario["path"]
    if not data_path.is_file():
        raise RuntimeError(f"IOH data file missing: {data_path}")
    runs: list[list[tuple[int, int, int]]] = []
    current: list[tuple[int, int, int]] | None = None
    with data_path.open(encoding="utf-8") as stream:
        for raw in stream:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("evaluations"):
                if current is not None:
                    runs.append(current)
                current = []
                continue
            if current is None:
                continue
            fields = line.split()
            if len(fields) < 3:
                continue
            try:
                evaluation = int(float(fields[0]))
                x = int(float(fields[1]))
                y = int(float(fields[2]))
            except ValueError:
                continue
            current.append((evaluation, x, y))
    if current is not None:
        runs.append(current)
    if len(runs) != RUNS:
        raise RuntimeError(f"author source produced {len(runs)} runs, expected {RUNS}")
    info = {
        "json_path": str(json_path.relative_to(root)),
        "data_path": str(data_path.relative_to(root)),
        "algorithm_name": (meta.get("algorithm") or {}).get("name"),
        "function_name": meta.get("function_name"),
        "scenario_dimension": scenario.get("dimension"),
        "data_sha256": sha256_file(data_path),
    }
    return runs, info


def source_first_hits(runs: list[list[tuple[int, int, int]]]) -> tuple[list[list[int]], list[int]]:
    matrix: list[list[int]] = [[-1 for _ in range(RUNS)] for _ in range(DIMENSION + 1)]
    expected = {(i, DIMENSION - i): i for i in range(DIMENSION + 1)}
    for run_index, events in enumerate(runs):
        seen: set[int] = set()
        for evaluation, x, y in events:
            point = expected.get((x, y))
            if point is None or point in seen:
                continue
            matrix[point][run_index] = evaluation
            seen.add(point)
        if len(seen) != DIMENSION + 1:
            missing = (DIMENSION + 1) - len(seen)
            raise RuntimeError(f"author run {run_index} incomplete: {missing} Pareto points missing")
    endpoints = [max(matrix[p][r] for p in range(DIMENSION + 1)) for r in range(RUNS)]
    return matrix, endpoints


def matrix_diff(a: list[list[int]], b: list[list[int]]) -> dict[str, Any]:
    mismatches = []
    max_abs = 0
    for point in range(DIMENSION + 1):
        for run in range(RUNS):
            av = a[point][run]
            bv = b[point][run]
            if av != bv:
                max_abs = max(max_abs, abs(av - bv))
                if len(mismatches) < 25:
                    mismatches.append({"point_index": point, "run": run, "source": av, "reference": bv})
    count = sum(1 for point in range(DIMENSION + 1) for run in range(RUNS) if a[point][run] != b[point][run])
    return {"mismatch_count": count, "max_abs_difference": max_abs, "examples": mismatches}


def ecdf_points(values: list[int]) -> list[tuple[float, float]]:
    ordered = sorted(values)
    n = len(ordered)
    return [(float(value), (index + 1) / n) for index, value in enumerate(ordered)]


def svg_polyline(points: list[tuple[float, float]], x0: float, y0: float, width: float, height: float,
                 xmin: float, xmax: float, ymin: float, ymax: float) -> str:
    if xmax <= xmin:
        xmax = xmin + 1
    if ymax <= ymin:
        ymax = ymin + 1
    coords = []
    for x, y in points:
        sx = x0 + (x - xmin) / (xmax - xmin) * width
        sy = y0 + height - (y - ymin) / (ymax - ymin) * height
        coords.append(f"{sx:.2f},{sy:.2f}")
    return " ".join(coords)


def write_ecdf_svg(path: Path, reference: list[int], source: list[int]) -> None:
    width, height = 900, 560
    margin = 70
    xmin = float(min(reference + source))
    xmax = float(max(reference + source))
    ref = svg_polyline(ecdf_points(reference), margin, margin, width - 2 * margin, height - 2 * margin, xmin, xmax, 0.0, 1.0)
    src = svg_polyline(ecdf_points(source), margin, margin, width - 2 * margin, height - 2 * margin, xmin, xmax, 0.0, 1.0)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/>
<text x="{width/2}" y="32" text-anchor="middle" font-family="sans-serif" font-size="20">EU26-27 source-native OLD endpoint ECDF</text>
<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="black"/>
<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="black"/>
<polyline fill="none" stroke="#1f77b4" stroke-width="3" points="{ref}"/>
<polyline fill="none" stroke="#d62728" stroke-width="2" stroke-dasharray="8,5" points="{src}"/>
<text x="{width-270}" y="70" font-family="sans-serif" font-size="15" fill="#1f77b4">Zenodo reference</text>
<text x="{width-270}" y="94" font-family="sans-serif" font-size="15" fill="#d62728">Source-native replay</text>
<text x="{width/2}" y="{height-18}" text-anchor="middle" font-family="sans-serif" font-size="15">Function evaluations to complete Pareto front</text>
<text x="18" y="{height/2}" transform="rotate(-90 18 {height/2})" text-anchor="middle" font-family="sans-serif" font-size="15">ECDF</text>
</svg>'''
    path.write_text(svg, encoding="utf-8")


def write_run_scatter_svg(path: Path, reference: list[int], source: list[int]) -> None:
    width, height = 700, 650
    margin = 70
    values = reference + source
    lo, hi = float(min(values)), float(max(values))
    span = max(1.0, hi - lo)
    lo -= 0.03 * span
    hi += 0.03 * span
    def xy(x: float, y: float) -> tuple[float, float]:
        sx = margin + (x - lo) / (hi - lo) * (width - 2 * margin)
        sy = margin + (hi - y) / (hi - lo) * (height - 2 * margin)
        return sx, sy
    x1, y1 = xy(lo, lo)
    x2, y2 = xy(hi, hi)
    circles = []
    for r, s in zip(reference, source):
        x, y = xy(float(r), float(s))
        circles.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="#1f77b4" fill-opacity="0.65"/>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/>
<text x="{width/2}" y="32" text-anchor="middle" font-family="sans-serif" font-size="20">Run-by-run source-native replay</text>
<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="black"/>
<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="black"/>
<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#d62728" stroke-dasharray="7,5"/>
{''.join(circles)}
<text x="{width/2}" y="{height-18}" text-anchor="middle" font-family="sans-serif" font-size="15">Zenodo endpoint FE</text>
<text x="18" y="{height/2}" transform="rotate(-90 18 {height/2})" text-anchor="middle" font-family="sans-serif" font-size="15">Source-native endpoint FE</text>
</svg>'''
    path.write_text(svg, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--author-output-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gsemo-sha", required=True)
    parser.add_argument("--ioh-sha", required=True)
    parser.add_argument("--runner-os", default=os.environ.get("RUNNER_OS", "unknown"))
    args = parser.parse_args()

    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = output / "work"
    work.mkdir(exist_ok=True)

    archive, archive_sha = download_reference(work)
    reference_matrix, reference_endpoints, reference_member_sha = read_reference(archive)
    source_runs, source_info = parse_author_runs(Path(args.author_output_root).resolve())
    source_matrix, source_endpoints = source_first_hits(source_runs)

    diff = matrix_diff(source_matrix, reference_matrix)
    endpoint_mismatches = [
        {"run": i, "source": s, "reference": r, "difference": s - r}
        for i, (s, r) in enumerate(zip(source_endpoints, reference_endpoints)) if s != r
    ]
    reference_mean = statistics.fmean(reference_endpoints)
    source_mean = statistics.fmean(source_endpoints)
    reference_median = statistics.median(reference_endpoints)
    source_median = statistics.median(source_endpoints)
    paper_raw_ok = abs(reference_mean - PUBLISHED_MEAN_FE) <= PUBLISHED_MEAN_TOL
    exact_matrix = diff["mismatch_count"] == 0
    exact_endpoints = not endpoint_mismatches
    decision = "PASS_SOURCE_NATIVE_OLD" if exact_matrix and exact_endpoints and paper_raw_ok else "FAIL_SOURCE_NATIVE_OLD"

    write_ecdf_svg(output / "endpoint_ecdf.svg", reference_endpoints, source_endpoints)
    write_run_scatter_svg(output / "run_by_run.svg", reference_endpoints, source_endpoints)

    report = {
        "schema": "eu26-27-source-native-old-report-v1",
        "decision": decision,
        "research_tag": "RESEARCH_2",
        "old_implementation": "FurongYe/GSEMO exact paper-era source",
        "gsemo_sha": args.gsemo_sha,
        "iohexperimenter_sha": args.ioh_sha,
        "runner_os": args.runner_os,
        "reference": {
            "zenodo_record": ZENODO_RECORD,
            "member": REFERENCE_MEMBER,
            "archive_sha256": archive_sha,
            "member_sha256": reference_member_sha,
            "runs": len(reference_endpoints),
            "mean_fe": reference_mean,
            "median_fe": reference_median,
            "published_mean_fe": PUBLISHED_MEAN_FE,
            "published_mean_tolerance": PUBLISHED_MEAN_TOL,
            "published_raw_alignment": paper_raw_ok,
        },
        "source_native": {
            "runs": len(source_endpoints),
            "mean_fe": source_mean,
            "median_fe": source_median,
            **source_info,
        },
        "exact_first_hit_matrix_match": exact_matrix,
        "first_hit_matrix_diff": diff,
        "exact_endpoint_vector_match": exact_endpoints,
        "endpoint_mismatch_count": len(endpoint_mismatches),
        "endpoint_mismatch_examples": endpoint_mismatches[:25],
        "claim_boundary": {
            "hybrid_authorized": decision == "PASS_SOURCE_NATIVE_OLD",
            "wall_clock_claim": false if False else False,
            "worker_parallelism_claim": False,
            "note": "Author OLD is a sequential global-RNG batch; parallel-worker equivalence is not claimed because parallelizing it changes the historical random stream."
        }
    }
    # Python has no lowercase JSON booleans in source; normalize the one field explicitly.
    report["claim_boundary"]["wall_clock_claim"] = False

    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "report.json": sha256_file(report_path),
        "endpoint_ecdf.svg": sha256_file(output / "endpoint_ecdf.svg"),
        "run_by_run.svg": sha256_file(output / "run_by_run.svg"),
    }
    (output / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = [
        "# EU26-27 source-native OLD", "", "```text",
        f"decision: {decision}",
        f"reference mean FE: {reference_mean:.6f}",
        f"source mean FE: {source_mean:.6f}",
        f"reference median FE: {reference_median:.6f}",
        f"source median FE: {source_median:.6f}",
        f"exact first-hit matrix: {exact_matrix}",
        f"exact endpoint vector: {exact_endpoints}",
        f"published 61618 alignment: {paper_raw_ok}",
        "```", "",
        "HYBRID is authorized only when the decision is PASS_SOURCE_NATIVE_OLD.",
    ]
    (output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0 if decision == "PASS_SOURCE_NATIVE_OLD" else 2


if __name__ == "__main__":
    raise SystemExit(main())

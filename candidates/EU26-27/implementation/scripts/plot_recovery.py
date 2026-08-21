from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

SERIES = [
    ("raw", "Raw Zenodo"),
    ("R1_uniform_balanced", "R1 uniform + 5/5"),
    ("R2_first_balanced", "R2 first + 5/5"),
    ("R3_uniform_literal", "R3 uniform + 4/6"),
    ("R4_first_literal", "R4 first + 4/6"),
]
PALETTE = ["#111827", "#dc2626", "#2563eb", "#d97706", "#059669"]


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_frame(title: str, body: str, width: int = 960, height: int = 600) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/>
<text x="48" y="42" font-family="sans-serif" font-size="22" font-weight="700">{esc(title)}</text>
{body}
</svg>\n'''


def write_ecdf(report: dict, path: Path) -> None:
    data = {"raw": report["raw"]["endpoints"]}
    for key, _label in SERIES[1:]:
        data[key] = report["variants"][key]["endpoints"]
    all_values = np.asarray([v for values in data.values() for v in values], dtype=float)
    xmin, xmax = float(np.min(all_values)), float(np.max(all_values))
    if xmax <= xmin:
        xmax = xmin + 1.0
    left, top, right, bottom = 80, 72, 910, 520
    w, h = right - left, bottom - top

    def xcoord(value: float) -> float:
        return left + (value - xmin) / (xmax - xmin) * w

    def ycoord(value: float) -> float:
        return bottom - value * h

    pieces = [
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#374151"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#374151"/>',
    ]
    for tick in range(6):
        y = tick / 5
        yy = ycoord(y)
        pieces.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="#e5e7eb"/>')
        pieces.append(f'<text x="{left-12}" y="{yy+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{y:.1f}</text>')
    for tick in range(6):
        value = xmin + tick / 5 * (xmax - xmin)
        xx = xcoord(value)
        pieces.append(f'<text x="{xx:.1f}" y="{bottom+22}" text-anchor="middle" font-family="sans-serif" font-size="12">{value/1000:.0f}k</text>')
    pieces.append(f'<text x="{(left+right)/2}" y="{bottom+48}" text-anchor="middle" font-family="sans-serif" font-size="14">Function evaluations to complete Pareto front</text>')
    pieces.append(f'<text x="24" y="{(top+bottom)/2}" text-anchor="middle" transform="rotate(-90 24 {(top+bottom)/2})" font-family="sans-serif" font-size="14">ECDF</text>')

    for idx, (key, label) in enumerate(SERIES):
        values = np.sort(np.asarray(data[key], dtype=float))
        points = []
        for j, value in enumerate(values, start=1):
            points.append(f"{xcoord(float(value)):.2f},{ycoord(j/len(values)):.2f}")
        pieces.append(f'<polyline fill="none" stroke="{PALETTE[idx]}" stroke-width="2.5" points="{" ".join(points)}"/>')
        lx, ly = 650, 92 + idx * 24
        pieces.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+28}" y2="{ly}" stroke="{PALETTE[idx]}" stroke-width="3"/>')
        pieces.append(f'<text x="{lx+36}" y="{ly+4}" font-family="sans-serif" font-size="12">{esc(label)}</text>')

    path.write_text(svg_frame("EU26-27 recovery: FE distribution", "\n".join(pieces)), encoding="utf-8")


def write_ratio(report: dict, path: Path) -> None:
    keys = [item[0] for item in SERIES[1:]]
    left, top, right, bottom = 100, 80, 900, 500
    ymin = 0.0
    ymax = max(2.6, max(report["variants"][key]["compatibility"]["median_ratio_ci95"][1] for key in keys) * 1.1)

    def ycoord(value: float) -> float:
        return bottom - (value - ymin) / (ymax - ymin) * (bottom - top)

    pieces = [
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#374151"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#374151"/>',
    ]
    for value, dash, color in [(0.9, "5,5", "#9ca3af"), (1.0, "", "#111827"), (1.1, "5,5", "#9ca3af")]:
        yy = ycoord(value)
        pieces.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="{color}" stroke-dasharray="{dash}"/>')
    for tick in np.linspace(0, ymax, 7):
        yy = ycoord(float(tick))
        pieces.append(f'<text x="{left-12}" y="{yy+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{tick:.2f}</text>')

    spacing = (right - left) / len(keys)
    for idx, key in enumerate(keys):
        info = report["variants"][key]["compatibility"]
        x = left + spacing * (idx + 0.5)
        low, high = info["median_ratio_ci95"]
        med = info["median_ratio"]
        pieces.append(f'<line x1="{x:.1f}" y1="{ycoord(low):.1f}" x2="{x:.1f}" y2="{ycoord(high):.1f}" stroke="{PALETTE[idx+1]}" stroke-width="4"/>')
        pieces.append(f'<circle cx="{x:.1f}" cy="{ycoord(med):.1f}" r="7" fill="{PALETTE[idx+1]}"/>')
        label = SERIES[idx+1][1]
        pieces.append(f'<text x="{x:.1f}" y="{bottom+26}" text-anchor="middle" font-family="sans-serif" font-size="12">{esc(label)}</text>')
    pieces.append(f'<text x="30" y="{(top+bottom)/2}" text-anchor="middle" transform="rotate(-90 30 {(top+bottom)/2})" font-family="sans-serif" font-size="14">Independent / raw median FE ratio</text>')
    path.write_text(svg_frame("Median-ratio diagnostic with frozen 95% intervals", "\n".join(pieces)), encoding="utf-8")


def write_final_rate(report: dict, path: Path) -> None:
    keys = [item[0] for item in SERIES[1:]]
    left, top, right, bottom = 100, 80, 900, 500
    ymax = max(25.0, max(max(report["variants"][key]["final_rates"]) for key in keys))

    def ycoord(value: float) -> float:
        return bottom - value / ymax * (bottom - top)

    pieces = [
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#374151"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#374151"/>',
    ]
    spacing = (right - left) / len(keys)
    for idx, key in enumerate(keys):
        values = np.asarray(report["variants"][key]["final_rates"], dtype=float)
        q1, med, q3 = np.quantile(values, [0.25, 0.5, 0.75])
        lo, hi = float(np.min(values)), float(np.max(values))
        x = left + spacing * (idx + 0.5)
        pieces.append(f'<line x1="{x:.1f}" y1="{ycoord(lo):.1f}" x2="{x:.1f}" y2="{ycoord(hi):.1f}" stroke="{PALETTE[idx+1]}" stroke-width="2"/>')
        pieces.append(f'<rect x="{x-28:.1f}" y="{ycoord(q3):.1f}" width="56" height="{max(2.0,ycoord(q1)-ycoord(q3)):.1f}" fill="none" stroke="{PALETTE[idx+1]}" stroke-width="3"/>')
        pieces.append(f'<line x1="{x-28:.1f}" y1="{ycoord(med):.1f}" x2="{x+28:.1f}" y2="{ycoord(med):.1f}" stroke="{PALETTE[idx+1]}" stroke-width="3"/>')
        pieces.append(f'<text x="{x:.1f}" y="{bottom+26}" text-anchor="middle" font-family="sans-serif" font-size="12">{esc(SERIES[idx+1][1])}</text>')
    pieces.append(f'<text x="30" y="{(top+bottom)/2}" text-anchor="middle" transform="rotate(-90 30 {(top+bottom)/2})" font-family="sans-serif" font-size="14">Final mutation strength r</text>')
    path.write_text(svg_frame("Final adaptive mutation-strength distribution", "\n".join(pieces)), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--commit", default="unknown")
    args = parser.parse_args()
    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_ecdf(report, out / "recovery_fe_ecdf.svg")
    write_ratio(report, out / "recovery_median_ratio.svg")
    write_final_rate(report, out / "recovery_final_rate.svg")
    manifest = {
        "schema": "eu26-27-recovery-figures-v1",
        "research_tag": "RESEARCH_2",
        "commit": args.commit,
        "source_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "figures": {},
    }
    for path in sorted(out.glob("*.svg")):
        manifest["figures"][path.name] = {
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

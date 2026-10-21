"""Correct an annotation ambiguity without recalculating scientific results."""
from pathlib import Path
import tempfile

from . import contract as c


def annotation_series(summary):
    result = []
    for subset, label, color, offset in (
        ("all_stagnant", "Усі випадки застою", "#32678e", -17),
        ("stagnant_with_improvement", "Застій із кращим сусідом", "#d07b27", 9),
    ):
        series = summary["availability"][subset]["detection"]
        c.require([item["sample_size"] for item in series] == [50, 100, 250] and
                  all(type(item["value"]) in (int, float) and 0 <= item["value"] <= 1 for item in series),
                  "Missing completed detection values")
        result.append({"subset": subset, "label": label, "color": color, "offset": offset,
                       "x": [item["sample_size"] for item in series],
                       "y": [100 * item["value"] for item in series]})
    c.require(all(a <= b for a, b in zip(result[0]["y"], result[1]["y"])), "Conditional detection must not be lower")
    return result


def render_presentation(output, permit):
    provenance = c.check_permit(permit, "present")
    registration = c.read_json(c.MODULE / "presentation_amendment.json")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    metadata = c.api(f"/actions/artifacts/{registration['source_artifact_id']}")
    c.require(metadata.get("name") == registration["source_artifact_name"] and
              metadata.get("workflow_run", {}).get("id") == registration["source_run_id"] and
              metadata.get("workflow_run", {}).get("head_sha") == registration["source_implementation_commit_sha"] and
              metadata.get("digest") == "sha256:" + registration["source_zip_sha256"], "Foreign completed summary")
    with tempfile.TemporaryDirectory(prefix="completed-presentation-source-") as temporary:
        source = Path(temporary) / "source"
        transport = c.base.old._download_zip(metadata, source)
        c.require(transport["file_manifest_sha256"] == registration["source_file_manifest_sha256"], "Source manifest changed")
        summary = c.read_json(source / "secondary_summary.json")
        c.require(summary["status"] == "COMPLETE_EXPLORATORY" and summary["counts"] ==
                  {"runs": 900, "stagnant": 210, "stagnant_with_improvement": 202}, "Source analysis incomplete")
        series = annotation_series(summary)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
        figure, axis = plt.subplots(figsize=(8.4, 4.8), layout="constrained")
        for row in series:
            axis.plot(row["x"], row["y"], marker="o", color=row["color"], label=row["label"])
            for x, y in zip(row["x"], row["y"]):
                axis.annotate(f"{y:.2f}", (x, y), xytext=(0, row["offset"]),
                              textcoords="offset points", ha="center", fontsize=9, color=row["color"])
        axis.set_xlabel("Перевірені різні сусіди, кількість")
        axis.set_ylabel("Імовірність виявити покращення, %")
        axis.set_xticks([50, 100, 250])
        axis.set_ylim(0, 105)
        axis.grid(axis="y", alpha=.25)
        axis.legend(frameon=False)
        figure.savefig(output / "sampling_detection.png", dpi=180)
        plt.close(figure)
        c.write_json(output / "presentation_receipt.json", {**provenance,
            "source_artifact": registration, "transport": transport,
            "source_summary": c.identity(source / "secondary_summary.json"),
            "original_figure": c.identity(source / "sampling_detection.png"),
            "corrected_figure": c.identity(output / "sampling_detection.png"),
            "series": series, "change": "Annotation positions and colors only; data coordinates unchanged",
            "new_search_performed": False, "statistics_recomputed": False})
    c.write_manifest(output)
    c.verify_manifest(output)
    c.require(c.payload_bytes(output) <= c.CAPS["summary"], "Presentation cap exceeded")

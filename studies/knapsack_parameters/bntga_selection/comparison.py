"""Evaluator-free journals for the preregistered B-NTGA operator study.

These functions consume externally supplied objective vectors.  They do not
create offspring, evaluate fitness, run a GA, or estimate algorithm quality.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .operator import freeze_selection, select_pair, update_archive


def _fields(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} must contain exactly {sorted(expected)!r}")


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list or tuple")
    return deepcopy(list(value))


def build_journal(
    initial_points: Any, blocks: Any, balanced: bool
) -> dict[str, Any]:
    """Apply explicit selection requests and externally supplied archive updates.

    ``initial_points`` are new points: their supplied counters are validated by
    the operator but reset to zero on admission, just as for later new points.
    Historical counts must therefore arise through recorded selection events,
    rather than being smuggled into a fresh archive.
    """

    if not isinstance(balanced, bool):
        raise ValueError("balanced must be bool")
    original_points = _sequence(initial_points, "initial_points")
    requested_blocks = _sequence(blocks, "blocks")
    archive = update_archive(original_points)
    initial_archive = deepcopy(archive)
    recorded_blocks: list[dict[str, Any]] = []
    selection_pairs = 0
    supplied_vectors = len(original_points)

    for block_index, block in enumerate(requested_blocks):
        _fields(block, {"dimension", "requests", "new_points"}, "block")
        requests = _sequence(block["requests"], "requests")
        new_points = _sequence(block["new_points"], "new_points")
        before = deepcopy(archive)
        plan = freeze_selection(archive, block["dimension"], balanced=balanced)
        counts = {point["id"]: point["selected"] for point in before}
        events: list[dict[str, Any]] = []

        for request in requests:
            _fields(
                request,
                {"tournament_draws", "neighbor_side"},
                f"block {block_index} request",
            )
            event = select_pair(
                plan,
                counts,
                request["tournament_draws"],
                neighbor_side=request["neighbor_side"],
            )
            events.append(event)
            counts = deepcopy(event["counts_after"])
            selection_pairs += 1

        after_selection = [
            {
                "id": point["id"],
                "objectives": deepcopy(point["objectives"]),
                "selected": counts[point["id"]],
            }
            for point in before
        ]
        archive = update_archive(new_points, existing=after_selection)
        supplied_vectors += len(new_points)
        recorded_blocks.append(
            {
                "archive_before": before,
                "plan": plan,
                "requests": requests,
                "events": events,
                "archive_after_selection": after_selection,
                "new_points": new_points,
                "archive_after_update": deepcopy(archive),
            }
        )

    return {
        "schema": "bntga-operator-journal-v1",
        "balanced": balanced,
        "initial_points": original_points,
        "initial_archive": initial_archive,
        "blocks": recorded_blocks,
        "final_archive": deepcopy(archive),
        "accounting": {
            "selection_pairs": selection_pairs,
            "objective_vectors_supplied": supplied_vectors,
            "new_fitness_evaluations": 0,
        },
    }


def teaching_comparison() -> dict[str, Any]:
    """Return a paired instructional example with a fully recorded history.

    The first block selects C and D twice.  Consequently C's selection count
    is two when the decisive B/C tournament is held in the second block.
    D also has count two; this is explicit and irrelevant to that tournament.
    No objective vector is manufactured by a search or fitness evaluator.
    """

    from .verifier import verify_journal

    initial = [
        {"id": "A", "objectives": [0, 6], "selected": 0},
        {"id": "B", "objectives": [2, 4], "selected": 0},
        {"id": "C", "objectives": [3, 3], "selected": 0},
        {"id": "D", "objectives": [6, 0], "selected": 0},
    ]
    blocks = [
        {
            "dimension": 0,
            "requests": [
                {"tournament_draws": [2, 2], "neighbor_side": 0},
                {"tournament_draws": [2, 2], "neighbor_side": 0},
            ],
            "new_points": [],
        },
        {
            "dimension": 0,
            "requests": [
                {"tournament_draws": [1, 2], "neighbor_side": 0},
            ],
            "new_points": [],
        },
    ]
    profiles: dict[str, Any] = {}
    decisive: dict[str, Any] = {}
    for name, balanced in (("unbalanced_gap", False), ("balanced_gap", True)):
        journal = build_journal(initial, blocks, balanced=balanced)
        receipt = verify_journal(journal)
        profiles[name] = {"journal": journal, "verification": receipt}
        decision_block = journal["blocks"][1]
        plan = decision_block["plan"]
        priorities = {
            point["id"]: priority
            for point, priority in zip(plan["archive"], plan["priorities"])
        }
        event = decision_block["events"][0]
        decisive[name] = {
            "first_parent": event["first_id"],
            "second_parent": event["second_id"],
            "B_priority": priorities["B"],
            "C_priority": priorities["C"],
        }

    return {
        "schema": "bntga-instructional-comparison-v1",
        "protocol_id": "GA-BNTGA-SELECTION-ADMISSION-V1",
        "scope": "instructional_operator_comparison_not_a_search_result",
        "profiles": profiles,
        "decisive_comparison": decisive,
        "history_explanation_uk": (
            "Перший блок двічі вибирає C і D. Перед другим блоком "
            "лічильники A=0, B=0, C=2, D=2. На турнірі B/C звичайний "
            "Gap-відбір обирає C (3 проти 2), а збалансований — B "
            "(2 проти 1). Лічильник D відрізняється від окремого "
            "канонічного знімка, але D не бере участі в цьому турнірі. "
            "Це навчальний приклад зміни вибору, не результат ГА на рюкзаку."
        ),
        "accounting": {
            "selection_pairs_per_profile": 3,
            "objective_vectors_supplied_per_profile": 4,
            "new_fitness_evaluations": 0,
        },
    }

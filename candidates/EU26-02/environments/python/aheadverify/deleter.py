"""Source-faithful clean-room model of the frozen Deleter helper.

This module follows ``adaptive.cpp`` at commit 04da9d, including the lifetime
mean, zero-based warm-up and tie rule.  Amendment 001 explains why these
semantics are not paper-faithful.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .canonical import canonical_sha256


class DeleterValidationError(ValueError):
    """Raised when a Deleter state or transition violates the frozen contract."""


def _require_int(value: Any, name: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DeleterValidationError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise DeleterValidationError(f"{name} must be >= {minimum}")
    return value


def _require_score(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DeleterValidationError(f"{name} must be numeric")
    score = float(value)
    if not math.isfinite(score) or score < 0:
        raise DeleterValidationError(f"{name} must be finite and non-negative")
    return score


@dataclass
class DeleterState:
    """Mutable source-turn state for one Deleter policy."""

    nb_operators: int
    nb_selected: int
    turn: int
    counts: list[int]
    means: list[float]
    surviving: list[int]
    removed: list[int]

    @classmethod
    def initialize(cls, nb_operators: int = 6, nb_selected: int = 2) -> "DeleterState":
        nb_operators = _require_int(nb_operators, "nb_operators", 1)
        nb_selected = _require_int(nb_selected, "nb_selected", 1)
        return cls(
            nb_operators=nb_operators,
            nb_selected=nb_selected,
            turn=0,
            counts=[0] * nb_operators,
            means=[0.0] * nb_operators,
            surviving=list(range(nb_operators)),
            removed=[],
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DeleterState":
        if not isinstance(value, dict):
            raise DeleterValidationError("state must be an object")
        state = cls(
            nb_operators=_require_int(value.get("nb_operators"), "nb_operators", 1),
            nb_selected=_require_int(value.get("nb_selected"), "nb_selected", 1),
            turn=_require_int(value.get("turn"), "turn", 0),
            counts=list(value.get("counts", [])),
            means=list(value.get("means", [])),
            surviving=list(value.get("surviving", [])),
            removed=list(value.get("removed", [])),
        )
        state.validate()
        state.counts = [int(item) for item in state.counts]
        state.means = [float(item) for item in state.means]
        state.surviving = [int(item) for item in state.surviving]
        state.removed = [int(item) for item in state.removed]
        return state

    def validate(self) -> None:
        _require_int(self.nb_operators, "nb_operators", 1)
        _require_int(self.nb_selected, "nb_selected", 1)
        _require_int(self.turn, "turn", 0)
        if len(self.counts) != self.nb_operators:
            raise DeleterValidationError("counts length must equal nb_operators")
        if len(self.means) != self.nb_operators:
            raise DeleterValidationError("means length must equal nb_operators")
        for index, count in enumerate(self.counts):
            _require_int(count, f"counts[{index}]", 0)
        for index, mean in enumerate(self.means):
            _require_score(mean, f"means[{index}]")
            if self.counts[index] == 0 and float(mean) != 0.0:
                raise DeleterValidationError(
                    f"means[{index}] must be zero while counts[{index}] is zero"
                )

        for name, values in (("surviving", self.surviving), ("removed", self.removed)):
            if len(values) != len(set(values)):
                raise DeleterValidationError(f"{name} must not contain duplicates")
            for index, operator in enumerate(values):
                operator = _require_int(operator, f"{name}[{index}]", 0)
                if operator >= self.nb_operators:
                    raise DeleterValidationError(f"{name}[{index}] is out of range")
        if not self.surviving:
            raise DeleterValidationError("at least one operator must survive")
        if self.surviving != sorted(self.surviving):
            raise DeleterValidationError("surviving operators must be sorted")
        if self.removed != sorted(self.removed):
            raise DeleterValidationError("removed operators must be sorted")
        if set(self.surviving) & set(self.removed):
            raise DeleterValidationError("surviving and removed operators overlap")
        if set(self.surviving) | set(self.removed) != set(range(self.nb_operators)):
            raise DeleterValidationError("surviving and removed must partition all operators")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "nb_operators": self.nb_operators,
            "nb_selected": self.nb_selected,
            "turn": self.turn,
            "counts": list(self.counts),
            "means": list(self.means),
            "surviving": list(self.surviving),
            "removed": list(self.removed),
        }

    def choose(self, rng: random.Random) -> int:
        """Uniformly choose one currently surviving operator."""

        self.validate()
        if not isinstance(rng, random.Random):
            raise DeleterValidationError("rng must be random.Random")
        return self.surviving[rng.randrange(len(self.surviving))]

    def advance(
        self,
        selected_operators: Sequence[int],
        scores: Sequence[int | float],
    ) -> dict[str, Any]:
        """Apply one source generation, delete if triggered, then increment turn."""

        self.validate()
        if len(selected_operators) != self.nb_selected:
            raise DeleterValidationError("selected_operators length must equal nb_selected")
        if len(scores) != self.nb_selected:
            raise DeleterValidationError("scores length must equal nb_selected")

        selected: list[int] = []
        numeric_scores: list[float] = []
        current_survivors = set(self.surviving)
        for index, operator in enumerate(selected_operators):
            operator = _require_int(operator, f"selected_operators[{index}]", 0)
            if operator not in current_survivors:
                raise DeleterValidationError(
                    f"selected_operators[{index}] is not a surviving operator"
                )
            selected.append(operator)
            score = _require_score(scores[index], f"scores[{index}]")
            if not score.is_integer():
                raise DeleterValidationError(f"scores[{index}] must be an integer penalty")
            numeric_scores.append(score)

        source_turn = self.turn
        for operator, score in zip(selected, numeric_scores):
            old_count = self.counts[operator]
            self.means[operator] = (
                (self.means[operator] * float(old_count)) + score
            ) / float(old_count + 1)
            self.counts[operator] = old_count + 1

        deleted: int | None = None
        if (
            source_turn >= 5 * self.nb_operators
            and source_turn % 5 == 0
            and len(self.surviving) > 1
        ):
            worst = self.surviving[0]
            for operator in self.surviving:
                if self.means[operator] > self.means[worst]:
                    worst = operator
            self.surviving.remove(worst)
            self.removed.append(worst)
            self.removed.sort()
            deleted = worst

        self.turn += 1
        self.validate()
        return {
            "source_turn": source_turn,
            "selected_operators": selected,
            "scores": numeric_scores,
            "deleted_operator": deleted,
            "state": self.to_dict(),
        }


def simulate_deleter(
    seed: int,
    turns: int,
    nb_operators: int = 6,
    nb_selected: int = 2,
) -> dict[str, Any]:
    """Run a deterministic synthetic source-formula workload.

    Python's RNG is intentionally not claimed to match C++ ``std::mt19937``.
    It supplies stable independent workloads for invariant and portability
    checks only.
    """

    seed = _require_int(seed, "seed", 0)
    turns = _require_int(turns, "turns", 0)
    state = DeleterState.initialize(nb_operators, nb_selected)
    rng = random.Random(seed)
    history: list[dict[str, Any]] = []
    deletion_events: list[dict[str, int]] = []
    previous_survivor_count = len(state.surviving)

    for _ in range(turns):
        selected = [state.choose(rng) for _ in range(nb_selected)]
        scores = [
            float(
                1
                + operator * 17
                + ((state.turn + 1) * (slot + 3) + seed) % 23
            )
            for slot, operator in enumerate(selected)
        ]
        event = state.advance(selected, scores)
        if len(state.surviving) > previous_survivor_count:
            raise AssertionError("survivor count increased")
        previous_survivor_count = len(state.surviving)
        history.append(
            {
                "source_turn": event["source_turn"],
                "selected": event["selected_operators"],
                "scores": event["scores"],
                "deleted": event["deleted_operator"],
            }
        )
        if event["deleted_operator"] is not None:
            deletion_events.append(
                {
                    "source_turn": event["source_turn"],
                    "operator": event["deleted_operator"],
                }
            )

    expected_updates = turns * nb_selected
    invariants = {
        "count_accounting": sum(state.counts) == expected_updates,
        "finite_means": all(math.isfinite(value) for value in state.means),
        "partition": set(state.surviving) | set(state.removed)
        == set(range(nb_operators)),
        "deletion_cadence": all(
            event["source_turn"] >= 5 * nb_operators
            and event["source_turn"] % 5 == 0
            for event in deletion_events
        ),
        "adaptation_observed": bool(deletion_events),
    }
    return {
        "schema_version": "1.0.0",
        "seed": seed,
        "turns": turns,
        "expected_updates": expected_updates,
        "final_state": state.to_dict(),
        "deletion_events": deletion_events,
        "selection_history_digest": canonical_sha256(
            history, domain="EU26-02-DELETER-HISTORY-V1"
        ),
        "invariants": invariants,
    }

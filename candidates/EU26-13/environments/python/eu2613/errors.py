"""Candidate-local exception types."""

from __future__ import annotations


class VerificationError(RuntimeError):
    """Raised when a frozen verification gate fails."""

    def __init__(self, stage: str, detail: str) -> None:
        self.stage = stage
        self.detail = detail
        super().__init__(f"{stage}: {detail}")

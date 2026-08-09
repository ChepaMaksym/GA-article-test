"""Candidate-local verification exceptions."""


class VerificationError(ValueError):
    """Raised whenever an identity, format, or claim-boundary gate fails."""

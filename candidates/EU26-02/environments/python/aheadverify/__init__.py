"""Independent verification helpers for EU26-02.

The package validates the frozen result archive and the source-revision
Deleter transition.  It is deliberately not a full AHEAD reimplementation.
"""

from .archive import (
    ArchiveValidationError,
    aggregate_results,
    list_instances,
    load_authenticated_member_payloads,
    validate_archive,
    validate_instance,
    validate_instance_payloads,
)
from .deleter import DeleterState, DeleterValidationError, simulate_deleter
from .witness import WitnessValidationError, validate_selected_witness

__all__ = [
    "ArchiveValidationError",
    "DeleterState",
    "DeleterValidationError",
    "WitnessValidationError",
    "aggregate_results",
    "list_instances",
    "load_authenticated_member_payloads",
    "simulate_deleter",
    "validate_archive",
    "validate_instance",
    "validate_instance_payloads",
    "validate_selected_witness",
]

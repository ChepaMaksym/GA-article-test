"""Frozen schemas and exact identities for retained gate attestations."""

from __future__ import annotations


# Updated only when the candidate-local suite intentionally adds or removes tests.
EXPECTED_TESTS_RUN = 117
EXPECTED_MUTATION_TESTS = 99

PYTHON_ATTESTATION_KEYS = frozenset(
    {
        "schema_version",
        "candidate_id",
        "status",
        "tests_run",
        "mutation_tests",
        "failures",
        "errors",
        "skipped",
        "expected_failures",
        "unexpected_successes",
        "implementation_files",
        "implementation_manifest_sha256",
        "source_native_status",
    }
)

OCTAVE_ATTESTATION_KEYS = frozenset(
    {
        "schema_version",
        "candidate_id",
        "status",
        "paper_mapping",
        "source_native_status",
        "contract_sha256",
        "fixture_sha256",
        "octave_script_sha256",
        "checks",
        "values",
    }
)

OCTAVE_CHECK_KEYS = frozenset(
    {
        "boundary",
        "endpoint_schema",
        "endpoint_value",
        "seed_schedule",
        "bipop_first",
        "bipop_second",
        "repelling",
        "csa",
        "hill_valley",
    }
)

OCTAVE_VALUE_KEYS = frozenset(
    {
        "seed_rows",
        "seed_last",
        "first_lambda",
        "second_lambda",
        "second_sigma",
        "repelling_radius",
        "repelling_shrinkage",
        "csa_sigma",
        "hill_fractions",
        "endpoint_best_y_decimal",
    }
)

# Filled after the unchanged Octave control is rerun in the corrective cycle.
EXPECTED_OCTAVE_ATTESTATION_SHA256 = "cc8fb17b0b45d8d4db4da64db19adb5103bc85ac33607e09ef49f33a1982d9df"

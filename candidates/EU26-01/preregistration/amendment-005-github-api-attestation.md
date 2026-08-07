# Amendment 005 — separate GitHub API attestation

Status: superseded by Amendment 006 after adversarial review demonstrated that
an offline caller could fabricate the record without contacting GitHub.

Recorded: 2026-08-07, before the implementation/source commit and before any
formal Work4, Work8 or GitHub4 execution.

This fail-closed provenance hardening does not change the frozen paper cell,
archive/member identity, Table 1 endpoints or tolerance, formula semantics,
fixture, fixed tape, workload matrix or timing repeats. It closes an evidence
authentication gap in H5.

The `github4.json` execution-context fields originate inside the profile and
are therefore self-asserted. They cannot authenticate the GitHub4 role. Full
H5 now requires a separate strict record acquired from authenticated GitHub
workflow-run and artifact API objects. It binds:

- repository and workflow path;
- checked-out head SHA, run ID and run attempt;
- validation artifact ID, name and non-expired state;
- exact `github4.json` member name and raw file SHA-256;
- the profile's internal canonical report SHA-256; and
- SHA-256 digests of the two retained raw API responses.

The comparator independently checks an exact record schema and canonical
record digest. Duplicate JSON keys and non-finite constants are rejected.
Without this separate record, even three otherwise matching profiles yield
`NOT_EVALUATED_UNAUTHENTICATED_GITHUB4`, never `PASS_PORTABILITY`.

This amendment narrows possible positive evidence and cannot clear
`BLOCKED_SOURCE_NATIVE_REPLAY`, change `conditional_noneligible`, or authorize
`PASS_FULL`.

# Amendment 006 — external authentication boundary

Recorded: 2026-08-07, after adversarial review of the implementation and
before any evidence from the repaired final source commit is interpreted.

This security amendment supersedes Amendment 005's claim that a
caller-supplied API-attestation JSON can authorize H5. The former record used
only public fields and unkeyed hashes; an offline caller could fabricate all
of them without contacting GitHub. It therefore did not prove API acquisition,
artifact custody or native execution.

The comparator now treats three matching profile reports as content evidence
only. It emits `CONTENT_MATCH_EXTERNAL_AUTH_REQUIRED` and retains H5 as
`NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED`. It has no input or code path
that can promote self-authored API metadata to `PASS_PORTABILITY`.

Only a trusted reviewer may later adjudicate GitHub provenance by independently
querying the completed run, downloading and hashing the artifact archive,
checking its exact member inventory and binding the extracted `github4.json`
bytes. That review remains external to this offline verifier.

The same hardening rejects finite-overflow JSON numbers, bool-as-integer CPU
claims, malformed worker CPU/thread state, colliding formal output paths and
pre-existing outputs. F5 wording is narrowed to what the tests perform: both
language implementations independently check the same frozen fixture; Octave
does not emit a canonical result artifact.

No paper cell, archive/member byte identity, endpoint, rounding rule, formula,
fixed tape, worker matrix, timing count or acceptance tolerance changed. This
amendment cannot clear `BLOCKED_SOURCE_NATIVE_REPLAY`, change
`conditional_noneligible`, or authorize `PASS_FULL`.

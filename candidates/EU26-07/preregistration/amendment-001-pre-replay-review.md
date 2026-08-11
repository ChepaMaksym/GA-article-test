# Amendment 001 — pre-replay review strengthening

Date: 2026-08-07 (Europe/Kyiv)

This amendment was made after the preregistration/implementation commit
`4e1681c` and before any full 500-row replay. An independent code review ran a
10-row diagnostic prefix; source-native and clean-room rows 1–10 were exact.
This expands the disclosed outcome exposure from two rows to ten. No later row
and no full-ledger digest had been inspected.

The primary problem, seed ledger, author source/data identities, profiles,
numerical targets, exact all-field tolerances, stop rule, and `PASS_FULL`
blocker are unchanged.

The review found that the verifier's claim composition was weaker than the
written contract. Before the full run, this amendment therefore requires:

1. `PASS_TARGET_ARTIFACT_REPLAY` to depend explicitly on every H0–H6 status,
   including H2 and H3;
2. H5 source-native and H6 clean-room row counts/statuses to remain separate;
3. the raw file's byte SHA-256 and the parsed canonical-row digest to have
   different field names;
4. H2 to execute deterministic witnesses for exact-position mutation and
   biased-uniform crossover, not only selection over supplied children;
5. Python and MATLAB/Octave to read the same fixed-tape JSON witness; and
6. execution exceptions to be preserved as a first-mismatch record rather
   than terminating without a report.

The review also records a platform constraint: the frozen upstream raw
filename contains colon characters, so source-native materialization requires
a POSIX-compatible filesystem (Linux/macOS/WSL), while formula-only tests do
not.

The revised fixed-tape fixture is frozen at SHA-256
`c80b9290d1e3eb21c9fbf1a12b2a981884752549d76d9d10d9d4df0dc17238ae`.
The eligibility and original verification-contract documents remain frozen at
SHA-256 `e83c129aefc1a5c995a5de40f5ee99746abc84b3b7e483c275604738e1cc17d4`
and `e7959622061600b5770e71349cdb6d35f5aaaed2c1c98fba7c481758317105e0`,
respectively.

This is a verifier-strengthening amendment, not a tolerance or algorithm
change. The full replay must start again at row 1 after these changes pass
unit review.

The protocol's historical `clean-room` profile label is retained as an
identifier. It means that upstream files are not vendored and observations are
disclosed; it is not asserted as a legal conclusion about originality.

# EU26-05 H4-H5 formula-portability contract

Evidence-authentication semantics in
[`amendment-001-offline-evidence-boundary.md`](amendment-001-offline-evidence-boundary.md)
supersede any original wording below that treated an offline envelope or
caller-supplied API-shaped JSON as proof of native execution or GitHub
authentication.

Frozen before Work4/Work8/GitHub4 evidence generation.

This amendment does not widen the v1 scientific scope. H0 remains exactly
**`PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE`**. The thesis maximum
binary extension profile remains a thesis-profile complement-of-origin oracle,
not a paper-author-code claim. Every probability-update call with any zero
denominator rejects.

## Frozen profiles

| Profile | Workers | Affinity-visible logical CPUs | Context |
|---|---:|---:|---|
| `work-4` | 4 | 4 | non-GitHub Work host |
| `work-8` | 8 | 8 | non-GitHub Work host |
| `github-4` | 4 | 4 | GitHub Actions with run ID/attempt |

Each profile executes exactly five repeats. A repeat recomputes the shared
fixture report, 120 probability-grid cases, 768 exhaustive four-bit one-point
transitions, 512 thesis-profile extension children, a discriminating
non-geometric extension witness, the 600-bit toy-objective anchor and 128
deterministic parallel formula/transition cases. Canonical scientific bytes
must be identical within the five repeats. A startup barrier must also expose
one distinct worker PID per frozen worker slot, the exact inherited affinity
mask and a complete deterministic shard of the 128 cases.

Timing, hostname and scheduler order are not scientific fields. The strict
cross-profile fields are the git commit, source aggregate, contract bytes,
fixture bytes, canonical scientific digest, paper-level blocker and H0 source
status. The comparator independently recomputes the payload and validates the
current source tree before trusting a report.

## Fail-closed outcomes

- One profile alone: `NOT_EVALUATED_SINGLE_PROFILE` for H5.
- Work4 plus Work8 without the real GitHub artifact:
  `NOT_RUN_MISSING_PROFILES`.
- All three payloads exact, with a coherent caller-supplied metadata record:
  `NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED`; offline code cannot emit an
  H5 pass.
- Any missing/tampered case, dirty-start report, CPU mismatch, relabelled
  GitHub context, source mismatch or blocker change: reject.

The `github-4` report's environment fields are a self-asserted context hint,
not authentication. The offline content matcher can bind only
caller-supplied metadata fields and local `github-4.json` bytes. It cannot
prove authenticated API acquisition or artifact membership, so it records
`offline_authorizes_h5=false`. Those facts require independent reviewer
verification after CI completion and remain outside the offline comparator.

H3 reports bind protocol, git HEAD, declared runtime, exact implementation
source hashes and semantic payload digest. Equal envelopes establish payload
and formula equivalence only. A declared `octave` or `matlab` string does not
authenticate native execution; that status remains
`NOT_EVALUATED_EXTERNAL_EXECUTION_AUTH_REQUIRED`. Minimal envelopes,
duplicate JSON keys, non-finite/overflowing numbers and forged payloads fail
closed.

None of these results executes CEC-2017, reconstructs P/P' selection, replays
author code or evaluates the published 27/30 descriptive endpoint.

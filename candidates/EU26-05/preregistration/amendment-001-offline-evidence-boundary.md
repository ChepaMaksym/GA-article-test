# Amendment 001 — offline evidence authentication boundary

Frozen: 2026-08-07, after the implementation-source audit and before any
formal Work4/Work8/GitHub4 outcome was accepted.

Reason: an adversarial review showed that a standalone JSON comparator cannot
prove which executable produced an envelope, whether caller-supplied JSON came
from an authenticated API, or whether a local report was extracted from a
named remote artifact. The original formula, fixture, source and claim
boundaries are unchanged. This amendment narrows evidence semantics only.

## H3 correction

An offline comparison of Python- and MATLAB-shaped envelopes may establish
only **`PASS_H3_PAYLOAD_FORMULA_EQUIVALENCE_ONLY`**. Runtime names, versions,
source hashes and equal payloads are self-asserted content. They do not prove
that MATLAB or Octave executed. Native-runtime execution therefore remains
**`NOT_EVALUATED_EXTERNAL_EXECUTION_AUTH_REQUIRED`** until a reviewer verifies
trusted execution records outside the offline comparator.

No offline envelope may emit `PASS_H3_CROSS_LANGUAGE_FIXED_TAPE` or otherwise
authorize a native-runtime claim.

## H5 correction

Caller-supplied workflow/artifact-shaped JSON and a local `github-4.json` can
be checked for internal identity and byte-digest coherence. That result is
only
**`PASS_CALLER_SUPPLIED_METADATA_AND_LOCAL_REPORT_COHERENCE_ONLY`**.
It cannot authenticate an API response, prove artifact membership, or
authorize H5.

Even after all three profile payloads match, the offline status remains
**`NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED`** and
`offline_authorizes_h5=false`. A reviewer must independently authenticate the
workflow run, jobs, artifact and downloaded bytes. The offline code contains
no path that emits `PASS_H5_PORTABILITY`.

## Evidence hardening

- JSON duplicate keys, literal non-finite constants and finite-syntax numeric
  overflow such as `1e9999` reject.
- Boolean values never satisfy integer evidence fields.
- CPU masks are sorted, unique, non-negative integer lists of exact frozen
  length.
- Each repeat uses a startup barrier and records distinct worker PIDs,
  inherited affinity and deterministic case shards.
- Formal Python evidence destinations are distinct, new, outside the
  repository and rejected when a symbolic-link ancestor is present.
- MATLAB/Octave report output requires an existing external directory and a
  previously absent destination.

The paper remains blocked, H0 remains
`PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE`, and `PASS_FULL` remains
forbidden.

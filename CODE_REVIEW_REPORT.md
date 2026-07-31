# Code review and repository audit

Date: 31 July 2026  
Branch reviewed and committed: `main` (the repository has no `master`
branch)

## Outcome

Critical defects found in the prospective staged-verification harness were
fixed. The retained USA-001 evidence remains byte-for-byte verifiable, the
research/context documentation now matches the recorded outcomes, and
generated or archival files were left outside the commit scope.

## Critical fixes

- Bound adapter wrapper/implementation bytes and immutable configuration
  to the contract, checkpoint and cache identity; the complete identity
  payload is checked, not only a copied digest.
- Replaced JSON contract hashing with the typed canonical SHA-256 encoder.
- Enforced fail-closed types and ranges for run IDs, all seed-ledger
  fields, contract numbers, gate numbers/flags, worker count and options.
- Required at least one required gate and at least one required terminal
  gate.
- Restricted irreversible early failure to required preterminal
  `perfect_fraction` deadlines.
- Scheduled every declared gate generation and preserved each gate's
  decision from that exact checkpoint.
- Implemented P4 as the maximum absolute per-run objective deviation, so a
  single terminal outlier cannot be hidden by a mean.
- Rejected non-finite or malformed evidence values and authenticated the
  retained evidence before runtime projection.
- Enforced exactly one recorded 100000-generation straggler per historical
  profile.
- Made pool-type mismatch explicit instead of silently reusing an
  incompatible pool.
- Protected evidence CSV bytes from Git line-ending normalization.

## Context and file audit

- Canonical registry: 15 candidates (7 EU, 8 USA), with 2 `hard_pass`, 3
  `conditional_noneligible` and 10 `hard_fail`.
- Both eligible candidates were executed and failed required numerical
  gates; there is no active candidate implementation.
- Stale “next candidate” wording, field counts, environment version,
  historical recommendation status and RNG-stream wording were corrected.
- USA-001 retains 25 manifest-listed evidence files plus the manifest.
  EU-001 retains narrative/summary evidence only, not independently
  recomputable raw rows.
- `old/` was not changed. Ignored `sandbox/results/` artifacts were neither
  staged nor deleted. No duplicate deliverables or broken local Markdown
  links were found in the reviewed scope.

## Verification performed

- MATLAB Code Analyzer: 18 files, 0 issues.
- MATLAB unit/regression suite: 20 passed, 0 failed, 0 incomplete.
- Real process-pool path: 2-worker test passed.
- Fresh integration run: 4 workers, 0 cache hits, expected
  `FAIL_DECISIVE` at P2 generation 2000.
- Retained evidence: 25/25 manifest entries passed byte-length and SHA-256
  checks; P1–P4 arithmetic and recorded failure status passed.
- Historical runtime analysis: four profiles validated; estimates remain
  142.2 minutes historical, 6.4 minutes empirical four-worker compute and
  7–9 minutes realistic end-to-end.

## Research stage and remaining questions

The current cohort is exhausted without a successful numerical
reproduction. Baseline/ablation work, the 18-sheet workbook and a success
package correctly remain blocked.

The next decision is either to close this cohort as a documented negative
result or authorize a new search cohort. The main unresolved inputs are:

- EU-001 author sweep driver, Table 1 interpretation, seeds/raw runs and
  environment;
- USA-001 author RNG/seeds, generated instances, initial populations,
  exact graph semantics, dependency versions and result-CSV license;
- EU-006 dataset provenance/license plus seeds/raw stochastic logs;
- USA-005 self-contained adaptation specification and legal inputs;
- USA-006 dynamic-rate formula/bounds, dimensional proof, matrices,
  implementation and seeds.

See `RESEARCH_STATUS.md` for the canonical stage report and decision path.

## Known non-blocking limitations

- The harness is prospective infrastructure exercised with mock adapters;
  the deleted USA-001 implementation cannot be rerun without a documented
  restore.
- MAT checkpoint replacement is atomic, but the MAT file and SHA-256
  sidecar are not committed as one filesystem transaction; validation
  remains fail-closed.
- Hashing a very large checkpoint currently reads the file into memory.

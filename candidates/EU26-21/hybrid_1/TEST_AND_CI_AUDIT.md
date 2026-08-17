# Hybrid 1 test and CI audit

Status: `AUDIT_IMPLEMENTED_CI_PENDING`.

This audit is separate from the scientific H1-H3 result. Its purpose is to
check whether the implementation is being tested for the claimed behavior,
whether negative cases fail closed, and whether GitHub Actions preserves useful
evidence when a test or experiment fails.

No merge is part of this stage.

## Confirmed historical CI result

The immutable 30-seed matrix run `31934321927` completed all 30 seed jobs, but
its original aggregate job failed. The failure was not an optimizer failure and
not a failed scientific hypothesis. The aggregator incorrectly rejected a
first target hit with NFE below 50, even though an initial-population mask may
reach a target at any objective call from 1 through 50.

A separate analysis-only correction workflow later passed. The audit moves this
rule into the canonical strict aggregator and tests that canonical path, rather
than relying on the former monkey-patch wrapper.

## Test traceability

| Topic | Main tests | What is actually checked |
|---|---|---|
| Offspring rounding and controls | `test_hybrid_1_core.py` | half-up offspring rounding, `p=lambda/n`, `c=1/lambda`, endpoint values |
| Lambda transitions | `test_hybrid_1_core.py`, `test_hybrid_1_core_semantics_extended.py` | success shrink, failure growth, reset only after a failed generation already at the cap |
| Mutation | `test_hybrid_1_core.py`, extended semantics | one shared exact mutation strength, exact distinct bit flips, zero-strength behavior |
| Crossover | core and extended semantics | realized biased crossover and probability-zero/probability-one endpoints |
| Final candidate pool | `test_hybrid_1_core.py` | selected best mutant is included; exact parent copies are excluded |
| Acceptance semantics | core and extended semantics | neutral candidate can be accepted, but only strict lexicographic improvement shrinks lambda |
| Budget and call accounting | core and extended semantics | no budget overshoot; objective call count equals recorded logical NFE |
| Parallel evaluation | worker and extended semantics | ordered 1/2/4-worker output, exception propagation, complete trace invariance |
| Jump definition | `test_hybrid_1_jump.py` | local optimum, valley, and global optimum values |
| Jump reset effect | unit smoke plus full CI campaign | reduced deterministic smoke and frozen 50-seed reset/no-reset confirmation |
| OneMax control | Jump/OneMax tests | both variants solve; reset remains unnecessary; no endpoint regression |
| Census boundary | `test_hybrid_1_census_synthetic.py` | empty-mask penalty, nonempty selected subset, validation/test separation smoke |
| OLD source behavior | source campaign and upstream tests | HUX, adaptive distance, restart, deterministic source endpoint, numerical gates |
| H1/H2/H3 decisions | paired-comparison tests | positive and deliberately failing synthetic ledgers, confidence and coverage gates |
| Immutable row integrity | audit validation tests | seed/configuration, reset flag, hex digests, mask-index consistency, monotone first-hit NFE, best-fitness support |
| Scientific failure reporting | audit validation tests | H1/H3 failure remains a scientific result while protocol status stays valid; H2 is blocked when H1 fails |
| CI topology | `test_hybrid_1_ci_audit.py`, `ci_audit.py` | path coverage, retired workflows, pinned canonical actions, partial-failure artifacts, protocol-vs-hypothesis semantics |

## CI semantics

The workflows deliberately distinguish two kinds of failure.

### Implementation or protocol failure

Examples:

- malformed or missing seed rows;
- wrong seed or search seed;
- non-binary/inconsistent feature mask;
- invalid first-hit NFE;
- incorrect reset configuration;
- worker-dependent result;
- test failure;
- source provenance mismatch.

These conditions make CI fail. Logs and partial artifacts are uploaded with
`if: always()` so the failure remains analyzable.

### Scientific hypothesis failure

Examples:

- H1 confidence interval crosses the non-inferiority margin;
- H2 does not reduce the feature count after H1 passes;
- H3 confidence lower bound does not exceed 20%;
- Jump reset does not reach its preregistered improvement threshold.

These must appear as `FAIL...` decisions in the scientific report. A valid
negative result is not rewritten as a protocol error. The canonical aggregator
therefore enforces row/protocol integrity, not a preferred H1-H3 outcome.

## CI changes made by the audit

1. The strict first-hit rule is used by the canonical matrix aggregator.
2. Positive and deliberately malformed ledgers are tested.
3. H2 is explicitly conditional on H1.
4. The canonical 30-seed workflow now watches every scientific source and test
   that can change the result.
5. The matrix keeps `fail-fast: false` and records per-seed logs.
6. The aggregate job runs with `if: always()` and writes a status artifact even
   when rows are missing or invalid.
7. Two superseded 30-seed workflows are manual-only, preventing duplicate or
   cancelling experiments.
8. The former correction replay is manual-only and uses the canonical strict
   aggregator.
9. Canonical matrix and audit actions are pinned to full commit SHAs.
10. OLD and Hybrid workflows are scoped so result-only documentation changes do
    not rerun unrelated expensive campaigns.
11. A code fingerprint job compares the current row-generation implementation
    with the immutable matrix commit.
12. Artifacts from the hardened workflows are retained for 90 days.

## Claim limitations retained

- NFE means logical wrapper-objective calls, not wall-clock time, CPU time, or
  equal floating-point work per call.
- H3 compares complete OLD and Hybrid search layers. It does not identify reset
  as the sole cause of the NFE difference.
- Reset-specific causal evidence comes from the paired Jump and Census
  reset/no-reset ablations.
- The public CHC-QX source and printed paper are not treated as literally
  identical; their divergences remain documented.
- One row-level initial-population digest plus the deterministic paired runner
  proves construction by the same mask list, but the artifact does not contain
  two independently stored copies of that list.
- The research branch currently has no branch-protection requirement. This
  audit does not change repository governance or merge the PR.

## Final gate

This document changes to `AUDIT_PASS`, `AUDIT_FAIL`, or
`AUDIT_PASS_WITH_LIMITATIONS` only after the independent audit workflow and the
hardened canonical matrix complete. A red workflow is retained and analyzed; it
is not relabeled as success.

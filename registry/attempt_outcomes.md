# Ranked reproduction outcomes

Date: 2026-07-30

This file records execution outcomes without changing the registry's
hard-filter fields. A `hard_pass` means that a paper was eligible to
attempt; it does not mean that the published numerical result was
successfully reproduced.

## Rank 1 — EU-001

`Adaptive Gene Level Mutation`, registry score 79.

- The MATLAB implementation passed its structural, deterministic, and
  50-run protocol checks.
- The adaptive locus method beat the fixed baseline qualitatively in all
  five selected N=64 conditions.
- Only 5 of 10 preregistered Table 1 cells met the required 5% numerical
  rule.
- All three source-grounded diagnostic cycles failed to reconcile the
  paper, released driver, and published table without arbitrary fitting.
- The failed candidate folder was deleted after logging.

Detailed evidence:
[`../failure_logs/EU-001_failure.md`](../failure_logs/EU-001_failure.md).

## Rank 2 — USA-001

`Calibration of an Adaptive Genetic Algorithm for Modeling Opinion
Diffusion`, registry score 77.

- The paper-faithful primary used ten frozen instances, populations, and
  algorithm seeds and passed the hardened provenance checks.
- Nine of ten runs were perfect by generation 1000, but run 8 remained
  nonzero through the complete 100000-generation budget.
- The published 10/10-perfect-by-2000 and zero-terminal-objective
  endpoints therefore failed.
- Q1, Q2, and Q3 used only source-grounded semantic variants; all three
  retained the same single unresolved observation and failed P2/P4.
- The failed candidate folder was deleted after a compact evidence bundle
  and complete pre-deletion hash inventory were externalized.

Detailed evidence:
[`../failure_logs/USA-001_primary_failure.md`](../failure_logs/USA-001_primary_failure.md).
Compact evidence:
[`../failure_logs/USA-001_evidence/README.md`](../failure_logs/USA-001_evidence/README.md).

## Exhaustion result

Both ranked `hard_pass` candidates were attempted and failed numerical
published-result verification. Five initially plausible alternatives
were re-audited to `hard_fail`; the remaining registry rows were already
hard-fail or conditional/noneligible. The final registry therefore has:

| Status | Count |
|---|---:|
| `hard_pass` attempted and failed | 2 |
| `conditional_noneligible` | 3 |
| `hard_fail` | 10 |
| **Total** | **15** |

There is no unattempted eligible candidate. The success-only fixed-GA
comparison, ablations, 18-sheet workbook, and complete reproducibility
package were not generated because no candidate passed its published
verification gate.

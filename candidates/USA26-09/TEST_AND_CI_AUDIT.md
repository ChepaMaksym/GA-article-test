# Test and CI audit - USA26-09 final rejection

```text
TEST_STATUS: INSUFFICIENT_FOR_SCIENTIFIC_CLAIMS
CI_STATUS: NO_AUTHENTICATED_CURRENT_HEAD_PASS
```

## Positive findings

- exact Split is checked against brute force on a small instance;
- permutation closure and basic lambda transitions are tested;
- deterministic initial populations are checked;
- a small workers 1/2 smoke comparison exists.

## Blocking findings

- no test of the complete paper Algorithm 1 transition;
- no STX, diversity, intersection, enrichment, diversification or 100/1000
  education schedule oracle;
- worker test omits workers 4 and the full confirmatory ledger;
- no statistical-gate tests, negative scientific controls or mutation tests;
- code used `ceil(0.75*n)`, which permits 23/30 although the protocol requires
  24/30;
- no accounting test for surrogate proposals, cache hits/misses and actual
  Split computations;
- the CI matrix uploads profile files but has no binder that compares digests
  across jobs;
- dependencies are range-based rather than pinned;
- no fail-closed final status, artifact manifest, coverage or static audit;
- no GitHub check/status context is authenticated for the audited head.

Because the candidate fails the scientific OLD gate, its executable source and
workflow are removed rather than repaired into a different unpublished
algorithm under the same candidate identifier.

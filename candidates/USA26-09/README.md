# USA26-09 - rejected min-max mTSP candidate

## Final decision

```text
USA26-09: REJECTED_INVALID_PUBLISHED_ENDPOINT_MAPPING
OLD: FAIL_METHOD_AND_ENDPOINT_EQUIVALENCE
HYBRID: BLOCKED_NOT_AUTHORIZED
MASTER THESIS: BLOCKED
PR #19 numerical evidence used: false
```

The candidate is Mahmoudinazlou and Kwon, *A hybrid genetic algorithm for the
min-max Multiple Traveling Salesman Problem*, Computers & Operations Research
162 (2024) 106455, DOI `10.1016/j.cor.2023.106455`.

## Why the candidate is rejected

The published `HGA-avg=1.82` cell for Set I, `N=50`, `m=10` is an average over
100 independently generated uniform instances, with HGA executed ten times for
each instance. The reconstructed protocol used one fixed instance and 30 search
seeds, then compared its median to the published multi-instance mean.

The fixed instance also has nearest-neighbor Split objective
`1.8288547696784496` before HGA evidence is considered. Therefore proximity to
`1.82` cannot validate the reconstructed OLD.

The source-tree OLD further omits material paper components: variable
`mu/lambda` population control, diversity sorting, Similar Tour Crossover,
intersection removal, enrichment, 100/1000-step adaptive education,
diversification and the published stopping rule. It is a useful experimental
optimizer, but not a reproduction of Algorithm 1.

HYBRID is not evaluated because OLD failed. Its variable amount of uncounted
surrogate proposal search would also make logical-NFE comparison unfair without
a complete effort ledger.

## Cleanup

Executable USA26-09 implementation and candidate workflow are removed from the
accepted evidence surface. The source manifest, rejection documents and
`PROFESSOR_AUDIT_TEMP.md` remain for auditability.

The next candidate must branch directly from
`research/EU26-07-reset-jump-verification`, not from this rejected branch.

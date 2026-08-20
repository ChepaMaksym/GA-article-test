# Candidate loop through USA26-09

## EU26-24 - Preferendus floating-wind design

Decision: `REJECTED_OLD_REPRODUCTION / HYBRID_BLOCKED_NOT_CREATED`.

Formula and feasibility checks passed, but the preregistered stochastic OLD
coverage gate failed. Executable files were removed and the rejection record
was retained.

## USA26-09 - min-max mTSP HGA

Decision:

```text
REJECTED_INVALID_PUBLISHED_ENDPOINT_MAPPING
OLD = FAIL_METHOD_AND_ENDPOINT_EQUIVALENCE
HYBRID = BLOCKED_NOT_AUTHORIZED
```

The paper's `1.82` cell averages 100 generated instances and ten HGA runs per
instance. The reconstruction used one fixed instance and a 30-seed median; its
nearest-neighbor baseline already equals `1.8288547696784496`. The source-tree
OLD also omits material HGA components, and HYBRID used unequal uncounted
surrogate effort.

No PR #19 numerical evidence was used. The next candidate starts from the
verified PR #8 base.

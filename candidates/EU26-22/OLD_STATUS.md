# OLD status and novelty gate

```text
source identity: PASS_PINNED_SOURCE
dimension gate: PASS_100_TO_7129
EU/USA affiliation gate: PASS_UK_AFFILIATION
adaptive control gate: PASS_IN_RUN_SELF_ADAPTIVE_CROSSOVER
formula kernel: PASS_8_TESTS
worker fixed-tape invariance: PASS_LOCAL_1_2_4
released runner: BLOCKED_RUN_M_TYPO
seed ledger: BLOCKED_NOT_PUBLISHED
paper numeric endpoint: NOT_YET_FROZEN
OLD numeric reproduction: NOT_RUN
HYBRID: BLOCKED_BY_OLD
```

The next executable step is not HYBRID. It is an outcome-blind amendment that selects one paper dataset/cell, authenticates its exact source bytes, defines the source-compatible runner repair, freezes RNG/split semantics and states a numeric acceptance rule.

After OLD numeric PASS, the accepted data, classifier, objectives, population, initial population, seed ledger and logical budget remain fixed. Only the MOEA-ISa Jaccard/state-action crossover control may be replaced by PR #8 reset self-adjusting `(1+(lambda,lambda))` control:

```text
p = lambda / D
c = 1 / lambda
lambda <- verified success-based shrink/growth/reset
```

The primary thesis claim requires paired evidence that quality is preserved within a preregistered margin, typical feature cardinality is not worsened, and matched quality is reached with fewer logical evaluations or iterations. Wall-clock time is secondary and reset-specific causality requires a reset/no-reset ablation.

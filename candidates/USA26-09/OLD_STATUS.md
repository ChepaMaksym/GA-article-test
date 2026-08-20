# USA26-09 OLD verification

## Decision

```text
PASS_OLD_COMPATIBILITY
```

The OLD gate was completed before the 30-seed confirmatory HYBRID campaign.

## Verified components

- exact min-max objective and route-cost micro-oracles;
- exact dynamic split against brute force on small instances;
- valid permutation closure for crossover and mutation;
- OLD roulette formula `p_i=w_i/sum(w)`;
- `w_i(0)=100` and +1 update only after strict improvement;
- deterministic repeat for a fixed seed;
- identical initial-population digest for paired OLD/HYBRID runs;
- identical scientific digest with 1, 2, and 4 workers.

## External anchor and limitation

The paper reports HGA average objective `1.82` for Set I, `N=50`, `m=10`. It also states that this cell averages 100 independently generated uniform instances and ten HGA executions per instance. The corresponding seed ledger is absent from the paper and author repository.

Consequently, this work does not label its result an exact Table-2 replay. The outcome-blind compatibility rule was:

```text
30/30 complete runs
median final objective <= 1.840
absolute gap from published 1.82 <= 0.020
worker invariance required
```

## Confirmatory OLD result

```text
runs: 30/30
median final objective: 1.8290005027
mean final objective:   1.8312617572
minimum:                1.8288547697
maximum:                1.8363077563
absolute median gap:    0.0090005027
matched-target coverage: 16/30
median capped target NFE: 1432.5
```

Every gate passed. This authorized the separately frozen HYBRID campaign.

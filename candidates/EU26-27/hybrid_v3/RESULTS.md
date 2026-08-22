# EU26-27 HYBRID v3 — bounded-control transfer with development/holdout separation

Status: `T3_DEVELOPMENT_SELECTED_CAP20 / T3_H1_FAIL`.  
Study type: **source-grounded bounded-control transfer with independent confirmation**, not numerical reproduction of the source paper.

## Source grounding

Primary source: Mario A. Hevia Fajardo & Dirk Sudholt, *Theoretical and Empirical Analysis of Parameter Control Mechanisms in the (1+(lambda,lambda)) Genetic Algorithm*, DOI `10.1145/3564755`.

The source study shows on `Jump_k` that self-adjusting `lambda` can grow to an ineffective maximum and that smaller upper bounds can improve behavior. This PR transfers only that **bounded-control proposition** to offspring-count control inside the exact-reproduced TwoRate GSEMO baseline. The problem, algorithm and success signal differ from the source study, so the relevant hypothesis concerns transferability.

## Frozen controller family

The paper-era TwoRate mutation-rate adaptation is unchanged.

```text
lambda_floor = 10
F = 1.5
success: lambda <- max(lambda/F, 10)
failure: lambda <- min(lambda*F^(1/4), lambda_cap)
cap grid = {15, 20, 30, 40, 60, 100}
```

The v2 ledger `28001..28030` is used as development data only. The deterministic selection rule chooses the cap with the largest paired median relative FE reduction; exact ties prefer the smaller cap. Independent holdout seeds are `29001..29030`.

## Hypotheses

### T3-Hdev — development selection criterion

> At least one frozen source-motivated cap yields a positive paired development effect and can therefore be selected by the frozen rule.

This is a **development criterion**, not confirmatory evidence.

### T3-H1 — independent transfer/generalization

> The development-selected cap reduces paired FE to complete Pareto-front discovery relative to exact-reproduced OLD on the untouched holdout; PASS requires the lower 95% bootstrap bound to exceed zero.

## Integrity gates

- v3 controller/selection unit tests: PASS
- independent holdout ledger exactly `29001..29030`: PASS
- holdout disjoint from v1/v2 ledgers: PASS
- exact upstream GSEMO / IOHexperimenter revisions and critical blobs: PASS
- additive source patch: PASS
- build: PASS
- patched `TwoRate` exact PR #23 / Zenodo regression: PASS
- all six frozen cap profiles smoke-run: PASS
- development grid completed for all caps and 30 retired v2 seeds: PASS
- selected cap persisted before first holdout run: PASS
- OLD and selected V3 full-Pareto completion on holdout: 30/30 and 30/30

These gates establish execution integrity. They do not determine T3-H1.

## Development-only selection

Paired median relative FE reduction on retired v2 seeds:

```text
cap 15:  +5.890756%
cap 20: +15.358279%  <- selected by the frozen rule
cap 30:  -7.224697%
cap 40: +10.231962%
cap 60:  +2.525843%
cap 100: +2.894851%
```

`T3-Hdev` is satisfied in the limited development sense and the deterministic rule selected `HybridCap20`. These values are not independent evidence of superiority.

## Independent holdout

```text
selected controller: HybridCap20
OLD median FE:        57,563.5
V3 median FE:         53,974.5
OLD mean FE:          59,719.4
V3 mean FE:           57,832.0

T3-H1 paired median relative FE reduction OLD -> V3: -1.263559%
T3-H1 95% percentile-bootstrap CI: [-15.884593%, +13.258223%]
bootstrap resamples: 50,000
bootstrap seed: 29029
T3-H1: FAIL
```

The lower marginal V3 median is descriptive only. It cannot override the preregistered paired statistic.

## Agreement with the source literature

Agreement class: **DEVELOPMENT_LEVEL_QUALITATIVE_ALIGNMENT / CONFIRMATORY_TRANSFER_FAILURE**.

The development ledger is qualitatively consistent with the source proposition that a smaller cap can help: caps 15, 20 and 40 show positive development effects, and cap 20 is best under the frozen rule. The effect does not generalize to the independent holdout. Therefore this experiment does not reproduce the source paper's favorable performance result and does not establish `HybridCap20` superiority.

## Scientific interpretation

The strongest result is methodological and empirical at the same time: under this frozen testbed, source-motivated parameter selection produced an apparently favorable development effect (`+15.36%`) that failed to survive an untouched stochastic ledger. This provides evidence for the need to separate mechanism development from confirmatory evaluation in adaptive evolutionary-algorithm research.

Post-hoc inspection may motivate a later, independently preregistered study, but cannot change T3-H1, the bootstrap rule or holdout composition.

## Claim boundary

Supported:

- bounded `lambda` control is grounded in prior parameter-control research;
- cap selection was frozen and completed before holdout execution;
- exact OLD behavior remained intact;
- T3-H1 failed on an independent ledger;
- development performance did not generalize under this protocol.

Not supported:

- numerical reproduction of Hevia Fajardo & Sudholt;
- superiority of cap 20;
- treating the lower marginal median as a confirmatory pass;
- generalization beyond the frozen OneMinMax/TwoRate/HV setting.

## Evidence identity

```text
workflow run: 32573546704
artifact: 9476099058
artifact SHA-256: 10dabff61802e9482d339742800949cacb25aad4298f87c35ad91b57d279bc98
```

The artifact retains the exact OLD regression report, all development and holdout raw `.dat` files, stdout/controller traces, selected-cap JSON, paired endpoint tables, statistical JSON and SVG evidence. The holdout is retired from future confirmation.

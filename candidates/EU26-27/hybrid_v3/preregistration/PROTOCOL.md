# EU26-27 HYBRID v3 preregistration

Stage: `RESEARCH_2 / HYBRID_REFINEMENT_2`.

This is a post-v2 development-plus-confirmation iteration. V1 (`27001..27030`) and v2 (`28001..28030`) outcomes are already known and cannot be used as new confirmatory evidence.

## Invariant OLD

- problem: OneMinMax
- dimension: `n=100`
- OLD algorithm: exact paper-era `TwoRate`
- initial `lambda=10`
- initial mutation-rate parameter: paper profile `p=1/n`
- adaptation metric: hypervolume
- exact GSEMO revision: `fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380`
- exact IOHexperimenter revision: `f223c682dff0749067d00b870f83ad754f7d96f5`
- canonical OLD regression: exact 101x100 first-hit matrix equality to PR #23 / Zenodo before any v3 result is accepted

## V3 controller family

The complete paper-era TwoRate mutation controller is preserved. V3 adds only offspring population-size control.

Common rule:

```text
lambda_floor = 10
F = 1.5
strict success = at least one generated offspring strictly improves current Pareto-front hypervolume

success: lambda <- max(lambda/F, 10)
failure: lambda <- min(lambda*F^(1/4), lambda_cap)
offspring count: floor(lambda + 0.5)
```

The candidate cap set is frozen before the v3 development run:

```text
lambda_cap in {15, 20, 30, 40, 60, 100}
```

No other algorithm parameter varies across the cap grid.

## Development set and deterministic selection

The already-retired v2 seed ledger `28001..28030` is reused **only as development data**. It is not counted as v3 confirmation.

For every cap and paired OLD run calculate

`r_i = (FE_OLD_i - FE_CAP_i) / FE_OLD_i`.

Selection rule, frozen before the development run:

1. require complete Pareto-front discovery for all 30 development runs;
2. choose the cap with the **largest paired median** of `r_i`;
3. exact tie: choose the smaller cap;
4. write the selected cap and all development statistics before starting holdout runs.

No manual cap choice is permitted after seeing development outputs.

## Independent confirmatory holdout

Holdout seeds are frozen in `holdout_seeds.csv` as `29001..29030` and must be disjoint from v1 and v2 ledgers.

Primary H1 compares exact OLD against the automatically selected v3 capped controller on paired holdout seeds.

Statistic: paired median relative FE reduction

`median((FE_OLD - FE_V3) / FE_OLD)`.

Uncertainty: deterministic 50,000-resample paired percentile bootstrap with bootstrap seed `29029`.

`H1 = PASS` only if:

- OLD completion = 30/30;
- V3 completion = 30/30;
- lower endpoint of the 95% bootstrap interval is strictly greater than zero.

Otherwise H1 fails. Marginal medians alone cannot make H1 pass.

## Mandatory execution gates

1. formula/selection/statistics unit tests;
2. v3 holdout is exactly `29001..29030` and disjoint from v1/v2;
3. exact upstream source/blob authentication;
4. additive source patch only;
5. patched `TwoRate` exact PR #23 / Zenodo regression;
6. all cap profiles compile and smoke-run;
7. complete development grid on retired v2 seeds;
8. deterministic cap selection written to artifact;
9. only then run the independent v3 holdout;
10. retain raw `.dat`, stdout/controller traces, selected-cap report, paired endpoints and statistical report.

Wall-clock time is diagnostic only. Function evaluations to complete the full Pareto front are the primary efficiency measure.

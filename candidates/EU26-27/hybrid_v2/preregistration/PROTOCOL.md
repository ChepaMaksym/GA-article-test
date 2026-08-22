# EU26-27 HYBRID v2 — baseline-preserving rollback preregistration

Date: 2026-08-22
Research tag: `RESEARCH_2 / HYBRID_REFINEMENT_1`
Parent OLD: PR #23 `PASS_SOURCE_NATIVE_OLD`
Parent negative evidence: PR #24 HYBRID v1 `H1 FAIL`

## Status and anti-cherry-picking rule

This is a prospective follow-up created after observing v1. It is not represented as part of the original v1 preregistration.

V1 confirmatory seeds `27001..27030` are retired. V2 uses a new holdout ledger `28001..28030`; no v2 confirmatory result may be selected or tuned using v1 seeds and then re-tested on the same seeds.

## Literature-grounded refinement

Bassin & Buzdalov's rollback modification of the one-fifth rule slows harmful population-size growth by keeping a base population size, counting unsuccessful iterations, and periodically rolling the active population size back to the base. Their algorithm uses `U=5`, initial `B=0`, initial growth span `Delta=10`, resets `B` and `Delta` after success, and increases `Delta` after each completed bad loop.

This project transfers that controller structure to the reproduced TwoRate GSEMO, but anchors it at the validated paper baseline `lambda=10` instead of the single-objective paper's initial `lambda=1`.

The original TwoRate mutation-rate controller remains unchanged.

## Frozen primary controller: HYBRID_ROLLBACK

Constants:

```text
F = 1.5        # verified PR #8 update factor, and inside the literature interval (1,2)
U = 5          # one-fifth rule
lambda_floor = 10  # exact-reproduced paper OLD population size
lambda_max = n = 100
Delta_initial = 10 # rollback literature
```

State:

```text
lambda_real = 10
lambda_base = 10
B = 0
Delta = 10
```

Strict success means at least one offspring would strictly increase hypervolume if added to the current Pareto archive, using the same HV metric frozen for OLD and v1.

Update after the unchanged TwoRate `r` adaptation:

```text
if strict_success:
    lambda_real = max(lambda_real / F, lambda_floor)
    lambda_base = lambda_real
    B = 0
    Delta = Delta_initial
else:
    B = B + 1
    if B == Delta:
        B = 0
        Delta = Delta + 1
    lambda_real = min(lambda_base * F^(B/(U-1)), lambda_max)
```

Executable offspring count is `floor(lambda_real + 0.5)`, clipped to `[lambda_floor, lambda_max]`.

## Frozen ablation: HYBRID_FLOOR

This isolates the effect of rollback from the independently justified `lambda >= 10` baseline floor:

```text
initial lambda_real = 10
success: lambda_real = max(lambda_real/F, 10)
failure: lambda_real = min(lambda_real*F^(1/4), 100)
```

No rollback state is used.

## Profiles

- `OLD`: exact TwoRate logic with fixed `lambda=10`.
- `HYBRID_ROLLBACK`: unchanged TwoRate `r` control + baseline-preserving rollback lambda control.
- `HYBRID_FLOOR`: unchanged TwoRate `r` control + floor-only one-fifth lambda control.

## New confirmatory holdout

Seeds: `28001..28030`, frozen in `seeds.csv` before v2 outcomes.

Each profile is run as a separate process with the same per-pair seed. This avoids cross-run global-RNG coupling and permits worker assignment in later portability tests without changing a run's random stream.

Problem/stopping rule:

```text
OneMinMax
n=100
HV adaptation metric
initial TwoRate p=1/n
full 101-point Pareto front completion
non-binding safety ceiling = 10,000,000 FE
```

All three profiles must complete 30/30 runs for a quality-valid comparison.

## H1 — primary efficiency hypothesis

Paired statistic:

`median_i((FE_OLD_i - FE_HYBRID_ROLLBACK_i)/FE_OLD_i)`.

Deterministic paired percentile bootstrap:

```text
50,000 resamples
bootstrap seed = 28028
95% two-sided interval
```

`H1 PASS` iff:

1. OLD completes 30/30;
2. HYBRID_ROLLBACK completes 30/30;
3. lower endpoint of the 95% bootstrap interval is strictly greater than zero.

## H2 — rollback-specific effect

Compare `HYBRID_FLOOR` to `HYBRID_ROLLBACK` using the same paired median relative FE reduction and bootstrap. Report `POSITIVE`, `NEGATIVE`, or `NO_CLEAR_EFFECT`. H2 cannot rescue a failed H1.

## Mandatory gates before v2 outcomes

1. unit tests for success, floor, bad-loop rollback, Delta increment, and success reset;
2. exact original upstream source/blob identity;
3. additive patch only; original `TwoRate` class body unchanged;
4. patched `TwoRate` must exactly reproduce PR #23's 101x100 Zenodo OLD matrix;
5. both v2 profiles deterministic smoke-run;
6. only then execute the new 30x3 holdout matrix;
7. save raw `.dat/.json`, controller stdout traces, paired CSV, report and graph.

## Decision boundary

If H1 fails, v2 remains negative evidence. No threshold, seed, F, floor, Delta, success definition or subset may be changed and then claimed as the same preregistered experiment.

If H1 passes, proceed to the predeclared portability/worker/load stage before making a final efficiency claim.

# EU26-27 HYBRID preregistration

Date: 2026-08-22
Research tag: `RESEARCH_2`
Parent OLD evidence: PR #23 `PASS_SOURCE_NATIVE_OLD`

## Outcome-blind design

This document is committed before any confirmatory HYBRID outcome is inspected.

The canonical OLD remains the exact paper-era `TwoRate` GSEMO reproduced in PR #23. HYBRID does **not** replace the OLD mutation-rate controller. It augments it with the verified reset self-adjusting one-fifth controller from PR #8, applied only to the offspring population size `lambda`.

This preserves the original TwoRate mutation mechanism while testing whether dynamic search effort can reduce function evaluations to full Pareto-front completion.

## Frozen controller

Let `L_t` be the real-valued controller state before generation `t`, with initial value `L_0 = 10`, update factor `F = 1.5`, lower bound `1`, and upper bound `n = 100`.

Strict success means that at least one offspring, when hypothetically added to the current Pareto archive, produces a strictly larger hypervolume than the archive before the generation. This uses the same HV metric already frozen for OLD.

Reset variant:

```text
if strict_success:
    L_{t+1} = max(L_t / F, 1)
elif L_t == n:
    L_{t+1} = 1
else:
    L_{t+1} = min(L_t * F^(1/4), n)
```

The executable offspring count for the next generation is `floor(L_{t+1} + 0.5)`, clipped to `[1,n]`.

No-reset ablation is identical except that the `L_t == n -> 1` reset branch is disabled.

The original TwoRate `r` update is executed unchanged every generation.

## Profiles

- `OLD`: unchanged TwoRate GSEMO, fixed `lambda=10`.
- `HYBRID_RESET`: unchanged TwoRate `r` adaptation plus reset one-fifth `lambda` control.
- `HYBRID_NO_RESET`: same as HYBRID_RESET with reset disabled.

## Paired seeds

Confirmatory comparison uses 30 independent per-run seeds, fixed before outcome inspection:

`27001..27030`.

Each profile starts each run from the same seed. Runs are executed one process per seed so scheduler/worker assignment cannot alter RNG state shared with another run.

The published OLD replay remains the separate canonical global-seed-10 / 100-run evidence from PR #23; the paired experiment is a new comparison protocol, not a replacement for the paper replay.

## Problem and stopping rule

- problem: OneMinMax
- dimension: `n=100`
- adaptation metric: HV
- initial mutation parameter: paper profile `p=1/n`
- initial `lambda=10`
- completion target: entire 101-point Pareto front
- safety ceiling: `10,000,000 FE` per run, non-binding by design

A profile fails the quality gate if any confirmatory run does not complete the Pareto front before the safety ceiling.

## Confirmatory hypotheses

### H1 — efficiency

Primary paired statistic:

`median_i((FE_OLD_i - FE_HYBRID_RESET_i) / FE_OLD_i)`.

Use a deterministic paired bootstrap with 50,000 resamples and bootstrap seed `27027`.

`H1 PASS` requires the lower endpoint of the two-sided 95% percentile bootstrap interval to be strictly greater than `0` **and** the quality gate to pass 30/30 for both OLD and HYBRID_RESET.

### H2 — reset-specific effect

Compare `HYBRID_RESET` with `HYBRID_NO_RESET` using the same paired statistic and bootstrap procedure. H2 is secondary and is reported as `POSITIVE`, `NEGATIVE`, or `NO_CLEAR_EFFECT`; it does not override H1.

## Mandatory implementation gates before confirmatory interpretation

1. PR #8 formula unit tests for success, grow, cap, reset and no-reset transitions.
2. exact upstream source/blob identity before patching.
3. patch is additive: original `TwoRate` class text is unchanged.
4. optional per-run seed plumbing leaves the default seed-10 behavior unchanged.
5. patched binary in `TwoRate` mode reproduces the exact PR #23 Zenodo matrix in a regression job.
6. HYBRID_RESET and HYBRID_NO_RESET compile and complete deterministic smoke runs.
7. no result may be called a speedup from wall-clock alone; primary efficiency is function evaluations.

## Later portability stage

Only after H1 result exists, repeat the frozen profiles on multiple OS/hardware/worker/load configurations. Per-run seeds remain fixed. Workers may distribute independent runs only; they must never split one run or one global RNG stream.

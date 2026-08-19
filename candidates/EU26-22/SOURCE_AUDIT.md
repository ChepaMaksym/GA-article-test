# Source audit

## Verified source behavior

`MOEAISa.m` initializes a binary population, computes ReliefF weights, bins the Jaccard similarity of two parents into 20 states, chooses one of 10 crossover cardinalities using a learned probability table, and then applies one weight-guided add/remove mutation.

For each observed state/action pair, `EnvironmentalSelection.m` counts an offspring as successful when neither parent has a better nondomination rank. The observed success rate is exponentially blended with `alpha=0.3`.

## Defects and ambiguities

### Runner defect

The released runner creates the string `FS = sprintf('FS%d',i)` but invokes `str2func(FS1)`. `FS1` is neither a quoted name nor the loop-created variable. A literal run therefore fails before the candidate can execute.

The only admissible executable correction is:

```matlab
str2func(FS)
```

It must be documented as a source-compatibility repair, not silently described as unmodified author execution.

### Run identity

The inner loop uses `r=1:30`, but does not pass `'-run',r`. The repository therefore does not bind each paper run to a reproducible RNG stream.

### All-zero parent state

The source computes intersection/union. Two all-zero parents give `0/0`, and the subsequent state lookup has no defined index. The clean-room verifier fails closed instead of inventing a state.

### Paper-result custody

No raw 30-run result ledger or complete comparison Pareto union is present. IGD/HV paper cells cannot be reconstructed only from the final source tree without first freezing the exact target and all required reference fronts.

### Environment

The source requires PlatEMO classes and MATLAB `relieff`. Historical MATLAB, Statistics and Machine Learning Toolbox, platform, thread and RNG versions are not locked.

## Decision

The candidate remains eligible for bounded OLD reconstruction because its paper-linked source and datasets are public and the adaptive formula is implementable. It is not yet eligible for a numeric success claim.

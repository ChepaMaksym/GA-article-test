# EU26-27 OLD profile freeze — two-rate GSEMO on OneMinMax

Date frozen: 2026-08-20

## Why AGSEMO was not selected

The first preregistered preference, AGSEMO, is not admitted to executable OLD
work. Zenodo record `7880836` contains complete AGSEMO result files but no
source code, and printed Algorithm 5 does not resolve all rate-inheritance and
extreme-point transition semantics without additional assumptions.

The preregistered fallback order therefore selects the first fully specified
profile:

```text
algorithm: two-rate GSEMO
indicator: hypervolume contribution
problem: OneMinMax
n: 100
paper offspring size: 10
initial rate multiplier r: 1
raw member: csv/om/TwoRateL10P1HVOneMaxD100.csv
```

No numerical token from the selected CSV was read before this freeze.

## Benchmark and archive

For a bit string `x in {0,1}^n`, maximize

```text
f1(x) = |x|_1
f2(x) = n - |x|_1.
```

The exact Pareto front has 101 objective points for `n=100`. The GSEMO archive
contains at most one representative for every objective pair. An offspring is
inserted if its objective pair is not already represented; on OneMinMax no two
distinct objective pairs dominate one another.

## Frozen two-rate transition

Start with one uniformly random bit string and `r=1`. Every generation creates
10 offspring. For each offspring, select a parent uniformly from the archive
present at the start of the generation.

- first five offspring: conditional standard bit mutation with `p=r/(2n)`;
- last five offspring: conditional standard bit mutation with `p=2r/n`;
- conditional mutation resamples until at least one bit is flipped;
- all ten objective evaluations count against the budget;
- all ten offspring are passed to the archive update.

The adaptation winner maximizes the one-generation hypervolume contribution
relative to the pre-generation archive. Hypervolume uses maximization and
reference point `(-1,-1)`. Ties are resolved uniformly.

For a lower-rate winner:

```text
r <- max(r/2, 1/2) with probability 3/4
r <- min(2r, n/4) otherwise.
```

For a higher-rate winner:

```text
r <- max(r/2, 1/2) with probability 1/4
r <- min(2r, n/4) otherwise.
```

The initial solution counts as one objective evaluation. A generation is not
started unless its complete ten-offspring evaluation block fits the remaining
budget.

## Raw endpoint — frozen before outcomes

The authenticated selected CSV has four metadata columns followed by 100 pairs
`found_j, First_hit_j`, and 101 data rows after its header. For run `j`, define

```text
complete_j = all 101 found_j entries indicate success
T_j = max over the 101 First_hit_j entries, if complete_j.
```

`T_j` is the number of objective evaluations required to discover the complete
OneMinMax Pareto front. The primary retained-artifact statistic is the median
of the 100 finite `T_j` values. Mean, standard deviation, quartiles and all 100
values are retained as diagnostics but cannot replace the primary statistic.

## Independent OLD campaign

- independent seeds: integers `270001..270100`;
- random generator: NumPy `PCG64DXSM`, pinned by the environment lock;
- maximum objective evaluations per run: `2,000,000`;
- target: all 101 Pareto objective points;
- same algorithm and accounting for every worker profile;
- required worker profiles: 1, 2 and 4;
- required OS profiles: Linux, macOS and Windows.

## Acceptance gates

1. selected archive and member hashes match the authenticated schema artifacts;
2. parser re-aggregation yields exactly 100 run endpoints and 101 front rows;
3. source/formula fixed-tape, objective, archive, indicator, tie and accounting
   tests pass;
4. all 100 independent OLD runs complete within the frozen budget;
5. exact scientific digest is identical for 1, 2 and 4 workers;
6. the 95% bootstrap interval for
   `median(T_independent) / median(T_raw)` lies wholly within `[0.90, 1.10]`;
7. the two-sample empirical Kolmogorov distance is at most `0.20`;
8. all required cross-machine CI jobs and the artifact binder pass.

Passing these gates authorizes only
`PASS_OLD_DISTRIBUTIONAL_COMPATIBILITY`. It is not exact historical seed replay.
Failure of any mandatory gate rejects EU26-27 and prohibits HYBRID.

## HYBRID prohibition

No executable HYBRID file, result, graph or positive novelty claim may be added
until all OLD gates above pass on the current commit.

# Hybrid 1 research hypotheses

## Research question

Can the reset self-adjusting `(1+(lambda,lambda))` parameter-control mechanism
from Hevia Fajardo and Sudholt improve the search layer of CHC-QX feature
selection while preserving the applied Census-Income prediction protocol?

The intervention is intentionally narrow:

- keep the Census-Income data, 60/20/20 source split, normalization, active
  sample, Decision Tree, and validation/test separation from OLD;
- replace only the CHC feature-mask search with reset self-adjusting
  `(1+(lambda,lambda))` search;
- use validation accuracy as the primary objective and fewer features only as a
  lexicographic tie-breaker;
- count logical feature-mask evaluations and compare algorithms under equal
  budgets.

The literature search found the reset mechanism and CHC-QX as separate lines of
work. No exact CHC-QX plus reset `(1+(lambda,lambda))` Census feature-selection
hybrid was found in the searched primary sources. This is a search result, not
an unconditional claim of worldwide novelty.

## Reproducibility amendment before the final Census campaign

The first three-seed pilot exposed that the public CHC-QX active-sampling
criterion contains a wall-clock-time ratio. Consequently, the chosen sample
size can change with hardware even when the seed is fixed. This amendment does
not use Hybrid 1 outcome quality to choose a better sample.

For the final seeds `1..10`, Hybrid 1 freezes the active-sample sizes observed in
the already passing OLD source ledger:

```text
seed: 1    2    3     4    5     6     7    8     9    10
size: 7482 7482 14964 7482 14964 14964 7482 14964 7482 14964
```

For each seed, the source random stream still generates the ten controlled
feature masks and all candidate instance samples in the original order. The
hardware-dependent timing decision is replaced only by selection of the
pre-frozen OLD size. The exact selected instance indices therefore remain
seeded and reproducible across machines.

This amendment is frozen before the final ten-seed Hybrid 1 campaign. It is
reported as `frozen_passing_old_size_ledger` in every applied result.

## H1 - applied quality non-inferiority

Across frozen seeds `1..10`, Hybrid 1 should preserve the strong OLD prediction
quality:

- median test accuracy must be at least `94.8455%` (OLD median `94.9455%`
  minus a preregistered `0.10` percentage-point margin);
- at least 8/10 runs must improve the all-feature baseline by at least `1.50`
  percentage points.

This hypothesis prevents a smaller subset or lower evaluation count from being
presented as an improvement if predictive quality is materially worse.

## H2 - sparse feature subsets

Conditional on H1 passing, the median number of selected features should be at
most `8`, the median of the frozen OLD source campaign. The primary comparison
is paired by seed.

## H3 - evaluation efficiency

At matched validation-fitness targets, Hybrid 1 should require at least 20%
fewer logical feature-mask evaluations than the instrumented OLD search. If a
run never reaches the target, it is censored at the common budget rather than
removed.

Until OLD has exact NFE instrumentation, H3 remains preregistered but cannot be
claimed as passed.

## H4 - local-optimum control on Jump

Jump is a mechanism-control benchmark, not the applied thesis endpoint.
A development pilot used seeds `1..50` to choose a nontrivial common budget.
The frozen confirmation ledger starts every run at the exact `Jump_3` local
optimum with `n=20`, budget `10000`, and seeds `101..150`:

- reset must improve success probability by at least `0.20` absolute;
- reset success count must be at least `1.50x` the no-reset count;
- at least one reset event must be observed.

This isolates whether the transferred controller performs the function for
which it was proposed: revisiting useful parameter regions instead of remaining
at maximum lambda near a local optimum.

## H5 - worker/core invariance

For identical seed, inputs, and budget, evaluation worker counts `1`, `2`, and
`4` must produce exactly the same:

- selected mask;
- fitness;
- logical NFE;
- lambda trajectory;
- reset count;
- acceptance and strict-success sequence.

Random offspring are generated in the coordinator thread and ordered mapping is
used for fitness evaluation. Runtime may differ; scientific output may not.
Campaign-level process workers `1`, `2`, and `4` must also preserve all Jump
rows exactly.

## H6 - no regression on OneMax

For `n=64`, seeds `1..20`, and budget `5000`, reset and no-reset variants must
both solve OneMax and produce the same evaluation count and final solution.
This verifies that the reset branch is dormant on the simple unimodal control
where maximum-lambda stagnation is not needed.

## H7 - critical semantic correctness

The implementation must pass fixed-tape and invariant tests for:

- nearest-half-up offspring rounding;
- `p=lambda/n` and `c=1/lambda`;
- one binomial mutation strength shared by all mutants in a generation;
- exact-bit mutation without replacement;
- selected-best-mutant plus crossover final pool;
- exclusion of parent copies from final selection;
- neutral acceptance but strict-success parameter control;
- success shrink, failure growth, and failure-at-cap reset;
- `1 <= lambda <= n` at every transition;
- no logical budget overshoot;
- empty Census feature masks receiving a dominated fitness;
- validation-only optimization and one final held-out test evaluation;
- exact active-sample size and indices under the frozen OLD seed ledger.

## Statistical reporting

The final applied campaign will report all per-seed rows, medians, bootstrap
95% confidence intervals, paired differences, selected-feature counts, NFE,
reset counts, and worker settings. A single lucky seed is never sufficient.

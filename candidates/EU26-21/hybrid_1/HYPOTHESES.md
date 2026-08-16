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

## Reproducibility amendment for the original ten-seed campaign

The first three-seed pilot exposed that the public CHC-QX active-sampling
criterion contains a wall-clock-time ratio. Consequently, the chosen sample
size can change with hardware even when the seed is fixed. This amendment did
not use Hybrid 1 outcome quality to choose a better sample.

For the original final seeds `1..10`, Hybrid 1 froze the active-sample sizes
observed in the already passing OLD source ledger:

```text
seed: 1    2    3     4    5     6     7    8     9    10
size: 7482 7482 14964 7482 14964 14964 7482 14964 7482 14964
```

For each seed, the source random stream still generated the ten controlled
feature masks and all candidate instance samples in the original order. The
hardware-dependent timing decision was replaced only by selection of the
pre-frozen OLD size.

## Extended paired amendment: seeds 1..30

The ten-seed result is retained as the first experiment. The strengthened H1
and the exact-NFE H3 experiment use a new, fully paired protocol frozen before
its execution:

- seeds `1..30`;
- exactly `14,964` active training instances for every seed, matching the
  authenticated executed author notebook endpoint;
- active indices generated in the public-source progressive-halving order;
- no wall-clock value used in any scientific decision;
- the same 50 source-density initial feature masks supplied to OLD and Hybrid 1
  for each seed;
- OLD source CHC parameters `f=10`, outer no-change limit `2`, and source HUX,
  distance adaptation, duplicate history, and restart behavior;
- Hybrid 1 practical budget `400` logical evaluations for H1-H2;
- Hybrid 1 budget `2,500` logical evaluations for H3;
- one final held-out test evaluation per optimizer result;
- 50,000 deterministic BCa bootstrap resamples.

This controlled profile is not presented as a hidden replacement for the
historical Table 2 experiment. Its purpose is a fair optimizer comparison after
the historical OLD source result was already reproduced.

## H1 - confidence-bound applied quality non-inferiority

The non-inferiority margin remains `0.10` percentage point:

```text
Hybrid test accuracy - paired OLD test accuracy >= -0.001
```

The primary H1 decision uses the one-sided 95% BCa lower confidence bound for
the paired median difference across seeds `1..30`:

- `PASS_CONFIDENCE_BOUND` if the lower bound is at least `-0.001` and at least
  24/30 Hybrid runs improve the all-feature baseline by `1.50` percentage
  points;
- `PASS_POINT_ONLY` if only the paired median point estimate meets the same
  margin and baseline-gain requirement;
- otherwise H1 fails.

A hypothesis failure is a scientific result and must not be converted into a CI
or implementation failure.

## H2 - sparse feature subsets

Under the paired 30-seed protocol, the median of

```text
Hybrid selected-feature count - OLD selected-feature count
```

should be at most zero. Accuracy remains the primary objective; sparsity cannot
compensate for failure of H1.

## H3 - exact logical evaluation efficiency

Every wrapper objective call is counted exactly:

- `OLD active NFE`: every source CHC feature-mask evaluation using the active
  sample;
- `OLD full-validation NFE`: each unique population member reevaluated by the
  outer CHC-QX wrapper on all training instances;
- `OLD optimizer NFE`: active NFE plus full-validation NFE;
- `Hybrid NFE`: initial masks plus all mutation and crossover evaluations.

Shared data preparation, construction of the active sample, baseline scoring,
and the one final held-out test evaluation are reported separately and are not
used to make one optimizer appear faster.

Matched validation targets are:

```text
0.945, 0.946, 0.947
```

The primary target is `0.946`. First-hit NFE is recorded. Failure to reach a
target is censored at the common `2,500`-evaluation budget rather than removed.
For a point-estimate H3 pass at the primary target:

- both algorithms must reach the target in at least 24/30 paired runs;
- Hybrid target coverage must be at least OLD target coverage;
- the paired median relative NFE reduction must be at least 20%.

A confidence-bound H3 pass additionally requires the one-sided 95% BCa lower
bound of the paired median relative reduction to be at least 20%.

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
- exact active-sample size, indices, initial-mask digest, and NFE accounting in
  the paired protocol.

## Statistical reporting

The extended campaign reports all 30 paired rows, medians, means, BCa 95%
confidence intervals, one-sided lower confidence bounds, selected-feature
counts, exact logical NFE, target coverage, censored observations, active-sample
digests, and initial-mask digests. A single lucky seed is never sufficient.

Methodological references:

- Altarabichi et al., *Fast Genetic Algorithm for feature selection - A
  qualitative approximation approach*, DOI `10.1016/j.eswa.2022.118528`;
- Hevia Fajardo and Sudholt, *Theoretical and Empirical Analysis of Parameter
  Control Mechanisms in the (1+(lambda,lambda)) Genetic Algorithm*, DOI
  `10.1145/3564755`;
- FDA, *Non-Inferiority Clinical Trials* guidance, used only for the general
  principle of a predeclared margin and confidence-bound decision;
- NIST/SEMATECH e-Handbook bootstrap guidance and BCa bootstrap documentation.

# Prospective common-objective bridge protocol

Frozen on **2026-08-23**, before implementation or inspection of any outcome
for seeds `41001..41030`.

## Research classification

This is a prospective confirmatory follow-up informed by the already observed
source-compatible and corrected EU26-21 results. Those historical rows remain
immutable retrospective context; they are not pooled, renamed, or reused in
the new estimators.

The comparator is a **harmonized pinned-source CHC feature-mask search**. It
reuses operator and state-transition semantics from the pinned public source,
but it is not the full printed CHC-QX/Algorithm 1 profile: the bridge removes
the learned instance-selection stage and the source chunk/full-validation
controller so both search arms receive exactly the same objective.

The parameter-control basis is Hevia Fajardo and Sudholt, *Theoretical and
Empirical Analysis of Parameter Control Mechanisms in the
`(1+(lambda,lambda))` Genetic Algorithm*, DOI `10.1145/3564755`. The
feature-selection context is Altarabichi et al., *Fast Genetic Algorithm for
feature selection - A qualitative approximation approach*, DOI
`10.1016/j.eswa.2022.118528`.

## Confirmatory hypothesis

> Under the frozen corrected official-UCI bridge, the reset-disabled
> self-adjusting `(1+(lambda,lambda))` GA will preserve final held-out weighted
> balanced accuracy relative to the harmonized pinned-source CHC feature-mask
> search within `-0.001` and will achieve a larger normalized area under the
> best-so-far validation-WBA trajectory over exactly 400 objective calls. The
> joint claim requires both confidence-bound gates.

Reset is disabled. This experiment tests the transferred self-adjusting search
layer, not a reset effect.

## Frozen common protocol

- Official UCI `census-income.data`: 199,523 rows, SHA-256
  `3676a81db7d3528f3f8b9f3c699d0f0aa28db45e6e994fa0b8ed38327539ee86`.
- Official UCI `census-income.test`: 99,762 rows, SHA-256
  `98402b1ab879573d0a7f38a699a40258080e25e33d3401e7bf9c96d3fa0fab8c`.
- Raw instance-weight index 24 is excluded from the predictors and supplied as
  sample weight. The predictive mask has 40 bits.
- Seeds are exactly `41001..41030`, in ascending order. Split and search
  randomness vary by seed; the official held-out test file is fixed.
- Each pair shares its split, active 14,964-row sample, preprocessing, weighted
  objective, and the same ordered 50 initial masks.
- After those shared masks are constructed, CHC uses an isolated Python-random
  stream and lambda uses an isolated NumPy `default_rng` stream; each is seeded
  with `seed + 1000003`, and neither arm consumes the other's RNG state.
- Fitness is lexicographic:

  ```text
  (validation weighted balanced accuracy, -selected_feature_fraction)
  ```

  If two queried masks have exactly the same two-component fitness, the common
  terminal winner is the one evaluated at the earlier objective-call index.
  This makes the single official-test mask unique without test information.

- Each arm consumes exactly 400 logical objective calls. Calls are not
  cached; duplicate masks still consume a call. No scientific early stopping
  is allowed. An empty-mask call uses its frozen shortcut fitness and still
  consumes one logical call even though it does not fit a classifier.
- The CHC arm evaluates fresh offspring in their generated list order. If the
  next generated batch crosses the cap, it evaluates exactly the prefix ending
  at call 400, records those queries, skips the partial generation's population
  and distance update, and terminates. Ordinary CHC population selection uses
  stable first-in-order resolution for exact two-component ties in the
  parent-plus-offspring sequence.
- The lambda arm preserves paired mutation/crossover batches and truncates only
  the final offspring count when required by the remaining even budget. Its
  initial-parent and within-generation exact-best ties use uniform selection
  from the isolated, seeded arm-local NumPy RNG stream.
- Lambda starts at 1, remains in `[1,40]`, uses `F=1.5`, `p=lambda/40`,
  `c=1/lambda`, nearest-half-up offspring rounding, strict-success shrink and
  failure growth. Reset is `false`, and the required reset count is zero.
- The final mask for each arm is the lexicographic best among the first 400
  queried masks, not a mask selected with test information.
- The official test is evaluated exactly once per seed and arm after the full
  search trace and final mask are frozen. The classifier is fitted on the
  internal 80% training partition, preserving corrected-profile semantics.

## Efficiency estimand

For arm `a`, seed `i`, and objective call `k`, define

```text
b[a,i,k] = max validation_WBA[a,i,j] for j <= k
AUC[a,i] = sum(b[a,i,k], k=1..400) / 400
```

This is a discrete normalized area under the best-so-far validation-WBA curve
per logical objective call.
It is not ROC-AUC, test-set AUC, wall-clock speed, or classifier-fit cost
normalization. A post-initial AUC for calls `51..400` is reported only as a
descriptive sensitivity because the shared first 50 calls contribute no paired
difference.

## Statistical decision order

All contrasts are paired by seed. The analysis uses the paired median, 50,000
deterministic BCa resamples, analysis seed `41031`, and a two-sided 95%
interval.

1. Quality difference:

   ```text
   official-test WBA(lambda no-reset) - official-test WBA(CHC)
   ```

   `PASS_NONINFERIORITY` requires the lower 95% BCa endpoint to be strictly
   greater than `-0.001`.

2. Efficiency difference:

   ```text
   AUC(lambda no-reset) - AUC(CHC)
   ```

   It is confirmatory only after quality passes. `PASS_AUC_SUPERIORITY`
   requires its lower 95% BCa endpoint to be strictly greater than zero.

3. `PASS_JOINT_BRIDGE_CLAIM` requires both gates. Feature count is secondary
   and cannot rescue a failed quality gate.

A negative or null hypothesis decision is a valid scientific result and must
leave protocol-valid CI green. Missing seeds, malformed traces, hash mismatch,
test leakage, or an incomplete artifact ledger make the evidence not evaluable;
they are not scientific failures.

## Claim boundary

Even if both gates pass, the allowed conclusion is limited to evaluation
efficiency of these two harmonized search components on this Census protocol.
The experiment cannot establish reset benefit, wall-clock speedup, literal
printed CHC-QX reproduction, causal superiority of lambda adaptation alone,
worldwide priority, or cross-dataset generality.

The machine-authoritative contract is [`protocol.json`](protocol.json). Its Git
containing commit and SHA-256 are recorded by CI and must be copied unchanged
into every per-seed result and final evidence manifest.

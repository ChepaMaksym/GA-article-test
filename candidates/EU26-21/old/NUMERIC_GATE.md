# EU26-21 Census-Income OLD numerical gate

This gate is frozen **before** executing the ten-seed source campaign. It applies only to OLD and cannot authorize HYBRID by itself.

## Literal paper endpoint

Table 2 reports the median and standard deviation over 10 runs for Census-Income:

- baseline Decision Tree test accuracy: `92.87%`;
- CHC test accuracy: `94.63% ± 0.35`;
- CHC-QX test accuracy: `94.94% ± 0.07`.

The executed author notebook additionally records one unseeded CHC-QX example:

- meta-model sample size `14,964`;
- validation fitness `0.9491` at printed generation `60`;
- test accuracy `94.96%`;
- selected feature indices `[12, 16, 17, 19, 40]`.

The notebook output is an authenticated artifact endpoint; it does not reveal the historical random seed.

## Frozen source campaign

- Upstream commit: `6ac5a7ec77f8a7c096ab4d019254fcc897988fd6`.
- Dataset: pinned `data/census-income.data`.
- Algorithm: pinned author `Evolution.CHCqx` without parameter tuning.
- Classifier: `DecisionTreeClassifier(random_state=0)`.
- Data processing: author `Dataset` implementation, normalization enabled, `shuffle=False`, contiguous 60/20/20 train/validation/test split.
- CHC-QX parameters from the executed notebook:
  - population size `50`;
  - evolution-control frequency `f=10`;
  - controlled individuals `q=10`;
  - outer no-change limit `2`.
- Auditor seed ledger: integer seeds `1..10` in ascending order, applied to both Python `random` and NumPy. The paper does not publish historical seeds.
- Seed 1 is executed twice and must be exactly reproducible for every algorithm/result field except wall-clock time.
- Python and dependency versions are frozen in CI.

## Gates

### S0 - provenance and data structure

Every run must report identical upstream commit/blob hashes and:

- 199,523 observations;
- 41 feature variables and one target column;
- train/validation/test sizes 119,713 / 39,905 / 39,905;
- two encoded target classes;
- non-empty unique selected feature indices contained in `[0, 40]`.

### S1 - deterministic source replay

The repeated seed-1 result must exactly match the first seed-1 result for:

- selected feature mask and indices;
- validation fitness and test accuracy;
- meta-model sample size;
- CHC chunk count;
- number of recorded improvements;
- baseline validation/test accuracy.

Wall-clock time is excluded.

### S2 - baseline endpoint

The deterministic all-feature test accuracy must be within `0.02` percentage points of the paper value `92.87%`.

### S3 - CHC-QX median alignment

Both conditions must hold:

1. absolute difference between the observed ten-run median test accuracy and `94.94%` is at most `0.15` percentage points;
2. at least 8 of 10 runs reach at least `94.75%` test accuracy.

### S4 - run-to-run dispersion

The observed sample standard deviation of test accuracy, measured in percentage points, must be at most `0.20` and differ from the reported `0.07` by at most `0.15`.

This accommodates an unpublished historical seed ledger without accepting an unstable endpoint.

### S5 - qualitative improvement

- every completed CHC-QX run must be no worse than the baseline;
- at least 8 of 10 runs must improve over the baseline by at least `1.50` percentage points.

### S6 - source completion and invariants

All 10 seeds plus the repeated seed must complete without exception, timeout, empty log, empty feature mask, or invalid fitness. Meta-model sample size must be between 5,000 and the training-set size.

## Source decision

- `PASS_SOURCE_NUMERIC_ALIGNMENT` requires S0-S6 all pass.
- Provenance/determinism/invariant failures produce `BLOCKED_SOURCE_IMPLEMENTATION_OR_PROVENANCE`.
- Completed but numerically different campaigns produce `BLOCKED_SOURCE_NUMERIC_MISMATCH`.
- Incomplete runs produce `BLOCKED_SOURCE_RUN_FAILURE` or `BLOCKED_SOURCE_TIMEOUT`.

A source pass is necessary but not sufficient for `PASS_OLD_FULL`. The independent printed-paper implementation must still be completed and compared with source before any executable HYBRID can be introduced.

The gate, seed ledger, parameters, classifier, dataset, and tolerances must not be changed after campaign results are observed merely to force a pass.

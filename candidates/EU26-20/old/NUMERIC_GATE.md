# EU26-20 Colon OLD numerical gate

This document freezes the acceptance rule **before** the ten-run campaign is added to CI. It applies only to OLD. It does not authorize implementation of `hybrid/`.

## Published target

Nematzadeh et al., Knowledge-Based Systems 301 (2024) 112345, Table 5 and Section 5.4 state that results are based on the average of **10 runs** with stratified 5-fold cross-validation. For Colon they report:

- baseline overall accuracy: `0.69`;
- CMF-AGAwER mean overall accuracy: `0.94`;
- CMF-AGAwER mean subset length: `6`.

Table 8 reports Colon average NFE `788`. Its caption says 3 runs while the nearby prose says 10 runs. NFE is therefore retained as a diagnostic and cannot independently pass or fail the literal Table 5 reproduction.

## Frozen campaign

- Profile: pinned author-source compatibility profile.
- Upstream commit: `d24e61e78ac197ad75342e8f4be5d63d17bd9e7a`.
- Dataset: pinned `Datasets/Colon.xlsx`.
- Search space: pinned Colon `features.npy`, 128 unique features.
- Runs: exactly 10.
- Auditor seed ledger: integers `1..10` in ascending order. The paper does not publish its seeds, so this ledger is not claimed to be the historical ledger.
- Determinism check: seed 1 is executed a second time and must reproduce every algorithm/result field exactly.
- Classifier: decision tree with `random_state=42`.
- Evaluation: stratified 5-fold cross-validation.
- Source semantics: Python built-in `round()` offspring counts. The separate paper profile keeps the paper's `ceil()` formulas and must not be silently conflated with this campaign.

## Gates

### G0 - provenance and structure

Every run must report the same pinned commit and artifact hashes, 62 rows, 2000 raw features, class counts 22/40, and a 128-feature search space. Every selected subset must be non-empty, unique, and contained in the search space.

### G1 - deterministic replay

The repeated seed-1 result must exactly match the first seed-1 result for:

- best accuracy and selected feature sequence;
- subset length;
- precision, recall, F-score, and MCC;
- NFE, iterations, adaptive-event count;
- final crossover/mutation rates;
- first iteration and NFE reaching accuracy 0.94.

### G2 - baseline endpoint

All 10 runs must report baseline accuracy exactly `0.69`.

### G3 - final accuracy alignment

Both conditions must hold:

1. absolute difference between campaign mean and `0.94` is at most `0.03`;
2. the two-sided 95% Student-t confidence interval for the mean includes `0.94`.

This prevents a much higher or lower but systematically different endpoint from being mislabeled as a literal reproduction.

### G4 - subset-length alignment

Both conditions must hold:

1. absolute difference between campaign mean subset length and `6` is at most `1.5`;
2. the two-sided 95% Student-t confidence interval for the mean includes `6`.

### G5 - qualitative improvement

At least 8 of 10 runs must improve over the `0.69` baseline by at least `0.20`, and no run may finish below the baseline.

## Decision

`PASS_OLD_REPRODUCTION` is allowed only when G0-G5 all pass.

If G0 or G1 fails, the implementation/fixture is defective and must be repaired before interpreting numerical results.

If G0-G2 pass but G3 or G4 fails, the status is `BLOCKED_NUMERIC_MISMATCH`. The candidate remains OLD-only. It may be debugged against documented paper/source ambiguities, but parameters, seeds, tolerances, classifier, and dataset must not be tuned merely to force a pass.

If the mismatch remains after the bounded verification cycle, the candidate becomes `REJECTED_OLD_REPRODUCTION`; no executable hybrid may be added.

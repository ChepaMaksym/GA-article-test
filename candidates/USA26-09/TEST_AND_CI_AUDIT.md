# Test, portability and load audit

## Local result

```text
pytest: 10 passed
worker profiles: 1, 2, 4
worker scientific digest:
66a5c94da82f775ade5592feeaf1bb189e0c3c650a3dc303d78dbb2691fac8c9
status: PASS
```

The suite covers:

- Split versus brute-force partitioning;
- instance and initial-population digests;
- permutation closure;
- OLD roulette probabilities and updates;
- `p=lambda/n`, `c=1/lambda`, half-up offspring rounding;
- success, failure and reset-delay transitions;
- fail-closed invalid states;
- exact deterministic reruns;
- paired initial-population identity;
- 1/2-worker scientific equality, plus an external 1/2/4 profile.

## Load profiles

Secondary load campaigns use budgets 300, 750 and 1500. They are retained to show when the efficiency effect emerges and to prevent selective reporting of only the favorable budget.

## Cross-machine workflow

`.github/workflows/usa26-09-validation.yml` defines nine profiles spanning:

- Ubuntu 24.04, macOS 14, Windows Server 2022;
- Python 3.11, 3.12 and 3.13;
- 1, 2 and 4 workers.

Every profile runs the complete test suite and recomputes a frozen six-row scientific digest. A separate job checks low, medium and high NFE loads. CI status must remain `PENDING_CURRENT_HEAD_CI` until GitHub Actions completes on the committed head.

## Failure semantics

CI must fail on malformed permutations, invalid formulas, worker-dependent rows, wrong instance digest, missing results, changed frozen profile digest, or failed unit tests.

A scientifically negative result is not a CI error. Quality non-inferiority, coverage and NFE criteria are recorded as scientific decisions rather than hidden by retuning.

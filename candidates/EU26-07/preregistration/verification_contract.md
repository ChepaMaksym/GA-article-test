# EU26-07 verification contract

This contract was frozen before executing the full 500-run replay.

## Immutable primary fixture

- problem: `Jump_4`, `n=20`, maximize, target `f*=24`;
- algorithm: resetting self-adjusting `(1+(lambda,lambda))` GA;
- `lambda_0=1`, `lambda_max=20`, `F=1.5`;
- each generation uses real-valued `lambda`, offspring count `m`,
  `p=lambda/n`, and `c=1/lambda`;
- source-compatible rounding: Python ties-to-even;
- base seed: `816114841`;
- runs: `r=1..500`, effective seed `base_seed+r` for both legacy NumPy RNG
  and Python's `random` module;
- stopping: optimum found, after charging the complete generation;
- accounting: `2*m` logical evaluations per generation; no initial-parent
  charge;
- author source commit: `49949a55208359ac93b7110afb23ed276bda158d`;
- author raw SHA-256:
  `b2ac8c81efaf786823d49dcef26eeb20f0257ca7fe9e1e2394d02ca5e26dd9a6`.

## Frozen targets

The primary target is the complete ordered 500-row raw ledger. Summary
cross-checks are exact:

| Statistic | Target |
|---|---:|
| Runs | 500 |
| Mean evaluations | 108964.48 |
| Median evaluations | 84730 |
| 25% quantile | 32787 |
| 75% quantile | 150829 |

The raw file does not publish a standard deviation. The verifier reports both
population and sample standard deviations as derived diagnostics and must not
mislabel either one as a paper value.

## Gates

| Gate | Pass condition |
|---|---|
| H0 source freeze | Every required local author file matches its frozen SHA-256 and source commit/tree |
| H1 eligibility | Every row in `eligibility_audit.md` remains passing |
| H2 paper formula | Boundary, rounding, update, reset-delay, mutation, crossover, tie and accounting tests pass for `paper_algorithm3` |
| H3 profile isolation | Adversarial witnesses distinguish paper half-up from source ties-to-even and one-mutant from all-mutant final pools |
| H4 published-data integrity | Raw file has 500 ordered rows and exactly recomputes all four processed statistics |
| H5 source-native replay | Pinned author class reproduces all 500 raw rows for generations, evaluations, final rounded lambda, last p and solved flag |
| H6 clean-room replay | Independent `artifact_jump_optimized` implementation reproduces those same 500 rows exactly |
| H7 cross-language | Python and MATLAB/Octave agree exactly on fixed-tape policy and transition fixtures |

H5 and H6 are exact gates; there is no percentage tolerance. An environment
change that breaks the historical RNG sequence is a recorded incompatibility,
not a reason to widen tolerances or change seeds.

## Stop and claim rules

- Stop the full replay on the first mismatching run and preserve the mismatch.
- Do not tune code against later raw rows. A semantic correction requires a
  dated amendment and a fresh run from row 1.
- `PASS_TARGET_ARTIFACT_REPLAY` requires H0-H6.
- `PASS_PAPER_FORMULA_PROFILE` requires H2, H3 and H7.
- `PASS_FULL` remains forbidden because the frozen paper/source divergences
  are facts, not test failures that code can erase.

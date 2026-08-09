# EU26-11 verification report

Run date: 2026-08-09.

## Outcome

- Target artifact: **`PASS_TARGET_ARTIFACT_REPLAY`**.
- Source eligibility: **`PASS_SOURCE_ADAPTATION_GATE`**.
- Overall scope: **`TARGETED_DETERMINISTIC_FIGURE1_REPLAY_ONLY`**.
- Paper-level boundary:
  **`TARGETED_ARTIFACT_ONLY_NOT_FULL_REPRODUCTION`**.

The authenticated 128-by-20 point set produced L2-star discrepancy
`6.892638555983242e-05`. The independently calculated base-10 logarithm was
`-4.1616144949364955`, which reproduces Figure 1 `OPT-128`, 20D as `-4.16`.
The independently computed value and the authenticated inert `discr.pkl`
binary64 cell were identical at the recorded precision (absolute difference
`0.0`).

The exact ModularCMAES tag `v1.0.8`, commit
`ec517cafaca432444f781a1c463b43963bff05eb`, and tree
`4200fc05eaa1a8eac4632aee3d0950ddf62cc75c` passed all member hashes. Its
generation order is mutation, selection, recombination, adaptation; the
adaptation stage updates evolution paths, step size, covariance matrix, and
the eigendecomposition.

## Checks

The authenticated local Python suite ran 25 tests with zero failures, errors,
or skips. It covered immutable identities, strict text parsing, formula
fixtures, malformed and non-finite mutations, inert numeric-block extraction,
source identity, adaptation ordering, create-only reporting, and the claim
boundary.

GNU Octave was not installed in the local worker, so the independent Octave
formula gate is **`NOT_RUN_LOCAL_NO_OCTAVE`**. The candidate workflow installs
Octave, authenticates the same point-set bytes, evaluates the formula without
Python or SciPy, and binds its result to the Python report. This local absence
is not reported as a pass.

## Prohibited interpretation

This result does not read or replay the 2.7-GB `eaf.db`, BBOB runs, EAF curves,
AUC cells, performance comparisons, or the authors' execution environment.
`PASS_FULL`, `PASS_BBOB_EMPIRICAL`, and `PASS_AUTHOR_EXECUTION_REPLAY` remain
forbidden even when all CI checks pass.

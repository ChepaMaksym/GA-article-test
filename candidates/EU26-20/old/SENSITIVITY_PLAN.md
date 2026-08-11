# EU26-20 bounded OLD sensitivity study

This plan is frozen after the primary source and paper campaigns and before sensitivity implementation. It is diagnostic only. It **cannot** change, replace, or retroactively relax `NUMERIC_GATE.md`.

## Established primary results

The independent printed-paper profile completed all 10 preregistered seeds and reproduced the reported Colon mean accuracy, but not the preregistered subset-length tolerance:

- mean accuracy `0.941` vs paper `0.94` - aligned;
- mean subset length `8.2` vs paper `6` - primary gate blocked;
- mean NFE `870.8` vs paper diagnostic `788`.

The pinned author-source profile completed only 9 of 10 seeds. Seed 4 could not generate the required 10 diverse repository candidates at main-loop iteration 1 within 20,000 attempts. Among the 9 completed runs, partial means were accuracy `0.9444`, subset length `7.2222`, and NFE `966.67`.

No executable HYBRID code is allowed while this investigation is open.

## Question

Which documented paper/source ambiguity materially affects Colon subset length and source non-termination?

## Frozen variants

Each variant uses the same Colon data, published 128-feature search space, decision-tree 5-fold fitness, seed ledger `1..10`, and repeated seed 1. One factor is changed from the primary paper profile unless explicitly marked as a bundle.

### S1 - `legacy_mt19937_rng`

- Printed-paper operators, feature-vector geometry, `ceil()` counts, and 20-failure stop remain unchanged.
- Replace NumPy `Generator(PCG64(seed))` with the Python 3.9-era `RandomState(MT19937)` stream.
- The same `RandomState` supplies initial subsets and KMeans initialization, approximating the author environment's global `np.random` behavior.

Purpose: determine whether the unpublished historical RNG family/consumption order explains the subset shift.

### S2 - `source_rounding`

- Change only offspring counts from printed `ceil()` to source Python `round()` ties-to-even.
- Keep PCG64, feature-vector geometry, corrected roulette ledger, and 20-failure stop.

Purpose: isolate the material count divergence (`10` vs `8` initial crossover offspring at `Pc=0.9`).

### S3 - `source_stop19`

- Change only the no-improvement stop from 20 completed failures to the public source's effective 19 failures (`Tag` starts at 1 and exits at 20).
- Keep printed counts, PCG64, feature-vector geometry, and corrected roulette ledger.

Purpose: measure whether one missing mutation-only iteration explains reported effort/subset length.

### S4 - `numeric_identifier_geometry`

- Change only Algorithms 2-4/KMeans geometry from 62-dimensional feature vectors to one-dimensional numeric feature identifiers, matching what the public DataFrame iteration executes.
- Keep printed counts, PCG64, corrected roulette ledger, and 20-failure stop.

Purpose: isolate the source/paper geometry divergence and repository feasibility.

### S5 - `source_like_bundle`

Combine:

- legacy MT19937 stream;
- source `round()` offspring counts;
- source effective 19-failure stop;
- numeric-identifier geometry.

The known stale-index roulette defect is **not** included. Roulette uses all current population fitnesses as required by Eqs. 9-11. Repository generation remains bounded and fail-closed.

Purpose: test whether source-visible semantics, excluding an unequivocal coding bug, approach the paper table and reproduce source non-termination.

## Campaign and reporting

For every variant:

- run seeds `1..10` once plus repeat seed 1;
- record every success, repository-generation failure, process failure, and wall timeout;
- preserve all traces and artifact hashes;
- compute mean, sample SD, median, min/max, and two-sided 95% Student-t CI only when all 10 runs complete;
- report accuracy, subset length, NFE, iterations, and adaptive events;
- compare to `0.94`, `6`, and diagnostic NFE `788` using the unchanged primary criteria.

## Interpretation rules

- A sensitivity variant can be called `ALIGNED_SENSITIVITY_ONLY`; it cannot receive `PASS_OLD_REPRODUCTION`.
- If a single-factor variant explains the primary mismatch, the result identifies an underspecified implementation dependency. The primary paper profile remains blocked unless the paper clearly supports replacing the frozen interpretation.
- If only the source-like bundle aligns, the paper is not independently reproducible from its printed description.
- If numeric-ID geometry reproduces non-termination, that supports rejecting the raw source as a stable OLD implementation.
- No post-result seed selection, tolerance changes, parameter tuning, classifier changes, or subset-length tie-break may be introduced.

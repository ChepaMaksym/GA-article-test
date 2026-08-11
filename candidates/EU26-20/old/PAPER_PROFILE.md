# EU26-20 independent OLD paper profile

This document freezes the independent interpretation of Nematzadeh et al. before a full clean-room optimizer is implemented. It is part of `old/`; it does not authorize `hybrid/`.

## Purpose

The public Python file is useful for provenance, but it is a notebook export with material implementation defects and is not interchangeable with the printed algorithm. Quality OLD verification therefore requires two separate tracks:

1. `author_source_compatibility` - execute the pinned source with only experiment-selection/reporting repairs;
2. `paper_cleanroom_feature_geometry` - independently implement the equations, algorithms, and flow printed in the paper.

Neither track may be silently substituted for the other.

## Frozen paper-profile semantics

### Dataset and feature pool

- Colon dataset from the pinned author repository: 62 rows, 2000 input features, class counts 22/40.
- Published Colon `features.npy`: 128 unique candidate features.
- Published feature pool is used directly, as explicitly allowed by the author README. CEI/MI/Fisher preprocessing is not recomputed inside the GA reproduction.

### Fitness

- `DecisionTreeClassifier(random_state=42)`.
- `StratifiedKFold(n_splits=5, shuffle=False)`.
- Objective is mean overall accuracy rounded to two decimal places, matching the published source and reported table precision.
- Precision, recall, F-score, and MCC are recorded diagnostically.
- Every classifier evaluation increments NFE, including repeated feature subsets; no memoization may alter paper NFE accounting.

### Representation and geometry

- A solution is an ordered, non-empty list of unique feature identifiers.
- Initial solution length is sampled uniformly from integers 1..10.
- For Algorithms 2-4, a feature is represented by its 62-dimensional Colon data vector. Pairwise distances and KMeans operate on feature vectors, as required by the paper's multicollinearity rationale and numerical feature-vector example.
- The source instead iterates DataFrame column labels and clusters numeric identifiers. That behavior remains confined to `author_source_compatibility`.
- No feature scaling is added because the paper does not specify it.

### GA operators

- Roulette probabilities are recalculated from every member of the current population using Eqs. 9-11. The source typo `Fits[i]` inside `for j` is repaired to the paper-intended current-population fitness vector.
- Variable-length single-point crossover follows Eq. 12 and the one-feature special cases.
- Replacement mutation follows Eq. 13 and cannot insert an already selected feature.
- Paper offspring counts are used exactly:
  - `nc = 2 * ceil(Pc * nPop / 2)`;
  - `nm = ceil(Pm * nPop)`.
- Population size remains 10 after merge, stable descending sort, and truncation.

### External repository

- `repository_features` excludes features used by the parent population and the newly generated crossover/mutation populations in that iteration.
- `q = floor(sqrt(len(repository_features)))`, with a minimum of one cluster.
- KMeans uses `n_init=10`; its random state is deterministically drawn from the run's auditor seed stream. The paper does not publish KMeans initialization, so this is an explicit reproducibility resolution, not a historical claim.
- Radius is `max_population_distance / 2` (`beta=2`).
- Algorithm 4 generates 10 diverse candidates whose average distance from the parent population is greater than the radius.
- A finite attempt ceiling is only a fail-closed guard against an underspecified/non-terminating configuration; reaching it invalidates the run rather than relaxing the diversity threshold.
- The best current repository candidate is crossed with repository memory, both offspring are evaluated, and memory is updated only on strict improvement.

### Adaptation and stopping

- Initial `Pc=0.9`, `Pm=0.4`.
- Strict best-fitness improvement resets both rates and both stagnation counters immediately.
- Every five consecutive non-improving iterations changes `Pc -= 0.3` and `Pm += 0.2`, clipped to `[0,1]`.
- Offspring counts for the next iteration are always derived from the updated rates. This avoids the source ordering defect where reset rates and cached counts can disagree.
- Stop at the first of:
  - accuracy 1;
  - 20 consecutive non-improving iterations;
  - 100 completed iterations.

## Randomness and claim boundary

- Auditor seed ledger: integers 1..10. Historical seeds are not published.
- Python `random.Random(seed)` controls discrete parent/crossover/mutation/repository choices.
- NumPy `Generator(PCG64(seed))` controls initial population choices and derives KMeans random states.
- Seed 1 is repeated exactly as a determinism gate.

The clean-room campaign uses the same preregistered Table 5 targets and statistical alignment rules as `NUMERIC_GATE.md`, but its result must be reported separately from the source-compatible campaign.

A source-compatible pass alone is **not** sufficient for `PASS_OLD_FULL`. Full OLD quality requires:

- source provenance and deterministic campaign gates pass;
- independent paper-profile unit/invariant tests pass;
- independent paper-profile ten-run campaign completes;
- any source/paper numerical divergence is explicitly analyzed.

Until these conditions are satisfied, `hybrid/` remains documentation-only.

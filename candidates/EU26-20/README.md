# EU26-20 - CMF-AGAwER candidate rejected before HYBRID

Status: `REJECTED_OLD_REPRODUCTION`.

Hossein Nematzadeh, José García-Nieto, Ismael Navas-Delgado, José F. Aldana-Montes, **Feature selection using a classification error impurity algorithm and an adaptive genetic algorithm improved with an external repository**, Knowledge-Based Systems 301 (2024) 112345, DOI `10.1016/j.knosys.2024.112345`.

## Why the candidate was selected

- Applied high-dimensional biomedical feature selection.
- Explicit premature-convergence/local-optimum motivation.
- Adaptive crossover and mutation probabilities.
- External repository intended to preserve exploration.
- Colon has 2,000 task variables, far above the required 15.
- Public author implementation, datasets, and precomputed feature pools.
- Clear Colon target: baseline accuracy `0.69`, CMF-AGAwER mean accuracy `0.94`, mean subset length `6`.

## OLD verification completed

The verification used two non-interchangeable tracks:

1. pinned author-source compatibility profile;
2. independent clean-room printed-paper profile.

The author repository was pinned to commit `d24e61e78ac197ad75342e8f4be5d63d17bd9e7a`, with exact source/data/feature blobs authenticated.

### Independent printed-paper result

All 10 preregistered seeds completed and seed 1 repeated exactly.

- baseline accuracy: `0.69` - PASS;
- mean final accuracy: `0.941`, 95% CI `[0.92575, 0.95625]` - PASS against `0.94`;
- mean subset length: `8.2`, 95% CI `[5.99383, 10.40617]` - FAIL against the frozen mean-difference tolerance for target `6`;
- mean NFE: `870.8` vs paper diagnostic `788`.

Verdict: `BLOCKED_PAPER_NUMERIC_MISMATCH`.

### Pinned author-source result

- only 9/10 seeds completed;
- seed 4 could not generate the required diverse external-repository population within 20,000 attempts;
- partial means: accuracy `0.94444`, subset length `7.22222`, NFE `966.67`.

Verdict: `BLOCKED_SOURCE_REPOSITORY_NONTERMINATION`.

### Bounded sensitivity result

Five preregistered profiles tested legacy MT19937, source `round()`, effective stop after 19 failures, numeric feature-ID geometry, and a source-like bundle.

No single documented ambiguity reproduced both target accuracy and target subset length. The source-like bundle approached subset `6.375` only on 8 completed runs and failed repository generation on 2/10 runs.

Detailed evidence, gates, per-seed values, artifact digests, and final rationale are in [`old/OLD_STATUS.md`](old/OLD_STATUS.md).

## Final OLD/HYBRID decision

The candidate does not meet the required OLD quality gate:

- printed-paper accuracy reproduced, but reported subset length did not;
- public source was not stable over the ten-seed campaign;
- sensitivity analysis did not identify one defensible paper ambiguity that repairs the result.

Therefore:

- this PR must not be merged as a successful reproduction;
- no executable PR #8 hybrid may be added;
- `hybrid/` remains documentation-only;
- the next candidate must branch from the shared PR #8 base, not from EU26-20.

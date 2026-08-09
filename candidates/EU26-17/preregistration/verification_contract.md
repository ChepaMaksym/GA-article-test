# EU26-17 source-transition verification contract v1

Frozen: 2026-08-09, before implementation tests and without observing a
published-result replay.

Scope: **`FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY`**

Eligibility: **`HARD_FAIL`**

## Immutable sources

- Core auditor freeze: `heidmic/suprb` commit
  `2af04212216ffd6a01160167f50ee01e62b2b36c`, tree
  `59335a04a71c4a6e3ddf0914485549ae0d6198fa`.
- Algorithm-addition comparison point: the same repository at
  `cefd949488dbe23c030f17bb50b6c7c73a44ae3`, tree
  `0146522f95e1ae49cb2bfac1b082e972056e5ea6`.
- Experiment snapshot: `heidmic/suprb-experimentation` commit
  `5c7c87df854ce397533b1d4efcdf8758b3783047`, tree
  `07b5a6557130a00d30912675f971eac24cb67836`.
- Institutional full text SHA-256
  `f55862101aaf771c3ccedcbc98d66c57d41903a89eabaebf8bed3903c1044fa0`,
  exactly 3,303,306 bytes.

The core freeze is selected by the auditor because it precedes the CEC 2024
conference. It is not an author-pinned dependency: the experiment requirements
file names the mutable branch `heidmic/suprb@main`. No gitlink is claimed.

## Frozen transition

For a finite, nonempty fitness vector whose maximum is nonzero,

\[
gdm = \frac{\operatorname{mean}(fitness)}{\operatorname{max}(fitness)}.
\]

Defaults are `v_min=0.005`, `v_max=0.15`, mutation rate `pm=0.025`
bounded to `[0.001, 0.25]`, crossover rate `pc=0.75` bounded to `[0.5,
1.0]`, and both multipliers are `1.1`.

- If `gdm > v_max`, set `pm=min(0.25, pm*1.1)` and
  `pc=max(0.5, pc/1.1)`.
- If `gdm < v_min`, set `pm=max(0.001, pm/1.1)` and
  `pc=min(1.0, pc*1.1)`.
- Equality to either threshold changes neither rate.

The update runs once at the start of every SAGA1 generation after the current
population has been fitted and before elitism, selection, crossover, mutation,
replacement, and refitting.

The clean-room implementation must reject empty vectors, any non-finite value,
and zero maximum before division. The upstream methods have no such guard. This
is a fail-closed test-harness policy only and must not be described as upstream
behavior. A source-body probe may separately demonstrate the frozen upstream
behavior without weakening the clean-room contract.

## Gates

| Gate | Requirement |
|---|---|
| S1 source identity | Commits, trees, required paths, Git blobs, byte counts, SHA-256 values, method source/token/AST identities, and GPL-3.0 license text match the manifest. |
| S2 addition/freeze equivalence | The authenticated SAGA1 file and both target method identities match at the algorithm-addition and auditor-freeze commits. |
| S3 unmodified body probe | AST-extracted `calc_gdm` and `adjust_rates` bodies execute without edits in a synthetic class and match the clean-room transition for valid inputs. |
| S4 branch semantics | High, low, both equalities, interior no-change, and repeated updates match the frozen equations. |
| S5 clamping | Mutation and crossover rates never exceed their frozen bounds; cap/floor witnesses hit every bound. |
| S6 fail closed | Empty, NaN, infinity, zero-maximum fitness, invalid thresholds, invalid bounds, invalid rates, and nonpositive multipliers are rejected by the clean-room harness. |
| S7 cross-language | Python and MATLAB/Octave independently produce identical rate trajectories for the frozen cases within absolute tolerance `1e-12`. |
| P1 experiment facts | AST/text probes establish master seed 42, `SeedSequence(42).generate_state(8)`, eight splits, mutable `suprb@main`, ignored/absent raw `mlruns`, and no stronger provenance claim. |
| P2 dataset fact | The authenticated loader and CSV produce exactly 18 named PT inputs and 5,875 rows; authenticated paper text contains Table I's PT `18`/`5875` row. |
| C1 claim boundary | Every report retains `HARD_FAIL_ELIGIBILITY_UNCHANGED`, a null endpoint and tolerance, and all forbidden claims. |

Python is the source-identity and evidence orchestrator. MATLAB/Octave is an
independent clean-room transition implementation; it does not import Python
results as expected outputs.

## Outcome labels

Only `PASS_SOURCE_IDENTITY`, `PASS_SOURCE_METHOD_TRANSITIONS`,
`PASS_CROSS_LANGUAGE`, `PASS_PARKINSON_DIMENSION_FACT`, and
`HARD_FAIL_ELIGIBILITY_UNCHANGED` may be emitted.

`PASS_FULL`, `PASS_CEC_EMPIRICAL_REPLAY`, `PASS_LITERAL_PAPER_ENDPOINT`,
`AUTHOR_PINNED_EXPERIMENT_CORE`, and
`HISTORICAL_EXECUTION_REVISION_PROVEN` are forbidden. No formula result can
clear the G8, G9, G10, C2, or applied-status blockers.

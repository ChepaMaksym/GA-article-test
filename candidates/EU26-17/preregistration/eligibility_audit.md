# EU26-17 eligibility audit

Frozen: 2026-08-09, before implementing or running the EU26-17 validators.

Overall derivation: **`HARD_FAIL`**. This label follows the cohort gate
derivation, not a discretionary candidate label. Gate 8 has a decisive failure,
so the candidate is not `conditional_noneligible` even though several other
facts remain unresolved.

| Criterion | Status | Frozen evidence and consequence |
|---|---|---|
| Direct-only | unresolved | SupRB directly selects a subset of learned rules, but this artifact does not adjudicate whether a benchmark ML model-composition task satisfies the requested applied-domain interpretation. |
| C1 lawful full text | pass | The University of Augsburg repository provides the full paper; the retrieved object identity is frozen in the source manifest. |
| C2 at least 11 genuine decisions | unresolved | Table I's PT row says 18 inputs. Those are dataset features, not automatically 18 chromosome decisions. SupRB's solution chromosome selects members of a growing rule pool, but no immutable published result cell freezes its direct decision count. |
| G3 runtime GA control change | source-pass | `adjust_rates` changes mutation and crossover rates during a single run. |
| G4 not surrogate-only | source-pass | The changed rates are passed directly to the SAGA1 mutation and crossover operators. |
| G5 complete adaptation semantics | source-only | Exact defaults, bounds, branch conditions, timing, and clamping exist in the selected code. The paper itself describes the mechanism qualitatively and does not print these exact constants. |
| G6 complete GA pipeline | unresolved | Relevant source exists, but the experiment's mutable `suprb@main` dependency prevents binding the published run to the auditor-selected core snapshot. |
| G7 lawful reproducible inputs | unresolved | The experiment repository vendors and attributes the UCI-derived CSV, but this audit does not elevate repository-level GPL text into a definitive dataset-license determination for the historical object. Formula validation requires no dataset execution. |
| G8 literal numeric published target | **fail** | The empirical SAGA results are plots. The paper has no literal, unambiguous numeric SAGA1 endpoint with a complete protocol cell. Approximate prose observations are explicitly forbidden as targets. |
| G9 stochastic protocol and provenance | fail | Source expresses master seed 42, eight derived model seeds, and eight splits, but raw `mlruns` are ignored and absent. The dependency is `suprb@main`, not a core commit. |
| G10 cross-environment/source-native feasibility | fail | Clean-room transition testing is feasible, but an honest historical source-native paper replay is not: no author-pinned core revision, raw result bundle, or timely release binds code to figures. |

The decisive G8 failure alone forces `HARD_FAIL`. Passing later formula tests
cannot change any row in this audit or establish candidate eligibility.

## Prohibited target substitution

No number estimated from a paper plot is admissible. In particular, qualitative
or approximate prose about a percentage of runs or a rule count is not a target,
confidence interval, tolerance, or replay endpoint. Table I's `18` and `5875`
are permitted only as dataset-description facts, never as optimizer outcomes.

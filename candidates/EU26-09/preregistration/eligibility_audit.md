# EU26-09 eligibility audit

Audit date: 2026-08-09. This record was frozen before candidate-local verifier
implementation and before any source-native execution.

## Candidate and eligibility

- Mario Hevia and Dirk Sudholt, *Theoretical and Empirical Analysis of
  Parameter Control Mechanisms in the (1+(lambda,lambda)) Genetic Algorithm*,
  TELO 2(4), 2022, DOI `10.1145/3564755`.
- Qualifying EU affiliation: Mario Hevia is also affiliated with the University
  of Passau, Germany, in the paper. The University of Sheffield affiliation is
  not used for the EU gate.
- Direct optimization: the selected experiment optimizes OneMax directly at
  `n=100`, well above the minimum 11 decision variables. It is not inverse
  optimization, parameter estimation, or a surrogate-only task.
- Full evolutionary algorithm: the `(1+(lambda,lambda))` GA executes mutation,
  crossover, offspring selection, and replacement until the optimum is found.
- Within-run adaptation: a known one-fifth-style rule updates real-valued
  `lambda`; that value controls mutation probability `lambda/n`, crossover
  probability `min(1, 1/lambda)`, and both offspring population sizes during
  the run. The reset variant returns `lambda` to one after an unsuccessful
  generation at the upper cap.
- Legal artifacts: an author-hosted full manuscript is available, and the
  official repository contains a GPL-3.0 license.
- Numeric evidence: the selected raw file contains 500 seed-addressable rows
  and exact decimal footers, while the README records the producing command.

The subject, year, geography, direct-objective, dimension, full-GA,
within-run-control, legal-full-text, author-code, and numeric-evidence gates
pass for a bounded artifact study.

## Admission decision

Status: **`CONDITIONAL_EVIDENCE`**

Study status: **`TARGETED_ARTIFACT_REPLAY`**

Paper mapping: **`PAPER_FIGURE_CONTEXT_ONLY`**

The candidate is admitted only to authenticate and independently verify the
selected raw artifact, the source control transitions, cross-language formula
fixtures, and—if feasible—the exact deterministic source-native regeneration
of the artifact. The artifact's exact endpoint is not a literal table cell or
printed point in the paper.

## Mandatory conflicts and hard stops

1. The paper's Figure 5 states that OneMax means use 500 runs, but the exact
   values `196.336`, `895.264`, `100.0`, and `9.892` are repository-artifact
   values rather than literal paper text.
2. The paper algorithm specifies `ceil(lambda)` offspring. The Python class
   uses Python `round(lambda)`, whose half-integer rule is ties-to-even.
3. The paper links the repository but does not pin a commit or dependency
   environment. Commit `49949a5...` is an auditor-selected publication-era
   revision.
4. The repository has no requirements file or other dependency lock. A modern
   replay cannot prove the historical NumPy/SciPy environment.
5. The raw rows expose only final pre-update `lambda` and mutation probability,
   not each generation's complete control trajectory or RNG draws.
6. The source omits the initial-parent fitness evaluation from its evaluation
   counter and adds `2*round(lambda)` even when the sampled mutation strength
   is zero. These are artifact semantics, not silently normalized semantics.

No successful candidate-local check may clear these conflicts. `PASS_FULL`,
`PASS_LITERAL_PAPER_ENDPOINT`, and a historical-environment provenance claim
are forbidden.

## Timing disclosure

Candidate triage inspected the README command, selected raw file, its four
footer values, the associated source class, and the paper's OneMax figure
context before this freeze. The endpoint and exact-equality criterion were
selected before verifier implementation. No source-native replay was run, and
no tolerance was chosen from a replay deviation. Artifact totals and decimal
means are required to match exactly.

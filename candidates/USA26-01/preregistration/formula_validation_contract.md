# USA26-01 formula-validation contract

Frozen: 2026-08-06, before any full-matrix optimization run.

Status: **`FORMULA_VALIDATION_ONLY`**
Published-result gate: **`BLOCKED_INCONCLUSIVE`**

This contract authorizes unit, property, deterministic smoke, and
fixed-random-tape cross-environment tests. It does not authorize a claim
that the article’s Table 1 was reproduced.

## Frozen direct-optimization scope

- Functions: Ackley, Griewank, Rastrigin, Rosenbrock, Sphere. This is a
  requested five-function subset; the paper's unbounded Linear function
  is not included and no full-paper matrix claim is made.
- Dimensions: 2, 30, 100, 1000, with the 30-versus-10 source conflict
  recorded in the source audit.
- Initial population: independent \(\mathcal N(0,s^2I)\),
  \(s\in\{1,10\}\).
- Full population: 101; \(N=100\) non-elites plus one elite.
- MR groups: \(K=10\), group size 10.
- Selection: \(\eta_x=\eta_\sigma=0.5\), with replacement.
- Initial MRs: ten log-spaced values from \(10^{-3}\) through \(10^3\).
- Meta mutation: \(\tau=2\), \(\sigma'=\sigma 2^u\),
  \(u\sim U[-1,1]\).
- No crossover, constraint repair, clipping, or inverse model.
- Seeds: integer IDs 0 through 39 for every matrix row.
- Prospective budgets: 100/300/1000/2500 generations for
  dimensions 2/30/100/1000, respectively; the author-driver conflict is
  not silently resolved.

The complete Cartesian matrix is in `config/experiment_matrix.csv`; the
shared seed definitions are in `config/seed_ledger.csv`. Their cross
product defines 1600 prospective runs. Those runs have **not** been
executed by this scaffold.

## Formula-validation gates

| Gate | Requirement | Frozen tolerance |
|---|---|---:|
| Objective unit | Known global optima for all five functions | absolute `1e-14` for Ackley, exact/roundoff-free checks otherwise |
| Transition micro-oracle | Python and MATLAB/Octave match `fixtures/cross_env_step.json` for population, fitness, group deltas, and MRs | absolute `1e-12`, relative 0 |
| Elitism property | best objective never increases | `1e-12` numerical slack |
| MR property | every MR remains finite and strictly positive | exact predicate |
| Adaptation property | at least one MR changes in the deterministic smoke run | exact predicate |
| Determinism | repeated run in one environment with the same seed is bitwise equal | exact predicate |
| Evaluation accounting | exactly `1+G` full-population objective calls and `(N+1)(G+1)` row evaluations | exact integer equality |
| Protocol schema | exactly 40 unique configurations and seeds exactly `0..39` | exact set equality |

Cross-environment stochastic full runs are distributional comparisons,
not trajectory comparisons, because the RNG algorithms differ. Only the
fixed-tape one-generation transition is a deterministic cross-environment
gate.

## Why `PASS_FULL` is impossible at this stage

The paper, appendix, and tracked driver disagree on dimensions, seed
count, and budgets. The tracked result table contains preliminary
generation-500 values rather than the exact camera-ready Table 1 artifact;
for \(d=100\), std=10 its five GESMR entries differ from the final table,
but this is not a like-for-like failure. Author raw per-seed runs, an
exact published driver/result revision, and a dependency/RNG lock that
generated the camera-ready table are not available in the audited
revision. No equivalence margin can distinguish a faithful reproduction
from a different source-supported protocol.

Accordingly, passing every test in this folder means only that the
clean-room formula kernel is internally consistent. It must not be
recorded as a reproduced paper, a passed published endpoint, or a
`PASS_FULL` outcome.

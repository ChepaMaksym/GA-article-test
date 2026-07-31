# Preregistered MATLAB experiment specification

## Status and scope

This specification was frozen on **2026-07-30**, before inspecting any MATLAB reproduction outcome. It uses the article, the fixed repository commit `2c33060320f722e6bb737b607cf0b27a9aa4256c`, and the already published author archive `hyper.csv.zip`.

The goal is a minimal but defensible **independent statistical reproduction** of one author-recommended adaptive-GA setting with exactly 10 runs. It is not a bitwise replay: the author seeds and generated input matrices are unavailable.

The primary algorithm is paper-faithful. Released-code quirks are isolated in a predeclared diagnostic profile and may not be selectively enabled to rescue a failed result.

## Primary experimental question

Using the paper's recommended adaptive controls on ten new \(N=20\) DeGroot instances, does a clean-room MATLAB implementation reproduce the exact ten-run solution-frequency and checkpoint pattern in the predeclared author-archive cell?

The GA estimates the eligible weights in \(W\). It does not optimize its own hyperparameters.

## Cell selection, frozen before MATLAB outcomes

The selected author-archive cell is:

| Field | Preregistered value |
|---|---:|
| `Size` / \(N\) | 20 |
| `Ordinal` / bins | 10 |
| `Degree` / target external mean degree | 2 |
| `TimeSteps` / \(T\) | 6 |
| `Chromosomes` | 21 |
| `ProbSigma` | Medium |
| `MinMax` | Moderate |
| `Factors` / MultFactor | Moderate |
| `Iter` / all five stagnation horizons | 200 |
| Runs | 10 |

The GA-control part of this cell follows the article's final recommendation: at least 21 chromosomes, values near the medium/moderate levels, and 200 generations without improvement. The problem factors were fixed a priori to satisfy the greater-than-10 independent-variable requirement (\(N=20\)), keep the first reproduction computationally modest (degree 2), use the most informative published time horizon (\(T=6\)), and use a middle published ordinal precision (10 bins). No alternative cell may be substituted after outcomes are seen.

## Expanded controls: no hidden defaults

| Paper control | Full adaptive value |
|---|---:|
| `chromosomes` | 21 |
| `probb` | 0.1 |
| `factorb` | 5 |
| `maxb` | 0.5 |
| `iterb` | 200 |
| `probc` | 0.1 |
| `factorc` | 0.2 |
| `minc` | 0.01 |
| `iterc` | 200 |
| `probm` | 0.1 |
| `factorm` | 0.2 |
| `minm` | 0.01 |
| `iterm` | 200 |
| `sigma` | 0.5 |
| `factors` | 0.2 |
| `mins` | 0.01 |
| `iters` | 200 |
| `max_iter` | 100000 |
| `min_improve` | 0 |
| `min_dev` | 0 |
| `reintroduce` | `"elite"` |
| `iterr` | 200 |

`print_iter` and Julia's `power` argument are not paper hyperparameters and must not be treated as experimental controls.

## Author-archive target locked before reproduction

The exact reference records are the `hyper.csv` **row-identifier values** `"66401"` through `"66410"`, not physical text lines 66,401–66,410. With the CSV header counted, those records are physical lines 66,402–66,411; physical line 66,401 belongs to the preceding \(N=4\) cell.

| CSV row ID | Run | Time (s) | Objective | Reported iteration | Recovery RMSE |
|---:|---:|---:|---:|---:|---:|
| 66401 | 1 | 3.663482116 | 0 | 1000 | 0.134136098596866 |
| 66402 | 2 | 3.695114347 | 0 | 1000 | 0.144732676637536 |
| 66403 | 3 | 3.835917038 | 0 | 1000 | 0.111817214977136 |
| 66404 | 4 | 3.617216724 | 0 | 1000 | 0.186048183476261 |
| 66405 | 5 | 3.647215932 | 0 | 1000 | 0.123039168376503 |
| 66406 | 6 | 3.706485776 | 0 | 1000 | 0.0936160787647205 |
| 66407 | 7 | 3.817585217 | 0 | 1000 | 0.131955367840855 |
| 66408 | 8 | 3.721172115 | 0 | 1000 | 0.142370305519169 |
| 66409 | 9 | 3.646736808 | 0 | 1000 | 0.120454841816024 |
| 66410 | 10 | 7.258819332 | 0 | 2000 | 0.159262193065063 |

Traceability: local archive `../source/DeGrootGeneticAlgorithm/Simulation-Study-Data/hyper.csv.zip`, SHA-256 `41ca24820e044b91a93f7cd8d2c327d712ccad4cb486afc48f069ed316a2e9c4`.

Derived, frozen reference summaries are:

- perfect by generation 1000: \(9/10=0.9\);
- perfect by generation 2000: \(10/10=1.0\);
- median reported iteration: 1000;
- final objective: 0 in all 10 runs;
- recovery mean: 0.134743212907013;
- recovery median: 0.133045733218860;
- recovery sample standard deviation: 0.025728643223250;
- ordinary two-sided 95% one-sample \(t\) interval for the archived recovery mean: \([0.116338050296472,\ 0.153148375517555]\).

The recovery interval is derived from the predeclared author raw rows; it was not printed as a scalar interval in the article.

## Primary endpoints and pass rule

All four gates below must pass for the full adaptive, paper-faithful profile:

| Gate | Published/archive target | Preregistered acceptance rule with \(n=10\) |
|---|---|---|
| P1: perfect by 1000 | 9/10 = 0.9 | Exactly 9 of 10; this is the only attainable proportion within 5% relative error of 0.9 |
| P2: perfect by 2000 | 10/10 = 1.0 | Exactly 10 of 10; proportions below 0.95 fail |
| P3: median checkpoint | 1000 generations | Reproduced median in \([950,1050]\); on the 1000-generation reporting grid this means exactly 1000 |
| P4: final objective | 0 for all 10 | All 10 terminal paper objectives equal 0 within an absolute floating-point tolerance of \(10^{-12}\) |

Relative error is

\[
e_{\mathrm{rel}}=\frac{|\widehat z-z|}{|z|}.
\]

For the zero target, only the stated absolute tolerance is used.

For context, a two-sided 95% Clopper–Pearson interval for 9/10 is approximately \([0.555,0.997]\), and for 10/10 approximately \([0.692,1]\). These intervals show the low precision of ten runs; they do not replace the stricter, protocol-driven gates above.

The study-wide 67.7% success-by-1000 rate, 4.5% failure-by-100000 rate, maximum failed objective 0.02, and hardware-dependent runtime medians are context only. They mix many cells and are not valid substitutes for the exact selected-cell targets.

### Secondary recovery diagnostic

Recovery RMSE is scientifically important but is not a primary pass gate because:

- exact author instances and seeds are missing;
- many \(W\) matrices can have the same zero ordinal objective;
- the article does not publish a scalar interval for this exact cell.

The following are nevertheless frozen before MATLAB outcomes:

1. Report all ten Equation (4) values, mean, median, sample SD, and a 95% \(t\) interval.
2. Flag whether the reproduced mean lies inside the author-row-derived interval \([0.116338050296472,0.153148375517555]\).
3. Report the difference in means and a two-sided Welch 95% confidence interval using the ten author and ten MATLAB values.
4. Do not declare equivalence from a nonsignificant test and do not tune the GA to move recovery into the interval.

Wall-clock time is descriptive only and must include hardware, OS, MATLAB release, thread/pool state, and whether startup/JIT time is included.

## Independent data-generation protocol

The following fills only details absent from the paper. Every assumption is fixed now and must be reported as a reconstruction assumption.

### Random streams and seed ledger

Use MATLAB `RandStream('mt19937ar','Seed',seed)` and separate streams for instance generation, initial population, and GA operators.

| Run \(r\) | Instance seed | Initial-population seed | Operator seed |
|---:|---:|---:|---:|
| 1 | 202204501 | 202214501 | 202224501 |
| 2 | 202204502 | 202214502 | 202224502 |
| 3 | 202204503 | 202214503 | 202224503 |
| 4 | 202204504 | 202214504 | 202224504 |
| 5 | 202204505 | 202214505 | 202224505 |
| 6 | 202204506 | 202214506 | 202224506 |
| 7 | 202204507 | 202214507 | 202224507 |
| 8 | 202204508 | 202214508 | 202224508 |
| 9 | 202204509 | 202214509 | 202224509 |
| 10 | 202204510 | 202214510 | 202224510 |

For every configuration, reuse the saved instance and initial population for a run and reset the configuration's operator stream to that run's listed operator seed. Once adaptive trajectories diverge, this is not exact common-random-number pairing, but it gives identical inputs and deterministic starts.

Route every `rand`, `randn`, beta, permutation, and integer-selection draw
through the named stream; do not mix in MATLAB's global stream. Save the
complete initial and final operator-stream states, plus a SHA-256 digest of
the complete state immediately before and after every completed generation.
Seeds may not be discarded, replaced, or screened.

### Network

For each run:

1. Set \(N=20\), target external degree \(d=2\), and \(p=d/(N-1)=2/19\).
2. Sample a simple undirected Erdős–Rényi \(G(N,p)\) graph without external self-loops.
3. Reject and redraw until the graph is connected, with a frozen hard cap of
   `maxConnectivityAttempts=10000`. Record the accepted draw number. If no
   connected graph is found within the cap, fail the instance generation;
   do not change or replace the seed.
4. Verify minimum external degree is at least 1.
5. Define \(A\) by adding every self-link \(a_{ii}=1\).

The paper states Erdős–Rényi, target degree, connectivity rejection, and minimum degree. It does not state \(p=d/(N-1)\), directionality, library semantics, or a rejection cap. The simple-undirected rule and the 10,000-attempt cap are preregistered reconstruction controls. The generator records the method identifier `undirected-gnp-upper-triangle-v1`, \(p\), the accepted draw number, and the cap. The instance manifest exposes these choices as `NetworkGenerator`, `NetworkAttempts`, and `MaxConnectivityAttempts`.

### True weights and opinions

For each row \(i\):

1. Draw \(w_{ii}\sim\operatorname{Beta}(2,2)\), equivalent to the paper's target mean 0.5 and \(\kappa=\alpha+\beta=4\).
2. For every external neighbor \(j\), draw \(u_{ij}\sim\operatorname{Unif}(0,1)\).
3. Set

\[
w_{ij}=(1-w_{ii})\frac{u_{ij}}{\sum_{k\in J_i\setminus\{i\}}u_{ik}},
\]

and set structural zeros exactly to zero.

The paper identifies the beta distribution but not its software sampler.
Freeze the self-weight sampler as
`marsaglia-tsang-gamma-ratio-v1`: draw independent
\(G_{\alpha},G_{\beta}\sim\operatorname{Gamma}(2,1)\) with the local
Marsaglia–Tsang rejection algorithm and set

\[
w_{ii}=\frac{G_{\alpha}}{G_{\alpha}+G_{\beta}}.
\]

Thus the frozen beta parameters are
\(\alpha=0.5\times4=2\), \(\beta=(1-0.5)\times4=2\), and gamma scale 1.
The method uses the run's named MT19937 instance stream and does not call
MATLAB's global RNG or an unspecified toolbox sampler. Record the sampler
identifier and both shape parameters with every saved problem. Also expose
them directly in the instance manifest as `SelfWeightBetaSampler`,
`BetaAlpha`, `BetaBeta`, and `GammaScale`.

Draw \(X_i(0)\stackrel{\mathrm{iid}}{\sim}\operatorname{Unif}(0,1)\), then compute

\[
X(t+1)=W_{\mathrm{true}}X(t),\qquad t=0,\ldots,4,
\]

so \(T=6\) includes \(t=0,\ldots,5\).

Create ten-bin observations with

\[
Y_i(t)=\max\{1,\lceil10X_i(t)\rceil\},
\]

and feed midpoint-transformed observations

\[
X^{\mathrm{obs}}_i(t)=\frac{Y_i(t)-0.5}{10}
\]

plus \(A\) to the GA.

Save \(A,W_{\mathrm{true}},X(0{:}5),Y(0{:}5)\) before any optimizer call.

### Independent decision variables

For every realized \(A\), sort the eligible column indices in each row. Optimize the first \(d_i-1\) eligible weights and derive the last from the row-sum constraint. Log

\[
D=\sum_i(d_i-1)=P-N.
\]

The run is invalid before optimization if \(D\le10\), but the generation rules imply \(D\ge20\); an invalid count indicates an implementation error and does not authorize redrawing a favorable network.

### Initial population

Create 21 feasible chromosomes:

1. one identity matrix, permitted because all self-links exist;
2. twenty random chromosomes, drawing independent \(\operatorname{Unif}(0,1)\) values at all eligible positions and normalizing each row to sum to one.

Structural zeros must remain exactly zero. Save this population and give the identical saved population to the full adaptive, baseline, and ablation configurations for that run.

## Paper-faithful objective

For candidate \(W\), generate \(\widehat X(t)\) from the observed midpoint initial state and compute

\[
f_{\mathrm{paper}}=
\sum_{i=1}^{20}\sum_{t=0}^{5}
\left|\widehat Y_i(t)-Y_i(t)\right|
\, 
\left|\widehat X_i(t)-X^{\mathrm{obs}}_i(t)\right|,
\]

where

\[
\widehat Y_i(t)=\max\{1,\lceil10\widehat X_i(t)\rceil\}.
\]

The corresponding row objective is the inner sum for one \(i\). Also log, but do not optimize separately,

\[
f_{\mathrm{release}}=\frac{f_{\mathrm{paper}}}{20(6-1)}.
\]

All objective evaluations must be finite. NaN or Inf is a hard implementation failure, not an unfavorable run.

## Exact iteration and adaptation order

### Initialization

Set \(p_b=p_c=p_m=0.1\), \(\sigma=0.5\), all five no-improvement counters to zero, and previous best to \(+\infty\). Evaluate the saved initial population once to validate and log finite objectives, but leave the comparison sentinel at \(+\infty\). The first selection therefore counts as an improvement and resets all counters, matching the released entry point's intended initialization without adopting its finite \(N^2-1\) sentinel.

### One completed generation \(g\)

1. **Selection:** evaluate all current chromosomes, identify the true elite, move it to the protected elite slot, and determine the current least-fit nonelite index after reordering.
2. **Selection gene swap:** propose all better-row swaps into the elite at once; accept all only on strict total-objective improvement.
3. **Improvement signal:** if the selected best decreases by more than `min_improve=0`, reset all five counters; otherwise increment all five once. Then store that selected best as the comparison value for the next generation.
4. **Adaptive action:** for every counter satisfying `counter >= 200`, apply its update and reset it. With common horizons and feedback, all due actions happen in the same generation:

\[
\begin{aligned}
p_b&\leftarrow\min(0.5,5p_b),\\
p_c&\leftarrow\max(0.01,0.2p_c),\\
p_m&\leftarrow\max(0.01,0.2p_m),\\
\sigma&\leftarrow\max(0.01,0.2\sigma).
\end{aligned}
\]

   If reintroduction is due, replace the current least-fit nonelite chromosome with an elite clone and reset `iterr`.
5. **Blending:** randomly pair all 20 nonelites and apply rowwise convex blending.
6. **Crossover:** apply rowwise permutation of nonfixed weights.
7. **Mutation:** perturb and redistribute free row mass while preserving every fixed entry and row sum.
8. **Survival:** compare each parent/offspring pair; retain parent on a tie; attempt the all-at-once row swap; carry the 20 survivors plus the protected elite forward.
9. **Postconditions:** assert nonnegativity, finite values, structural zeros, exact fixed values, and row sums within \(10^{-12}\).
10. **Checkpoint:** only after a completed generation divisible by 1000, calculate and store the best paper objective. Stop if it is at most `min_dev=0`; otherwise continue through generation 100000.

All due adaptive updates use the same pre-update control vector; the four numerical assignments and reintroduction are conceptually simultaneous. A code implementation may execute assignments in a fixed order only because none of these formulas depends on another updated control.

For the selected settings, a persistent plateau produces:

| Plateau event | \(p_b\) | \(p_c\) | \(p_m\) | \(\sigma\) |
|---:|---:|---:|---:|---:|
| Initial | 0.1 | 0.1 | 0.1 | 0.5 |
| After first 200-event trigger | 0.5 | 0.02 | 0.02 | 0.1 |
| After second 200-event trigger | 0.5 | 0.01 | 0.01 | 0.02 |
| After third 200-event trigger | 0.5 | 0.01 | 0.01 | 0.01 |

An intervening strict best improvement resets the horizon count but does not reset control values to their initial values.

### Preregistered recovery-horizon sensitivity

Before any MATLAB outcome was produced, two additional exact author-data
excerpts were frozen for the same \(N=20,d=2,T=6\), 10-bin, 21-chromosome,
medium/moderate/moderate cell:

| Adaptation/reintroduction horizon | Author record IDs | Author recovery mean | Author recovery SD |
|---:|---|---:|---:|
| 200 | 66401--66410 | 0.134743212907013 | 0.025728643223250 |
| 1000 | 212201--212210 | 0.162897005808785 | 0.021785061569789 |
| 5000 | 358001--358010 | 0.156829265514767 | 0.027525501325787 |

The 1000/5000 excerpt is
`source/published_sensitivity_rows.csv`, pinned by SHA-256
`3353ef63fea27c7c89bad5107e56fc539371c85d704c036f71510f2ee32fdf33`.
For each sensitivity profile, set all four numerical-control horizons and
the elite-reintroduction horizon to the stated value. Reuse the same ten
saved instances, initial populations, operator seeds, 100000-generation
maximum, and 1000-generation reporting grid.

The required directional gate S1 is:

\[
\overline{\operatorname{RMSE}}_{200}
<
\overline{\operatorname{RMSE}}_{1000}
\quad\text{and}\quad
\overline{\operatorname{RMSE}}_{200}
<
\overline{\operatorname{RMSE}}_{5000}.
\]

This gate tests the selected paper conclusion about shorter adaptation
horizons; it was not chosen after seeing MATLAB results. Report all three
means and 95% intervals, and keep author and reproduced values separate.
For each horizon, also require the reproduced recovery mean to fall inside
the 95% Student-t interval derived from the ten frozen author rows or to
have relative mean error no greater than 5%. P1--P4 determine exact
selected-cell numerical reproduction; the final candidate-level success
claim additionally requires S1 and all three recovery-magnitude checks.

## Fixed baseline and ablations

These comparisons are researcher-added and were not reported by Johnson and Carnegie. They test the adaptive mechanism without changing the primary reproduction gate.

| Configuration | Gene swapping | Numerical control adaptation | Elite reintroduction | Purpose |
|---|---|---|---|---|
| A. `AdaptiveFull` | Selection and survival | Yes: all four laws | Yes | Primary reproduction |
| B. `FixedParameterBaseline` | Selection and survival | No; hold \(0.1,0.1,0.1,0.5\) | No | Remove stagnation feedback |
| C. `AblationNoGeneSwap` | No | Yes | Yes | Remove the rowwise recombination mechanism |
| D. `AblationNoReintroduction` | Selection and survival | Yes | No | Isolate numerical-control feedback |
| E. `AblationNoControlAdaptation` | Selection and survival | No; hold initial values | Yes | Isolate elite reintroduction |

Every configuration receives the same ten saved instances and initial populations. Run exactly ten replicates per configuration. Do not add replicates based on interim results.

For B--E report perfect-by-1000, perfect-by-2000, terminal objective,
checkpoint iteration, recovery RMSE, objective evaluations, and wall-clock
time. Compare A against B--E with paired run-level differences and exact
paired success tables. With only ten pairs, effect estimates and exact
confidence intervals take priority over asymptotic \(p\)-values. No
baseline or ablation result can replace a failed A-profile gate.

## Released-code compatibility diagnostics

The fixed-commit behavior is diagnostic, not the primary algorithm. The following toggles are frozen before outcomes:

| Diagnostic | Change from paper-faithful profile |
|---|---|
| Q1: strict horizon | Trigger on `counter > 200`, i.e. the 201st nonimproving event |
| Q2: release elite-index defect | Reproduce the `elite_index != 5` test at population 21 |
| Q3: stale replacement index | Use the pre-reordering worst index for reintroduction |
| Q4: release stopping placement | Test \(f=0\) before variation every loop; separately round first-hit generation upward to a 1000 checkpoint for archive comparison |
| Q5: release mutation scaling | Reproduce whole-row scaling and final normalization only in a quarantined invariant-failure test, never in the scientific profile |

Use the explicit study settings even in compatibility diagnostics; never use the Julia entry-point defaults. Run Q1–Q4 one at a time and then as one fixed combined compatibility profile if resources permit. Q5 is unsafe for known nonzero fixed values and is limited to structural-zero study rows or isolated tests.

Diagnostics must be labeled prominently. A diagnostic match may explain a paper-faithful mismatch but cannot be reported as a paper-faithful reproduction.

## Required implementation tests before experimental runs

### Model and transformation

- Equation (1) agrees with hand-calculated two-step matrices.
- Ordinal midpoint mapping sends \(1\mapsto0.05\), \(10\mapsto0.95\); back-mapping handles \(0\mapsto1\), bin boundaries, and \(1\mapsto10\).
- An observed/predicted pair in the same bin contributes zero.
- A one-bin mismatch contributes bin distance times continuous absolute distance.
- Row objectives sum exactly to the paper objective.
- The release-scale objective equals \(f_{\mathrm{paper}}/[N(T-1)]\).

### Feasibility and operators

- Every generated row is nonnegative, sums to one within \(10^{-12}\), and has exact structural zeros.
- Blending matches Equation (3) for a fixed \(\beta\) and preserves both row sums.
- Crossover is a permutation of free entries only.
- Mutation covers negative clamp, upper clamp, proportional rescale, zero-remainder redistribution, and one-free-entry cases.
- Selection protects the true elite for populations 5, 21, 51, and 99, including a test where the true elite begins at index 5.
- Gene swaps are all-or-none and rejected when the composite objective does not strictly improve.
- Survival retains the parent on a tie.

### Adaptation and stopping

- With no improvement, the first trigger occurs at event 200, not 199 or 201.
- All five common-horizon actions fire together and reset their own counters.
- A strict improvement resets counters but not current control values.
- The control trace matches the plateau table above.
- No stop occurs at a non-checkpoint generation in the primary profile.
- Generation 100000 is the final allowed completed generation.

### Reproducibility

- Repeating a run with the same saved inputs and stream state yields identical results.
- Configuration ordering does not change a configuration's result.
- Every raw output row carries run ID, all three seeds, input hashes, configuration, MATLAB/OS metadata, source revision, and objective-definition label.

Experimental runs may begin only after every paper-faithful unit/invariant test passes. Failed tests authorize code correction, not parameter changes.

## Analysis and reporting

Preserve one raw row per run/configuration and a separate per-checkpoint trace. At minimum record:

- all 22 fixed hyperparameters;
- \(p_b,p_c,p_m,\sigma\) at every adaptive event and checkpoint;
- all five counters and event reasons;
- best paper objective and release-scale objective;
- objective-evaluation count;
- first exact-zero generation and rounded 1000 checkpoint;
- terminal \(\widehat W\), \(W_{\mathrm{true}}\), and Equation (4) recovery;
- exact independent-variable count \(D\);
- feasibility residuals;
- elapsed time and environment.

Published and reproduced values must remain in separate columns. Calculate absolute error, relative error where the target is nonzero, gate pass/fail, and confidence intervals from raw rows; never hand-enter derived summaries.

## No outcome-informed choices

After the first MATLAB result is produced, the following are prohibited:

- replacing or screening seeds;
- redrawing a valid difficult network;
- choosing a different Table 5 cell;
- changing the 200-event threshold or `>=` semantics;
- changing operator order, tie handling, objective, population, or checkpoint grid;
- increasing the number of runs because the first ten are inconvenient;
- enabling only the compatibility quirk that moves an outcome toward the target;
- tuning the baseline or ablations;
- treating a diagnostic result as the paper-faithful result.

Permitted changes are limited to defects demonstrated by a predeclared unit/invariant test. Every correction requires a versioned change note, a rerun of the complete test suite, and a rerun of all ten seeds for every affected configuration. Earlier failed outputs remain archived.

## Interpretation rule

- **Numerical reproduction passed:** configuration A passes P1–P4 with all tests and invariants passing.
- **Numerical reproduction failed:** any P1–P4 gate fails after validated implementation and the allowed documented diagnostic cycles.
- **Compatibility-only match:** a preregistered Q profile matches but A does not; report this as evidence that released-code behavior, not the paper-faithful algorithm, explains the archive.
- **Inconclusive implementation:** a required invariant cannot be satisfied or an unresolved source ambiguity prevents a unique run; do not claim success or numerical failure.

Even a pass is an independent ten-run statistical reproduction, not recovery of the authors' exact random trajectories.

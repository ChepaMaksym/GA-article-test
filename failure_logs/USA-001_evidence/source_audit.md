# Source audit: Johnson & Carnegie (2022) adaptive DeGroot GA

## Audit decision

This candidate is suitable for an **independent statistical MATLAB reproduction**, but not for a bitwise rerun of the authors' experiment. The paper, a fixed source-code commit, and the authors' raw result archive are available. The original random seeds, generated adjacency matrices, true weight matrices, initial opinions, initial GA populations, simulation driver, and exact Julia environment are not.

The implementation must keep two targets distinct:

1. **Paper-faithful algorithm:** a clean-room implementation of the equations and prose in the CC BY 4.0 article, resolving only explicitly documented ambiguities.
2. **Released-code behavior:** evidence from the GPL-3.0 Julia files at commit `2c33060320f722e6bb737b607cf0b27a9aa4256c`, including defects and defaults that are not the paper's simulation settings.

The preregistered numerical endpoint is defined separately in `experiment_specification.md`. No MATLAB outcome was used to choose that endpoint.

## Identity and eligibility

| Field | Audited value |
|---|---|
| Candidate | USA-001; local candidate 02 |
| Title | *Calibration of an Adaptive Genetic Algorithm for Modeling Opinion Diffusion* |
| Authors | Kara Layne Johnson; Nicole Bohme Carnegie |
| Source type | Peer-reviewed journal article |
| Journal | *Algorithms* 15(2), article 45 |
| Official publication date | 28 January 2022 |
| DOI | [10.3390/a15020045](https://doi.org/10.3390/a15020045) |
| Geographic basis | Department of Mathematical Sciences, Montana State University, Bozeman, Montana, USA |
| Adaptive-GA classification | Feedback-based, multi-parameter adaptive GA |
| Runtime-adaptive controls | Four: blending probability \(p_b\), crossover probability \(p_c\), mutation probability \(p_m\), and mutation standard deviation \(\sigma\) |
| Feedback signal | Consecutive generations with no strict improvement of the best objective |
| Decision-variable criterion | Passed for the preregistered \(N=20\) cell: at least 20 independent row-simplex variables, hence more than 10 |

## Authoritative sources and local fixity

| Evidence | Locator and role | Fixity / legal status |
|---|---|---|
| Version-of-record article | [MDPI article](https://www.mdpi.com/1999-4893/15/2/45), especially §§2.1–2.3, Tables 1–5, Figures 3–7, §4, and Data Availability | Article states CC BY 4.0 |
| Legal full-text mirror | [PubMed Central PMC9162034](https://pmc.ncbi.nlm.nih.gov/articles/PMC9162034/) | Public full text; same article |
| Local article PDF | `../source/johnson_carnegie_2022_algorithms.pdf` | SHA-256 `76dc851d356c578995821f66c5c80fc1911c87fd0d9a9b110a5e0f4c59716ccb` |
| Fixed repository state | [commit/tree `2c33060320f722e6bb737b607cf0b27a9aa4256c`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/tree/2c33060320f722e6bb737b607cf0b27a9aa4256c) | Commit dated 13 December 2021 (`Add files via upload`), fixed for this audit; do not use a moving branch head |
| GA entry point | [`GeneticAlgorithm.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/GeneticAlgorithm.jl) | GPL-3.0-covered source evidence |
| Operators | [`SelectionOperator.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/SelectionOperator.jl), [`BlendingOperator.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/BlendingOperator.jl), [`CrossoverOperator.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/CrossoverOperator.jl), [`MutationOperator.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/MutationOperator.jl), and [`SurvivalOperator.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/SurvivalOperator.jl) | GPL-3.0-covered source evidence |
| Model/objective utilities | [`OpinionsFunction.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/OpinionsFunction.jl), [`PowerDeviationFunction.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/PowerDeviationFunction.jl), and [`ScaleFunction.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/ScaleFunction.jl) | GPL-3.0-covered source evidence |
| Code license | [`Algorithm-Code/LICENSE`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/LICENSE) | GNU General Public License, version 3 |
| Raw simulation archive | `../source/DeGrootGeneticAlgorithm/Simulation-Study-Data/hyper.csv.zip` | SHA-256 `41ca24820e044b91a93f7cd8d2c327d712ccad4cb486afc48f069ed316a2e9c4`; separate data-license notice not found |

The paper's Data Availability statement identifies `hyper.csv.zip`, the `Algorithm-Code` directory, Julia 1.5 or higher, the GNU GPL, and the `Algorithms-archive` branch. The fixed commit is used here because a branch name is mutable.

The fixed repository state contains the operator and utility files plus result CSVs (`fit.csv`, `hyper.csv.zip`, `recovery.csv`, and `useability.csv`). It does **not** contain the hyperparameter-study driver, a seed ledger, the generated inputs, a README that reconstructs the study, or a `Project.toml`/`Manifest.toml` environment lock.

## Mathematical model and paper-to-code map

### DeGroot dynamics: paper Equation (1)

For \(N\) agents,

\[
X(t+1)=W X(t),
\]

where \(X(t)\in[0,1]^N\), \(W=[w_{ij}]\in[0,1]^{N\times N}\), \(w_{ij}\ge 0\), and

\[
\sum_{j=1}^{N}w_{ij}=1\quad\text{for every }i.
\]

The adjacency matrix \(A=[a_{ij}]\) imposes the structural zeros:

\[
a_{ij}=0\ \Longrightarrow\ w_{ij}=0.
\]

The study includes self-links \(a_{ii}=1\). The released `Opinions` function implements \(X(:,t+1)=W X(:,t)\) for the unbounded DeGroot profile.

### Ordinal transformation

For an ordinal scale with \(b\) bins and a value \(y\in\{1,\ldots,b\}\), the forward midpoint transform is

\[
x=\frac{y-\tfrac12}{b}.
\]

The back-transform is

\[
y=\max\{1,\lceil b x\rceil\}.
\]

The article gives these rules in §2.1.2. `ScaleFunction.jl` implements the same mapping, including a special treatment of \(x=0\). A MATLAB implementation should not reproduce the source function's mutation of its input when handling the zero edge case; it should return a new value.

### Objective: paper Equations (2a) and (2b)

Let \(B(\widehat x_i(t),x_i(t))\) be the absolute difference between the ordinal-bin labels of the predicted and observed continuous opinions. The chromosome-level paper objective is

\[
f(\widehat X,X)=
\sum_{i=1}^{N}\sum_{t=0}^{T-1}
B(\widehat x_i(t),x_i(t))
\left|\widehat x_i(t)-x_i(t)\right|.
\tag{2a}
\]

The row/gene objective is

\[
f_i(\widehat X,X)=
\sum_{t=0}^{T-1}
B(\widehat x_i(t),x_i(t))
\left|\widehat x_i(t)-x_i(t)\right|.
\tag{2b}
\]

Thus an error inside the correct ordinal bin is unpenalized, and \(f=0\) need not imply recovery of the true \(W\).

`PowerDeviationFunction.jl` computes the same bin-distance-times-continuous-distance term but divides each row sum by \(N(T-1)\); the selection operator then sums rows. Consequently its model-level value is

\[
f_{\text{release}}=\frac{f_{\text{paper}}}{N(T-1)}
\]

for complete data. This positive constant does not change rankings or the event \(f=0\), but it changes nonzero objective magnitudes. The function's `power` argument is not used, despite its name and default. It also fills missing observed entries in place; the simulation study did not rely on a documented missing-data design.

The paper-faithful implementation must expose \(f_{\text{paper}}\) and may log \(f_{\text{release}}\) as a compatibility diagnostic.

### Blending: paper Equation (3)

After randomly pairing the even number of nonelite chromosomes, for each row \(i\) independently with probability \(p_b\), draw \(\beta\sim\operatorname{Unif}(0,1)\) and update the pair simultaneously:

\[
\begin{aligned}
B'_i&=\beta B_i+(1-\beta)C_i,\\
C'_i&=(1-\beta)B_i+\beta C_i.
\end{aligned}
\tag{3}
\]

Convex blending preserves nonnegativity, row sums, structural zeros, and
common fixed entries. The released Julia expressions look like Equation
(3), but the population is an array of mutable row arrays and the operator
uses a shallow `copy`. It writes the first child before evaluating the
second-child expression, so the second child reads the already-updated
first child. The archive-compatible diagnostic reproduces that sequential
aliasing. The primary profile instead implements the simultaneous
Equation (3) assignments stated in the paper.

### Recovery: paper Equation (4)

Let \(P=\sum_{i,j}a_{ij}\) be the number of nonstructurally-zero weights. The reported recovery measure is

\[
\operatorname{RMSE}_{\mathrm{rec}}
=\sqrt{\frac{
\sum_{\{(i,j):a_{ij}=1\}}
(w_{ij}-\widehat w_{ij})^2}{P}}.
\tag{4}
\]

The paper calls all \(P\) nonzero-eligible entries parameters. For optimization-dimension accounting, the \(N\) row-sum equalities remove one degree of freedom per row, so the number of **independent decision variables** is \(P-N\), not \(P\).

## Operators, in paper order

One iteration comprises selection, blending, crossover, mutation, and survival.

### 1. Selection and gene swapping

1. Evaluate all chromosomes and retain the minimum-objective chromosome as elite.
2. Evaluate Equation (2b) for every row of every chromosome.
3. For every row in which a nonelite chromosome has a better row objective than the elite, construct one composite proposal by swapping all such rows at once.
4. Re-evaluate the composite elite with Equation (2a).
5. Retain **all** proposed row swaps only if the composite objective is strictly lower; otherwise revert all of them.
6. Exempt the retained elite from blending, crossover, and mutation.

The all-at-once acceptance is important because a row's predicted trajectory can depend on other rows even though row-level objective contributions are available.

### 2. Blending

Use Equation (3) on randomly paired nonelite chromosomes, with an independent Bernoulli(\(p_b\)) decision for every row.

### 3. Crossover

For every nonelite chromosome and row, independently with probability \(p_c\), randomly permute all nonfixed weights within that row. Fixed positions remain fixed. Permutation preserves the free mass and row sum.

### 4. Mutation

For every nonelite chromosome and row, independently with probability \(p_m\):

1. Choose one nonfixed entry \(w_{ij}\) uniformly.
2. Draw \(\epsilon\sim\mathcal N(0,\sigma^2)\) and propose \(w^\star=w_{ij}+\epsilon\).
3. Let \(s_i\) be the fixed mass in row \(i\) and \(q_i=1-s_i\) its free mass.
4. Clamp and redistribute:
   - if \(w^\star<0\), set the selected weight to 0 and rescale the other free weights to sum to \(q_i\);
   - if \(w^\star\ge q_i\), set the selected weight to \(q_i\) and all other free weights to 0;
   - otherwise set the selected weight to \(w^\star\) and rescale the remaining free weights proportionally to sum to \(q_i-w^\star\);
   - when the old remaining free mass is zero, distribute \(q_i-w^\star\) equally among the other free entries.

A robust implementation must explicitly handle a row with only one free entry and must preserve nonzero fixed entries exactly.

### 5. Survival and gene swapping

Pair each parent with its corresponding offspring, retain the fitter member, and try the same all-at-once gene-swapping procedure using fitter rows from the rejected member. The surviving nonelite chromosomes plus the preserved elite form the next generation.

The paper does not define tie-breaking. The released code retains the offspring on an objective tie; the paper-faithful profile preregisters deterministic parent-on-tie behavior so an equal-fitness random replacement does not masquerade as improvement.

## All 22 paper hyperparameters: Table 1

The paper has exactly 22 user controls. The four runtime values \(p_b,p_c,p_m,\sigma\) are adaptive; their starting values, limits, factors, and stagnation horizons are fixed hyperparameters within a run.

| # | Paper name | Meaning | Status within one run |
|---:|---|---|---|
| 1 | `chromosomes` | Odd population size | Fixed |
| 2 | `probb` | Initial blending probability \(p_b\) | Fixed initializer for adaptive \(p_b\) |
| 3 | `factorb` | Multiplier for \(p_b\) | Fixed |
| 4 | `maxb` | Upper bound for \(p_b\) | Fixed |
| 5 | `iterb` | No-improvement horizon for \(p_b\) | Fixed |
| 6 | `probc` | Initial crossover probability \(p_c\) | Fixed initializer for adaptive \(p_c\) |
| 7 | `factorc` | Multiplier for \(p_c\) | Fixed |
| 8 | `minc` | Lower bound for \(p_c\) | Fixed |
| 9 | `iterc` | No-improvement horizon for \(p_c\) | Fixed |
| 10 | `probm` | Initial mutation probability \(p_m\) | Fixed initializer for adaptive \(p_m\) |
| 11 | `factorm` | Multiplier for \(p_m\) | Fixed |
| 12 | `minm` | Lower bound for \(p_m\) | Fixed |
| 13 | `iterm` | No-improvement horizon for \(p_m\) | Fixed |
| 14 | `sigma` | Initial mutation standard deviation \(\sigma\) | Fixed initializer for adaptive \(\sigma\) |
| 15 | `factors` | Multiplier for \(\sigma\) | Fixed |
| 16 | `mins` | Lower bound for \(\sigma\) | Fixed |
| 17 | `iters` | No-improvement horizon for \(\sigma\) | Fixed |
| 18 | `max_iter` | Maximum iterations | Fixed |
| 19 | `min_improve` | Minimum objective decrease counted as improvement | Fixed |
| 20 | `min_dev` | Stopping objective | Fixed |
| 21 | `reintroduce` | Reintroduced chromosome type | Fixed categorical control |
| 22 | `iterr` | No-improvement horizon for reintroduction | Fixed |

Table 1 describes `probm` as the initial probability of “blending”; this is an editorial typo. The surrounding mutation section, notation \(p_m\), and source code establish that it is the mutation probability.

The fixed Julia entry point renames the five paper horizon arguments as `max_iterb`, `max_iterc`, `max_iterm`, `max_iters`, and `max_iterr`. Those are implementation names, not additional hyperparameters.

## Adaptive laws and threshold semantics

On a shared no-improvement event, each control has its own counter and update:

\[
\begin{aligned}
p_b&\leftarrow\min(\texttt{maxb},p_b\,\texttt{factorb}),\\
p_c&\leftarrow\max(\texttt{minc},p_c\,\texttt{factorc}),\\
p_m&\leftarrow\max(\texttt{minm},p_m\,\texttt{factorm}),\\
\sigma&\leftarrow\max(\texttt{mins},\sigma\,\texttt{factors}).
\end{aligned}
\]

The corresponding counter is reset after its update. Reintroduction replaces the current least-fit nonelite chromosome with the selected type and resets its counter. Because the study assigns the same horizon to all five counters, they are conceptually simultaneous whenever the common horizon is reached.

The article says the change occurs when the specified number of generations is “reached.” The paper-faithful interpretation is therefore `counter >= horizon`: a horizon of 200 fires after exactly 200 consecutive nonimproving selections. The release tests `counter > horizon`, so its nominal 200 fires on the 201st event. This is a preregistered paper/code distinction, not a tunable choice.

## Tables 2–4: exact grouped settings

### Table 2: ProbSigma

| Level | `probb` | `probc` | `probm` | `sigma` |
|---|---:|---:|---:|---:|
| Low | 0.01 | 0.05 | 0.05 | 0.2 |
| Medium | 0.1 | 0.1 | 0.1 | 0.5 |
| High | 0.2 | 0.2 | 0.2 | 1 |

### Table 3: MinMax

| Level | `maxb` | `minc` | `minm` | `mins` |
|---|---:|---:|---:|---:|
| Minimal | 1 | 0 | 0 | 0 |
| Moderate | 0.5 | 0.01 | 0.01 | 0.01 |
| Extreme | 0.2 | 0.05 | 0.05 | 0.05 |

### Table 4: MultFactor

| Level | `factorb` | `factorc` | `factorm` | `factors` |
|---|---:|---:|---:|---:|
| Slow | 2 | 0.5 | 0.5 | 0.5 |
| Moderate | 5 | 0.2 | 0.2 | 0.2 |
| Rapid | 10 | 0.1 | 0.1 | 0.1 |

## Table 5: simulation design and generators

| Input | Published levels / rule |
|---|---|
| Network size | \(N\in\{4,20,50\}\); reachability enforced |
| Target mean degree | \(d\in\{2,5,9\}\); minimum degree 1 for every node |
| Self-weight | Target \(w_{ii}=0.5\), beta distribution with \(\kappa=\alpha+\beta=4\), hence \(\operatorname{Beta}(2,2)\); the article does not identify a beta RNG implementation |
| Time steps | \(T\in\{2,3,6\}\), including the initial state |
| Ordinal bins | \(b\in\{5,7,10,20,30\}\) |
| Chromosomes | \(\{5,21,51,99\}\) |
| ProbSigma | Low, medium, high |
| MinMax | Minimal, moderate, extreme |
| MultFactor | Slow, moderate, rapid |
| No-improvement horizon | \(\{200,1000,5000\}\), shared by `iterb`, `iterc`, `iterm`, `iters`, and `iterr` |
| Replicates | 10 new network/weight/data instances per combination |

The procedure in §2.3.2 is:

1. Generate an Erdős–Rényi network at the requested size and target degree; reject disconnected networks.
2. Draw each self-weight with mean 0.5 and beta precision \(\kappa=4\).
3. Draw other eligible weights independently from \(\operatorname{Unif}(0,1)\), then scale them to the remaining row mass.
4. Draw \(X(0)\) independently from \(\operatorname{Unif}(0,1)\).
5. Generate \(X(1),\ldots,X(T-1)\) with Equation (1).
6. Back-transform to the requested ordinal scale and supply \(A\) and the observed ordinal opinions to the GA.

The paper does not state the exact mapping from “target degree” to the Erdős–Rényi edge probability, graph-library call and version, rejection-loop RNG consumption or cap, beta-distribution sampler, or random seeds. The transparent assumption \(p=d/(N-1)\) is therefore a reconstruction choice, not an author-stated fact.

The frozen MATLAB reconstruction uses a simple undirected upper-triangle
\(G(N,p)\) generator identified as `undirected-gnp-upper-triangle-v1`,
rejects disconnected draws for at most 10,000 attempts, and treats exhaustion
as a hard generation failure rather than replacing a seed. Self-weights use
the explicitly versioned `marsaglia-tsang-gamma-ratio-v1` method:
independent \(\operatorname{Gamma}(\alpha,1)\) and
\(\operatorname{Gamma}(\beta,1)\) draws are divided by their sum. For the
selected cell, \(\alpha=\beta=2\). These are preregistered reconstruction
choices, not properties claimed for the authors' unarchived generator.

Study-wide fixed controls were `max_iter=100000`, `min_dev=0`, `min_improve=0`, and `reintroduce="elite"`. The paper says the stopping check was applied only every 1000 generations. Runtime measurements used one Julia thread on Ubuntu Server 21.10 with a Ryzen 9 3950X and 64 GB of 3000 MHz RAM.

## Decision-variable accounting

For row \(i\), let

\[
J_i=\{j:a_{ij}=1\},\qquad d_i=|J_i|.
\]

The eligible weights are

\[
\{w_{i,j}:i=1,\ldots,N,\ j\in J_i\}.
\]

Choose any deterministic ordering \(J_i=(j_{i,1},\ldots,j_{i,d_i})\). A nonredundant full decision vector is

\[
\theta=
\left(
\{w_{i,j_{i,k}}:k=1,\ldots,d_i-1\}
\right)_{i=1}^{N},
\]

with the last weight in each row derived as

\[
w_{i,j_{i,d_i}}
=1-\sum_{k=1}^{d_i-1}w_{i,j_{i,k}}.
\]

Therefore

\[
D=\sum_{i=1}^{N}(d_i-1)=P-N.
\]

This is the complete variable schema. An exact list such as \(w_{1,7},w_{1,12},\ldots\) cannot be given before a realized adjacency matrix exists; the paper and archive do not release those matrices.

For the preregistered \(N=20\) cell, every node has at least one external neighbor and a self-link, so \(d_i\ge2\) and

\[
D\ge \sum_{i=1}^{20}1=20>10.
\]

If the realized external mean degree were exactly the target \(d=2\), then \(P\approx20(2+1)=60\) and \(D\approx40\). The exact count must be calculated and logged for each generated network.

GA hyperparameters are not decision variables. The GA optimizes the free entries of \(W\); it does not optimize its 22 controls in this experiment.

## Published numerical evidence

The paper reports these study-wide summaries:

- 67.7% of all runs found a perfect objective within the first 1000 generations.
- 4.5% did not find a perfect objective by 100,000 generations; their largest terminal objective was 0.02.
- For 21, 51, and 99 chromosomes, median reported solution times were 4.7, 11.0, and 19.3 seconds, respectively, on the authors' hardware.
- Figures 3–7 and §4 support a horizon of 200, at least 21 chromosomes, and settings near the medium/moderate grouped levels.

Those global summaries mix the complete factorial design and are not the primary target for a ten-run single-cell reproduction. The exact predeclared cell and its author-archive records are specified in `experiment_specification.md`.

## Released-code quirks and incompatibilities

These observations apply only to the fixed commit. They must not be silently folded into the paper-faithful implementation.

| Area | Fixed-commit behavior | Paper-faithful treatment |
|---|---|---|
| Defaults | Defaults include 5 chromosomes, `max_iter=10000000`, `min_dev=0.001`, `min_improve=0.0001`, and different initial/limit settings | Use the explicit study settings, never entry-point defaults |
| Horizon trigger | Strict `counter > max_iter*` | `counter >= horizon` |
| Stopping check | Every loop, before variation | Only at completed 1000-generation checkpoints |
| Maximum iteration | Checks `iter > max_iter`, permitting an extra selection evaluation | End at the stated maximum |
| `min_improve` | Argument is defined but ignored; any `new < old` resets counters | With study value 0, use strict objective decrease |
| Elite location | `SelectionOperator.jl` tests `elite_index != 5`, not `elite_index != chromosomes` | Always move the true elite to the protected elite slot |
| Consequence at 21/51/99 chromosomes | If the true elite happens to be at index 5, it is not moved; the last chromosome is then treated as elite | Treat this as a released-code defect |
| Worst index | Computed before elite reordering and returned without remapping | Recompute/remap after reordering before reintroduction |
| Objective scale | Divides Equation (2a) by \(N(T-1)\) | Log both scales; optimize the paper value |
| `power` | Present but unused in `PowerDeviation` | Do not expose a fictitious power-objective option |
| Mutation with fixed values | Normal branch divides the entire row, including fixed entries, by a scale; final “Bandaid” renormalizes every row | Rescale only free entries and preserve fixed values exactly |
| Mutation degenerate row | Equal redistribution can divide by zero when only one free entry remains | Explicitly handle the one-free-entry case |
| Survival tie | Offspring survives a tie | Parent survives a tie in the preregistered paper profile |
| Initial best sentinel | Initializes `old=N^2-1`, `new=N^2` instead of evaluating an initial best | Initialize previous best to \(+\infty\), then evaluate |
| Reproducibility | No seed argument or RNG-state ledger | Use and save preregistered MATLAB streams |
| Environment | No locked Julia project or simulation driver at the fixed commit | Record MATLAB release, toolboxes, OS, CPU, and exact local revision |

The fact that the archived `Iteration` field is recorded only in 1000-generation increments, while the released GA checks every generation and does not return an iteration count, is further evidence that an unreleased driver or study-specific wrapper was used.

## Legal and redistribution constraints

1. **Article:** the article is CC BY 4.0. Equations, prose-derived specifications, and tables may be adapted with attribution and a link to the license.
2. **Julia code:** `Algorithm-Code/LICENSE` is GNU GPL version 3. The local source snapshot must retain its license and attribution. Modified or redistributed derivatives must satisfy GPL-3.0 obligations, including corresponding source.
3. **MATLAB implementation:** use a clean-room implementation from the CC BY paper. Do not translate the Julia files line by line or copy their comments/structure into a permissively licensed MATLAB package. Code-observed quirks may be represented as documented compatibility tests or opt-in diagnostic switches. This is a risk-control practice, not legal advice.
4. **Result data:** the paper publicly designates `hyper.csv.zip` as its data source, but the fixed repository has no separate data-license file. Preserve provenance and hashes. Do not imply that the GPL code license automatically licenses the CSV data, and do not redistribute the archive outside this research bundle without resolving its licensing status.
5. **Attribution:** every report using the article or author archive must cite the authors, title, journal, year, DOI, and fixed repository commit.

## Unresolved items and their consequence

| Missing or ambiguous item | Consequence | Preregistered control |
|---|---|---|
| Author seeds, RNG algorithm, and beta sampler | Exact instances and trajectories cannot be regenerated | New fixed MATLAB seed ledger plus `marsaglia-tsang-gamma-ratio-v1`; call result an independent statistical reproduction |
| \(A\), \(W_{\mathrm{true}}\), \(X(0)\), and initial populations for CSV rows | Cannot replay author rows one-for-one | Generate ten new instances from the published distributions |
| Exact Erdős–Rényi library call, target-degree mapping, and rejection cap | Graph distribution is not bitwise identified | Freeze \(p=d/(N-1)\), `undirected-gnp-upper-triangle-v1`, and a 10,000-attempt connectivity cap before outcomes |
| Study driver | Exact check placement, logging, and archive production are partly unknown | Use paper-faithful update order; run a separate fixed compatibility sensitivity |
| Exact Julia package versions | Direct Julia rerun is not environment-locked | MATLAB is the reproduction language; record its environment |
| Data license beyond availability statement | Redistribution status is uncertain | Keep archive provenance; do not relicense it |

No missing item authorizes post-outcome seed selection, threshold changes, operator changes, extra restarts, or target-cell substitution.

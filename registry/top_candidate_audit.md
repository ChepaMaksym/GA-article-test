# Deep audit of selected adaptive-GA candidates

Audit date: 2026-07-30  
Scope: evidence and implementation-readiness review before any MATLAB port or numerical reproduction  
Evidence policy: primary papers, legal institutional/publisher copies, and repositories at fixed revisions only

## Registry correction on 2026-07-30

USA-002, the 2021 *Applied Network Science* article “Using a novel genetic algorithm to assess peer influence on willingness to use pre-exposure prophylaxis in networks of Black men who have sex with men,” was re-audited separately. Its former score 77 and eligible rank 3 are withdrawn: the archived CSVs are incomplete outputs rather than rerunnable inputs, and the generator, driver, seeds, matrices, analysis script, and a uniquely specified weight-generation law are missing. Paper/code execution conflicts add a second source of non-uniqueness. The canonical evidence and immutable artifact hashes are in [`re_audits/USA-002_no_go.md`](./re_audits/USA-002_no_go.md); its registry status is now **`[audit 2026-07-30] hard_fail`** and `final_score=null`.

EU-002, the 2022 *Applied Sciences* article “An Efficient Hybrid Evolutionary Optimization Method Coupling Cultural Algorithm with Genetic Algorithms and Its Application to Aerodynamic Shape Design,” was also re-audited separately. Its former score 67 and eligible rank 3 are withdrawn. The printed diversity Equation (10) is unusable without inventing a correction; entropy construction and normalizers are absent; \(\beta=0.7\) in the Equation (16) prose conflicts with \(\beta=0.3\) in Table 6; and the base GA operators, ninth CST bound, wing geometry, solver, and mesh are incomplete. Table 7’s 30-run \(F_4,D=12\) mean is too noisy to serve as a dependable 5% reproduction gate, and there are no seeds or raw runs. The canonical evidence, publisher-PDF hashes, and probability calculation are in [`re_audits/EU-002_no_go.md`](./re_audits/EU-002_no_go.md); its registry status is now **`[audit 2026-07-30] hard_fail`** and `final_score=null`.

EU-003, the 2021 *Journal of Hydroinformatics* article “A decision support tool for optimising groundwater-level monitoring networks using an adaptive genetic algorithm,” was re-audited separately. Its former score 56 and eligible rank 3 are withdrawn. The paper explicitly states that its 70-borehole data cannot be made publicly available; 80/15/5 method fractions conflict with Table 8’s 85/10/5; an every-five-stall trigger conflicts with a first change at stall 10; the 50% uniform-crossover probability is not reconciled with population fractions; and the 10% step, 80% threshold, custom uniqueness-preserving operators, seeds, run count, and raw outputs are unavailable. No scalar checkpoint has SD, CI, or repeated-run provenance for a defensible ≤5% gate. The canonical evidence, official citations, corrected-proof hash caveat, dimensional audit, Table 3/Table 8 checkpoints, and target analysis are in [`re_audits/EU-003_no_go.md`](./re_audits/EU-003_no_go.md); its registry status is now **`[audit 2026-07-30] hard_fail`** and `final_score=null`.

USA-003, the 2023 *Expert Systems with Applications* article “Genetic algorithms with self-adaptation for predictive classification of Medicare standardized payments for physical therapists,” was re-audited separately. Its former score 54 and eligible rank 3 are withdrawn. Although the paper has 51 true solution genes, a canonical-GA baseline, and explicit 50-run confidence-interval tables, the exact 40,662-row analytic table and split memberships are request-only; ten adaptive operator-argument mappings, boundary handling, parameter self-mutation timing, no-crossover inheritance, two-/three-parent accounting, and tie/replacement semantics are absent; and no source, environment, seeds, or raw 50-run values exist. Table 9’s SD-SAGA 93.15±0.54 interval cannot validate an unknown input/algorithm pipeline, while a ±5% band also accepts nonadaptive baselines. The canonical evidence, institutional-PDF hash and license boundary, dimensional audit, upstream-data/reconstruction analysis, operator ambiguities, and target table are in [`re_audits/USA-003_no_go.md`](./re_audits/USA-003_no_go.md); its registry status is now **`[audit 2026-07-30] hard_fail`** and `final_score=null`.

USA-004, the 2022 GECCO paper “Effects of Imputation Strategy on Genetic Algorithms and Neural Networks on a Binary Classification Problem,” was re-audited separately. Its former score 45 and eligible rank 3 are withdrawn. The 51-gene solution dimension is valid and an institutional full text is lawfully readable, but the exact processed table is unavailable: the reported 20,331/10,016/10,016 split totals 40,363, which is 299 short of the stated 40,662 records. The 900 missing-value masks/imputed pairs, preprocessing, seeds, parameter-chromosome mappings, operator arguments, boundary rules, tie and replacement semantics, multi-parent accounting, no-crossover inheritance, code, environment, and raw runs are absent. Figures 2–9 provide graphical confidence bands rather than recoverable numerical targets, and a forced ±5% gate is non-discriminating because it also admits the canonical-GA baselines. The canonical evidence, official-PDF hashes and rights boundary, dimensional audit, upstream-data licenses, split arithmetic, algorithm ambiguities, and target analysis are in [`re_audits/USA-004_no_go.md`](./re_audits/USA-004_no_go.md); its registry status is now **`[audit 2026-07-30] hard_fail`** and `final_score=null`.

The three candidates below are the previously selected deep-audit set, not a claim that all three are currently the top three eligible rows. CMF-AGAwER remains conditional and noneligible. After the five hard-fail corrections, two candidates remain eligible, in canonical order: EU-001 and USA-001. The authoritative ranks and scores are in [`ranking.csv`](./ranking.csv).

## Executive verdict

The three papers are genuine, post-2020 journal articles from eligible US/EU institutions and all describe an adaptive GA on a problem with more than ten optimization variables. They are not equally reproducible.

| Audit order | Candidate | Score | Hard-filter status | Pre-execution readiness verdict |
|---:|---|---:|---|---|
| 1 | Al-Afandi & Horváth (2021), *Adaptive Gene Level Mutation* | **79/100** | Pass, using the deterministic \(N\)-Queens experiments | Best first MATLAB candidate, but the released sweep driver cannot be trusted without a documented correction |
| 2 | Johnson & Carnegie (2022), *Calibration of an Adaptive Genetic Algorithm for Modeling Opinion Diffusion* | **77/100** | Pass | Best audit trail and intermediate data; use a clean-room MATLAB implementation if the deliverable must remain MIT-licensed |
| 3 | Nematzadeh et al. (2024), *CMF-AGAwER* | **73/100 provisional** | Algorithmic pass; **implementation hold** until dataset rights are traced | Strong paper-level ablations, but the released script is not an executable reproduction package |

The numerical scores measure reproducibility evidence, not scientific novelty or reported solution quality. CMF-AGAwER remains provisional because a public GitHub copy of a biomedical dataset is not, by itself, proof that the dataset may be redistributed or reused.

## Exact rubric used

The required 100 points are:

1. mathematical specification — 15;
2. experimental settings — 10;
3. legal/open data — 10;
4. runs and random seeds — 10;
5. open code — 10;
6. code-license quality — 10;
7. intermediate results — 10;
8. adaptive parameters/mechanism — 10;
9. update order — 5;
10. baseline GA — 5;
11. ablation study — 5.

“Open code” is scored separately from “code license.” A visible repository can score poorly as an executable artifact even when its license is excellent. Likewise, a CC BY paper does not license its code or third-party datasets.

## Hard-filter verification

| Required condition | Al-Afandi & Horváth | Johnson & Carnegie | Nematzadeh et al. |
|---|---|---|---|
| Official publication in 2020 or later | Pass: 9 January 2021 | Pass: 28 January 2022 | Pass: 9 October 2024 |
| At least one US/EU institutional affiliation | Pass: Pázmány Péter Catholic University, Hungary (EU) | Pass: Montana State University, USA | Pass: Universidad de Málaga/IBIMA, Spain (EU) |
| Legal full text | Pass: publisher CC BY 4.0 article | Pass: publisher/PMC CC BY 4.0 article | Pass: Universidad de Málaga repository copy, CC BY 4.0 |
| At least 11 decision variables, excluding GA controls | Pass: \(q_1,\ldots,q_{32}\) in the smallest principal \(N\)-Queens experiment; 31 freely choosable positions after the all-different constraint fixes the last | Pass: for \(N=20\), independent free weights are \(D=\sum_i(d_i-1)\), approximately 40 at nonself mean degree 2; larger settings are much higher-dimensional | Pass under the standard binary formulation: \(z_1,\ldots,z_M\), \(M=121\ldots145\), subject to a subset-size constraint; see representation caveat below |
| Adaptive change of a GA parameter or operator | Pass: the within-chromosome locus-selection distribution is recomputed from current gene errors | Pass: \(p_b,p_c,p_m,\sigma\) change after stagnation | Pass: \(P_c,P_m\) change after stagnation |
| Mechanism, initial values, bounds, and order recoverable | Pass, after resolving paper/code variants explicitly | Pass; paper plus operator code are unusually detailed | Paper passes; released code introduces contradictory execution semantics |
| Fitness and constraints known | Pass | Pass | Pass |
| Population size and stopping rule known | Pass | Pass | Pass |
| Inputs legal or reproducible | Pass for \(N\)-Queens; do not rely on bundled TSPLIB files without a separate rights check | Pass for a new synthetic simulation; posted result CSVs lack a separate data-license notice | **Not yet proven** for redistributed biomedical datasets |
| Code reusable under a suitable license or clean-room path available | Pass: MIT | Pass: GPL-3.0 code, or clean-room from CC BY paper | Code pass: MIT; data remain separate |
| No pirated material needed | Pass | Pass | Pass |

### Decision-variable accounting

This accounting deliberately excludes population size, generation limit, mutation probability, and all other GA controls.

- **Al-Afandi & Horváth:** choose the paper’s \(N=32\) queens case. The chromosome is \(q=(q_1,\ldots,q_{32})\), where \(q_i\in\{0,\ldots,31\}\) gives the row of the queen in column \(i\), and all \(q_i\) are different. There are 32 encoded decision variables and 31 freely selectable values after the permutation constraint. Either interpretation exceeds ten. The analogous TSP vector is a city permutation.
- **Johnson & Carnegie:** the chromosome is a row-stochastic influence matrix \(W\). If row \(i\) has \(d_i\) nonfixed entries, a nonredundant list is
  \[
  \{w_{i,j_{i,1}},\ldots,w_{i,j_{i,d_i-1}}\}_{i=1}^{N},
  \qquad
  w_{i,j_{i,d_i}}=1-\sum_{r=1}^{d_i-1}w_{i,j_{i,r}}.
  \]
  Hence \(D=\sum_i(d_i-1)=P-N\), where \(P\) is the number of nonfixed/nonzero entries used by the paper’s recovery RMSE. Because the paper’s degree excludes the always-present self-link, \(N=20\) and intended nonself mean degree 2 give \(D\approx20\times2=40\); the \(N=20,50\) and degree 5 or 9 cases are much larger. The exact variable names differ in every randomly generated network, and cannot be reconstructed for a published run because its network and seed were not archived.
- **CMF-AGAwER:** after the three rankers are unioned, define \(z_m\in\{0,1\}\) for candidate feature \(m\). The candidate-pool sizes are Colon 128, CNS 144, GLI 131, SMK 145, Leukemia-Binary 121, Leukemia-Multiclass 130, Covid-19 142, MLL 127, and SRBCT 123 (paper Table 7). The paper/code store a sparse, variable-length list of selected feature IDs instead of an explicit binary vector and restrict searched subsets to at most 18. This is an equivalent constrained representation of \(M\ge121\) binary decisions, but it should be documented because an overly literal “current chromosome length” reading would produce lengths from 1 to 18 rather than a fixed \(M\).

## Candidate 1 — Al-Afandi & Horváth (2021)

### Identity and legal artifacts

- Type: peer-reviewed journal article.
- DOI: [10.3390/a14010016](https://doi.org/10.3390/a14010016).
- Legal full text: [MDPI article](https://www.mdpi.com/1999-4893/14/1/16), especially Sections 3–5, Equations (4)–(7), Algorithms 1–2, Tables 1–4, and Figures 6–9.
- Repository: [fixed tree at `7e13ea43861203637b50320226a19e24689a20ff`](https://github.com/Al-Afandi/Adaptive-Gene-Level-Mutation/tree/7e13ea43861203637b50320226a19e24689a20ff).
- Code license: [MIT license at the audited revision](https://github.com/Al-Afandi/Adaptive-Gene-Level-Mutation/blob/7e13ea43861203637b50320226a19e24689a20ff/LICENSE). Use, modification, and redistribution are allowed if the copyright and license notice are preserved; there is no copyleft. A derivative MATLAB port may be MIT-licensed.
- Data: \(N\)-Queens is fully synthetic/deterministic. The repository also contains TSPLIB files, but it does not provide a dataset-specific license/provenance manifest. The safest first reproduction therefore uses \(N\)-Queens only.

### Exact mechanism

For queen \(j\), define its partial conflict count

\[
h_j(q)=\sum_{k\ne j}\mathbf 1\!\left(|q_j-q_k|=|j-k|\right).
\]

The released implementation forms

\[
w_j=h_j+\epsilon,\qquad
\Pr(J=j\mid q)=\frac{w_j^{\,\mathrm{Pow}}}{\sum_{\ell=1}^{N}w_\ell^{\,\mathrm{Pow}}},
\]

selects two indices without replacement from that distribution, and swaps the two genes. In the code, \(\epsilon=0.1\). `Pow=0` makes the choice uniform, `Pow=1` is the default locus mutation, and the limiting `Pow -> Inf` choice deterministically concentrates on the worst loci. The paper text gives 0.001 as an illustrative nonzero floor, while the Figure 8 configuration and code use `MinGeneMutRate=0.1`; the floor is therefore a configuration item, not a universal constant.

For TSP, paper Equation (7) gives the partial fitness

\[
PF_i=\frac{d(i,i+1)-d_{\min}(i)}
           {d_{\max}(i)-d_{\min}(i)}.
\]

The code again adds the nonzero floor, raises the value to `Pow`, normalizes, chooses two positions, and swaps them. The relevant implementations are [`queens.py`](https://github.com/Al-Afandi/Adaptive-Gene-Level-Mutation/blob/7e13ea43861203637b50320226a19e24689a20ff/queens.py) and [`tsp.py`](https://github.com/Al-Afandi/Adaptive-Gene-Level-Mutation/blob/7e13ea43861203637b50320226a19e24689a20ff/tsp.py).

This is a **gene/locus-level feedback-adaptive mutation operator**, not an adaptive global mutation probability. `MutationRate` and `Pow` are fixed within a run; the gene-selection probabilities are adaptive because they are recomputed from the current chromosome, including after each accepted swap.

### Parameters and order

| Item | Published/released value | Status |
|---|---|---|
| Population size | 200 and 400 in principal tables/figures | Fixed per run |
| Generations | 20 for Table 1 \(N\)-Queens; 100 stated for Table 2 TSP | Fixed/stopping |
| Mutation rate | sweep \(\{0.01,0.1,0.3,0.6,0.9\}\); code default 0.5 | Fixed per run |
| Elite/keep ratio | 0.05 in code | Fixed |
| Random-new ratio | 0.20 in code | Fixed |
| Crossover-created fraction | 0.75, implied by keep + random-new | Fixed |
| `Pow` | 1 default; 0 through the infinite-norm limit in the power experiment | Fixed per run |
| Minimum locus weight | 0.1 in released code and Figure 8 setup | Fixed floor |
| Locus probabilities | normalized \(w_j^{\mathrm{Pow}}\), always in \([0,1]\) | Adaptive, recomputed |

The released order is:

1. evaluate/rank the population;
2. retain 5% elite;
3. generate 75% by order-preserving crossover;
4. replace 20% with random chromosomes;
5. recompute partial gene errors;
6. for chromosomes from index 2 onward, execute swaps while a fresh uniform variate is below `MutationRate`;
7. recompute partial errors after each swap;
8. advance the generation.

The `while U < MutationRate` implementation is not a single Bernoulli mutation. It gives
\[
\Pr(K=k)=p_m^k(1-p_m),\quad k=0,1,\ldots,
\qquad E[K]=\frac{p_m}{1-p_m},
\]
so \(p_m=0.9\) produces nine swaps on average. This semantic must be preserved in a code-faithful port or explicitly changed and labeled in a paper-faithful port.

No explicit NaN/Inf guard is present. The nonzero locus floor protects normalization when all conflict counts are zero, but the TSP denominator in Equation (7) still requires a duplicate-distance guard in a robust port.

### Experiments, baselines, and intermediate evidence

- Table 1 reports means over 50 repetitions after 20 generations for \(N=32,64,128,256\), two population sizes discussed in the text, and five mutation rates. Examples are \(N=32,p_m=0.3\): baseline 1.70 hits versus locus 0; \(N=64,p_m=0.9\): 6.52 versus 0.24; \(N=256,p_m=0.6\): 50.18 versus 30.75.
- The Table 1 layout does not identify which of the two stated population sizes produced each single reported cell. This prevents an exact table-cell configuration from being recovered without an assumption.
- TSP results use 100 repetitions and random new city layouts/weights/populations according to Section 5.2. Table 2 states 100 generations; the current `tsp.py` sets 200.
- Figure 6 compares traditional, individual-adaptive, and locus mutation. It is not a fair estimator comparison: the paper uses the mean locus result but selects the best result for the other two methods.
- Figure 8 is a useful component ablation/sensitivity study over `Pow`, including the uniform (`Pow=0`) and worst-locus limit.
- Tables 1–4 and mean/standard-deviation convergence bands are checkable intermediate targets. The repository contains plot images, but no per-run CSV, saved arrays, or seed ledger.
- Independent-run counts are explicit: 50 for the principal \(N\)-Queens table, 100 for TSP, and 10 for the Figure 6/Figure 8 studies. No random seeds are reported or set.

### Released-code audit

The repository is valuable algorithmic evidence but is not a turnkey reproduction:

- In both sweep drivers, `setter(MutationRate)` is called **after** the repetitions for the labeled rate. Consequently, the first column labeled 0.01 runs at the default 0.5; subsequent labels are shifted; and 0.9 is never executed. See the driver tail in [`queens.py`](https://github.com/Al-Afandi/Adaptive-Gene-Level-Mutation/blob/7e13ea43861203637b50320226a19e24689a20ff/queens.py#L215-L232) and [`tsp.py`](https://github.com/Al-Afandi/Adaptive-Gene-Level-Mutation/blob/7e13ea43861203637b50320226a19e24689a20ff/tsp.py#L232-L253).
- The baseline and locus solvers reinitialize populations in ways that do not guarantee paired identical starts.
- `tsp.py` creates one random problem per size/population block rather than a new problem in every repetition as the paper states.
- [`adaptive_mutation.py`](https://github.com/Al-Afandi/Adaptive-Gene-Level-Mutation/blob/7e13ea43861203637b50320226a19e24689a20ff/adaptive_mutation.py) ends with inconsistent/undefined result names and an out-of-range generation index.
- [`queens_power.py`](https://github.com/Al-Afandi/Adaptive-Gene-Level-Mutation/blob/7e13ea43861203637b50320226a19e24689a20ff/queens_power.py) refers to an undefined `GAT`.
- There is no environment lock or requirements file; use of removed NumPy aliases such as `np.int` breaks on current NumPy.

### MATLAB feasibility

Feasibility is high. A clean MATLAB implementation needs only permutation generation, conflict counting, weighted sampling without replacement, order-preserving crossover, and a controlled RNG. No external dataset or Python-model parity is required. The implementation must expose two explicit modes:

- `paper_intended`: set the rate before each sweep cell, generate inputs as described, and use documented settings;
- `released_code`: preserve the geometric swap loop and any other code semantics required for forensic comparison.

The first verification target should be a newly frozen \(64\)-Queens configuration with `PopSize=400`, 20 generations, `MutationRate=0.5`, and `Pow=1`, because Figure 6 fully states these values. It can test qualitative convergence and locus-vs-uniform effects, but the original figure’s best-vs-mean asymmetry means it is not an exact unbiased numerical target. Table 1 can be a secondary distributional target only after recording the unresolved population-size interpretation.

## Candidate 2 — Johnson & Carnegie (2022)

### Identity and legal artifacts

- Type: peer-reviewed journal article.
- DOI: [10.3390/a15020045](https://doi.org/10.3390/a15020045).
- Legal full text: [MDPI article](https://www.mdpi.com/1999-4893/15/2/45) and [PubMed Central copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC9162034/). Key locators are Sections 2.1.3, 2.2.1–2.2.3, 2.3, Tables 1–5, and Figures 3–7.
- Repository: [fixed archived tree at `2c33060320f722e6bb737b607cf0b27a9aa4256c`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/tree/2c33060320f722e6bb737b607cf0b27a9aa4256c).
- Code license: [GNU GPL v3 in `Algorithm-Code`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/LICENSE). Use, modification, and redistribution are legal under GPL conditions; a distributed derivative must remain GPL and provide corresponding source. It is not suitable for copying into an MIT-only implementation. A genuinely independent clean-room port from the CC BY paper is the MIT-compatible route.
- Data artifacts: `Simulation-Study-Data/fit.csv`, `hyper.csv.zip`, `recovery.csv`, and `useability.csv` are present at the fixed revision. They provide the strongest intermediate audit trail of the three candidates, but no separate data license is stated and the GPL file is located under `Algorithm-Code`, not at repository root.

### Objective and operators

The DeGroot model is

\[
X(t+1)=WX(t),\qquad w_{ij}\ge0,\qquad \sum_j w_{ij}=1,
\]

with adjacency-fixed zero entries and a permitted self-link. The paper’s ordinal/continuous hybrid objective (Equation 2a) is

\[
f(\widehat X,X)=
\sum_{i=1}^{N}\sum_{t=0}^{T-1}
B\!\left(\widehat x_i(t),x_i(t)\right)
\left|\widehat x_i(t)-x_i(t)\right|,
\]

where \(B\) is the absolute ordinal-bin deviation. Equation (2b) removes the sum over agents to obtain a gene/row-level loss for gene swapping.

The chromosome is \(W\), and gene \(i\) is row \(W_i\). The core operators in Sections 2.2.1–2.2.3 and [`GeneticAlgorithm.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/GeneticAlgorithm.jl) are:

1. selection plus gene swapping using the row-level objective;
2. blending of a pair of rows, with \(\beta\sim U(0,1)\):
   \[
   B_i'=\beta B_i+(1-\beta)C_i,\qquad
   C_i'=(1-\beta)B_i+\beta C_i,
   \]
   evaluated simultaneously from the old rows;
3. within-row crossover: independently with probability \(p_c\), randomly shuffle all nonfixed entries in the row;
4. mutation: independently by row with probability \(p_m\), choose a nonfixed weight, add \(\epsilon\sim N(0,\sigma)\), clamp it to the row’s feasible interval, and rescale/distribute the remaining free mass to preserve row sum and fixed entries;
5. pairwise parent/offspring survival with the elite retained.

### Complete hyperparameter inventory and adaptation

Paper Table 1 lists 22 controls:

`chromosomes`, `probb`, `factorb`, `maxb`, `iterb`, `probc`, `factorc`, `minc`, `iterc`, `probm`, `factorm`, `minm`, `iterm`, `sigma`, `factors`, `mins`, `iters`, `max_iter`, `min_improve`, `min_dev`, `reintroduce`, and `iterr`.

The four adaptive controls are \(p_b,p_c,p_m,\sigma\). Their stagnation counters and multiplicative factors are fixed hyperparameters. At a triggered update the code applies

\[
\begin{aligned}
p_b &\leftarrow \min(p_{b,\max},p_b\,f_b),\\
p_c &\leftarrow \max(p_{c,\min},p_c\,f_c),\\
p_m &\leftarrow \max(p_{m,\min},p_m\,f_m),\\
\sigma &\leftarrow \max(\sigma_{\min},\sigma\,f_\sigma).
\end{aligned}
\]

The four updates depend on their old value and their own counter/bound, not on newly updated values of the other controls. They are simultaneous in the conceptual algorithm and sequential but independent in code. Bounds are applied by `min`/`max`; no explicit NaN/Inf guard is present.

Paper Tables 2–4 give the exact calibration levels:

| Group | Level | Values in paper order |
|---|---|---|
| Initial `ProbSigma` | low | \(p_b=0.01,p_c=0.05,p_m=0.05,\sigma=0.2\) |
|  | medium | \(0.1,0.1,0.1,0.5\) |
|  | high | \(0.2,0.2,0.2,1\) |
| `MinMax` | minimal | \(p_{b,\max}=1,p_{c,\min}=0,p_{m,\min}=0,\sigma_{\min}=0\) |
|  | moderate | \(0.5,0.01,0.01,0.01\) |
|  | extreme | \(0.2,0.05,0.05,0.05\) |
| Multipliers | slow | \(f_b=2,f_c=0.5,f_m=0.5,f_\sigma=0.5\) |
|  | moderate | \(5,0.2,0.2,0.2\) |
|  | rapid | \(10,0.1,0.1,0.1\) |

Stagnation thresholds are 200, 1000, or 5000 generations for all four controls and chromosome reintroduction. `max_iter=100000`, `min_dev=0`, `min_improve=0`, and `reintroduce="elite"` in the simulation. Population sizes are 5, 21, 51, and 99.

### Exact code order and implementation caveats

The code-level generation order is:

1. evaluate/select and identify the elite;
2. check the stopping conditions;
3. reset or increment each no-improvement counter;
4. if a counter is over its threshold, update and clamp the associated control; independently trigger elite/identity reintroduction;
5. copy parents;
6. blend;
7. crossover;
8. mutate;
9. apply survival;
10. repeat.

The implementation tests `counter > threshold`, not `counter >= threshold`; a nominal 200 threshold therefore fires after 201 non-improving passes. The code defines `min_improve` but compares only `new < old`; the simulation’s `min_improve=0` masks this discrepancy for the published study.

Other released-code limitations:

- [`SelectionOperator.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/SelectionOperator.jl) contains `elite_index != 5` rather than comparing with the configured population endpoint. With 21, 51, or 99 chromosomes, an elite at index 5 can be mishandled.
- The archived branch contains operator code but no complete simulation-study driver, no Julia `Project.toml`/`Manifest.toml`, and no seed ledger.
- The paper says Julia 1.5 or higher, but exact dependency versions are not locked.

### Experiments, runs, and intermediate evidence

The factorial simulation uses network size \(N\in\{4,20,50\}\), target mean degree \(\{2,5,9\}\), time steps \(\{2,3,6\}\), ordinal bins \(\{5,7,10,20,30\}\), population \(\{5,21,51,99\}\), the three levels of each `ProbSigma`, `MinMax`, and multiplier group, and stagnation thresholds \(\{200,1000,5000\}\). Each combination is run ten times with a newly generated network, \(W\), and opinion data. Hardware/software are reported: AMD Ryzen 9 3950X, 64 GB RAM, Ubuntu Server 21.10, Julia 1.5, single thread.

Published intermediate targets include:

- raw study CSVs at the archived revision;
- Figures 3–7 with recovery RMSE, generation count, and runtime distributions;
- 67.7% of runs finding a perfect solution within 1000 generations and 4.5% reaching 100,000 without a perfect solution;
- median solution times of 4.7, 11.0, and 19.3 seconds for populations 21, 51, and 99.

The paper states ten runs per cell but gives no random seeds. Exact run replay is impossible; distribution-level comparison against the archived CSVs is possible.

There is no direct adaptation-off, fixed-control GA baseline. The factorial design is a strong sensitivity/calibration analysis of starting values, limits, factors, and stagnation thresholds, but it does not isolate “adaptive versus fixed” under otherwise identical settings. It earns partial ablation credit and zero baseline credit.

### MATLAB feasibility

The matrix operators, ordinal transform, objective, and adaptive updates are straightforward to port. The main obstacles are provenance rather than mathematics:

- do not translate GPL source line-by-line into an MIT project;
- derive a clean-room implementation from the CC BY paper, and record that status;
- independently regenerate synthetic networks/data with declared MATLAB seeds;
- use the archived CSVs only as distributional validation targets unless their reuse terms are clarified;
- unit-test row sums, fixed zeros, mutation boundary cases, simultaneous blending, and the `>` threshold semantics.

If the project may be GPL-3.0, the official operator implementation can be adapted with attribution and source-distribution compliance. If MIT is required, the paper is detailed enough for a clean-room implementation, but the official code should then be used only for black-box behavioral comparison and discrepancy discovery.

## Candidate 3 — Nematzadeh et al. (2024), CMF-AGAwER

### Identity and legal artifacts

- Type: peer-reviewed journal article.
- DOI: [10.1016/j.knosys.2024.112345](https://doi.org/10.1016/j.knosys.2024.112345).
- Publisher record: [ScienceDirect article](https://www.sciencedirect.com/science/article/pii/S0950705124009791).
- Legal full text: [Universidad de Málaga repository PDF](https://riuma.uma.es/xmlui/bitstream/handle/10630/32475/1-s2.0-S0950705124009791-main.pdf?isAllowed=y&sequence=1), CC BY 4.0. Key locators: Algorithms 1–5 and Equations (9)–(13) on PDF pages 4–8; settings and Tables 4–5 on pages 8–10; Figures 5–8 and Tables 7–9 on pages 10–13.
- Repository: [fixed tree at `d24e61e78ac197ad75342e8f4be5d63d17bd9e7a`](https://github.com/KhaosResearch/CMF-AGAwER/tree/d24e61e78ac197ad75342e8f4be5d63d17bd9e7a).
- Code license: [MIT](https://github.com/KhaosResearch/CMF-AGAwER/blob/d24e61e78ac197ad75342e8f4be5d63d17bd9e7a/LICENSE), compatible with an MIT MATLAB port when the notice is preserved.
- Dataset rights: unresolved. The repository contains nine biomedical datasets and derived feature arrays, but no per-dataset license/provenance manifest. The repository’s MIT file cannot automatically relicense third-party source data. Implementation should remain on hold until each selected dataset’s authoritative terms are recorded.

### Objective and exact adaptive mechanism

The candidate set is the union of the top 50 features from CEI, mutual information, and Fisher ratio. For a selected subset \(S\), the wrapper fitness is mean stratified five-fold decision-tree accuracy:

\[
F(S)=\frac{1}{5}\sum_{r=1}^{5}
\operatorname{Accuracy}\!\left(\mathrm{DT}_r(S)\right),
\]

maximized. The released code rounds fitness to two decimals and fixes only `DecisionTreeClassifier(random_state=42)`; other stochastic components are not seeded.

Roulette-wheel selection follows paper Equations (9)–(11). Variable single-point crossover (Equation 12) is

\[
O_1=S_1[{:}C_1]\mathbin{\|}S_2[C_2{:}],\qquad
O_2=S_2[{:}C_2]\mathbin{\|}S_1[C_1{:}],
\]

with duplicate-feature repair. Mutation (Equation 13) replaces one selected feature with an unselected candidate feature.

The two adaptive controls are \(P_c\) and \(P_m\). Initial values are

\[
P_c^{(0)}=0.9,\qquad P_m^{(0)}=0.4.
\]

After five consecutive generations without best-fitness improvement:

\[
P_c\leftarrow\max(0,P_c-0.3),\qquad
P_m\leftarrow\min(1,P_m+0.2).
\]

Thus the intended schedules are \(P_c:0.9,0.6,0.3,0\) and \(P_m:0.4,0.6,0.8,1\). Both update from their old values at the same generation; neither depends on the newly updated other control. Any improvement resets both to 0.9 and 0.4. Stopping occurs at 20 generations without improvement, 100 iterations, or accuracy 1.

The paper specifies

\[
n_c=2\left\lceil \frac{P_c n_{\mathrm{pop}}}{2}\right\rceil,\qquad
n_m=\left\lceil P_m n_{\mathrm{pop}}\right\rceil.
\]

The released Python uses `round`, not `ceil`; at \(P_c=0.9,n_{\mathrm{pop}}=10\), Python’s tie-to-even rounding produces 8 crossover offspring instead of the paper’s 10.

### Fixed controls, repository mechanism, and order

| Item | Value |
|---|---:|
| Population | 10 |
| Initial subset length | uniformly 1–10 |
| Evaluated subset-size cap/search expression | 18 |
| Maximum iterations | 100 |
| Stop after no improvement | 20 generations |
| Adapt after no improvement | every block of 5 |
| Initial \(P_c,P_m\) | 0.9, 0.4 |
| Bounds | \(P_c,P_m\in[0,1]\) |
| External-repository radius divisor \(\beta\) | 2 |
| External clusters | \(q=\sqrt{\text{number of unused features}}\) |
| Tournament size | 10 |
| CV folds | 5, stratified |
| Ranker contribution | top 50 from each of CEI, MI, and FR before union |

The paper-level order (Algorithm 5) is:

1. evaluate the current population;
2. generate crossover offspring;
3. generate mutation offspring;
4. generate a diverse external-repository candidate using the radius/cluster/tournament mechanism;
5. merge parents, crossover offspring, mutation offspring, and repository candidate;
6. sort and truncate to population 10;
7. recompute selection probabilities and the best solution;
8. update/reset \(P_c,P_m\);
9. check the stopping rules.

The external repository measures modified Hausdorff-like distances between feature sets, defines a radius as maximum pairwise distance divided by \(\beta=2\), clusters unused features, constructs diverse subsets, and crosses the best diverse candidate with repository memory. Algorithms 2–4 on PDF pages 5–7 are the controlling source.

### Experiments, runs, baselines, and intermediate evidence

- Python 3.9.13, Windows 10, Intel i5-4200U 1.60 GHz, and 12 GB RAM are reported.
- Table 5 and Figure 5 use ten runs with stratified five-fold CV. Other comparison/NFE tables use three runs, so “number of runs” is result-specific rather than global.
- Table 5 supplies exact before/after targets. Examples: Colon accuracy 0.69 to 0.94 with six features; CNS 0.68 to 0.93 with nine; Leukemia-Binary 0.89 to 0.99 with nine; MLL 0.79 to 1.00 with eight.
- Table 8 reports function evaluations over three runs, including Colon 788, CNS 1159, GLI 964, SMK 1319, and MLL 667.
- Figure 6 isolates the external repository’s effect on GA; Figure 7 studies adaptive crossover/mutation settings; Figure 8 compares convergence with DWES. These are strong mechanism-level ablations.
- The “before CMF-AGAwER” classifier and comparisons with other feature-selection methods are useful baselines, but they are not a perfectly matched fixed-parameter version of the same GA. Baseline credit is therefore partial, not full.
- No per-run raw results, fold assignments, convergence arrays, or general RNG seeds are released.

### Released-script audit

The only main artifact, [`CMF-AGAwER.py`](https://github.com/KhaosResearch/CMF-AGAwER/blob/d24e61e78ac197ad75342e8f4be5d63d17bd9e7a/CMF-AGAwER.py), is a 51 KB monolithic, interactive-analysis script:

- it sequentially loads every dataset from hard-coded `D:\...` paths, with later loads overwriting earlier ones;
- `features` is used by the GA but is never loaded/defined in the executable path;
- duplicated fitness-function definitions cause the later definition to overwrite the earlier;
- the later precision/recall/F-score calls use binary defaults and fail for multiclass datasets unless manually changed;
- no `random.seed` or `numpy.random.seed` is set, and KMeans has no `random_state`;
- offspring counts use `round` rather than the paper’s `ceil`;
- a probability-refresh loop assigns `Fits[i] = pop[i].fit` while looping on `j`, leaving most entries stale;
- offspring counts are computed before an improvement-triggered reset of \(P_c,P_m\), so one subsequent generation can use counts from the old controls;
- there is no requirements/environment lock, command-line entry point, test suite, or raw-result export.

The repository therefore supports algorithm inspection, not a claim of exact execution-level reproduction.

### MATLAB feasibility

The GA operators are implementable, but exact parity is materially harder than for the other candidates:

- MATLAB decision-tree splitting and scikit-learn `DecisionTreeClassifier` need not choose identical trees;
- KMeans initialization and cluster labeling must be specified;
- folds and all RNG streams must be reconstructed;
- paper-faithful (`ceil`) and code-faithful (`round`, plus or minus bugs) variants diverge;
- dataset rights must be resolved before redistributing or publishing a reproduction.

A MATLAB port can reproduce the algorithmic hypothesis, but it cannot honestly claim an exact replication of the published numbers without first freezing a lawful dataset, fold partition, preprocessing, classifier semantics, and variant policy.

## Scoring arithmetic

| Dimension | Max | Al-Afandi & Horváth | Johnson & Carnegie | CMF-AGAwER |
|---|---:|---:|---:|---:|
| 1. Mathematical specification | 15 | 12 | 14 | 12 |
| 2. Experimental settings | 10 | 8 | 10 | 9 |
| 3. Legal/open data | 10 | 10 | 8 | 5 |
| 4. Runs/seeds | 10 | 5 | 5 | 5 |
| 5. Open code | 10 | 5 | 7 | 4 |
| 6. Code-license quality | 10 | 10 | 6 | 10 |
| 7. Intermediate results | 10 | 7 | 10 | 8 |
| 8. Adaptive parameters/mechanism | 10 | 8 | 10 | 9 |
| 9. Update order | 5 | 4 | 5 | 3 |
| 10. Baseline GA | 5 | 5 | 0 | 3 |
| 11. Ablation study | 5 | 5 | 2 | 5 |
| **Total** | **100** | **79** | **77** | **73 provisional** |

The explicit sums are:

- Al-Afandi & Horváth: \(12+8+10+5+5+10+7+8+4+5+5=\mathbf{79}\).
- Johnson & Carnegie: \(14+10+8+5+7+6+10+10+5+0+2=\mathbf{77}\).
- CMF-AGAwER: \(12+9+5+5+4+10+8+9+3+3+5=\mathbf{73}\).

### Why points were withheld

| Candidate | Main deductions |
|---|---|
| Al-Afandi & Horváth | Table/code generation and sweep mismatches; population ambiguity in Table 1; no seeds/raw runs/environment; several broken scripts; overall mutation rate is not adaptive |
| Johnson & Carnegie | No seeds or archived simulation driver/environment; GPL is legally usable but incompatible with an MIT derivative; result CSVs have no separate license; no adaptation-off baseline |
| CMF-AGAwER | Dataset rights not established; no raw runs/seeds; main script is not end-to-end runnable; `ceil`/`round`, stale-index, and update-timing contradictions; no perfectly matched fixed-GA baseline |

## Historical recommendation — executed and superseded

This section records the pre-implementation decision as it existed at the
ranking freeze. It is not a current action plan. EU-001 was attempted first,
then USA-001 as fallback; both failed their published-result gates. The
canonical post-execution state is recorded in
[`attempt_outcomes.md`](./attempt_outcomes.md).

The frozen recommendation was to proceed first with **Al-Afandi &
Horváth’s \(N\)-Queens locus mutation in MATLAB**, because it had the highest
score, needed no contested dataset, had a permissive MIT reference
implementation, included a traditional-GA baseline and a `Pow` ablation, and
was the least dependent on cross-language machine-learning semantics.

The implementation must not silently “repair” the published/released workflow. Before coding, freeze:

1. a paper-intended specification;
2. a released-code specification;
3. the selected interpretation of the Table 1 population-size ambiguity;
4. a new seed schedule declared before viewing outcomes;
5. a correction log for the mutation-rate setter bug;
6. separate labels for reproduced results and newly corrected experiments.

The frozen fallback was **Johnson & Carnegie** if the first candidate could
not meet the numerical verification threshold. That fallback was also
executed and failed. CMF-AGAwER remains noneligible until the chosen dataset’s
legal provenance and license are independently verified.

## Source locator index

### Al-Afandi & Horváth

- [Publisher article and CC BY full text](https://www.mdpi.com/1999-4893/14/1/16): affiliation/publication metadata; Sections 3–4 for Equations (4)–(7); Section 5.1 and Table 1 for \(N\)-Queens; Section 5.2 and Table 2 for TSP; Section 5.4/Figure 8 for `Pow`; Section 5.5/Table 4 for timing.
- [Audited repository tree](https://github.com/Al-Afandi/Adaptive-Gene-Level-Mutation/tree/7e13ea43861203637b50320226a19e24689a20ff).
- [MIT license](https://github.com/Al-Afandi/Adaptive-Gene-Level-Mutation/blob/7e13ea43861203637b50320226a19e24689a20ff/LICENSE).

### Johnson & Carnegie

- [Publisher article and CC BY full text](https://www.mdpi.com/1999-4893/15/2/45): Section 2.1.3/Equations (2a)–(2b); Sections 2.2.1–2.2.3 for operators/adaptation; Section 2.3 and Tables 1–5 for the factorial design; Figures 3–7 for intermediate results; Data Availability statement.
- [PMC legal copy with accessible equations](https://pmc.ncbi.nlm.nih.gov/articles/PMC9162034/).
- [Audited archived repository tree](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/tree/2c33060320f722e6bb737b607cf0b27a9aa4256c).
- [GPL-3.0 license](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/2c33060320f722e6bb737b607cf0b27a9aa4256c/Algorithm-Code/LICENSE).

### Nematzadeh et al.

- [Universidad de Málaga legal PDF](https://riuma.uma.es/xmlui/bitstream/handle/10630/32475/1-s2.0-S0950705124009791-main.pdf?isAllowed=y&sequence=1): Algorithms 1–5; Equations (9)–(13); Tables 4–9; Figures 5–8.
- [Publisher record and data-availability statement](https://www.sciencedirect.com/science/article/pii/S0950705124009791).
- [Audited repository tree](https://github.com/KhaosResearch/CMF-AGAwER/tree/d24e61e78ac197ad75342e8f4be5d63d17bd9e7a).
- [MIT license](https://github.com/KhaosResearch/CMF-AGAwER/blob/d24e61e78ac197ad75342e8f4be5d63d17bd9e7a/LICENSE).

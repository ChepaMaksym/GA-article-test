# Failure record — EU-001 Adaptive Gene Level Mutation

Date: 2026-07-30  
DOI: [10.3390/a14010016](https://doi.org/10.3390/a14010016)  
Country/category: Hungary / EU  
Implementation: MATLAB R2026a Update 4, with an independent Python 3.13/NumPy 2.4.4 forensic probe  
Deleted candidate folder: `candidate_01_adaptive_gene_level_mutation`

## Classification and conclusion

The candidate is classified as **not numerically reproduced** because the paper, released sweep driver, and reported Table 1 values cannot be reconciled under the required 5% rule without arbitrary parameter fitting.

The implementation passed 11/11 unit tests, deterministic replay, all permutation/bound checks, all NaN/Inf checks, adaptive-probability checks, the full 50-run protocol, and the main qualitative result: locus mutation had lower mean loss than the fixed baseline in all five N=64 rate blocks. The preregistered quantitative endpoint failed: 5/10 Table 1 cells passed, maximum absolute error was 4.90 attacking pairs, and maximum relative error was 7.08571428571429 (708.57%).

The released `queens.py` contains mutually consequential defects:

- the two diagonal predicates in `Fittnes` are algebraically identical, so only one diagonal is counted;
- `setter(MutationRate)` runs after each labelled block, shifting the effective mutation rates;
- roulette uses loss as weight and then advances the chosen sorted index by one;
- only the first two chromosomes are protected although `KeepRatio=0.05`;
- baseline and locus populations are not actually paired as the paper states;
- the final reported trace point is evaluated before the last reproduction step.

The single-diagonal behavior was independently confirmed by executing the archived MIT-licensed Python class: at N=64, population 400, 20 generations, and rate 0.5, one deterministic reference probe produced baseline 7 and locus 1, consistent with the corresponding MATLAB forensic probe. Therefore the remaining discrepancy is not explained by the MATLAB port.

## Diagnostic cycles

### Cycle 1 — correct paper-intended fitness to released-code fitness

- Problem: the first MATLAB probe counted both diagonals and produced N=64 baseline/locus values 21/11, far from the published 6.6/1.0 endpoint.
- Hypothesis: `queens.py::Fittnes` accidentally duplicates the `row+column` predicate; Table 1 appears to use that released behavior.
- Changed element: added an explicit `source_single_diagonal` forensic mode while retaining a separately labelled correct two-diagonal sensitivity mode.
- Evidence: pinned repository commit `7e13ea43861203637b50320226a19e24689a20ff`, `queens.py` fitness predicate, plus an isolated execution of the upstream class.
- Before: baseline 21, locus 11 for the deterministic probe.
- After: baseline 7, locus 0 in the analogous MATLAB probe; archived Python probe gave 7/1.
- Endpoint absolute errors before: 14.4 baseline and 10.0 locus.
- Endpoint absolute errors after: 0.4 baseline and 1.0 locus for the MATLAB probe.
- Relative errors before: 218.18% baseline and 1000% locus.
- Relative errors after: 6.06% baseline and 100% locus for that single probe.
- Error reduced: yes.
- Artificial fitting: no; this restored the exact released predicate and kept the mathematically correct variant separate.

The ensuing preregistered run used 50 runs for each of two population sizes (100 observations per Table 1 cell), five labelled/effective rate blocks, and both baseline/locus methods: 1,000 primary runs, plus the declared ablation and corrected sensitivity. Structural checks passed; 5/10 numeric cells passed. Maximum absolute/relative errors were 4.90 and 708.57%.

### Cycle 2 — repository `queens_power.py` keep ratio

- Problem: the locus curve was systematically weaker than Table 1 at the low effective mutation rates.
- Hypothesis: the table may have used `KeepRatio=0.60`, which is explicitly present in the author’s `queens_power.py`, rather than 0.05 in `queens.py`.
- Changed element: keep/new/crossover ratios changed from 0.05/0.20/0.75 to 0.60/0.20/0.20 in a separate 10-run diagnostic grid.
- Evidence: `queens_power.py` at the pinned commit.
- Before: primary maximum absolute/relative errors 4.90 / 708.57%; 5/10 cells passed.
- After: maximum absolute/relative errors 4.97 / 646.48%; 3/10 cells passed.
- Error reduced: maximum relative error fell, but overall agreement worsened and the pass count fell.
- Artificial fitting: no; the only altered value was an author-repository configuration. It was rejected and never substituted for the primary run.

### Cycle 3 — paper’s illustrative minimum locus weight

- Problem: the repository’s 0.1 floor may dilute locus targeting compared with the paper text.
- Hypothesis: the paper’s explicit 0.001 example may have been used for Table 1.
- Changed element: locus floor changed from 0.1 to 0.001 in a separate 10-run diagnostic grid.
- Evidence: article Section 5.4 and its minimum-gene-mutation discussion.
- Before: primary maximum absolute/relative errors 4.90 / 708.57%; 5/10 cells passed.
- After: maximum absolute/relative errors 4.52 / 590.14%; 3/10 cells passed.
- Error reduced: maximum errors fell, but the required cellwise verification still failed and the pass count fell.
- Artificial fitting: no; the value is explicitly mentioned by the paper. It was rejected and never substituted for the primary run.

No further parameter search was performed. In particular, no seeds, outliers, rate values, or result cells were selected after inspecting outcomes.

## Deleted-file manifest

The verified deletion target was:

`C:\Users\User\OneDrive\Документы\MATLAB\GA new version\candidate_01_adaptive_gene_level_mutation`

It resolved inside the workspace and contained 181 visible files, 15 visible subdirectories, 15,403,482 visible bytes, plus the archived repository’s hidden `.git` metadata. The complete folder was scheduled for deletion. Its contents comprised:

- 8 MATLAB entry/diagnostic scripts and 1 Python reference probe;
- 38 modular `src/+aglga/*.m` implementation files and 1 MATLAB test file;
- 2 evidence/specification documents;
- official paper PDF and Figure 5 image;
- the complete pinned author repository, including its MIT license, 10 top-level Python/image/readme files, 123 TSPLIB route files, and hidden Git metadata;
- primary, smoke, two diagnostic result sets, raw run tables, generation logs, MAT/JSON/CSV artifacts, and the workbook smoke artifact.

No file outside that candidate folder was scheduled for deletion. The combined candidate registry, this detailed failure record, and `Failure_Log.csv` are retained.

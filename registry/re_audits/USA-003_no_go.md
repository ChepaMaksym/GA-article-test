# USA-003 re-audit — hard fail / no-go

Audit date: 2026-07-30  
Candidate: USA-003  
DOI: [10.1016/j.eswa.2023.119529](https://doi.org/10.1016/j.eswa.2023.119529)  
Decision: **`[audit 2026-07-30] hard_fail`**

## Official identity, date, and strict USA affiliation

The audited work is Reamonn Norat, Annie S. Wu, and Xinliang Liu, “Genetic algorithms with self-adaptation for predictive classification of Medicare standardized payments for physical therapists,” *Expert Systems with Applications* 218, article 119529.

- The [official publisher record](https://www.sciencedirect.com/science/article/pii/S0957417423000301) and DOI identify the article.
- The manuscript was received on 31 May 2021, revised on 23 December 2022, accepted on 5 January 2023, and made available online on **10 January 2023**. The issue date is 15 May 2023.
- Norat and Wu are affiliated with the University of Central Florida, Orlando, Florida. Liu is affiliated with Lehigh University, Bethlehem, Pennsylvania. The strict USA-affiliation requirement passes.
- The [UCF Evolutionary Computation Lab project page](https://www.cs.ucf.edu/~ecl/projects/ga-data.html) lists the publication and links its institutionally hosted full text.

Identity, post-2020 publication date, and strict USA affiliation pass.

## Legal-access and license boundary

The full article is publicly readable from the authors’ official UCF institutional site:

`https://www.cs.ucf.edu/~ecl/papers/2301.eswa.norat.pdf`

It is a publisher-formatted final article carrying `© 2023 Published by Elsevier Ltd.` It does **not** carry a Creative Commons or open-source license. The institutional copy provides lawful reading access for this audit, but it is not an open license to redistribute or adapt the PDF.

The exact UCF-hosted bytes audited were:

| Property | Value |
|---|---|
| Bytes | `1,895,836` |
| SHA-256 | `2EBDC0BE7E6A5B25E50B41E38C4AE8B4D1653F29C34DD9D5936A1DAF69C63B88` |
| MD5 | `A491F2D0BF71DB6EC99344A91FC0DF9E` |

The URL is institution-controlled rather than content-addressed; the hashes pin the exact public bytes used for the audit. No source-code archive, release, commit, dependency lock, or data-package checksum was found.

The related open-access UCF thesis, [“Improving Usability of Genetic Algorithms through Self Adaptation on Static and Dynamic Environments”](https://stars.library.ucf.edu/etd2020/107/), is background evidence, not an executable or data deposit. Its persistent identifier is [DP0023153](https://purls.library.ucf.edu/go/DP0023153).

## Dimensional audit

The eleven-variable filter passes.

The solution chromosome contains 51 floating-point genes:

\[
(c_0,c_1,\ldots,c_{50})\in[-1,1]^{51}.
\]

- \(c_0\) is an intercept.
- \(c_1,\ldots,c_{25}\) are coefficients for the 25 provider/county predictors.
- \(c_{26},\ldots,c_{50}\) select exponents \(1,2,3,4\) for the corresponding coefficients through a piecewise map.

These are genuine task decisions: each coefficient and exponent selection can change the classifier. The SAGA individual also carries a separate 23-gene parameter chromosome \(p_0,\ldots,p_{22}\), but those adaptive-control genes are not needed to satisfy the task-dimension threshold.

## Official upstream data versus the unavailable analytic input

The paper says its 40,662 provider rows were built from:

1. the 2014 Medicare Provider Utilization and Payment Data: Physician and Other Supplier PUF; and
2. the 2015–2016 Area Health Resources File.

Lawful official upstream sources remain identifiable:

- [HHS/CMS CY 2014 guidance and historical file description](https://www.hhs.gov/guidance/document/physician-and-other-supplier-data-cy-2014);
- [CMS historical AMA-gated download](https://www.cms.gov/apps/ama/license.asp?file=http%3A%2F%2Fdownload.cms.gov%2FResearch-Statistics-Data-and-Systems%2FStatistics-Trends-and-Reports%2FMedicare-Provider-Charge-Data%2FDownloads%2FMedicare_Provider_Util_Payment_PUF_CY2014.zip);
- [current CMS catalog family](https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners);
- [HRSA AHRF download catalog](https://data.hrsa.gov/data/download?AHRF=&data=AHRF);
- [2015–2016 AHRF technical documentation](https://data.hrsa.gov/DataDownload/AHRF/AHRF_USER_TECH_2015-2016.zip);
- [2015–2016 county ASCII file](https://data.hrsa.gov/DataDownload/AHRF/ahrf2016.asc).

HRSA states that AHRF has no usage limitation. The historical CMS package is public but includes an AMA CPT/HCPCS license boundary. Neither source license automatically licenses an authors’ derived analytic table that was never deposited.

The article’s complete Data Availability Statement is:

> Data will be made available on request.

No public artifact contains the exact \(40{,}662\times25\) predictor table, labels, row order, or split indices. Reconstructing it from the upstream files requires undocumented decisions about:

- which provider types, credentials, and records identify physical therapists;
- NPI, HCPCS, and place-of-service aggregation;
- beneficiary deduplication and payment weighting;
- the exact HCPCS/CPT sets used for physical-agent, therapeutic-procedure, and new-patient variables;
- Doctor of Physical Therapy credential parsing;
- provider ZIP/address to county mapping and treatment of multi-location providers;
- exact AHRF field identifiers and reference years for all county variables;
- join failures, missing values, exclusions, and row ordering;
- whether each train/test split is stratified and whether it is fixed or redrawn across the 50 runs;
- the sample-versus-population standard-deviation convention.

The printed row count and median payment `$23,296.85` are only checksums in a loose descriptive sense; they cannot determine the missing row-level choices. The exact analytic input is therefore not reconstructible without fabrication.

## Classifier and objective that can be transcribed

The paper defines

\[
\operatorname{prediction}_j
=
c_0+\sum_{i=1}^{25}c_i'v_{i,j},
\]

with class one when the prediction is greater than zero and class zero otherwise. Fitness is percentage of correctly classified training rows.

For \(i=1,\ldots,25\), the corresponding exponent selector maps \(c_{i+25}\) to:

\[
c_i'=
\begin{cases}
c_i^1,&-1\le c_{i+25}<-0.5,\\
c_i^2,&-0.5\le c_{i+25}<0,\\
c_i^3,&0\le c_{i+25}<0.5,\\
c_i^4,&0.5\le c_{i+25}<1.
\end{cases}
\]

The paper describes initialization on the inclusive range `[-1,1]`, but the printed map excludes the exact endpoint \(c_{i+25}=1\). Boundary creation or repair can therefore reach a value for which Equation (3) defines no exponent.

## Stated SAGA controls

The fixed SAGA settings are:

| Setting | Value |
|---|---:|
| Population | 100 |
| Generations | 200 |
| Parent selection | Tournament, size 10 |

Each individual carries 23 parameter genes initialized in `[0,1]`:

- mutation rate and crossover rate;
- fitness/ranking genes for three mutation and eight crossover operators;
- ten operator-argument genes.

The candidate mutation operators are uniform-random, Gaussian, and polynomial mutation. The candidate crossover operators are two-point, simulated binary, blend, arithmetic, linear, simplex, PCX, and UNDX.

Algorithm 3 sorts operators by encoded fitness. At each nonlast operator it accepts the current operator when a new uniform draw is below 0.9 and otherwise advances; the last operator is selected by default. A child uses its own mutation controls. Parent crossover rates and crossover-operator fitnesses are averaged.

This is a useful conceptual design, but it is not an exact executable specification.

## Exact adaptive/operator ambiguities

### Missing argument mappings

Ten encoded argument genes lie in `[0,1]`. The paper says that values are mapped to an operator’s “expected range” when that range is not `[0,1]`, but supplies neither the target ranges nor the mapping formulas. This affects Gaussian sigma, polynomial index, SBX index, blend/arithmetic settings, simplex settings, both PCX arguments, and both UNDX arguments. The cited source papers do not identify the authors’ chosen finite encoded ranges.

### Operator variants and bounds

The paper deliberately omits detailed mathematical definitions for the complex operators and points to earlier literature. That does not fix:

- the implementation variant for each real-coded operator;
- inclusive/exclusive random endpoints;
- how children outside `[-1,1]` or parameter genes outside `[0,1]` are clipped, reflected, resampled, or rejected;
- how NaN/infinite or degenerate-parent cases are handled.

Different reasonable implementations produce different search distributions.

### Self-referential mutation

The parameter chromosome is said to evolve through the same operators as the solution chromosome. The paper does not specify:

- whether mutation rate is a per-individual event probability or a per-locus probability;
- whether mutation is selected and parameterized from the child’s pre-mutation or post-mutation control genes;
- whether one random mutation decision/operator is shared by the solution and parameter chromosomes;
- how a parameter gene controls the operation that mutates that gene itself.

### Crossover and parent accounting

The no-crossover branch is absent: it is unclear exactly how solution and parameter chromosomes are inherited when crossover is not performed. Some operators use two parents and others use three, but the pseudocode does not specify:

- when the operator is chosen relative to selecting the required number of parents;
- how parent groups are formed;
- how many offspring each operator creates;
- how population size 100 is restored when offspring counts differ;
- whether the same stochastic operator draw/arguments are applied to both chromosomes.

### Selection, replacement, and ties

Tournament sampling with or without replacement, fitness ties, survivor ties, and child-count truncation are not specified. Algorithm 3 depends only on ordering the operator-fitness genes; equal values have no tie-order rule. The magnitudes of the fitness genes otherwise do not enter the printed selection probabilities.

### RNG and implementation

No GA/SAGA implementation language, RNG family, seed, dependency version, numerical precision, or hardware environment is reported. The only named software dependency is scikit-learn for logistic regression, but its version, solver, regularization, stopping settings, and seed are absent.

The related [2019 precursor paper](https://www.cs.ucf.edu/~ecl/papers/1905.flairs.wu.liu.norat.pdf) cannot repair these omissions: it describes a materially different four-parameter SAGA and a different operator pool.

## Baseline and ablation status

The canonical GA baseline is specified at a high level:

| Setting | Value |
|---|---:|
| Population | 100 |
| Generations | 200 |
| Tournament size | 10 |
| Crossover | Two-point, rate 0.9 |
| Mutation | Uniform-random, rate 0.2 |

Logistic regression is an additional benchmark. These baselines are scientifically useful, but source, environment, exact split membership, and seeds are absent. The paper’s significant-variable and insignificant-variable reruns are feature-subset studies, not mutation/crossover/rate/operator-argument ablations. No component-wise adaptation-off experiment isolates the 23 adaptive controls.

## Runs and published targets

The paper explicitly reports **50 GA/SAGA runs for each configuration** and presents the best result, the 50-run mean, and a quantity labelled a 95% confidence interval. This corrects neither the absent seeds nor the absent run-level observations.

Table 9’s standardized-data SAGA test accuracies are:

| Test share | Best | Mean ± reported 95% CI |
|---:|---:|---:|
| 50% | 93.84 | 93.15 ± 0.54 |
| 75% | 93.86 | 93.25 ± 0.49 |
| 90% | 93.80 | 92.40 ± 1.92 |
| 95% | 93.40 | 91.91 ± 1.89 |
| 99% | 91.95 | 87.92 ± 3.02 |

For the 50% test-share configuration, Table 9 also reports:

| Method | Best | Mean ± reported 95% CI |
|---|---:|---:|
| RD-SAGA | 92.92 | 77.80 ± 13.61 |
| SD-SAGA | 93.84 | 93.15 ± 0.54 |
| RD-GA | 93.12 | 89.35 ± 0.96 |
| SD-GA | 91.32 | 90.40 ± 0.17 |
| Logistic regression | 92.90 | deterministic scalar only |

Tables and figures do not archive the 50 accuracy values, genomes, parameter chromosomes, split files, generation histories, or fitted classifiers. The CI formula—normal versus Student-\(t\), confidence-level construction, and any treatment of shared splits—is not stated.

## Why CI/SD and ≤5% cannot validate reproduction

The literal SD-SAGA 50% interval is:

\[
[93.15-0.54,\ 93.15+0.54]=[92.61,\ 93.69].
\]

It is a published aggregate, but it cannot validate a clean-room implementation when the analytic rows, split membership, operator mappings, boundary rules, implementation, and RNG are unknown. Matching it could result from compensating differences rather than algorithmic equivalence.

A relative ±5% window around 93.15 is:

\[
[88.4925,\ 97.8075].
\]

That interval contains RD-GA’s mean 89.35, SD-GA’s mean 90.40, logistic regression’s 92.90, and SD-SAGA’s own result. A method that does not implement the adaptive mechanism can therefore pass the 5% test. Such a threshold has no discriminatory value.

The absent 50 raw observations also prevent independent verification of the stated CIs or a same-seed comparison. Neither the reported CI nor a 5% band establishes exact reproduction without the missing inputs and state machine.

## MATLAB/Python feasibility and compute

A conceptual reimplementation is feasible in either MATLAB or Python:

- MATLAB would require custom implementations of all eight crossover and three mutation operators, the linked two-chromosome inheritance, argument mappings, and boundary semantics.
- Python could use NumPy/pandas/scikit-learn plus custom or third-party evolutionary operators, but DEAP/pymoo or other library variants cannot be assumed equivalent to the authors’ unavailable implementation.

Each run evaluates population 100 for 200 generations, approximately 20,000 population-member evaluations before implementation-specific initial/final accounting. Across raw/standardized SAGA/GA, five split ratios, and 50 runs, the study is substantial but practical with vectorization or parallel compute. No paper hardware or runtime benchmark is supplied. Compute is not the decisive blocker.

## Hard-fail conclusion

USA-003 passes identity, date, strict USA affiliation, lawful full-text access, adaptive-GA topicality, the 51-variable task dimension, and the existence of official upstream data sources. It fails the exact-reproduction gate because:

1. the exact 40,662-row analytic table and every split are request-only and not reconstructible from the upstream files without undocumented choices;
2. encoded argument ranges, operator variants, boundary handling, self-referential parameter mutation, multi-parent accounting, no-crossover behavior, and tie semantics are missing;
3. no code, code license, release, commit, environment, seeds, raw runs, genomes, parameter chromosomes, or traces exist;
4. the 50-run CIs cannot be independently verified or tied to a clean-room implementation;
5. a ±5% accuracy gate is broad enough for nonadaptive baselines to pass.

Implementation would require fabricating both inputs and algorithm semantics. The former score `54` is withdrawn, all eleven score dimensions are null, `final_score=null`, and the candidate is noneligible. Recovery requires the processed data and split indices, exact source with a license and immutable revision, operator mappings and boundary/state semantics, environment and RNG details, all seeds, raw 50-run outputs, and the CI calculation.

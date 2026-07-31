# USA-004 re-audit — hard fail / no-go

Audit date: 2026-07-30  
Candidate: USA-004  
DOI: [10.1145/3512290.3528863](https://doi.org/10.1145/3512290.3528863)  
Decision: **`[audit 2026-07-30] hard_fail`**

## Official identity, publication date, and strict USA affiliation

The audited work is Esteban Segarra Martinez, Stephen V. Maldonado, Annie S. Wu, Ryan P. McMahan, Xinliang Liu, and Blake Oakley, “Effects of Imputation Strategy on Genetic Algorithms and Neural Networks on a Binary Classification Problem,” *GECCO ’22*, pages 1272–1280.

- The DOI and [ACM record](https://dl.acm.org/doi/10.1145/3512290.3528863) identify the proceedings article.
- [Crossref metadata](https://api.crossref.org/works/10.1145%2F3512290.3528863) gives the online, print, issued, and publication date as **8 July 2022**. The conference ran 9–13 July 2022; those event dates are not the publication date.
- Five authors were affiliated with the University of Central Florida, Orlando, Florida. Xinliang Liu was affiliated with Lehigh University, Bethlehem, Pennsylvania.

Identity, post-2020 publication date, and strict USA affiliation pass.

## Legal full text and license boundary

The authors’ [official UCF Evolutionary Computation Laboratory project page](https://www.cs.ucf.edu/~ecl/projects/ga-data.html) links a public institution-hosted copy:

`https://www.cs.ucf.edu/~ecl/papers/2207.gecco.segarra.pdf`

The exact audited bytes were:

| Property | Value |
|---|---|
| Bytes | `1,678,534` |
| SHA-256 | `6EC925F34D92EB15212C8C0F976DDB37D8CE9B6DD1200BB323D3F5976D81CA81` |
| MD5 | `62157F1411FC69110A86CC75E9D3ECF9` |

The publisher-formatted PDF carries `© 2022 Association for Computing Machinery` and limited permission for personal or classroom copying subject to its notice. It is lawfully readable from the UCF site, but it does not carry a Creative Commons license or a general right to redistribute or adapt the article.

The cited UCF thesis, [“Improving Usability of Genetic Algorithms through Self Adaptation on Static and Dynamic Environments”](https://stars.library.ucf.edu/etd2020/107/), is an open-access general SAGA source, not a study-specific code or data archive. Its audited PDF was `3,843,478` bytes with SHA-256 `731D636E506FEA7D8D148ABF0AF407A4AFD1557230334CD1E941DBBA20EDE631`.

No study code, study-code license, data package, derived-data license, artifact badge, supplement, release, commit, or dependency lock was found.

## Dimensional audit

The requirement of at least eleven task decision variables passes.

The solution chromosome contains 51 real-valued genes in `[-1,1]`:

- one intercept;
- 25 coefficient genes, one for each provider/county predictor in Table 1;
- 25 exponent-selector genes.

Equation (1) maps each exponent selector to an integer exponent in `{1,2,3,4}`. Equation (2) applies the evolved coefficients and exponents to the 25 input features, adds the intercept, and predicts the positive class when the weighted sum is greater than zero. Because every coefficient and exponent selector can change the classifier, all 51 loci are genuine task decisions rather than GA controls.

Fitness is training-set classification accuracy. The dimensional and fitness-function gates therefore pass.

## Exact processed input is unavailable

The paper states that its 40,662 provider rows derive from:

1. the 2014 Medicare Provider Utilization and Payment Data: Physician and Other Supplier PUF; and
2. the 2015–2016 Area Health Resources File.

Lawful upstream sources remain public:

- [CMS/HHS CY2014 guidance](https://www.hhs.gov/guidance/document/physician-and-other-supplier-data-cy-2014);
- [current CMS 2014 provider/service API](https://data.cms.gov/data-api/v1/dataset/f63b48ae-946e-48f7-9f56-327a68da4e0b/data);
- [current CMS 2014 provider-summary API](https://data.cms.gov/data-api/v1/dataset/100d9e00-03cd-4105-9f58-27f9bf9ab773/data);
- [HRSA AHRF catalog](https://data.hrsa.gov/data/download?AHRF=&data=AHRF);
- [2015–2016 AHRF technical archive](https://data.hrsa.gov/DataDownload/AHRF/AHRF_USER_TECH_2015-2016.zip);
- [2015–2016 AHRF ASCII data](https://data.hrsa.gov/DataDownload/AHRF/ahrf2016.asc).

HRSA reports no usage limitation for AHRF. The detailed CMS PUF is public government data but includes an AMA CPT/HCPCS license agreement. Neither upstream source supplies or licenses the authors’ undeclared derived analytic table.

No exact `40,662 × 25` table, row identifiers, ordering, labels, data dictionary, preparation source, checksum, or immutable source revision was deposited. Reconstructing it would require unsupported choices about:

- physical-therapist/provider and credential filters;
- duplicate, suppression, and missing-value handling;
- NPI, HCPCS/CPT, and place-of-service aggregation;
- HCPCS/CPT group definitions for physical-agent, therapeutic-procedure, and new-patient features;
- provider ZIP/address to county mapping;
- exact AHRF field identifiers, years, and join rules;
- categorical location construction and one-hot encoding;
- normalization or standardization;
- exclusions and row ordering;
- median-label construction.

### Printed split inconsistency

The paper reports:

| Quantity | Rows |
|---|---:|
| Total analytic data | `40,662` |
| Training | `20,331` |
| Test | `10,016` |
| FFNN validation | `10,016` |
| Sum of reported splits | `40,363` |
| Unexplained difference | **`299`** |

No split-index artifact explains the missing 299 rows. Guessing which count is wrong would fabricate an input.

## Missingness and imputation artifacts

The paper uses nine imputation strategies, ten missingness levels from 0% through 90%, and ten unique realizations per cell. It therefore states 900 training/test dataset pairs per algorithm.

None of these artifacts is deposited:

- base split/permutation indices;
- missingness masks or imputed tables;
- RNG seeds, states, generator, or draw order;
- row-order guarantee;
- categorical-to-numeric mappings, rounding, inverse mappings, or mode-tie behavior;
- whether masks are shared across strategies and algorithms;
- whether train/test/validation data are imputed jointly, independently, or through a training-fitted imputer;
- feature scaling before KNN, DataWig, iterative imputation, or the FFNN.

The paper gives KNN `K=5`, ten iterations for the two iterative imputers, and otherwise relies heavily on defaults. It does not pin scikit-learn, Keras/TensorFlow, DataWig, MXNet, NumPy, or pandas versions. Default behavior is therefore not an immutable specification.

Each plotted cell averages ten runs, while each run also uses a different missing-data realization. Without raw observations or a documented nested design, the confidence band mixes dataset-mask variability with algorithm randomness.

## Stated adaptive controls

The fixed top-level GA settings include population 100 and 200 generations. The SAGA identifies fourteen direct self-adaptive numeric controls:

- tournament weight;
- crossover rate;
- mutation rate;
- usage rates for four mutation candidates: uniform random, Gaussian, polynomial, and swap;
- usage rates for seven crossover candidates: uniform, simulated binary, arithmetic, linear, blend, simplex, and parent-centric.

The paper states that direct mutation/crossover rates and tournament weights lie in `[0,1]`, that crossover controls are averaged across parents, and that parent-tournament weights accumulate toward a maximum total of 2. These facts establish a self-adaptive GA concept, but not a unique executable state machine.

## Critical algorithmic omissions

The paper does not supply:

- parameter-chromosome length, locus order, or initialization distribution;
- exact inheritance and variation rules for the parameter chromosome;
- operator-selection tournament participants, sampling, comparison formula, win rule, or tie behavior;
- values or ranges for Gaussian, polynomial, simulated-binary, blend, arithmetic, linear, simplex, and parent-centric operator arguments;
- per-individual versus per-locus mutation-rate semantics;
- parent count, offspring count, and population restoration for multi-parent operators;
- boundary repair for solution offspring outside `[-1,1]` or controls outside `[0,1]`;
- which child’s control genes govern mutation and whether controls act before or after their own mutation;
- whether one stochastic operator decision is shared by the solution and parameter chromosomes;
- no-crossover inheritance;
- tournament sampling with or without replacement;
- whether the individual that crosses accumulated weight 2 is included;
- a zero-weight safeguard or maximum parent-tournament size;
- elitism, replacement, truncation, and fitness-tie rules;
- the meaning of swap mutation on a heterogeneous intercept/weight/exponent chromosome;
- implementation language, RNG family, precision, hardware, or software environment.

The [2019 precursor](https://www.cs.ucf.edu/~ecl/papers/1905.flairs.wu.liu.norat.pdf) and the [2023 SAGA article](https://www.cs.ucf.edu/~ecl/papers/2301.eswa.norat.pdf) cannot be imported as exact repair sources. They use materially different SAGA variants. The 2023 article, for example, uses three mutation candidates, eight crossover candidates, a 23-locus parameter chromosome, and a fixed parent-tournament size of 10. Substituting those details would change the audited 2022 algorithm.

The paper’s statement that solution genes range over `[-1,1]` does not specify clipping or any other boundary-repair operator. The former registry claim that genes are clipped was unsupported.

## Baselines, runs, and published targets

The canonical-GA baseline is reported at a high level:

| Setting | Value |
|---|---:|
| Population | `100` |
| Generations | `200` |
| Tournament size | `10` |
| Crossover | two-point, rate `0.8` |
| Mutation | uniform, rate `0.2` |

An FFNN is an additional baseline. There is no component-wise adaptation-off ablation: SAGA and CGA differ simultaneously in operator repertoire, rates, and parent-selection behavior.

Figures 2–9 publish curves and shaded 95% confidence bands for imputation errors, training/test/control accuracy, and selected weights. They do not publish machine-readable:

- means;
- standard deviations;
- confidence-interval endpoints;
- ten run-level observations;
- predictions or fitted classifiers;
- solution or parameter chromosomes;
- missingness masks;
- convergence histories;
- adaptive-parameter trajectories.

The only textual accuracy checkpoints are approximate: FFNN training accuracy reaches as high as 98%, while CGA and SAGA control accuracy remains slightly above 80%. There is no GA fitness-by-generation convergence curve.

## Why the reported CI and ≤5% criteria cannot validate reproduction

The task’s numeric rule first requires a reproduced result to fall within a published confidence interval or standard deviation. Only graphical bands are shown; their numeric endpoints and construction method are absent. Plot digitization would add unreported extraction error and still could not recover the ten raw observations or distinguish mask variability from GA variability.

The fallback relative-error threshold of at most 5% is not appropriate because the paper does claim confidence intervals. Even if that fallback were forced:

- a relative ±5% window around 80% spans approximately 76%–84%;
- a relative ±5% window around 98% spans approximately 93.1%–100%;
- the paper itself concludes that SAGA and CGA test/control differences are not notable.

A nonadaptive canonical baseline could therefore satisfy such a band. Passing it would not demonstrate that the self-adaptive mechanism, operator tournament, or parameter chromosome was reproduced.

The absence of a convergence trace or parameter trajectory also prevents verification of the task’s mandatory adaptive-behavior and convergence requirements.

## Code and repository search

No public study repository, supplement, Zenodo/Figshare/OSF deposit, release, tag, commit, environment file, or dependency lock was found.

Two adjacent coauthor repositories are not reproduction artifacts:

- [`StephenMal/simpgenalg`](https://github.com/StephenMal/simpgenalg/tree/42a275d8724eca58f1056d258fbfca3669329cee), pinned at `42a275d8724eca58f1056d258fbfca3669329cee`, is an uncited generic GA package without a license and without this SAGA experiment, data, masks, or outputs.
- [`StephenMal/Undergrad_Thesis`](https://github.com/StephenMal/Undergrad_Thesis/tree/315daf88a3f3c4bd1ca073d146e3ebabb9fec911), pinned at `315daf88a3f3c4bd1ca073d146e3ebabb9fec911`, concerns a different study and also has no reusable license.

Under the project’s license rules, neither repository may be treated as official or reusable study code.

## Compute and language feasibility

Python is the natural ecosystem because the paper names scikit-learn, DataWig, and Keras. MATLAB could implement a conceptual surrogate with custom GA operators and suitable toolboxes, but it cannot reproduce historical DataWig/scikit-learn behavior natively.

One GA run uses roughly `100 × 200 = 20,000` population-member evaluations. Nine strategies, ten missingness levels, and ten runs imply about 18 million evaluations for each GA, or 36 million across SAGA and CGA. On 20,331 training rows and 25 feature terms, this is on the order of `1.8 × 10^13` feature-term operations before imputation and FFNN training. Compute is substantial but not the decisive blocker; missing provenance and non-unique semantics are.

## Hard-fail conclusion

USA-004 passes identity, date, strict USA affiliation, lawful reading access, adaptive-GA topicality, the 51-variable task dimension, fitness-function availability, and the existence of official upstream government data.

It fails the exact-reproduction gate because:

1. the exact processed analytic table and preparation pipeline are absent;
2. the published split arithmetic leaves 299 rows unexplained;
3. all 900 missingness/imputation instances, split indices, seeds, and RNG states are absent;
4. the SAGA parameter chromosome, operator semantics, boundary behavior, and reproduction state machine are not uniquely specified;
5. no study source, license, environment, release, or dependency lock exists;
6. no numeric CI endpoints, raw ten-run observations, convergence trace, or adaptive-parameter trajectory supplies a discriminating reproduction target;
7. a forced ±5% accuracy band could accept the nonadaptive baseline.

Implementation would require fabricating both inputs and algorithm semantics. The former score `45` is withdrawn, all eleven score dimensions are null, `final_score=null`, and the candidate is noneligible.

Recovery requires the processed `40,662 × 25` table and preparation source; source checksums; corrected split counts and indices; all masks or exact RNG states; the complete parameter-chromosome layout and state semantics; licensed study code with a pinned environment; raw ten-run results; numeric confidence-interval calculations; and convergence/adaptive-parameter traces.

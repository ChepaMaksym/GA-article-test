# USA-001 source manifest — Johnson & Carnegie (2022)

## Scope

This directory is an isolated source archive for:

> Kara Layne Johnson and Nicole Bohme Carnegie, “Calibration of an Adaptive Genetic Algorithm for Modeling Opinion Diffusion,” *Algorithms* 15(2), 45 (2022), DOI: 10.3390/a15020045.

The archive was assembled on 2026-07-30. It contains the open-access paper, the publisher's machine-readable article XML, an exact Git checkout of the authors' archived branch, and a ten-row source excerpt selected as the primary implementation target. No MATLAB implementation or registry file is part of this archive.

## Provenance

| Item | Upstream URL | Local path | Pin / retrieval fact |
|---|---|---|---|
| Article landing page | <https://doi.org/10.3390/a15020045> | — | Published 2022-01-28 |
| Publisher PDF | <https://mdpi-res.com/d_attachment/algorithms/algorithms-15-00045/article_deploy/algorithms-15-00045.pdf?version=1643378681> | `johnson_carnegie_2022_algorithms.pdf` | Direct MDPI asset; valid PDF 1.7 |
| Publisher JATS XML | <https://mdpi-res.com/d_attachment/algorithms/algorithms-15-00045/article_deploy/algorithms-15-00045.xml> | `johnson_carnegie_2022_algorithms.xml` | Direct MDPI asset used to cross-check exact captions and result statements |
| Institutional record | <https://scholarworks.montana.edu/items/42370cdc-733e-4cec-80d9-c4f5c40fc1b3> | — | Montana State University record; identifies `johnson-algorithm-2022.pdf` and CC BY |
| Institutional PDF mirror | <https://scholarworks.montana.edu/bitstreams/84ea42d3-51f3-410d-85aa-197f5c9779aa/download> | — | Legal institutional mirror; the archived local PDF was retrieved from MDPI |
| Author repository | <https://github.com/karajohnson4/DeGrootGeneticAlgorithm> | `DeGrootGeneticAlgorithm/` | Cloned from `Algorithms-archive` with Git's Schannel HTTPS backend |
| Primary target excerpt | `DeGrootGeneticAlgorithm/Simulation-Study-Data/hyper.csv.zip` → `hyper.csv` | `published_target_rows.csv` | Exact header plus source data rows 66,401–66,410 |

### Repository pin

| Field | Value |
|---|---|
| Remote | `https://github.com/karajohnson4/DeGrootGeneticAlgorithm.git` |
| Local branch | `Algorithms-archive` |
| Upstream | `origin/Algorithms-archive` |
| Commit | `2c33060320f722e6bb737b607cf0b27a9aa4256c` |
| Commit date | `2021-12-13 12:44:45 -0700` |
| Author | Kara Johnson `<kara.johnson4@msu.montana.edu>` |
| Subject | `Add files via upload` |
| History in cloned branch | 33 commits |
| Submodules | None |
| Checkout state at audit | Clean; branch and upstream both at the pinned commit (`+0/-0`) |
| Object integrity | `git fsck --full` completed successfully |

The clone retained `.git/`, so the branch, commit object, remote, and history can be inspected directly. The requested commit is both the local branch tip and `refs/remotes/origin/Algorithms-archive`.

## Licenses and reuse boundaries

- **Paper PDF and JATS XML:** © 2022 by the authors and distributed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). This is stated in the article front matter and the XML `<permissions>` block.
- **Algorithm code:** `Algorithm-Code/LICENSE` contains the complete GNU General Public License, version 3 text. The paper's Data Availability Statement also says the code “uses the GNU GENERAL PUBLIC LICENSE.” No later-version grant or per-file copyright header was found, so this manifest records the evidence as **GPL version 3**, without adding an “or later” interpretation.
- **Simulation data:** there is no root repository license and no separate license or rights statement in `Simulation-Study-Data/`. The article's CC BY license covers the article; it should not automatically be assumed to relicense the repository data. `published_target_rows.csv` is an exact excerpt of that data and does not grant additional rights.

## Integrity and inventory

All SHA-256 values below are lowercase hexadecimal hashes of the files as stored in this directory.

### Archive-level artifacts

| Path | Bytes | SHA-256 |
|---|---:|---|
| `johnson_carnegie_2022_algorithms.pdf` | 633,360 | `76dc851d356c578995821f66c5c80fc1911c87fd0d9a9b110a5e0f4c59716ccb` |
| `johnson_carnegie_2022_algorithms.xml` | 132,623 | `ac47e4330e019348ccda3247c397dc9cbaf2d61d11ca3dead1ed782420ec5dbe` |
| `published_target_rows.csv` | 1,093 | `710feb1ae22f2c7baf27ac0092b60662ac49cae53f59f3ddf2a92ecff08bad37` |
| `published_sensitivity_rows.csv` | 2,093 | `3353ef63fea27c7c89bad5107e56fc539371c85d704c036f71510f2ee32fdf33` |

### Pinned repository tracked files

`Git bytes` and `Git blob` describe the canonical content stored by commit `2c33060…`. `Checkout bytes` and SHA-256 describe the current Windows checkout. Git was configured with `core.autocrlf=true`, so text files have CRLF checkout bytes while the Git blobs retain canonical LF content. The Git commit and blob IDs are therefore the platform-independent source pins; the SHA-256 values verify this local archive.

| Tracked path | Purpose | Git bytes | Git blob (SHA-1) | Checkout bytes | Checkout SHA-256 |
|---|---|---:|---|---:|---|
| `Algorithm-Code/BlendingOperator.jl` | Pairwise blending operator | 997 | `d411318e64ab0ec6290bd2316774ddb58678a4f7` | 1,025 | `1bde78fe6db359fe8a2f3c42a2d53b385ddaa6830b4ac18ee90d8a8e62b8fd7b` |
| `Algorithm-Code/CrossoverOperator.jl` | Within-row crossover / permutation operator | 799 | `fe083fdff3be2f345ba7121749d40551b9868508` | 823 | `80f0fa410a356ccdcaf7daba02a15cc90c8949b278b4be9174f7767e6f6a01c9` |
| `Algorithm-Code/GeneticAlgorithm.jl` | Main `GA` routine and adaptive control logic | 20,634 | `029e05c0419b9555ca8a78868fa86d8ba7978f33` | 21,160 | `639d3e6868b03c2e31e1e071fde418ca7035943dcdf477afc4f9a6d4a9699bf6` |
| `Algorithm-Code/LICENSE` | GNU GPL version 3 text | 35,149 | `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7` | 35,823 | `230184f60bae2feaf244f10a8bac053c8ff33a183bcc365b4d8b876d2b7f4809` |
| `Algorithm-Code/MutationOperator.jl` | Gaussian mutation operator | 4,221 | `6a1ca65f8277a2fbc661fd563ff825556b8216ad` | 4,330 | `b1e00fccefa44088d54edaddc4dce0880e3214df8de81645f7b033bd1102f3d2` |
| `Algorithm-Code/OpinionsFunction.jl` | DeGroot / decay / bounded-confidence opinion simulation | 7,362 | `3ecd9b021d449d72aded7fa0d613e863b582a5d8` | 7,549 | `ac4ed4d5f8083e7a657b2f724d895149bf9015be00d30b071a7ccff71930dde5` |
| `Algorithm-Code/PowerDeviationFunction.jl` | Objective / power-deviation calculation | 1,502 | `bfcbdc309899f786ff6fc421733edfd2df55e4ca` | 1,537 | `41c40f0e103d088136d22dd6131213a030e49670cb7580152ba167ba2e3bcec0` |
| `Algorithm-Code/ScaleFunction.jl` | Continuous ↔ ordinal scale transformation | 2,293 | `ac0f7c14e0f52001a941c44d173086b4958a5ac0` | 2,358 | `52ab0b3bca0a145038f627f81dae9ad609bc275946f1714c72f71b7bf732e8f9` |
| `Algorithm-Code/SelectionOperator.jl` | Elite selection and gene swapping | 3,304 | `258ceea27c52ee69d8f0f3fe5f049a464b9c27d9` | 3,378 | `a633ddc864e839bad8ccda29af04ce404aec63c61031bd7ffc9c536c9d482714` |
| `Algorithm-Code/SurvivalOperator.jl` | Fitness evaluation and survivor selection | 4,510 | `eea3af53b4e0534ea6dfd4a087296eda8a19d1bc` | 4,591 | `99ce174a96c3e7c4bd7fd03e78b7f4f357844886d0054228f940d87c8a68ebad` |
| `Simulation-Study-Data/fit.csv` | Auxiliary fit trajectories | 3,655,500 | `af4c474799daa15410dc7363f0407a4bbaa7230c` | 3,733,501 | `517e3f29a89924ea907843c983d5c74d1843c75640e4d6a42ad936a94da94215` |
| `Simulation-Study-Data/hyper.csv.zip` | 2022 hyperparameter-study result archive | 9,645,367 | `369f2f439234694649054ccc0015903cbc0e338f` | 9,645,367 | `41ca24820e044b91a93f7cd8d2c327d712ccad4cb486afc48f069ed316a2e9c4` |
| `Simulation-Study-Data/recovery.csv` | Auxiliary recovery summaries | 379,149 | `48d213059191ceadec20390e312f8f9cf37d3336` | 383,050 | `d007fb4ce9bda0e111e4deccf64bca55f16ba91cab3e29377bac9f2713d8ac58` |
| `Simulation-Study-Data/useability.csv` | Auxiliary usability-study results (upstream spelling) | 10,676,095 | `15f1e28cd60084e0cb6b03be7147f3456c12439f` | 10,791,296 | `811c877faba0d04b4fd83e8dfddd5cb37afaea89c92c1cea4a6077de79bc9c20` |

### `hyper.csv.zip` entries

The ZIP central directory and CRC test passed; no corrupt entry was reported.

| Entry | Compressed bytes | Uncompressed bytes | CRC-32 | Uncompressed SHA-256 |
|---|---:|---:|---|---|
| `hyper.csv` | 9,644,883 | 40,341,801 | `69f58739` | `13db468838f6c31dacdedb90dd5c7407508994e43c903e4aeba6416977a148bc` |
| `__MACOSX/._hyper.csv` | 92 | 220 | `df63fc75` | `4ea43ac0a12b7837e7b224ef7977fddef51323de090ba4c81c24d9d868116bf2` |

`__MACOSX/._hyper.csv` is AppleDouble filesystem metadata, not study data.

## Tree and reproducibility audit

The pinned tree has two top-level content directories:

```text
DeGrootGeneticAlgorithm/
├── Algorithm-Code/          9 Julia source files + GPLv3 license text
└── Simulation-Study-Data/   3 CSV files + hyper.csv.zip
```

The article states that the algorithm is platform-independent Julia code requiring Julia 1.5 or higher. The archived code defines the main `GA` function plus the selection, blending, crossover, mutation, survival, opinion-simulation, scale, and objective functions.

Important completeness findings:

- There is no README, `Project.toml`, `Manifest.toml`, package lock, test suite, example launcher, simulation-study driver, or figure-analysis script at the pinned commit.
- The source files have no `include`, `using`, or `import` statements. Calls to `shuffle` require Julia's `Random` standard library and calls to `Normal` require an external distribution implementation such as `Distributions.jl`; dependency versions are not pinned.
- Random draws are used throughout, but no random seed or saved RNG state is present.
- The raw generating networks, adjacency matrices, true weight matrices, opinion matrices, fitted weight matrices, and per-generation histories are not archived.
- Consequently, the result CSV can be aggregated exactly, but its 437,400 runs cannot be regenerated exactly from this tree alone.

## Raw-data schemas

Types below are inferred by streaming every record. Except for the explicitly noted `NA` values and all-zero padding, no empty or non-finite value was found.

### `hyper.csv` inside `hyper.csv.zip`

This is the dataset explicitly named by the paper's Data Availability Statement. It has **437,400 rows**, **15 columns**, and no missing values. It is a complete balanced factorial:

`3 Size × 5 Ordinal × 3 Degree × 3 TimeSteps × 4 Chromosomes × 3 ProbSigma × 3 MinMax × 3 Factors × 3 Iter × 10 Run = 437,400`.

There are 43,740 design cells and exactly ten runs per cell.

| Column | Type and observed domain | Meaning |
|---|---|---|
| `""` | integer 1…437,400 | Exported R row-name / source row index |
| `Run` | integer `{1,…,10}` | Replicate within a design cell |
| `Size` | integer `{4,20,50}` | Network size / number of agents |
| `Ordinal` | integer `{5,7,10,20,30}` | Number of ordinal-scale bins |
| `Degree` | integer `{2,5,9}` | Target network degree |
| `TimeSteps` | integer `{2,3,6}` | Observed opinion time steps |
| `Chromosomes` | integer `{5,21,51,99}` | GA population size |
| `ProbSigma` | string `{Low,Medium,High}` | Grouped starting probabilities and mutation sigma |
| `MinMax` | string `{Minimal,Moderate,Extreme}` | Grouped lower/upper control-parameter limits |
| `Factors` | string `{Slow,Moderate,Rapid}` | Paper's `MultFactor` multiplicative-adjustment group |
| `Iter` | integer `{200,1000,5000}` | Common stagnation trigger used for `iterb`, `iterc`, `iterm`, `iters`, and `iterr` |
| `Time` | number 0.029514093…11,297.914261306 | Elapsed seconds, recorded at thousand-generation checks |
| `Objective` | number 0…0.0247550134906484 | Final objective value; zero is a perfect ordinal-scale solution |
| `Iteration` | integer 1,000…100,000 in 1,000 increments | Generation of stopping/checkpoint; 100,000 is the run cap |
| `Recovery` | number 0.00535740347956046…0.642676705071738 | Parameter-recovery RMSE from paper Equation (4) |

### `fit.csv`

- **78,000 rows**, 8 numeric columns: `Run`, `Time`, `Size`, `Missingness`, `SelfWeight`, `Degree`, `TimeSteps`, `Fit`.
- Inferred types: integer-like `Run`, `Time`, `Size`, `Degree`, `TimeSteps`; numeric `Missingness`, `SelfWeight`, `Fit`.
- Observed ranges including padding: `Run` 0…10, `Time` 0…20, `Size` 0…50, `Missingness` 0…0.5, `SelfWeight` 0…0.8, `Degree` 0…9, `TimeSteps` 0…11, `Fit` 0…1.7038850235796892.
- **14,040 rows are entirely zero padding**; 63,960 rows contain results.

### `recovery.csv`

- **3,900 rows**, 11 numeric columns: `Run`, `Size`, `Missingness`, `SelfWeight`, `Degree`, `TimeSteps`, `Recovery`, `MeanDegree`, `MeanSelfWeight`, `Fit`, `RMSETime`.
- Integer-like fields: `Run`, `Size`, `Degree`, `TimeSteps`; all others numeric.
- Outcome ranges including padding: `Recovery` 0…0.7250062008646103, `MeanDegree` 0…11.5, `MeanSelfWeight` 0…0.9273960414709097, `Fit` 0…1.3717874583225234, `RMSETime` 0…1.300358007348233.
- **702 rows are entirely zero padding**; 3,198 rows contain results. The 63,960 non-padding `fit.csv` records equal 20 time records for each of these 3,198 recovery records.

### `useability.csv`

- **115,200 rows**, 14 columns: `""`, `Run`, `Size`, `Degree`, `TimeSteps`, `Scale`, `Recruit`, `Adjacency`, `Bounded`, `Decay`, `Recovery`, `Modeling`, `Prediction`, `Fit`.
- Domains: source index 1…115,200; `Run` 1…10; `Size` `{10,20,50}`; `Degree` `{5,9}`; `TimeSteps` `{2,3,6}`; `Scale` `{5,7,10,20,30}`; `Recruit` `{0.5,1}`; `Adjacency` `{Build,Remove,Correct,Complete}`.
- `Bounded` and `Decay` each use `{0.1,0.5,0.9}` when applicable and each contain exactly **28,800 `NA` values**.
- Outcome ranges: `Recovery` 0.06187201…0.623804074589001, `Modeling` 0.00233866925167776…0.248960934370361, `Prediction` 0.000286859236199396…0.508057579780659, `Fit` 0…0.053665631459995.

Only `hyper.csv.zip` is identified by the 2022 paper as its generated and analyzed simulation-study data. The three auxiliary CSVs are present in the pinned tree but have no repository documentation tying their schemas to the 2022 calibration figures; they must not be silently pooled with `hyper.csv`.

## Exact published aggregates derivable from `hyper.csv`

The following values were recomputed directly from all 437,400 archived records. Percentages use the full row count as denominator. Quartile checkpoints use the default R/type-7 sample quantile, matching the conventional boxplot calculation; violin-density geometry still depends on plotting parameters that are not archived.

### Results-section headline claims

| Published statement | Exact archived calculation | Published rounding |
|---|---|---|
| 67.7% found a perfect solution within the first 1,000 generations | `count(Objective == 0 && Iteration == 1000) = 295,917`; `295,917 / 437,400 = 0.6765363511659808` | 67.7% |
| 4.5% failed to find a perfect solution within 100,000 generations | `count(Objective > 0) = 19,713`; `19,713 / 437,400 = 0.045068587105624145` | 4.5% |
| Largest final objective among failures was 0.02 | all 19,713 failures have `Iteration == 100000`; `max(Objective | Objective > 0) = 0.0247550134906484` | 0.02 |

For completeness, 417,687 rows have `Objective == 0`, or 95.49314128943759% of the archive.

### Figure 3 — recovery by stagnation trigger, early perfect solutions

Exact filter: `Objective == 0 && Iteration == 1000`. Group `Recovery` by `Iter`.

| `Iter` | n | Q1 | Median | Q3 |
|---:|---:|---:|---:|---:|
| 200 | 113,327 | 0.127616059572417 | 0.148192538088883 | 0.1704706878561365 |
| 1,000 | 91,254 | 0.15737675084126151 | 0.191371956142353 | 0.233345564141909 |
| 5,000 | 91,336 | 0.15717451742211175 | 0.1913848984616035 | 0.23309367645283025 |

These three groups contain all 295,917 early perfect-solution rows used for the published recovery comparison.

### Figure 4 — full-data recovery facets

Use all 437,400 rows. Plot/group `Recovery` by `Iter`, faceted horizontally by `ProbSigma` and vertically by `TimeSteps`. This yields 27 exact `Iter × ProbSigma × TimeSteps` distributions, each with 16,200 records. The archived columns are sufficient to recover every observation, boxplot quartile, and grouped summary in the figure. The unarchived plotting script prevents a claim of pixel-identical violin-density curves.

### Figure 5 — generations by stagnation trigger

Use all rows and plot `log10(Iteration)` by `Iter`. Rows stopped at 100,000 are the capped/failure mass described in the paper.

| `Iter` | n | Iteration Q1 | Median | Q3 | Rows at 100,000 |
|---:|---:|---:|---:|---:|---:|
| 200 | 145,800 | 1,000 | 1,000 | 1,000 | 10,541 (7.229766803840878%) |
| 1,000 | 145,800 | 1,000 | 1,000 | 3,000 | 5,431 (3.724965706447188%) |
| 5,000 | 145,800 | 1,000 | 1,000 | 6,000 | 3,748 (2.570644718792867%) |

The quartiles on the plotted scale are simply `log10` of the tabulated values.

### Figure 6 — generations by chromosomes when `Iter == 200`

Exact filter: `Iter == 200`. Plot `log10(Iteration)` by `Chromosomes`.

| Chromosomes | n | Iteration Q1 | Median | Q3 | Rows at 100,000 |
|---:|---:|---:|---:|---:|---:|
| 5 | 36,450 | 1,000 | 1,000 | 2,000 | 5,566 (15.270233196159122%) |
| 21 | 36,450 | 1,000 | 1,000 | 1,000 | 2,408 (6.6063100137174215%) |
| 51 | 36,450 | 1,000 | 1,000 | 1,000 | 1,476 (4.049382716049383%) |
| 99 | 36,450 | 1,000 | 1,000 | 1,000 | 1,091 (2.993141289437586%) |

### Figure 7 — elapsed time by chromosomes when `Iter == 200`

Exact filter: `Iter == 200`; the narrative excludes five chromosomes after Figure 6. Median `Time` values reproduce the three published numbers exactly after rounding to one decimal:

| Chromosomes | n | Exact median seconds | Published |
|---:|---:|---:|---:|
| 21 | 36,450 | 4.749346206 | 4.7 s |
| 51 | 36,450 | 10.995936021 | 11.0 s |
| 99 | 36,450 | 19.34459197 | 19.3 s |

The archived five-chromosome median is 1.2034625625 seconds, but it is not one of the three medians quoted in the paper. Timing values reproduce historical aggregates, not portable runtime expectations: the paper used a Ryzen 9 3950X, Ubuntu Server 21.10, Julia 1.5, and one thread per run.

## Primary implementation target excerpt

`published_target_rows.csv` preserves the exact `hyper.csv` header and data rows **66,401–66,410**. Counting the header, these are physical file lines 66,402–66,411. The exported row-index field also contains 66,401…66,410. A byte-line comparison against the ZIP member passed with exact equality; both use LF newlines.

The unique filter selecting these ten records is:

```text
Size        = 20
Ordinal     = 10
Degree      = 2
TimeSteps   = 6
Chromosomes = 21
ProbSigma   = Medium
MinMax      = Moderate
Factors     = Moderate
Iter        = 200
Run         = 1…10
```

This cell combines the paper's recommended starting choices (at least 21 chromosomes, medium/moderate grouped controls, and a 200-generation stagnation trigger) with a fixed network/data scenario. It is an archive-derived reproducibility target; the paper does not print this individual cell as a separate table.

| Target statistic | Exact value |
|---|---:|
| Rows | 10 |
| Final objective exactly zero | 10/10 |
| Stop at 1,000 generations | 9/10 |
| Stop at 2,000 generations | 1/10 (Run 10) |
| Mean iterations | 1,100 |
| Median iterations | 1,000 |
| Mean elapsed seconds | 4.0609745405 |
| Median elapsed seconds | 3.7008000615 |
| Mean recovery RMSE | 0.13474321290701335 |
| Median recovery RMSE | 0.13304573321886048 |

The excerpt SHA-256 is `710feb1ae22f2c7baf27ac0092b60662ac49cae53f59f3ddf2a92ecff08bad37`.

## What cannot be derived exactly

The archive supports exact recomputation of the published result counts, filters, grouped observations, conventional boxplot statistics, and reported medians above. It does **not** support:

- regenerating the 437,400 raw runs, because the study driver, random seeds/states, generated networks, true weights, and opinions are absent;
- recomputing each row's `Recovery` from true and estimated matrices, because those matrices are absent;
- recreating the exact violin-density geometry or publication graphics byte-for-byte, because the plotting code, bandwidth choices, package versions, fonts, and export settings are absent;
- reproducing historical elapsed times on different hardware or software;
- reconstructing per-generation trajectories from the final/checkpoint summaries.

These limitations do not affect the exact aggregate checkpoints computed from the archived result records.

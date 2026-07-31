# USA-002 re-audit — hard fail / no-go

Audit date: 2026-07-30  
Candidate: USA-002  
DOI: [10.1007/s41109-020-00347-2](https://doi.org/10.1007/s41109-020-00347-2)  
Decision: **`[audit 2026-07-30] hard_fail`**

## Official identity and legal full text

The audited work is Kara Layne Johnson, Jennifer L. Walsh, Yuri A. Amirkhanian, John J. Borkowski, and Nicole Bohme Carnegie, “Using a novel genetic algorithm to assess peer influence on willingness to use pre-exposure prophylaxis in networks of Black men who have sex with men,” *Applied Network Science* 6, article 22.

- The [official Springer record](https://link.springer.com/article/10.1007/s41109-020-00347-2) gives **18 March 2021** as the publication date and 22 December 2020 as the acceptance date.
- The [official publisher PDF](https://appliednetsci.springeropen.com/counter/pdf/10.1007/s41109-020-00347-2.pdf) is the version of record. Its title page, author list, affiliations, methods, Table 1, Table 2, results tables, and “Availability of data and materials” statement are the principal paper evidence used here.
- The [Montana State University ScholarWorks record](https://scholarworks.montana.edu/items/7cfc71c3-9b71-4306-932e-5a7219fc4e21) independently records the article and its CC BY license.
- The qualifying US affiliations are Montana State University, Bozeman, Montana, and the Medical College of Wisconsin, Milwaukee, Wisconsin.
- The article is licensed under CC BY 4.0. That article license does not, by itself, license repository data or code.

The old registry text gave only the year and acceptance date. The correct publication date is 2021-03-18.

## Immutable repository evidence

The paper’s data-availability statement names the repository’s **`ANS-Archive`** branch. It does not name the later `Algorithms-archive` branch. This audit fixes the cited artifact at:

- tree: [`cd5c852f4b02b5b620a28263a14bf008218d6e2c`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/tree/cd5c852f4b02b5b620a28263a14bf008218d6e2c);
- commit: [`cd5c852f4b02b5b620a28263a14bf008218d6e2c`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/commit/cd5c852f4b02b5b620a28263a14bf008218d6e2c).

The material files used in this audit have the following immutable Git blob identities:

| Path at the audited commit | Git blob SHA-1 | Bytes |
|---|---|---:|
| [`Algorithm-Code/GeneticAlgorithm.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/cd5c852f4b02b5b620a28263a14bf008218d6e2c/Algorithm-Code/GeneticAlgorithm.jl) | `029e05c0419b9555ca8a78868fa86d8ba7978f33` | 20,634 |
| [`Algorithm-Code/LICENSE`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/cd5c852f4b02b5b620a28263a14bf008218d6e2c/Algorithm-Code/LICENSE) | `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7` | 35,149 |
| [`Simulation-Study-Data/fit.csv`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/cd5c852f4b02b5b620a28263a14bf008218d6e2c/Simulation-Study-Data/fit.csv) | `af4c474799daa15410dc7363f0407a4bbaa7230c` | 3,655,500 |
| [`Simulation-Study-Data/recovery.csv`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/cd5c852f4b02b5b620a28263a14bf008218d6e2c/Simulation-Study-Data/recovery.csv) | `48d213059191ceadec20390e312f8f9cf37d3336` | 379,149 |

At this revision, the archive contains ten Julia source files and the two result CSVs above. It contains no simulation generator, experiment driver, R analysis script, Julia `Project.toml`/`Manifest.toml`, saved input matrices, initial populations, or random-seed ledger.

### License boundary

The paper says the code is available under the GNU General Public License. `Algorithm-Code/LICENSE` contains the GNU GPL version 3 text, so the code has usable GPL-3.0 terms at the audited revision. The license file is inside `Algorithm-Code`; there is no root or data-directory license and no dataset-specific grant for the two CSVs. Public readability of the CSV files is not an explicit redistribution license. The restricted PrEP pilot data are not usable without permission.

## Dimensional audit

The dimensional hard filter itself passes.

For the explicit simulation setting \(N=10,d=9\), the Erdős–Rényi probability stated by the paper is

\[
p=\frac{d}{N-1}=\frac{9}{9}=1,
\]

so the graph is complete. The implementation stores all 100 weights \(w_{ij}\). Each of the ten rows is constrained to sum to one, leaving

\[
100-10=90
\]

independent degrees of freedom. This is well above the required 11 decision variables.

The native implementation represents the matrix by rows \(W_1,\ldots,W_{10}\), with entries \(w_{i1},\ldots,w_{i10}\) in each row. The bounds are \(0\leq w_{ij}\leq1\); every row sums to one; and weights on absent ties are fixed to zero. Neither the paper nor the archived code defines a unique flattened list of 90 independent coordinates, although the feasible dimension is unambiguous.

The state model and objective are:

\[
X(t+1)=WX(t),
\qquad
f_C(\widehat X,X)=\sum_i\sum_t\bigl(\widehat x_i(t)-x_i(t)\bigr)^2.
\]

## Reported GA configuration

Table 1 of the official paper reports 22 named settings:

| Setting | Reported value |
|---|---:|
| `chromosomes` | 21 |
| `probb`, `factorb`, `maxb`, `iterb` | 0.01, 2, 0.2, 1000 |
| `probc`, `factorc`, `minc`, `iterc` | 0.2, 0.5, 0, 1000 |
| `probm`, `factorm`, `minm`, `iterm` | 0.2, 0.5, 0.01, 1000 |
| `sigma`, `factors`, `mins`, `iters` | 1, 0.5, 0.001, 2000 |
| `max_iter` | \(10^6\) |
| `min_improve`, `min_dev` | 0, 0 |
| `reintroduce`, `iterr` | elite, 2500 |

The paper states that the GA was run ten times for each generated dataset. It does not publish the seeds.

The synthetic design crosses \(N\in\{4,10,20,50\}\), degree \(d\in\{2,5,9\}\) where feasible, target self-weight \(\{0.1,0.5,0.8\}\), observed duration \(T\in\{2,3,6,11\}\), and missingness \(\{0,10,25,50\}\%\). It states that the remaining row weight is “randomly distributed” over nonself ties but does not give the probability law or algorithm. That omission prevents an independent generator from recreating the study inputs.

## Archive row audit

The two CSVs are result tables, not rerunnable inputs. Counting data records at the audited blobs gives:

| File | Total records | All-zero placeholder records | Non-placeholder records |
|---|---:|---:|---:|
| `recovery.csv` | 3,900 | 702 | 3,198 |
| `fit.csv` | 78,000 | 14,040 | 63,960 |

The intended factorial layout calls for 3,900 valid recovery records (and 78,000 corresponding fit records), so the zero rows replace expected results; they are not harmless extra padding.

For `recovery.csv`, the non-placeholder records by network size and degree are:

| \(N\) | \(d\) | Non-placeholder records |
|---:|---:|---:|
| 4 | 2 | 390 |
| 10 | 2 | 390 |
| 10 | 5 | 390 |
| 10 | 9 | 390 |
| 20 | 2 | 387 |
| 20 | 5 | 390 |
| 20 | 9 | 386 |
| 50 | 2 | 120 |
| 50 | 5 | 174 |
| 50 | 9 | 181 |

Thus the file has 3,900 physical records but only 3,198 usable non-placeholder results. Calling this complete “raw simulation data” is inaccurate.

As a consistency check, the public \(N=10,d=9\), all-row/type-7 subset of `recovery.csv` gives median `0.1565902258175686` and IQR `0.10552789120656977`, which ordinarily round to `0.16 (0.11)`. Published Table 4 reports `0.15 (0.10)`. With no archived analysis script, filtering code, or precision rule, the discrepancy cannot be resolved from the deposit.

## Paper/code conflicts

The source is useful algorithmic evidence, but it does not establish which exact executable semantics produced the paper:

1. The archived adaptation tests use strict `>` comparisons, so nominal thresholds of 1000, 2000, and 2500 stagnant iterations trigger on 1001, 2001, and 2501 under the counter semantics, not “when reached” as the paper describes. See the fixed [`GeneticAlgorithm.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/cd5c852f4b02b5b620a28263a14bf008218d6e2c/Algorithm-Code/GeneticAlgorithm.jl).
2. [`SelectionOperator.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/cd5c852f4b02b5b620a28263a14bf008218d6e2c/Algorithm-Code/SelectionOperator.jl#L23) hard-codes `elite_index != 5` although Table 1 gives a population of 21, then later logic assumes the last index is the elite.
3. [`BlendingOperator.jl`](https://github.com/karajohnson4/DeGrootGeneticAlgorithm/blob/cd5c852f4b02b5b620a28263a14bf008218d6e2c/Algorithm-Code/BlendingOperator.jl#L10) writes the first offspring into an aliased matrix and then reads the changed parent while constructing the second offspring. This is not the simultaneous two-offspring equation stated in the paper.
4. Function defaults differ from Table 1, and the missing study driver leaves no evidence that the published overrides were applied.

## Missing exact-reproduction inputs

The deposit does not contain:

- the generated adjacency and true weight matrices;
- the generated opinion trajectories or missingness masks;
- initial GA populations;
- random seeds or RNG version;
- the simulation/input generator;
- the experiment driver that supplies Table 1 values;
- the analysis script used to turn results into the published tables;
- a locked Julia environment.

The paper also leaves the nonself-weight generation distribution unspecified. These are not minor convenience omissions: recreating them would require inventing experimental inputs and choosing among conflicting operator semantics.

## Hard-filter conclusion

**No-go for strict reproduction and for the planned MATLAB implementation.**

The critical hard-filter condition “input data are available or reproducible” fails. The repository supplies incomplete output CSVs, not the inputs required to rerun the GA. The missing generator, driver, seeds, matrices, and analysis code prevent exact regeneration; the underspecified weight law and paper/code conflicts prevent a unique clean-room reconstruction. The CSV redistribution license is also unresolved.

An output-only descriptive reanalysis of the two archived CSVs is possible, subject to the unresolved data-license boundary. It is not an exact reproduction of the reported GA and must not be presented as one. USA-002 therefore has no final reproducibility score, is noneligible for ranking, and no implementation work should proceed for it.

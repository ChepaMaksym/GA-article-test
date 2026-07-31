# EU-003 re-audit — hard fail / no-go

Audit date: 2026-07-30  
Candidate: EU-003  
DOI: [10.2166/hydro.2021.045](https://doi.org/10.2166/hydro.2021.045)  
Decision: **`[audit 2026-07-30] hard_fail`**

## Official identity, publication date, affiliation, and lawful text

The audited work is Antonios Parasyris, Katerina Spanoudaki, Emmanouil A. Varouchakis, and Nikolaos A. Kampanis, “A decision support tool for optimising groundwater-level monitoring networks using an adaptive genetic algorithm,” *Journal of Hydroinformatics* 23(5), 1066–1082.

- The [official article](https://iwaponline.com/jh/article/23/5/1066/83242/A-decision-support-tool-for-optimising-groundwater) and [version-of-record PDF](https://iwaponline.com/jh/article-pdf/23/5/1066/938912/jh0231066.pdf) identify DOI `10.2166/hydro.2021.045`.
- The article was received on 4 April 2021, accepted after revision on 8 July 2021, and made available online on **28 July 2021**. The registry publication date `2021-07-28` is therefore retained.
- Parasyris, Spanoudaki, and Kampanis are affiliated with the Foundation for Research and Technology–Hellas, Institute of Applied and Computational Mathematics, Heraklion, Greece. Varouchakis is affiliated with the School of Environmental Engineering, Technical University of Crete, Chania, Greece. The strict EU-affiliation test passes.
- The [Technical University of Crete publication record](https://dias.library.tuc.gr/view/93756), its [full-text record](https://dias.library.tuc.gr/view/manf/93757), and the [OpenArchives aggregation](https://www.openarchives.gr/aggregator-openarchives/edm/dias/000058-93756?language=en) provide lawful institutional provenance.
- The article is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). That article license does not create a license for unavailable borehole data or absent source code.

Identity, date, lawful full text, and EU affiliation pass. They do not cure the reproducibility failures below.

## Audited PDF and hash caveat

The canonical article artifact is the publisher’s version-of-record PDF:

`https://iwaponline.com/jh/article-pdf/23/5/1066/938912/jh0231066.pdf`

The publisher endpoint did not yield stable bytes for local hashing during this audit, and the institutional record does not publish an official checksum. A publicly accessible Semantic Scholar file was used to inspect the equations and tables when the publisher endpoint challenged automated retrieval:

| Property | Value |
|---|---|
| Description | Earlier publisher-labelled “Corrected Proof,” not the final version of record |
| URL | `https://pdfs.semanticscholar.org/ffdd/1c08cadc4de407b5b2041cdda7ae49bfc9fc.pdf` |
| Bytes | `1,241,130` |
| SHA-256 | `80F7D3230D8D9C79BF837364A240403B8F4A0A0CD204CAC6A60CFB864E5A9B9D` |
| MD5 | `58282D543DE1F24251496ED2C75BCE46` |

This hash pins only the audited public corrected-proof bytes. It is **not** an official VOR checksum, a code commit, a data version, or an immutable reproduction archive. No source-code commit, release, DOI archive, or machine-readable data version was found.

## Dimensional audit

The decision-dimension hard filter passes.

The original monitoring network contains 70 boreholes. The three optimization scenarios remove \(k=30\), \(40\), or \(50\) boreholes. The paper represents an individual as \(k\) unique integer borehole identifiers. Equivalently, the task can be written with 70 binary decisions:

\[
y_i\in\{0,1\},\quad i=1,\ldots,70,\qquad
\sum_{i=1}^{70}y_i=k.
\]

Thus even the smallest reported chromosome has 30 integer loci, and the equivalent fixed representation has 70 binary variables with one cardinality constraint. Both readings exceed eleven true task decisions. The all-different validity requirement is material: crossover and mutation must not create duplicate borehole identifiers.

## Exact input-data blocker

The application uses 70 hydraulic-head measurements from the Mires basin during the wet period, October through April, of hydrological year 2002–2003. Interpolation comparisons use a \(100\times100\) rectangular grid restricted to the convex hull of the measurements.

The article’s Data Availability Statement is explicit:

> Data cannot be made publicly available; readers should contact the corresponding author for details.

No public machine-readable artifact was found for:

- the 70 borehole identifiers, coordinates, and measured heads;
- the exact grid coordinates, extent, and convex-hull mask;
- the initial retained/removed network used for every reported comparison;
- lag classes, bin boundaries, fitting weights, or numerical fitting procedure;
- the complete Box–Cox transform and back-transform choices;
- exact ordinary-kriging conventions and numerical solver behavior.

The related prior work, [Varouchakis et al. (2012)](https://doi.org/10.1080/02626667.2012.717174), supplies methodological context and summary information, not a licensed 70-row coordinate/head table. The related [2016 thesis metadata record](https://www.openarchives.gr/aggregator-openarchives/edm/elocus/000018-dlib_3_f_8_metadata-dlib-1482308368-41844-2033.tkl) is not a versioned code/data deposit. Digitizing maps or inferring coordinates and heads would fabricate the optimization inputs.

No standalone data license exists because no public dataset artifact exists.

## Objectives that can be transcribed

The paper defines useful high-level objectives. For removed measurement locations \(s_i\), Equation (3) gives

\[
\operatorname{RMSE}
=
\sqrt{\frac{1}{N}\sum_{i=1}^{N}
\left[z^*(s_i)-z(s_i)\right]^2}.
\]

Equation (5) compares the initial and optimized interpolation surfaces on the grid:

\[
\operatorname{RMSD}
=
\sqrt{\frac{1}{M}\sum_{i=1}^{M}
\left[z_{\mathrm{init}}(s_i)-\hat z(s_i)\right]^2}.
\]

An Akaike-based criterion is also printed in Equation (4). These scalar definitions do not reconstruct the unavailable spatial inputs, variogram fitting, kriging system, or stochastic search.

## Adaptive-mechanism conflicts

The old registry called the stepwise prose sufficient for clean-room implementation. It is not. The paper leaves multiple incompatible or undefined state machines.

### Probability versus population fractions

The uniform crossover operation is described as using a crossover probability initially set to **50%** and later changed adaptively. Separately, the paper says that the fractions of the population undergoing crossover and mutation are also modified. These may be four distinct quantities:

1. within-crossover gene probability;
2. mutation probability;
3. crossover population fraction;
4. mutation population fraction.

The paper does not give separate equations, initial values, bounds, and update rules for all four. Treating “probability,” “rate,” and “fraction” as synonyms is an undocumented implementation choice.

### Conflicting initial fractions

The method text initializes crossover/mutation/elitism fractions at:

\[
80\% / 15\% / 5\%.
\]

Table 8 compares the fully adaptive method beginning from:

\[
85\% / 10\% / 5\%.
\]

The reset instruction says to restore the initial fractions but does not resolve which initial configuration is canonical.

### Conflicting stall triggers

One passage says adaptation occurs every **five stalled generations**. Another says the mutation fraction increases and crossover fraction decreases when the stall counter **reaches 10**. Table 8 again describes a reduction every five stalled generations. The paper does not specify whether the first change is at stall 5 or 10.

### Undefined step and threshold

The change is described as 10%, but the paper does not say whether that means:

- ten percentage points, such as 15% to 25%; or
- a relative 10% change, such as 15% to 16.5%.

The prose gives a threshold of 80% without unambiguously naming the governed fraction or defining clipping. Starting mutation at 15% and adding ten percentage points yields \(15,25,\ldots,75,85\), never exactly 80%. A cap at 80%, overshoot to 85%, or a different step would have to be invented.

### Missing ordering and operator semantics

The paper does not uniquely state:

- whether the trigger test is `>`, `>=`, or an exact multiple test;
- whether adaptation occurs before or after producing the offspring of the triggering generation;
- which fitness comparison and tolerance defines an improvement;
- whether the trigger uses best-candidate fitness or the mean-fitness change mentioned elsewhere;
- whether an improvement resets probabilities, population fractions, or both;
- lower bounds and all upper bounds;
- the exact selection method and replacement behavior;
- the customized creation, integer crossover, mutation, uniqueness repair, and duplicate-handling logic.

The authors say MATLAB R2019a custom creation, crossover, and mutation functions were used, but publish none of them. MATLAB defaults cannot replace functions the authors explicitly customized.

## Baseline and ablation evidence

Table 8 compares a standard GA, a semi-adaptive GA, and the fully adaptive GA. This is useful qualitative evidence, but not a reproducibility-grade controlled ablation:

- only one apparent result is printed per configuration;
- no run count, seed, standard deviation, confidence interval, or raw result vector accompanies the comparison;
- the fully adaptive start conflicts with the method’s main initial fractions;
- no mutation-only and crossover-only controlled arms isolate the two adaptations.

The paper reports sensitivity grids for population and stall settings, but a sensitivity grid is not a substitute for repeated independent runs.

## Published scalar checkpoints

Table 3 reports the following optimization checkpoints for removal scenarios 30, 40, and 50:

| Criterion | 30 removals | 40 removals | 50 removals |
|---|---:|---:|---:|
| Optimized RMSD | 0.5671 | 0.8250 | 1.3542 |
| Optimized RMSE | 6.8550 | 14.2811 | 17.9336 |
| RMSD corresponding to RMSE solution | 0.9528 | 0.9621 | 1.1672 |
| Akaike criterion | -158.3399 | -165.3199 | -192.8193 |
| RMSD corresponding to Akaike solution | 2.2906 | 4.9930 | 8.6190 |

Table 8, for 30 removals, population 50, and stall termination 20, reports:

| Variant | Generations | Function evaluations | RMSE |
|---|---:|---:|---:|
| Fully adaptive | 118 | 5,950 | 8.042 |
| Semi-adaptive | 103 | 5,200 | 9.004 |
| Standard | 94 | 4,750 | 10.27 |

No selected-well vectors, prediction residuals, per-run rows, generation histories, or numeric convergence curves accompany these aggregates.

## Why no CI/SD or 5% target is valid

No random seed, RNG family/state, independent-run count, run-level output, standard deviation, or confidence interval is reported. The tables fluctuate non-monotonically across population/stall configurations and appear to contain individual stochastic outcomes.

For illustration only, a nominal ±5% band around Table 8’s adaptive RMSE 8.042 would be:

\[
[7.6399,\ 8.4441].
\]

There is no evidence that this band has a 95% coverage probability—or any stated coverage probability—for a correct implementation. A clean-room implementation could miss it because of the unavailable measurements, ambiguous kriging pipeline, contradictory adaptive state machine, customized operators, or ordinary stochastic variation. Treating any Table 3 or Table 8 scalar as a deterministic ≤5% acceptance target would therefore fabricate a validation rule.

## Code, environment, and compute feasibility

No official source repository, code archive, release, commit, source license, dependency lock, or author implementation was identified. The article reports MATLAB R2019a and customized GA functions. A faithful MATLAB attempt would require the relevant `ga` tooling plus custom integer-safe operators and geostatistical routines. A Python approximation could use NumPy/SciPy and kriging/GA packages, but it would not reproduce MATLAB’s customized operators, variogram fitting, transforms, or numerical conventions.

Reported runtimes range from approximately 76 to 3,171 seconds for RMSE experiments and 9,700 to 55,610 seconds for RMSD experiments. No hardware is identified. The experiment is computationally feasible, although some RMSD runs take hours; provenance and specification, not compute, are the decisive barriers.

## Hard-fail conclusion

EU-003 passes publication date, strict EU affiliation, lawful article access, adaptive-GA topicality, and the eleven-variable dimensional threshold. It nevertheless fails the exact-reproduction gate because:

1. the authors explicitly withhold the 70-borehole input data;
2. the adaptive mechanism has conflicting initial values and triggers plus undefined probabilities, steps, bounds, caps, and update order;
3. the customized validity-preserving GA operators and geostatistical implementation are unavailable;
4. there is no source code, code license, versioned data artifact, seed, run ledger, raw output, or machine-readable selected network;
5. no reported scalar has the uncertainty evidence required for a CI/SD or defensible ≤5% reproduction test.

Reproduction would require a lawfully licensed machine-readable input dataset, the authors’ exact customized operators and adaptive state machine, a pinned software environment, seeds and repeated-run protocol, and raw reference runs. Until those are supplied, implementation would require fabrication. The former score `56` is withdrawn, every score dimension is null, `final_score=null`, and the candidate is noneligible.

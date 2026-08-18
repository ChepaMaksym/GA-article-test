# Scientific novelty and claim boundary

Date checked: **2026-08-18**.

## What is not new

The project does not claim novelty for any of the following components in
isolation:

- genetic-algorithm feature selection;
- CHC or CHC-QX qualitative approximation;
- the `(1+(lambda,lambda))` genetic algorithm;
- the one-fifth-style self-adjustment rule;
- failure-at-cap reset for the `(1+(lambda,lambda))` GA;
- wrapper classification with a Decision Tree;
- balanced accuracy, BCa bootstrap, or mutation testing.

## Project contribution

The defensible incremental contribution is the reproducible integration and
verification of existing research lines:

1. a reset self-adjusting `(1+(lambda,lambda))` binary-mask search layer is
   applied to the CHC-QX/QX large-data feature-selection protocol;
2. the intervention is isolated from data preparation and classifier choice;
3. OLD and Hybrid receive paired active samples and initial masks;
4. logical wrapper-objective evaluations are counted at the objective boundary;
5. Jump and OneMax controls distinguish local-optimum behavior from unimodal
   no-regression behavior;
6. complete scientific signatures are checked for 1, 2, and 4 workers;
7. deliberate critical-code mutants test whether unit tests detect wrong
   formulas, reset timing, acceptance, selection, and NFE accounting;
8. the corrected applied track uses both official UCI Census-Income files,
   removes instance weight from predictors, uses it as sample weight, reports
   balanced metrics, varies the train/validation split, and includes a paired
   reset/no-reset Census ablation.

## Thesis-level H2 - source-compatible search efficiency

The thesis-level H2 is a **joint efficiency hypothesis**, not an accuracy-
superiority hypothesis:

> Under the frozen source-compatible protocol, Hybrid 1 has higher search
> efficiency than OLD CHC-QX if it preserves predictive quality within the
> predeclared non-inferiority margin, does not increase the typical selected-
> feature count, and reaches the matched validation target with fewer logical
> fitness evaluations.

Formally:

```text
H2 = quality preservation AND subset compactness AND logical-NFE economy
```

The immutable 30-seed evidence gives:

```text
quality preservation:
paired median Hybrid - OLD = -0.0263125 percentage point
95% BCa = [-0.0676607, -0.0012530] percentage point
margin = -0.10 percentage point
result = PASS_CONFIDENCE_BOUND

subset compactness:
OLD median = 5.5 features
Hybrid median = 5.0 features
paired median Hybrid - OLD = -1 feature
result = PASS

logical-NFE economy at validation target 0.946:
OLD median capped NFE = 319.0
Hybrid median capped NFE = 141.5
paired median reduction = 55.4990%
95% BCa = [34.9110%, 64.9701%]
result = PASS_CONFIDENCE_BOUND
```

Therefore:

```text
H2 = SUPPORTED_SOURCE_COMPATIBLE_ONLY
```

The supported claim is **search efficiency with quality preservation**, not
higher predictive accuracy. The complete definition and machine-readable data
are stored in:

- `hybrid_1/H2_SOURCE_COMPATIBLE_EFFICIENCY.md`;
- `hybrid_1/h2_source_compatible_evidence.csv`.

H2 must always be qualified as source-compatible. It does not override the
corrected official-UCI outcome, where C-H1 is `FAIL_NONINFERIORITY`.

## Literature-search result

Exact-phrase and component searches performed on 2026-08-17 found CHC-QX,
reset self-adjusting `(1+(lambda,lambda))`, and other adaptive evolutionary
feature-selection methods as separate research lines. They did not identify an
exact prior publication combining all of the following:

```text
CHC-QX/QX Census feature-selection protocol
+
reset self-adjusting (1+(lambda,lambda)) binary-mask search
+
paired exact logical-NFE comparison
+
official-test weight-aware balanced-metric validation
```

This is evidence from a documented search, not proof of worldwide priority.
The master thesis must not use an unconditional phrase such as "first in the
world".

## Allowed novelty statement

A suitable statement is:

> The work proposes and reproducibly evaluates an incremental hybrid search
> architecture that transfers reset self-adjusting `(1+(lambda,lambda))`
> parameter control to the CHC-QX/QX feature-selection setting. Its additional
> methodological contribution is a paired logical-NFE protocol with local-
> optimum controls, worker-invariance verification, deliberate-mutant test
> sensitivity, and a corrected official-UCI weight-aware validation track. In
> the source-compatible profile the hybrid satisfies the joint H2 search-
> efficiency criterion, while the corrected profile establishes the boundary
> beyond which that positive conclusion does not transfer.

## Forbidden or unsupported claims

Do not claim that:

- a fundamentally new genetic algorithm was invented;
- reset or `(1+(lambda,lambda))` was invented in this project;
- Hybrid is more accurate unless a corresponding confidence interval supports
  superiority;
- the H2 source-compatible result applies to the corrected official-UCI
  profile;
- all OLD-versus-Hybrid efficiency is caused only by reset;
- logical NFE is equivalent to wall-clock speedup;
- public CHC-QX source is identical to the printed paper;
- one Census split proves general superiority across datasets or classifiers;
- a null or negative corrected applied result invalidates successful mechanism
  tests on Jump;
- the exact combination is globally unprecedented without a systematic review.

## References used to delimit novelty

- Altarabichi et al., *Fast Genetic Algorithm for feature selection - A
  qualitative approximation approach*, DOI `10.1016/j.eswa.2022.118528`;
- Hevia Fajardo and Sudholt, *Theoretical and Empirical Analysis of Parameter
  Control Mechanisms in the `(1+(lambda,lambda))` Genetic Algorithm*, DOI
  `10.1145/3564755`;
- related adaptive and hybrid evolutionary feature-selection literature is
  retained in the literature-search ledger and final thesis bibliography.

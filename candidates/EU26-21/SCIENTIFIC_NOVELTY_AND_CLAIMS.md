# EU26-21 scientific novelty, source agreement, and claim boundary

Date re-audited: **2026-08-22**.

## Study classification

This candidate is an **applied mechanism-transfer and external-validity study**. It contains two non-interchangeable validity profiles:

1. a **source-compatible** profile tied to the pinned public CHC-QX implementation;
2. a **corrected official-UCI** profile tied to the official Census-Income train/test semantics and instance weights.

Because `old/PAPER_SOURCE_DIVERGENCES.md` records material differences between the printed CHC-QX paper and the public implementation, source-compatible numerical alignment must not be renamed a literal paper reproduction.

## Source studies

### CHC-QX source line

Altarabichi et al., *Fast Genetic Algorithm for feature selection — A qualitative approximation approach*, Expert Systems with Applications 211 (2023), DOI `10.1016/j.eswa.2022.118528`.

The paper reports that CHC-QX can converge faster than CHC and obtain higher-accuracy feature subsets, with particular benefits on large datasets. These paper-level statements define the **directional context** for the feature-selection study; they are not treated as a literal numeric target when source/paper semantics diverge.

### Reset/self-adjustment source line

Hevia Fajardo & Sudholt, *Theoretical and Empirical Analysis of Parameter Control Mechanisms in the (1+(lambda,lambda)) Genetic Algorithm*, DOI `10.1145/3564755`.

The reset/self-adjusting mechanism is prior art. This project transfers that mechanism to binary-mask search inside the CHC-QX/QX feature-selection setting and tests whether the resulting behavior survives source-compatible and corrected applied evaluation.

## What is not new

No novelty is claimed for these components in isolation:

- genetic-algorithm feature selection;
- CHC, CHC-QX, or qualitative approximation;
- the `(1+(lambda,lambda))` genetic algorithm;
- one-fifth-style parameter control;
- failure-at-cap reset;
- Decision Tree wrapper classification;
- balanced accuracy or BCa bootstrap;
- mutation testing, worker checks, or CI as standalone techniques.

## Hypotheses

### A1-Hsrc — source-compatible OLD alignment

> Under the frozen source-compatible protocol, the pinned public CHC-QX implementation reproduces the authenticated source behavior used as OLD.

Status: `PASS_SOURCE_NUMERIC_ALIGNMENT`.

This is a **Class S source-compatible result**, not `PASS_LITERAL_PAPER_PROFILE`.

### A1-Heff — source-compatible hybrid search efficiency

> Hybrid is more search-efficient than source-compatible OLD if it preserves predictive quality within the preregistered non-inferiority margin, does not increase the typical selected-feature count, and reaches the matched validation target with fewer logical wrapper-objective evaluations.

Formally:

```text
A1-Heff = quality preservation
       AND subset compactness
       AND logical-NFE economy
```

Frozen 30-seed result:

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
A1-Heff = SUPPORTED_SOURCE_COMPATIBLE_ONLY
```

The supported claim is **search efficiency with quality preservation**, not accuracy superiority and not wall-clock speedup.

### A1-Htransfer — corrected official-UCI external validity

> The source-compatible quality-preservation conclusion remains valid under the corrected official-UCI, weight-aware evaluation protocol.

Frozen result:

```text
paired median Hybrid - corrected OLD = -0.3580 percentage point
95% BCa = [-0.6932, -0.2159] percentage point
non-inferiority margin = -0.10 percentage point
A1-Htransfer = FAIL_NONINFERIORITY
```

The smaller-subset observation is retained descriptively but is blocked as a successful joint applied claim because the corrected quality gate fails.

## Agreement with the source literature

Agreement class: **PARTIAL_SOURCE_DIRECTION_ALIGNMENT_WITH_EXTERNAL_VALIDITY_BOUNDARY**.

The source-compatible profile agrees with the CHC-QX research line in the **efficiency direction**: under the frozen source semantics, Hybrid reaches the matched validation target using substantially fewer logical objective calls while preserving quality within the predeclared margin. It does **not** reproduce the CHC-QX paper's stronger accuracy-superiority statement, and it does not establish literal paper/source equivalence.

The corrected official-UCI profile then provides a measured boundary: the source-compatible quality conclusion does not transfer to the corrected weight-aware protocol. This negative result does not erase A1-Heff; it restricts where A1-Heff may be claimed.

## Reset-specific ablation

```text
reset - no-reset paired median = 0.0000 percentage point
95% BCa = [0.0000, 0.0096] percentage point
runs with reset events = 30/30
result = NO_CLEAR_EFFECT
```

Reset was exercised, but the complete OLD-versus-Hybrid efficiency difference cannot be attributed solely to reset.

## Defensible incremental contribution

The contribution is the reproducible integration and evaluation of existing research lines rather than invention of their components:

1. transfer of reset-adaptive binary-mask search into the CHC-QX/QX feature-selection setting;
2. isolation of the search intervention from data preparation and classifier choice;
3. paired active samples and initial masks across OLD and Hybrid;
4. logical wrapper-objective accounting at the objective boundary;
5. Jump and OneMax controls for local-optimum and unimodal behavior;
6. scientific-signature checks across 1, 2 and 4 workers;
7. deliberate critical-code mutants for formula, reset timing, acceptance, selection and NFE accounting;
8. a corrected official-UCI track using both official files, excluding the instance weight from predictors and using it as sample weight;
9. explicit measurement of the boundary between a positive source-compatible conclusion and a negative corrected applied transfer.

A suitable thesis-level statement is:

> The study reproducibly evaluates an incremental mechanism transfer in which reset-based adaptive parameter control is introduced into the CHC-QX/QX feature-selection setting. Under the frozen source-compatible semantics, the hybrid satisfies a joint quality-preserving search-efficiency criterion; under the corrected official-UCI weight-aware protocol, the corresponding quality-transfer hypothesis fails. The contribution is therefore both the controlled integration and the explicit measurement of its external-validity boundary.

## Terminology policy

For the transferred controller, prefer **adaptive feedback-based parameter control** or **self-adjusting search control**. Do not use “self-adaptive” as a generic synonym unless directly quoting a source that uses that term; in the classical Eiben taxonomy, self-adaptation has a narrower meaning.

## Literature-search boundary

The documented search did not identify a publication with the exact full combination of:

```text
CHC-QX/QX Census feature-selection protocol
+
reset-adjusted (1+(lambda,lambda)) binary-mask search
+
paired logical-NFE comparison
+
official-test weight-aware balanced-metric validation
```

This supports an **incremental combination claim**, not a statement of worldwide priority. Phrases such as “first in the world”, “novel genetic algorithm”, or “globally unprecedented” remain forbidden without a systematic review capable of supporting them.

## Unsupported claims

Do not claim that:

- a fundamentally new GA or reset mechanism was invented;
- Hybrid is more accurate than OLD;
- A1-Heff applies to the corrected official-UCI profile;
- all efficiency gain is caused by reset;
- logical NFE is wall-clock speedup;
- the public CHC-QX source is identical to the printed paper protocol;
- one Census experiment proves general superiority across datasets or classifiers;
- a negative corrected result invalidates source-compatible or mechanism-level evidence.

## Canonical evidence

- `old/PAPER_SOURCE_DIVERGENCES.md` — printed-paper/public-source boundary;
- `hybrid_1/H2_SOURCE_COMPATIBLE_EFFICIENCY.md` — source-compatible joint hypothesis;
- `hybrid_1/h2_source_compatible_evidence.csv` — machine-readable source-compatible evidence;
- `corrected_applied/RESULTS.md` — corrected applied result;
- `corrected_applied/METHODOLOGY_AMENDMENT.md` — corrected protocol.

# Evidence map for the master's thesis

Updated: **2026-08-22**.

This document is the authoritative claim-to-evidence ledger for the current thesis branch. It supersedes the earlier `v3 pending` wording. A workflow success is an execution gate; a scientific hypothesis is decided only by its frozen evidence rule.

## 1. Study classes

- `SOURCE_FACT` — a statement directly supported by a paper, source repository or authenticated artifact.
- `REPRODUCED_EXACT` — same frozen study cell with exact numerical/raw agreement.
- `SOURCE_COMPATIBLE` — alignment to a pinned public implementation when printed-paper/source equivalence is not established.
- `TRANSFER_TEST` — a source-grounded mechanism is moved to a different algorithm/problem/success-signal setting; this tests external validity, not source-paper reproduction.
- `CONFIRMATORY_FAIL` — a frozen improvement hypothesis did not meet its acceptance rule.
- `DEVELOPMENT_ONLY` — evidence may guide design but is not independent confirmation.
- `SYNTHESIS` — thesis-level interpretation combining empirical studies; it cannot manufacture a new experiment.

## 2. Core GSEMO research sequence

### PR #23 / R23 — exact reproduction foundation

**Source:** Ye et al., *Towards Self-adaptive Mutation in Evolutionary Multi-Objective Algorithms*.

**Hypothesis R23:** the unchanged paper-era author implementation reproduces the authenticated OneMinMax `n=100`, TwoRate, HV, `lambda=10` trajectory and published aggregate under the paper-reported stopping semantics.

| Evidence | Result |
|---|---|
| complete runs | `100/100` |
| first-hit matrix | exact `101 x 100`, 0 mismatches |
| endpoint vector | exact `100/100`, 0 mismatches |
| source mean | `61,623.78 FE` |
| authenticated Zenodo mean | `61,623.78 FE` |
| paper Table-1 display | `61,624 FE` |
| status | `REPRODUCED_EXACT / PASS_SOURCE_NATIVE_OLD` |

This is the only PR in the GSEMO sequence that may be described as an **exact numerical/raw reproduction of a published study cell**.

### PR #24 / T1 — reset-control transfer

**Sources:** Hevia Fajardo & Sudholt; Doerr, El Hadri & Pinard.

The source literature motivates success-based dynamic `lambda`, resetting/capping, and warns that uncontrolled `lambda` growth can be harmful. In PR #24 these ideas are transferred to offspring count inside exact-reproduced TwoRate GSEMO with strict hypervolume improvement as the success signal.

**T1-H1:** reset-based adaptive offspring-count control reduces paired FE relative to OLD.

```text
point estimate: -20.237076%
95% CI: [-32.412176%, +4.934754%]
status: CONFIRMATORY_FAIL
```

**T1-H2:** reset improves paired FE relative to no-reset ablation.

```text
point estimate: -2.388751%
95% CI: [-15.523548%, +10.684546%]
status: NO_CLEAR_EFFECT
```

Agreement class: `MECHANISM_TRANSFER_WITH_PERFORMANCE_NONREPLICATION`.

### PR #25 / T2 — rollback-control transfer

**Source:** Bassin & Buzdalov rollback research.

**T2-H1:** rollback offspring control reduces paired FE relative to OLD.

```text
point estimate: +1.575182%
95% CI: [-14.390699%, +19.145964%]
status: CONFIRMATORY_FAIL
```

**T2-H2:** rollback improves paired FE relative to floor-only ablation.

```text
point estimate: -11.055069%
95% CI: [-21.663500%, +9.532151%]
status: NO_CLEAR_EFFECT
```

Rollback was actually exercised (`median 55` rollback events/run). Agreement class: `STRUCTURAL_SOURCE_ALIGNMENT_WITH_FAILED_PERFORMANCE_TRANSFER`.

### PR #26 / T3 — bounded-control development→holdout study

**Source:** Hevia Fajardo & Sudholt's finding that smaller `lambda` caps can be beneficial when self-adjustment grows `lambda` excessively in the source setting.

**T3-Hdev:** at least one frozen cap gives a positive paired development effect and can be selected by the predetermined rule.

Development data are retired v2 seeds `28001..28030` and are explicitly not independent evidence.

```text
cap 15:  +5.890756%
cap 20: +15.358279%  <- selected
cap 30:  -7.224697%
cap 40: +10.231962%
cap 60:  +2.525843%
cap 100: +2.894851%
```

Status: `DEVELOPMENT_ONLY / selection criterion satisfied`.

**T3-H1:** selected `HybridCap20` reduces paired FE on untouched `29001..29030` holdout with lower 95% CI > 0.

```text
OLD marginal median: 57,563.5 FE
V3 marginal median:  53,974.5 FE
paired point estimate: -1.263559%
95% CI: [-15.884593%, +13.258223%]
status: CONFIRMATORY_FAIL
```

The lower marginal median is descriptive and is not a substitute for the frozen paired statistic.

Agreement class: `DEVELOPMENT_LEVEL_QUALITATIVE_ALIGNMENT / CONFIRMATORY_TRANSFER_FAILURE`.

## 3. Companion applied study — PR #19

PR #19 has a **different scientific novelty** and should not be silently treated as another GSEMO iteration.

**Sources:** Altarabichi et al. CHC-QX feature-selection study; Hevia Fajardo & Sudholt reset/self-adjustment study.

- `A1-Hsrc`: pinned public CHC-QX source alignment — `PASS_SOURCE_NUMERIC_ALIGNMENT`, but not literal paper reproduction because documented paper/source divergences remain.
- `A1-Heff`: quality-preserving source-compatible search efficiency — `SUPPORTED_SOURCE_COMPATIBLE_ONLY`; paired logical-NFE reduction `55.4990%`, 95% BCa `[34.9110%, 64.9701%]`, with quality and subset-size gates satisfied.
- `A1-Htransfer`: corresponding quality preservation under corrected official-UCI weight-aware evaluation — `FAIL_NONINFERIORITY`; paired median `-0.3580` percentage point, 95% BCa `[-0.6932, -0.2159]`, margin `-0.10`.

Agreement class: `PARTIAL_SOURCE_DIRECTION_ALIGNMENT_WITH_EXTERNAL_VALIDITY_BOUNDARY`.

If the final thesis remains narrowly titled around TwoRate GSEMO, PR #19 should be presented as a companion/contrast study or omitted from the main causal sequence. If the thesis question is broadened to transferability of adaptive GA parameter control across domains, PR #19 can become a full empirical chapter.

## 4. Evidence-strength ranking

| Rank | PR | Evidence strength | Reason |
|---:|---|---|---|
| 1 | #23 | **A+** | exact raw + aggregate reproduction of a frozen published cell |
| 2 | #19 | **A-** | source-compatible positive result plus corrected external-validity test; paper/source boundary explicit |
| 3 | #26 | **A-** | clean development→untouched-holdout separation; negative independent result retained |
| 4 | #25 | **B+** | strong source grounding, ablation and independent holdout; transfer effect not confirmed |
| 5 | #24 | **B+** | valid source-grounded transfer with independent holdout; larger distance from source setting |

PR #27 is `SYNTHESIS`, not an empirical rank entry.

## 5. Novelty-strength ranking

| Rank | PR | Defensible novelty |
|---:|---|---|
| 1 | #19 | applied integration + corrected external-validity boundary in feature selection |
| 2 | #26 | methodological development→holdout separation and observed generalization failure |
| 3 | #25 | rollback state-machine transfer into offspring control of exact-reproduced TwoRate GSEMO |
| 4 | #24 | reset-based success control transfer into TwoRate GSEMO |
| 5 | #23 | reproducibility foundation rather than new algorithmic mechanism |

Evidence strength and novelty are intentionally ranked separately.

## 6. Immutable identities and seed roles

### OLD

```text
GSEMO revision: fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
IOHexperimenter revision: f223c682dff0749067d00b870f83ad754f7d96f5
gsemo.hpp blob: 2693144bcfccff902343a02c6c8e48d7dd263257
main.cpp blob: 22025e4680da85c98e3bb5ea30db8334ca25dff3
```

### Seed non-reuse

| Ledger | Historical role | Current role | Independent confirmation again? |
|---|---|---|---|
| `27001..27030` | v1 confirmatory | retired diagnostic/development only | No |
| `28001..28030` | v2 confirmatory | retired; v3 development only | No |
| `29001..29030` | v3 independent holdout | retired after v3 inspection | No |

### v2 evidence

```text
workflow: 32572161500
artifact: 9475683444
SHA-256: 085a477d5594e4fedb465c5817ebf3e4c3183165456f5ea7a3205388481a2ef3
```

### v3 evidence

```text
workflow: 32573546704
artifact: 9476099058
SHA-256: 10dabff61802e9482d339742800949cacb25aad4298f87c35ad91b57d279bc98
```

## 7. Wording rules

### Use precise agreement language

Use one of:

- `exact numerical/raw reproduction`;
- `source-compatible alignment`;
- `qualitative/mechanistic agreement`;
- `failed performance transfer`;
- `external-validity boundary`.

Do not write “the results match the paper” unless the exact target and level of agreement are specified.

### After a failed improvement hypothesis

Allowed:

- “the frozen data do not support the preregistered improvement claim”;
- “the 95% bootstrap interval crosses zero”;
- “the point estimate is ... under the frozen protocol”;
- “the favorable source-side result did not transfer to this testbed”.

Not allowed:

- “the algorithms are equal”;
- “absence of effect is proven”;
- “Hybrid is better” because of a lower marginal median;
- changing metric, seed subset or acceptance margin after outcome inspection to create a PASS.

### Terminology

For our added `lambda` mechanisms prefer:

- **adaptive feedback-based parameter control**;
- **self-adjusting offspring-count control**;
- **source-grounded mechanism transfer**.

Do not use “self-adaptive `lambda`” as a generic label. The classical Eiben taxonomy gives `self-adaptive` a narrower meaning. The phrase “self-adaptive mutation” may remain when accurately describing the terminology of Ye et al.

### Avoid template language

Replace:

- “green CI means ...” → state the execution gate and hypothesis verdict directly;
- “this demonstrates ...” → “under this frozen testbed, the experiment provides evidence that ...”;
- “novel hybrid algorithm” → “incremental source-grounded mechanism transfer” unless broader novelty is independently established;
- “results partially match” → name exactly what is aligned and what is not.

## 8. Thesis-level scientific conclusion currently permitted

The current GSEMO sequence does **not** support a claim that any tested adaptive offspring-count controller improves exact-reproduced TwoRate GSEMO.

It does support a stronger methodological and external-validity conclusion:

> A published parameter-control mechanism cannot be assumed to retain its performance benefit after transfer to a different evolutionary-algorithm setting merely because the update law is structurally similar. Exact source-native baseline reproduction, explicit ablations, independent seed ledgers, and separation of development from confirmation are required to distinguish implementation correctness from a transferable performance effect.

That statement is consistent with R23 PASS and the independent T1/T2/T3 outcomes without converting negative results into success claims.

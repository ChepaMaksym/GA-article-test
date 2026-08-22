# EU26-27 final research report

Status: **COMPLETE RESEARCH AUDIT / VALID NEGATIVE HYBRID RESULT**

This document is the authoritative consolidated report for PR #26. Historical PRs #23, #24 and #25 record the development sequence but are not separate thesis studies after consolidation.

## 1. Research question

The study asks two ordered questions:

1. Can the selected published TwoRate GSEMO experimental cell be reproduced exactly from authenticated author source and raw results?
2. If the baseline is exact, do source-grounded success-based offspring-count controllers improve the number of function evaluations required to obtain the complete Pareto front?

The second question is a mechanism-transfer study. It is not a claim that the numerical results of the source parameter-control papers are being reproduced on their original problems.

## 2. Scientific sources

### 2.1 Baseline source

Furong Ye, Frank Neumann, Jacob de Nobel, Aneta Neumann and Thomas Bäck, *Towards Self-adaptive Mutation in Evolutionary Multi-Objective Algorithms*, FOGA 2023.

Frozen baseline cell:

- OneMinMax;
- dimension `n=100`;
- TwoRate GSEMO;
- hypervolume adaptation metric;
- `lambda=10`;
- initial mutation probability `1/n`;
- 100 sequential runs;
- endpoint: function evaluations until the complete Pareto front is obtained;
- paper Table-1 display: `61624 FE`.

Authenticated raw reference: Zenodo record `7880836`, member `csv/om/TwoRateL10P1HVOneMaxD100.csv`.

### 2.2 Parameter-control sources

The transferred controllers are grounded in published research on the `(1+(lambda,lambda))` GA and related multi-objective variants:

- Hevia Fajardo and Sudholt: success-based `lambda` control, caps and reset behavior;
- Doerr, El Hadri and Pinard: one-fifth-inspired dynamic parameter control in a multi-objective `(1+(lambda,lambda))` Global SEMO setting;
- Bassin and Buzdalov: rollback modification intended to damp harmful population-size growth.

These papers justify the mechanisms and transfer hypotheses. They do not imply that the mechanisms must improve TwoRate GSEMO.

## 3. Frozen hypotheses

### R1 - exact baseline reproduction

Under the paper-compatible stop semantics and frozen author/dependency revisions, the unchanged TwoRate author implementation reproduces the authenticated raw trajectory and published aggregate.

Acceptance: exact source identity, 100/100 completed runs, exact `101 x 100` first-hit matrix, exact 100-run endpoint vector, and raw mean consistent with the displayed paper value.

### T1 - reset transfer

A one-fifth-style success controller on offspring count with reset reduces paired FE relative to OLD.

Secondary: reset contributes an FE benefit relative to the same controller without reset.

### T2 - rollback transfer

A baseline-preserving rollback controller reduces paired FE relative to OLD.

Secondary: rollback contributes an FE benefit relative to the corresponding floor-only ablation.

### T3 - bounded-controller development and independent confirmation

A cap selected using retired development data generalizes to an independent holdout and reduces paired FE relative to OLD.

The development score is not confirmatory evidence. The independent holdout alone resolves T3.

## 4. Baseline reproduction result

Canonical author source:

```text
FurongYe/GSEMO
fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
```

Canonical dependency:

```text
IOHprofiler/IOHexperimenter
f223c682dff0749067d00b870f83ad754f7d96f5
release v0.3.9
```

Canonical replay uses a `10,000,000 FE` non-binding executable safety ceiling. This number is not presented as a paper budget. The author algorithm terminates a run once the entire Pareto front is obtained.

Result:

```text
complete runs:              100/100
source mean FE:             61623.78
authenticated raw mean FE:  61623.78
paper Table-1 display:      61624
maximum raw endpoint:       131875
101 x 100 first-hit matrix: EXACT
matrix mismatches:          0
100-run endpoint vector:    EXACT
endpoint mismatches:        0
```

Canonical workflow: `32565217851`.
Canonical artifact: `9474001673`.
Artifact SHA-256: `26a3fa177ab7e5cf6bc7d972bd96de2b2c7d5f2abf171ebbf21f9770073e267b`.

Verdict R1: **PASS_EXACT_REPRODUCTION**.

## 5. Historical reconstruction defect and correction

An earlier reconstruction imposed a `100000 FE` ceiling. This was invalid for the paper cell because the authenticated raw endpoint vector contains values greater than 100000 FE, including `131875`.

The author seeds one global RNG stream before the sequential 100-run campaign. Truncating one run therefore changes the RNG state entering subsequent runs and creates a cascade of mismatches. The corrected completion-based protocol exactly reproduces the raw reference.

The 100k experiments remain forensic evidence only. They are not part of the canonical baseline verdict.

## 6. Hybrid implementations and results

The original TwoRate mutation-rate adaptation is retained as an invariant. Every hybrid branch first re-runs the patched executable in ordinary `TwoRate` mode and requires exact equality with the canonical OLD trajectory before hybrid outcomes are evaluated.

### 6.1 T1 - reset controller

Frozen confirmatory seeds: `27001..27030`.

```text
OLD median FE:             55,425.0
HYBRID_RESET median FE:    62,489.0
HYBRID_NO_RESET median FE: 57,912.5

T1 primary paired median relative FE reduction:
-20.237076%
95% percentile-bootstrap CI:
[-32.412176%, +4.934754%]
T1: FAIL

reset-specific paired effect:
-2.388751%
95% CI:
[-15.523548%, +10.684546%]
reset contribution: NO_CLEAR_EFFECT
```

Workflow: `32571460043`.
Artifact: `9475506328`.
SHA-256: `5ebd8d33ea5da63463427b2a821e3aa8a2c7e208903bd90dc70c0334daa9e8d0`.

### 6.2 T2 - rollback controller

Frozen confirmatory seeds: `28001..28030`.

```text
OLD median FE:             63,782.0
HYBRID_ROLLBACK median FE: 64,136.0
HYBRID_FLOOR median FE:    56,181.5

T2 primary paired median relative FE reduction:
+1.575182%
95% percentile-bootstrap CI:
[-14.390699%, +19.145964%]
T2: FAIL

rollback-specific paired effect:
-11.055069%
95% CI:
[-21.663500%, +9.532151%]
rollback contribution: NO_CLEAR_EFFECT
```

Workflow: `32572161500`.
Artifact: `9475683444`.
SHA-256: `085a477d5594e4fedb465c5817ebf3e4c3183165456f5ea7a3205388481a2ef3`.

### 6.3 T3 - capped controller with development/holdout separation

Retired v2 ledger `28001..28030` is used only as development data.

Frozen cap family:

```text
{15, 20, 30, 40, 60, 100}
```

Development paired median relative FE reductions:

```text
cap 15:  +5.890756%
cap 20: +15.358279%  <- selected by frozen rule
cap 30:  -7.224697%
cap 40: +10.231962%
cap 60:  +2.525843%
cap 100: +2.894851%
```

The selection was persisted before the independent holdout was executed.

Frozen holdout: `29001..29030`.

```text
selected algorithm: HybridCap20
OLD median FE:       57,563.5
V3 median FE:        53,974.5

T3 paired median relative FE reduction:
-1.263559%
95% percentile-bootstrap CI:
[-15.884593%, +13.258223%]
T3: FAIL
```

The lower marginal V3 median is descriptive. It cannot override the paired preregistered statistic.

Workflow: `32573546704`.
Artifact: `9476099058`.
SHA-256: `10dabff61802e9482d339742800949cacb25aad4298f87c35ad91b57d279bc98`.

## 7. Verification

Verification asks whether the implementation executes the specified algorithms correctly.

The repository provides:

- exact upstream commit and blob checks before use;
- exact IOHexperimenter revision checks;
- unchanged-source checks for canonical OLD;
- fail-closed comparator unit and negative controls;
- wrong-preimage rejection in hybrid patchers;
- additive source patching followed by `git diff --check`;
- build of the patched C++ executable;
- smoke execution of every frozen hybrid profile;
- exact canonical OLD regression after every hybrid patch;
- controller formula tests;
- parser tests for complete/incomplete Pareto fronts;
- seed-ledger identity and disjointness checks;
- deterministic bootstrap checks;
- deterministic cap-selection and tie-break tests;
- final repository-level evidence binder audit.

A critical verification property is that an additive hybrid patch cannot proceed to interpretation if ordinary `TwoRate` no longer exactly reproduces the canonical reference.

## 8. Validation

Validation asks whether the experiment measures the stated scientific question.

### Internal validity

Strong for the frozen OneMinMax cell because OLD is reproduced at raw-trajectory level, not only by approximate summary statistics.

### Construct validity

The primary cost measure is function evaluations to complete Pareto-front discovery. It is algorithmic and does not conflate CPU speed with search efficiency.

The hybrid primary statistic is a paired per-seed relative FE reduction. Therefore a lower unpaired marginal median alone is explicitly insufficient for a success claim.

### Statistical validity

Each hybrid confirmatory experiment uses a frozen 30-seed ledger and 50,000 deterministic percentile-bootstrap resamples of the paired median relative effect. A positive superiority claim requires the lower 95% confidence bound to be greater than zero.

No tested hybrid satisfies that rule.

### Development/confirmation validity

V1, v2 and v3 confirmation ledgers are distinct. After inspection, a ledger is retired from future independent confirmation. V2 data are reused in v3 only as explicitly labeled development data. V3 then uses untouched seeds `29001..29030`.

### External validity

The final hybrid verdict is limited to the frozen `OneMinMax n=100` TwoRate/HV testbed and the tested controller mappings. The study does not prove that reset, rollback or caps are ineffective in their original source settings or on other MOEA landscapes.

## 9. CI/CD audit

The research pipeline uses commit-pinned GitHub Actions and read-only repository permissions.

Canonical OLD CI includes:

- comparator/negative tests;
- Ubuntu, macOS and Windows source build/smoke;
- exact source hashes before and after build;
- full 100-run completion replay;
- exact Zenodo comparison;
- retained evidence artifacts.

Hybrid CI includes:

- formula/statistical tests;
- source/dependency authentication;
- additive patch application;
- patched executable build;
- exact OLD regression;
- hybrid smoke tests;
- frozen seed execution;
- paired statistical analysis;
- retained raw `.dat`, reports and figures.

The consolidated PR adds a final binder workflow that runs repository syntax compilation, all candidate-local unit/negative suites and the final fail-closed evidence audit without reclassifying already inspected holdouts as fresh confirmation.

Historical confirmatory workflows remain evidence generators. Documentation-triggered reruns after outcome inspection are noncanonical and cannot replace the frozen workflow/artifact identities listed in `FINAL_EVIDENCE.json`.

## 10. Code review

### Finding C1 - historical budget reconstruction

Severity: scientific-critical, corrected.

The earlier `100000 FE` ceiling was not the paper stop condition and invalidated exact replay after the first binding run. The canonical protocol now uses completion semantics and a proven non-binding ceiling.

### Finding C2 - v3 tests duplicated part of the tested logic

Severity: medium, corrected.

The initial v3 test file independently reimplemented controller/selection formulas. It has been strengthened to import and test the real `select_cap.py` and `analyze_holdout.py` modules, exercise synthetic complete/incomplete `.dat` parsing, reject an overlapping/modified holdout ledger and verify wrong-upstream-preimage failure in the real patcher.

### Finding C3 - paired versus marginal result interpretation

Severity: scientific-critical, controlled.

V3 has a lower marginal median but a negative paired primary point estimate with a confidence interval crossing zero. Final claim wording explicitly follows the preregistered paired statistic.

### Finding C4 - source mutation risk

Severity: high, controlled.

Each hybrid patch validates exact Git blob preimages. Canonical OLD hashes are rechecked, and patched ordinary `TwoRate` must reproduce the exact canonical raw reference before a hybrid experiment is accepted as technically valid.

### Finding C5 - seed reuse risk

Severity: high, controlled.

V1, v2 and v3 confirmation ledgers are disjoint. V2 reuse is explicitly development-only in v3 and is not counted twice as independent evidence.

### Finding C6 - CI green versus scientific PASS

Severity: medium, controlled.

Operational workflow success means the frozen experiment executed and evidence was produced. It does not mean an improvement hypothesis passed. Final reports use separate operational and scientific verdicts.

No unresolved code defect found in the audited paths currently justifies changing the scientific verdict.

## 11. Final professor verdict

### Reproducibility

**ACCEPT.** The selected OLD cell is reproduced exactly at raw trajectory and aggregate levels.

### Implementation verification

**ACCEPT.** Source identity, patch preimages, builds, formula tests, negative controls, exact OLD regressions and evidence preservation provide a defensible implementation chain.

### Experimental validation

**ACCEPT WITH SCOPE LIMIT.** The paired/holdout design is valid for the frozen OneMinMax testbed. It does not establish broad cross-problem generalization.

### Hybrid improvement claim

**REJECT.** T1, T2 and T3 do not establish a preregistered independent FE-efficiency advantage. Confidence intervals cross zero for v2/v3 and v1's point estimate is unfavorable.

### Scientific value

**ACCEPT AS A VALID EMPIRICAL RESEARCH RESULT.** The contribution is not a successful new superior controller. The contribution is the exact reproduction foundation plus a controlled external-validity study showing that three source-grounded offspring-count control transfers failed to establish an independent improvement despite correct implementation and, in v3, favorable development performance.

### Thesis-safe conclusion

> Exact implementation fidelity and literature-grounded parameter-control design are not sufficient to infer performance transfer to another evolutionary algorithm. On the exactly reproduced TwoRate GSEMO / OneMinMax testbed, reset, rollback and development-selected capped offspring-count controllers did not establish the preregistered FE-efficiency improvement. The observed development-to-holdout failure supports the methodological need for exact baseline reproduction, explicit ablation, retired seed ledgers and independent confirmation.

Final classification:

```text
OLD_REPRODUCTION: PASS
IMPLEMENTATION_VERIFICATION: PASS
VALIDATION_DESIGN: PASS_WITH_SCOPE_LIMIT
HYBRID_V1_IMPROVEMENT: FAIL
HYBRID_V2_IMPROVEMENT: FAIL
HYBRID_V3_IMPROVEMENT: FAIL
RESEARCH_INTEGRITY: PASS
PROFESSOR_VERDICT: VALID_RESEARCH / NEGATIVE_HYBRID_RESULT
```

# Thesis claim corrections — 2026-08-22

This file records wording corrections that are authoritative for the next integration pass of `MASTER_THESIS_DRAFT.md`. It exists because the working manuscript still contains pre-v3 phrases such as `v3 pending`; those phrases must not be cited as current scientific status.

## 1. Working title correction

### Replace

> Самоадаптивне керування параметрами багатоцільових еволюційних алгоритмів: відтворення GSEMO та контрольована гібридизація механізмів адаптації

### With

> **Адаптивне керування параметрами багатоцільових еволюційних алгоритмів: точне відтворення TwoRate GSEMO та експериментальна перевірка переносимості механізмів керування offspring size**

Rationale: the added `lambda` rules are explicit feedback-based parameter control. Under the classical Eiben taxonomy, “self-adaptive” is narrower and should not be used as a generic label for all feedback mechanisms. Preserve the phrase “self-adaptive mutation” only when describing the terminology of the Ye et al. source study.

## 2. Core research question

### Replace any broad question equivalent to

> Can adaptive `lambda` improve the reproduced algorithm?

### With

> **To what extent do source-grounded success-based offspring-size control mechanisms retain their reported or theoretically motivated benefits when transferred to an exactly reproduced TwoRate GSEMO, and how should such transfer be evaluated without conflating source reproduction, development tuning, and independent confirmation?**

This question remains valid even though all three GSEMO transfer H1 hypotheses failed.

## 3. Thesis hypothesis structure

The final manuscript should not use one generic “Hybrid H1” across all PRs.

### R23 — reproduction

> The unchanged author implementation reproduces the authenticated OneMinMax `n=100`, TwoRate/HV/`lambda=10` source trajectory and published aggregate under the correct stopping semantics.

Verdict: **PASS / exact raw reproduction**.

### T1 — reset transfer

- `T1-H1`: reset-based adaptive offspring-count control reduces paired FE vs OLD. **FAIL**.
- `T1-H2`: reset improves paired FE vs no-reset. **NO_CLEAR_EFFECT**.

### T2 — rollback transfer

- `T2-H1`: rollback reduces paired FE vs OLD. **FAIL**.
- `T2-H2`: rollback improves paired FE vs floor-only. **NO_CLEAR_EFFECT**.

### T3 — bounded-control development/generalization

- `T3-Hdev`: a positive cap can be selected on frozen development data. **Satisfied as development criterion only**; cap 20 selected at `+15.358279%` paired median.
- `T3-H1`: selected cap 20 improves OLD on untouched holdout. **FAIL**; paired estimate `-1.263559%`, 95% CI `[-15.884593%, +13.258223%]`.

## 4. Abstract replacement — GSEMO results paragraph

Use the following factual structure rather than the stale v1/v2-only paragraph:

> Після точного відтворення baseline було проведено три незалежно визначені ітерації перенесення success-based керування кількістю offspring. Reset-вариант не підтвердив покращення: paired median relative FE reduction становила `-20.237%`, 95% bootstrap interval `[-32.412%, +4.935%]`. Rollback-вариант дав point estimate `+1.575%`, але interval `[-14.391%, +19.146%]` перетнув нуль. У третій ітерації верхню межу `lambda` обирали лише на retired development ledger із замороженої множини `{15,20,30,40,60,100}`; правило вибрало cap `20` із development effect `+15.358%`. На незалежних seeds `29001..29030` цей ефект не відтворився: paired estimate становила `-1.264%`, 95% interval `[-15.885%, +13.258%]`. Отже, жодна з трьох transfer-гіпотез не дала статистично підтвердженої переваги над точно відтвореним baseline, а третя ітерація безпосередньо показала розрив між development selection та independent confirmation.

## 5. Scientific novelty replacement

### Do not write

> A new hybrid algorithm improves GSEMO.

No confirmatory result supports that sentence.

### Use

> **Наукова новизна полягає в систематичній експериментальній перевірці переносимості кількох опублікованих success-based parameter-control ideas до точно відтвореного TwoRate GSEMO при незмінному mutation controller, а також у процедурі, яка розділяє source reproduction, mechanism transfer, ablation, development selection та independent confirmation.**

A narrower algorithmic statement is allowed for individual PRs:

- PR #24: incremental reset-control transfer;
- PR #25: incremental rollback-control transfer;
- PR #26: bounded-control family plus development→holdout selection protocol.

No statement of “first adaptive-lambda MOEA” is allowed because prior work already includes dynamic `lambda` in multi-objective Global SEMO.

## 6. Main conclusion replacement

### Avoid

> The hybrid was unsuccessful.

This is scientifically too coarse because implementation validity and transfer-performance validity are different.

### Use

> **Усі три transfer implementations пройшли source-regression та execution gates, однак жодна не пройшла відповідний незалежний improvement gate. Отже, коректність реалізації source-grounded control law не є достатньою умовою для переносимості його performance benefit до іншого EA setting.**

Then state separately:

- v1: unfavorable/uncertain reset transfer;
- v2: rollback performance transfer not confirmed;
- v3: development-selected cap did not generalize.

## 7. Wording replacements throughout the manuscript

| Avoid | Replace with |
|---|---|
| `green CI means the experiment passed` | `execution gates passed; the scientific hypothesis is decided by the frozen statistical criterion` |
| `results match the paper` | name the exact class: `exact raw reproduction`, `source-compatible alignment`, `qualitative mechanism alignment`, or `failed performance transfer` |
| `self-adaptive lambda controller` | `adaptive feedback-based lambda control` or `self-adjusting offspring-count control` |
| `novel hybrid algorithm` | `incremental source-grounded mechanism transfer` unless broader novelty is independently established |
| `v3 demonstrated improvement during development` | `v3 showed a positive development estimate; this was development-only and did not generalize to holdout` |
| `the lack of significance proves no effect` | `the frozen data do not establish the preregistered improvement; the interval includes zero` |
| `lower median means Hybrid is better` | `the marginal median is descriptive; the paired preregistered statistic determines the hypothesis` |
| `partial reproduction` without detail | explicitly name which formula, trajectory, aggregate, direction, or source behavior agrees and which does not |

## 8. PR #19 placement

PR #19 has a different applied novelty. It should not be inserted into the GSEMO sequence as “Hybrid v0” or another λ iteration.

Two defensible options exist:

1. **Narrow GSEMO thesis:** keep PR #19 as a companion/contrast study or appendix.
2. **Broader transferability thesis:** make PR #19 a separate applied chapter showing that source-compatible efficiency can be positive while corrected external validation fails.

If included, the exact hypotheses are `A1-Hsrc`, `A1-Heff`, and `A1-Htransfer` from `PR_SCIENTIFIC_AUDIT.md` and `EVIDENCE_MAP.md`.

## 9. Current authoritative thesis conclusion

> **The exact baseline reproduction succeeds. The tested reset, rollback, and bounded offspring-count mechanisms are all scientifically valid source-grounded transfer experiments, but none establishes an independent FE-efficiency improvement in the frozen TwoRate GSEMO testbed. The cumulative contribution is therefore not a positive “best hybrid” result; it is a reproducible map of transfer failures and a methodology for distinguishing implementation fidelity, development performance, and generalizable algorithmic benefit.**

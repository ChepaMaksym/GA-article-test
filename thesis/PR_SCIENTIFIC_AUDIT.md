# Професорський аудит наукових PR

Дата аудиту: 2026-08-22.

Цей документ відділяє три речі, які не можна змішувати в магістерській роботі:

1. **відтворення опублікованого результату**;
2. **перенесення опублікованого механізму в інший алгоритм або протокол**;
3. **власну експериментальну або методологічну новизну**.

Негативний результат не робить дослідження невалідним. Невалідним воно стає тоді, коли механізм не має джерела, результат джерела приписується іншому алгоритму, development-дані видаються за confirmation або формулювання сильніше за фактичний evidence.

---

## 1. Класи збігу з джерелом

### Class R — numerical/raw reproduction

Однакові або належно заморожені:

- algorithm/profile;
- problem and dimension;
- metric/end point;
- source/dependency identity;
- stopping semantics;
- published/authenticated target.

Тільки Class R дозволяє слово **reproduction / відтворення** без додаткового застереження.

### Class S — source-compatible alignment

Відтворюється поведінка публічного source/artifact, але printed-paper protocol не можна повністю ототожнити з source implementation. Такий результат може бути сильним, але його треба називати **source-compatible**, а не literal paper reproduction.

### Class T — mechanism transfer

Зі статті береться формула, state machine або принцип parameter control, але змінюється алгоритм, benchmark, success signal або controlled role of the parameter. Тут перевіряється **external validity / transfer hypothesis**. Навіть повний збіг напрямку ефекту не є numerical reproduction джерельної статті.

---

# 2. Сортування за силою доказу

| Rank | PR | Тип | Оцінка | Пояснення |
|---:|---|---|---|---|
| 1 | #23 | Class R exact reproduction | **A+** | Повний `101 x 100` first-hit matrix та `100/100` endpoint vector збігаються з authenticated Zenodo; mean `61623.78` узгоджується з paper display `61624`. |
| 2 | #19 | Class S + applied external-validity test | **A-** | Є source-compatible positive track і окремий corrected official-UCI negative track; paper/source divergences задокументовані, а позитивний висновок не переноситься між профілями. |
| 3 | #26 | Class T + clean development/holdout split | **A-** | Сильний дизайн: cap family заморожена, development selection завершено до holdout, independent H1 не пройшов. Слабше за #23 тільки тому, що це не reproduction source result. |
| 4 | #25 | Class T rollback transfer | **B+** | Чисте джерело rollback, ablation, незалежний holdout; performance transfer не підтверджено. |
| 5 | #24 | Class T reset transfer | **B+** | Валідний transfer test із незалежним ledger, але відстань від source setting більша: інший algorithm role для `lambda` і HV-based success signal. |

`PR #27` не входить у цей рейтинг: це **synthesis/thesis PR**, а не окремий stochastic experiment.

---

# 3. Сортування за власною науковою новизною

| Rank | PR | Новизна | Професорська оцінка |
|---:|---|---|---|
| 1 | #19 | Перенесення reset-adaptive binary-mask search у CHC-QX/QX feature-selection setting + paired logical-NFE protocol + corrected weight-aware external validation | **найсильніша прикладна новизна** |
| 2 | #26 | Source-motivated bounded `lambda` family + explicit development→independent-holdout selection protocol; empirical case of development gain failing to generalize | **сильна методологічна новизна** |
| 3 | #25 | Перенесення rollback state machine на offspring-count control у exact-reproduced TwoRate GSEMO | **чітка incremental algorithmic novelty** |
| 4 | #24 | Перенесення reset one-fifth-style control на offspring-count control у TwoRate GSEMO | **валідна, але більш базова transfer novelty** |
| 5 | #23 | Exact source-native reconstruction of a published cell | **фундаментальна reproducibility contribution, але не новий алгоритм** |

Ці дві таблиці навмисно мають різний порядок. Сила доказу і сила новизни — не одна характеристика.

---

# 4. Окремі гіпотези для кожного PR

## PR #19 — applied CHC-QX hybridization

### A1-Hsrc — source-compatible alignment

> Пінована публічна CHC-QX implementation відтворює зафіксовану source-compatible поведінку під нашим frozen protocol.

**Verdict:** `PASS_SOURCE_NUMERIC_ALIGNMENT`.

Це Class S, а не literal printed-paper reproduction, тому що `PAPER_SOURCE_DIVERGENCES.md` фіксує відмінності в active sampling, `q`, objective, split semantics, convergence, mutation, initialization та HUX.

### A1-Heff — source-compatible hybrid efficiency

> Hybrid зберігає predictive quality у межах non-inferiority margin, не збільшує typical subset size та використовує менше logical wrapper-objective evaluations для matched target.

**Verdict:** `SUPPORTED_SOURCE_COMPATIBLE_ONLY`.

Ключовий результат: paired median logical-NFE reduction `55.4990%`, 95% BCa `[34.9110%, 64.9701%]`, при quality gate PASS і paired median `-1` feature.

### A1-Htransfer — corrected official-UCI external validity

> Source-compatible quality-preservation conclusion переноситься на corrected official-UCI weight-aware protocol.

**Verdict:** `FAIL_NONINFERIORITY`.

Це дуже важлива negative boundary, а не причина видаляти позитивний source-compatible experiment.

### Збіг із джерелом

Altarabichi et al. повідомляють швидшу convergence CHC-QX і вищу accuracy порівняно з CHC, особливо на великих datasets. Наш source-compatible experiment **збігається в efficiency direction**, але не відтворює accuracy-superiority claim; corrected profile додатково не проходить non-inferiority. Отже: **partial directional agreement only**.

---

## PR #23 — exact TwoRate GSEMO reproduction

### R23-H1 — exact source-native reproduction

> Незмінений author implementation із замороженою paper-era dependency та paper stopping semantics відтворює authenticated raw trajectory і published aggregate для OneMinMax `n=100`, TwoRate, HV, `lambda=10`.

**Verdict:** `PASS_SOURCE_NATIVE_OLD`.

### Збіг із джерелом

- first-hit matrix: exact `101 x 100`, 0 mismatches;
- endpoint vector: exact `100/100`, 0 mismatches;
- source mean: `61623.78 FE`;
- authenticated mean: `61623.78 FE`;
- paper display: `61624 FE`.

Це **full target-cell agreement**, не “половина сходиться”.

---

## PR #24 — reset transfer to TwoRate GSEMO

### T1-H1 — transfer benefit

> Reset-based adaptive offspring-count control зменшує paired FE відносно exact OLD.

**Verdict:** `FAIL`.

Effect `-20.237076%`, 95% CI `[-32.412176%, +4.934754%]`.

### T1-H2 — reset-specific effect

> Reset є кращим за ідентичний transferred controller без reset.

**Verdict:** `NO_CLEAR_EFFECT`.

### Збіг із джерелом

Hevia Fajardo & Sudholt показують користь reset/capping на `Jump_k`; Doerr et al. показують користь one-fifth-inspired dynamic parameters у їхньому `(1+(lambda,lambda))` Global SEMO на OneMinMax. У PR #24 **формула/ідея має валідне джерело**, але favorable performance direction **не переноситься**. Це negative transfer study, не failed reproduction.

---

## PR #25 — rollback transfer

### T2-H1 — rollback vs OLD

> Source-grounded rollback offspring controller покращує paired FE відносно exact OLD.

**Verdict:** `FAIL`.

Effect `+1.575182%`, 95% CI `[-14.390699%, +19.145964%]`.

### T2-H2 — rollback-specific effect

> Rollback покращує paired FE відносно floor-only ablation.

**Verdict:** `NO_CLEAR_EFFECT`.

### Збіг із джерелом

Bassin & Buzdalov показують, що rollback може зменшувати шкоду від надто агресивного one-fifth `lambda` growth у їхньому `(1+(lambda,lambda))` GA setting. У нашому GSEMO transfer rollback state machine є source-grounded і реально активується, але favorable source-side performance **не підтверджується**. Це чиста boundary-of-generality result.

---

## PR #26 — bounded-control development→holdout study

### T3-Hdev — development selection criterion

> Серед заморожених caps `{15,20,30,40,60,100}` існує source-motivated cap із positive paired development effect.

**Verdict:** development criterion satisfied; cap 20 selected at `+15.358279%`.

Це не confirmatory hypothesis.

### T3-H1 — independent generalization

> Development-selected cap 20 дає positive paired FE reduction на untouched `29001..29030` holdout із lower 95% CI > 0.

**Verdict:** `FAIL`.

Effect `-1.263559%`, 95% CI `[-15.884593%, +13.258223%]`.

### Збіг із джерелом

Hevia Fajardo & Sudholt показують, що менший cap може бути корисним на `Jump_k`. Наш development set має **qualitative alignment** із цим source proposition, але independent holdout не підтверджує transfer. Саме розрив development→holdout є найціннішим результатом PR #26.

---

# 5. Що є достатнім “частковим збігом” із джерелом

Фразу “в мене половина сходиться” не слід використовувати в академічному тексті. Треба вказувати конкретний рівень agreement:

| PR | Правильне формулювання agreement |
|---|---|
| #19 | source-compatible efficiency-direction agreement; paper-level accuracy superiority not reproduced; corrected transfer fails |
| #23 | exact raw and aggregate reproduction of frozen published cell |
| #24 | source-grounded mechanism, favorable performance transfer rejected |
| #25 | source-grounded rollback mechanism, favorable performance transfer rejected |
| #26 | qualitative development alignment with capped-control source result, independent transfer rejected |

Таким чином кожний empirical PR має валідне наукове джерело, але **не кожний PR є reproduction study**. Це треба зберегти у формулюваннях.

---

# 6. Формулювання, які треба уникати

## Замість шаблонного “green CI means ...”

Використовувати:

> Workflow completion establishes execution validity only; the scientific hypothesis is decided by the frozen statistical criterion.

Або ще краще — просто навести gate status та hypothesis verdict без пояснення кольору CI.

## Замість “this demonstrates that ...” при одному benchmark

Використовувати:

> This experiment provides evidence that ... under the frozen protocol.

або:

> In this testbed, the result is consistent/inconsistent with ...

## Замість “novel hybrid algorithm”

Використовувати:

> source-grounded mechanism transfer / incremental hybridization.

Поки немає broader-problem evidence, слово “new algorithm” є занадто широким.

## Замість “self-adaptive lambda” для наших feedback rules

За Eiben taxonomy використовувати:

> adaptive feedback-based parameter control / self-adjusting `lambda` control.

Термін `self-adaptive mutation` можна залишати при цитуванні Ye et al., бо це термін source paper.

## Замість “results match the paper”

Уточнювати один із класів:

- exact numerical/raw reproduction;
- source-compatible alignment;
- qualitative/mechanistic agreement;
- failed performance transfer.

---

# 7. Рекомендація для магістерської

Якщо магістерська залишається вузько про **TwoRate GSEMO**, логічне ядро таке:

1. PR #23 — reproduction foundation;
2. PR #24 — reset transfer failure;
3. PR #25 — rollback transfer failure;
4. PR #26 — bounded-control development→holdout failure;
5. загальний висновок — published parameter-control mechanisms не можна переносити між EA settings лише за схожістю формули; потрібні source-native baseline, ablations та independent holdouts.

У такій роботі головна новизна не повинна звучати як “Hybrid покращив GSEMO”, бо жоден confirmatory H1 цього не показав. Сильніший і чесніший thesis claim:

> **Систематична експериментальна оцінка переносимості success-based offspring-size control до точно відтвореного TwoRate GSEMO та методологія, що відокремлює source reproduction, mechanism transfer і незалежне підтвердження.**

PR #19 має іншу, прикладну новизну і може бути:

- окремим розділом ширшої магістерської про transferability adaptive GA control across domains; або
- самостійною companion study.

Його не слід механічно змішувати з GSEMO sequence, якщо назва й research question магістерської залишаються вузько про multi-objective GSEMO.

---

# 8. Підсумковий професорський verdict

- **#23 — accept as exact reproduction foundation.**
- **#19 — accept as applied incremental research with explicit source/corrected-profile boundary.**
- **#24 — accept as negative transfer study; do not call it reproduction.**
- **#25 — accept as negative rollback-transfer study; strong source grounding.**
- **#26 — accept as methodologically strongest transfer iteration; emphasize development/holdout non-generalization rather than lower marginal median.**
- **#27 — keep as synthesis only; it must report the above study types without manufacturing an extra empirical claim.**

# Стан дослідження

Дата зрізу: 9 вересня 2026 року.

## Поточний етап

Попередній 15-кандидатний literature cohort завершено як задокументований
negative reproduction result. Після нього відкрито окреме активне дослідження
EU26-21 для CHC-QX, Census-Income і Hybrid 1 у гілці
`research/EU26-21-chcqx-census-old-first` та draft PR #19.

| Етап | Стан | Результат |
|---|---|---|
| 15-кандидатний search cohort | Завершено | 15 кандидатів: 7 EU + 8 USA |
| Eligibility / deep audit cohort | Завершено | 2 `hard_pass`, 3 `conditional_noneligible`, 10 `hard_fail` |
| Ranked execution cohort | Завершено | 2/2 eligible виконані, обидва numerical FAIL |
| EU26-21 public-source OLD | Завершено | `PASS_SOURCE_NUMERIC_ALIGNMENT` |
| EU26-21 Hybrid mechanism controls | Завершено | Jump, OneMax, NFE і worker-invariance controls PASS |
| EU26-21 source-compatible H1-H3 | Завершено | `PASS_EXTENDED_30_SEED_H1_H2_H3` |
| EU26-21 corrected official-UCI profile | Завершено | `PASS_PROTOCOL_RESULTS_AVAILABLE` |
| Corrected C-H1 | Завершено | `FAIL_NONINFERIORITY` |
| Corrected C-H2 | Завершено | `BLOCKED_BY_H1` |
| Corrected C-H8 reset ablation | Завершено | `NO_CLEAR_EFFECT` |
| EU26-21 common-objective bridge | Завершено, 30/30 пар | `FAIL_NONINFERIORITY`; AUC/sparsity claims заблоковані quality gate |
| Strict immutable replay / complete quality audit | Завершено | 112 tests PASS на research SHA; bridge та історичні artifacts переагреговані без optimizer rerun |
| Фінальний науковий звіт і візуалізації | Завершено | 117 tests PASS на reporting SHA; CI сформував 30-row CSV, таблиці, два графіки та hash manifest |
| PR #19 | Відкритий draft | Merge не виконано |

## EU26-21 - окремі історичні та новий профілі

EU26-21 має два історичні профілі й завершений новий common-objective bridge.
Їхні результати не можна об'єднувати або взаємозамінювати.

### Новий common-objective bridge

За замороженим протоколом виконано 30 пар `41001..41030`, 40-бітні маски,
400 calls на групу, спільний evaluator, reset off. Research SHA:
`79c9b154206cdc3d318b90b598c7f0f48ca02b53`.
Матриця [34233477859](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34233477859)
та незалежний від пошуку replay
[34234286460](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34234286460)
завершилися успішно.

Парна test-WBA різниця lambda−CHC: медіана −0,013734 в.п.,
95% BCa [−0,208726; +0,151807] в.п. Нижня межа не перевищує −0,10 в.п.,
тому non-inferiority не підтверджено. Позитивна validation-AUC різниця та
медіана парної різниці −1 ознака не підміняють failed quality gate. Інтервал містить нуль:
це не доказ однозначної гіршості методу.

Звіт, математична модель, перевірка related work та точні IDs/SHA-256:
[магістерський науковий звіт](candidates/EU26-21/common_bridge/THESIS_REPORT_UK.md).
Історичні архіви окремо перевірено в
[34233480959](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34233480959).
Описовий фінальний пакет сформовано в
[34315178330](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34315178330),
artifact [10089818679](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34315178330/artifacts/10089818679).
Reporting SHA `4a4bf9ebe5d1385689172fa5fc7a92ced2a5b91b` відокремлений від
research SHA; жодної моделі або scientific decision повторно не обчислювали.

### Source-compatible профіль

Збережено:

- upstream encoded Census representation;
- 41-бітну feature mask;
- source-oriented 60/20/20 split;
- accuracy objective;
- поведінку pinned public CHC-QX source.

За 30 paired seeds:

```text
H1 accuracy non-inferiority: PASS_CONFIDENCE_BOUND
H2 paired feature count: PASS
H3 logical NFE reduction: PASS_CONFIDENCE_BOUND
```

Primary H3 target 0.946:

```text
OLD median capped NFE: 319.0
Hybrid median capped NFE: 141.5
paired median reduction: 55.50%
95% BCa: [34.91%, 64.97%]
```

Це доказ для historical source-compatible профілю. Він не є доказом corrected
weighted balanced-accuracy non-inferiority або wall-clock speedup.

### Corrected applied профіль

Виправлено applied-validity обмеження:

- використано official raw `census-income.data` і held-out
  `census-income.test`;
- raw instance-weight index 24 вилучено з predictors;
- predictive mask зменшено з 41 до 40 біт;
- instance weights передаються до fitting і weighted metrics;
- primary objective змінено на weighted balanced accuracy;
- 30 stratified train/validation splits змінюються між paired seeds;
- додано equal-budget sequential reset/no-reset Census ablation.

Immutable secure evidence:

```text
source run: 32049437836
artifact: 9297184026
artifact SHA-256: 13d2f691eefb46067d3cdffbad4c22c032c429ce91600a33addbd3f5887bbdeb
seed rows: 30/30
strict row-validation errors: 0
independently regenerated plots: 5/5
```

C-H1:

```text
Hybrid H1 - corrected OLD paired median: -0.3580 percentage point
95% BCa: [-0.6932, -0.2159] percentage point
preregistered margin: -0.10 percentage point
result: FAIL_NONINFERIORITY
```

C-H2:

```text
paired median feature-count difference: -1 feature
result: BLOCKED_BY_H1
```

C-H8:

```text
reset - no-reset paired median: 0.0000 percentage point
95% BCa: [0.0000, 0.0096] percentage point
reset exercised: 30/30 runs, 49 events
result: NO_CLEAR_EFFECT
```

Негативний C-H1 і нульовий C-H8 є валідними науковими результатами, а не
protocol failure. Вони не перейменовуються на PASS і не усуваються tuning-ом.

Канонічні EU26-21 матеріали:

- [огляд кандидата](candidates/EU26-21/README.md);
- [source-compatible результати](candidates/EU26-21/hybrid_1/RESULTS.md);
- [corrected результати](candidates/EU26-21/corrected_applied/RESULTS.md);
- [межі novelty і claims](candidates/EU26-21/SCIENTIFIC_NOVELTY_AND_CLAIMS.md).

## Попередній 15-кандидатний cohort

Для попереднього cohort пошук, hard-filter, deep audit і ranked execution
завершені. Етапи, дозволені лише після успішного published-result gate, не
починалися.

- **EU-001, rank 1, score 79.** Structural, deterministic і 50-run protocol
  checks пройдені; adaptive locus якісно перевершив fixed baseline у п'яти N=64
  умовах. Лише 5/10 Table 1 cells витримали 5% rule, а три source-grounded
  diagnostics не усунули розбіжність без довільного fitting.
- **USA-001, rank 2, score 77.** Primary і Q1-Q3 дали 9/10 perfect. Run 8
  лишився ненульовим до generation 100000, тому P2 і P4 провалені. Q2 та Q3
  окремо узгодили recovery statistic, але не exact-fit P2/P4.
- Це негативний результат відтворення, а не спростування статей: доступних
  artifacts недостатньо, щоб відтворити required published-result gates без
  outcome-informed припущень.

Канонічні джерела попереднього стану:

- [реєстр](registry/README.md);
- [execution outcomes](registry/attempt_outcomes.md);
- [Failure Log](failure_logs/Failure_Log.csv);
- [USA-001 audit](failure_logs/USA-001_primary_failure.md).

Failed-candidate directories попереднього етапу видалено лише після зовнішнього
логування. EU26-21 є окремим наступним дослідженням і не змінює вже зафіксовані
outcomes cohort.

## Evidence та обмеження

- USA-001 має manifest-listed evidence з byte lengths і SHA-256, run ledgers,
  gate tables та provenance, але bundle навмисно не містить implementation,
  instance MAT-файлів, великих generation/event ledgers або copied upstream
  sources.
- Для EU-001 залишилися narrative failure record і рядок загального log. Raw
  runs, tests, source mirror, outputs і повний hash inventory не збережені, тому
  5/10 не можна незалежно перерахувати з raw rows цього репозиторію.
- EU26-21 source-compatible profile не доводить тотожність printed Algorithm 1
  та public code.
- EU26-21 corrected profile є одним Census dataset protocol і не доводить
  universal generalization.
- Logical NFE не є автоматично wall-clock speedup.
- `old/` є архівом попередніх проєктів. `sandbox/results/` містить generated
  artifacts, і Git його ігнорує.

Деталі evidence попереднього cohort:
[failure_logs/README.md](failure_logs/README.md).

## Поточне рішення

Для EU26-21 завершено нову підтверджувальну кампанію та повторну перевірку
трьох окремих профілів. Seeds, margins, budgets, objectives, rows і наукові
рішення не змінюються. Залишено видимими negative/null outcomes і
nonblocking historical lint findings та повідомлення `PYSEC-2024-110` у
старому `scikit-learn==1.2.2`; modern corrected dependency gate зелений.
Описові таблиці й графіки сформовано
лише з уже зафіксованих artifacts через analysis-only CI. Звіт містить
математичну модель, верифікацію, результати, обмеження та evidence links.
Для інституційного оформлення повного рукопису лишаються потрібними вимоги
кафедри й титульні реквізити; безстрокове сховище artifacts не налаштовано.

Новий bridge не перезаписує історичні artifacts і не є повним друкованим
CHC-QX. Фінальний науковий висновок залишається негативним щодо joint claim;
його не виправляють підбором порогів або вилученням seed. PR19 лишається draft,
merge без окремої вказівки не виконується.

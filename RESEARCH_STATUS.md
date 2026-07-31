# Стан дослідження

Дата зрізу: 31 липня 2026 року.

## Поточний етап

Поточний 15-кандидатний cohort вичерпано без успішної числової
реплікації. Пошук, hard-filter, deep audit і ranked execution завершені.
Етапи, дозволені лише після успішного published-result gate, не
починалися.

| Етап | Стан | Результат |
|---|---|---|
| Пошук | Завершено | 15 кандидатів: 7 EU + 8 USA |
| Eligibility / deep audit | Завершено | 2 `hard_pass`, 3 `conditional_noneligible`, 10 `hard_fail` |
| Ranked execution | Завершено | 2/2 eligible виконані, обидва numerical FAIL |
| Fixed-GA comparison / ablations | Не розпочато | Заблоковано published-result gate |
| 18-sheet workbook / success package | Не створено | Заблоковано тим самим gate |
| Активна candidate implementation | Відсутня | Є лише prospective verification harness |

Канонічні джерела стану: [реєстр](registry/README.md),
[execution outcomes](registry/attempt_outcomes.md) і
[Failure Log](failure_logs/Failure_Log.csv).

## Що встановлено

- **EU-001, rank 1, score 79.** Structural, deterministic і 50-run
  protocol checks пройдені; adaptive locus якісно перевершив fixed
  baseline у п'яти N=64 умовах. Лише 5/10 Table 1 cells витримали 5%
  rule, а три source-grounded diagnostics не усунули розбіжність без
  довільного fitting.
- **USA-001, rank 2, score 77.** Primary і Q1–Q3 дали 9/10 perfect.
  Run 8 лишився ненульовим до generation 100000, тому P2 (10/10 by
  2000) і P4 (усі terminal objectives у межах `1e-12`) провалені. Q2
  та Q3 окремо узгодили recovery statistic, але не exact-fit P2/P4.
- Це негативний результат відтворення, а не спростування статей:
  доступних artifacts недостатньо, щоб відтворити required
  published-result gates без outcome-informed припущень.

## Evidence та обмеження

- USA-001 має 25 manifest-listed evidence files із перевірюваними byte
  lengths і SHA-256 плюс сам `evidence_manifest.csv`, а також run
  ledgers, gate tables та provenance.
- USA bundle навмисно не містить implementation, instance MAT-файлів,
  великих generation/event ledgers або copied upstream sources.
  `source_manifest.md` усередині bundle є історичним описом видаленого
  source archive, а не переліком поточних локальних файлів.
- Для EU-001 залишилися детальний narrative failure record і рядок
  загального log. Raw runs, tests, source mirror, outputs і повний hash
  inventory не збережені, тому результат 5/10 не можна незалежно
  перерахувати з raw rows цього репозиторію.
- `old/` є архівом попередніх проєктів. `sandbox/results/` містить
  generated artifacts, і Git його ігнорує.

Деталі меж evidence: [failure_logs/README.md](failure_logs/README.md).

## Що ще треба дізнатися

Для причин уже зафіксованих невдач:

- EU-001: original sweep driver, точну Table 1 population
  interpretation, author seeds/raw runs/environment і profile, який
  фактично створив таблицю;
- USA-001: author seeds/RNG, generated networks/weights/opinions,
  initial populations, study driver, check placement, exact graph
  library/degree-mapping/rejection semantics, dependency versions та
  окремий data-license status архівних result CSV.

Для можливого наступного кандидата:

- **EU-006:** підтвердити upstream provenance та license конкретного
  biomedical dataset, а потім розв'язати rounding/update-timing і
  runnable-pipeline blockers та отримати seeds/raw stochastic logs;
- **USA-005:** отримати самодостатню adaptation specification, controls,
  legal inputs і seeds;
- **USA-006:** отримати exact dynamic-rate function/bounds, доказ
  щонайменше 11 active route genes, matrices, implementation і seeds.

## Наступне рішення

У поточному registry немає кандидата, якого можна чесно почати
реалізовувати. Спочатку потрібно обрати: завершити цей cohort як
задокументований negative result або авторизувати новий search cohort.
Якщо дослідження продовжується:

1. виконати пріоритетну legal-provenance перевірку dataset для EU-006;
2. якщо EU-006 не стає eligible, відкрити новий literature cohort без
   послаблення критеріїв і наперед зафіксувати quota та stopping rule
   (перший `PASS_FULL` або вичерпання preregistered eligible candidates);
3. до перегляду outcomes зафіксувати source revision, data hashes,
   numerical endpoints, seeds, adapter source manifest і immutable
   adapter configuration;
4. під'єднати нового кандидата до
   [staged harness](verification/README.md);
5. запускати baseline, ablations і workbook лише після `PASS_FULL`.

Відновлення видалених candidate folders із backup може покращити
auditability, але не повинно змінювати вже зафіксований failed outcome.
